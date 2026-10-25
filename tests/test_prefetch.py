"""Offline playback/cache checks; no account, network, or audio device needed."""
import sys
import tempfile
import threading
import time
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from PySide6.QtCore import QCoreApplication
from felismusic_gui import backend

core = backend.core


class AudioPlaybackTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.downloads = Counter()
        self.blocked = set()
        self.release = threading.Event()
        self.fail_once = set()
        self.cancelled = set()
        self.played = []
        self.stops = []
        self.errors = []
        self.status = SimpleNamespace(
            player_state='PLAYING', idle_reason='', adjusted_current_time=5,
            duration=180,
        )
        self.mc = SimpleNamespace(
            status=self.status, play_media=self.play_media,
            block_until_active=lambda **kwargs: None, stop=self.stop,
        )
        output = SimpleNamespace(
            media_controller=self.mc,
            status=SimpleNamespace(volume_level=1, volume_muted=False),
        )
        case = self

        class FakeYoutubeDL:
            def __init__(self, options):
                self.options = options

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def extract_info(self, url, download):
                video_id = url.split('v=')[-1]
                case.downloads[video_id] += 1
                try:
                    while video_id in case.blocked and not case.release.wait(.005):
                        self.progress()
                    self.progress()
                    if video_id in case.fail_once:
                        case.fail_once.remove(video_id)
                        raise RuntimeError('simulated network failure')
                    path = self.options['outtmpl'].replace('%(ext)s', 'm4a')
                    Path(path).write_bytes(b'offline test audio')
                    return {'ext': 'm4a', 'path': path}
                except core.AudioPreparationCancelled:
                    case.cancelled.add(video_id)
                    raise

            def progress(self):
                for hook in self.options.get('progress_hooks', []):
                    hook({'status': 'downloading'})

            def prepare_filename(self, info):
                return info['path']

        self.patches = [
            patch.object(core, 'LOCAL_CACHE_DIR', self.temp.name),
            patch.object(core, 'LOCAL_AUDIO_CACHE', {}),
            patch.object(core, 'LOCAL_CACHE_ORDER', []),
            patch.object(core.yt_dlp, 'YoutubeDL', FakeYoutubeDL),
            patch.object(core.AUTH, 'yt_dlp_http_headers', return_value={}),
            patch.object(core, 'create_local_output', return_value=output),
        ]
        for p in self.patches:
            p.start()
        self.b = backend.BackendBridge()
        self.b._player_timer.stop()
        self.b.errorOccurred.connect(self.errors.append)

    def tearDown(self):
        self.release.set()
        self.b.shutdown()
        self.b._playback_executor.shutdown(wait=True, cancel_futures=True)
        deadline = time.monotonic() + 3
        while Path(self.temp.name).exists() and time.monotonic() < deadline:
            time.sleep(.005)
        self.assertFalse(Path(self.temp.name).exists(), 'cleanup did not finish')
        self.app.processEvents()
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def play_media(self, uri, content_type, **kwargs):
        self.played.append(Path(uri).stem)
        self.status.player_state = 'PLAYING'
        self.status.idle_reason = ''

    def stop(self, *, keep_output=False):
        self.stops.append(keep_output)
        self.status.player_state = 'IDLE'
        self.status.idle_reason = ''

    def until(self, predicate):
        deadline = time.monotonic() + 4
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.005)
        self.assertTrue(predicate(), 'timed out')

    def start(self, *ids):
        self.b._library_items_model.set_items([
            dict(kind='song', title=vid, videoId=vid, duration='3:00', likeStatus='LIKE')
            for vid in ids
        ])
        self.b.playFrom('library', 0)
        self.until(lambda: self.b.playerState == 'playing')

    def eos(self):
        self.status.player_state = 'IDLE'
        self.status.idle_reason = 'FINISHED'
        self.b._poll_player()



class PrefetchTests(AudioPlaybackTestCase):
    def test_next_track_is_ready_before_eos_and_only_one_ahead(self):
        self.start('A', 'B', 'C')
        self.until(lambda: 'B' in core.LOCAL_AUDIO_CACHE)
        self.assertEqual(self.played, ['A'])
        self.assertNotIn('C', self.downloads)
        self.assertEqual(self.b.playerQueueIndex, 0)
        self.assertEqual(self.b.playerState, 'playing')
        self.eos()
        self.until(lambda: self.b.playerQueueIndex == 1 and self.b.playerState == 'playing')
        self.until(lambda: 'C' in core.LOCAL_AUDIO_CACHE)
        self.assertEqual(self.downloads['B'], 1)
        self.assertEqual(self.played[:2], ['A', 'B'])
        self.eos()
        self.until(lambda: self.b.playerState == 'playing' and self.b.playerQueueIndex == 2)
        self.eos()
        self.assertEqual(self.b.playerState, 'idle')
        self.assertEqual(self.downloads, Counter(A=1, B=1, C=1))
        self.assertFalse(self.errors)

    def test_eos_during_download_reuses_inflight_prefetch(self):
        self.blocked.add('B')
        self.start('A', 'B')
        self.until(lambda: self.downloads['B'] == 1)
        self.eos()
        self.assertEqual(self.b.playerState, 'loading')
        self.release.set()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.downloads['B'], 1)
        self.assertEqual(self.played, ['A', 'B'])
        self.assertNotIn('B', self.cancelled)

    def test_prefetch_failure_does_not_skip_or_interrupt_current_track(self):
        self.fail_once.add('B')
        self.start('A', 'B')
        self.until(lambda: self.b._prefetch_future.done())
        self.assertFalse(self.errors)
        self.assertEqual(self.b.playerQueueIndex, 0)
        self.assertEqual(self.b.playerState, 'playing')
        self.eos()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['A', 'B'])
        self.assertEqual(self.downloads['B'], 2)

    def test_manual_selection_only_cancels_obsolete_prefetch(self):
        self.blocked.add('B')
        self.start('A', 'B')
        self.until(lambda: self.downloads['B'] == 1)
        self.b._library_items_model.set_items([
            dict(kind='song', title='D', videoId='D', likeStatus='LIKE')
        ])
        self.b.playFrom('library', 0)
        self.until(lambda: self.played == ['A', 'D'] and self.b.playerState == 'playing')
        self.assertIn('B', self.cancelled)
        self.assertNotIn('B', core.LOCAL_AUDIO_CACHE)
        self.assertFalse(self.errors)

    def test_manual_selection_stops_old_audio_before_new_download_finishes(self):
        self.start('A')
        self.blocked.add('D')
        self.b._library_items_model.set_items([
            dict(kind='song', title='D', videoId='D', likeStatus='LIKE')
        ])
        self.b.playFrom('library', 0)
        self.assertEqual(self.status.player_state, 'IDLE')
        self.assertEqual(self.b.playerState, 'loading')
        self.assertTrue(self.stops[-1], 'transition must preserve audio output')
        self.until(lambda: self.downloads['D'] == 1)
        self.assertEqual(self.played, ['A'])
        self.release.set()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['A', 'D'])

    def test_new_click_cancels_obsolete_foreground_download(self):
        self.start('A')
        self.blocked.add('D')
        self.b._library_items_model.set_items([
            dict(kind='song', title='D', videoId='D', likeStatus='LIKE'),
            dict(kind='song', title='E', videoId='E', likeStatus='LIKE'),
        ])
        self.b.playFrom('library', 0)
        self.until(lambda: self.downloads['D'] == 1)
        self.b.playFrom('library', 1)
        self.until(lambda: self.b.playerState == 'playing')
        self.assertIn('D', self.cancelled)
        self.assertEqual(self.played, ['A', 'E'])
        self.assertFalse(self.errors)

    def test_next_previous_stop_immediately_but_eos_keeps_prefetch_fast_path(self):
        self.start('A', 'B')
        self.until(lambda: 'B' in core.LOCAL_AUDIO_CACHE)
        stops = len(self.stops)
        self.b.nextTrack()
        self.assertEqual(len(self.stops), stops + 1)
        self.assertEqual(self.status.player_state, 'IDLE')
        self.until(lambda: self.b.playerState == 'playing')
        self.b.previousTrack()
        self.assertEqual(len(self.stops), stops + 2)
        self.until(lambda: self.b.playerState == 'playing')
        self.eos()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(len(self.stops), stops + 2)
        self.assertEqual(self.downloads['B'], 1)

    def test_invalid_selection_does_not_stop_current_audio(self):
        self.start('A')
        stops = len(self.stops)
        self.b.playFrom('library', -1)
        self.b.playFrom('library', 99)
        self.assertEqual(len(self.stops), stops)
        self.assertEqual(self.b.playerState, 'playing')

    def test_shutdown_cancels_prefetch_before_cache_cleanup(self):
        self.blocked.add('B')
        self.start('A', 'B')
        self.until(lambda: self.downloads['B'] == 1)
        self.b.shutdown()
        self.until(lambda: not Path(self.temp.name).exists())
        self.assertIn('B', self.cancelled)
        self.assertEqual(self.played, ['A'])
        self.assertFalse(self.errors)

    def test_shutdown_during_initial_download_does_not_start_audio(self):
        self.blocked.add('A')
        self.b._library_items_model.set_items([
            dict(kind='song', title='A', videoId='A', likeStatus='LIKE')
        ])
        self.b.playFrom('library', 0)
        self.until(lambda: self.downloads['A'] == 1)
        self.b.shutdown()
        self.until(lambda: not Path(self.temp.name).exists())
        self.assertIn('A', self.cancelled)
        self.assertFalse(self.played)
        self.assertFalse(self.errors)


if __name__ == '__main__':
    unittest.main()
