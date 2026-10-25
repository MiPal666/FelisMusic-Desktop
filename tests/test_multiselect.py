"""Desktop selection and batch actions without implicit playback."""
from unittest.mock import Mock
import test_prefetch as support


class MultiSelectionTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.items = [dict(kind='song', videoId=v, title=v) for v in ('A', 'B', 'A', 'C')]
        self.b._library_items_model.set_items(self.items)

    def select(self, index, ctrl=False, shift=False, source='library'):
        self.b.selectTrack(source, index, ctrl, shift)

    def test_click_control_toggle_and_no_implicit_audio(self):
        self.select(1); self.assertEqual(self.b.selectedTrackIndices, [1])
        self.select(3, True); self.assertEqual(self.b.selectedTrackIndices, [1, 3])
        self.select(1, True); self.assertEqual(self.b.selectedTrackIndices, [3])
        self.select(0); self.assertEqual(self.b.selectedTrackIndices, [0])
        self.assertFalse(self.played); self.assertFalse(self.b.playerHasTrack)
        self.b.clearTrackSelection(); self.assertEqual(self.b.selectedTrackIndices, [])

    def test_shift_range_control_shift_union_and_duplicates_are_rows(self):
        self.select(3); self.select(1, shift=True)
        self.assertEqual(self.b.selectedTrackIndices, [1, 2, 3])
        self.select(0, ctrl=True); self.select(1, ctrl=True, shift=True)
        self.assertEqual(self.b.selectedTrackIndices, [0, 1, 2, 3])
        self.select(0); self.select(2, ctrl=True)
        self.assertEqual(self.b.selectedTrackIndices, [0, 2])

    def test_non_tracks_are_not_selected_and_source_switch_resets_anchor(self):
        self.b._search_results_model.set_items([
            dict(kind='album', browseId='album'), self.items[0], self.items[1]])
        self.select(0, source='search'); self.assertEqual(self.b.selectedTrackIndices, [])
        self.b.selectAllTracks('search'); self.assertEqual(self.b.selectedTrackIndices, [1, 2])
        self.select(0); self.select(2, shift=True, source='search')
        self.assertEqual(self.b.selectedTrackIndices, [2])
        self.b.clearTrackSelection()
        self.b.playSelectedTrack(); self.assertFalse(self.played)

    def test_selection_invalidates_on_structural_changes_but_not_ratings(self):
        self.select(0); self.select(2, ctrl=True)
        self.b._library_items_model.update_role_by_video_id('A', 'likeStatus', 'LIKE')
        self.assertEqual(self.b.selectedTrackIndices, [0, 2])
        self.b._history_model.set_items(self.items)
        self.assertEqual(self.b.selectedTrackIndices, [0, 2])
        self.b._library_items_model.insert_item(0, self.items[3])
        self.assertEqual(self.b.selectedTrackIndices, [])
        self.select(1); self.b._library_items_model.remove_item(0)
        self.assertEqual(self.b.selectedTrackIndices, [])
        self.select(1); self.b._library_items_model.set_items(list(reversed(self.items)))
        self.assertEqual(self.b.selectedTrackIndices, [])

    def test_enter_plays_focused_selection_with_original_playlist(self):
        self.select(1); self.select(3, ctrl=True)
        self.b.playSelectedTrack(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['C'])
        self.assertEqual(self.b.playerQueueIndex, 3)
        self.assertEqual([x['videoId'] for x in self.b._queue.tracks], ['A', 'B', 'A', 'C'])

    def test_batch_next_and_append_preserve_visible_order_and_current_audio(self):
        self.start('Q', 'R'); self.b._library_items_model.set_items(self.items)
        self.b._player_position = 31; queue = self.b._queue; stops = len(self.stops)
        self.select(3); self.select(1, ctrl=True); self.select(2, ctrl=True)
        self.assertTrue(self.b.enqueueSelection(True, {}))
        self.assertEqual([x['videoId'] for x in queue.tracks], ['Q', 'B', 'A', 'C', 'R'])
        self.select(0); self.select(3, ctrl=True)
        self.assertTrue(self.b.enqueueSelection(False, {}))
        self.assertEqual([x['videoId'] for x in queue.tracks], ['Q', 'B', 'A', 'C', 'R', 'A', 'C'])
        self.assertEqual(self.b.playerPosition, 31)
        self.assertEqual(self.played, ['Q']); self.assertEqual(len(self.stops), stops)

    def test_batch_from_queue_captures_selection_before_inserting(self):
        self.start('A', 'B', 'C')
        self.select(2, source='playing'); self.select(1, ctrl=True, source='playing')
        self.assertTrue(self.b.enqueueSelection(True, {}))
        self.assertEqual([x['videoId'] for x in self.b._queue.tracks], ['A', 'B', 'C', 'B', 'C'])
        self.assertEqual(self.b.selectedTrackIndices, [])
        self.assertEqual(self.played, ['A'])

    def test_batch_into_empty_queue_stays_stopped(self):
        self.select(3); self.select(0, ctrl=True)
        self.assertTrue(self.b.enqueueSelection(True, {}))
        self.assertEqual([x['videoId'] for x in self.b._queue.tracks], ['A', 'C'])
        self.assertEqual(self.b.playerState, 'idle'); self.assertFalse(self.played)

    def test_playlist_selection_captures_items_and_order_independently_of_later_selection(self):
        api = Mock(); self.b._ytmusic = api
        api.get_library_playlists.return_value = []
        self.select(3); self.select(0, ctrl=True); self.select(2, ctrl=True)
        self.assertTrue(self.b.selectionCanSavePlaylist)
        self.assertTrue(self.b.openSelectedPlaylistSave())
        self.until(lambda: not self.b.busy)
        self.b.clearTrackSelection(); self.b._library_items_model.clear()
        self.assertEqual([x['videoId'] for x in self.b._playlist_save_items], ['A', 'A', 'C'])
        self.assertEqual(self.b.playlistSaveState['selectionCount'], 3)
        self.assertTrue(self.b.playlistSaveState['collection'])
        api.add_playlist_items.assert_not_called()
        self.assertFalse(self.played)

    def test_unsupported_playlist_selection_or_empty_selection_does_not_open_or_enqueue(self):
        self.b._ytmusic = Mock()
        self.assertFalse(self.b.enqueueSelection(True, {}))
        self.assertFalse(self.b.openSelectedPlaylistSave())
        self.b._library_items_model.set_items([dict(videoId='ep', kind='episode')])
        self.select(0)
        self.assertFalse(self.b.selectionCanSavePlaylist)
        self.assertFalse(self.b.openSelectedPlaylistSave())
        self.b._ytmusic.get_library_playlists.assert_not_called()

    def playlist_api(self):
        api = Mock(); self.b._ytmusic = api
        self.b._playlist_verify_delays = (0,)
        api.get_library_playlists.return_value = []
        api.create_playlist.return_value = 'new'
        api.get_playlist.return_value = dict(title='New', owned=True, tracks=[
            dict(videoId='A', title='A'), dict(videoId='C', title='C')])
        self.select(0); self.select(3, ctrl=True)
        self.assertTrue(self.b.openSelectedPlaylistSave())
        self.until(lambda: not self.b.busy)
        return api

    def test_successful_batch_enqueue_clears_selection_but_rejected_action_keeps_it(self):
        self.select(0); self.select(3, ctrl=True)
        self.b._playback_transitioning = True
        self.assertFalse(self.b.enqueueSelection(True, {}))
        self.assertEqual(self.b.selectedTrackIndices, [0, 3])
        self.b._playback_transitioning = False
        self.assertTrue(self.b.enqueueSelection(True, {}))
        self.assertEqual(self.b.selectedTrackIndices, [])
        self.assertFalse(self.played)

    def test_verified_playlist_save_clears_original_selection(self):
        self.playlist_api()
        self.assertEqual(self.b.selectedTrackIndices, [0, 3])  # Opening/cancelling writes nothing.
        self.b.createPlaylistWithSong('New')
        self.until(lambda: not self.b.busy)
        self.assertTrue(self.b.playlistSaveState['verified'])
        self.assertEqual(self.b.selectedTrackIndices, [])

    def test_failed_or_unverified_save_keeps_selection_until_successful_recheck(self):
        api = self.playlist_api()
        api.get_playlist.side_effect = RuntimeError('parser failure')
        self.b.createPlaylistWithSong('New'); self.until(lambda: not self.b.busy)
        self.assertFalse(self.b.playlistSaveState['verified'])
        self.assertEqual(self.b.selectedTrackIndices, [0, 3])
        api.get_playlist.side_effect = None
        self.b.recheckPlaylistSave(); self.until(lambda: not self.b.busy)
        self.assertTrue(self.b.playlistSaveState['verified'])
        self.assertEqual(self.b.selectedTrackIndices, [])
        api.create_playlist.assert_called_once()
        api = self.playlist_api()
        api.create_playlist.side_effect = RuntimeError('write failure')
        self.b.createPlaylistWithSong('New'); self.until(lambda: not self.b.busy)
        self.assertEqual(self.b.selectedTrackIndices, [0, 3])

    def test_old_dialog_completion_does_not_clear_a_later_selection(self):
        self.playlist_api()
        self.b.clearTrackSelection()
        self.select(0); self.select(3, ctrl=True)  # Even identical rows form a new selection.
        self.b.createPlaylistWithSong('New'); self.until(lambda: not self.b.busy)
        self.assertTrue(self.b.playlistSaveState['verified'])
        self.assertEqual(self.b.selectedTrackIndices, [0, 3])
