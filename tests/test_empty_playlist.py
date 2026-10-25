"""Creating an empty private playlist must never use playback/selection tracks."""
from threading import Event
from unittest.mock import Mock
import test_prefetch as support


class EmptyPlaylistTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock()
        self.api.create_playlist.return_value = 'new-id'
        self.b._ytmusic = self.api
        self.changed = []
        self.b.playlistsChanged.connect(self.changed.append)

    def ready(self):
        self.until(lambda: not self.b.busy)

    def test_create_empty_without_a_queue_and_allow_same_name(self):
        self.assertTrue(self.b.beginEmptyPlaylist())
        self.assertTrue(self.b.createEmptyPlaylist('  Same name  ')); self.ready()
        self.api.create_playlist.assert_called_once_with('Same name', '', privacy_status='PRIVATE')
        self.assertTrue(self.b.emptyPlaylistState['completed'])
        self.assertFalse(self.b.playerHasTrack)
        self.assertEqual(self.changed, ['new-id'])
        self.api.add_playlist_items.assert_not_called()
        self.api.get_playlist.assert_not_called()
        self.assertTrue(self.b.beginEmptyPlaylist())
        self.api.create_playlist.return_value = 'another-id'
        self.b.createEmptyPlaylist('Same name'); self.ready()
        self.assertEqual(self.changed, ['new-id', 'another-id'])

    def test_validation_before_write_and_missing_auth(self):
        self.assertFalse(self.b.createEmptyPlaylist('No dialog'))
        self.b.beginEmptyPlaylist()
        for name in ('', ' ', '<bad>', 'bad>'):
            self.assertFalse(self.b.createEmptyPlaylist(name))
        self.api.create_playlist.assert_not_called()
        self.assertFalse(self.b.emptyPlaylistState['locked'])
        self.b._ytmusic = None
        self.assertFalse(self.b.beginEmptyPlaylist())
        self.assertFalse(self.b.createEmptyPlaylist('No auth'))

    def test_creation_does_not_use_selected_song_or_change_playback(self):
        self.start('A', 'B'); queue = self.b._queue; stops = len(self.stops)
        self.b._player_position = 53
        self.b._playlist_save_item = {'videoId': 'A'}
        self.b._playlist_save_items = [{'videoId': 'A'}, {'videoId': 'B'}]
        self.b.beginEmptyPlaylist(); self.b.createEmptyPlaylist('Empty'); self.ready()
        self.api.create_playlist.assert_called_once_with('Empty', '', privacy_status='PRIVATE')
        self.assertIs(self.b._queue, queue)
        self.assertEqual(self.b.playerPosition, 53)
        self.assertEqual(self.played, ['A'])
        self.assertEqual(len(self.stops), stops)
        self.assertEqual(self.b.playerLikeStatus, 'LIKE')
        self.api.add_playlist_items.assert_not_called()

    def test_unknown_result_blocks_retry_and_does_not_expose_server_dump(self):
        self.b.beginEmptyPlaylist()
        self.api.create_playlist.side_effect = RuntimeError('responseContext private server dump')
        self.b.createEmptyPlaylist('Empty'); self.ready()
        self.assertTrue(self.b.emptyPlaylistState['locked'])
        self.assertTrue(self.b.emptyPlaylistState['error'])
        self.assertFalse(self.b.emptyPlaylistState['completed'])
        self.assertNotIn('responseContext', self.b.emptyPlaylistState['message'])
        self.assertFalse(self.b.createEmptyPlaylist('Empty'))
        self.api.create_playlist.assert_called_once()
        self.assertFalse(self.changed)
        self.b.beginEmptyPlaylist()
        self.api.create_playlist.side_effect = None
        self.api.create_playlist.return_value = {'status': 'STATUS_FAILED'}
        self.b.createEmptyPlaylist('Empty'); self.ready()
        self.assertFalse(self.b.emptyPlaylistState['completed'])
        self.assertFalse(self.changed)

    def test_double_submit_and_reopening_during_write_are_blocked(self):
        entered = Event()
        def slow(*args, **kwargs):
            entered.set(); self.release.wait(3); return 'new-id'
        self.api.create_playlist.side_effect = slow
        self.b.beginEmptyPlaylist(); self.b.createEmptyPlaylist('Empty'); self.until(entered.is_set)
        self.assertFalse(self.b.createEmptyPlaylist('Empty'))
        self.assertFalse(self.b.beginEmptyPlaylist())
        self.release.set(); self.ready()
        self.assertFalse(self.b.createEmptyPlaylist('Empty'))
        self.api.create_playlist.assert_called_once()

    def test_open_empty_playlist_keeps_detail_and_existing_playback(self):
        self.start('A', 'B'); queue = self.b._queue
        self.api.get_playlist.return_value = {'title': 'Empty', 'owned': True, 'tracks': []}
        self.b.loadPlaylistTracks('new-id', 'Empty'); self.ready()
        self.assertEqual(self.b.detailTitle, 'Empty')
        self.assertEqual(self.b.detailTracksModel.count, 0)
        self.assertEqual(self.b.detailMeta['playlistId'], 'new-id')
        self.assertIs(self.b._queue, queue)
        self.assertEqual(self.played, ['A'])

    def test_delayed_library_response_keeps_confirmed_card_until_server_catches_up(self):
        self.api.get_library_playlists.return_value = [
            {'playlistId': 'old', 'title': 'Same name', 'count': 2}]
        self.b.playlistsChanged.connect(lambda _: self.b.loadLibrarySection('playlists', ''))
        self.b.beginEmptyPlaylist(); self.b.createEmptyPlaylist('Same name'); self.ready()
        cards = self.b.libraryItemsModel.snapshot()
        self.assertEqual([x['playlistId'] for x in cards], ['new-id', 'old'])
        self.assertEqual(cards[0]['subtitle'], '0 skladeb')
        self.b.loadLibrarySection('playlists', ''); self.ready()
        self.assertEqual(self.b.libraryItemsModel.count, 2)
        self.api.get_library_playlists.return_value.append(
            {'playlistId': 'new-id', 'title': 'Server title', 'count': 1})
        self.b.loadLibrarySection('playlists', ''); self.ready()
        cards = self.b.libraryItemsModel.snapshot()
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[1]['title'], 'Server title')
        self.assertFalse(self.b._pending_created_playlists)
        # Once observed in YTM, a later external deletion must not resurrect it.
        self.api.get_library_playlists.return_value.pop()
        self.b.loadLibrarySection('playlists', ''); self.ready()
        self.assertEqual(self.b.libraryItemsModel.count, 1)

    def test_multiple_pending_creations_preserve_ids_and_library_sorting(self):
        self.api.get_library_playlists.return_value = [{'playlistId': 'old', 'title': 'Middle'}]
        for playlist_id, title in [('z', 'Zulu'), ('a', 'Alpha')]:
            self.api.create_playlist.return_value = playlist_id
            self.b.beginEmptyPlaylist(); self.b.createEmptyPlaylist(title); self.ready()
        for order, expected in [('', ['a', 'z', 'old']), ('a_to_z', ['a', 'old', 'z']),
                                ('z_to_a', ['z', 'old', 'a'])]:
            self.b.loadLibrarySection('playlists', order); self.ready()
            self.assertEqual([x['playlistId'] for x in self.b.libraryItemsModel.snapshot()], expected)
        self.api.get_library_albums.return_value = []
        self.b.loadLibrarySection('albums', ''); self.ready()
        self.assertEqual(self.b.libraryItemsModel.count, 0)
