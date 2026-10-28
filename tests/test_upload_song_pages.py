"""Real installed ytmusicapi upload parser and continuation request shape."""
from copy import deepcopy
import unittest
import test_prefetch as support
from ytmusicapi import YTMusic
from felismusic_gui.paging import UploadSongPages


def row(video='A'):
    artist='FEmusic_library_privately_owned_artist_detaila_po_artist'
    album='FEmusic_library_privately_owned_release_detailb_po_album'
    def column(text,bid=None):
        run={'text':text}
        if bid:run['navigationEndpoint']={'browseEndpoint':{'browseId':bid}}
        return {'musicResponsiveListItemFlexColumnRenderer':{'text':{'runs':[run]}}}
    delete={'confirmDialogEndpoint':{'content':{'confirmDialogRenderer':{'confirmButton':{'buttonRenderer':{'command':{
        'musicDeletePrivatelyOwnedEntityCommand':{'entityId':'entity-'+video}}}}}}}}
    return {'musicResponsiveListItemRenderer':{'flexColumns':[column('Song '+video),column('Artist',artist),column('Album',album)],
        'menu':{'menuRenderer':{'items':[
            {'menuServiceItemRenderer':{'serviceEndpoint':{'queueAddEndpoint':{'queueTarget':{'videoId':video}}}}},
            {'menuNavigationItemRenderer':{'navigationEndpoint':delete}}],
            'topLevelButtons':[{'likeButtonRenderer':{'likeStatus':'LIKE'}}]}}}}


def shelf(rows,token=None):
    result={'contents':rows}
    if token:result['continuations']=[{'nextContinuationData':{'continuation':token}}]
    return result


def initial(content):
    return {'contents':{'singleColumnBrowseResultsRenderer':{'tabs':[{'tabRenderer':{'content':{'sectionListRenderer':{
        'contents':[{'musicShelfRenderer':content}]}}}}]}}}


class API:
    get_library_upload_songs=YTMusic.get_library_upload_songs
    def __init__(self,responses):self.responses=responses;self.calls=[]
    def _check_auth(self):pass
    def _send_request(self,endpoint,body,*args):
        self.calls.append((endpoint,deepcopy(body),args));return deepcopy(self.responses[len(self.calls)-1])


class UploadSongPageParserTests(unittest.TestCase):
    def test_first_parser_keeps_duplicates_order_ids_and_continuations_reuse_body(self):
        api=API([initial(shelf([{'mix':{}},row(),row()],'next')),{'continuationContents':{'musicShelfContinuation':shelf([row('B')])}}])
        send=api._send_request;pager=UploadSongPages(api,order='a_to_z')
        tracks,more=pager.next_page()
        self.assertTrue(more);self.assertEqual([x['videoId'] for x in tracks],['A','A'])
        self.assertTrue(tracks[0]['artists'][0]['id'].startswith('FEmusic_library_privately_owned_artist'))
        self.assertEqual(len(api.calls),1);self.assertEqual(api._send_request,send)
        tracks,more=pager.next_page();self.assertFalse(more);self.assertEqual(tracks[0]['videoId'],'B')
        self.assertEqual(api.calls[1][0],'browse');self.assertEqual(api.calls[0][1],api.calls[1][1])
        self.assertIn('continuation=next',api.calls[1][2][0])
        self.assertEqual(pager.next_page(),([],False));self.assertEqual(len(api.calls),2)

    def test_repeated_cursor_fails_without_exposing_replayed_rows(self):
        api=API([initial(shelf([{'mix':{}},row()],'same')),{'continuationContents':{'musicShelfContinuation':shelf([row('B')],'same')}}])
        pager=UploadSongPages(api);pager.next_page()
        with self.assertRaisesRegex(RuntimeError,'repeated_upload_continuation'):pager.next_page()

    def test_empty_page_with_new_cursor_is_not_mistaken_for_end(self):
        api=API([initial(shelf([{'mix':{}},row()],'one')),{'continuationContents':{'musicShelfContinuation':shelf([],'two')}},
            {'continuationContents':{'musicShelfContinuation':shelf([row('B')])}}])
        pager=UploadSongPages(api);pager.next_page();self.assertEqual(pager.next_page(),([],True))
        tracks,more=pager.next_page();self.assertEqual(tracks[0]['videoId'],'B');self.assertFalse(more)

    def test_single_empty_library_completes_and_malformed_continuation_is_error(self):
        pager=UploadSongPages(API([initial(shelf([]))]));self.assertEqual(pager.next_page(),([],False))
        pager=UploadSongPages(API([initial(shelf([{'mix':{}},row()],'one')),{'bad':{}}]));pager.next_page()
        with self.assertRaises(Exception):pager.next_page()
