"""Repeat behavior with real queue/cache logic and fake offline audio."""
import test_prefetch as support


class RepeatTests(support.AudioPlaybackTestCase):
    def test_new_playback_resets_repeat_for_each_browsing_source(self):
        for mode in ('all', 'one'):
            for source in ('library', 'detail', 'search', 'liked', 'history'):
                with self.subTest(mode=mode, source=source):
                    self.start('old')
                    self.mode(mode)
                    self.b._source_model(source).set_items([
                        dict(kind='song', title='New', videoId='new'),
                        dict(kind='song', title='Next', videoId='next')])
                    events = []
                    def record():
                        events.append(self.b.playerRepeatMode)
                    self.b.playerChanged.connect(record)
                    self.b.playFrom(source, 0)
                    self.until(lambda: self.b.playerState == 'playing')
                    self.b.playerChanged.disconnect(record)
                    self.assertEqual(self.b.playerRepeatMode, 'off')
                    self.assertIn('off', events)
                    self.assertEqual(self.b.playerVideoId, 'new')
                    self.assertEqual(self.b._next_prefetch_id(), 'next')

    def test_restarting_same_browsing_collection_creates_new_repeat_context(self):
        self.start('A', 'B')
        self.mode('one')
        old_queue = self.b._queue
        self.b.playFrom('library', 1)
        self.until(lambda: self.b.playerState == 'playing')
        self.assertIsNot(self.b._queue, old_queue)
        self.assertEqual(self.b.playerRepeatMode, 'off')
        self.assertEqual(self.b.playerVideoId, 'B')

    def test_queue_selection_pause_stop_and_restart_preserve_repeat(self):
        self.mc.pause = lambda: setattr(self.status, 'player_state', 'PAUSED')
        self.mc.play = lambda: setattr(self.status, 'player_state', 'PLAYING')
        self.start('A', 'B')
        for mode in ('all', 'one'):
            with self.subTest(mode=mode):
                self.mode(mode)
                queue = self.b._queue
                self.b.togglePlayPause()
                self.assertEqual(self.b.playerState, 'paused')
                self.assertEqual(self.b.playerRepeatMode, mode)
                self.b.togglePlayPause()
                self.b.playFrom('playing', 1)
                self.until(lambda: self.b.playerState == 'playing')
                self.assertEqual(self.b.playerRepeatMode, mode)
                self.b.stopPlayback()
                self.assertEqual(self.b.playerRepeatMode, mode)
                self.b.togglePlayPause()
                self.until(lambda: self.b.playerState == 'playing')
                self.assertEqual(self.b.playerRepeatMode, mode)
                self.assertIs(self.b._queue, queue)

    def test_browsing_cover_and_invalid_playback_leave_repeat_unchanged(self):
        self.b._detail_title = 'Album'
        self.b._detail_tracks_model.set_items([dict(kind='song', title='A', videoId='A')])
        self.b.playFrom('detail', 0)
        self.until(lambda: self.b.playerState == 'playing')
        self.mode('one'); queue = self.b._queue
        self.b.clearDetail()
        self.assertEqual(self.b.playerRepeatMode, 'one')
        self.assertTrue(self.b.restorePlayingSource(1))
        for source, index in (('detail', -1), ('detail', 99), ('playing', 99), ('missing', 0)):
            self.b.playFrom(source, index)
            self.assertEqual(self.b.playerRepeatMode, 'one')
            self.assertIs(self.b._queue, queue)

    def test_first_enqueue_creates_idle_queue_with_repeat_off(self):
        self.mode('one')
        self.b._search_results_model.set_items([dict(kind='song', videoId='A', title='A')])
        self.assertTrue(self.b.enqueueFrom('search', 0, False, {}))
        self.assertEqual(self.b.playerRepeatMode, 'off')
        self.assertEqual(self.b.playerState, 'idle')
        self.assertFalse(self.played)

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
        self.start('A', 'B')
        self.mode('one')
        for count in (2, 3):
            self.eos()
            self.until(lambda: self.b.playerState == 'playing')
            self.assertEqual(len(self.played), count)
            self.assertEqual(self.b.playerQueueIndex, 0)
        self.assertEqual(self.played, ['A', 'A', 'A'])
        self.assertEqual(self.downloads['A'], 1)
        self.assertEqual(self.b._next_prefetch_id(), '')
        self.assertFalse(self.errors)

    def test_manual_next_previous_ignore_repeat_one_and_keep_boundaries(self):
        self.start('A', 'B')
        self.mode('one')
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
        self.start('A', 'B')
        self.mode('all')
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
        self.start('A')
        self.mode('all')
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
