"""Direct Cast URL selection, cached sources and rejected LOAD fallback."""
from threading import Event, Lock
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
import test_prefetch as support
from test_cast_output import CastOutputFixture
from felismusic_gui import direct_audio
from felismusic_gui.cast_output import CastController
from felismusic_gui.cast_streams import CastStreamCache


class CastURLTests(TestCase):
    def test_direct_url_remains_a_string_and_cache_retains_retry_metadata(self):
        resolver = Mock()
        resolver.resolve.return_value = [dict(mimeType='audio/mp4', url='https://test.googlevideo.com/audio', itag=140)]
        with patch.object(direct_audio, 'getproxies', return_value={}):
            with patch.object(direct_audio, 'DirectResolver', return_value=resolver):
                url = direct_audio.resolve_cast_url('ojvldIzbaMo')
        self.assertIsInstance(url, str)
        self.assertEqual(url.video_id, 'ojvldIzbaMo')
        resolver.close.assert_called_once()
        resolver.download.assert_not_called()
        cache = CastStreamCache()
        key = ('queue', 'output', 'ojvldIzbaMo')
        ticket = cache.reserve(key)
        self.assertTrue(cache.complete(ticket, (url, 'audio/mp4')))
        self.assertIs(cache.take(key)[0], url)

    def test_resolution_failure_uses_existing_yt_dlp_stream(self):
        with patch.object(support.core, 'resolve_cast_url', side_effect=RuntimeError('unavailable')):
            with patch.object(support.core, 'get_yt_dlp_audio_stream', return_value=('fallback', 'audio/mp4')) as fallback:
                self.assertEqual(support.core.get_audio_stream('video'), ('fallback', 'audio/mp4'))
        fallback.assert_called_once_with('video')

    def test_direct_success_does_not_run_yt_dlp(self):
        url = direct_audio.DirectCastURL('https://test.googlevideo.com/audio', 'ojvldIzbaMo')
        with patch.object(support.core, 'resolve_cast_url', return_value=url):
            with patch.object(support.core, 'get_yt_dlp_audio_stream') as fallback:
                self.assertIs(support.core.get_audio_stream('ojvldIzbaMo')[0], url)
        fallback.assert_not_called()


class CastLoadFallbackTests(TestCase):
    def setUp(self):
        self.status = SimpleNamespace(content_id='', media_session_id=1, player_state='IDLE', idle_reason='')
        self.remote = Mock(status=self.status)
        self.controller = CastController(self.remote)
        self.url = direct_audio.DirectCastURL('https://direct.invalid/audio', 'ojvldIzbaMo')
        self.remote.play_media.side_effect = self.load

    def load(self, url, content_type, **kwargs):
        if isinstance(url, direct_audio.DirectCastURL):
            kwargs['callback_function'](False, {'type': 'LOAD_FAILED'})
        else:
            self.status.content_id = url
            self.status.player_state = 'PLAYING' if kwargs['autoplay'] else 'PAUSED'
            kwargs['callback_function'](True, {'type': 'MEDIA_STATUS'})

    def test_rejected_direct_load_preserves_position_pause_and_metadata(self):
        self.controller.play_media_at(self.url, 'audio/mp4', position=42, paused=True, title='Track', stream_type='BUFFERED')
        with patch.object(support.core, 'get_yt_dlp_audio_stream', return_value=('fallback', 'audio/mp4')) as fallback:
            self.controller.block_until_active(timeout=.01, load_lock=Lock())
        fallback.assert_called_once_with('ojvldIzbaMo')
        self.assertEqual(self.remote.play_media.call_count, 2)
        options = self.remote.play_media.call_args.kwargs
        self.assertEqual((options['current_time'], options['autoplay'], options['title'], options['stream_type']),
                         (42, False, 'Track', 'BUFFERED'))

    def test_synchronous_load_error_also_runs_fallback_outside_play_call(self):
        self.remote.play_media.side_effect = [RuntimeError('send failed'), self.load]
        self.controller.play_media(self.url, 'audio/mp4')
        self.remote.play_media.side_effect = self.load
        with patch.object(support.core, 'get_yt_dlp_audio_stream', return_value=('fallback', 'audio/mp4')):
            self.controller.block_until_active(timeout=.01)
        self.assertEqual(self.remote.play_media.call_count, 2)

    def test_cancelled_after_fallback_resolution_cannot_start_stale_media(self):
        cancelled = Event()
        self.controller.play_media(self.url, 'audio/mp4')
        def resolve(_video):
            cancelled.set()
            return 'fallback', 'audio/mp4'
        with patch.object(support.core, 'get_yt_dlp_audio_stream', side_effect=resolve):
            with self.assertRaises(support.core.AudioPreparationCancelled):
                self.controller.block_until_active(timeout=.01, cancelled=cancelled.is_set, load_lock=Lock())
        self.assertEqual(self.remote.play_media.call_count, 1)

    def test_disconnected_cast_does_not_start_fallback(self):
        lost = Event()
        self.controller.connection_lost = lost
        self.controller.play_media(self.url, 'audio/mp4')
        lost.set()
        with patch.object(support.core, 'get_yt_dlp_audio_stream') as fallback:
            with self.assertRaises(RuntimeError):
                self.controller.block_until_active(timeout=.01)
        fallback.assert_not_called()

    def test_fallback_load_rejected_propagates_without_recursive_retry(self):
        self.remote.play_media.side_effect = lambda *args, **kwargs: kwargs['callback_function'](False, {'type': 'LOAD_FAILED'})
        self.controller.play_media(self.url, 'audio/mp4')
        with patch.object(support.core, 'get_yt_dlp_audio_stream', return_value=('fallback', 'audio/mp4')) as fallback:
            with self.assertRaises(RuntimeError):
                self.controller.block_until_active(timeout=.01)
        fallback.assert_called_once()
        self.assertEqual(self.remote.play_media.call_count, 2)


class DirectCastHandoffTests(CastOutputFixture):
    def test_actual_gui_handoff_retries_direct_rejection_at_same_position(self):
        self.start('A')
        self.status.adjusted_current_time = 42
        self.status.player_state = 'PAUSED'
        self.stream_call.side_effect = lambda vid, mc: (direct_audio.DirectCastURL('direct', vid), 'audio/mp4')
        original_load = self.load_remote
        def load(url, content_type, **kwargs):
            if isinstance(url, direct_audio.DirectCastURL):
                kwargs['callback_function'](False, {'type': 'LOAD_FAILED'})
            else:
                original_load(url, content_type, **kwargs)
        self.remote.play_media.side_effect = load
        with patch.object(support.core, 'get_yt_dlp_audio_stream', return_value=('fallback', 'audio/mp4')):
            self.switch()
        self.assertEqual(self.b.outputName, 'Speaker')
        self.assertEqual(self.b.playerState, 'paused')
        self.assertEqual(self.remote.play_media.call_args.kwargs['current_time'], 42)
        self.assertFalse(self.errors)


class DirectCastPlaybackTests(CastOutputFixture):
    def setUp(self):
        super().setUp()
        self.switch()
        self.stream_call.side_effect = lambda vid, mc: (direct_audio.DirectCastURL('direct-' + vid, vid), 'audio/mp4')
        original_load = self.load_remote
        def load(url, content_type, **kwargs):
            if isinstance(url, direct_audio.DirectCastURL):
                kwargs['callback_function'](False, {'type': 'LOAD_FAILED'})
            else:
                original_load(url, content_type, **kwargs)
        self.remote.play_media.side_effect = load

    def test_foreground_and_cached_direct_streams_both_fall_back(self):
        with patch.object(support.core, 'get_yt_dlp_audio_stream', side_effect=lambda vid: ('fallback-' + vid, 'audio/mp4')) as fallback:
            self.start('A', 'B')
            self.until(lambda: self.b._prefetch_future is not None and self.b._prefetch_future.done())
            self.remote_status.player_state = 'IDLE'
            self.remote_status.idle_reason = 'FINISHED'
            self.b._poll_player()
            self.until(lambda: self.b.playerTitle == 'B' and self.b.playerState == 'playing')
        self.assertEqual([call.args[0] for call in fallback.call_args_list], ['A', 'B'])
        self.assertFalse(self.errors)
        self.assertEqual(self.b._queue.index, 1)

    def test_gui_stop_during_fallback_cannot_issue_late_load(self):
        entered = Event()
        def resolve(_video):
            entered.set()
            self.release.wait(3)
            return 'fallback', 'audio/mp4'
        with patch.object(support.core, 'get_yt_dlp_audio_stream', side_effect=resolve):
            self.b._library_items_model.set_items([dict(kind='song', title='A', videoId='A')])
            self.b.playFrom('library', 0)
            self.until(entered.is_set)
            self.b.stopPlayback()
            self.release.set()
            self.b._playback_executor.submit(lambda: None).result(3)
            self.app.processEvents()
        self.assertEqual(self.remote.play_media.call_count, 1)
        self.assertEqual(self.b.playerState, 'idle')
        self.assertFalse(self.errors)

    def test_failed_fallback_for_prefetched_direct_url_is_not_retried_again(self):
        with patch.object(support.core, 'get_yt_dlp_audio_stream', side_effect=lambda vid: ('fallback-' + vid, 'audio/mp4')) as fallback:
            self.start('A', 'B')
            self.until(lambda: self.b._prefetch_future is not None and self.b._prefetch_future.done())
            self.remote.play_media.side_effect = lambda *args, **kwargs: kwargs['callback_function'](False, {'type': 'LOAD_FAILED'})
            self.remote_status.player_state = 'IDLE'
            self.remote_status.idle_reason = 'FINISHED'
            self.b._poll_player()
            self.until(lambda: bool(self.errors))
        self.assertEqual([call.args[0] for call in fallback.call_args_list], ['A', 'B'])
