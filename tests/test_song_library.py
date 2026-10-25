"""Song library membership is independent of ratings and the playback queue."""
from threading import Event
from unittest.mock import Mock
import test_prefetch as support


class SongLibraryTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock()
        self.b._ytmusic = self.api
        self.b._library_probe_api = self.api
        self.member = False
        self.selected = 'A'
        self.api.get_watch_playlist.side_effect = self.watch
        self.api.edit_song_library_status.side_effect = self.edit
        self.changed = []
        self.b.songLibraryChanged.connect(lambda: self.changed.append(True))

    def watch(self, **kwargs):
        return {'tracks': [dict(title=kwargs['videoId'], videoId=kwargs['videoId'],
            inLibrary=self.member, feedbackTokens={'add': 'add-token', 'remove': 'remove-token'})]}

    def edit(self, feedbackTokens):
        self.member = feedbackTokens == ['add-token']
        return {'feedbackResponses': [{'isProcessed': True}]}

    def probe(self, source='library', index=0):
        self.request = self.b.prepareSongLibrary(source, index)
        self.assertGreater(self.request, 0)
        self.until(lambda: not self.b.songLibraryMenuState.get("pending"))

    def change(self):
        self.b.changeSongLibrary(self.request)
        self.until(lambda: not self.b.busy)

    def test_add_remove_verified_without_rating_or_audio_changes(self):
        self.start('A', 'B'); queue = self.b._queue; stops = len(self.stops)
        self.b._player_position = 42
        self.probe()
        self.assertFalse(self.b.songLibraryMenuState['inLibrary'])
        self.change()
        self.assertTrue(self.b.songLibraryMenuState['inLibrary'])
        self.api.edit_song_library_status.assert_called_with(feedbackTokens=['add-token'])
        self.change()
        self.api.edit_song_library_status.assert_called_with(feedbackTokens=['remove-token'])
        self.assertFalse(self.b.songLibraryMenuState['inLibrary'])
        self.api.rate_song.assert_not_called()
        self.assertEqual(self.b.playerLikeStatus, 'LIKE')
        self.assertEqual(self.b.playerPosition, 42)
        self.assertIs(self.b._queue, queue)
        self.assertEqual(self.played, ['A'])
        self.assertEqual(len(self.stops), stops)
        self.assertEqual(len(self.changed), 2)

    def test_missing_controls_does_not_infer_membership_from_like(self):
        self.start('A')
        self.api.get_watch_playlist.side_effect = None
        self.api.get_watch_playlist.return_value = {'tracks': [dict(videoId='A', likeStatus='LIKE')]}
        self.probe()
        self.assertFalse(self.b.songLibraryMenuState['available'])
        self.assertFalse(self.b.songLibraryMenuState['pending'])
        self.b.changeSongLibrary(self.request)
        self.api.edit_song_library_status.assert_not_called()

    def test_album_fallback_matches_exact_video_and_preserves_album_id_in_queue(self):
        raw = dict(title='Song', videoId='A', album={'name': 'Album', 'id': 'album-id'})
        normalized = self.b._track(raw)
        self.b.libraryItemsModel.set_items([normalized])
        self.b.playFrom('library', 0); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playingTracksModel.snapshot()[0]['albumId'], 'album-id')
        self.api.get_watch_playlist.side_effect = None
        self.api.get_watch_playlist.return_value = {'tracks': [{'videoId': 'wrong', 'inLibrary': True, 'feedbackTokens': {'remove': 'wrong'}}]}
        self.api.get_album.return_value = {'tracks': [
            {'videoId': 'other', 'inLibrary': True, 'feedbackTokens': {'remove': 'wrong'}},
            {'videoId': 'A', 'inLibrary': False, 'feedbackTokens': {'add': 'correct'}}]}
        self.probe('playing')
        self.assertTrue(self.b.songLibraryMenuState['available'])
        self.assertEqual(self.b._song_library_token, 'correct')
        self.api.get_album.assert_called_with('album-id')

    def test_album_does_not_substitute_different_edition(self):
        self.b.searchResultsModel.set_items([dict(kind='song', title='A', videoId='A', albumId='album-id')])
        self.api.get_watch_playlist.side_effect = None
        self.api.get_watch_playlist.return_value = {'tracks': []}
        self.api.get_album.return_value = {'tracks': [{'videoId': 'other', 'inLibrary': False, 'feedbackTokens': {'add': 'wrong'}}]}
        self.probe('search')
        self.assertFalse(self.b.songLibraryMenuState['available'])
        self.api.edit_song_library_status.assert_not_called()

    def test_write_failure_does_not_change_local_state(self):
        self.start('A'); self.probe()
        self.api.edit_song_library_status.side_effect = RuntimeError('Offline')
        self.change()
        self.assertFalse(self.b.songLibraryMenuState['available'])
        self.assertFalse(self.b.songLibraryMenuState['inLibrary'])
        self.assertFalse(self.changed)
        self.assertEqual(self.played, ['A'])

    def test_readback_mismatch_reports_unverified_change(self):
        self.start('A'); self.probe()
        self.api.edit_song_library_status.side_effect = None
        self.api.edit_song_library_status.return_value = {}
        self.change()
        self.assertFalse(self.b.songLibraryMenuState['available'])
        self.assertIn('ověřit', self.b.songLibraryMenuState['message'])
        self.assertFalse(self.changed)

    def test_dialog_is_bound_to_selected_song_after_playback_moves(self):
        self.start('A', 'B'); self.probe()
        self.b.nextTrack(); self.until(lambda: self.b.playerState == 'playing')
        self.change()
        self.api.get_watch_playlist.assert_called_with(videoId='A', limit=1)
        self.assertEqual(self.b.playerTitle, 'B')
        self.assertEqual(self.played, ['A', 'B'])

    def test_removal_refreshes_library_snapshots_without_removing_queue_item(self):
        self.start('A', 'B')
        self.b._library_section = 'songs'; self.b._library_order = 'a_to_z'
        self.b.setPlaybackSourceContext({'page': 1, 'librarySection': 'songs', 'libraryOrder': 'a_to_z'})
        self.member = True
        self.probe(); self.change()
        self.assertEqual([x['videoId'] for x in self.b.libraryItemsModel.snapshot()], ['B'])
        self.assertEqual([x['videoId'] for x in self.b._queue.tracks], ['A', 'B'])
        self.b.restorePlayingSource(1)
        self.assertEqual([x['videoId'] for x in self.b.libraryItemsModel.snapshot()], ['B'])
        self.assertEqual(self.b.playerSourceIndex, -1)
        self.b.nextTrack(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerSourceIndex, 0)

    def test_addition_updates_original_library_snapshot_in_its_sort_order(self):
        self.start('A', 'B')
        self.b.setPlaybackSourceContext({'page': 1, 'librarySection': 'songs', 'libraryOrder': 'z_to_a'})
        self.b.searchResultsModel.set_items([dict(kind='song', title='Z', videoId='Z')])
        self.probe('search'); self.change()
        self.b.restorePlayingSource(1)
        self.assertEqual([x['videoId'] for x in self.b.libraryItemsModel.snapshot()], ['Z', 'B', 'A'])
        self.assertEqual(self.b.playerSourceIndex, 2)

    def test_private_episode_invalid_busy_and_disconnected_are_rejected(self):
        self.b.searchResultsModel.set_items([
            dict(kind='upload_song', videoId='private'), dict(kind='episode', videoId='ep'),
            dict(kind='song', videoId='private', browseId='privately_owned_x')])
        for i in (-1, 0, 1, 2, 3):
            self.assertFalse(self.b.prepareSongLibrary('search', i))
        self.b._set_busy(True)
        self.assertFalse(self.b.prepareSongLibrary('search', 0))
        self.b._set_busy(False); self.b._ytmusic = None
        self.assertFalse(self.b.prepareSongLibrary('search', 0))
        self.api.edit_song_library_status.assert_not_called()

    def test_double_submit_sends_only_one_write(self):
        self.start('A'); self.probe()
        entered = Event()
        def blocked_edit(feedbackTokens):
            entered.set(); self.release.wait(3)
            return self.edit(feedbackTokens)
        self.api.edit_song_library_status.side_effect = blocked_edit
        self.b.changeSongLibrary(self.request); self.until(entered.is_set)
        self.b.changeSongLibrary(self.request)
        self.release.set(); self.until(lambda: not self.b.busy)
        self.assertEqual(self.api.edit_song_library_status.call_count, 1)
        self.assertTrue(self.member)

    def test_cover_restore_of_album_cards_does_not_turn_them_into_song_list(self):
        self.start('A', 'B')
        self.b._library_section = 'songs'
        card = self.b._album_item(dict(title='Album', browseId='album-id'))
        for song in self.b._queue.tracks:
            origin = song['_guiOrigin']
            origin['context'] = {'page': 1, 'librarySection': 'albums'}
            origin['snapshots']['library'] = [card]
        self.b.restorePlayingSource(1)
        self.probe('playing'); self.change()
        self.assertEqual(self.b._library_section, 'albums')
        self.assertEqual(self.b.libraryItemsModel.snapshot(), [card])

    def test_pending_probe_does_not_block_enqueue_or_radio_api_worker(self):
        self.start('A', 'B')
        entered = Event()
        probe_api = Mock()
        def blocked_watch(**kwargs):
            entered.set(); self.release.wait(3)
            return self.watch(**kwargs)
        probe_api.get_watch_playlist.side_effect = blocked_watch
        self.b._library_probe_api = probe_api
        request = self.b.prepareSongLibrary('library', 0)
        self.until(entered.is_set)
        self.assertFalse(self.b.busy)
        self.assertTrue(self.b.playerCanEditQueue)
        self.assertTrue(self.b.enqueueFrom('library', 1, False, {}))
        self.api.get_watch_playlist.side_effect = None
        self.api.get_watch_playlist.return_value = {'tracks': [dict(title=v, videoId=v) for v in ('A', 'X')]}
        self.assertTrue(self.b.startRadioFrom('playing', 0))
        self.until(lambda: not self.b.busy)
        self.assertTrue(self.b._queue.radio_active)
        self.assertFalse(self.release.is_set())
        self.b.cancelSongLibraryProbe(request)
        self.release.set()

    def test_closed_or_replaced_menu_ignores_stale_result(self):
        self.start('A', 'B')
        entered = Event()
        def blocked_watch(**kwargs):
            if kwargs['videoId'] == 'A':
                entered.set(); self.release.wait(3)
                return {'tracks': [dict(videoId='A', inLibrary=True, feedbackTokens={'remove': 'old'})]}
            return self.watch(**kwargs)
        self.api.get_watch_playlist.side_effect = blocked_watch
        old = self.b.prepareSongLibrary('library', 0); self.until(entered.is_set)
        self.b.cancelSongLibraryProbe(old)
        new = self.b.prepareSongLibrary('library', 1)
        self.release.set()
        self.until(lambda: not self.b.songLibraryMenuState.get('pending'))
        self.assertEqual(self.b.songLibraryMenuState['requestId'], new)
        self.assertEqual(self.b.songLibraryMenuState['videoId'], 'B')
        self.assertFalse(self.b.songLibraryMenuState['inLibrary'])
        self.b.changeSongLibrary(old)
        self.api.edit_song_library_status.assert_not_called()
        self.b.cancelSongLibraryProbe(new)
        self.assertEqual(self.b.songLibraryMenuState, {})

    def test_probe_constructs_independent_authenticated_client(self):
        from unittest.mock import patch
        self.start('A')
        probe_api = Mock()
        probe_api.get_watch_playlist.side_effect = self.watch
        self.b._library_probe_api = None
        self.b._library_probe_headers = {'test-auth': 'fake'}
        with patch.object(support.backend, 'YTMusic', return_value=probe_api) as factory:
            self.probe()
        factory.assert_called_once_with({'test-auth': 'fake'})
        probe_api.get_watch_playlist.assert_called_once_with(videoId='A', limit=1)
        self.api.get_watch_playlist.assert_not_called()
        self.assertFalse(self.b.busy)

    def test_open_album_inherits_known_id_and_keeps_specific_track_album_id(self):
        self.api.get_album.return_value = {'title': 'Known album', 'tracks': [
            dict(title='A', videoId='A', album='Known album', inLibrary=False,
                 feedbackTokens={'add': 'album-add'}),
            dict(title='B', videoId='B', album={'name': 'Other edition', 'id': 'specific-album'})]}
        self.b.openLibraryItem('album', 'parent-album', '', 'Known album')
        self.until(lambda: not self.b.busy)
        items = self.b.detailTracksModel.snapshot()
        self.assertEqual([x['albumId'] for x in items], ['parent-album', 'specific-album'])
        self.b.enqueueFrom('detail', 0, False, {})
        self.assertEqual(self.b.playingTracksModel.snapshot()[0]['albumId'], 'parent-album')
        # The watch response has no album or library controls: only the ID
        # inherited from the opened album makes the exact-match fallback work.
        self.api.get_watch_playlist.side_effect = None
        self.api.get_watch_playlist.return_value = {'tracks': [{'videoId': 'A'}]}
        self.probe('playing')
        self.assertTrue(self.b.songLibraryMenuState['available'])
        self.assertEqual(self.b._song_library_token, 'album-add')
        self.api.get_album.assert_called_with('parent-album')
