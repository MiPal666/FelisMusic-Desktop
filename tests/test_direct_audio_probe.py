"""Resolver probe regressions without network or an audio device."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import probe_direct_audio as probe


class DirectAudioProbeTests(unittest.TestCase):
    def test_only_plain_audio_candidates_are_selected(self):
        base = dict(mimeType='audio/mp4', url='https://media.googlevideo.com/audio', itag=140)
        candidates = [
            base,
            dict(base, signatureCipher='cipher', url=''),
            dict(base, url=base['url'] + '?n=challenge'),
            dict(base, drmFamilies=['widevine']),
            dict(base, type='FORMAT_STREAM_TYPE_OTF'),
            dict(base, mimeType='video/mp4'),
        ]
        self.assertEqual(probe.audio_formats({'streamingData': {'adaptiveFormats': candidates}}), [base])

    def test_success_skips_fallback(self):
        resolver = Mock()
        resolver.download.return_value = Path('verified.m4a')
        with patch.object(probe, 'download_fallback') as fallback:
            self.assertEqual(probe.prepare_audio(resolver, 'video', Path('.')), (Path('verified.m4a'), 'direct'))
        fallback.assert_not_called()

    def test_failure_retries_through_fallback_without_logging_url(self):
        resolver = Mock()
        resolver.download.side_effect = ValueError('https://signed.example/secret')
        output = io.StringIO()
        with patch.object(probe, 'download_fallback', return_value=Path('fallback.m4a')) as fallback:
            with contextlib.redirect_stdout(output):
                result = probe.prepare_audio(resolver, 'video', Path('.'))
        self.assertEqual(result, (Path('fallback.m4a'), 'yt-dlp'))
        fallback.assert_called_once_with('video', Path('.'))
        resolver.close.assert_called_once()
        self.assertNotIn('secret', output.getvalue())

    def test_partial_audio_is_rejected_and_response_closed(self):
        resolver = probe.DirectResolver()
        resolver.client = {'userAgent': 'probe'}
        response = Mock(status=200)
        response.read.side_effect = [b'short', b'']
        resolver.transport = Mock()
        resolver.transport.request.return_value = response
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, 'Incomplete audio'):
                resolver.transfer({'url': 'https://media.googlevideo.com/audio'}, 10, Path(directory) / 'audio')
        response.close.assert_called_once()

    def test_fallback_failure_is_reported(self):
        resolver = Mock()
        resolver.download.side_effect = RuntimeError()
        with patch.object(probe, 'download_fallback', side_effect=OSError('unavailable')):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(OSError):
                probe.prepare_audio(resolver, 'video', Path('.'))

    def test_keyboard_interrupt_does_not_start_fallback(self):
        resolver = Mock()
        resolver.download.side_effect = KeyboardInterrupt()
        with patch.object(probe, 'download_fallback') as fallback:
            with self.assertRaises(KeyboardInterrupt):
                probe.prepare_audio(resolver, 'video', Path('.'))
        fallback.assert_not_called()


if __name__ == '__main__':
    unittest.main()
