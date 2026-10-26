"""Artist sections, continuations and navigation without network or audio."""
from copy import deepcopy
from unittest.mock import Mock
import test_prefetch as support


class ArtistTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock()
        self.b._ytmusic = self.api
        self.data = {
            'name': 'Artist',
            'songs': {'results': [{'title': 'Song', 'videoId': 'S', 'likeStatus': 'LIKE'}], 'browseId': 'VLsongs'},
            'albums': {'results': [{'title': 'Album', 'browseId': 'album'}], 'browseId': 'artistAlbums', 'params': 'albumsParam'},
            'singles': {'results': [{'title': 'EP', 'browseId': 'ep'}]},
        }
        self.api.get_artist.return_value = deepcopy(self.data)
        self.api.get_playlist.return_value = {'tracks': deepcopy(self.data['songs']['results'])}
        self.api.get_artist_albums.return_value = deepcopy(self.data['albums']['results'])
        self.api.get_album.return_value = {'title': 'Album', 'tracks': [{'title': 'Album song', 'videoId': 'T'}]}

    def open_artist(self):
        self.b.openLibraryItem('artist', 'artist', '', 'Artist')
        self.until(lambda: not self.b.busy)

    def test_sections_and_nested_back_preserve_artist_tab(self):
        self.open_artist()
        self.assertEqual(self.b.detailTracksModel.snapshot()[0]['videoId'], 'S')
        self.b.selectArtistSection('albums'); self.until(lambda: not self.b.busy)
        self.b.openDetailItem(0)
        self.until(lambda: not self.b.busy)
        self.assertEqual(self.b.detailMeta, {'kind': 'album', 'browseId': 'album', 'shufflePlaylistId': ''})
        self.assertEqual(self.b.detailTracksModel.snapshot()[0]['videoId'], 'T')
        self.b.backDetail()
        self.assertEqual(self.b.detailMeta['section'], 'albums')
        self.assertEqual(self.b.detailTracksModel.snapshot()[0]['browseId'], 'album')
        self.b.selectArtistSection('singles')
        self.assertEqual(self.b.detailTracksModel.snapshot()[0]['title'], 'EP')
        self.b.backDetail()
        self.assertEqual(self.b.detailTitle, '')

    def test_expansion_uses_server_pointer_and_is_cached(self):
        self.api.get_artist_albums.return_value = [{'title': str(i), 'browseId': str(i)} for i in range(103)]
        self.open_artist(); self.b.selectArtistSection('albums'); self.until(lambda: not self.b.busy)
        self.until(lambda: not self.b.busy)
        self.api.get_artist_albums.assert_called_once_with('artistAlbums', 'albumsParam', limit=None)
        self.assertEqual(self.b.detailTracksModel.count, 103)
        self.b.selectArtistSection('albums')
        self.b.selectArtistSection('songs'); self.b.selectArtistSection('albums'); self.until(lambda: not self.b.busy)
        self.assertEqual(self.b.detailTracksModel.count, 103)
        self.assertEqual(self.api.get_artist_albums.call_count, 1)

    def test_song_expansion_and_missing_continuation(self):
        self.api.get_playlist.return_value = {'tracks': [{'title': 'Full', 'videoId': 'full'}]}
        self.open_artist(); self.until(lambda: not self.b.busy)
        self.api.get_playlist.assert_called_once_with('VLsongs', limit=None)
        self.assertEqual(self.b.detailTracksModel.snapshot()[0]['videoId'], 'full')
        self.b.selectArtistSection('singles')
        self.api.get_artist_albums.assert_not_called()

    def test_failure_retains_parent_without_extra_history(self):
        self.open_artist(); self.b.selectArtistSection('albums'); self.until(lambda: not self.b.busy)
        self.api.get_album.side_effect = RuntimeError('Unavailable')
        self.b.openDetailItem(0); self.until(lambda: not self.b.busy)
        self.assertEqual(self.b.detailMeta['section'], 'albums')
        self.assertFalse(self.b._detail_history)
        self.assertIsNone(self.b._pending_detail_parent)

    def test_cover_restores_artist_sections_and_nested_album_history(self):
        self.open_artist(); self.b.playFrom('detail', 0)
        self.until(lambda: self.b.playerState == 'playing')
        self.b.clearDetail(); self.b.restorePlayingSource(1)
        self.assertEqual(self.b.detailMeta['kind'], 'artist')
        self.b.selectArtistSection('albums'); self.until(lambda: not self.b.busy); self.b.openDetailItem(0)
        self.until(lambda: not self.b.busy)
        self.b.playFrom('detail', 0); self.until(lambda: self.b.playerState == 'playing')
        self.b.clearDetail(); self.b.restorePlayingSource(1); self.b.backDetail()
        self.assertEqual(self.b.detailMeta['section'], 'albums')
        self.assertEqual(self.played, ['S', 'T'])

    def test_empty_artist_keeps_detail_and_browsing_does_not_change_audio(self):
        self.start('A', 'B')
        queue = self.b._queue; stops = len(self.stops)
        self.api.get_artist.return_value = {'name': 'Empty'}
        self.open_artist(); self.b.selectArtistSection('singles')
        self.assertEqual(self.b.detailTitle, 'Empty')
        self.assertEqual(self.b.detailTracksModel.count, 0)
        self.assertIs(self.b._queue, queue)
        self.assertEqual(self.played, ['A'])
        self.assertEqual(len(self.stops), stops)

    def test_rating_survives_tab_switch_and_cover_restore(self):
        self.open_artist()
        self.b.enqueueFrom('detail', 0, False, {})
        self.b._propagate_like_status('S', 'DISLIKE')
        self.b.selectArtistSection('albums'); self.until(lambda: not self.b.busy); self.b.selectArtistSection('songs')
        self.assertEqual(self.b.detailTracksModel.snapshot()[0]['likeStatus'], 'DISLIKE')
        self.b.clearDetail(); self.b.restorePlayingSource(1)
        self.assertEqual(self.b.detailTracksModel.snapshot()[0]['likeStatus'], 'DISLIKE')

    def test_expansion_failure_and_upload_artist_keep_existing_behavior(self):
        self.api.get_artist_albums.side_effect = RuntimeError('Temporary')
        self.open_artist(); self.b.selectArtistSection('albums'); self.until(lambda: not self.b.busy)
        self.assertIn('albums', self.b.detailMeta['pointers'])
        self.assertEqual(self.b.detailMeta['section'], 'songs')
        self.api.get_library_upload_artist.return_value = [{'title': 'Private', 'videoId': 'private'}]
        self.b.clearDetail(); self.b.openLibraryItem('upload_artist', 'privateArtist', '', 'Uploaded artist')
        self.until(lambda: not self.b.busy)
        self.assertEqual(self.b.detailMeta, {})
        self.assertEqual(self.b.detailTracksModel.snapshot()[0]['kind'], 'upload_song')
        self.assertEqual(self.api.get_artist.call_count, 1)

    def test_full_initial_songs_sort_and_restore_server_order(self):
        self.api.get_playlist.return_value = {'tracks': [
            {'title': 'Zulu', 'videoId': 'Z'}, {'title': 'Alpha', 'videoId': 'A'},
            {'title': 'Beta', 'videoId': 'B'}]}
        self.open_artist()
        def titles():
            return [x['title'] for x in self.b.detailTracksModel.snapshot()]
        self.assertEqual(titles(), ['Alpha', 'Beta', 'Zulu'])
        self.b.setArtistOrder('z_to_a')
        self.assertEqual(titles(), ['Zulu', 'Beta', 'Alpha'])
        self.b.setArtistOrder('default')
        self.assertEqual(titles(), ['Zulu', 'Alpha', 'Beta'])
        self.b.setArtistOrder('newest')  # Not available on songs.
        self.assertEqual(titles(), ['Zulu', 'Alpha', 'Beta'])
        self.api.get_playlist.assert_called_once_with('VLsongs', limit=None)

    def test_year_order_missing_year_and_per_section_preferences(self):
        self.api.get_artist_albums.return_value = [
            {'title': 'Zulu', 'browseId': 'z', 'year': '2000'},
            {'title': 'Unknown', 'browseId': 'u'},
            {'title': 'Alpha', 'browseId': 'a', 'year': '2025'}]
        self.open_artist(); self.b.setArtistOrder('z_to_a')
        self.b.selectArtistSection('albums'); self.until(lambda: not self.b.busy)
        def ids():
            return [x['browseId'] for x in self.b.detailTracksModel.snapshot()]
        self.assertEqual(ids(), ['a', 'u', 'z'])
        self.b.setArtistOrder('newest'); self.assertEqual(ids(), ['a', 'z', 'u'])
        self.b.setArtistOrder('oldest'); self.assertEqual(ids(), ['z', 'a', 'u'])
        self.b.selectArtistSection('songs')
        self.assertEqual(self.b.detailMeta['orders']['songs'], 'z_to_a')
        self.b.selectArtistSection('albums')
        self.assertEqual(ids(), ['z', 'a', 'u'])
        self.api.get_artist_albums.assert_called_once()

    def test_singles_load_all_with_own_pointer_and_retry_after_failure(self):
        self.api.get_artist.return_value['singles'].update(browseId='singlesId', params='singlesParam')
        self.api.get_artist_albums.side_effect = [RuntimeError('Temporary'), [
            {'title': 'Zulu EP', 'browseId': 'z'}, {'title': 'Alpha EP', 'browseId': 'a'}]]
        self.open_artist(); self.b.selectArtistSection('singles'); self.until(lambda: not self.b.busy)
        self.assertEqual(self.b.detailMeta['section'], 'songs')
        self.b.selectArtistSection('singles'); self.until(lambda: not self.b.busy)
        self.assertEqual([x['browseId'] for x in self.b.detailTracksModel.snapshot()], ['a', 'z'])
        self.api.get_artist_albums.assert_called_with('singlesId', 'singlesParam', limit=None)
        self.b.selectArtistSection('songs'); self.b.selectArtistSection('singles')
        self.assertEqual(self.api.get_artist_albums.call_count, 2)
