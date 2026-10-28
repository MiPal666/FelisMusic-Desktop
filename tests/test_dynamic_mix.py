"""RD mixes: one preview, exact source cursor, refill driven by playback."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock, patch
import test_prefetch as support


class DynamicMixTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock(); self.b._ytmusic = self.api
        self.pages = [([self.song(x) for x in 'ABCD'], True),
                      ([self.song(x) for x in 'EFG'], True), ([self.song('H')], False)]
        self.calls = []; self.created = []; self.entered = Event(); self.block_next = False
        owner = self
        class Pages:
            def __init__(self, api, pid, *, shuffle=True, limit=None):
                self.api, self.pid, self.index = api, pid, 0
                owner.created.append((pid, shuffle, limit))
                self._phase = 'initial_request'
            def next_page(self):
                owner.calls.append((self.pid, self.index))
                self._phase = 'continuation_request' if self.index else 'initial_request'
                if self.index:
                    owner.entered.set()
                    if owner.block_next: owner.release.wait(3)
                else:
                    self.api.get_watch_playlist(playlistId=self.pid, limit=0)
                value = owner.pages[self.index]
                if isinstance(value, Exception):
                    if not isinstance(value, TimeoutError): self._phase = 'continuation_parse'
                    raise value
                self.index += 1
                return deepcopy(value)
        for patcher in (patch.object(support.backend, 'WatchPages', Pages),
                        patch.object(support.core, 'current_mix_refill_threshold', return_value=1)):
            patcher.start(); self.addCleanup(patcher.stop)

    @staticmethod
    def song(vid):
        return dict(videoId=vid, title=vid, likeStatus='LIKE')

    def load(self, via_mixes=False, pid='RDTMAKsuper'):
        method = self.b.loadMixTracks if via_mixes else self.b.loadPlaylistTracks
        method(pid, 'My Supermix'); self.until(lambda: not self.b.busy)
        self.assertEqual(self.b.detailTracksModel.count, len(self.pages[0][0]))

    def play(self, index=0):
        self.b.playFrom('detail', index); self.until(lambda: self.b.playerState == 'playing')

    def ready_page(self, expected):
        self.until(lambda: not self.b._playlist_stream['load']['fetching'])
        self.assertEqual(self.b.playerQueueCount, expected)

    def near_end(self):
        self.b.playFrom('playing', self.b.playerQueueCount - 2)
        self.until(lambda: self.b.playerState == 'playing')

    def test_both_entry_points_only_read_initial_page_of_same_id(self):
        for via_mixes in (False, True):
            self.load(via_mixes=via_mixes)
            for _ in range(10): self.app.processEvents()
            self.assertTrue(self.b.detailMeta['dynamicMix'])
            self.assertFalse(self.b.detailLoading); self.assertTrue(self.b.detailComplete)
            self.assertFalse(self.b.detailCanShuffle); self.assertFalse(self.b.detailCanSavePlaylist)
            self.assertEqual(self.b.detailTitle, 'My Supermix')
        self.assertEqual(self.calls, [('RDTMAKsuper', 0)] * 2)
        self.assertEqual(self.created, [('RDTMAKsuper', False, None)] * 2)
        self.api.get_playlist.assert_not_called()

    def test_prefix_rule_and_vl_normalization(self):
        for pid in ('RDTMAKsuper', 'RDAMVMvideo', 'RDAMPLPLsource', 'RDEMartist', 'RDCLAKcurated'):
            self.assertTrue(self.b._is_dynamic_playlist(pid))
        for pid in ('PLmine', 'LM', 'LL', 'OLAKalbum', '', None):
            self.assertFalse(self.b._is_dynamic_playlist(pid))
        self.load(pid='VLRDTMAKsuper')
        self.assertEqual(self.created, [('RDTMAKsuper', False, None)])

    def test_no_eager_pages_then_two_refills_from_original_cursor_and_real_end(self):
        self.load(); self.play()
        self.assertTrue(self.b.playerQueueDynamic); self.assertFalse(self.b.playerQueueLoading)
        self.assertFalse(self.b.playerCanShuffle)
        self.assertFalse(self.b._maybe_refill_radio()); self.assertEqual(len(self.calls), 1)
        self.near_end(); self.assertTrue(self.b._maybe_refill_radio()); self.ready_page(7)
        for _ in range(10): self.app.processEvents()
        self.assertEqual(len(self.calls), 2)
        self.near_end(); self.assertTrue(self.b._maybe_refill_radio()); self.ready_page(8)
        self.assertFalse(self.b._queue_has_more()); self.assertFalse(self.b._maybe_refill_radio())
        self.assertEqual(self.calls, [('RDTMAKsuper', 0), ('RDTMAKsuper', 1), ('RDTMAKsuper', 2)])
        self.api.get_watch_playlist.assert_called_once_with(playlistId='RDTMAKsuper', limit=0)

    def test_preview_while_another_queue_plays_does_not_refill_new_mix(self):
        self.start('old', 'next'); old = self.b._queue
        self.load(); self.b._maybe_refill_radio()
        self.assertIs(self.b._queue, old); self.assertEqual(len(self.calls), 1)

    def test_eos_waits_and_resumes_when_block_arrives(self):
        self.load(); self.play(3); self.block_next = True
        self.eos(); self.until(self.entered.is_set)
        self.assertTrue(self.b.playerWaitingForTracks); self.assertTrue(self.b.playerQueueLoading)
        self.assertFalse(self.b._maybe_refill_radio())
        self.release.set(); self.ready_page(7)
        self.until(lambda: self.b.playerState == 'playing' and self.b.playerVideoId == 'E')

    def test_stop_cancels_resume_but_accepts_inflight_block(self):
        self.load(); self.play(3); self.block_next = True
        self.eos(); self.until(self.entered.is_set)
        self.b.stopPlayback(); plays = len(self.played)
        self.release.set(); self.ready_page(7)
        self.assertEqual(self.b.playerState, 'idle'); self.assertEqual(len(self.played), plays)
        self.assertFalse(self.b._maybe_refill_radio())

    def test_pause_does_not_request_more_and_inflight_refill_preserves_pause(self):
        self.load(); self.play(3)
        self.b._player_state = 'paused'; self.status.player_state = 'PAUSED'
        self.assertFalse(self.b._maybe_refill_radio()); self.assertEqual(len(self.calls), 1)
        self.b._player_state = 'playing'; self.block_next = True
        self.assertTrue(self.b._maybe_refill_radio()); self.until(self.entered.is_set)
        current = self.b._queue.current(); self.b._player_position = 42
        self.b._player_state = 'paused'; self.status.player_state = 'PAUSED'
        self.release.set(); self.ready_page(7)
        self.assertIs(self.b._queue.current(), current)
        self.assertEqual(self.b.playerPosition, 42); self.assertEqual(self.b.playerState, 'paused')

    def test_repeat_all_waits_for_future_and_one_replays_current(self):
        self.load(); self.play(3); self.b.cycleRepeat(); self.block_next = True
        self.eos(); self.assertTrue(self.b.playerWaitingForTracks)
        self.release.set(); self.ready_page(7); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, 'E')
        self.b.cycleRepeat(); self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, 'E')

    def test_refill_preserves_manual_objects_and_duplicate_occurrences(self):
        self.pages[1] = ([self.song('A'), self.song('E')], True)
        self.load(); self.play(3); current = self.b._queue.current()
        self.b._search_results_model.set_items([self.b._track(self.song('X'))])
        self.b.enqueueFrom('search', 0, False, {})
        manual = self.b._queue.tracks[-1]
        self.assertTrue(self.b._maybe_refill_radio()); self.ready_page(7)
        self.assertIs(self.b._queue.current(), current)
        self.assertIs(self.b._queue.tracks[4], manual)
        self.assertEqual([x['videoId'] for x in self.b._queue.tracks], ['A', 'B', 'C', 'D', 'X', 'A', 'E'])
        self.assertTrue(all('_guiPlaylistBinding' not in x for x in self.b._queue.tracks))

    def test_navigation_does_not_replace_source_and_cover_snapshot_grows(self):
        self.load(); self.play(3); self.b.clearDetail()
        self.assertTrue(self.b._maybe_refill_radio()); self.ready_page(7)
        self.assertEqual(self.b.detailTitle, '')
        self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual(self.b.detailMeta['playlistId'], 'RDTMAKsuper')
        self.assertEqual(self.b.detailTracksModel.count, 7)

    def test_reopening_same_mix_preview_does_not_cancel_playing_cursor(self):
        self.load(); self.play(3)
        queue = self.b._queue; playing_load = self.b._playlist_stream['load']
        self.load(via_mixes=True)
        self.assertIs(self.b._queue, queue)
        self.assertIs(self.b._playlist_stream['load'], playing_load)
        self.assertFalse(self.b.playerQueueIncomplete)
        self.assertTrue(self.b._maybe_refill_radio()); self.ready_page(7)
        self.assertEqual(self.b.detailTracksModel.count, 4)
        self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual(self.b.detailTracksModel.count, 7)

    def test_new_queue_ignores_old_inflight_mix_page(self):
        self.load(); self.play(3); self.block_next = True
        self.b._maybe_refill_radio(); self.until(self.entered.is_set)
        self.start('other'); queue = self.b._queue
        self.release.set(); self.until(lambda: not self.b._playlist_load['fetching'])
        self.assertIs(self.b._queue, queue); self.assertEqual(queue.count(), 1)

    def test_transport_failure_has_backoff_and_retries_same_cursor(self):
        self.pages[1] = TimeoutError('PRIVATE')
        self.load(); self.play(3)
        self.assertTrue(self.b._maybe_refill_radio()); self.ready_page(4)
        load = self.b._playlist_stream['load']
        self.assertGreater(load['retry_after'], 0)
        self.assertFalse(self.b._maybe_refill_radio()); self.assertFalse(self.b.playerQueueIncomplete)
        self.pages[1] = ([self.song('E')], False); load['retry_after'] = 0
        self.assertTrue(self.b._maybe_refill_radio()); self.ready_page(5)
        self.assertEqual(self.calls[-2:], [('RDTMAKsuper', 1), ('RDTMAKsuper', 1)])
        self.assertFalse(self.errors)

    def test_bad_continuation_stops_without_request_storm_or_modal(self):
        self.pages[1] = ValueError('PRIVATE')
        self.load(); self.play(3)
        self.assertTrue(self.b._maybe_refill_radio()); self.ready_page(4)
        self.assertTrue(self.b.playerQueueIncomplete); self.assertFalse(self.b._maybe_refill_radio())
        self.assertFalse(self.errors)

    def test_empty_block_with_cursor_is_not_treated_as_end_and_has_backoff(self):
        self.pages[1] = ([], True)
        self.load(); self.play(3)
        self.assertTrue(self.b._maybe_refill_radio()); self.ready_page(4)
        self.assertTrue(self.b._queue_has_more()); self.assertFalse(self.b._maybe_refill_radio())

    def test_server_can_end_after_first_block(self):
        self.pages[0] = (self.pages[0][0], False)
        self.load(); self.play(3)
        self.assertFalse(self.b._queue_has_more()); self.assertFalse(self.b._maybe_refill_radio())
        self.eos(); self.assertEqual(self.b.playerState, 'idle')
