"""Liked collection playback and navigation with mocked API/audio."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock, patch
import test_prefetch as support


class LikedPlaybackTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock(); self.b._ytmusic = self.api
        self.items = [dict(videoId=v, title=v, duration='3:00', likeStatus='LIKE') for v in ('A', 'B', 'C')]
        self.b._liked_model.set_items([self.b._track(x) for x in self.items])
        self.api.get_watch_playlist.return_value = {'tracks': deepcopy(self.items[::-1])}
        self.b.playbackSourceCaptured.connect(lambda: self.b.setPlaybackSourceContext({'page': 2, 'likedOrder': 'a_to_z'}))
        self.starts = []
        self.b.collectionShuffleStarted.connect(lambda: self.starts.append('shuffle'))
        self.b.radioStarted.connect(lambda: self.starts.append('radio'))

    def start(self, mode):
        self.assertTrue(self.b.startLikedPlayback(mode))
        self.until(lambda: not self.b.busy)
        self.until(lambda: self.b.playerState == 'playing')

    def test_local_shuffle_and_cover_restore_liked_list(self):
        self.b._liked_order = 'a_to_z'
        with patch.object(support.backend.random, 'shuffle', side_effect=lambda rows: rows.reverse()):
            self.start('shuffle')
        self.api.get_watch_playlist.assert_not_called()
        self.assertEqual([x['videoId'] for x in self.b._queue.tracks], ['C', 'B', 'A'])
        self.assertEqual(self.b.playerQueueSource, 'liked')
        self.assertEqual(self.b.playerSourceIndex, 2)
        self.assertEqual(self.b.playerSourceContext['page'], 2)
        self.assertEqual(self.b._queue.source_playlist_id, 'LL')
        self.b._liked_model.set_items([])
        self.assertTrue(self.b.restorePlayingSource(2))
        self.assertEqual([x['videoId'] for x in self.b.likedModel.snapshot()], ['A', 'B', 'C'])
        self.assertEqual(self.b._liked_order, 'a_to_z')
        self.b.playFrom('playing', 1)
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerSourceIndex, 1)
        self.assertEqual(self.starts, ['shuffle'])

    def test_large_list_preserves_every_duplicate_and_exact_source_index(self):
        self.items = [dict(videoId=str(i % 1599), title=str(i), likeStatus='LIKE') for i in range(1635)]
        self.b._liked_model.set_items([self.b._track(x) for x in self.items])
        original = self.b.likedModel.snapshot()
        with patch.object(support.backend.random, 'shuffle', side_effect=lambda rows: rows.reverse()):
            self.start('shuffle')
        self.assertEqual(self.b.playerQueueCount, 1635)
        self.assertEqual(self.b._queue_source_indices, list(reversed(range(1635))))
        self.assertEqual([x['_guiOrigin']['index'] for x in self.b._queue.tracks], list(reversed(range(1635))))
        self.assertEqual([x['title'] for x in self.b._queue.tracks], [str(i) for i in reversed(range(1635))])
        self.assertEqual(self.b.likedModel.snapshot(), original)
        self.assertFalse(self.b.playerQueueLoading); self.assertFalse(self.b.playerQueueIncomplete)
        self.assertFalse(self.b._queue.radio_active)
        self.api.get_watch_playlist.assert_not_called()
        self.api.get_liked_songs.assert_not_called()
        self.api.get_playlist.assert_not_called()

    def test_queue_stores_one_isolated_source_snapshot_for_all_occurrences(self):
        self.start('shuffle')
        origins = [song['_guiOrigin'] for song in self.b._queue.tracks]
        snapshot = origins[0]['snapshots']['liked']
        self.assertTrue(all(origin['snapshots']['liked'] is snapshot for origin in origins))
        self.assertEqual(sorted(origin['index'] for origin in origins), [0, 1, 2])
        self.assertEqual(len({id(origin) for origin in origins}), 3)
        self.b._liked_model.set_items([self.b._track(dict(videoId='new', title='New'))])
        self.assertEqual([row['videoId'] for row in snapshot], ['A', 'B', 'C'])
        self.assertTrue(self.b.restorePlayingSource(2))
        self.assertEqual([row['videoId'] for row in self.b.likedModel.snapshot()], ['A', 'B', 'C'])

    def test_generated_origin_copy_isolated_from_input_and_preserves_per_song_indices(self):
        items = self.b.likedModel.snapshot()
        origin = self.b._make_origin('liked', -1, items)
        tracks = [self.b._playback_track(item) for item in items]
        for index, track in enumerate(tracks):
            track['_guiOrigin'] = dict(origin, index=index)
        self.b._start_generated_queue(tracks, 'Test', shuffle=True, origin=origin)
        self.until(lambda: self.b.playerState == 'playing')
        stored = self.b._queue.tracks[0]['_guiOrigin']['snapshots']['liked']
        self.assertIsNot(stored, items)
        items[0]['title'] = 'Changed input'
        self.assertEqual(stored[0]['title'], 'A')
        self.b._queue.tracks[0]['_guiOrigin']['index'] = 99
        self.assertEqual(self.b._queue.tracks[1]['_guiOrigin']['index'], 1)

    def test_each_start_randomizes_again_and_resets_repeat(self):
        with patch.object(support.backend.random, 'shuffle', side_effect=lambda rows: rows.reverse()) as mix:
            self.start('shuffle'); first = self.b._queue
            self.b.cycleRepeat(); self.start('shuffle')
        self.assertEqual(mix.call_count, 2)
        self.assertIsNot(first, self.b._queue)
        self.assertEqual(self.b.playerRepeatMode, 'off')
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, 'B')
        self.b.previousTrack(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, 'C')
        self.b.playFrom('playing', 2); self.until(lambda: self.b.playerState == 'playing')
        self.eos(); self.assertEqual(self.b.playerState, 'idle')
        self.api.get_watch_playlist.assert_not_called()

    def test_loading_or_incomplete_list_cannot_be_shuffled(self):
        for state in ('loading', 'error'):
            self.b._liked_load_state = state
            self.assertFalse(self.b.startLikedPlayback('shuffle'))
        self.api.get_watch_playlist.assert_not_called()

    def test_late_local_result_after_stop_or_source_change_is_discarded(self):
        for action in ('stop', 'source_change'):
            with self.subTest(action=action):
                self.start('shuffle'); old = self.b._queue
                entered = Event(); self.release.clear(); before = len(self.starts)
                def hold(rows):
                    entered.set(); self.release.wait(3); rows.reverse()
                with patch.object(support.backend.random, 'shuffle', side_effect=hold):
                    self.assertTrue(self.b.startLikedPlayback('shuffle')); self.until(entered.is_set)
                    self.assertFalse(self.b.startLikedPlayback('shuffle'))
                    if action == 'stop': self.b.stopPlayback()
                    else: self.b._liked_model.set_items(self.b.likedModel.snapshot()[:-1])
                    self.release.set(); self.until(lambda: not self.b.busy)
                self.assertIs(self.b._queue, old)
                self.assertEqual(len(self.starts), before)

    def test_local_shuffle_failure_preserves_audio_and_repeat(self):
        self.start('shuffle'); old = self.b._queue; self.b.cycleRepeat()
        with patch.object(support.backend.random, 'shuffle', side_effect=RuntimeError('Test failure')):
            self.assertTrue(self.b.startLikedPlayback('shuffle')); self.until(lambda: not self.b.busy)
        self.assertIs(self.b._queue, old)
        self.assertEqual(self.b.playerRepeatMode, 'all')
        self.assertEqual(self.b.playerState, 'playing')
        self.assertEqual(len(self.errors), 1)

    def test_mix_uses_whole_collection_and_refills(self):
        self.start('radio')
        self.api.get_watch_playlist.assert_called_once_with(playlistId='RDAMPLLL', limit=support.core.MIX_LIMIT, radio=True)
        self.assertTrue(self.b._queue.radio_active)
        self.assertEqual(self.b.playerQueueSource, 'liked')
        self.api.get_watch_playlist.return_value = {'tracks': [dict(videoId='new', title='New')]}
        self.b._maybe_refill_radio()
        self.until(lambda: not self.b._radio_refill_pending)
        self.assertEqual(self.b._queue.tracks[-1]['videoId'], 'new')
        self.b.playFrom('playing', 3); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerSourceIndex, -1)
        self.assertEqual(self.b.playerSourceContext['page'], 2)
        self.b._liked_model.set_items([])
        self.assertTrue(self.b.restorePlayingSource(2))
        self.assertEqual(self.b.likedModel.count, 3)
        self.assertEqual(self.starts, ['radio'])

    def test_failed_request_preserves_queue_repeat_and_emits_no_navigation(self):
        self.start('shuffle'); old = self.b._queue
        self.b.cycleRepeat(); repeat = self.b.playerRepeatMode
        self.api.get_watch_playlist.side_effect = RuntimeError('Offline')
        self.assertTrue(self.b.startLikedPlayback('radio'))
        self.until(lambda: not self.b.busy)
        self.assertIs(self.b._queue, old)
        self.assertEqual(self.b.playerRepeatMode, repeat)
        self.assertEqual(self.starts, ['shuffle'])

    def test_empty_list_and_invalid_mode_do_not_submit(self):
        self.assertFalse(self.b.startLikedPlayback('invalid'))
        self.b._liked_model.set_items([])
        for mode in ('radio', 'shuffle'):
            self.assertFalse(self.b.startLikedPlayback(mode))
        self.api.get_watch_playlist.assert_not_called()

    def test_stop_supersedes_pending_request(self):
        self.start('shuffle'); old = self.b._queue
        entered = Event()
        def watch(**kwargs):
            entered.set(); self.release.wait(3)
            return {'tracks': deepcopy(self.items)}
        self.api.get_watch_playlist.side_effect = watch
        self.assertTrue(self.b.startLikedPlayback('radio'))
        self.until(entered.is_set)
        self.b.stopPlayback(); self.release.set()
        self.until(lambda: not self.b.busy)
        self.assertIs(self.b._queue, old)
        self.assertEqual(self.starts, ['shuffle'])
