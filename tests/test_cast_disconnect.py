"""Connection loss latches, preserves queue and requires explicit recovery."""
from threading import Event, Thread
from types import SimpleNamespace
from unittest.mock import Mock, patch
from test_cast_output import CastOutputFixture
from felismusic_gui import backend


class CastDisconnectTests(CastOutputFixture):
    def lose(self):
        output=self.b._cast_output
        output.new_connection_status(SimpleNamespace(status='CONNECTED'))
        output.new_connection_status(SimpleNamespace(status='LOST'))
        self.b._poll_player()
        return output

    def fresh(self, device_id='speaker'):
        raw=Mock();raw.is_local=False
        raw.cast_info=SimpleNamespace(uuid=device_id,friendly_name='Fresh',cast_type='audio')
        raw.status=SimpleNamespace(volume_level=.5,volume_muted=False)
        status=SimpleNamespace(content_id='',media_session_id=None,player_state='IDLE',idle_reason='',
                               adjusted_current_time=0,duration=180)
        raw.media_controller.status=status
        def load(url,content_type,**kw):
            status.content_id=url;status.media_session_id=3
            status.player_state='PLAYING' if kw['autoplay'] else 'PAUSED'
            kw['callback_function'](True,{'type':'MEDIA_STATUS'})
        raw.media_controller.play_media.side_effect=load
        return raw

    def test_loss_freezes_queue_occurrence_repeat_position_and_stale_eos(self):
        self.start('A','B','A');self.b._queue.index=2;self.b._set_player_from_queue();self.switch()
        self.b._repeat_mode='all';queue=self.b._queue;current=queue.current()
        self.b._player_position=42;played=list(self.played)
        output=self.lose();self.until(lambda:self.cast.disconnect.called)
        for _ in range(3):
            self.remote_status.player_state='IDLE';self.remote_status.idle_reason='FINISHED'
            self.remote_status.adjusted_current_time=180;self.b._poll_player()
        self.assertIs(self.b._queue,queue);self.assertIs(queue.current(),current);self.assertEqual(queue.index,2)
        self.assertEqual(self.b.playerPosition,42);self.assertEqual(self.b.playerRepeatMode,'all')
        self.assertEqual(self.b.playerState,'idle');self.assertFalse(self.b.playbackOutputAvailable)
        self.assertIs(self.b._cast_output,output);self.assertIn('odpojeno',self.b.outputName)
        self.assertFalse(self.b.playerCanSeek);self.assertFalse(self.b.playerCanNext)
        self.assertEqual(self.played,played);self.remote.stop.assert_not_called()
        self.cast.disconnect.assert_called_once()

    def test_return_to_local_after_loss_does_not_play_until_user_requests_it(self):
        self.start('A','B');self.switch();self.b._player_position=42;queue=self.b._queue
        self.lose();self.until(lambda:self.cast.disconnect.called);played=list(self.played)
        with patch.object(backend.core,'get_local_audio_source',side_effect=AssertionError('automatic audio')):
            self.assertTrue(self.b.selectLocalOutput());self.until(lambda:not self.b._output_switching)
        self.assertEqual(self.b.outputName,'Toto zařízení');self.assertIs(self.b._queue,queue)
        self.assertEqual(self.b.playerState,'idle');self.assertEqual(self.b.playerPosition,42)
        self.assertEqual(self.played,played);self.assertFalse(self.recoveries)
        self.b.togglePlayPause();self.until(lambda:self.b.playerState=='playing')
        self.assertEqual(len(self.played),len(played)+1);self.remote.stop.assert_not_called()

    def test_reconnected_socket_and_rediscovery_never_resume_or_clear_loss(self):
        self.start('A');self.switch();output=self.lose();loads=self.remote.play_media.call_count
        output.new_connection_status(SimpleNamespace(status='CONNECTED'))
        self.b._apply_cast_devices(self.b._cast_generation,[dict(id='speaker',name='Speaker',kind='audio')],False,'')
        self.b._poll_player()
        self.assertTrue(self.b.castState['disconnected']);self.assertEqual(self.b.playerState,'idle')
        self.assertEqual(self.remote.play_media.call_count,loads);self.assertFalse(self.b.playbackOutputAvailable)

    def test_explicit_same_uuid_reconnect_creates_new_connection_without_autoplay(self):
        self.start('A');self.switch();old=self.lose();self.until(lambda:self.cast.disconnect.called)
        fresh=self.fresh();self.scanner.resolve.return_value=fresh
        self.assertTrue(self.b.castState['canReconnect']);self.assertTrue(self.b.selectCastOutput('speaker'))
        self.until(lambda:not self.b._output_switching)
        self.assertIsNot(self.b._cast_output,old);self.assertFalse(self.b.castState['disconnected'])
        self.assertEqual(self.b.playerState,'idle');fresh.media_controller.play_media.assert_not_called()
        self.b.togglePlayPause();self.until(lambda:self.b.playerState=='playing')
        fresh.media_controller.play_media.assert_called_once()

    def test_explicit_other_cast_after_loss_does_not_stop_lost_cast_or_play_automatically(self):
        self.start('A');self.switch();self.lose();fresh=self.fresh('other')
        self.scanner.resolve.return_value=fresh;self.b._cast_devices.append(dict(id='other',name='Fresh',kind='audio'))
        with patch.object(backend.core,'get_local_audio_source',side_effect=AssertionError('local download')):
            self.assertTrue(self.b.selectCastOutput('other'));self.until(lambda:not self.b._output_switching)
        self.assertEqual(self.b.castState['currentId'],'other');self.assertEqual(self.b.playerState,'idle')
        self.remote.stop.assert_not_called();fresh.media_controller.play_media.assert_not_called()

    def test_stale_discovery_removal_does_not_disconnect_healthy_playing_cast(self):
        self.start('A');self.switch()
        self.b._apply_cast_devices(self.b._cast_generation,[],False,'');self.b._poll_player()
        self.assertFalse(self.b.castState['disconnected']);self.assertEqual(self.b.playerState,'playing')
        self.assertTrue(any(row['id']=='speaker' for row in self.b.castState['devices']))
        self.cast.disconnect.assert_not_called()

    def test_offline_selection_remains_visible_after_discovery_removal(self):
        self.start('A');self.switch();self.lose()
        self.b._apply_cast_devices(self.b._cast_generation,[],False,'')
        self.assertTrue(any(row['id']=='speaker' for row in self.b.castState['devices']))
        self.assertFalse(self.b.castState['canReconnect']);self.assertTrue(self.b.castState['canReturn'])
        self.assertFalse(self.b.selectCastOutput('speaker'))

    def test_loss_during_audio_preparation_never_skips_the_remaining_queue(self):
        self.start('A','B','C');self.switch();entered=Event()
        self.b._playback_executor.submit(lambda:None).result(timeout=4)
        self.b._cast_streams.clear()
        def blocked(vid,mc):entered.set();self.release.wait(3);return self.stream(vid,mc)
        self.stream_call.side_effect=blocked;loads=self.remote.play_media.call_count
        self.b.nextTrack();self.until(entered.is_set);self.lose();self.release.set()
        self.b._playback_executor.submit(lambda:None).result(timeout=4);self.app.processEvents()
        self.assertEqual(self.b._queue.index,1);self.assertEqual(self.b.playerTitle,'B')
        self.assertEqual(self.remote.play_media.call_count,loads);self.assertEqual(self.b.playerState,'idle')

    def test_loss_during_switch_cancels_candidate_and_releases_busy(self):
        self.start('A');self.switch();fresh=self.fresh('other');entered=Event()
        def wait(**kw):entered.set();self.release.wait(3)
        fresh.wait.side_effect=wait;self.scanner.resolve.return_value=fresh
        self.b._cast_devices.append(dict(id='other',name='Fresh',kind='audio'))
        self.assertTrue(self.b.selectCastOutput('other'));self.until(entered.is_set)
        self.lose();self.assertFalse(self.b.busy);self.release.set()
        self.until(lambda:not self.b._output_result_pending)
        fresh.media_controller.play_media.assert_not_called();fresh.disconnect.assert_called_once()
        self.assertEqual(self.b.castState['currentId'],'speaker');self.assertTrue(self.b.castState['disconnected'])

    def test_old_connection_callback_after_switch_has_no_effect_on_new_output(self):
        self.start('A');self.switch();old=self.b._cast_output
        self.assertTrue(self.b.selectLocalOutput());self.until(lambda:not self.b._output_switching)
        old.new_connection_status(SimpleNamespace(status='LOST'));self.b._poll_player()
        self.assertEqual(self.b.outputName,'Toto zařízení');self.assertEqual(self.b.playerState,'playing')
        self.assertFalse(self.b.castState['disconnected'])

    def test_transport_commands_are_blocked_without_mutating_lost_queue(self):
        self.start('A','B');self.switch();self.lose();queue=self.b._queue
        self.b.togglePlayPause();self.b.nextTrack();self.b.previousTrack();self.b.seekTo(70)
        self.b.setVolume(20);self.b.toggleMute();self.b.stopPlayback();self.b.playFrom('library',1)
        self.assertIs(self.b._queue,queue);self.assertEqual(queue.index,0)
        self.remote.play.assert_not_called();self.remote.pause.assert_not_called();self.remote.seek.assert_not_called()
        self.remote.stop.assert_not_called();self.cast.set_volume.assert_not_called();self.cast.set_volume_muted.assert_not_called()

    def test_empty_queue_loss_and_paused_loss_are_detected(self):
        self.switch();self.lose();self.assertTrue(self.b.castState['disconnected'])
        self.assertTrue(self.b.selectLocalOutput());self.until(lambda:not self.b._output_switching)
        self.scanner.resolve.return_value=self.fresh();self.start('A');self.switch()
        self.b._player_state='paused';self.lose();self.assertEqual(self.b.playerState,'idle')
        self.assertEqual(self.b.playerTitle,'A')

    def test_socket_thread_only_sets_latch_until_qt_poll_and_shutdown_disconnects_once(self):
        self.start('A');self.switch();output=self.b._cast_output
        listener=self.cast.register_connection_listener.call_args.args[0];self.assertIs(listener,output)
        thread=Thread(target=listener.new_connection_status,args=(SimpleNamespace(status='LOST'),))
        thread.start();thread.join();self.assertFalse(self.b._cast_lost)
        self.b._poll_player();self.until(lambda:self.cast.disconnect.called);self.b.shutdown()
        self.cast.disconnect.assert_called_once();self.assertEqual(self.b.playerState,'idle')

    def test_loss_clears_radio_waiting_and_invalidates_pending_refill(self):
        self.start('A');self.switch();self.b._queue.radio_active=True
        self.b._radio_waiting_for_tracks=self.b._queue;revision=self.b._radio_refill_revision
        self.lose();self.assertIsNone(self.b._radio_waiting_for_tracks)
        self.assertGreater(self.b._radio_refill_revision,revision)
        self.assertFalse(self.b._maybe_refill_radio())
