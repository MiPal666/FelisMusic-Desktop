"""Cast probe selects URLs without downloading and retains the existing fallback."""
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import probe_direct_cast as probe


class CastProbeTests(TestCase):
    def test_direct_url_is_sent_to_cast_without_host_download(self):
        resolver = Mock()
        resolver.resolve.return_value = [dict(url='https://direct.invalid/SECRET', mimeType='audio/mp4', itag=140)]
        controller = Mock()
        with patch.object(probe, 'play_sample') as sample, patch.object(probe.core, 'get_yt_dlp_audio_stream') as fallback:
            result = probe.test_track(resolver, controller, 'video', 5, set())
        self.assertEqual(result, 'direct')
        sample.assert_called_once()
        self.assertEqual(sample.call_args.args[1:3], ('https://direct.invalid/SECRET', 'audio/mp4'))
        resolver.download.assert_not_called()
        fallback.assert_not_called()

    def test_cast_rejection_uses_existing_stream_resolver(self):
        resolver = Mock()
        resolver.resolve.return_value = [dict(url='direct', mimeType='audio/mp4', itag=140)]
        controller = Mock(status=SimpleNamespace(content_id='direct'))
        with patch.object(probe, 'play_sample', side_effect=[RuntimeError(), None]) as sample:
            with patch.object(probe.core, 'get_yt_dlp_audio_stream', return_value=('fallback', 'audio/mp4')) as fallback:
                self.assertEqual(probe.test_track(resolver, controller, 'video', 5, set()), 'yt-dlp')
        controller.stop.assert_called_once()
        fallback.assert_called_once_with('video')
        self.assertEqual(sample.call_count, 2)

    def test_no_plain_url_uses_fallback(self):
        resolver = Mock()
        resolver.resolve.side_effect = probe.DirectAudioError('unavailable')
        controller = Mock(status=SimpleNamespace(content_id=''))
        with patch.object(probe, 'play_sample'), patch.object(probe.core, 'get_yt_dlp_audio_stream', return_value=('fallback', 'audio/mp4')):
            self.assertEqual(probe.test_track(resolver, controller, 'video', 5, set()), 'yt-dlp')

    def test_interrupt_does_not_load_fallback(self):
        resolver = Mock()
        resolver.resolve.side_effect = KeyboardInterrupt()
        with patch.object(probe.core, 'get_yt_dlp_audio_stream') as fallback:
            with self.assertRaises(KeyboardInterrupt):
                probe.test_track(resolver, Mock(), 'video', 5, set())
        fallback.assert_not_called()
