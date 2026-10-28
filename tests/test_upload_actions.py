"""Uploaded collection/row/batch queue and playlist actions, mocked API/audio."""
from copy import deepcopy
from unittest.mock import Mock, patch
import test_prefetch as support
import test_upload_shuffle as upload_support


class UploadActionTests(support.AudioPlaybackTestCase):
    load = upload_support.UploadShuffleTests.load

    def setUp(self):
        super().setUp()
        self.api = Mock(); self.b._ytmusic = self.api
        self.source = [dict(videoId=vid, title=f'Upload {i}', entityId=f'entity-{i}', likeStatus='LIKE')
                       for i, vid in enumerate(('A', 'B', 'A', 'C'))]
        self.api.get_library_upload_songs.return_value = deepcopy(self.source)
        self.api.get_library_upload_album.return_value = dict(title='Uploaded Album', tracks=deepcopy(self.source))
        self.api.get_library_upload_artist.return_value = deepcopy(self.source)
        self.b._playlist_verify_delays = (0, 0, 0)
        self.saved = dict(title='Target', owned=True, tracks=[])
        self.api.get_library_playlists.return_value = [dict(title='Target', playlistId='target', owned=True)]
        self.api.get_playlist.side_effect = lambda pid, **kwargs: deepcopy(self.saved)
        self.api.add_playlist_items.side_effect = self.add
        self.api.create_playlist.side_effect = self.create

    def add(self, pid, videoIds, duplicates):
        self.saved['tracks'].extend(dict(videoId=v, title=v) for v in videoIds)
        return dict(status='STATUS_SUCCEEDED')

    def create(self, title, description, privacy_status, video_ids):
        self.saved.update(title=title, tracks=[dict(videoId=v, title=v) for v in video_ids])
        return 'new'

    def ready(self):
        self.until(lambda: not self.b.busy)

    def source_context(self, kind):
        return ('library' if kind == 'songs' else 'detail',
                dict(page=1, librarySection=self.b._library_section, libraryOrder='a_to_z'))

    def open_save(self, kind):
        opened = self.b.openUploadSongsPlaylistSave() if kind == 'songs' else self.b.openCollectionPlaylistSave()
        self.assertTrue(opened); self.ready()

    def test_whole_collections_next_and_append_keep_current_audio_and_exact_occurrences(self):
        for kind in ('songs', 'album', 'artist'):
            for play_next in (True, False):
                with self.subTest(kind=kind, play_next=play_next):
                    self.start('current', 'last'); self.b.cycleRepeat()
                    self.load(kind); source, context = self.source_context(kind)
                    before = self.b._source_items(source); queue = self.b._queue
                    self.b._player_position = 42; played = list(self.played)
                    self.assertTrue(self.b.enqueueUploadCollection(source, play_next, context))
                    expected = ['current', 'A', 'B', 'A', 'C', 'last'] if play_next else ['current', 'last', 'A', 'B', 'A', 'C']
                    self.assertEqual([x['videoId'] for x in queue.tracks], expected)
                    self.assertEqual([x['videoId'] for x in self.b.playingTracksModel.snapshot()], expected)
                    self.assertIs(self.b._queue, queue); self.assertEqual(self.played, played)
                    self.assertEqual(self.b.playerPosition, 42); self.assertEqual(self.b.playerRepeatMode, 'all')
                    self.assertEqual(self.b._source_items(source), before)
                    slot = 1 if play_next else 2
                    inserted = queue.tracks[slot:slot+4]
                    self.assertTrue(all(x['_guiKind'] == 'upload_song' for x in inserted))
                    self.assertEqual([x['_guiOrigin']['index'] for x in inserted], [0, 1, 2, 3])
                    self.b.playFrom('playing', slot+2); self.until(lambda: self.b.playerState == 'playing')
                    self.b.clearDetail(); self.assertTrue(self.b.restorePlayingSource(1))
                    self.assertEqual(self.b._source_items(source), before)
                    self.assertEqual(self.b.playerSourceIndex, 2)
        self.api.get_watch_playlist.assert_not_called()

    def test_empty_queue_pause_and_stop_do_not_start_playback(self):
        self.load('songs'); source, context = self.source_context('songs')
        self.assertTrue(self.b.enqueueUploadCollection(source, True, context))
        self.assertEqual(self.b.playerState, 'idle'); self.assertFalse(self.played)
        self.assertEqual(self.b.playingListTitle, 'Nahrané skladby')
        self.b.playFrom('playing', 0); self.until(lambda: self.b.playerState == 'playing')
        self.b._player_state = 'paused'; played = list(self.played)
        self.assertTrue(self.b.enqueueUploadCollection(source, False, context))
        self.assertEqual(self.b.playerState, 'paused'); self.assertEqual(self.played, played)
        self.b.stopPlayback()
        self.assertTrue(self.b.enqueueUploadCollection(source, True, context))
        self.assertEqual(self.b.playerState, 'idle'); self.assertEqual(self.played, played)

    def test_single_and_multiselection_enqueue_and_save_preserve_upload_rows(self):
        self.start('current', 'last')
        for kind in ('songs', 'album', 'artist'):
            with self.subTest(kind=kind):
                self.load(kind); source, context = self.source_context(kind)
                self.assertTrue(self.b.enqueueFrom(source, 2, False, context))
                self.b.selectTrack(source, 0, False, False); self.b.selectTrack(source, 2, True, False)
                self.assertTrue(self.b.enqueueSelection(True, context))
                self.assertEqual(self.b.selectedTrackIndices, [])
                self.assertEqual([x['videoId'] for x in self.b._queue.tracks[1:3]], ['A', 'A'])
                self.b.selectTrack(source, 1, False, False); self.b.selectTrack(source, 3, True, False)
                self.assertTrue(self.b.openSelectedPlaylistSave()); self.ready()
                self.assertEqual([x['videoId'] for x in self.b._playlist_save_items], ['B', 'C'])
                self.assertTrue(all(x['kind'] == 'upload_song' for x in self.b._playlist_save_items))
                self.saved['tracks'] = []
                self.b.saveSongToPlaylist('target', False); self.ready()
                self.assertEqual(self.b.selectedTrackIndices, [])
                self.assertTrue(self.b.playlistSaveState['verified'])
                self.assertEqual([x['videoId'] for x in self.saved['tracks']], ['B', 'C'])
                self.assertTrue(self.b.openPlaylistSave(source, 2)); self.ready()
                self.assertEqual(self.b._playlist_save_items[0]['videoId'], 'A')
        self.assertEqual(self.played, ['current'])

    def test_whole_collection_save_existing_duplicate_policy_and_create_privacy(self):
        for kind in ('songs', 'album', 'artist'):
            with self.subTest(kind=kind):
                self.load(kind); self.open_save(kind)
                self.assertEqual(self.b.playlistSaveState['selectionCount'], 4)
                self.assertTrue(self.b.playlistSaveState['collection'])
                self.saved['tracks'] = [dict(videoId='A')]
                self.b.saveSongToPlaylist('target', False); self.ready()
                self.api.add_playlist_items.assert_called_with('target', videoIds=['B', 'C'], duplicates=False)
                self.assertTrue(self.b.playlistSaveState['verified'])
                self.open_save(kind); self.b.saveSongToPlaylist('target', True); self.ready()
                self.api.add_playlist_items.assert_called_with('target', videoIds=['A', 'B', 'A', 'C'], duplicates=True)
                self.open_save(kind); self.b.createPlaylistWithSong('Uploads', 'UNLISTED'); self.ready()
                self.api.create_playlist.assert_called_with('Uploads', '', privacy_status='UNLISTED', video_ids=['A', 'B', 'C'])
                self.assertTrue(self.b.playlistSaveState['verified'])
        self.assertFalse(self.played)

    def test_large_batch_uses_one_source_snapshot_not_one_per_song(self):
        self.api.get_library_upload_artist.return_value = [dict(self.source[i % 4], title=str(i)) for i in range(2101)]
        self.load('artist'); source, context = self.source_context('artist')
        with patch.object(self.b, '_make_origin', wraps=self.b._make_origin) as make_origin:
            self.assertTrue(self.b.enqueueUploadCollection(source, False, context))
        self.assertEqual(make_origin.call_count, 1)
        self.assertEqual(self.b.playerQueueCount, 2101)
        origins = [x['_guiOrigin'] for x in self.b._queue.tracks]
        self.assertTrue(all(x['detail_state'] is origins[0]['detail_state'] for x in origins))
        self.assertEqual([x['index'] for x in origins], list(range(2101)))

    def test_guards_reject_wrong_empty_incomplete_busy_and_transitioning_sources(self):
        self.assertFalse(self.b.enqueueUploadCollection('missing', False, {}))
        self.assertFalse(self.b.openUploadSongsPlaylistSave())
        self.load('album')
        self.assertFalse(self.b.enqueueUploadCollection('library', False, {}))
        self.b._detail_meta['playlistLoadState'] = 'loading'
        self.assertFalse(self.b.enqueueUploadCollection('detail', False, {}))
        self.b._detail_meta.pop('playlistLoadState'); self.b._busy = True
        self.assertFalse(self.b.enqueueUploadCollection('detail', False, {})); self.b._busy = False
        self.b._playback_transitioning = True
        self.assertFalse(self.b.enqueueUploadCollection('detail', False, {})); self.b._playback_transitioning = False
        self.b._detail_tracks_model.clear()
        self.assertFalse(self.b.enqueueUploadCollection('detail', False, {}))
