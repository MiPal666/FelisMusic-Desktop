"""Continuous radio through CLI refill logic, with fake account/audio only."""
from copy import deepcopy
from threading import Event
from time import monotonic
from unittest.mock import Mock, patch
import test_prefetch as support


class RadioRefillTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock(); self.b._ytmusic = self.api
        self.initial = [self.song('S')] + [self.song(f'T{i}') for i in range(1, 10)]
        self.block = [self.song(f'N{i}') for i in range(10)]
        self.refill_entered = Event(); self.block_request = False; self.fail = False
        self.api.get_watch_playlist.side_effect = self.watch

    @staticmethod
    def song(vid):
        return dict(videoId=vid, title=vid, duration='3:00', likeStatus='LIKE')

    def watch(self, **kwargs):
        if kwargs.get('videoId') == 'S':
            return {'tracks': deepcopy(self.initial)}
        self.refill_entered.set()
        if self.block_request:
            self.release.wait(3)
        if self.fail:
            raise RuntimeError('Offline')
        return {'tracks': deepcopy(self.block)}

    def radio(self):
        self.b._search_results_model.set_items([dict(self.song('S'), kind='song')])
        self.assertTrue(self.b.startRadioFrom('search', 0))
        self.until(lambda: not self.b.busy)
        self.until(lambda: self.b.playerState == 'playing')

    def near_end(self, index=None):
        self.b.playFrom('playing', self.b._queue.count() - 2 if index is None else index)
        self.until(lambda: self.b.playerState == 'playing')

    def done(self):
        self.until(lambda: not self.b._radio_refill_pending)

    def ids(self):
        return [x['videoId'] for x in self.b._queue.tracks]

    def test_threshold_single_request_no_global_busy_and_append_without_audio_reset(self):
        self.radio()
        self.assertFalse(self.b._maybe_refill_radio())
        self.near_end(4)  # Five remaining tracks trigger the CLI threshold.
        queue = self.b._queue; current = queue.current()
        self.b._player_position = 47; self.b.cycleRepeat()
        self.block_request = True
        events = []; resets = []; inserted = []
        self.b.playerTrackChanged.connect(lambda: events.append(True))
        self.b.playingTracksModel.modelReset.connect(lambda: resets.append(True))
        self.b.playingTracksModel.rowsInserted.connect(lambda *a: inserted.append(True))
        before = (len(self.played), len(self.stops), self.b._playback_generation)
        self.assertTrue(self.b._maybe_refill_radio()); self.until(self.refill_entered.is_set)
        self.assertFalse(self.b.busy)
        self.assertFalse(self.b._maybe_refill_radio())
        self.assertEqual(queue.count(), 10)
        self.release.set(); self.done()
        self.assertIs(self.b._queue, queue); self.assertIs(queue.current(), current)
        self.assertEqual(queue.index, 4); self.assertEqual(self.b.playerPosition, 47)
        self.assertEqual(self.b.playerRepeatMode, 'all')
        self.assertEqual(queue.count(), 20)
        self.assertEqual(self.ids()[-10:], [f'N{i}' for i in range(10)])
        self.assertEqual((len(self.played), len(self.stops), self.b._playback_generation), before)
        self.assertFalse(events); self.assertFalse(resets); self.assertEqual(len(inserted), 10)
        self.assertEqual(self.b.playingTracksModel.count, 20)
        self.assertEqual(queue.tracks[-1]['_guiOrigin'], {'source': 'playing', 'index': 19, 'context': {'page': 5}})
        self.api.get_watch_playlist.assert_called_with(videoId='T9', limit=support.core.MIX_LIMIT, radio=True)

    def test_filters_existing_seed_unavailable_missing_and_internal_duplicates(self):
        self.radio(); self.near_end()
        self.block = [self.song('T9'), self.song('S'), self.song('T3'), self.song('new'),
                      self.song('new'), dict(self.song('bad'), isAvailable=False),
                      {'title': 'No ID'}, self.song('other')]
        self.b._maybe_refill_radio(); self.done()
        self.assertEqual(self.ids(), [x['videoId'] for x in self.initial] + ['new', 'other'])
        self.assertFalse(self.errors)

    def test_multiple_blocks_seed_from_last_track_and_include_manual_duplicates_in_filter(self):
        self.radio(); self.near_end()
        self.b._search_results_model.set_items([dict(self.song('manual'), kind='song')])
        self.b.enqueueFrom('search', 0, False, {})
        self.block = [self.song('manual'), self.song('N1'), self.song('N2')]
        self.b._maybe_refill_radio(); self.done()
        self.api.get_watch_playlist.assert_called_with(videoId='manual', limit=support.core.MIX_LIMIT, radio=True)
        self.assertEqual(self.ids().count('manual'), 1)
        self.near_end(); self.block = [self.song('N1'), self.song('N2'), self.song('next')]
        self.b._maybe_refill_radio(); self.done()
        self.api.get_watch_playlist.assert_called_with(videoId='N2', limit=support.core.MIX_LIMIT, radio=True)
        self.assertEqual(self.ids()[-3:], ['N1', 'N2', 'next'])

    def test_next_same_queue_during_request_does_not_discard_useful_block(self):
        self.radio(); self.near_end(5); self.block_request = True
        self.b._maybe_refill_radio(); self.until(self.refill_entered.is_set)
        self.b.nextTrack(); self.until(lambda: self.b.playerState == 'playing')
        current = self.b._queue.current(); self.b._player_position = 25
        self.release.set(); self.done()
        self.assertIs(self.b._queue.current(), current)
        self.assertEqual(self.b.playerQueueIndex, 6); self.assertEqual(self.b.playerPosition, 25)
        self.assertEqual(self.b.playerQueueCount, 20)

    def test_paused_and_repeat_one_preserved(self):
        self.radio(); self.near_end()
        self.status.player_state = 'PAUSED'; self.b._player_state = 'paused'
        self.b._player_position = 37; self.b.cycleRepeat(); self.b.cycleRepeat()
        plays = len(self.played)
        self.b._maybe_refill_radio(); self.done()
        self.assertEqual(self.b.playerState, 'paused'); self.assertEqual(self.b.playerPosition, 37)
        self.assertEqual(self.b.playerRepeatMode, 'one'); self.assertEqual(len(self.played), plays)

    def test_at_last_track_prefetches_new_successor_and_eos_plays_it(self):
        self.radio(); self.near_end(9)
        self.assertEqual(self.b._next_prefetch_id(), '')
        self.b._maybe_refill_radio(); self.done()
        self.until(lambda: 'N0' in support.core.LOCAL_AUDIO_CACHE)
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, 'N0'); self.assertEqual(self.downloads['N0'], 1)

    def test_last_eos_while_request_pending_resumes_only_when_block_arrives(self):
        self.radio(); self.near_end(9); self.block_request = True
        self.eos(); self.until(self.refill_entered.is_set)
        self.assertEqual(self.b.playerState, 'idle')
        self.assertIs(self.b._radio_waiting_for_tracks, self.b._queue)
        self.assertTrue(self.b.playerWaitingForRadio)
        plays = len(self.played)
        self.release.set(); self.done(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, 'N0'); self.assertEqual(len(self.played), plays + 1)

    def test_stop_after_natural_end_cancels_auto_resume_and_late_result(self):
        self.radio(); self.near_end(9); self.block_request = True
        self.eos(); self.until(self.refill_entered.is_set)
        self.b.stopPlayback(); self.release.set(); self.done()
        self.assertEqual(self.b.playerState, 'idle'); self.assertEqual(self.b.playerQueueCount, 10)
        self.assertIsNone(self.b._radio_waiting_for_tracks)
        self.assertFalse(self.b.playerWaitingForRadio)
        self.assertFalse(self.b._maybe_refill_radio())

    def test_network_error_empty_or_duplicate_only_delays_retry_without_modal(self):
        self.radio(); self.near_end()
        for response in ('network', 'empty', 'duplicates'):
            with self.subTest(response=response):
                self.b._queue.radio_refill_retry_after = 0
                self.fail = response == 'network'
                self.block = [self.song('S'), self.song('T9')] if response == 'duplicates' else []
                self.b._maybe_refill_radio(); self.done()
                self.assertGreater(self.b._queue.radio_refill_retry_after, monotonic() + 25)
                calls = self.api.get_watch_playlist.call_count
                self.assertFalse(self.b._maybe_refill_radio())
                self.assertEqual(self.api.get_watch_playlist.call_count, calls)
                self.assertEqual(self.b.playerQueueCount, 10)
                self.assertEqual(self.b.playerState, 'playing'); self.assertFalse(self.errors)
        self.fail = False; self.block = [self.song('finally')]
        self.b._queue.radio_refill_retry_after = 0
        self.b._maybe_refill_radio(); self.done()
        self.assertEqual(self.ids()[-1], 'finally')
        self.assertEqual(self.b._queue.radio_refill_retry_after, 0)

    def test_error_at_end_can_retry_and_resume_without_replaying_last(self):
        self.radio(); self.near_end(9); self.fail = True
        self.eos(); self.done()
        self.assertEqual(self.b.playerState, 'idle')
        self.assertIs(self.b._radio_waiting_for_tracks, self.b._queue)
        self.fail = False; self.b._queue.radio_refill_retry_after = 0
        self.b._poll_player(); self.done(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, 'N0'); self.assertEqual(self.played.count('T9'), 1)

    def test_stop_new_queue_and_manual_edit_ignore_old_result_and_error(self):
        for change in ('stop', 'new', 'enqueue'):
            with self.subTest(change=change):
                self.release.clear(); self.refill_entered.clear(); self.block_request = True
                self.radio(); self.near_end()
                self.b._maybe_refill_radio(); self.until(self.refill_entered.is_set)
                if change == 'stop':
                    self.b.stopPlayback()
                elif change == 'new':
                    self.b._library_items_model.set_items([dict(self.song('other'), kind='song')])
                    self.b.playFrom('library', 0); self.until(lambda: self.b.playerState == 'playing')
                else:
                    self.b.enqueueFrom('playing', 0, False, {})
                expected = list(self.b._queue.tracks)
                self.release.set(); self.done()
                self.assertEqual(self.b._queue.tracks, expected); self.assertFalse(self.errors)

    def test_api_serialization_and_refill_completion_does_not_clear_user_busy(self):
        self.radio(); self.near_end(); self.block_request = True
        library_entered, library_release = Event(), Event()
        def library(**kwargs):
            library_entered.set(); library_release.wait(3); return []
        self.api.get_library_playlists.side_effect = library
        self.b._maybe_refill_radio(); self.until(self.refill_entered.is_set)
        try:
            self.b.loadLibrarySection('playlists', '')
            self.assertTrue(self.b.busy); self.assertFalse(library_entered.is_set())
            self.release.set(); self.until(library_entered.is_set); self.done()
            self.assertTrue(self.b.busy); self.assertEqual(self.b.playerQueueCount, 20)
        finally:
            library_release.set()
        self.until(lambda: not self.b.busy)

    def test_user_new_radio_request_wins_over_pending_old_refill(self):
        self.radio(); self.near_end(); old = self.b._queue
        self.block_request = True
        self.b._maybe_refill_radio(); self.until(self.refill_entered.is_set)
        self.assertTrue(self.b.startRadioFrom('search', 0))
        self.release.set(); self.done(); self.until(lambda: not self.b.busy)
        self.until(lambda: self.b.playerState == 'playing')
        self.assertIsNot(self.b._queue, old)
        self.assertEqual(old.count(), 10)
        self.assertEqual(self.b.playerQueueCount, 10)
        self.assertEqual(self.b.playerVideoId, 'S')
        self.assertTrue(self.b._queue.radio_active)

    def test_user_new_collection_shuffle_wins_over_pending_old_refill(self):
        self.radio(); self.near_end(); old = self.b._queue
        self.b._detail_meta = {'kind': 'playlist', 'playlistId': 'PLother'}
        self.b._detail_title = 'Other playlist'
        self.b._detail_tracks_model.set_items([dict(self.song('other'), kind='song')])
        self.block_request = True
        self.b._maybe_refill_radio(); self.until(self.refill_entered.is_set)
        self.assertTrue(self.b.shuffleDetail())
        self.release.set(); self.done(); self.until(lambda: not self.b.busy)
        self.until(lambda: self.b.playerState == 'playing')
        self.assertIsNot(self.b._queue, old); self.assertEqual(old.count(), 10)
        self.assertEqual(self.b._queue.source_playlist_id, 'PLother')
        self.assertTrue(self.b._queue.shuffle_active)
        self.assertFalse(self.b._queue.radio_active)

    def test_normal_and_stopped_radio_queues_do_not_fetch(self):
        self.start('A', 'B'); self.assertFalse(self.b._maybe_refill_radio())
        self.radio(); self.near_end(); self.b.stopPlayback()
        calls = self.api.get_watch_playlist.call_count
        self.assertFalse(self.b._maybe_refill_radio())
        self.assertEqual(self.api.get_watch_playlist.call_count, calls)

    def test_cli_test_block_limit_is_respected(self):
        self.radio(); self.near_end()
        with patch.object(support.core, 'MIX_TEST_MAX_TRACKS', 3):
            self.b._maybe_refill_radio(); self.done()
        self.assertEqual(self.ids()[-3:], ['N0', 'N1', 'N2'])
        self.assertEqual(self.b.playerQueueCount, 13)
