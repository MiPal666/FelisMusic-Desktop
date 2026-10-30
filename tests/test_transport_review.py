"""Controlled interleavings between failed preparation and GUI cancellation."""
import threading
from unittest.mock import patch

import test_prefetch as support


class ObservedRLock:
    def __init__(self):
        self.lock = threading.RLock()
        self.owner = threading.get_ident()
        self.observe = False
        self.worker_waiting = threading.Event()

    def __enter__(self):
        if self.observe and threading.get_ident() != self.owner:
            self.worker_waiting.set()
        self.lock.acquire()
        return self

    def __exit__(self, *args):
        self.lock.release()


class TransportReviewTests(support.AudioPlaybackTestCase):
    def interleave_failed_preparation(self, action):
        entered, fail = threading.Event(), threading.Event()
        lock = ObservedRLock()
        self.b._transport_lock = lock
        original = support.core.get_local_audio_source

        def source(video_id, **kwargs):
            if video_id == 'A':
                entered.set()
                if not fail.wait(3):
                    raise AssertionError('test did not release extraction')
                raise RuntimeError('controlled extraction failure')
            return original(video_id, **kwargs)

        with patch.object(support.core, 'get_local_audio_source', side_effect=source):
            self.b._library_items_model.set_items([
                dict(kind='song', title=v, videoId=v, duration='3:00')
                for v in ('A', 'B', 'C')])
            self.b.playFrom('library', 0)
            self.assertTrue(entered.wait(2))
            try:
                with lock:
                    lock.observe = True
                    fail.set()
                    self.assertTrue(lock.worker_waiting.wait(2), 'worker did not reach failure advance')
                    action()
                if self.b._closing.is_set():
                    self.b._playback_executor.shutdown(wait=True, cancel_futures=True)
                else:
                    self.b._playback_executor.submit(lambda: None).result(timeout=3)
                self.app.processEvents()
            finally:
                fail.set()

    def test_failed_old_preparation_cannot_skip_new_manual_selection(self):
        self.interleave_failed_preparation(lambda: self.b.playFrom('playing', 1))
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b._queue.index, 1)
        self.assertEqual(self.b.playerTitle, 'B')
        self.assertEqual(self.played, ['B'])
        self.assertFalse(self.errors)

    def test_failed_old_preparation_cannot_move_stopped_queue(self):
        self.interleave_failed_preparation(self.b.stopPlayback)
        self.assertEqual(self.b._queue.index, 0)
        self.assertEqual(self.b.playerState, 'idle')
        self.assertFalse(self.played)
        self.assertFalse(self.errors)

    def test_failed_old_preparation_cannot_move_queue_after_shutdown(self):
        self.interleave_failed_preparation(self.b.shutdown)
        self.assertEqual(self.b._queue.index, 0)
        self.assertFalse(self.played)
        self.assertFalse(self.errors)
