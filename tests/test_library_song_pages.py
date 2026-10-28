"""The installed online library parser, separate endpoint and exact cursors."""
import unittest
from ytmusicapi import YTMusic
import test_upload_song_pages as fixtures
from test_paging import song
from felismusic_gui.paging import LibrarySongPages


class API(fixtures.API):
    get_library_songs=YTMusic.get_library_songs


class LibrarySongPageTests(unittest.TestCase):
    def test_online_endpoint_parser_order_duplicates_and_continuation_body(self):
        api=API([fixtures.initial(fixtures.shelf([{'mix':{}},song('A'),song('A')],'one')),
            {'continuationContents':{'musicShelfContinuation':fixtures.shelf([song('B')])}}])
        send=api._send_request;pager=LibrarySongPages(api,order='z_to_a')
        rows,more=pager.next_page();self.assertTrue(more);self.assertEqual([x['videoId'] for x in rows],['A','A'])
        self.assertEqual(api.calls[0][1]['browseId'],'FEmusic_liked_videos')
        self.assertIn('params',api.calls[0][1]);self.assertEqual(api._send_request,send)
        rows,more=pager.next_page();self.assertFalse(more);self.assertEqual(rows[0]['videoId'],'B')
        self.assertEqual(api.calls[1][1],api.calls[0][1]);self.assertIn('continuation=one',api.calls[1][2][0])
        self.assertEqual(pager.next_page(),([],False));self.assertEqual(len(api.calls),2)

    def test_empty_continuation_and_repeated_token_are_distinct(self):
        api=API([fixtures.initial(fixtures.shelf([{'mix':{}},song('A')],'one')),
            {'continuationContents':{'musicShelfContinuation':fixtures.shelf([],'two')}},
            {'continuationContents':{'musicShelfContinuation':fixtures.shelf([song('B')],'two')}}])
        pager=LibrarySongPages(api);pager.next_page();self.assertEqual(pager.next_page(),([],True))
        with self.assertRaises(RuntimeError):pager.next_page()

    def test_empty_library_finishes_and_malformed_response_does_not_silently_truncate(self):
        self.assertEqual(LibrarySongPages(API([fixtures.initial(fixtures.shelf([]))])).next_page(),([],False))
        pager=LibrarySongPages(API([fixtures.initial(fixtures.shelf([{'mix':{}},song('A')],'one')),{}]))
        pager.next_page()
        with self.assertRaises(Exception):pager.next_page()
