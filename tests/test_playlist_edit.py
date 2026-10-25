"""Playlist metadata edits: exact identity, fresh ownership, no audio changes."""
from threading import Event
from unittest.mock import Mock
import test_prefetch as support


class PlaylistEditTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock()
        self.data = dict(title='Original', description='Old description', privacy='PRIVATE', owned=True, tracks=[])
        self.api.get_playlist.side_effect = lambda *a, **kw: dict(self.data)
        self.api.edit_playlist.return_value = 'STATUS_SUCCEEDED'
        self.api._send_request.return_value = {'status': 'STATUS_SUCCEEDED'}
        self.b._ytmusic = self.api
        self.b._detail_meta = dict(kind='playlist', playlistId='own-id', owned=True)
        self.b._detail_title = 'Original'

    def ready(self):
        self.until(lambda: not self.b.busy)

    def open(self):
        self.assertTrue(self.b.openPlaylistEdit()); self.ready()

    def test_load_actual_values_and_reject_non_owned_or_missing_privacy(self):
        requested = []
        self.b.playlistEditRequested.connect(lambda: requested.append(self.b.busy))
        self.open()
        self.assertEqual(requested, [False])
        self.assertEqual(self.b.playlistEditState['description'], 'Old description')
        self.api.get_playlist.assert_called_with('own-id', limit=1)
        for key, value in [('owned', False), ('privacy', None)]:
            self.data[key] = value
            self.open()
            self.assertEqual(len(requested), 1)
            self.data[key] = True if key == 'owned' else 'PRIVATE'
        for meta in ({}, dict(kind='album'), dict(kind='playlist', playlistId='other', owned=False)):
            self.b._detail_meta = meta
            self.assertFalse(self.b.detailCanEditPlaylist)
            self.assertFalse(self.b.openPlaylistEdit())
        self.api.edit_playlist.assert_not_called()

    def test_save_values_and_update_visible_cards_without_touching_playback(self):
        self.start('A', 'B'); queue = self.b._queue; stops = len(self.stops)
        self.b._player_position = 37
        self.b._library_items_model.set_items([
            self.b._playlist({'playlistId': 'own-id', 'title': 'Original'}),
            self.b._playlist({'playlistId': 'other-id', 'title': 'Original'})])
        self.open()
        self.assertTrue(self.b.savePlaylistEdit(' Renamed ', 'Two\nlines', 'UNLISTED')); self.ready()
        self.api.edit_playlist.assert_called_once_with('own-id', title='Renamed', description='Two\nlines', privacyStatus='UNLISTED')
        self.assertEqual(self.b.detailTitle, 'Renamed')
        self.assertEqual(self.b.detailMeta['privacy'], 'UNLISTED')
        self.assertEqual([x['title'] for x in self.b.libraryItemsModel.snapshot()], ['Renamed', 'Original'])
        self.assertTrue(self.b.playlistEditState['completed'])
        self.assertIs(self.b._queue, queue)
        self.assertEqual(self.b.playerPosition, 37)
        self.assertEqual(self.played, ['A']); self.assertEqual(len(self.stops), stops)
        self.assertFalse(self.b.savePlaylistEdit('Again', 'x', 'PUBLIC'))

    def test_clear_description_sends_explicit_empty_action_in_one_request(self):
        self.open(); self.b.savePlaylistEdit('Name', '', 'PUBLIC'); self.ready()
        endpoint, body = self.api._send_request.call_args.args
        self.assertEqual(endpoint, 'browse/edit_playlist')
        self.assertEqual(body['playlistId'], 'own-id')
        self.assertIn({'action': 'ACTION_SET_PLAYLIST_DESCRIPTION', 'playlistDescription': ''}, body['actions'])
        self.assertEqual(len(body['actions']), 3)
        self.api._send_request.assert_called_once()
        self.api.edit_playlist.assert_not_called()
        self.assertTrue(self.b.playlistEditState['completed'])

    def test_validation_and_fresh_ownership_before_write(self):
        self.assertFalse(self.b.savePlaylistEdit('X', 'x', 'PUBLIC'))
        self.open()
        for title, desc, privacy in [('', '', 'PRIVATE'), ('<bad>', '', 'PRIVATE'), ('X', 'bad>', 'PRIVATE'), ('X', '', 'unknown')]:
            self.assertFalse(self.b.savePlaylistEdit(title, desc, privacy))
        self.data['owned'] = False
        self.b.savePlaylistEdit('X', 'x', 'PUBLIC'); self.ready()
        self.api.edit_playlist.assert_not_called(); self.api._send_request.assert_not_called()
        self.assertTrue(self.b.playlistEditState['error'])
        self.assertFalse(self.b.playlistEditState['locked'])
        self.assertEqual(self.b.detailTitle, 'Original')

    def test_uncertain_write_locks_retry_and_keeps_old_display(self):
        self.open()
        self.api.edit_playlist.side_effect = RuntimeError('private server dump')
        self.b.savePlaylistEdit('X', 'x', 'PUBLIC'); self.ready()
        self.assertTrue(self.b.playlistEditState['locked'])
        self.assertFalse(self.b.playlistEditState['completed'])
        self.assertNotIn('private server dump', self.b.playlistEditState['message'])
        self.assertEqual(self.b.detailTitle, 'Original')
        self.assertFalse(self.b.savePlaylistEdit('X', 'x', 'PUBLIC'))
        self.api.edit_playlist.assert_called_once()

    def test_failed_status_is_not_success(self):
        self.open(); self.api.edit_playlist.return_value = {'status': 'STATUS_FAILED'}
        self.b.savePlaylistEdit('X', 'x', 'PRIVATE'); self.ready()
        self.assertFalse(self.b.playlistEditState['completed'])
        self.assertTrue(self.b.playlistEditState['locked'])

    def test_dialog_binds_to_loaded_id_and_blocks_double_submit(self):
        self.open()
        self.b._detail_meta = dict(kind='playlist', playlistId='other', owned=True)
        self.b._detail_title = 'Other'
        entered = Event()
        def slow(*args, **kwargs):
            entered.set(); self.release.wait(3); return 'STATUS_SUCCEEDED'
        self.api.edit_playlist.side_effect = slow
        self.b.savePlaylistEdit('X', 'x', 'PUBLIC'); self.until(entered.is_set)
        self.assertFalse(self.b.savePlaylistEdit('X', 'x', 'PUBLIC'))
        self.assertFalse(self.b.openPlaylistEdit())
        self.release.set(); self.ready()
        self.assertEqual(self.api.edit_playlist.call_args.args, ('own-id',))
        self.assertEqual(self.b.detailTitle, 'Other')

    def test_detail_loader_preserves_ownership_even_for_empty_playlist(self):
        for owned in (True, False):
            self.data['owned'] = owned
            self.b.loadPlaylistTracks('own-id', 'Original'); self.ready()
            self.assertEqual(self.b.detailCanEditPlaylist, owned)
            self.assertEqual(self.b.detailTracksModel.count, 0)
