"""Direct local playback, cancellation, atomic files and authenticated fallback."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import test_prefetch as support
from felismusic_gui import direct_audio


class DirectResolverTests(unittest.TestCase):
    def resolver(self):
        resolver = direct_audio.DirectResolver()
        resolver.headers = {}
        resolver.client = {'userAgent': 'test'}
        resolver.post = Mock(return_value={
            'playabilityStatus': {'status': 'OK'},
            'videoDetails': {'videoId': 'ojvldIzbaMo'},
            'streamingData': {'adaptiveFormats': [dict(
                mimeType='audio/mp4', url='https://test.googlevideo.com/audio',
                contentLength='5', itag=140,
            )]},
        })
        return resolver

    def test_completed_file_is_published_after_full_transfer(self):
        resolver = self.resolver()
        response = Mock(status=206)
        response.getheader.return_value = 'bytes 0-4/5'
        response.read.side_effect = [b'audio', b'']
        resolver.transport = Mock()
        resolver.transport.request.return_value = response
        with tempfile.TemporaryDirectory() as directory:
            path = resolver.download('ojvldIzbaMo', Path(directory))
            self.assertEqual(path.read_bytes(), b'audio')
            self.assertEqual(list(Path(directory).iterdir()), [path])
            self.assertEqual(path.suffix, '.m4a')
        response.close.assert_called_once()

    def test_incomplete_transfer_leaves_no_file(self):
        resolver = self.resolver()
        response = Mock(status=200)
        response.read.side_effect = [b'bad', b'']
        resolver.transport = Mock()
        resolver.transport.request.return_value = response
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(direct_audio.DirectAudioError):
                resolver.download('ojvldIzbaMo', Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_cancellation_during_transfer_closes_response_and_removes_partial(self):
        resolver = self.resolver()
        cancelled = False
        def read(_size):
            nonlocal cancelled
            cancelled = True
            return b'audio'
        def check():
            if cancelled:
                raise support.core.AudioPreparationCancelled()
        resolver.check_cancelled = check
        response = Mock(status=200)
        response.read.side_effect = read
        resolver.transport = Mock()
        resolver.transport.request.return_value = response
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(support.core.AudioPreparationCancelled):
                resolver.download('ojvldIzbaMo', Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])
        response.close.assert_called_once()

    def test_proxy_uses_fallback_transport_without_direct_request(self):
        with patch.object(direct_audio, 'getproxies', return_value={'https': 'proxy'}):
            with patch.object(direct_audio, 'DirectResolver') as factory:
                with self.assertRaises(direct_audio.DirectAudioError):
                    direct_audio.download_audio('ojvldIzbaMo', '.', check_cancelled=lambda: None)
        factory.assert_not_called()

    def test_restricted_track_and_changed_client_metadata_raise_for_fallback(self):
        resolver = self.resolver()
        resolver.post.return_value = {'playabilityStatus': {'status': 'LOGIN_REQUIRED'}}
        with self.assertRaises(direct_audio.DirectAudioError):
            resolver.download('ojvldIzbaMo', Path('.'))
        with patch('yt_dlp.extractor.youtube._base.INNERTUBE_CLIENTS', {}):
            with self.assertRaises(KeyError):
                direct_audio.DirectResolver().configure()


class DirectPlaybackTests(support.AudioPlaybackTestCase):
    def direct_download(self, video_id, directory, *, check_cancelled):
        check_cancelled()
        path = Path(directory) / (video_id + '.m4a')
        path.write_bytes(b'direct audio')
        return str(path)

    def test_normal_playback_prefetch_and_eos_use_direct_files(self):
        with patch.object(support.core, 'download_direct_audio', side_effect=self.direct_download) as direct:
            self.start('A', 'B')
            self.until(lambda: 'B' in support.core.LOCAL_AUDIO_CACHE)
            self.eos()
            self.until(lambda: self.played == ['A', 'B'])
            self.assertEqual(direct.call_count, 2)
            self.assertFalse(self.downloads)
            self.assertFalse(self.errors)

    def test_direct_failure_uses_existing_authenticated_downloader(self):
        with patch.object(support.core, 'download_direct_audio', side_effect=RuntimeError('unavailable')):
            self.start('A')
            self.assertEqual(self.downloads['A'], 1)
            self.assertEqual(self.played, ['A'])

    def test_cancellation_does_not_launch_authenticated_fallback(self):
        with patch.object(support.core, 'download_direct_audio', side_effect=support.core.AudioPreparationCancelled):
            with self.assertRaises(support.core.AudioPreparationCancelled):
                support.core.get_local_audio_source('A')
        self.assertFalse(self.downloads)
        self.assertFalse(support.core.LOCAL_AUDIO_CACHE)

    def test_cancellation_after_direct_download_removes_file(self):
        cancelled = False
        def download(*args, **kwargs):
            nonlocal cancelled
            path = self.direct_download(*args, **kwargs)
            cancelled = True
            return path
        with patch.object(support.core, 'download_direct_audio', side_effect=download):
            with self.assertRaises(support.core.AudioPreparationCancelled):
                support.core.get_local_audio_source('A', cancelled=lambda: cancelled)
        self.assertFalse(list(Path(self.temp.name).iterdir()))
        self.assertFalse(self.downloads)
        self.assertFalse(support.core.LOCAL_AUDIO_CACHE)
