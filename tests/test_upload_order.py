"""Uploaded artist ordering reuses local sort and preserves playback snapshots."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock, patch
import test_prefetch as support


class UploadOrderTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock(); self.b._ytmusic = self.api
        self.rows = [dict(videoId=vid, title=title, entityId=f'entity-{i}', likeStatus='LIKE',
                          artists=[{'name': 'Uploaded Artist'}], album={'name': 'Album', 'id': 'upload-album'})
                     for i, (vid, title) in enumerate((('Z', 'Zulu'), ('A', 'Alpha'), ('A', 'Alpha'), ('B', 'beta')))]
        self.api.get_library_upload_artist.return_value = deepcopy(self.rows)
        self.api.get_library_upload_album.return_value = dict(title='Album', tracks=deepcopy(self.rows))
        self.b.playbackSourceCaptured.connect(lambda: self.b.setPlaybackSourceContext(
            dict(page=1, librarySection='upload_artists', libraryLabel='Nahraní interpreti')))

    def ready(self):
        self.until(lambda: not self.b.busy)

    def load(self):
        self.b.openLibraryItem('upload_artist', 'private-artist', '', 'Artist'); self.ready()

    def titles(self):
        return [x['title'] for x in self.b.detailTracksModel.snapshot()]

    def test_initial_a_to_z_reverse_and_original_order_preserve_all_metadata_and_duplicates(self):
        self.load()
        self.assertEqual(self.titles(), ['Alpha', 'Alpha', 'beta', 'Zulu'])
        self.b.setArtistOrder('z_to_a')
        self.assertEqual(self.titles(), ['Zulu', 'beta', 'Alpha', 'Alpha'])
        self.b.setArtistOrder('default')
        self.assertEqual(self.titles(), ['Zulu', 'Alpha', 'Alpha', 'beta'])
        self.assertEqual(self.b.detailMeta['orders']['songs'], 'default')
        items = self.b.detailTracksModel.snapshot()
        self.assertTrue(all(x['kind'] == 'upload_song' and x['albumId'] == 'upload-album' for x in items))
        self.b.setArtistOrder('a_to_z')
        self.assertEqual(self.titles(), ['Alpha', 'Alpha', 'beta', 'Zulu'])
        self.api.get_library_upload_artist.assert_called_once_with('private-artist', limit=None)
        self.api.get_watch_playlist.assert_not_called()

    def test_sort_during_playback_preserves_queue_audio_and_cover_restores_captured_order(self):
        self.load(); self.b.setArtistOrder('z_to_a')
        original = self.b._detail_state()
        self.b.playFrom('detail', 2); self.until(lambda: self.b.playerState == 'playing')
        queue = self.b._queue; songs = list(queue.tracks); played = list(self.played)
        self.b._player_position = 42; self.b.cycleRepeat()
        self.b.setArtistOrder('default')
        self.assertEqual(queue.tracks, songs); self.assertEqual(self.played, played)
        self.assertEqual(self.b.playerPosition, 42); self.assertEqual(self.b.playerRepeatMode, 'all')
        self.b.clearDetail(); self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual(self.b._detail_state(), original)
        self.assertEqual(self.b.playerSourceIndex, 2)
        self.assertIs(self.b._queue, queue); self.assertEqual(self.played, played)

    def test_shuffle_from_selected_order_has_exact_indices_and_cover(self):
        self.load(); self.b.setArtistOrder('default'); before = self.b.detailTracksModel.snapshot()
        with patch.object(support.backend.random, 'shuffle', side_effect=lambda rows: rows.reverse()):
            self.assertTrue(self.b.shuffleDetail()); self.ready()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual([x['videoId'] for x in self.b._queue.tracks], ['B', 'A', 'A', 'Z'])
        self.assertEqual(self.b._queue_source_indices, [3, 2, 1, 0])
        self.b.clearDetail(); self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual(self.b.detailTracksModel.snapshot(), before)
        self.assertEqual(self.b.detailMeta['orders']['songs'], 'default')

    def test_album_order_invalid_orders_and_busy_guards(self):
        self.b.openLibraryItem('upload_album', 'upload-album', '', 'Album'); self.ready()
        before = self.b._detail_state(); self.b.setArtistOrder('a_to_z')
        self.assertEqual(self.b._detail_state(), before)
        self.load(); before = self.b._detail_state()
        for order in ('newest', 'oldest', 'invalid'):
            self.b.setArtistOrder(order); self.assertEqual(self.b._detail_state(), before)
        self.b._busy = True; self.b.setArtistOrder('default'); self.b._busy = False
        self.assertEqual(self.b._detail_state(), before)
        self.b.selectArtistSection('albums'); self.assertEqual(self.b._detail_state(), before)

    def test_change_of_order_invalidates_pending_shuffle_and_empty_artist_can_be_sorted(self):
        self.load(); entered = Event(); self.release.clear()
        def hold(indices):
            entered.set(); self.release.wait(3); indices.reverse()
        with patch.object(support.backend.random, 'shuffle', side_effect=hold):
            self.assertTrue(self.b.shuffleDetail()); self.until(entered.is_set)
            # Simulate a source-state change before delivery of the worker result.
            self.b._detail_meta['orders']['songs'] = 'default'
            self.release.set(); self.ready()
        self.assertFalse(self.b.playerHasTrack)
        self.api.get_library_upload_artist.return_value = []
        self.load(); self.b.setArtistOrder('z_to_a')
        self.assertEqual(self.b.detailTracksModel.count, 0)
        self.assertFalse(self.b.detailCanShuffle)
