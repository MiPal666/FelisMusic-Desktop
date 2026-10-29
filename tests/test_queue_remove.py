"""Listening-only removal of exact occurrences, offline audio/API stubs."""
from copy import deepcopy
from unittest.mock import Mock
import test_prefetch as support


class QueueRemoveTests(support.AudioPlaybackTestCase):
    def ids(self):
        return [x['videoId'] for x in self.b._queue.tracks]

    def test_duplicate_history_and_next_removal_preserves_audio_and_source(self):
        self.start('A', 'B', 'A', 'C')
        self.b.playFrom('playing', 2); self.until(lambda: self.b.playerState == 'playing')
        current = self.b._queue.current()
        original = deepcopy(self.b._library_items_model.snapshot())
        self.b._ytmusic = Mock()
        self.b._player_position = 42; self.b._repeat_mode = 'all'
        played, stops = list(self.played), list(self.stops)
        self.assertTrue(self.b.removeQueueItem(0))
        self.assertEqual(self.ids(), ['B', 'A', 'C'])
        self.assertIs(self.b._queue.current(), current)
        self.assertEqual(self.b.playerQueueIndex, 1)
        self.assertEqual(self.b.playerSourceIndex, 2)
        self.assertEqual(self.b.playerPosition, 42)
        self.assertTrue(self.b.removeQueueItem(2))
        self.assertEqual(self.ids(), ['B', 'A'])
        self.assertEqual(self.b.playerRepeatMode, 'all')
        self.assertEqual(self.b._next_prefetch_id(), 'B')
        self.assertEqual(self.played, played); self.assertEqual(self.stops, stops)
        self.assertEqual(self.b._library_items_model.snapshot(), original)
        self.b._ytmusic.assert_not_called()
        self.assertFalse(self.b._ytmusic.mock_calls)
        self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual(self.b._library_items_model.snapshot(), original)

    def test_current_deferred_then_eos_ignores_repeat_one(self):
        self.start('A', 'B', 'A'); self.b._repeat_mode = 'one'
        played = list(self.played)
        self.assertTrue(self.b.removeQueueItem(0))
        self.assertTrue(self.b.playerRemovalPending)
        self.assertFalse(self.b.removeQueueItem(0))
        self.assertEqual(self.ids(), ['A', 'B', 'A']); self.assertEqual(self.played, played)
        self.assertEqual(self.b._next_prefetch_id(), 'B')
        self.eos(); self.until(lambda: self.b.playerState == 'playing' and self.b.playerTitle == 'B')
        self.assertEqual(self.ids(), ['B', 'A'])
        self.assertFalse(self.b.playerRemovalPending)
        self.assertEqual(self.b.playerRepeatMode, 'one')

    def test_other_removal_keeps_deferred_current_and_pause(self):
        self.start('A', 'B', 'C'); self.b._player_state = 'paused'
        self.b._player_position = 42
        self.assertTrue(self.b.removeQueueItem(0))
        self.assertTrue(self.b.removeQueueItem(1))
        self.assertEqual(self.ids(), ['A', 'C'])
        self.assertTrue(self.b.playerRemovalPending)
        self.assertEqual(self.b.playerState, 'paused'); self.assertEqual(self.b.playerPosition, 42)
        self.b.stopPlayback()
        self.assertEqual(self.ids(), ['C']); self.assertEqual(self.b.playerState, 'idle')
        self.assertEqual(self.played, ['A'])

    def test_last_playing_occurrence_finishes_to_empty_and_can_enqueue_again(self):
        self.start('A'); self.assertTrue(self.b.removeQueueItem(0))
        self.eos(); self.assertEqual(self.ids(), [])
        self.assertFalse(self.b.playerHasTrack); self.assertEqual(self.b.playerQueueIndex, -1)
        self.assertEqual(self.b.playerState, 'idle')
        self.assertTrue(self.b.enqueueFrom('library', 0, False, {}))
        self.b.togglePlayPause(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['A', 'A'])

    def test_stopped_current_removed_immediately_without_starting_successor(self):
        self.start('A', 'B'); self.b.stopPlayback(); played = list(self.played)
        self.assertTrue(self.b.removeQueueItem(0))
        self.assertEqual(self.ids(), ['B']); self.assertEqual(self.b.playerTitle, 'B')
        self.assertEqual(self.b.playerState, 'idle'); self.assertEqual(self.played, played)
        self.assertTrue(self.b.removeQueueItem(0))
        self.assertFalse(self.b.playerHasTrack); self.assertEqual(self.b.playingTracksModel.count, 0)

    def test_next_previous_and_repeat_all_after_pending_removal(self):
        self.start('A', 'B', 'C')
        self.b.playFrom('playing', 2); self.until(lambda: self.b.playerState == 'playing')
        self.b._repeat_mode = 'all'; self.b.removeQueueItem(2)
        self.b.nextTrack(); self.until(lambda: self.b.playerState == 'playing' and self.b.playerTitle == 'A')
        self.assertEqual(self.ids(), ['A', 'B'])
        self.b.playFrom('playing', 1); self.until(lambda: self.b.playerState == 'playing')
        self.b.removeQueueItem(1); self.b.previousTrack()
        self.until(lambda: self.b.playerState == 'playing' and self.b.playerTitle == 'A')
        self.assertEqual(self.ids(), ['A'])

    def test_radio_and_manual_occurrences_survive_exact_removal(self):
        self.start('A', 'B'); self.b._queue.radio_active = True
        self.b.enqueueFrom('playing', 1, False, {})
        self.assertTrue(self.b.removeQueueItem(1))
        self.assertEqual(self.ids(), ['A', 'B'])
        self.assertTrue(self.b._queue.tracks[1]['_guiManualEnqueue'])
        self.assertTrue(self.b._queue.radio_active)

    def test_invalid_index_transition_and_closing_do_not_edit(self):
        self.assertFalse(self.b.removeQueueItem(0))
        self.start('A', 'B')
        for index in (-1, 2): self.assertFalse(self.b.removeQueueItem(index))
        self.b._playback_transitioning = True
        self.assertFalse(self.b.removeQueueItem(1)); self.b._playback_transitioning = False
        self.b._closing.set()
        self.assertFalse(self.b.removeQueueItem(1)); self.b._closing.clear()
        self.assertEqual(self.ids(), ['A', 'B'])
