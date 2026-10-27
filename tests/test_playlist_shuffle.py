"""Local playlist shuffle preserves exact occurrences without server queues."""
from collections import Counter
from threading import Event
from unittest.mock import Mock, patch
import test_prefetch as support


class PlaylistShuffleTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock(); self.b._ytmusic = self.api
        self.source = [dict(videoId=vid, title=vid, setVideoId=f'set-{i}', likeStatus='LIKE')
                       for i, vid in enumerate(('A', 'B', 'A', 'C'))]
        self.api.get_playlist.return_value = dict(title='Mine', owned=True, tracks=self.source)

    def load(self):
        self.b.loadPlaylistTracks('PLmine', 'Mine')
        self.until(lambda: not self.b.busy)

    def shuffle(self):
        self.assertTrue(self.b.shuffleDetail())
        self.until(lambda: not self.b.busy and self.b.playerState == 'playing')

    def test_occurrences_origin_cover_prefetch_and_repeat(self):
        self.load(); snapshot = self.b.detailTracksModel.snapshot()
        self.b.playbackSourceCaptured.connect(lambda: self.b.setPlaybackSourceContext({'page': 1}))
        with patch.object(support.backend.random, 'shuffle', side_effect=lambda rows: rows.reverse()):
            self.shuffle()
        queue = self.b._queue
        self.assertEqual([x['videoId'] for x in queue.tracks], ['C', 'A', 'B', 'A'])
        self.assertEqual(self.b._queue_source_indices, [3, 2, 1, 0])
        self.assertEqual([x['_guiOrigin']['index'] for x in queue.tracks], [3, 2, 1, 0])
        self.assertEqual([x['_guiPlaylistBinding'] for x in queue.tracks],
                         [('PLmine', f'set-{i}') for i in (3, 2, 1, 0)])
        self.assertEqual(snapshot, self.b.detailTracksModel.snapshot())
        self.assertTrue(queue.shuffle_active); self.assertFalse(queue.radio_active)
        self.assertFalse(self.b.playerQueueLoading); self.assertFalse(self.b.playerQueueIncomplete)
        self.assertEqual(self.b.playerRepeatMode, 'off')
        self.until(lambda: 'A' in support.core.LOCAL_AUDIO_CACHE)
        self.b.clearDetail(); self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual(self.b.detailTitle, 'Mine')
        self.assertEqual(self.b.detailTracksModel.snapshot(), snapshot)
        self.assertEqual(self.b.playerSourceContext['page'], 1)
        self.b.cycleRepeat()
        for expected in ('A', 'B', 'A', 'C'):
            self.eos(); self.until(lambda: self.b.playerState == 'playing')
            self.assertEqual(self.b.playerVideoId, expected)
        self.api.get_playlist.assert_called_once()
        self.api.get_watch_playlist.assert_not_called()

    def test_new_shuffle_uses_fresh_randomization_without_reloading(self):
        self.load(); self.start('old'); self.b.cycleRepeat()
        with patch.object(support.backend.random, 'shuffle', side_effect=lambda rows: rows.reverse()) as mix:
            self.shuffle(); first = self.b._queue
            self.b.cycleRepeat(); self.shuffle()
        self.assertIsNot(self.b._queue, first)
        self.assertEqual(mix.call_count, 2)
        self.assertEqual(self.b.playerRepeatMode, 'off')
        self.api.get_playlist.assert_called_once()
        self.api.get_watch_playlist.assert_not_called()

    def test_large_playlist_retains_all_occurrences_and_stops_at_end(self):
        self.source = [dict(videoId=str(i % 1599), title=str(i), setVideoId=f'set-{i}', likeStatus='LIKE') for i in range(1635)]
        self.api.get_playlist.return_value['tracks'] = self.source
        self.load(); self.shuffle()
        self.assertEqual(self.b.playerQueueCount, 1635)
        self.assertEqual(Counter(x['videoId'] for x in self.b._queue.tracks),
                         Counter(x['videoId'] for x in self.source))
        self.assertEqual(len(set(self.b._queue_source_indices)), 1635)
        self.b.playFrom('playing', 1634); self.until(lambda: self.b.playerState == 'playing')
        self.eos(); self.assertEqual(self.b.playerState, 'idle')
        self.api.get_watch_playlist.assert_not_called()

    def test_late_result_after_stop_or_navigation_is_ignored(self):
        for action in ('stop', 'navigate'):
            with self.subTest(action=action):
                self.start('old'); old = self.b._queue; self.load()
                entered = Event(); self.release.clear()
                def hold(rows):
                    entered.set(); self.release.wait(3); rows.reverse()
                with patch.object(support.backend.random, 'shuffle', side_effect=hold):
                    self.assertTrue(self.b.shuffleDetail()); self.until(entered.is_set)
                    self.assertFalse(self.b.shuffleDetail())
                    if action == 'stop': self.b.stopPlayback()
                    else: self.b.clearDetail()
                    self.release.set(); self.until(lambda: not self.b.busy)
                self.assertIs(self.b._queue, old)

    def test_local_failure_preserves_existing_audio_and_repeat(self):
        self.load(); self.start('old'); old = self.b._queue; self.b.cycleRepeat()
        with patch.object(support.backend.random, 'shuffle', side_effect=RuntimeError('Test failure')):
            self.assertTrue(self.b.shuffleDetail()); self.until(lambda: not self.b.busy)
        self.assertIs(self.b._queue, old)
        self.assertEqual(self.b.playerVideoId, 'old')
        self.assertEqual(self.b.playerRepeatMode, 'all')
        self.assertEqual(len(self.errors), 1)
        self.api.get_watch_playlist.assert_not_called()
