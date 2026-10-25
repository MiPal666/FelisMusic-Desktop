"""Repeat behavior with real queue/cache logic and fake offline audio."""
import test_prefetch as support


class RepeatTests(support.AudioPlaybackTestCase):
    def mode(self, mode):
        for _ in range(3):
            if self.b.playerRepeatMode == mode:
                return
            self.b.cycleRepeat()
        self.assertEqual(self.b.playerRepeatMode, mode)

    def test_cycle_and_empty_queue_are_safe(self):
        self.assertEqual(self.b.playerRepeatMode, 'off')
        for expected in ('all', 'one', 'off'):
            self.b.cycleRepeat()
            self.assertEqual(self.b.playerRepeatMode, expected)
            self.assertFalse(self.b.playerCanNext)
            self.assertFalse(self.b.playerCanPrevious)
            self.b.nextTrack()
            self.b.previousTrack()
        self.assertFalse(self.played)

    def test_one_replays_current_from_cache_and_does_not_prefetch_next(self):
        self.mode('one')
        self.start('A', 'B')
        for count in (2, 3):
            self.eos()
            self.until(lambda: self.b.playerState == 'playing')
            self.assertEqual(len(self.played), count)
            self.assertEqual(self.b.playerQueueIndex, 0)
        self.assertEqual(self.played, ['A', 'A', 'A'])
        self.assertEqual(self.downloads['A'], 1)
        self.assertNotIn('B', self.downloads)
        self.assertFalse(self.errors)

    def test_manual_next_previous_ignore_repeat_one_and_keep_boundaries(self):
        self.mode('one')
        self.start('A', 'B')
        self.assertFalse(self.b.playerCanPrevious)
        self.b.nextTrack()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerQueueIndex, 1)
        self.assertFalse(self.b.playerCanNext)
        self.eos()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played[-2:], ['B', 'B'])
        self.b.previousTrack()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerQueueIndex, 0)

    def test_all_wraps_automatically_and_manually_using_cache(self):
        self.mode('all')
        self.start('A', 'B')
        self.assertTrue(self.b.playerCanPrevious)
        self.until(lambda: 'B' in support.core.LOCAL_AUDIO_CACHE)
        self.eos()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerQueueIndex, 1)
        self.assertTrue(self.b.playerCanNext)
        self.eos()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerQueueIndex, 0)
        self.b.previousTrack()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerQueueIndex, 1)
        self.b.nextTrack()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerQueueIndex, 0)
        self.assertEqual(self.played, ['A', 'B', 'A', 'B', 'A'])
        self.assertEqual(self.downloads['A'], 1)
        self.assertEqual(self.downloads['B'], 1)

    def test_last_track_prefetches_first_when_repeat_all_is_enabled(self):
        self.start('A', 'B')
        self.until(lambda: 'B' in support.core.LOCAL_AUDIO_CACHE)
        self.b.nextTrack()
        self.until(lambda: self.b.playerState == 'playing')
        # Simulate an evicted first track to verify wrap-around preparation.
        support.core.LOCAL_AUDIO_CACHE.pop('A')
        self.mode('all')
        self.until(lambda: self.downloads['A'] == 2)
        self.until(lambda: 'A' in support.core.LOCAL_AUDIO_CACHE)
        self.assertEqual(self.b.playerQueueIndex, 1)
        self.assertEqual(self.played, ['A', 'B'])

    def test_single_track_repeat_all_and_changing_mode_while_paused(self):
        self.mode('all')
        self.start('A')
        self.eos()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['A', 'A'])
        self.b._player_state = 'paused'
        self.status.player_state = 'PAUSED'
        self.b._player_position = 42
        count = len(self.played)
        self.mode('one')
        self.mode('off')
        self.assertEqual(self.b.playerState, 'paused')
        self.assertEqual(self.b.playerPosition, 42)
        self.assertEqual(len(self.played), count)

    def test_enabling_repeat_after_end_does_not_restart_without_play(self):
        self.start('A')
        self.eos()
        self.assertEqual(self.b.playerState, 'idle')
        self.mode('all')
        self.b._poll_player()
        self.assertEqual(self.played, ['A'])
        self.assertEqual(self.b.playerState, 'idle')

    def test_repeat_change_cancels_obsolete_prefetch_without_interrupting_audio(self):
        self.blocked.add('B')
        self.start('A', 'B')
        self.until(lambda: self.downloads['B'] == 1)
        self.mode('one')
        self.until(lambda: 'B' in self.cancelled)
        self.assertEqual(self.b.playerState, 'playing')
        self.assertEqual(self.played, ['A'])
        self.assertFalse(self.errors)
        self.mode('off')
        self.release.set()
        self.until(lambda: 'B' in support.core.LOCAL_AUDIO_CACHE)
        self.assertEqual(self.played, ['A'])
