"""Confirmed deletion of an exact owned playlist, without changing audio/queue."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock
import test_prefetch as support


class PlaylistDeleteTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock(); self.b._ytmusic = self.api
        self.b._playlist_delete_verify_delays = (0, 0, 0)
        self.data = dict(title='Same title', owned=True, tracks=[
            dict(videoId='A', title='A', setVideoId='a'), dict(videoId='B', title='B', setVideoId='b')])
        self.api.get_playlist.side_effect = lambda *a, **kw: deepcopy(self.data)
        self.api.delete_playlist.return_value = 'STATUS_SUCCEEDED'
        self.cards = [self.b._playlist(dict(playlistId=pid, title='Same title')) for pid in ('mine', 'other')]
        self.b._library_items_model.set_items(self.cards)
        self.deleted = []; self.requested = []
        self.b.playlistDeleted.connect(lambda pid, overview: self.deleted.append((pid, overview, self.b.busy)))
        self.b.playlistDeleteRequested.connect(lambda: self.requested.append(self.b.busy))

    def ready(self):
        self.until(lambda: not self.b.busy)

    def load(self):
        self.b.loadPlaylistTracks('mine', 'Same title'); self.ready()

    def open(self):
        self.assertTrue(self.b.openPlaylistDelete()); self.ready()

    def test_open_is_read_only_cancel_invalidates_confirmation(self):
        self.load(); self.open()
        self.assertEqual(self.requested, [False])
        self.assertEqual(self.b.playlistDeleteState['title'], 'Same title')
        self.api.delete_playlist.assert_not_called()
        self.b.cancelPlaylistDelete()
        self.assertFalse(self.b.confirmPlaylistDelete())
        self.api.delete_playlist.assert_not_called()
        self.assertEqual(self.b.detailTitle, 'Same title')

    def test_confirm_deletes_exact_id_and_same_name_other_card_stays(self):
        self.load(); self.open()
        self.b._pending_created_playlists['mine'] = self.cards[0]
        self.b._pending_playlist_moves['mine'] = []
        self.b._pending_removed_playlist_items['mine'] = {'gone'}
        self.assertTrue(self.b.confirmPlaylistDelete()); self.ready()
        self.api.delete_playlist.assert_called_once_with('mine')
        self.assertEqual(self.deleted, [('mine', True, False)])
        self.assertEqual([x['playlistId'] for x in self.b.libraryItemsModel.snapshot()], ['other'])
        self.assertEqual(self.b.detailTitle, '')
        self.assertTrue(self.b.playlistDeleteState['completed'])
        self.assertNotIn('mine', self.b._pending_created_playlists)
        self.assertNotIn('mine', self.b._pending_playlist_moves)
        self.assertNotIn('mine', self.b._pending_removed_playlist_items)
        self.assertFalse(self.b.confirmPlaylistDelete())

    def test_empty_playlist_can_be_deleted(self):
        self.data['tracks'] = []; self.load()
        self.assertTrue(self.b.detailCanDeletePlaylist)
        self.assertFalse(self.b.detailCanSavePlaylist)
        self.open(); self.b.confirmPlaylistDelete(); self.ready()
        self.api.delete_playlist.assert_called_once_with('mine')

    def test_fresh_ownership_and_name_required_before_deletion(self):
        self.load(); self.open(); self.data['owned'] = False
        self.b.confirmPlaylistDelete(); self.ready()
        self.api.delete_playlist.assert_not_called()
        self.assertTrue(self.b.playlistDeleteState['locked'])
        self.data['owned'] = True; self.open(); self.data['title'] = 'Renamed elsewhere'
        self.b.confirmPlaylistDelete(); self.ready()
        self.api.delete_playlist.assert_not_called()
        self.assertTrue(self.b.playlistDeleteState['locked'])
        self.assertFalse(self.deleted)
        self.open()
        self.assertEqual(self.b.playlistDeleteState['title'], 'Renamed elsewhere')
        self.b.confirmPlaylistDelete(); self.ready()
        self.api.delete_playlist.assert_called_once_with('mine')

    def test_foreign_automatic_and_other_collection_types_never_offer_delete(self):
        for meta in ({}, dict(kind='album', playlistId='mine', owned=True),
                     dict(kind='playlist', playlistId='mine', owned=False)):
            self.b._detail_meta = meta
            self.assertFalse(self.b.detailCanDeletePlaylist)
            self.assertFalse(self.b.openPlaylistDelete())
        for pid in ('LM', 'SE', 'RDmix', 'VLLM', 'VLRDmix'):
            self.b._detail_meta = dict(kind='playlist', playlistId=pid, owned=True)
            self.assertFalse(self.b.detailCanDeletePlaylist)
            self.assertFalse(self.b.openPlaylistDelete())
        self.api.get_playlist.assert_not_called(); self.api.delete_playlist.assert_not_called()

    def test_read_errors_do_not_write_and_unknown_write_blocks_retry(self):
        self.load(); self.api.get_playlist.side_effect = RuntimeError('private server dump')
        self.open(); self.assertFalse(self.requested)
        self.assertNotIn('private server dump', self.errors[-1])
        self.api.get_playlist.side_effect = lambda *a, **kw: deepcopy(self.data)
        self.open(); self.api.get_playlist.side_effect = RuntimeError('private server dump')
        self.b.confirmPlaylistDelete(); self.ready()
        self.assertFalse(self.b.playlistDeleteState['locked'])
        self.api.delete_playlist.assert_not_called()
        self.api.get_playlist.side_effect = lambda *a, **kw: deepcopy(self.data)
        self.api.delete_playlist.side_effect = RuntimeError('private server dump')
        self.b.confirmPlaylistDelete(); self.ready()
        self.assertTrue(self.b.playlistDeleteState['locked'])
        self.assertNotIn('private server dump', self.b.playlistDeleteState['message'])
        self.assertFalse(self.b.confirmPlaylistDelete())
        self.api.delete_playlist.assert_called_once_with('mine')
        self.assertFalse(self.deleted)
        self.assertEqual(self.b.detailTitle, 'Same title')

    def test_failed_status_is_not_a_success(self):
        self.load(); self.open(); self.api.delete_playlist.return_value = {'status': 'STATUS_FAILED'}
        self.b.confirmPlaylistDelete(); self.ready()
        self.assertTrue(self.b.playlistDeleteState['error'])
        self.assertFalse(self.b.playlistDeleteState['completed'])
        self.assertFalse(self.deleted)
        self.assertEqual(self.b.libraryItemsModel.count, 2)

    def test_playing_queue_audio_and_prefetch_continue_cover_uses_queue(self):
        self.load(); self.b.playFrom('detail', 0); self.until(lambda: self.b.playerState == 'playing')
        queue = self.b._queue; current = queue.current(); stops = len(self.stops)
        self.b._player_position = 57
        self.open(); self.b.confirmPlaylistDelete(); self.ready()
        self.assertIs(self.b._queue, queue); self.assertIs(queue.current(), current)
        self.assertEqual(self.b.playingTracksModel.count, 2)
        self.assertEqual(self.b.playerPosition, 57)
        self.assertEqual(self.played, ['A']); self.assertEqual(len(self.stops), stops)
        self.assertEqual(self.b.playerQueueSource, 'playing')
        self.assertEqual(self.b.playerSourceContext, {'page': 5})
        self.assertTrue(all('_guiPlaylistBinding' not in x for x in queue.tracks))
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['A', 'B'])
        self.assertEqual(self.b.playerQueueSource, 'playing')

    def test_late_library_search_and_save_targets_do_not_resurrect_deleted_card(self):
        self.load(); self.open(); self.b.confirmPlaylistDelete(); self.ready()
        self.api.get_library_playlists.return_value = [dict(title='Same title', playlistId=pid, owned=True) for pid in ('mine','other')]
        self.b.loadLibrarySection('playlists', ''); self.ready()
        self.assertEqual([x['playlistId'] for x in self.b.libraryItemsModel.snapshot()], ['other'])
        self.b._apply_result('search', self.cards)
        self.assertEqual([x['playlistId'] for x in self.b.searchResultsModel.snapshot()], ['other'])
        self.api.get_playlist.reset_mock(); self.b.loadPlaylistTracks('mine', 'Same title')
        self.api.get_playlist.assert_not_called()
        self.start('A'); self.b.openPlaylistSave('playing', 0); self.ready()
        self.assertEqual(self.b.playlistSaveState['targets'], [{'playlistId':'other', 'title':'Same title'}])

    def test_confirmation_is_bound_to_id_double_submit_and_view_change_are_safe(self):
        self.load(); self.open(); entered = Event()
        def slow(pid):
            entered.set(); self.release.wait(3); return 'STATUS_SUCCEEDED'
        self.api.delete_playlist.side_effect = slow
        self.b.confirmPlaylistDelete(); self.until(entered.is_set)
        self.assertFalse(self.b.confirmPlaylistDelete())
        self.assertFalse(self.b.openPlaylistDelete())
        self.b.cancelPlaylistDelete()  # Can't cancel/retarget an already sent request.
        self.b._detail_meta = dict(kind='playlist', playlistId='other', owned=True)
        self.b._detail_title = 'Other'
        self.release.set(); self.ready()
        self.api.delete_playlist.assert_called_once_with('mine')
        self.assertEqual(self.b.detailTitle, 'Other')
        self.assertEqual(self.deleted, [('mine', False, False)])

    @staticmethod
    def library_response(items=None):
        return {'contents': {'singleColumnBrowseResultsRenderer': {'tabs': [
            {'tabRenderer': {'content': {'sectionListRenderer': {'contents': [
                {'gridRenderer': {'items': [{}] + (items or [])}}
            ]}}}}
        ]}}}

    def library(self, ids):
        self.api._send_request.return_value = self.library_response()
        self.api.get_library_playlists.side_effect = lambda **kw: [
            dict(playlistId=pid, title='Same title', owned=True) for pid in ids]

    def test_statusless_success_confirmed_by_exact_id_disappearing(self):
        alive = ['mine', 'other']; self.library(alive)
        def delete(pid):
            alive.remove(pid)
            return {'responseContext': {'private': 'not logged'}, 'actions': []}
        self.api.delete_playlist.side_effect = delete
        self.load(); self.open(); self.b.confirmPlaylistDelete(); self.ready()
        self.assertTrue(self.b.playlistDeleteState['completed'])
        self.assertFalse(self.b.playlistDeleteState['error'])
        self.assertEqual([x['playlistId'] for x in self.b.libraryItemsModel.snapshot()], ['other'])
        self.api.delete_playlist.assert_called_once_with('mine')

    def test_statusless_uncertain_result_then_read_only_recheck(self):
        alive = ['mine', 'other']; self.library(alive)
        self.api.delete_playlist.return_value = {'responseContext': {}}
        self.load(); self.open(); self.b.confirmPlaylistDelete(); self.ready()
        self.assertFalse(self.b.playlistDeleteState['completed'])
        self.assertFalse(self.b.playlistDeleteState['error'])
        self.assertTrue(self.b.playlistDeleteState['canRecheck'])
        self.assertTrue(self.b.playlistDeleteState['locked'])
        self.assertFalse(self.b.confirmPlaylistDelete())
        self.assertEqual(self.b.detailTitle, 'Same title')
        alive.remove('mine'); self.b.recheckPlaylistDelete(); self.ready()
        self.assertTrue(self.b.playlistDeleteState['completed'])
        self.assertFalse(self.b.playlistDeleteState['canRecheck'])
        self.api.delete_playlist.assert_called_once_with('mine')

    def test_exception_after_actual_deletion_can_be_confirmed_without_another_write(self):
        alive = ['mine', 'other']; self.library(alive)
        def delete(pid):
            alive.remove(pid); raise RuntimeError('transport response lost')
        self.api.delete_playlist.side_effect = delete
        self.load(); self.open(); self.b.confirmPlaylistDelete(); self.ready()
        self.assertTrue(self.b.playlistDeleteState['completed'])
        self.api.delete_playlist.assert_called_once_with('mine')

    def test_invalid_library_layout_does_not_confirm_empty_public_result(self):
        alive = ['mine']; self.library(alive)
        def delete(pid):
            alive.remove(pid)
            self.api._send_request.return_value = {'responseContext': {}}
            return {}
        self.api.delete_playlist.side_effect = delete
        self.load(); self.open(); self.b.confirmPlaylistDelete(); self.ready()
        self.assertFalse(self.b.playlistDeleteState['completed'])
        self.assertTrue(self.b.playlistDeleteState['canRecheck'])
        self.assertEqual(self.b.detailTitle, 'Same title')
        self.api._send_request.return_value = self.library_response()
        self.b.recheckPlaylistDelete(); self.ready()
        self.assertTrue(self.b.playlistDeleteState['completed'])
        self.api.delete_playlist.assert_called_once()

    def test_network_failure_during_verification_never_proves_deletion(self):
        alive = ['mine']; self.library(alive)
        def delete(pid):
            self.api._send_request.side_effect = RuntimeError('network down')
            return {'responseContext': {}}
        self.api.delete_playlist.side_effect = delete
        self.load(); self.open(); self.b.confirmPlaylistDelete(); self.ready()
        self.assertFalse(self.b.playlistDeleteState['completed'])
        self.assertEqual(self.b.libraryItemsModel.count, 2)
        self.assertTrue(self.b.playlistDeleteState['canRecheck'])
        self.assertFalse(self.b.playlistDeleteState['error'])

    def test_playlist_already_absent_from_library_is_not_a_transition(self):
        self.library([])
        self.api.delete_playlist.return_value = {}
        self.load(); self.open(); self.b.confirmPlaylistDelete(); self.ready()
        self.assertFalse(self.b.playlistDeleteState['completed'])
        self.assertEqual(self.b.detailTitle, 'Same title')
        self.assertTrue(self.b.playlistDeleteState['canRecheck'])

    def test_explicit_not_found_with_valid_library_can_confirm_without_baseline_membership(self):
        from ytmusicapi.exceptions import YTMusicServerError
        self.library([])
        self.load(); self.open()
        def delete(pid):
            self.api.get_playlist.side_effect = YTMusicServerError('Server returned HTTP 404: Not Found.')
            return {}
        self.api.delete_playlist.side_effect = delete
        self.b.confirmPlaylistDelete(); self.ready()
        self.assertTrue(self.b.playlistDeleteState['completed'])
        self.api.delete_playlist.assert_called_once_with('mine')

    def test_validated_first_page_cannot_disappear_from_a_broken_full_list(self):
        card = {'musicTwoRowItemRenderer': {
            'title': {'runs': [{'text': 'Same title', 'navigationEndpoint': {'browseEndpoint': {'browseId': 'VLmine'}}}]},
            'subtitle': {'runs': []}}}
        self.api._send_request.return_value = self.library_response([card])
        self.api.get_library_playlists.return_value = []
        with self.assertRaises(ValueError):
            self.b._read_playlist_library_ids(self.api)
