"""Exercise the installed artist parser and desktop paths without network."""
from copy import deepcopy
from gettext import NullTranslations
from unittest import TestCase
from unittest.mock import Mock, patch

import test_prefetch as support
from test_paging import song
from ytmusicapi import YTMusic
from ytmusicapi.parsers.i18n import Parser
from felismusic_gui import artist_compat


def response(*, untitled=True, songs=True, subscribed=False):
    sections = []
    if songs:
        sections.append({'musicShelfRenderer': {
            'title': {'runs': [{'text': 'Songs'}]}, 'contents': [song('track')]}})
    if untitled:
        sections.append({'musicCarouselShelfRenderer': {
            'contents': [], 'opaque': 'PRIVATE_VALUE'}})
    sections.append({'musicCarouselShelfRenderer': {
        'header': {'musicCarouselShelfBasicHeaderRenderer': {'title': {'runs': [{
            'text': 'Albums', 'navigationEndpoint': {'browseEndpoint': {
                'browseId': 'UCalbums', 'params': 'albumsParam'}}}]}}}, 'contents': []}})
    return {'header': {'musicImmersiveHeaderRenderer': {
        'title': {'runs': [{'text': 'Artist'}]},
        'subscriptionButton': {'subscribeButtonRenderer': {
            'channelId': 'UCsubscription', 'subscribed': subscribed}},
        'playButton': {'buttonRenderer': {'navigationEndpoint': {
            'watchEndpoint': {'playlistId': 'RDshuffle'}}}},
        'startRadioButton': {'buttonRenderer': {'navigationEndpoint': {
            'watchEndpoint': {'playlistId': 'RDradio'}}}}}},
        'contents': {'singleColumnBrowseResultsRenderer': {'tabs': [{'tabRenderer': {
            'content': {'sectionListRenderer': {'contents': sections}}}}]}}}


def api_for(data):
    api = YTMusic.__new__(YTMusic)
    api.parser = Parser(NullTranslations())
    api._send_request = Mock(side_effect=lambda *a, **k: deepcopy(data))
    return api


class ArtistCompatibilityTests(TestCase):
    def test_missing_header_no_longer_discards_songs_albums_or_controls(self):
        data = response(); original = deepcopy(data); api = api_for(data)
        parser = api.parser; parse = parser.parse_channel_contents
        with self.assertRaises(KeyError):
            api.get_artist('UCtest')
        api._send_request.reset_mock()
        fixed = artist_compat.get_artist(api, 'UCtest')
        self.assertEqual(fixed['songs']['results'][0]['videoId'], 'track')
        self.assertEqual(fixed['albums']['browseId'], 'UCalbums')
        self.assertEqual(fixed['albums']['params'], 'albumsParam')
        self.assertEqual((fixed['radioId'], fixed['shuffleId']), ('RDradio', 'RDshuffle'))
        self.assertEqual((fixed['channelId'], fixed['subscribed']), ('UCsubscription', False))
        api._send_request.assert_called_once_with('browse', {'browseId': 'UCtest'})
        self.assertEqual(data, original)
        self.assertIs(api.parser, parser)
        self.assertEqual(api.parser.parse_channel_contents, parse)
        with self.assertRaises(KeyError):
            api.get_artist('UCtest')

    def test_regular_page_is_unchanged(self):
        api = api_for(response(untitled=False))
        self.assertEqual(artist_compat.get_artist(api, 'UCtest'), api.get_artist('UCtest'))

    def test_missing_songs_preserves_albums(self):
        fixed = artist_compat.get_artist(api_for(response(songs=False)), 'UCtest')
        self.assertEqual(fixed['songs'], {'browseId': None})
        self.assertEqual(fixed['albums']['browseId'], 'UCalbums')

    def test_other_parser_errors_propagate(self):
        data = response()
        sections = data['contents']['singleColumnBrowseResultsRenderer']['tabs'][0]['tabRenderer']['content']['sectionListRenderer']['contents']
        sections[-1]['musicCarouselShelfRenderer']['header'] = {}
        with self.assertRaises(KeyError):
            artist_compat.get_artist(api_for(data), 'UCtest')

    def test_debug_records_only_skipped_count(self):
        trace = Mock()
        with patch.object(artist_compat, 'current_trace', return_value=trace):
            artist_compat.get_artist(api_for(response()), 'UCtest')
        trace.event.assert_called_once_with('artist.untitled_carousels', count=1)


class ArtistCompatibilityDesktopTests(support.AudioPlaybackTestCase):
    def test_empty_songs_detail_still_opens_albums_and_subscription_works(self):
        data = response(songs=False)
        api = api_for(data); self.b._ytmusic = api; self.b._set_connected(True)
        api.get_artist_albums = Mock(return_value=[{'title': 'Album', 'browseId': 'album'}])
        api.get_library_artists = Mock(return_value=[])
        def subscribe(channel):
            data['header']['musicImmersiveHeaderRenderer']['subscriptionButton']['subscribeButtonRenderer']['subscribed'] = True
            return {'status': 'STATUS_SUCCEEDED'}
        api.subscribe_artist = Mock(side_effect=subscribe)
        self.b.openLibraryItem('artist', 'UCtest', '', 'Artist')
        self.until(lambda: not self.b.busy)
        self.assertEqual(self.b.detailTitle, 'Artist')
        self.assertEqual(self.b.detailTracksModel.count, 0)
        self.assertTrue(self.b.detailCanArtistSubscription)
        self.b.selectArtistSection('albums'); self.until(lambda: not self.b.busy)
        self.assertEqual(self.b.detailTracksModel.snapshot()[0]['browseId'], 'album')
        self.assertTrue(self.b.changeArtistSubscription()); self.until(lambda: not self.b.busy)
        self.assertTrue(self.b.detailMeta['artistSubscription']['subscribed'])
        api.subscribe_artist.assert_called_once_with('UCsubscription')
        self.assertEqual(api._send_request.call_count, 3)  # detail, preflight, verification
        self.assertFalse(self.errors)
