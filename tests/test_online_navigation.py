"""Catalog track → album/artist navigation with intact source history/audio."""
from copy import deepcopy
from unittest.mock import Mock
import test_prefetch as support


class OnlineNavigationTests(support.AudioPlaybackTestCase):
    ALBUM='MPREalbum';ARTIST='UCartist';OTHER='UCother'

    def setUp(self):
        super().setUp();self.api=Mock();self.b._ytmusic=self.api
        self.rows=[dict(videoId='song',title='Song',likeStatus='LIKE',duration='3:00',
            artists=[dict(name='Artist',id=self.ARTIST)],album=dict(name='Album',id=self.ALBUM))]
        self.api.get_library_songs.return_value=deepcopy(self.rows)
        self.api.get_album.return_value=dict(title='Album',artists=[dict(name='Artist',id=self.ARTIST)],
            audioPlaylistId='OLAKalbum',tracks=[dict(self.rows[0],artists=None)])
        self.api.get_artist.return_value=dict(name='Artist',songs={'results':deepcopy(self.rows)},
            albums={'results':[]},singles={},radioId='RDEMactual',shuffleId='RDAactual')
        self.api.get_playlist.return_value=dict(title='Mine',owned=True,tracks=[dict(self.rows[0],setVideoId='first'),dict(self.rows[0],setVideoId='second')])
        self.context=dict(page=1,librarySection='songs',libraryLabel='Skladby',libraryOrder='a_to_z')
        self.opened=[];self.restored=[]
        self.b.uploadNavigationOpened.connect(lambda context:self.opened.append(dict(context)))
        self.b.sourceNavigationRestored.connect(lambda context:self.restored.append(dict(context)))
        self.b.playbackSourceCaptured.connect(lambda:self.b.setPlaybackSourceContext(self.context))
    def ready(self):self.until(lambda:not self.b.busy)
    def load(self):self.b.loadLibrarySection('songs','a_to_z');self.ready()
    def navigate(self,source,target,aid='',context=None,index=0):
        self.assertTrue(self.b.openTrackTarget(source,index,target,aid,context or self.context));self.ready()
    def play(self,source='library',index=0):self.b.playFrom(source,index);self.until(lambda:self.b.playerState=='playing')

    def test_library_album_artist_two_backs_restore_menu_rows_and_audio(self):
        self.load();self.play();queue=self.b._queue;played=list(self.played);self.b._player_position=42
        rows=self.b.libraryItemsModel.snapshot()
        self.navigate('library','album');album=self.b._detail_state()
        self.assertEqual(self.opened[-1]['librarySection'],'albums')
        self.navigate('detail','artist',self.ARTIST,context=self.opened[-1])
        self.assertEqual(self.opened[-1]['librarySection'],'artists')
        self.b.backDetail();self.assertEqual(self.b._detail_state(),album)
        self.assertEqual(self.restored[-1]['librarySection'],'albums')
        self.b.backDetail();self.assertEqual(self.b.detailTitle,'')
        self.assertEqual(self.b.libraryItemsModel.snapshot(),rows);self.assertEqual(self.restored[-1],self.context)
        self.assertIs(self.b._queue,queue);self.assertEqual(self.played,played);self.assertEqual(self.b.playerPosition,42)
        self.api.get_album.assert_called_once_with(self.ALBUM);self.api.get_artist.assert_called_once_with(self.ARTIST)

    def test_artist_album_back_preserves_artist_section_sort_and_catalog_actions(self):
        self.b.openLibraryItem('artist',self.ARTIST,'','Artist');self.ready()
        self.b.setArtistOrder('z_to_a');state=self.b._detail_state()
        self.navigate('detail','album');self.b.backDetail()
        self.assertEqual(self.b._detail_state(),state)
        self.assertTrue(self.b.detailCanArtistRadio);self.assertTrue(self.b.detailCanArtistShuffle)
        self.assertFalse(self.b.openTrackTarget('detail',0,'artist',self.ARTIST,self.context))

    def test_playlist_duplicates_bindings_and_navigation_history_are_untouched(self):
        self.b.loadPlaylistTracks('mine','Mine');self.ready();self.play('detail',1)
        state=self.b._detail_state();queue=self.b._queue;bindings=[x['_guiPlaylistBinding'] for x in queue.tracks]
        self.navigate('detail','album');self.navigate('detail','artist',self.ARTIST,context=self.opened[-1])
        self.b.backDetail();self.b.backDetail()
        self.assertEqual(self.b._detail_state(),state);self.assertTrue(self.b.detailCanEditPlaylist)
        self.assertEqual([x['_guiPlaylistBinding'] for x in queue.tracks],bindings)
        self.assertIs(self.b._queue,queue);self.assertEqual(self.b.playerSourceIndex,1)

    def test_queue_preserves_catalog_links_and_returns_to_real_queue(self):
        self.load();self.play();queue=self.b._queue;played=list(self.played)
        row=self.b.playingTracksModel.snapshot()[0]
        self.assertEqual(row['artistLinks'],[dict(id=self.ARTIST,name='Artist')]);self.assertEqual(row['albumId'],self.ALBUM)
        self.navigate('playing','artist',self.ARTIST,context=dict(self.context,page=5))
        self.assertEqual(self.opened[-1]['page'],1);self.b.backDetail()
        self.assertEqual(self.restored[-1]['page'],5);self.assertIs(self.b._queue,queue);self.assertEqual(self.played,played)

    def test_search_and_history_return_without_reloading_or_restarting(self):
        for source,page in (('search',0),('history',3)):
            with self.subTest(source=source):
                items=[self.b._track(self.rows[0])];self.b._source_model(source).set_items(items)
                context=dict(self.context,page=page,searchScope='catalog',searchMode='songs',searchText='Song')
                self.navigate(source,'album',context=context);self.b.backDetail()
                self.assertEqual(self.restored[-1],context);self.assertEqual(self.b._source_items(source),items)
        self.api.search.assert_not_called();self.api.get_history.assert_not_called()

    def test_liked_back_uses_completed_current_revision_with_original_sort(self):
        items=[self.b._track(self.rows[0])]
        self.b._liked_default_items=items;self.b._liked_model.set_items(items)
        self.b._liked_load_revision=1;self.b._liked_order='z_to_a'
        context=dict(self.context,page=2,likedOrder='z_to_a')
        self.navigate('liked','album',context=context)
        self.b._liked_default_items.append(dict(items[0],videoId='new',title='Zulu'))
        self.b.backDetail()
        self.assertEqual(self.b.likedModel.count,2);self.assertEqual(self.b.likedModel.snapshot()[0]['videoId'],'new')
        self.assertEqual(self.b._liked_order,'z_to_a');self.assertEqual(self.restored[-1]['page'],2)

    def test_multiple_artists_uses_selected_server_id_without_search(self):
        self.rows[0]['artists'].append(dict(name='Other',id=self.OTHER));self.api.get_library_songs.return_value=self.rows
        self.load();self.navigate('library','artist',self.OTHER)
        self.api.get_artist.assert_called_once_with(self.OTHER);self.api.search.assert_not_called()

    def test_album_header_fallback_keeps_track_specific_artist_and_queue_links(self):
        self.api.get_album.return_value['tracks']=[dict(self.rows[0],artists=None),
            dict(self.rows[0],videoId='other',artists=[dict(name='Other',id=self.OTHER)])]
        self.b.openLibraryItem('album',self.ALBUM,'','Album');self.ready()
        rows=self.b.detailTracksModel.snapshot()
        self.assertEqual(rows[0]['artistLinks'],[dict(id=self.ARTIST,name='Artist')])
        self.assertEqual(rows[1]['artistLinks'],[dict(id=self.OTHER,name='Other')])
        self.play('detail',1);self.assertEqual(self.b.playingTracksModel.snapshot()[1]['artistLinks'],rows[1]['artistLinks'])

    def test_full_artist_pointer_tracks_without_artist_ids_use_known_artist_context(self):
        self.api.get_artist.return_value['songs']={'browseId':'VLcatalog','results':[]}
        self.api.get_playlist.return_value={'tracks':[dict(self.rows[0],artists=None)]}
        self.b.openLibraryItem('artist',self.ARTIST,'','Artist');self.ready()
        self.assertEqual(self.b.detailTracksModel.snapshot()[0]['artistLinks'],[dict(id=self.ARTIST,name='Artist')])
        self.api.get_playlist.assert_called_once_with('VLcatalog',limit=None)

    def test_guards_reject_missing_ids_wrong_type_and_same_detail_target(self):
        self.load();self.b.libraryItemsModel.set_items([self.b._track(dict(self.rows[0],artists=[],album=None))])
        self.assertFalse(self.b.openTrackTarget('library',0,'album','',self.context))
        self.assertFalse(self.b.openTrackTarget('library',0,'artist',self.ARTIST,self.context))
        self.assertFalse(self.b.openTrackTarget('library',0,'unknown','',self.context))
        self.b.libraryItemsModel.set_items([dict(kind='upload_song',videoId='u',albumId=self.ALBUM,artistLinks=[dict(id=self.ARTIST,name='Artist')])])
        self.assertFalse(self.b.openTrackTarget('library',0,'album','',self.context))
        self.b.openLibraryItem('album',self.ALBUM,'','Album');self.ready()
        self.assertFalse(self.b.openTrackTarget('detail',0,'album','',self.context))
        self.api.get_album.reset_mock();self.b._busy=True
        self.assertFalse(self.b.openTrackTarget('detail',0,'artist',self.ARTIST,self.context));self.b._busy=False
        self.api.get_album.assert_not_called()

    def test_failed_catalog_endpoint_keeps_source_and_pending_history_clear(self):
        self.load();rows=self.b.libraryItemsModel.snapshot();self.api.get_album.side_effect=RuntimeError('offline')
        self.navigate('library','album')
        self.assertEqual(self.b.detailTitle,'');self.assertEqual(self.b.libraryItemsModel.snapshot(),rows)
        self.assertFalse(self.opened);self.assertIsNone(self.b._pending_detail_parent)
        self.assertEqual(self.b._library_section,'songs');self.assertEqual(len(self.errors),1)

    def test_artist_album_card_switches_library_section_and_back_restores_tab(self):
        self.api.get_artist.return_value['albums']={'results':[dict(title='Album',browseId=self.ALBUM)]}
        self.b.openLibraryItem('artist',self.ARTIST,'','Artist');self.ready()
        self.b.selectArtistSection('albums');state=self.b._detail_state()
        context=dict(self.context,librarySection='artists',libraryLabel='Interpreti')
        self.b.openDetailItem(0,context);self.ready()
        self.assertEqual(self.opened[-1]['librarySection'],'albums')
        self.b.backDetail();self.assertEqual(self.b._detail_state(),state)
        self.assertEqual(self.restored[-1]['librarySection'],'artists')
