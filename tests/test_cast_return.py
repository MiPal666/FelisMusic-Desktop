"""Cast -> local handoff with mocked devices, cache and failure recovery."""
from threading import Event
from unittest.mock import Mock, patch
from test_cast_output import CastOutputFixture
from felismusic_gui import backend


class CastReturnTests(CastOutputFixture):
    def return_local(self):
        self.assertTrue(self.b.selectLocalOutput())
        self.until(lambda:not self.b._output_switching)

    def test_playing_return_keeps_exact_queue_repeat_and_late_position(self):
        self.start('A','B','A');self.b._queue.index=2;self.b._set_player_from_queue()
        self.b._repeat_mode='one';self.switch()
        queue=self.b._queue;current=queue.current();self.events.clear()
        def prepared(*args,**kwargs):
            self.events.append('local-prepared');self.remote_status.adjusted_current_time=61
            return 'file:///tmp/A.m4a','audio/mp4'
        with patch.object(backend.core,'get_local_audio_source',side_effect=prepared):
            self.return_local()
        self.assertEqual(self.events,['local-prepared','cast-stop','local-restore'])
        self.assertIs(self.b._queue,queue);self.assertIs(queue.current(),current)
        self.assertEqual(queue.index,2);self.assertEqual(self.b.playerRepeatMode,'one')
        self.assertEqual(self.recoveries,[(61,False)]);self.assertEqual(self.b.playerPosition,61)
        self.assertEqual(self.b.outputName,'Toto zařízení');self.assertEqual(self.b.playerState,'playing')
        self.until(lambda:self.cast.disconnect.called)
        self.assertTrue(self.b.castState['canSelect']);self.assertFalse(self.b.castState['canReturn'])

    def test_paused_return_restores_local_volume_and_transport_and_prefetch(self):
        self.start('A','B');self.switch();self.b._player_state='paused'
        self.remote_status.player_state='PAUSED';self.remote_status.adjusted_current_time=42
        self.mc.play=Mock();self.mc.pause=Mock();self.mc.seek=Mock()
        self.return_local()
        self.assertEqual(self.recoveries,[(42,True)]);self.assertEqual(self.b.playerState,'paused')
        self.assertEqual(self.b.playerVolume,100);self.assertFalse(self.b.playerMuted)
        self.until(lambda:'B' in backend.core.LOCAL_AUDIO_CACHE)
        self.b.togglePlayPause();self.mc.play.assert_called_once();self.remote.play.assert_not_called()
        self.b.togglePlayPause();self.mc.pause.assert_called_once();self.remote.pause.assert_not_called()
        self.b.seekTo(60);self.mc.seek.assert_called_once_with(60,timeout=3)
        self.b.nextTrack();self.until(lambda:self.b.playerTitle=='B' and self.b.playerState=='playing')
        self.assertEqual(self.remote.play_media.call_count,1)

    def test_empty_queue_return_disconnects_without_starting_audio(self):
        self.switch();self.return_local();self.until(lambda:self.cast.disconnect.called)
        self.assertIsNone(self.b._cast_output);self.assertEqual(self.b.playerState,'idle')
        self.assertFalse(self.recoveries);self.remote.stop.assert_not_called()
        self.start('A');self.assertEqual(self.remote.play_media.call_count,0)

    def test_download_error_leaves_cast_playing_and_connected(self):
        self.start('A');self.switch();self.events.clear()
        with patch.object(backend.core,'get_local_audio_source',side_effect=RuntimeError('PRIVATE_URL')):
            self.return_local()
        self.assertEqual(self.events,[]);self.assertEqual(self.b.outputName,'Speaker')
        self.assertEqual(self.b.playerState,'playing');self.cast.disconnect.assert_not_called()
        self.assertNotIn('PRIVATE',self.errors[-1])

    def test_unconfirmed_cast_stop_never_starts_local(self):
        self.start('A');self.switch();self.remote.stop.side_effect=RuntimeError('network')
        self.return_local();self.assertFalse(self.recoveries)
        self.assertEqual(self.b.outputName,'Speaker');self.cast.disconnect.assert_not_called()

    def test_local_failure_stops_local_before_restoring_cast_at_same_pause_and_position(self):
        self.start('A');self.switch();self.b._player_state='paused'
        self.remote_status.player_state='PAUSED';self.remote_status.adjusted_current_time=42
        self.events.clear()
        original_stop=self.mc.stop
        def stopped(**kwargs):self.events.append('local-stop');original_stop(**kwargs)
        with patch.object(self.mc,'play_media_at',side_effect=RuntimeError('decoder')), patch.object(self.mc,'stop',side_effect=stopped):
            self.return_local()
        self.assertLess(self.events.index('local-stop'),self.events.index('cast-load'))
        self.assertEqual(self.remote.play_media.call_args.kwargs['current_time'],42)
        self.assertFalse(self.remote.play_media.call_args.kwargs['autoplay'])
        self.assertEqual(self.b.playerState,'paused');self.assertEqual(self.b.outputName,'Speaker')
        self.cast.disconnect.assert_not_called();self.assertTrue(self.errors)

    def test_unconfirmed_local_stop_never_restarts_cast_in_parallel(self):
        self.start('A');self.switch();loads=self.remote.play_media.call_count
        with patch.object(self.mc,'play_media_at',side_effect=RuntimeError('decoder')), patch.object(self.mc,'stop',side_effect=RuntimeError('pipeline')):
            self.return_local()
        self.assertEqual(self.remote.play_media.call_count,loads)
        self.assertEqual(self.b.playerState,'idle');self.assertEqual(self.b.outputName,'Speaker')

    def test_stop_during_local_preparation_cancels_without_local_start(self):
        self.start('A');self.switch();entered=Event()
        def blocked(*args,**kwargs):
            entered.set();self.release.wait(3);return 'file:///tmp/A.m4a','audio/mp4'
        with patch.object(backend.core,'get_local_audio_source',side_effect=blocked):
            self.assertTrue(self.b.selectLocalOutput());self.until(entered.is_set)
            self.assertFalse(self.b.selectLocalOutput());self.b.stopPlayback()
            self.assertFalse(self.b.selectLocalOutput());self.assertFalse(self.b.castState['canReturn'])
            self.release.set()
            self.b._playback_executor.submit(lambda:None).result(timeout=4)
            self.app.processEvents()
        self.assertFalse(self.recoveries);self.assertEqual(self.b.playerState,'idle')
        self.assertEqual(self.b.outputName,'Speaker');self.cast.disconnect.assert_not_called()
        self.assertTrue(self.b.castState['canReturn'])

    def test_late_success_after_stop_is_cleaned_without_selecting_local(self):
        self.start('A');self.switch();generation=self.b._playback_generation
        self.b.stopPlayback();stops=len(self.stops)
        self.b._apply_output_switch(generation,dict(output=self.b._local_output,local=True,active=True,
                                                  paused=False,position=42,error=''))
        self.assertEqual(len(self.stops),stops+1);self.assertEqual(self.b.outputName,'Speaker')
        self.assertEqual(self.b.playerState,'idle');self.cast.disconnect.assert_not_called()

    def test_return_unavailable_without_local_player_or_selected_cast(self):
        self.assertFalse(self.b.selectLocalOutput());self.switch()
        local=self.b._local_output
        try:
            self.b._local_output=None
            self.assertFalse(self.b.castState['canReturn']);self.assertFalse(self.b.selectLocalOutput())
            self.assertTrue(self.errors);self.assertEqual(self.b.outputName,'Speaker')
        finally:self.b._local_output=local

    def test_stop_during_local_load_cleans_local_without_cast_restart(self):
        self.start('A');self.switch();loads=self.remote.play_media.call_count
        original_load=self.mc.play_media_at
        def load(*args,**kwargs):
            original_load(*args,**kwargs);self.b.stopPlayback()
        with patch.object(self.mc,'play_media_at',side_effect=load):
            self.assertTrue(self.b.selectLocalOutput())
            self.b._playback_executor.submit(lambda:None).result(timeout=4)
            self.app.processEvents()
        self.assertEqual(self.status.player_state,'IDLE')
        self.assertEqual(self.b.playerState,'idle');self.assertEqual(self.b.outputName,'Speaker')
        self.assertEqual(self.remote.play_media.call_count,loads)

    def test_round_trip_allows_another_explicit_cast_selection(self):
        self.start('A');self.switch();queue=self.b._queue
        self.return_local();self.until(lambda:self.cast.disconnect.called)
        self.cast.disconnect.reset_mock();self.switch()
        self.assertIs(self.b._queue,queue);self.assertEqual(self.b.outputName,'Speaker')
        self.assertEqual(self.remote.play_media.call_count,2)
