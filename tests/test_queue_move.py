"""Adjacent queue edits keep exact occurrences, origins and current audio."""
from copy import deepcopy
from unittest.mock import Mock
import test_prefetch as support


class QueueMoveTests(support.AudioPlaybackTestCase):
    def ids(self):
        return [x['videoId'] for x in self.b._queue.tracks]

    def test_move_duplicate_around_current_preserves_audio_source_and_rating(self):
        self.start('A', 'B', 'A', 'C')
        self.b.playFrom('playing', 1); self.until(lambda: self.b.playerState == 'playing')
        queue, current = self.b._queue, self.b._queue.current()
        duplicate = queue.tracks[2]
        source = deepcopy(self.b._library_items_model.snapshot())
        self.b._ytmusic = Mock()
        self.b._player_position = 42; self.b._repeat_mode = 'all'; self.b._player_like_status = 'LIKE'
        played, stops = list(self.played), list(self.stops)
        changes = []; self.b.playerTrackChanged.connect(lambda: changes.append(True))
        self.assertTrue(self.b.moveQueueItem(2, -1))
        self.assertEqual(self.ids(), ['A', 'A', 'B', 'C'])
        self.assertIs(queue.tracks[1], duplicate); self.assertIs(queue.current(), current)
        self.assertEqual(self.b._queue_source_indices, [0, 2, 1, 3])
        self.assertEqual(self.b.playerQueueIndex, 2); self.assertEqual(self.b.playerSourceIndex, 1)
        self.assertEqual(self.b.playerPosition, 42); self.assertEqual(self.b.playerLikeStatus, 'LIKE')
        self.assertEqual(self.b.playerRepeatMode, 'all'); self.assertEqual(self.played, played)
        self.assertEqual(self.stops, stops); self.assertFalse(changes)
        self.assertFalse(self.b._ytmusic.mock_calls)
        self.assertEqual(self.b._library_items_model.snapshot(), source)
        self.assertTrue(self.b.moveQueueItem(2, 1))
        self.assertEqual(self.ids(), ['A', 'A', 'C', 'B'])
        self.assertIs(queue.current(), current); self.assertEqual(self.b.playerQueueIndex, 3)
        self.assertEqual(self.b._next_prefetch_id(), 'A')
        self.assertEqual(self.b.playerPosition, 42); self.assertFalse(changes)
        self.b.restorePlayingSource(1)
        self.assertEqual(self.b._library_items_model.snapshot(), source)
        self.assertEqual(self.b.playerSourceIndex, 1)

    def test_next_prefetch_and_eos_follow_new_order(self):
        self.start('A', 'B', 'C'); self.until(lambda: 'B' in support.core.LOCAL_AUDIO_CACHE)
        self.assertTrue(self.b.moveQueueItem(2, -1))
        self.assertEqual(self.b._next_prefetch_id(), 'C')
        self.until(lambda: 'C' in support.core.LOCAL_AUDIO_CACHE)
        self.eos(); self.until(lambda: self.b.playerState == 'playing' and self.b.playerTitle == 'C')
        self.assertEqual(self.ids(), ['A', 'C', 'B'])
        self.b.previousTrack(); self.until(lambda: self.b.playerState == 'playing' and self.b.playerTitle == 'A')

    def test_pause_stop_repeat_and_manual_copy_flags_survive(self):
        self.start('A', 'B'); self.b.enqueueFrom('playing', 1, False, {})
        copy = self.b._queue.tracks[2]
        self.b._player_state = 'paused'; played = list(self.played)
        self.b._repeat_mode = 'one'; self.b._queue.shuffle_active = True
        self.assertTrue(self.b.moveQueueItem(2, -1))
        self.assertIs(self.b._queue.tracks[1], copy); self.assertTrue(copy['_guiManualEnqueue'])
        self.assertEqual(self.b.playerState, 'paused'); self.assertEqual(self.played, played)
        self.assertEqual(self.b.playerRepeatMode, 'one'); self.assertTrue(self.b._queue.shuffle_active)
        self.b.stopPlayback(); self.assertTrue(self.b.moveQueueItem(0, 1))
        self.assertEqual(self.b.playerState, 'idle'); self.assertEqual(self.b.playerTitle, 'A')
        self.assertEqual(self.played, played)

    def test_pending_current_moves_and_is_still_removed_on_next(self):
        self.start('A', 'B', 'C'); self.b.removeQueueItem(0)
        self.assertTrue(self.b.moveQueueItem(0, 1))
        self.assertEqual(self.ids(), ['B', 'A', 'C']); self.assertTrue(self.b.playerRemovalPending)
        self.b.nextTrack(); self.until(lambda: self.b.playerState == 'playing' and self.b.playerTitle == 'C')
        self.assertEqual(self.ids(), ['B', 'C'])

    def test_playlist_binding_preserved_but_later_playlist_reorder_does_not_undo_local_order(self):
        self.start('A', 'B', 'C')
        for i, song in enumerate(self.b._queue.tracks): song['_guiPlaylistBinding'] = ('PLsource', str(i))
        self.assertTrue(self.b.moveQueueItem(2, -1))
        self.b._sync_playlist_queue_order(dict(meta=dict(playlistId='PLsource'), tracks=[dict(setVideoId=str(i)) for i in range(3)]))
        self.assertEqual(self.ids(), ['A', 'C', 'B'])
        self.b._sync_removed_playlist_queue_item('PLsource', '2')
        self.assertEqual(self.ids(), ['A', 'B'])

    def test_invalid_boundaries_transition_waiting_and_empty_are_noops(self):
        self.assertFalse(self.b.moveQueueItem(0, 1))
        self.start('A', 'B'); tracks = list(self.b._queue.tracks)
        for index, direction in ((-1, 1), (2, -1), (0, -1), (1, 1), (0, 0), (0, 2)):
            self.assertFalse(self.b.moveQueueItem(index, direction))
        self.b._playback_transitioning = True
        self.assertFalse(self.b.moveQueueItem(0, 1)); self.b._playback_transitioning = False
        self.b._radio_waiting_for_tracks = self.b._queue
        self.assertFalse(self.b.playerCanMoveQueue); self.assertFalse(self.b.moveQueueItem(0, 1))
        self.b._radio_waiting_for_tracks = None
        self.b._closing.set(); self.assertFalse(self.b.moveQueueItem(0, 1)); self.b._closing.clear()
        self.assertEqual(self.b._queue.tracks, tracks)
