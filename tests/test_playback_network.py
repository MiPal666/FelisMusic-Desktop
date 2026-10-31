"""Network failures must preserve the exact queue occurrence for manual retry."""
import socket
from unittest.mock import patch
from yt_dlp.utils import DownloadError, ExtractorError
from yt_dlp.networking.exceptions import TransportError
import test_prefetch as support
from test_cast_output import CastOutputFixture


def dns_failure():
    cause = TransportError(cause=socket.gaierror(-3, 'Temporary failure in name resolution'))
    extractor = ExtractorError('Unable to download API page', cause=cause)
    return DownloadError('private diagnostic URL', exc_info=(type(extractor), extractor, None))


class PlaybackNetworkTests(support.AudioPlaybackTestCase):
    def barrier(self):
        self.b._playback_executor.submit(lambda: None).result(timeout=3)
        self.app.processEvents()

    def test_cached_tracks_finish_then_network_failure_preserves_occurrence_and_play_retries(self):
        self.start('A', 'B', 'C', 'D')
        self.until(lambda: 'B' in support.core.LOCAL_AUDIO_CACHE)
        original = support.core.get_local_audio_source
        def source(video_id, **kwargs):
            if video_id in ('C', 'D'):
                raise dns_failure()
            return original(video_id, **kwargs)
        with patch.object(support.core, 'get_local_audio_source', side_effect=source):
            self.eos()
            self.until(lambda: self.b.playerState == 'playing' and self.b.playerQueueIndex == 1)
            self.barrier()  # speculative C prefetch failed without affecting B
            self.eos()
            self.until(lambda: bool(self.errors))
            self.barrier()
            self.assertEqual(self.b.playerQueueIndex, 2)
            self.assertEqual(self.b.playerTitle, 'C')
            self.assertEqual(self.b.playerState, 'idle')
            self.assertEqual(self.played, ['A', 'B'])
            self.assertNotIn('private diagnostic', self.errors[-1])
        self.b.togglePlayPause()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerQueueIndex, 2)
        self.assertEqual(self.played, ['A', 'B', 'C'])

    def test_unavailable_track_then_network_failure_displays_failed_occurrence(self):
        self.b._library_items_model.set_items([
            dict(kind='song', title=v, videoId=v, duration='3:00') for v in ('A', 'B', 'C')])
        def source(video_id, **kwargs):
            if video_id == 'A':
                raise ExtractorError('Video unavailable', expected=True)
            raise dns_failure()
        with patch.object(support.core, 'get_local_audio_source', side_effect=source):
            self.b.playFrom('library', 0)
            self.until(lambda: bool(self.errors))
            self.assertEqual(self.b.playerQueueIndex, 1)
            self.assertEqual(self.b.playerTitle, 'B')
            self.assertFalse(self.played)

    def test_previous_network_failure_keeps_exact_duplicate_occurrence(self):
        self.start('A', 'B', 'A', 'D')
        self.b.playFrom('playing', 3)
        self.until(lambda: self.b.playerState == 'playing' and self.b.playerQueueIndex == 3)
        with patch.object(support.core, 'get_local_audio_source', side_effect=dns_failure()):
            self.b.previousTrack()
            self.until(lambda: bool(self.errors))
            self.assertEqual(self.b.playerQueueIndex, 2)
            self.assertEqual(self.b.playerTitle, 'A')
        self.b.togglePlayPause()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerQueueIndex, 2)


class NetworkClassificationTests(support.unittest.TestCase):
    def test_typed_wrappers_and_unrelated_errors(self):
        from felismusic_gui.network_errors import is_network_failure
        from requests.exceptions import ReadTimeout, ConnectionError
        from urllib.error import URLError
        import errno
        for error in (dns_failure(), ReadTimeout('timeout'), ConnectionError('offline'),
                      URLError(socket.gaierror(-3, 'dns')), TimeoutError(),
                      OSError(errno.ENETUNREACH, 'no route')):
            with self.subTest(error=type(error).__name__):
                self.assertTrue(is_network_failure(error))
        for error in (DownloadError('Video unavailable'),
                      ExtractorError('Video private', expected=True),
                      RuntimeError('network failure is only arbitrary text'),
                      FileNotFoundError('missing cache file')):
            with self.subTest(error=type(error).__name__):
                self.assertFalse(is_network_failure(error))

    def test_cyclic_exception_chain_terminates(self):
        from felismusic_gui.network_errors import is_network_failure
        exc = RuntimeError('cycle')
        exc.__cause__ = exc
        self.assertFalse(is_network_failure(exc))


class CastNetworkTests(CastOutputFixture):
    def test_cast_stream_network_failure_keeps_occurrence_for_manual_retry(self):
        self.start('A', 'B', 'C')
        self.switch()
        self.b._playback_executor.submit(lambda: None).result(timeout=3)
        self.b._cast_streams.clear()
        self.stream_call.side_effect = dns_failure()
        self.b.nextTrack()
        self.until(lambda: bool(self.errors))
        self.assertEqual(self.b.playerQueueIndex, 1)
        self.assertEqual(self.b.playerTitle, 'B')
        self.assertEqual(self.b.playerState, 'idle')
        self.stream_call.side_effect = self.stream
        self.b.togglePlayPause()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerQueueIndex, 1)
        self.assertEqual(self.remote_status.content_id, 'https://audio.invalid/B')
