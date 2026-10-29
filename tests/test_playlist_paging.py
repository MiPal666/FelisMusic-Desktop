"""Incremental playlist browsing and its finite playback queue, offline only."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock, patch
import test_prefetch as support


class PlaylistPagingTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.b._ytmusic = Mock()
        self.entered = Event(); self.calls = []
        self.pages = [([self.song('A', 0), self.song('B', 1)], True),
                      ([self.song('B', 2), self.song('C', 3)], False)]
        owner = self
        class Pages:
            def __init__(self, api, pid, **kwargs):
                self.pid = pid; self.index = 0
                self.metadata = dict(title=pid, owned=True, **getattr(owner, 'header_metadata', {}))
            def next_page(self):
                owner.calls.append((self.pid, self.index))
                if self.index:
                    owner.entered.set(); owner.release.wait(3)
                value = owner.pages[self.index]; self.index += 1
                if isinstance(value, Exception): raise value
                return deepcopy(value)
        pager = patch.object(support.backend, 'PlaylistPages', Pages)
        pager.start(); self.addCleanup(pager.stop)

    @staticmethod
    def song(vid, index):
        return dict(videoId=vid, title=vid, setVideoId=f'set-{index}', likeStatus='LIKE')

    def load(self, pid='PLsource'):
        self.b.loadPlaylistTracks(pid, pid)
        self.until(lambda: not self.b.busy and self.entered.is_set())

    def play(self, index=0):
        self.b.playFrom('detail', index)
        self.until(lambda: self.b.playerState == 'playing')

    def finish(self):
        self.release.set(); self.until(lambda: not self.b.detailLoading)

    def ids(self):
        return [x['videoId'] for x in self.b._queue.tracks]

    def test_first_page_is_visible_without_global_busy_and_full_actions_wait(self):
        self.load()
        self.assertEqual(self.b.detailTracksModel.count, 2)
        self.assertTrue(self.b.detailLoading); self.assertFalse(self.b.detailComplete)
        self.assertFalse(self.b.detailCanShuffle); self.assertFalse(self.b.detailCanCollectionRadio)
        self.assertFalse(self.b.detailCanEditPlaylist); self.assertFalse(self.b.detailCanSavePlaylist)
        self.assertFalse(self.b.shuffleDetail()); self.assertFalse(self.b.openCollectionPlaylistSave())
        self.assertFalse(self.b.enqueueFrom('detail', 0, False, {}))
        self.b.selectAllTracks('detail'); self.assertFalse(self.b.selectedTrackIndices)
        self.b.selectTrack('detail', 0, False, False)
        self.assertEqual(self.b.selectedTrackIndices, [0])
        self.b.selectTrack('detail', 1, True, False)
        self.assertEqual(self.b.selectedTrackIndices, [0])
        self.finish()
        self.assertTrue(self.b.detailComplete); self.assertTrue(self.b.detailCanShuffle)
        self.assertTrue(self.b.detailCanEditPlaylist); self.assertTrue(self.b.detailCanSavePlaylist)
        self.assertEqual(self.b.detailTracksModel.count, 4)

    def test_playback_starts_on_prefix_and_appends_exact_occurrences(self):
        self.load(); self.play()
        queue = self.b._queue; current = queue.current(); origin = current['_guiOrigin']
        self.b._player_position = 42; self.b.cycleRepeat()
        self.assertTrue(self.b.playerQueueLoading); self.assertFalse(self.b.playerCanShuffle)
        self.finish()
        self.assertIs(self.b._queue, queue); self.assertIs(queue.current(), current)
        self.assertEqual(self.ids(), ['A', 'B', 'B', 'C'])
        self.assertEqual([x['_guiPlaylistBinding'] for x in queue.tracks],
                         [('PLsource', f'set-{i}') for i in range(4)])
        self.assertEqual([x['_guiOrigin']['index'] for x in queue.tracks], [0, 1, 2, 3])
        self.assertIs(current['_guiOrigin'], origin)
        self.assertEqual(self.b.playerPosition, 42); self.assertEqual(self.b.playerRepeatMode, 'all')
        self.assertFalse(self.b.playerQueueLoading); self.assertFalse(self.b.playerQueueIncomplete)

    def test_whole_playlist_enqueue_waits_for_all_pages(self):
        self.start('current', 'last')
        self.load()
        self.assertFalse(self.b.detailCanEnqueuePlaylist)
        self.assertFalse(self.b.enqueuePlaylistCollection(True, {}))
        self.assertEqual(self.ids(), ['current', 'last'])
        self.finish()
        calls, played = list(self.calls), list(self.played)
        self.assertTrue(self.b.detailCanEnqueuePlaylist)
        self.assertTrue(self.b.enqueuePlaylistCollection(True, {}))
        self.assertEqual(self.ids(), ['current', 'A', 'B', 'B', 'C', 'last'])
        self.assertEqual([x['setVideoId'] for x in self.b._queue.tracks[1:5]],
                         ['set-0', 'set-1', 'set-2', 'set-3'])
        self.assertEqual(self.calls, calls)
        self.assertEqual(self.played, played)

    def test_queue_removal_during_paging_does_not_return_removed_occurrence(self):
        self.load(); self.play()
        source = deepcopy(self.b.detailTracksModel.snapshot())
        self.assertTrue(self.b.removeQueueItem(1))
        self.assertEqual(self.ids(), ['A'])
        self.assertEqual(self.b.detailTracksModel.snapshot(), source)
        self.finish()
        self.assertEqual(self.ids(), ['A', 'B', 'C'])
        self.assertEqual([x['setVideoId'] for x in self.b._queue.tracks], ['set-0', 'set-2', 'set-3'])
        self.assertEqual(self.b.detailTracksModel.count, 4)

    def test_queue_move_during_paging_preserves_origins_and_appends_new_rows(self):
        self.load(); self.play()
        self.assertTrue(self.b.moveQueueItem(0, 1))
        self.assertEqual(self.ids(), ['B', 'A'])
        self.assertEqual(self.b.playerQueueIndex, 1)
        self.finish()
        self.assertEqual(self.ids(), ['B', 'A', 'B', 'C'])
        self.assertEqual(self.b._queue_source_indices, [1, 0, 2, 3])
        self.assertEqual([x['setVideoId'] for x in self.b._queue.tracks],
                         ['set-1', 'set-0', 'set-2', 'set-3'])
        self.assertEqual(self.b.playerSourceIndex, 0)
        self.assertEqual([x['videoId'] for x in self.b.detailTracksModel.snapshot()], ['A', 'B', 'B', 'C'])

    def test_header_metadata_and_total_are_preserved_while_only_complete_lengths_are_summed(self):
        self.header_metadata = dict(author=dict(name='Owner'), year='2024', trackCount=4, duration_seconds=180)
        for i, song in enumerate([song for rows, more in self.pages for song in rows]):
            song['duration'] = f'{i+1}:00'
        self.load()
        self.assertEqual(self.b.detailHeaderSummary, 'Owner · 2024 · Načteno 2 z 4 skladeb')
        self.play(); played=list(self.played)
        self.finish()
        self.assertEqual(self.b.detailHeaderSummary, 'Owner · 2024 · 4 skladby · Délka 10:00')
        self.assertEqual(self.played, played)

    def test_removed_last_prefix_track_waits_and_plays_first_new_occurrence(self):
        self.load(); self.play(1)
        self.assertTrue(self.b.removeQueueItem(1))
        self.eos()
        self.assertTrue(self.b.playerWaitingForTracks)
        self.finish()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.ids(), ['A', 'B', 'C'])
        self.assertEqual(self.b._queue.current()['setVideoId'], 'set-2')
        self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual(self.b.detailTracksModel.count, 4)

    def test_eos_waits_and_continues_when_more_arrives(self):
        self.load(); self.play(1); self.eos()
        self.assertTrue(self.b.playerWaitingForTracks)
        self.finish(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b._queue.current()['setVideoId'], 'set-2')

    def test_stop_cancels_wait_without_canceling_front_loading(self):
        self.load(); self.play(1); self.eos(); self.b.stopPlayback()
        self.finish()
        self.assertEqual(self.b.playerState, 'idle'); self.assertEqual(self.b.playerQueueCount, 4)
        self.assertFalse(self.b.playerWaitingForTracks)
        self.assertEqual(len(self.played), 1)

    def test_repeat_all_waits_at_prefix_and_wraps_only_at_real_end(self):
        self.load(); self.play(1); self.b.cycleRepeat(); self.eos()
        self.assertTrue(self.b.playerWaitingForTracks)
        self.finish(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerQueueIndex, 2)
        self.b.playFrom('playing', 3); self.until(lambda: self.b.playerState == 'playing')
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, 'A')

    def test_repeat_one_replays_current_instead_of_waiting(self):
        self.load(); self.play(1); self.b.cycleRepeat(); self.b.cycleRepeat()
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerQueueIndex, 1)
        self.assertFalse(self.b.playerWaitingForTracks)
        self.finish()

    def test_paused_queue_and_manual_insertions_survive_completion(self):
        self.load(); self.play()
        self.b._player_state = 'paused'; self.status.player_state = 'PAUSED'
        self.b._search_results_model.set_items([self.b._track(self.song('X', 99))])
        self.assertTrue(self.b.enqueueFrom('search', 0, True, {}))
        manual = self.b._queue.tracks[1]
        self.finish()
        self.assertEqual(self.ids(), ['A', 'X', 'B', 'B', 'C'])
        self.assertIs(self.b._queue.tracks[1], manual)
        self.assertEqual(self.b.playerState, 'paused')

    def test_background_error_marks_prefix_incomplete_without_modal(self):
        self.pages[1] = TimeoutError('SECRET')
        self.load(); self.play(1); self.eos(); self.finish()
        self.assertFalse(self.b.detailComplete); self.assertFalse(self.b.playerWaitingForTracks)
        self.assertTrue(self.b.playerQueueIncomplete); self.assertFalse(self.errors)
        self.assertFalse(self.b.playerCanShuffle)
        self.b.clearDetail(); self.assertTrue(self.b.restorePlayingSource(1))
        self.assertFalse(self.b.detailComplete); self.assertFalse(self.b.detailLoading)

    def test_navigation_keeps_playing_queue_loading_and_cover_restores_full_list(self):
        self.load(); self.play(); self.b.clearDetail()
        self.release.set(); self.until(lambda: not self.b.playerQueueLoading)
        self.assertEqual(self.b.detailTitle, '')
        self.assertEqual(self.ids(), ['A', 'B', 'B', 'C'])
        self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual(self.b.detailTracksModel.count, 4)
        self.assertTrue(self.b.detailComplete)

    def test_navigation_without_queue_does_not_overwrite_other_detail(self):
        self.pages[1] = ([self.song('C', 2)], True)
        self.load(); self.b.clearDetail()
        self.release.set(); self.until(lambda: self.b._playlist_load['meta']['playlistLoadState'] == 'error')
        self.assertEqual(self.b.detailTitle, '')
        self.assertEqual(self.calls, [('PLsource', 0), ('PLsource', 1)])

    def test_refresh_does_not_append_old_pages_to_old_prefix_queue(self):
        self.load(); self.play(); old = self.b._queue
        self.b.loadPlaylistTracks('PLsource', 'New')
        self.release.set(); self.until(lambda: not self.b.busy and self.b.detailComplete)
        self.assertIs(self.b._queue, old); self.assertEqual(old.count(), 2)
        self.assertTrue(self.b.playerQueueIncomplete)
        self.assertEqual(self.b.detailTracksModel.count, 4)

    def test_new_queue_does_not_receive_old_playlist_page(self):
        self.load(); self.play()
        self.start('other'); queue = self.b._queue
        self.finish()
        self.assertIs(self.b._queue, queue); self.assertEqual(self.ids(), ['other'])

    def test_page_application_defers_during_foreground_busy(self):
        self.load(); self.play(); self.b._set_busy(True)
        self.release.set()
        for _ in range(20): self.app.processEvents()
        self.assertEqual(self.b.playerQueueCount, 2)
        self.b._set_busy(False); self.until(lambda: self.b.detailComplete)
        self.assertEqual(self.b.playerQueueCount, 4)

    def test_three_thousand_rows_and_empty_intermediate_page(self):
        self.pages = [([self.song(str(i), i) for i in range(100)], True), ([], True),
                      ([self.song(str(i), i) for i in range(100, 3000)], False)]
        self.load(); self.play(); current = self.b._queue.current()
        self.finish()
        self.assertEqual(self.b.detailTracksModel.count, 3000)
        self.assertEqual(self.b.playerQueueCount, 3000)
        self.assertIs(self.b._queue.current(), current)
        self.assertEqual(len(self.calls), 3)

    def test_empty_first_page_still_continues_and_becomes_playable(self):
        self.pages[0] = ([], True)
        self.load()
        self.assertEqual(self.b.detailTracksModel.count, 0)
        self.assertTrue(self.b.detailLoading)
        self.finish(); self.play()
        self.assertEqual(self.ids(), ['B', 'C'])

    def test_single_page_completes_without_background_or_partial_state(self):
        self.pages[0] = ([], False)
        self.b.loadPlaylistTracks('PLempty', 'Empty')
        self.until(lambda: not self.b.busy)
        self.assertEqual(self.b.detailTitle, 'PLempty')
        self.assertTrue(self.b.detailComplete); self.assertFalse(self.b.detailLoading)
        self.assertEqual(self.calls, [('PLempty', 0)])

    def test_first_page_failure_preserves_existing_detail_and_audio(self):
        self.b._detail_meta = {'kind': 'album', 'browseId': 'old'}
        self.b._detail_title = 'Old album'; self.start('old')
        old = self.b._queue; self.pages[0] = RuntimeError('PRIVATE')
        self.b.loadPlaylistTracks('PLfailed', 'New')
        self.until(lambda: not self.b.busy)
        self.assertEqual(self.b.detailTitle, 'Old album')
        self.assertIs(self.b._queue, old)
        self.assertEqual(len(self.errors), 1)
        self.assertNotIn('PRIVATE', self.errors[0])

    def test_foreground_new_playlist_cannot_receive_old_background_page(self):
        self.load()
        self.b.loadPlaylistTracks('PLnew', 'New')
        self.release.set(); self.until(lambda: not self.b.busy and self.b.detailComplete)
        self.assertEqual(self.b.detailMeta['playlistId'], 'PLnew')
        self.assertEqual(self.b.detailTracksModel.count, 4)

