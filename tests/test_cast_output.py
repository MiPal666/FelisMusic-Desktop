"""Local -> Cast transport, exact queue/position and rollback without real devices."""
from types import SimpleNamespace
from threading import Event
from unittest.mock import Mock, patch
import test_prefetch as support
from felismusic_gui.cast_output import CastController


class CastOutputFixture(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp();self.events=[];self.recoveries=[]
        self.remote_status=SimpleNamespace(content_id='',media_session_id=None,player_state='IDLE',idle_reason='',
                                           adjusted_current_time=0,duration=180)
        self.remote=Mock();self.remote.status=self.remote_status
        self.remote.play_media.side_effect=self.load_remote
        self.remote.launch.side_effect=lambda **kw:kw['callback_function'](True,{'type':'RECEIVER_STATUS'})
        self.remote.stop.side_effect=lambda **kw:self.stop_remote()
        self.remote.pause.side_effect=lambda:setattr(self.remote_status,'player_state','PAUSED')
        self.remote.play.side_effect=lambda:setattr(self.remote_status,'player_state','PLAYING')
        self.cast=Mock();self.cast.is_local=False;self.cast.cast_info=SimpleNamespace(uuid='speaker',friendly_name='Speaker',cast_type='audio')
        self.cast.media_controller=self.remote;self.cast.status=SimpleNamespace(volume_level=.35,volume_muted=True)
        self.cast.wait.side_effect=lambda **kw:self.events.append('ready')
        self.cast.set_volume.side_effect=lambda v:self.volume(v)
        self.cast.set_volume_muted.side_effect=lambda v:setattr(self.cast.status,'volume_muted',v)
        self.scanner=Mock();self.scanner.resolve.return_value=self.cast
        self.b._cast_discovery=self.scanner;self.b._cast_devices=[dict(id='speaker',name='Speaker',kind='audio')]
        self.mc.play_media_at=self.restore_local
        p=patch.object(support.core,'get_playback_source',side_effect=self.stream);self.stream_call=p.start();self.addCleanup(p.stop)
        p=patch.object(support.core,'get_media_position',side_effect=lambda mc:float(mc.status.adjusted_current_time))
        p.start();self.addCleanup(p.stop)

    def volume(self,value):self.cast.status.volume_level=value;return value
    def stream(self,video_id,mc):self.events.append('stream');return 'https://audio.invalid/'+video_id,'audio/mp4'
    def load_remote(self,url,content_type,**kwargs):
        self.events.append('cast-load');self.remote_status.content_id=url;self.remote_status.media_session_id=1
        self.remote_status.player_state='PLAYING' if kwargs['autoplay'] else 'PAUSED'
        self.remote_status.adjusted_current_time=kwargs['current_time'];self.remote_status.idle_reason=''
        kwargs['callback_function'](True,{})
    def stop_remote(self):self.events.append('cast-stop');self.remote_status.player_state='IDLE'
    def restore_local(self,url,content_type,**kwargs):
        self.events.append('local-restore');self.recoveries.append((kwargs['position'],kwargs['paused']))
        self.play_media(url,content_type,**kwargs)
        self.status.player_state='PAUSED' if kwargs['paused'] else 'PLAYING'
        self.status.adjusted_current_time=kwargs['position']
    def switch(self):
        self.assertTrue(self.b.selectCastOutput('speaker'));self.until(lambda:not self.b._output_switching)


class CastOutputTests(CastOutputFixture):
    def test_playing_handoff_keeps_exact_occurrence_queue_repeat_and_samples_position_after_stream(self):
        self.start('A','B','A');self.b._queue.index=2;self.b._set_player_from_queue();self.b._repeat_mode='one'
        queue=self.b._queue;current=queue.current();played=list(self.played)
        self.b._player_position=42;self.status.adjusted_current_time=42
        def stream(vid,mc):self.status.adjusted_current_time=48;return self.stream(vid,mc)
        self.stream_call.side_effect=stream
        original_stop=self.mc.stop
        def stop(**kwargs):self.events.append('local-stop');return original_stop(**kwargs)
        with patch.object(self.mc,'stop',side_effect=stop):self.switch()
        self.assertEqual(self.events,['ready','stream','local-stop','cast-load'])
        self.assertIs(self.b._queue,queue);self.assertIs(queue.current(),current);self.assertEqual(queue.index,2)
        self.assertEqual(self.b.playerPosition,48);self.assertEqual(self.b.playerRepeatMode,'one')
        self.assertEqual(self.played,played);self.assertEqual(self.remote.play_media.call_args.kwargs['current_time'],48)
        self.assertTrue(self.remote.play_media.call_args.kwargs['autoplay']);self.assertEqual(self.b.outputName,'Speaker')
        self.assertEqual(self.b.castState['currentId'],'speaker');self.assertTrue(self.b.castState['canSelect'])
        self.assertFalse(self.b.selectCastOutput('speaker'))
        self.assertEqual(self.b.playerVolume,35);self.assertTrue(self.b.playerMuted)

    def test_paused_handoff_loads_without_autoplay_and_controls_route_to_cast(self):
        self.start('A','B');self.b._player_state='paused';self.status.player_state='PAUSED'
        self.status.adjusted_current_time=42;self.switch()
        self.assertFalse(self.remote.play_media.call_args.kwargs['autoplay']);self.assertEqual(self.b.playerState,'paused')
        self.b.togglePlayPause();self.remote.play.assert_called_once();self.assertEqual(self.b.playerState,'playing')
        self.b.togglePlayPause();self.remote.pause.assert_called_once()
        self.b.seekTo(55);self.remote.seek.assert_called_once_with(55,timeout=3)
        self.b.setVolume(25);self.assertEqual(self.b.playerVolume,25);self.cast.set_volume.assert_called_once_with(.25)
        self.b.toggleMute();self.assertFalse(self.b.playerMuted);self.cast.set_volume_muted.assert_called_once_with(False)
        self.b.stopPlayback();self.remote.stop.assert_called_once();self.assertEqual(self.b.playerState,'idle')

    def test_next_eos_and_repeat_stay_on_cast_without_local_download_or_prefetch(self):
        self.start('A','B','C');self.switch();downloads=dict(self.downloads);played=list(self.played)
        self.b.nextTrack();self.until(lambda:self.b.playerState=='playing' and self.b.playerTitle=='B')
        self.assertEqual(self.remote_status.content_id,'https://audio.invalid/B')
        self.remote_status.player_state='IDLE';self.remote_status.idle_reason='FINISHED';self.b._poll_player()
        self.until(lambda:self.b.playerState=='playing' and self.b.playerTitle=='C')
        self.b._repeat_mode='one';self.remote_status.player_state='IDLE';self.remote_status.idle_reason='FINISHED'
        self.b._poll_player();self.until(lambda:not self.b._playback_transitioning)
        self.assertEqual(self.remote_status.content_id,'https://audio.invalid/C')
        self.assertEqual(dict(self.downloads),downloads);self.assertEqual(self.played,played)

    def test_idle_selection_does_not_start_media_and_next_new_queue_uses_cast(self):
        self.assertEqual(self.b.outputName,'Toto zařízení');self.switch()
        self.remote.play_media.assert_not_called();self.stream_call.assert_not_called();self.assertEqual(self.b.playerState,'idle')
        self.b._library_items_model.set_items([dict(kind='song',videoId='A',title='A')])
        self.b.playFrom('library',0);self.until(lambda:self.b.playerState=='playing')
        self.assertEqual(self.remote_status.content_id,'https://audio.invalid/A');self.assertFalse(self.played)

    def test_stream_failure_keeps_local_playing_and_does_not_stop_other_media_on_cast(self):
        self.start('A','B');queue=self.b._queue;stops=list(self.stops);self.stream_call.side_effect=RuntimeError('PRIVATE_SIGNED_URL')
        self.switch();self.assertIsNone(self.b._cast_output);self.assertIs(self.b._queue,queue)
        self.assertEqual(self.b.playerState,'playing');self.assertEqual(self.stops,stops)
        self.remote.stop.assert_not_called();self.cast.disconnect.assert_called_once()
        self.assertTrue(self.errors);self.assertNotIn('PRIVATE',self.errors[-1])

    def test_rejected_cast_load_stops_target_before_local_recovery_at_position_and_pause(self):
        self.start('A','B');self.b._player_state='paused';self.status.player_state='PAUSED';self.status.adjusted_current_time=42
        self.remote_status.media_session_id=7
        self.remote.play_media.side_effect=lambda *a,**kw:kw['callback_function'](False,{})
        self.switch();self.assertIsNone(self.b._cast_output);self.assertEqual(self.b.playerState,'paused')
        self.assertEqual(self.recoveries,[(42,True)])
        self.assertLess(self.events.index('cast-stop'),self.events.index('local-restore'))
        self.assertTrue(self.errors)

    def test_failed_target_stop_does_not_restart_local_in_parallel(self):
        self.remote_status.media_session_id=7
        self.start('A','B');self.remote.play_media.side_effect=lambda *a,**kw:kw['callback_function'](False,{})
        self.remote.stop.side_effect=RuntimeError('lost connection');self.switch()
        self.assertFalse(self.recoveries);self.assertEqual(self.b.playerState,'idle');self.assertIsNone(self.b._cast_output)

    def test_stop_during_preparation_cancels_handoff_and_blocks_replacing_queue(self):
        self.start('A','B');entered=Event();queue=self.b._queue
        def blocked(vid,mc):entered.set();self.release.wait(3);return self.stream(vid,mc)
        self.stream_call.side_effect=blocked
        self.assertTrue(self.b.selectCastOutput('speaker'));self.until(entered.is_set)
        self.b.playFrom('library',1);self.assertIs(self.b._queue,queue);self.assertEqual(queue.index,0)
        self.assertFalse(self.b.selectCastOutput('speaker'));self.b.stopPlayback();self.release.set()
        self.until(lambda:self.cast.disconnect.called)
        self.assertIsNone(self.b._cast_output);self.assertEqual(self.b.playerState,'idle');self.assertFalse(self.b.busy)
        self.remote.play_media.assert_not_called();self.remote.stop.assert_not_called()

    def test_load_ack_is_required_even_if_old_cast_session_has_same_url(self):
        controller=CastController(self.remote);self.remote_status.content_id='https://audio.invalid/A'
        self.remote_status.media_session_id=1;self.remote_status.player_state='PLAYING'
        self.remote.play_media.side_effect=None
        controller.play_media('https://audio.invalid/A','audio/mp4')
        with self.assertRaises(RuntimeError):controller.block_until_active(timeout=.01)

    def test_shutdown_stops_and_disconnects_only_selected_cast(self):
        self.start('A');self.switch();self.b.shutdown();self.remote.stop.assert_called_once();self.cast.disconnect.assert_called_once()
        self.assertFalse(self.b.selectCastOutput('speaker'))

    def test_idle_receiver_without_session_allows_first_play_and_play_after_stop(self):
        def stop(**kwargs):
            if self.remote_status.media_session_id is None:
                raise RuntimeError('STOP without media session')
            self.stop_remote();self.remote_status.media_session_id=None
        self.remote.stop.side_effect=stop
        self.switch()
        self.b._library_items_model.set_items([dict(kind='song',videoId='A',title='A')])
        self.b.playFrom('library',0);self.until(lambda:self.b.playerState=='playing')
        self.remote.stop.assert_not_called();self.assertFalse(self.errors)
        self.b.stopPlayback();self.assertIsNone(self.remote_status.media_session_id)
        self.b.playFrom('library',0);self.until(lambda:self.b.playerState=='playing')
        self.remote.stop.assert_called_once();self.assertFalse(self.errors)

    def test_stop_without_session_skips_sdk_rejection(self):
        from pychromecast.controllers.media import MediaController
        raw=MediaController();controller=CastController(raw)
        with patch.object(raw,'stop',wraps=raw.stop) as stop:
            controller.stop()
        stop.assert_not_called()

    def test_stop_with_session_keeps_transport_failure_visible(self):
        self.remote_status.media_session_id=7
        self.remote.stop.side_effect=RuntimeError('lost connection')
        with self.assertRaisesRegex(RuntimeError,'lost connection'):
            CastController(self.remote).stop()
        self.remote.stop.assert_called_once_with(timeout=3)
