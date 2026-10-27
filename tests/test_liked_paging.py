"""Incremental browsing; no real account/network/audio."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock, patch
import test_prefetch as support


class LikedPagingTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.b._ytmusic = Mock()
        self.calls = []; self.entered = Event(); self.block = False
        self.pages = [([self.song('Z'), self.song('A')], True), ([self.song('B')], False)]
        owner = self
        class Pages:
            def __init__(self, api, pid, **kwargs):
                owner.calls.append((api, pid, kwargs)); self.index = 0
            def next_page(self):
                if self.index == 1:
                    owner.entered.set()
                    if owner.block: owner.release.wait(3)
                value = owner.pages[self.index]; self.index += 1
                if isinstance(value, Exception): raise value
                return deepcopy(value)
        self.page_patch = patch.object(support.backend, 'PlaylistPages', Pages)
        self.page_patch.start(); self.addCleanup(self.page_patch.stop)

    @staticmethod
    def song(vid):
        return dict(videoId=vid, title=vid, duration='3:00', likeStatus='LIKE')

    def ids(self):
        return [x['videoId'] for x in self.b.likedModel.snapshot()]

    def load_first(self):
        self.block = True; self.b.loadLiked()
        self.until(lambda: self.entered.is_set() and not self.b.busy)

    def test_first_page_visible_before_rest_without_global_busy_or_partial_actions(self):
        self.load_first()
        self.assertEqual(self.ids(), ['Z', 'A'])
        self.assertTrue(self.b.likedLoading); self.assertFalse(self.b.likedComplete)
        self.b.playFrom('liked', 0); self.until(lambda: self.b.playerState == 'playing')
        self.assertTrue(self.b.playerQueueLoading)
        self.assertEqual(self.b.playerVideoId, 'Z')
        self.assertFalse(self.b.startLikedPlayback('shuffle'))
        self.assertFalse(self.b.enqueueFrom('liked', 0, False, {}))
        self.assertFalse(self.b.openPlaylistSave('liked', 0))
        self.b.selectAllTracks('liked'); self.assertEqual(self.b.selectedTrackIndices, [])
        self.release.set(); self.until(lambda: self.b.likedComplete)
        self.assertEqual(self.ids(), ['Z', 'A', 'B'])
        self.assertFalse(self.b.likedLoading)
        self.assertEqual(self.calls[0][1:], ('LM', {'liked': True}))
        self.b.playFrom('liked', 2); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, 'B')

    def test_three_thousand_items_no_cap_duplicates_and_unavailable_filter(self):
        self.pages = [([self.song(str(i)) for i in range(n, n+100)], n < 2900)
                      for n in range(0, 3000, 100)]
        self.pages[-1][0].extend([self.song('0'), dict(self.song('bad'), isAvailable=False)])
        self.b.loadLiked(); self.until(lambda: self.b.likedComplete)
        self.assertEqual(self.b.likedModel.count, 3001)
        self.assertEqual(self.ids()[:2], ['0', '1']); self.assertEqual(self.ids()[-1], '0')
        self.assertNotIn('bad', self.ids())

    def test_final_sort_only_after_complete_and_default_appends_without_reset(self):
        self.b._liked_order = 'a_to_z'; self.load_first()
        self.assertEqual(self.ids(), ['Z', 'A'])
        self.b.sortLiked('z_to_a'); self.assertEqual(self.b._liked_order, 'a_to_z')
        self.release.set(); self.until(lambda: self.b.likedComplete)
        self.assertEqual(self.ids(), ['A', 'B', 'Z'])

    def test_error_preserves_prefix_marks_incomplete_and_reload_recovers(self):
        self.pages[1] = TimeoutError('secret')
        self.b.loadLiked(); self.until(lambda: not self.b.likedLoading)
        self.assertFalse(self.b.likedComplete); self.assertEqual(self.ids(), ['Z', 'A'])
        self.assertFalse(self.b.busy); self.assertFalse(self.errors)
        self.pages = [([self.song('fresh')], False)]
        self.b.loadLiked(); self.until(lambda: self.b.likedComplete)
        self.assertEqual(self.ids(), ['fresh'])

    def test_stale_page_after_refresh_cannot_append_to_new_snapshot(self):
        self.load_first()
        self.b.loadLiked()  # old next request is still in the serial worker
        self.release.set(); self.until(lambda: self.b.likedComplete and not self.b.busy)
        self.assertEqual(self.ids(), ['Z', 'A', 'B'])
        self.assertEqual(len(self.calls), 2)

    def test_background_completion_does_not_clear_other_user_request_busy(self):
        self.load_first()
        self.b._set_busy(True)
        self.release.set(); self.until(lambda: self.b.likedComplete)
        self.assertTrue(self.b.busy)
        self.b._set_busy(False)

    def test_background_does_not_replace_current_audio_queue_or_navigation_detail(self):
        self.start('playing-song')
        queue = self.b._queue
        self.b._detail_title = 'Other'; self.b._detail_meta = {'kind': 'album', 'browseId': 'other'}
        self.b.loadLiked(); self.until(lambda: self.b.likedComplete)
        self.assertIs(self.b._queue, queue)
        self.assertEqual(self.b.playerVideoId, 'playing-song')
        self.assertEqual(self.b.detailTitle, 'Other')
        self.assertEqual(self.played, ['playing-song'])

    def play_partial(self, index=1):
        self.load_first()
        self.b.playFrom('liked', index)
        self.until(lambda: self.b.playerState == 'playing')

    def test_play_first_block_appends_without_restarting_current_and_prefetches_next(self):
        self.play_partial()
        queue = self.b._queue; current = queue.current()
        self.b._player_position = 42
        self.b.cycleRepeat()
        self.release.set(); self.until(lambda: self.b.likedComplete)
        self.assertIs(self.b._queue, queue); self.assertIs(queue.current(), current)
        self.assertEqual([x['videoId'] for x in queue.tracks], ['Z', 'A', 'B'])
        self.assertEqual(self.b.playerQueueIndex, 1); self.assertEqual(self.b.playerPosition, 42)
        self.assertEqual(self.b.playerRepeatMode, 'all')
        self.assertEqual(self.played, ['A'])
        self.until(lambda: 'B' in support.core.LOCAL_AUDIO_CACHE)
        self.assertFalse(self.b.playerQueueLoading); self.assertFalse(self.b.playerQueueIncomplete)
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, 'B')

    def test_natural_tail_waits_and_arrival_resumes_into_new_block(self):
        self.play_partial(); self.eos()
        self.assertTrue(self.b.playerWaitingForTracks)
        self.assertFalse(self.b.playerWaitingForRadio)
        self.assertEqual(self.b.playerState, 'idle')
        self.release.set(); self.until(lambda: self.b.playerState == 'playing' and self.b.playerVideoId == 'B')
        self.assertFalse(self.b.playerWaitingForTracks)
        self.assertEqual(self.played, ['A', 'B'])

    def test_stop_while_waiting_keeps_queue_growth_but_cancels_auto_resume(self):
        self.play_partial(); self.eos(); self.b.stopPlayback()
        self.assertFalse(self.b.playerWaitingForTracks)
        self.release.set(); self.until(lambda: self.b.likedComplete)
        self.assertEqual(self.b.playerState, 'idle'); self.assertEqual(self.played, ['A'])
        self.assertEqual(self.b.playerQueueCount, 3)

    def test_stop_before_tail_never_restarts_audio_on_append(self):
        self.play_partial(); self.b.stopPlayback()
        self.release.set(); self.until(lambda: self.b.likedComplete)
        self.assertEqual(self.b.playerState, 'idle'); self.assertEqual(self.played, ['A'])

    def test_paused_audio_remains_paused_on_arrival(self):
        self.play_partial(); self.b._set_player_state('paused')
        self.release.set(); self.until(lambda: self.b.likedComplete)
        self.assertEqual(self.b.playerState, 'paused'); self.assertEqual(self.played, ['A'])

    def test_new_queue_never_receives_late_liked_tracks_or_auto_start(self):
        self.play_partial(); self.eos()
        self.start('other', 'next')
        queue = self.b._queue
        self.release.set(); self.until(lambda: self.b.likedComplete)
        self.assertIs(self.b._queue, queue)
        self.assertEqual([x['videoId'] for x in queue.tracks], ['other', 'next'])
        self.assertEqual(self.b.playerVideoId, 'other')
        self.assertFalse(self.b.playerQueueLoading); self.assertFalse(self.b.playerWaitingForTracks)

    def test_error_while_waiting_marks_queue_incomplete_without_resume(self):
        self.pages[1] = TimeoutError()
        self.play_partial(); self.eos()
        self.release.set(); self.until(lambda: not self.b.likedLoading)
        self.assertTrue(self.b.playerQueueIncomplete)
        self.assertFalse(self.b.playerQueueLoading); self.assertFalse(self.b.playerWaitingForTracks)
        self.assertEqual(self.b.playerState, 'idle'); self.assertEqual(self.played, ['A'])

    def test_refresh_detaches_old_incomplete_queue_and_cancels_wait(self):
        self.play_partial(); self.eos()
        queue = self.b._queue
        self.b.loadLiked()
        self.release.set(); self.until(lambda: self.b.likedComplete)
        self.assertIs(self.b._queue, queue)
        self.assertEqual(queue.count(), 2)
        self.assertTrue(self.b.playerQueueIncomplete)
        self.assertFalse(self.b.playerWaitingForTracks)
        self.assertEqual(self.played, ['A'])

    def test_repeat_all_waits_at_temporary_tail_then_wraps_only_at_true_end(self):
        self.play_partial(); self.b.cycleRepeat(); self.eos()
        self.assertTrue(self.b.playerWaitingForTracks)
        self.assertEqual(self.b.playerQueueIndex, 1)
        self.release.set(); self.until(lambda: self.b.playerVideoId == 'B' and self.b.playerState == 'playing')
        self.eos(); self.until(lambda: self.b.playerVideoId == 'Z' and self.b.playerState == 'playing')

    def test_repeat_one_keeps_current_while_pages_append(self):
        self.play_partial(); self.b.cycleRepeat(); self.b.cycleRepeat()
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, 'A')
        self.assertFalse(self.b.playerWaitingForTracks)
        self.release.set(); self.until(lambda: self.b.likedComplete)
        self.assertEqual(self.b.playerVideoId, 'A'); self.assertEqual(self.b.playerRepeatMode, 'one')

    def test_empty_final_page_resolves_wait_and_repeat_all_can_wrap(self):
        self.pages[1] = ([], False)
        self.play_partial(); self.b.cycleRepeat(); self.eos()
        self.release.set(); self.until(lambda: self.b.likedComplete and self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, 'Z')
        self.assertFalse(self.b.playerWaitingForTracks)

    def test_cover_full_sorted_snapshot_and_occurrence_mapping_preserve_queue_order(self):
        self.b._liked_order = 'a_to_z'
        self.b.playbackSourceCaptured.connect(lambda: self.b.setPlaybackSourceContext({'page': 2, 'likedOrder': 'a_to_z'}))
        self.play_partial(0)
        self.release.set(); self.until(lambda: self.b.likedComplete)
        self.assertEqual([x['videoId'] for x in self.b._queue.tracks], ['Z', 'A', 'B'])
        self.assertEqual(self.b.playerSourceIndex, 2)
        self.b._liked_model.set_items([])
        self.assertTrue(self.b.restorePlayingSource(2))
        self.assertEqual(self.ids(), ['A', 'B', 'Z'])
        self.b.playFrom('playing', 2); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerSourceIndex, 1)
        self.assertEqual(self.b.playerSourceContext['page'], 2)

    def test_manual_insertion_stays_in_place_and_duplicates_are_not_removed(self):
        self.pages[1] = ([self.song('Z'), self.song('B')], False)
        self.play_partial(0)
        self.b._library_items_model.set_items([self.b._track(self.song('manual'))])
        self.assertTrue(self.b.enqueueFrom('library', 0, True, {'page': 1}))
        manual = self.b._queue.tracks[1]
        self.release.set(); self.until(lambda: self.b.likedComplete)
        self.assertEqual([x['videoId'] for x in self.b._queue.tracks], ['Z', 'manual', 'A', 'Z', 'B'])
        self.assertIs(self.b._queue.tracks[1], manual)
        self.b.playFrom('playing', 3); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerSourceIndex, 2)

    def test_select_single_and_enter_works_but_partial_batch_actions_remain_disabled(self):
        self.load_first()
        self.b.selectTrack('liked', 1, False, False)
        self.assertEqual(self.b.selectedTrackIndices, [1])
        self.b.selectTrack('liked', 0, True, False)
        self.assertEqual(self.b.selectedTrackIndices, [1])
        self.assertFalse(self.b.openSelectedPlaylistSave())
        self.b.playSelectedTrack(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, 'A')

    def test_many_pages_append_all_occurrences_and_keep_current_object(self):
        self.pages = [([self.song(str(i)) for i in range(n, n+100)], n < 2900)
                      for n in range(0, 3000, 100)]
        self.play_partial(50)
        queue = self.b._queue; current = queue.current()
        self.release.set(); self.until(lambda: self.b.likedComplete)
        self.assertIs(self.b._queue, queue); self.assertIs(queue.current(), current)
        self.assertEqual(queue.count(), 3000)
        self.assertEqual([x['videoId'] for x in queue.tracks], [str(i) for i in range(3000)])
        self.assertEqual(self.b.playerQueueIndex, 50)
        self.assertEqual(self.played, ['50'])

    def test_empty_intermediate_page_keeps_wait_until_nonempty_next_page(self):
        self.play_partial(); self.eos()
        revision = self.b._liked_load_revision
        self.b._extend_liked_queue([], revision, True)
        self.assertTrue(self.b.playerWaitingForTracks)
        self.assertEqual(self.played, ['A'])
        self.release.set(); self.until(lambda: self.b.playerVideoId == 'B' and self.b.playerState == 'playing')
