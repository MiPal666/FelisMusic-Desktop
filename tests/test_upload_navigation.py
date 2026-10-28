"""Uploaded track navigation preserves real IDs, history, queue and audio."""
from copy import deepcopy
from unittest.mock import Mock
import test_prefetch as support


class UploadNavigationTests(support.AudioPlaybackTestCase):
    ALBUM = 'FEmusic_library_privately_owned_release_detailb_po_album'
    ARTIST = 'FEmusic_library_privately_owned_artist_detaila_po_artist'
    OTHER = 'FEmusic_library_privately_owned_artist_detaila_po_other'

    def setUp(self):
        super().setUp()
        self.api = Mock(); self.b._ytmusic = self.api
        self.rows = [dict(videoId='upload', title='Song', entityId='entity', likeStatus='LIKE',
                          artists=[dict(name='Artist', id=self.ARTIST)], album=dict(name='Album', id=self.ALBUM))]
        self.api.get_library_upload_songs.return_value = deepcopy(self.rows)
        self.api.get_library_upload_artist.return_value = deepcopy(self.rows)
        self.api.get_library_upload_album.return_value = dict(title='Album', tracks=deepcopy(self.rows))
        self.context = dict(page=1, librarySection='upload_songs', libraryLabel='Nahrané skladby', libraryOrder='a_to_z')
        self.opened = []; self.restored = []
        self.b.uploadNavigationOpened.connect(lambda context: self.opened.append(dict(context)))
        self.b.sourceNavigationRestored.connect(lambda context: self.restored.append(dict(context)))

    def ready(self):
        self.until(lambda: not self.b.busy)

    def load(self):
        self.b.loadLibrarySection('upload_songs', 'a_to_z'); self.ready()

    def navigate(self, source, target, artist='', context=None):
        self.assertTrue(self.b.openUploadTrackTarget(source, 0, target, artist, context or self.context)); self.ready()

    def test_library_song_album_artist_and_two_backs_preserve_original_list_and_audio(self):
        self.load(); items = self.b.libraryItemsModel.snapshot()
        self.b.playFrom('library', 0); self.until(lambda: self.b.playerState == 'playing')
        queue = self.b._queue; played = list(self.played); self.b._player_position = 42
        self.navigate('library', 'album')
        self.api.get_library_upload_album.assert_called_once_with(self.ALBUM)
        album = self.b._detail_state()
        self.navigate('detail', 'artist', self.ARTIST)
        self.api.get_library_upload_artist.assert_called_once_with(self.ARTIST, limit=None)
        self.assertEqual(self.b.detailMeta['kind'], 'upload_artist')
        self.b.setArtistOrder('z_to_a'); self.b.backDetail()
        self.assertEqual(self.b._detail_state(), album)
        self.b.backDetail()
        self.assertEqual(self.b.detailTitle, '')
        self.assertEqual(self.b.libraryItemsModel.snapshot(), items)
        self.assertEqual(self.restored[-1], self.context)
        self.assertIs(self.b._queue, queue); self.assertEqual(self.played, played)
        self.assertEqual(self.b.playerPosition, 42)
        self.assertEqual(self.b.playerVisibleSourceIndex, 0)

    def test_artist_album_back_restores_order_and_exact_duplicate_rows(self):
        self.api.get_library_upload_artist.return_value = self.rows * 2
        self.b.openLibraryItem('upload_artist', self.ARTIST, '', 'Artist'); self.ready()
        self.b.setArtistOrder('z_to_a'); state = self.b._detail_state()
        self.navigate('detail', 'album'); self.b.backDetail()
        self.assertEqual(self.b._detail_state(), state)
        self.assertEqual(self.b.detailTracksModel.count, 2)
        self.assertEqual(self.b.detailMeta['orders']['songs'], 'z_to_a')

    def test_queue_keeps_artist_ids_and_returns_to_queue_context_after_navigation(self):
        self.load(); self.b.playFrom('library', 0); self.until(lambda: self.b.playerState == 'playing')
        item = self.b.playingTracksModel.snapshot()[0]
        self.assertEqual(item['artistLinks'], [dict(name='Artist', id=self.ARTIST)])
        self.assertEqual(item['albumId'], self.ALBUM)
        queue = self.b._queue; played = list(self.played)
        context = dict(self.context, page=5)
        self.navigate('playing', 'artist', self.ARTIST, context)
        self.assertEqual(self.opened[-1]['page'], 1)
        self.assertEqual(self.opened[-1]['librarySection'], 'upload_artists')
        self.b.backDetail()
        self.assertEqual(self.restored[-1]['page'], 5)
        self.assertIs(self.b._queue, queue); self.assertEqual(self.played, played)

    def test_search_navigation_restores_search_rows_without_another_request(self):
        self.b.searchResultsModel.set_items([self.b._track(self.rows[0], upload=True)])
        context = dict(page=0, searchScope='uploads', searchMode='all', searchText='Song')
        self.navigate('search', 'album', context=context)
        self.b.backDetail()
        self.assertEqual(self.restored[-1], context)
        self.assertEqual(self.b.searchResultsModel.count, 1)
        self.api.search.assert_not_called()

    def test_multiple_artists_use_selected_id_without_search_or_name_matching(self):
        row = dict(self.rows[0], artists=[dict(name='First', id=self.ARTIST), dict(name='Second', id=self.OTHER)])
        self.b._library_section = 'upload_songs'
        self.b.libraryItemsModel.set_items([self.b._track(row)])
        self.navigate('library', 'artist', self.OTHER)
        self.api.get_library_upload_artist.assert_called_once_with(self.OTHER, limit=None)
        self.api.search.assert_not_called(); self.api.get_artist.assert_not_called()

    def test_album_id_and_artist_context_fallback_when_track_payload_lacks_links(self):
        self.api.get_library_upload_album.return_value['tracks'] = [dict(self.rows[0], album=None)]
        self.b.openLibraryItem('upload_album', self.ALBUM, '', 'Album'); self.ready()
        self.assertEqual(self.b.detailTracksModel.snapshot()[0]['albumId'], self.ALBUM)
        self.api.get_library_upload_artist.return_value = [dict(self.rows[0], artists=None)]
        self.b.openLibraryItem('upload_artist', self.ARTIST, '', 'Artist'); self.ready()
        self.assertEqual(self.b.detailTracksModel.snapshot()[0]['artistLinks'], [dict(id=self.ARTIST, name='Artist')])

    def test_missing_links_catalog_rows_invalid_targets_and_busy_are_rejected(self):
        self.b.libraryItemsModel.set_items([self.b._track(dict(self.rows[0], artists=[], album=None))])
        for target, aid in (('album', ''), ('artist', self.ARTIST), ('unknown', '')):
            self.assertFalse(self.b.openUploadTrackTarget('library', 0, target, aid, self.context))
        self.load(); self.b._busy = True
        self.assertFalse(self.b.openUploadTrackTarget('library', 0, 'album', '', self.context)); self.b._busy = False
        self.b.libraryItemsModel.set_items([dict(self.b.libraryItemsModel.snapshot()[0], kind='song')])
        self.assertFalse(self.b.openUploadTrackTarget('library', 0, 'album', '', self.context))
        self.assertFalse(self.opened)

    def test_failed_endpoint_preserves_parent_and_clears_pending_navigation(self):
        self.b.openLibraryItem('upload_artist', self.ARTIST, '', 'Artist'); self.ready()
        state = self.b._detail_state()
        self.api.get_library_upload_album.side_effect = RuntimeError('unavailable')
        self.navigate('detail', 'album')
        self.assertEqual(self.b._detail_state(), state)
        self.assertIsNone(self.b._pending_detail_parent)
        self.assertFalse(self.opened); self.assertEqual(len(self.errors), 1)

    def test_detail_target_restrictions_and_menu_sections_follow_navigation_and_back(self):
        self.load()
        self.navigate('library', 'artist', self.ARTIST)
        artist_context = self.opened[-1]
        self.assertEqual(artist_context['librarySection'], 'upload_artists')
        self.assertEqual(self.b._library_section, 'upload_artists')
        self.assertFalse(self.b.openUploadTrackTarget('detail', 0, 'artist', self.ARTIST, artist_context))
        self.navigate('detail', 'album', context=artist_context)
        album_context = self.opened[-1]
        self.assertEqual(album_context['librarySection'], 'upload_albums')
        self.assertEqual(self.b._library_section, 'upload_albums')
        self.assertFalse(self.b.openUploadTrackTarget('detail', 0, 'album', '', album_context))
        self.b.backDetail()
        self.assertEqual(self.restored[-1]['librarySection'], 'upload_artists')
        self.assertEqual(self.b._library_section, 'upload_artists')
        self.b.backDetail()
        self.assertEqual(self.restored[-1]['librarySection'], 'upload_songs')
        self.assertEqual(self.b._library_section, 'upload_songs')

    def test_search_moves_to_corresponding_library_menu_then_back_to_search(self):
        self.b.searchResultsModel.set_items([self.b._track(self.rows[0], upload=True)])
        context = dict(page=0, searchScope='uploads', searchMode='all', searchText='Song')
        self.navigate('search', 'album', context=context)
        self.assertEqual(self.opened[-1]['page'], 1)
        self.assertEqual(self.opened[-1]['librarySection'], 'upload_albums')
        self.b.backDetail(); self.assertEqual(self.restored[-1], context)

    def test_album_header_supplies_artist_when_track_has_none_and_preserves_track_override(self):
        self.api.get_library_upload_album.return_value.update(
            artists=[dict(name='Album Artist', id=self.ARTIST)],
            tracks=[dict(self.rows[0], artists=None),
                    dict(self.rows[0], videoId='other', artists=[dict(name='Track Artist', id=self.OTHER)])])
        self.b.openLibraryItem('upload_album', self.ALBUM, '', 'Album'); self.ready()
        items = self.b.detailTracksModel.snapshot()
        self.assertEqual(items[0]['artistLinks'], [dict(id=self.ARTIST, name='Album Artist')])
        self.assertEqual(items[1]['artistLinks'], [dict(id=self.OTHER, name='Track Artist')])
        self.navigate('detail', 'artist', self.ARTIST)
        self.api.get_library_upload_artist.assert_called_once_with(self.ARTIST, limit=None)
        self.b.backDetail()
        self.assertEqual(self.b.detailTracksModel.snapshot(), items)
        self.b.playFrom('detail', 0); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playingTracksModel.snapshot()[0]['artistLinks'], items[0]['artistLinks'])

    def test_album_header_multiple_artists_and_missing_private_ids(self):
        self.api.get_library_upload_album.return_value.update(
            artists=[dict(name='First', id=self.ARTIST), dict(name='Second', id=self.OTHER)],
            tracks=[dict(self.rows[0], artists=None)])
        self.b.openLibraryItem('upload_album', self.ALBUM, '', 'Album'); self.ready()
        self.assertEqual(len(self.b.detailTracksModel.snapshot()[0]['artistLinks']), 2)
        self.navigate('detail', 'artist', self.OTHER)
        self.api.get_library_upload_artist.assert_called_once_with(self.OTHER, limit=None)
        for artists in (None, [dict(name='No ID')], [dict(name='Catalog', id='UCcatalog')]):
            self.api.get_library_upload_album.return_value['artists'] = artists
            self.b.openLibraryItem('upload_album', self.ALBUM, '', 'Album'); self.ready()
            self.assertEqual(self.b.detailTracksModel.snapshot()[0]['artistLinks'], [])
            self.assertFalse(self.b.openUploadTrackTarget('detail', 0, 'artist', self.ARTIST, self.context))

    def test_menu_link_generic_name_is_resolved_by_actual_uploaded_artist_id(self):
        self.api.get_library_upload_album.return_value['tracks'] = [dict(self.rows[0], artists=None,
            artistLinks=[dict(id=self.ARTIST, name='Interpret')])]
        self.b.openLibraryItem('upload_album', self.ALBUM, '', 'Album'); self.ready()
        self.navigate('detail', 'artist', self.ARTIST)
        self.assertEqual(self.b.detailTitle, 'Artist')
