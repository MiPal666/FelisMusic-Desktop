"""Cast -> Cast/group handoff, without real receivers or account access."""
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch
from test_cast_output import CastOutputFixture
from felismusic_gui import backend
from felismusic_gui.cast_output import CastOutput, CastController


class CastSwitchTests(CastOutputFixture):
    def setUp(self):
        super().setUp()
        self.target_status=SimpleNamespace(content_id='',media_session_id=None,player_state='IDLE',
                                          idle_reason='',adjusted_current_time=0,duration=180)
        self.target_mc=Mock();self.target_mc.status=self.target_status
        self.target_mc.play_media.side_effect=self.load_target
        self.target_mc.launch.side_effect=lambda **kw:kw['callback_function'](True,{'type':'RECEIVER_STATUS'})
        self.target_mc.stop.side_effect=lambda **kw:self.stop_target()
        self.target_mc.pause.side_effect=lambda:setattr(self.target_status,'player_state','PAUSED')
        self.target_mc.play.side_effect=lambda:setattr(self.target_status,'player_state','PLAYING')
        self.target=Mock();self.target.is_local=False
        # Same names must still identify distinct receivers by UUID.
        self.target.cast_info=SimpleNamespace(uuid='speaker2',friendly_name='Speaker',cast_type='audio')
        self.target.media_controller=self.target_mc
        self.target.status=SimpleNamespace(volume_level=.6,volume_muted=False)
        self.target.wait.side_effect=lambda **kw:self.events.append('target-ready')
        self.target.set_volume.side_effect=lambda v:v
        self.target.set_volume_muted.side_effect=lambda v:None
        self.scanner.resolve.side_effect=lambda device_id:{'speaker':self.cast,'speaker2':self.target}[device_id]
        self.b._cast_devices.append(dict(id='speaker2',name='Speaker',kind='audio'))

    def load_target(self,url,content_type,**kwargs):
        self.events.append('target-load');self.target_status.content_id=url
        self.target_status.media_session_id=2;self.target_status.idle_reason=''
        self.target_status.player_state='PLAYING' if kwargs['autoplay'] else 'PAUSED'
        self.target_status.adjusted_current_time=kwargs['current_time']
        kwargs['callback_function'](True,{})

    def stop_target(self):
        self.events.append('target-stop');self.target_status.player_state='IDLE'
        self.target_status.media_session_id=None

    def switch_target(self):
        self.assertTrue(self.b.selectCastOutput('speaker2'))
        self.until(lambda:not self.b._output_switching)

    def test_playing_switch_preserves_occurrence_repeat_and_samples_position_after_stream(self):
        self.start('A','B','A');self.b._queue.index=2;self.b._set_player_from_queue()
        self.b._repeat_mode='one';self.switch();queue=self.b._queue;current=queue.current()
        played=list(self.played);self.events.clear()
        def stream(vid,mc):self.remote_status.adjusted_current_time=72;return self.stream(vid,mc)
        self.stream_call.side_effect=stream
        with patch.object(backend.core,'get_local_audio_source',side_effect=AssertionError('local download')):
            self.switch_target()
        self.assertEqual(self.events,['target-ready','stream','cast-stop','target-load'])
        self.assertIs(self.b._queue,queue);self.assertIs(queue.current(),current)
        self.assertEqual(queue.index,2);self.assertEqual(self.b.playerRepeatMode,'one')
        self.assertEqual(self.b.playerPosition,72);self.assertEqual(self.played,played)
        self.assertEqual(self.target_mc.play_media.call_args.kwargs['current_time'],72)
        self.assertEqual(self.b.castState['currentId'],'speaker2');self.assertEqual(self.b.playerVolume,60)
        self.assertFalse(self.b.playerMuted);self.until(lambda:self.cast.disconnect.called)
        self.target.disconnect.assert_not_called();self.remote.stop.assert_called_once()
        self.target_mc.launch.assert_not_called()

    def test_paused_switch_and_controls_next_eos_repeat_stay_on_target(self):
        self.start('A','B','C');self.switch();self.remote_status.player_state='PAUSED'
        self.remote_status.adjusted_current_time=42;self.b._player_state='paused'
        self.switch_target();self.assertFalse(self.target_mc.play_media.call_args.kwargs['autoplay'])
        self.assertEqual(self.b.playerState,'paused');self.assertEqual(self.b.playerPosition,42)
        self.b.togglePlayPause();self.target_mc.play.assert_called_once();self.remote.play.assert_not_called()
        self.b.togglePlayPause();self.target_mc.pause.assert_called_once()
        self.b.seekTo(55);self.target_mc.seek.assert_called_once_with(55,timeout=3)
        self.b.setVolume(25);self.target.set_volume.assert_called_once_with(.25)
        self.b.toggleMute();self.target.set_volume_muted.assert_called_once_with(True)
        self.b.nextTrack();self.until(lambda:self.b.playerTitle=='B' and self.b.playerState=='playing')
        self.target_status.player_state='IDLE';self.target_status.idle_reason='FINISHED';self.b._poll_player()
        self.until(lambda:self.b.playerTitle=='C' and self.b.playerState=='playing')
        self.b._repeat_mode='one';self.target_status.player_state='IDLE';self.target_status.idle_reason='FINISHED'
        self.b._poll_player();self.until(lambda:not self.b._playback_transitioning)
        self.assertEqual(self.target_status.content_id,'https://audio.invalid/C')
        self.assertEqual(self.remote.play_media.call_count,1)

    def test_group_switch_and_back_use_exact_ids_and_disconnect_without_extra_stop(self):
        self.target.cast_info.cast_type='group';self.target.cast_info.friendly_name='Music'
        self.b._cast_devices[1].update(name='Music',kind='group')
        self.start('A');self.switch();self.switch_target()
        self.assertEqual(self.b.outputName,'Music');self.until(lambda:self.cast.disconnect.called)
        self.assertTrue(self.b.selectCastOutput('speaker'));self.until(lambda:not self.b._output_switching)
        self.until(lambda:self.target.disconnect.called)
        self.assertEqual(self.b.castState['currentId'],'speaker')
        self.assertEqual(self.scanner.resolve.call_args_list[-2].args,('speaker2',))
        self.assertEqual(self.scanner.resolve.call_args_list[-1].args,('speaker',))
        self.remote.stop.assert_called_once();self.target_mc.stop.assert_called_once()

    def test_idle_switch_has_no_load_and_first_play_uses_target(self):
        self.switch();self.switch_target();self.until(lambda:self.cast.disconnect.called)
        self.target_mc.play_media.assert_not_called();self.remote.stop.assert_not_called()
        self.assertEqual(self.b.playerState,'idle');self.assertFalse(self.played)
        self.start('A');self.assertEqual(self.target_status.content_id,'https://audio.invalid/A')
        self.assertFalse(self.played)

    def test_connect_failure_keeps_source_playing_without_stopping_target(self):
        self.start('A');self.switch();self.target.wait.side_effect=RuntimeError('network')
        self.switch_target();self.assertEqual(self.b.castState['currentId'],'speaker')
        self.assertEqual(self.b.playerState,'playing');self.remote.stop.assert_not_called()
        self.target_mc.stop.assert_not_called();self.target.disconnect.assert_called_once()
        self.cast.disconnect.assert_not_called()

    def test_stream_failure_does_not_stop_old_target_content_or_source(self):
        self.start('A');self.switch();self.stream_call.side_effect=RuntimeError('PRIVATE_URL')
        self.target_status.media_session_id=7;self.target_status.player_state='PLAYING'
        self.switch_target();self.remote.stop.assert_not_called();self.target_mc.stop.assert_not_called()
        self.assertEqual(self.b.castState['currentId'],'speaker');self.assertNotIn('PRIVATE',self.errors[-1])

    def test_unconfirmed_source_stop_never_loads_target(self):
        self.start('A');self.switch();self.remote.stop.side_effect=RuntimeError('network')
        self.switch_target();self.target_mc.play_media.assert_not_called()
        self.assertEqual(self.b.castState['currentId'],'speaker');self.cast.disconnect.assert_not_called()
        self.target.disconnect.assert_called_once()

    def test_rejected_load_stops_target_then_restores_source_pause_and_position(self):
        self.start('A');self.switch();self.remote_status.player_state='PAUSED'
        self.remote_status.adjusted_current_time=42;self.b._player_state='paused'
        self.target_status.media_session_id=7;self.events.clear()
        self.target_mc.play_media.side_effect=lambda *a,**kw:kw['callback_function'](False,{})
        with patch.object(backend.core,'get_local_audio_source',side_effect=AssertionError('local rollback')):
            self.switch_target()
        self.assertLess(self.events.index('target-stop'),self.events.index('cast-load'))
        self.assertEqual(self.remote.play_media.call_args.kwargs['current_time'],42)
        self.assertFalse(self.remote.play_media.call_args.kwargs['autoplay'])
        self.assertEqual(self.b.playerState,'paused');self.assertEqual(self.b.castState['currentId'],'speaker')
        self.assertFalse(self.recoveries);self.cast.disconnect.assert_not_called()

    def test_failed_target_stop_never_restarts_source_in_parallel(self):
        self.start('A');self.switch();self.target_status.media_session_id=7
        self.target_mc.play_media.side_effect=lambda *a,**kw:kw['callback_function'](False,{})
        self.target_mc.stop.side_effect=RuntimeError('network');self.switch_target()
        self.assertEqual(self.remote.play_media.call_count,1);self.assertEqual(self.b.playerState,'idle')
        self.assertEqual(self.b.castState['currentId'],'speaker')

    def test_stop_during_stream_preparation_cancels_target_and_keeps_selected_source(self):
        self.start('A');self.switch();entered=Event()
        def blocked(vid,mc):entered.set();self.release.wait(3);return self.stream(vid,mc)
        self.stream_call.side_effect=blocked
        self.assertTrue(self.b.selectCastOutput('speaker2'));self.until(entered.is_set)
        self.b.stopPlayback();self.assertFalse(self.b.selectCastOutput('speaker2'));self.release.set()
        self.until(lambda:not self.b._output_result_pending)
        self.target_mc.play_media.assert_not_called();self.target.disconnect.assert_called_once()
        self.assertEqual(self.b.playerState,'idle');self.assertEqual(self.b.castState['currentId'],'speaker')

    def test_late_target_result_blocks_next_switch_until_cleanup_acknowledged(self):
        self.start('A');self.switch();generation=self.b._playback_generation
        self.b.stopPlayback();entered=Event();self.target_status.media_session_id=7
        def blocked_stop(**kw):entered.set();self.release.wait(3);self.stop_target()
        self.target_mc.stop.side_effect=blocked_stop;self.b._output_result_pending=True
        self.b._apply_output_switch(generation,dict(output=CastOutput(self.target),active=True))
        self.until(entered.is_set);self.assertFalse(self.b.castState['canSelect'])
        self.assertFalse(self.b.selectCastOutput('speaker2'));self.release.set()
        self.until(lambda:not self.b._output_result_pending)
        self.target.disconnect.assert_called_once();self.assertEqual(self.b.castState['currentId'],'speaker')

    def test_same_receiver_and_missing_id_are_rejected_without_connection(self):
        self.switch();calls=self.scanner.resolve.call_count
        self.assertFalse(self.b.selectCastOutput('speaker'));self.assertFalse(self.b.selectCastOutput('missing'))
        self.assertEqual(self.scanner.resolve.call_count,calls)

    def test_target_disappears_after_scan_without_interrupting_source(self):
        self.start('A');self.switch()
        self.scanner.resolve.side_effect=RuntimeError('missing UUID')
        self.switch_target();self.remote.stop.assert_not_called()
        self.cast.disconnect.assert_not_called();self.target_mc.play_media.assert_not_called()
        self.assertEqual(self.b.castState['currentId'],'speaker');self.assertEqual(self.b.playerState,'playing')

    def test_shutdown_during_target_load_stops_and_disconnects_both_owned_connections(self):
        self.start('A');self.switch()
        def load(*args,**kwargs):
            self.load_target(*args,**kwargs);self.b.shutdown()
        self.target_mc.play_media.side_effect=load
        self.assertTrue(self.b.selectCastOutput('speaker2'))
        self.until(lambda:self.target.disconnect.called)
        self.assertEqual(self.target_status.player_state,'IDLE');self.assertEqual(self.remote_status.player_state,'IDLE')
        self.cast.disconnect.assert_called_once();self.target.disconnect.assert_called_once()
        self.assertEqual(self.remote.play_media.call_count,1);self.assertFalse(self.recoveries)

    def test_group_member_starts_independent_receiver_after_group_stop_before_load(self):
        self.cast.cast_info.cast_type='group';self.start('A');self.switch()
        self.remote_status.adjusted_current_time=42;self.remote_status.player_state='PAUSED';self.b._player_state='paused'
        self.events.clear();independent=Event()
        def launch(**kwargs):
            self.assertIn('cast-stop',self.events);self.events.append('receiver-launch')
            self.assertTrue(kwargs['force_launch']);independent.set()
            kwargs['callback_function'](True,{'type':'RECEIVER_STATUS'})
        def load(*args,**kwargs):
            self.assertTrue(independent.is_set());self.load_target(*args,**kwargs)
        self.target_mc.launch.side_effect=launch;self.target_mc.play_media.side_effect=load
        self.switch_target()
        self.assertLess(self.events.index('cast-stop'),self.events.index('receiver-launch'))
        self.assertLess(self.events.index('receiver-launch'),self.events.index('target-load'))
        self.assertEqual(self.b.castState['currentId'],'speaker2');self.assertEqual(self.b.playerState,'paused')
        self.assertEqual(self.target_mc.play_media.call_args.kwargs['current_time'],42)
        self.assertFalse(self.target_mc.play_media.call_args.kwargs['autoplay'])

    def test_failed_independent_receiver_restores_group_without_target_load(self):
        self.cast.cast_info.cast_type='group';self.start('A');self.switch()
        self.remote_status.adjusted_current_time=42
        self.target_mc.launch.side_effect=lambda **kw:kw['callback_function'](False,{'type':'LAUNCH_ERROR'})
        self.switch_target();self.target_mc.play_media.assert_not_called()
        self.assertEqual(self.b.castState['currentId'],'speaker');self.assertEqual(self.b.playerState,'playing')
        self.assertEqual(self.remote.play_media.call_args.kwargs['current_time'],42)

    def test_stop_while_receiver_launch_is_pending_never_loads_after_late_callback(self):
        self.cast.cast_info.cast_type='group';self.start('A');self.switch();entered=Event();callbacks=[]
        def launch(**kw):callbacks.append(kw['callback_function']);entered.set()
        self.target_mc.launch.side_effect=launch
        self.assertTrue(self.b.selectCastOutput('speaker2'));self.until(entered.is_set)
        self.b.stopPlayback();callbacks[0](True,{'type':'RECEIVER_STATUS'})
        self.until(lambda:not self.b._output_result_pending)
        self.target_mc.play_media.assert_not_called();self.target.disconnect.assert_called_once()
        self.assertEqual(self.remote.play_media.call_count,1);self.assertEqual(self.b.playerState,'idle')

    def test_independent_receiver_launch_timeout_is_reported(self):
        self.target_mc.launch.side_effect=None
        with self.assertRaisesRegex(RuntimeError,'včas'):
            CastController(self.target_mc).start_receiver(timeout=.01)

    def test_idle_group_to_member_prepares_receiver_without_starting_audio(self):
        self.cast.cast_info.cast_type='group';self.switch();self.switch_target()
        self.target_mc.launch.assert_called_once()
        self.assertTrue(self.target_mc.launch.call_args.kwargs['force_launch'])
        self.target_mc.play_media.assert_not_called();self.assertEqual(self.b.playerState,'idle')

    def test_rejected_load_response_is_not_treated_as_successful_ack(self):
        def rejected(*args,**kwargs):kwargs['callback_function'](True,{'type':'LOAD_FAILED'})
        self.target_mc.play_media.side_effect=rejected;controller=CastController(self.target_mc)
        controller.play_media('https://audio.invalid/A','audio/mp4')
        with self.assertRaisesRegex(RuntimeError,'odmítl'):
            controller.block_until_active(timeout=.1)

    def test_load_diagnostics_do_not_expose_url_or_unexpected_response_fields(self):
        controller=CastController(self.target_mc);trace=Mock()
        def accepted(url,content_type,**kwargs):
            self.target_status.content_id=url;self.target_status.player_state='PRIVATE_STATUS'
            self.target_status.idle_reason='PRIVATE_REASON'
            kwargs['callback_function'](True,{'type':'PRIVATE_RESPONSE','url':url})
        self.target_mc.play_media.side_effect=accepted
        controller.play_media('https://PRIVATE_SIGNED_URL/A','audio/mp4')
        with patch('felismusic_gui.cast_output.current_trace',return_value=trace):
            with self.assertRaises(RuntimeError):controller.block_until_active(timeout=.01)
        trace.event.assert_called()
        self.assertNotIn('PRIVATE',str(trace.event.call_args_list))
