"""Saving a selected song into owned playlists, with explicit duplicate policy."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock
import test_prefetch as support


class PlaylistSaveTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock()
        self.b._ytmusic = self.api
        self.b._playlist_verify_delays = (0, 0, 0)
        self.data = {'mine': {'title': 'Mine', 'owned': True, 'tracks': []}}
        self.api.get_library_playlists.return_value = [
            {'title': 'Mine', 'playlistId': 'mine', 'owned': True},
            {'title': 'Foreign', 'playlistId': 'foreign', 'owned': False},
            {'title': 'Unknown', 'playlistId': 'unknown'},
            {'title': 'Automatic', 'playlistId': 'LM', 'owned': True}]
        self.api.get_playlist.side_effect = lambda pid, **kwargs: deepcopy(self.data[pid])
        self.api.add_playlist_items.side_effect = self.add
        self.api.create_playlist.side_effect = self.create
        self.opened = []
        self.b.playlistSaveRequested.connect(lambda: self.opened.append(self.b.busy))

    def add(self, pid, videoIds, duplicates):
        self.data[pid]['tracks'].extend(dict(videoId=v, title=v, setVideoId=str(i)) for i, v in enumerate(videoIds))
        return {'status': 'STATUS_SUCCEEDED'}

    def create(self, title, description, privacy_status, video_ids):
        self.data['new'] = dict(title=title, owned=True, tracks=[dict(videoId=v, title=v) for v in video_ids])
        return 'new'

    def ready(self):
        self.until(lambda: not self.b.busy)

    def open(self, source='library', index=0):
        self.assertTrue(self.b.openPlaylistSave(source, index)); self.ready()

    def test_only_owned_targets_and_selected_song_no_audio_or_rating_changes(self):
        self.start('A', 'B'); queue = self.b._queue; stops = len(self.stops)
        self.b._player_position = 44
        self.open()
        self.assertEqual(self.b.playlistSaveState['targets'], [{'playlistId': 'mine', 'title': 'Mine'}])
        self.assertEqual(self.opened, [False])
        self.api.get_library_playlists.assert_called_once_with(limit=None)
        self.b.saveSongToPlaylist('mine', False); self.ready()
        self.api.add_playlist_items.assert_called_once_with('mine', videoIds=['A'], duplicates=False)
        self.assertEqual([x['videoId'] for x in self.data['mine']['tracks']], ['A'])
        self.assertTrue(self.b.playlistSaveState['completed'])
        self.assertIs(self.b._queue, queue)
        self.assertEqual(self.played, ['A'])
        self.assertEqual(len(self.stops), stops)
        self.assertEqual(self.b.playerPosition, 44)
        self.api.rate_song.assert_not_called()
        self.api.edit_song_library_status.assert_not_called()

    def test_duplicates_skipped_by_default_and_explicit_extra_occurrence(self):
        self.start('A'); self.data['mine']['tracks'] = [dict(videoId='A')]
        self.open(); self.b.saveSongToPlaylist('mine', False); self.ready()
        self.api.add_playlist_items.assert_not_called()
        self.assertIn('Nic se nepřidalo', self.b.playlistSaveState['message'])
        self.assertTrue(self.b.playlistSaveState['duplicate'])
        self.open(); self.b.saveSongToPlaylist('mine', True); self.ready()
        self.assertEqual(len(self.data['mine']['tracks']), 2)
        self.api.add_playlist_items.assert_called_once_with('mine', videoIds=['A'], duplicates=True)

    def test_create_private_with_song_in_single_request(self):
        self.start('A'); self.api.get_library_playlists.return_value = []
        self.open(); self.b.createPlaylistWithSong('  New list  '); self.ready()
        self.api.create_playlist.assert_called_once_with('New list', '', privacy_status='PRIVATE', video_ids=['A'])
        self.api.add_playlist_items.assert_not_called()
        self.assertTrue(self.b.playlistSaveState['completed'])
        self.assertEqual(self.b.playlistSaveState['playlistId'], 'new')

    def test_name_validation_and_unsupported_rows(self):
        self.start('A'); self.open()
        for title in ('', ' ', '<bad>', 'bad>'):
            self.b.createPlaylistWithSong(title)
        self.api.create_playlist.assert_not_called()
        self.b.searchResultsModel.set_items([dict(kind='album', browseId='album'), dict(kind='episode', videoId='ep')])
        for index in (-1, 0, 1, 2):
            self.assertFalse(self.b.openPlaylistSave('search', index))

    def test_unknown_target_and_changed_ownership_do_not_write(self):
        self.start('A'); self.open()
        self.b.saveSongToPlaylist('foreign', False)
        self.api.get_playlist.assert_not_called()
        self.data['mine']['owned'] = False
        self.b.saveSongToPlaylist('mine', False); self.ready()
        self.api.add_playlist_items.assert_not_called()
        self.assertTrue(self.b.playlistSaveState['error'])
        self.assertFalse(self.b.playlistSaveState['locked'])

    def test_write_failure_and_unverified_result_block_automatic_retry(self):
        self.start('A'); self.open()
        self.api.add_playlist_items.side_effect = RuntimeError('Offline')
        self.b.saveSongToPlaylist('mine', False); self.ready()
        self.assertTrue(self.b.playlistSaveState['locked'])
        self.b.saveSongToPlaylist('mine', False)
        self.assertEqual(self.api.add_playlist_items.call_count, 1)
        self.open()
        self.api.add_playlist_items.side_effect = None
        self.api.add_playlist_items.return_value = {'status': 'STATUS_SUCCEEDED'}
        self.b.saveSongToPlaylist('mine', False); self.ready()
        self.assertTrue(self.b.playlistSaveState['completed'])
        self.assertFalse(self.b.playlistSaveState['verified'])
        self.assertTrue(self.b.playlistSaveState['canRecheck'])
        self.assertTrue(self.b.playlistSaveState['locked'])

    def test_failed_create_response_is_not_reported_as_new_playlist(self):
        self.start('A'); self.open()
        self.api.create_playlist.side_effect = None
        self.api.create_playlist.return_value = {'status': 'STATUS_FAILED'}
        self.b.createPlaylistWithSong('New'); self.ready()
        self.assertTrue(self.b.playlistSaveState['error'])
        self.assertFalse(self.b.playlistSaveState['completed'])

    def test_create_succeeds_but_readback_fails_reports_existing_creation(self):
        self.start('A'); self.open()
        self.api.get_playlist.side_effect = RuntimeError('Read failed')
        self.b.createPlaylistWithSong('New'); self.ready()
        self.assertIn('byl vytvořen', self.b.playlistSaveState['message'])
        self.assertTrue(self.b.playlistSaveState['locked'])
        self.b.createPlaylistWithSong('New')
        self.assertEqual(self.api.create_playlist.call_count, 1)
        self.assertIn('new', self.data)

    def test_selection_stays_bound_after_next_and_upload_uses_exact_id(self):
        self.start('A', 'B'); self.open()
        self.b.nextTrack(); self.until(lambda: self.b.playerState == 'playing')
        self.b.saveSongToPlaylist('mine', False); self.ready()
        self.assertEqual(self.data['mine']['tracks'][0]['videoId'], 'A')
        self.b.searchResultsModel.set_items([dict(kind='upload_song', videoId='private-id', title='Uploaded')])
        self.open('search'); self.b.saveSongToPlaylist('mine', False); self.ready()
        self.assertEqual(self.data['mine']['tracks'][-1]['videoId'], 'private-id')
        self.assertEqual(self.played, ['A', 'B'])

    def test_double_submit_and_completed_operation_cannot_repeat(self):
        self.start('A'); self.open()
        entered = Event()
        def slow(pid, **kwargs):
            entered.set(); self.release.wait(3); return self.add(pid, **kwargs)
        self.api.add_playlist_items.side_effect = slow
        self.b.saveSongToPlaylist('mine', False); self.until(entered.is_set)
        self.b.saveSongToPlaylist('mine', False)
        self.release.set(); self.ready()
        self.b.saveSongToPlaylist('mine', False)
        self.assertEqual(self.api.add_playlist_items.call_count, 1)

    def test_saved_playlist_view_updates_without_rebuilding_its_playback_queue(self):
        self.data['mine']['tracks'] = [dict(videoId='B', title='B', likeStatus='LIKE')]
        self.b.loadPlaylistTracks('mine', 'Mine'); self.ready()
        self.b.playFrom('detail', 0); self.until(lambda: self.b.playerState == 'playing')
        queue = self.b._queue
        self.b.searchResultsModel.set_items([dict(kind='song', title='A', videoId='A')])
        self.open('search'); self.b.saveSongToPlaylist('mine', False); self.ready()
        self.assertEqual([x['videoId'] for x in self.b.detailTracksModel.snapshot()], ['B', 'A'])
        self.assertIs(self.b._queue, queue)
        self.assertEqual([x['videoId'] for x in queue.tracks], ['B'])
        self.assertEqual(self.played, ['B'])

    def test_create_retries_missing_response_and_stale_contents_without_recreating(self):
        self.start('A'); self.open()
        reads = []
        def eventual(pid, **kwargs):
            reads.append(pid)
            if len(reads) == 1:
                raise KeyError("contents: responseContext with private diagnostics")
            if len(reads) == 2:
                return {'tracks': []}
            return deepcopy(self.data[pid])
        self.api.get_playlist.side_effect = eventual
        self.b.createPlaylistWithSong('Eventually ready'); self.ready()
        self.assertTrue(self.b.playlistSaveState['verified'])
        self.assertFalse(self.b.playlistSaveState['canRecheck'])
        self.assertEqual(reads, ['new', 'new', 'new'])
        self.api.create_playlist.assert_called_once()
        self.api.add_playlist_items.assert_not_called()

    def test_manual_recheck_never_repeats_creation_or_insertion(self):
        self.start('A'); self.open()
        self.api.get_playlist.side_effect = KeyError('contents: responseContext secret details')
        self.b.createPlaylistWithSong('New'); self.ready()
        state = self.b.playlistSaveState
        self.assertTrue(state['completed'])
        self.assertTrue(state['canRecheck'])
        self.assertFalse(state['error'])
        self.assertIn('byl vytvořen', state['message'])
        self.assertNotIn('responseContext', state['message'])
        self.assertLess(len(state['message']), 300)
        self.api.get_playlist.side_effect = lambda pid, **kwargs: deepcopy(self.data[pid])
        self.b.recheckPlaylistSave(); self.ready()
        self.assertTrue(self.b.playlistSaveState['verified'])
        self.assertFalse(self.b.playlistSaveState['canRecheck'])
        self.api.create_playlist.assert_called_once()
        self.api.add_playlist_items.assert_not_called()

    def test_confirmed_addition_with_failed_readback_can_only_repeat_reads(self):
        self.start('A'); self.open()
        calls = []
        def get(pid, **kwargs):
            calls.append(pid)
            if len(calls) > 1:
                raise KeyError('contents: responseContext secret details')
            return deepcopy(self.data[pid])
        self.api.get_playlist.side_effect = get
        self.b.saveSongToPlaylist('mine', False); self.ready()
        self.assertTrue(self.b.playlistSaveState['canRecheck'])
        self.assertIn('potvrdilo přidání', self.b.playlistSaveState['message'])
        self.assertNotIn('secret', self.b.playlistSaveState['message'])
        self.b.saveSongToPlaylist('mine', True)
        self.api.get_playlist.side_effect = lambda pid, **kwargs: deepcopy(self.data[pid])
        self.b.recheckPlaylistSave(); self.ready()
        self.assertTrue(self.b.playlistSaveState['verified'])
        self.api.add_playlist_items.assert_called_once()
        self.assertEqual(len(self.data['mine']['tracks']), 1)

    def collection(self, ids):
        self.b._detail_title = 'Collection'
        self.b.detailTracksModel.set_items([dict(kind='song', title=v, videoId=v) for v in ids])
        self.b.detailTitleChanged.emit()
        self.assertTrue(self.b.openCollectionPlaylistSave()); self.ready()

    def test_collection_skips_existing_and_internal_duplicates_in_visible_order(self):
        self.start('Q', 'R'); queue = self.b._queue
        self.data['mine']['tracks'] = [dict(videoId='B')]
        self.collection(['A', 'B', 'A', 'C'])
        self.assertEqual(self.b.playlistSaveState['selectionCount'], 4)
        self.b.clearDetail()  # Selection is already captured.
        self.b.saveSongToPlaylist('mine', False); self.ready()
        self.api.add_playlist_items.assert_called_once_with('mine', videoIds=['A', 'C'], duplicates=False)
        self.assertTrue(self.b.playlistSaveState['verified'])
        self.assertIn('Vynecháno duplicit: 2', self.b.playlistSaveState['message'])
        self.assertIs(self.b._queue, queue)
        self.assertEqual(self.played, ['Q'])
        self.assertEqual([x['videoId'] for x in queue.tracks], ['Q', 'R'])

    def test_collection_explicit_duplicates_keep_every_occurrence(self):
        self.data['mine']['tracks'] = [dict(videoId='A')]
        self.collection(['A', 'B', 'A'])
        self.b.saveSongToPlaylist('mine', True); self.ready()
        self.api.add_playlist_items.assert_called_once_with('mine', videoIds=['A', 'B', 'A'], duplicates=True)
        self.assertEqual([x['videoId'] for x in self.data['mine']['tracks']], ['A', 'A', 'B', 'A'])
        self.assertTrue(self.b.playlistSaveState['verified'])

    def test_collection_create_private_deduplicates_without_reordering(self):
        self.collection(['C', 'A', 'C', 'B'])
        self.b.createPlaylistWithSong('Collected'); self.ready()
        self.api.create_playlist.assert_called_once_with('Collected', '', privacy_status='PRIVATE', video_ids=['C', 'A', 'B'])
        self.assertTrue(self.b.playlistSaveState['verified'])
        self.api.add_playlist_items.assert_not_called()

    def test_collection_all_existing_has_duplicate_result_without_write(self):
        self.data['mine']['tracks'] = [dict(videoId='A'), dict(videoId='B')]
        self.collection(['B', 'A', 'B'])
        self.b.saveSongToPlaylist('mine', False); self.ready()
        self.assertTrue(self.b.playlistSaveState['duplicate'])
        self.assertTrue(self.b.playlistSaveState['collection'])
        self.api.add_playlist_items.assert_not_called()

    def test_collection_partial_readback_does_not_claim_full_success_or_reinsert(self):
        self.collection(['A', 'B'])
        reads = []
        def partial(pid, **kwargs):
            reads.append(pid)
            if len(reads) == 1:
                return deepcopy(self.data[pid])
            return dict(owned=True, tracks=[dict(videoId='A')])
        self.api.get_playlist.side_effect = partial
        self.b.saveSongToPlaylist('mine', False); self.ready()
        self.assertTrue(self.b.playlistSaveState['canRecheck'])
        self.assertFalse(self.b.playlistSaveState['verified'])
        self.api.get_playlist.side_effect = lambda pid, **kwargs: deepcopy(self.data[pid])
        self.b.recheckPlaylistSave(); self.ready()
        self.assertTrue(self.b.playlistSaveState['verified'])
        self.api.add_playlist_items.assert_called_once()

    def test_collection_loads_full_playlist_and_rejects_non_song_section(self):
        self.data['mine']['tracks'] = [dict(title='A', videoId='A'), dict(title='Upload', videoId='private-id')]
        self.b.loadPlaylistTracks('mine', 'Mine'); self.ready()
        self.api.get_playlist.assert_called_with('mine', limit=None)
        self.assertTrue(self.b.detailCanSavePlaylist)
        self.assertTrue(self.b.openCollectionPlaylistSave()); self.ready()
        self.assertEqual(self.b.playlistSaveState['selectionCount'], 2)
        self.b._detail_title = 'Artist albums'
        self.b.detailTracksModel.set_items([dict(kind='album', browseId='album')])
        self.assertFalse(self.b.detailCanSavePlaylist)
        self.assertFalse(self.b.openCollectionPlaylistSave())
