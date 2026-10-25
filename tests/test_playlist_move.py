"""Move exact occurrences, preserve playback/manual queue slots, project delayed reads."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock
import test_prefetch as support


class PlaylistMoveTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock(); self.b._ytmusic = self.api
        self.data = dict(title='Mine', owned=True, tracks=[
            dict(videoId='A', title='Same', setVideoId='first'),
            dict(videoId='hidden', title='Unavailable', setVideoId='hidden', isAvailable=False),
            dict(videoId='A', title='Same', setVideoId='second'),
            dict(videoId='B', title='Other', setVideoId='third')])
        self.api.get_playlist.side_effect = lambda *a, **kw: deepcopy(self.data)
        self.api.edit_playlist.side_effect = self.edit

    def edit(self, playlist_id, moveItem):
        selected, before = moveItem if isinstance(moveItem, tuple) else (moveItem, '')
        self.data['tracks'] = self.b._project_playlist_moves(self.data['tracks'], [(selected, before)])
        return 'STATUS_SUCCEEDED'

    def ready(self):
        self.until(lambda: not self.b.busy)

    def load(self):
        self.b.loadPlaylistTracks('mine', 'Mine'); self.ready()

    def ids(self):
        return [x['setVideoId'] for x in self.b.detailTracksModel.snapshot()]

    def test_move_duplicate_up_by_exact_occurrence_and_preserve_scroll_model(self):
        self.load(); moved = []; resets = []
        self.b.detailTracksModel.rowsMoved.connect(lambda *a: moved.append(True))
        self.b.detailTracksModel.modelReset.connect(lambda: resets.append(True))
        self.b.selectTrack('detail', 1, False, False)
        self.assertTrue(self.b.moveDetailPlaylistItem('A', 'second', -1)); self.ready()
        self.api.edit_playlist.assert_called_once_with('mine', moveItem=('second', 'first'))
        self.assertEqual(self.ids(), ['second', 'first', 'third'])
        self.assertTrue(moved); self.assertFalse(resets)
        self.assertEqual(self.b.selectedTrackIndices, [])

    def test_move_down_and_to_end_with_unavailable_raw_rows(self):
        self.load()
        self.b.moveDetailPlaylistItem('A', 'first', 1); self.ready()
        self.api.edit_playlist.assert_called_with('mine', moveItem=('first', 'third'))
        self.assertEqual(self.ids(), ['second', 'first', 'third'])
        self.b.moveDetailPlaylistItem('A', 'first', 1); self.ready()
        self.api.edit_playlist.assert_called_with('mine', moveItem='first')
        self.assertEqual(self.ids(), ['second', 'third', 'first'])
        self.assertEqual([x['setVideoId'] for x in self.data['tracks']], ['hidden', 'second', 'third', 'first'])

    def test_boundaries_invalid_ids_and_foreign_views_do_not_write(self):
        self.load()
        for video, sid, direction in [('A', 'first', -1), ('B', 'third', 1),
                                      ('A', 'second', 0), ('B', 'second', -1), ('A', '', 1)]:
            self.assertFalse(self.b.moveDetailPlaylistItem(video, sid, direction))
        self.b._detail_meta['owned'] = False
        self.assertFalse(self.b.moveDetailPlaylistItem('A', 'second', -1))
        self.api.edit_playlist.assert_not_called()

    def test_fresh_ownership_neighbor_and_exact_identity_required(self):
        self.load(); original = deepcopy(self.data)
        for change in ('owned', 'video', 'neighbor', 'duplicate'):
            self.data = deepcopy(original)
            if change == 'owned': self.data['owned'] = False
            elif change == 'video': self.data['tracks'][2]['videoId'] = 'Wrong'
            elif change == 'neighbor': self.data['tracks'] = list(reversed(self.data['tracks']))
            else: self.data['tracks'].append(deepcopy(self.data['tracks'][2]))
            self.b.moveDetailPlaylistItem('A', 'second', -1); self.ready()
            self.api.edit_playlist.assert_not_called()
            self.assertEqual(self.ids(), ['first', 'second', 'third'])
            self.assertTrue(self.errors)

    def test_read_write_failures_and_bad_status_leave_display_unchanged(self):
        self.load()
        self.api.get_playlist.side_effect = RuntimeError('private response')
        self.b.moveDetailPlaylistItem('A', 'second', -1); self.ready()
        self.api.edit_playlist.assert_not_called()
        self.api.get_playlist.side_effect = lambda *a, **kw: deepcopy(self.data)
        for response in ('STATUS_FAILED', {'status': 'STATUS_FAILED'}, RuntimeError('private response')):
            self.api.edit_playlist.side_effect = response if isinstance(response, Exception) else None
            self.api.edit_playlist.return_value = response
            self.b.moveDetailPlaylistItem('A', 'second', -1); self.ready()
            self.assertEqual(self.ids(), ['first', 'second', 'third'])
            self.assertNotIn('private response', self.errors[-1])

    def test_busy_and_view_change_do_not_retarget_inflight_move(self):
        self.load(); entered = Event()
        def slow(*args, **kw):
            entered.set(); self.release.wait(3); return self.edit(*args, **kw)
        self.api.edit_playlist.side_effect = slow
        self.b.moveDetailPlaylistItem('A', 'second', -1); self.until(entered.is_set)
        self.assertFalse(self.b.moveDetailPlaylistItem('A', 'first', 1))
        self.b._detail_meta = dict(kind='playlist', playlistId='other', owned=True)
        self.b._detail_title = 'Other'
        self.release.set(); self.ready()
        self.api.edit_playlist.assert_called_once_with('mine', moveItem=('second', 'first'))
        self.assertEqual(self.b.detailTitle, 'Other')
        self.assertEqual(self.ids(), ['first', 'second', 'third'])

    def test_delayed_reads_preserve_multiple_confirmed_moves_then_retire_projection(self):
        self.load()
        self.api.edit_playlist.side_effect = None
        self.api.edit_playlist.return_value = {'status': 'STATUS_SUCCEEDED'}
        self.b.moveDetailPlaylistItem('A', 'second', -1); self.ready()
        self.load(); self.assertEqual(self.ids(), ['second', 'first', 'third'])
        self.b.moveDetailPlaylistItem('B', 'third', -1); self.ready()
        self.load(); self.assertEqual(self.ids(), ['second', 'third', 'first'])
        self.data['tracks'] = self.b._project_playlist_moves(self.data['tracks'], self.b._pending_playlist_moves['mine'])
        self.load(); self.assertFalse(self.b._pending_playlist_moves)
        self.data['tracks'].reverse()
        self.load(); self.assertEqual(self.ids(), ['first', 'third', 'second'])

    def test_waiting_originals_reorder_manual_slots_and_current_audio_stay(self):
        self.data['tracks'].append(dict(videoId='C', title='Last', setVideoId='fourth'))
        self.load(); self.b.playFrom('detail', 0); self.until(lambda: self.b.playerState == 'playing')
        self.b.enqueueFrom('detail', 3, True, {})  # Manual copy must stay in slot 1.
        queue = self.b._queue; manual = queue.tracks[1]; current = queue.current()
        self.b._player_position = 42; stops = len(self.stops)
        self.b.moveDetailPlaylistItem('C', 'fourth', -1); self.ready()
        self.assertEqual([x['setVideoId'] for x in queue.tracks], ['first', 'fourth', 'second', 'fourth', 'third'])
        self.assertIs(queue.tracks[1], manual); self.assertIs(queue.current(), current)
        self.assertEqual(self.b.playerPosition, 42); self.assertEqual(self.played, ['A'])
        self.assertEqual(len(self.stops), stops)
        self.b.clearDetail(); self.b.restorePlayingSource(1)
        self.assertEqual(self.ids(), ['first', 'second', 'fourth', 'third'])
        self.b.moveDetailPlaylistItem('A', 'first', 1); self.ready()
        self.assertIs(queue.current(), current); self.assertEqual(self.b.playerQueueIndex, 2)
        self.assertEqual(self.b.playerSourceIndex, 1)
        self.assertEqual(self.b.playerPosition, 42)

    def test_other_queue_is_not_rebuilt(self):
        self.start('Q', 'R'); queue = self.b._queue
        self.load(); self.b.moveDetailPlaylistItem('A', 'second', -1); self.ready()
        self.assertIs(self.b._queue, queue)
        self.assertEqual([x['videoId'] for x in queue.tracks], ['Q', 'R'])
        self.assertEqual(self.played, ['Q'])

    def test_prefetch_retargets_when_next_original_moves(self):
        self.data['tracks'] = [dict(videoId=v, title=v, setVideoId=s)
                               for v, s in [('A', 'first'), ('B', 'second'), ('C', 'third')]]
        self.blocked.add('B'); self.load(); self.b.playFrom('detail', 0)
        self.until(lambda: self.b.playerState == 'playing')
        self.until(lambda: self.downloads['B'] == 1)
        self.b.moveDetailPlaylistItem('C', 'third', -1); self.ready()
        self.until(lambda: 'B' in self.cancelled)
        self.until(lambda: 'C' in support.core.LOCAL_AUDIO_CACHE)
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['A', 'C'])

    def test_many_moves_do_not_reapply_already_observed_operations(self):
        self.load()
        for step in range(15):
            visible = self.b.detailTracksModel.snapshot()
            index = step % len(visible)
            direction = -1 if index else 1
            row = visible[index]
            self.assertTrue(self.b.moveDetailPlaylistItem(row['videoId'], row['setVideoId'], direction))
            self.ready()
            self.assertEqual(self.ids(), [x['setVideoId'] for x in support.core.usable_tracks(self.data['tracks'])])
        self.load()
        self.assertFalse(self.b._pending_playlist_moves)

    def play_detail(self, index=1):
        self.load(); self.b.playFrom('detail', index)
        self.until(lambda: self.b.playerState == 'playing')

    def test_move_current_across_duplicate_keeps_audio_time_rating_and_next(self):
        self.play_detail()
        queue = self.b._queue; current = queue.current(); stops = len(self.stops)
        self.b._player_position = 73
        rating = self.b.playerLikeStatus
        events = []; self.b.playerTrackChanged.connect(lambda: events.append(True))
        self.b.moveDetailPlaylistItem('A', 'second', -1); self.ready()
        self.assertEqual([x['setVideoId'] for x in queue.tracks], ['second', 'first', 'third'])
        self.assertEqual([x['setVideoId'] for x in self.b.playingTracksModel.snapshot()], ['second', 'first', 'third'])
        self.assertIs(queue.current(), current)
        self.assertEqual(self.b.playerQueueIndex, 0); self.assertEqual(self.b.playerSourceIndex, 0)
        self.assertEqual(self.b.playerPosition, 73); self.assertEqual(self.b.playerLikeStatus, rating)
        self.assertEqual(self.played, ['A']); self.assertEqual(len(self.stops), stops)
        self.assertFalse(events)
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(queue.current()['setVideoId'], 'first')
        self.assertEqual(self.b.playerQueueIndex, 1)
        self.b.nextTrack(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(queue.current()['setVideoId'], 'third')

    def test_move_previous_row_after_current_changes_next_without_restarting(self):
        self.play_detail()
        queue = self.b._queue; current = queue.current()
        self.b.moveDetailPlaylistItem('A', 'first', 1); self.ready()
        self.assertEqual([x['setVideoId'] for x in queue.tracks], ['second', 'first', 'third'])
        self.assertIs(queue.current(), current); self.assertEqual(self.b.playerQueueIndex, 0)
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(queue.current()['setVideoId'], 'first')

    def test_stopped_and_paused_queue_reorder_all_rows_without_playing(self):
        self.play_detail()
        self.b.stopPlayback(); queue = self.b._queue; current = queue.current()
        count = len(self.played)
        self.b.moveDetailPlaylistItem('A', 'second', -1); self.ready()
        self.assertEqual([x['setVideoId'] for x in queue.tracks], ['second', 'first', 'third'])
        self.assertEqual(self.b.playerQueueIndex, 0); self.assertIs(queue.current(), current)
        self.assertEqual(self.b.playerState, 'idle'); self.assertEqual(len(self.played), count)
        self.b._player_state = 'paused'; self.status.player_state = 'PAUSED'; self.b._player_position = 29
        self.b.moveDetailPlaylistItem('A', 'second', 1); self.ready()
        self.assertEqual([x['setVideoId'] for x in queue.tracks], ['first', 'second', 'third'])
        self.assertEqual(self.b.playerQueueIndex, 1); self.assertIs(queue.current(), current)
        self.assertEqual(self.b.playerState, 'paused'); self.assertEqual(self.b.playerPosition, 29)
        self.assertEqual(len(self.played), count)

    def test_move_loading_current_keeps_same_download_and_occurrence(self):
        self.blocked.add('A'); self.load(); self.b.playFrom('detail', 1)
        self.until(lambda: self.downloads['A'] == 1)
        current = self.b._queue.current()
        self.b.moveDetailPlaylistItem('A', 'second', -1); self.ready()
        self.assertEqual(self.b.playerState, 'loading'); self.assertEqual(self.b.playerQueueIndex, 0)
        self.assertIs(self.b._queue.current(), current)
        self.release.set(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['A']); self.assertIs(self.b._queue.current(), current)
        self.assertEqual(self.b.playerQueueIndex, 0)
