"""Raw upload row menu links survive the public album parser, no extra request."""
from copy import deepcopy
import unittest
import test_prefetch as support
from felismusic_gui.uploads import load_upload_album

ARTIST = 'FEmusic_library_privately_owned_artist_detaila_po_a'
OTHER = 'FEmusic_library_privately_owned_artist_detaila_po_b'


def row(vid='song', ids=(ARTIST,)):
    items = [dict(menuServiceItemRenderer=dict(serviceEndpoint=dict(queueAddEndpoint=dict(queueTarget=dict(videoId=vid)))))]
    items += [dict(menuNavigationItemRenderer=dict(navigationEndpoint=dict(browseEndpoint=dict(browseId=x)))) for x in ids]
    return dict(musicResponsiveListItemRenderer=dict(menu=dict(menuRenderer=dict(items=items))))


class FakeAPI:
    def __init__(self, response, tracks):
        self.response, self.tracks, self.calls = response, tracks, []

    def _send_request(self, endpoint, body):
        self.calls.append((endpoint, dict(body)))
        return deepcopy(self.response)

    def get_library_upload_album(self, browse_id):
        self._send_request('browse', dict(browseId=browse_id))
        return dict(tracks=deepcopy(self.tracks))


class UploadAlbumLinkTests(unittest.TestCase):
    def test_reads_menu_ids_from_same_request_and_leaves_shared_client_untouched(self):
        api = FakeAPI(dict(contents=[row()]), [dict(videoId='song', artists=None)])
        send = api._send_request
        data = load_upload_album(api, 'album')
        self.assertEqual(data['tracks'][0]['artistLinks'], [dict(id=ARTIST, name='Interpret')])
        self.assertEqual(api.calls, [('browse', dict(browseId='album'))])
        self.assertEqual(api._send_request, send)
        self.assertNotIn('artistLinks', api.tracks[0])

    def test_preserves_row_artist_and_filters_unknown_and_catalog_links(self):
        api = FakeAPI([row(ids=(OTHER,)), row('second', ('UCcatalog', ARTIST, ARTIST))],
                      [dict(videoId='song', artists=[dict(id=ARTIST, name='Original')]), dict(videoId='second', artists=None)])
        data = load_upload_album(api, 'album')
        self.assertNotIn('artistLinks', data['tracks'][0])
        self.assertEqual(data['tracks'][1]['artistLinks'], [dict(id=ARTIST, name='Interpret')])

    def test_multiple_artists_and_unmatched_rows(self):
        api = FakeAPI([row(ids=(ARTIST, OTHER))], [dict(videoId='song', artists=None), dict(videoId='missing', artists=None)])
        data = load_upload_album(api, 'album')
        self.assertEqual([x['id'] for x in data['tracks'][0]['artistLinks']], [ARTIST, OTHER])
        self.assertNotIn('artistLinks', data['tracks'][1])

    def test_request_failure_does_not_change_shared_method(self):
        class FailingAPI(FakeAPI):
            def _send_request(self, *args):
                raise RuntimeError('offline')
        api = FailingAPI({}, []); send = api._send_request
        with self.assertRaises(RuntimeError):
            load_upload_album(api, 'album')
        self.assertEqual(api._send_request, send)
