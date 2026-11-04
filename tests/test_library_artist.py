"""Library artist songs are a separate exact-ID source from the catalog."""
from copy import deepcopy
from unittest.mock import Mock
import unittest
import test_prefetch as support
import test_upload_song_pages as fixtures
from test_paging import song
from felismusic_gui.paging import LibraryArtistSongPages


class LibraryArtistParserTests(unittest.TestCase):
    def test_exact_endpoint_duplicates_and_continuations(self):
        api = fixtures.API([fixtures.initial(fixtures.shelf([song('A'),song('A')], 'one')),
            {'continuationContents': {'musicShelfContinuation': fixtures.shelf([], 'two')}},
            {'continuationContents': {'musicShelfContinuation': fixtures.shelf([song('B')])}}])
        pager = LibraryArtistSongPages(api, 'MPLAUCactual')
        rows,more=pager.next_page();self.assertTrue(more)
        self.assertEqual([x['videoId'] for x in rows],['A','A'])
        self.assertEqual(pager.next_page(),([],True))
        rows,more=pager.next_page();self.assertFalse(more);self.assertEqual(rows[0]['videoId'],'B')
        self.assertEqual(pager.next_page(),([],False))
        self.assertEqual([x[1] for x in api.calls],[{'browseId':'MPLAUCactual'}]*3)
        self.assertIn('continuation=one',api.calls[1][2][0])

    def test_empty_malformed_repeat_and_invalid_id(self):
        self.assertEqual(LibraryArtistSongPages(fixtures.API([fixtures.initial(fixtures.shelf([]))]),'MPLAUCx').next_page(),([],False))
        with self.assertRaises(ValueError):LibraryArtistSongPages(Mock(),'UCx')
        with self.assertRaises(Exception):LibraryArtistSongPages(fixtures.API([{}]),'MPLAUCx').next_page()
        pager=LibraryArtistSongPages(fixtures.API([fixtures.initial(fixtures.shelf([song('A')],'one')),
            {'continuationContents':{'musicShelfContinuation':fixtures.shelf([song('B')],'one')}}]),'MPLAUCx')
        pager.next_page()
        with self.assertRaisesRegex(RuntimeError,'repeated_library_artist'):pager.next_page()


class LibraryArtistTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp();self.api=Mock();self.b._ytmusic=self.api
        self.catalog=[dict(videoId='C',title='Catalog'),dict(videoId='A',title='Alpha')]
        self.api.get_artist.return_value=dict(name='Artist',songs={'results':[], 'browseId':'VLsongs'},
            albums={'results':[dict(title='Album',browseId='MPREalbum')]},singles={'results':[]},radioId='RDradio')
        self.api.get_playlist.return_value={'tracks':deepcopy(self.catalog)}
        self.api._send_request.return_value=fixtures.initial(fixtures.shelf([song('L'),song('L')]))
    def open(self,bid='MPLAUCartist'):
        self.b.openLibraryItem('artist',bid,'','Artist');self.until(lambda:not self.b.busy)
    def ids(self):return [x['videoId'] for x in self.b.detailTracksModel.snapshot()]

    def test_library_default_catalog_switch_and_sort_without_network(self):
        self.open();self.assertEqual(self.ids(),['L','L']);self.assertEqual(self.b.detailMeta['songScope'],'library')
        self.api._send_request.assert_called_once_with('browse',{'browseId':'MPLAUCartist'})
        self.b.selectArtistSongScope('all');self.assertEqual(self.ids(),['C','A'])
        self.b.setArtistOrder('z_to_a');self.assertEqual(self.ids(),['C','A'])
        self.b.selectArtistSongScope('library');self.assertEqual(self.ids(),['L','L'])
        self.b.selectArtistSongScope('all');self.assertEqual(self.ids(),['C','A'])
        self.api.get_playlist.assert_called_once_with('VLsongs',limit=None)
        self.api._send_request.assert_called_once()

    def test_albums_back_scope_and_audio_queue_unchanged(self):
        self.open();self.b.playFrom('detail',1);self.until(lambda:self.b.playerState=='playing')
        queue=self.b._queue;played=list(self.played)
        self.b.selectArtistSongScope('all');self.b.selectArtistSection('albums')
        self.api.get_album.return_value=dict(title='Album',tracks=[])
        self.b.openDetailItem(0);self.until(lambda:not self.b.busy);self.b.backDetail()
        self.assertEqual(self.b.detailMeta['section'],'albums');self.assertEqual(self.b.detailMeta['songScope'],'all')
        self.b.selectArtistSongScope('library');self.assertEqual(self.ids(),['L','L'])
        self.assertIs(self.b._queue,queue);self.assertEqual(self.played,played)

    def test_normal_catalog_has_no_library_scope(self):
        self.open('UCartist');self.assertEqual(self.ids(),['C','A'])
        self.assertNotIn('songScopes',self.b.detailMeta);self.api._send_request.assert_not_called()
        state=self.b._detail_state();self.b.selectArtistSongScope('library');self.assertEqual(self.b._detail_state(),state)

    def test_library_failure_preserves_previous_detail(self):
        self.open('UCartist');state=self.b._detail_state()
        self.api._send_request.side_effect=RuntimeError('unavailable')
        self.open();self.assertEqual(self.b._detail_state(),state)

    def test_empty_library_retains_catalog_shuffle_and_mix(self):
        self.api._send_request.return_value=fixtures.initial(fixtures.shelf([]));self.open()
        self.assertEqual(self.ids(),[]);self.assertTrue(self.b.detailCanArtistShuffle);self.assertTrue(self.b.detailCanArtistRadio)
        self.assertTrue(self.b.startArtistPlayback('shuffle'));self.until(lambda:not self.b.busy)
        self.until(lambda:self.b.playerState=='playing')
        self.assertCountEqual([x['videoId'] for x in self.b._queue.tracks],['A','C'])
