"""Profiles filter identity, continuation boundaries, detail navigation and errors."""
from copy import deepcopy
from threading import Event
from unittest import TestCase
from unittest.mock import Mock, patch

import test_prefetch as support
from felismusic_gui import profiles


def page(rows=None, header=None):
    return {'contents': {'singleColumnBrowseResultsRenderer': {'tabs': [
        {'tabRenderer': {'selected': True, 'content': {'sectionListRenderer': {
            'contents': rows or [], 'header': header or {}}}}},
        {'tabRenderer': {'content': {'sectionListRenderer': {'contents': []}}}}
    ]}}}


def profile_row(name, ident, kind='MUSIC_PAGE_TYPE_USER_CHANNEL'):
    return {'musicResponsiveListItemRenderer': {
        'navigationEndpoint': {'browseEndpoint': {'browseId': ident,
            'browseEndpointContextSupportedConfigs': {'browseEndpointContextMusicConfig': {'pageType': kind}}}},
        'flexColumns': [{'musicResponsiveListItemFlexColumnRenderer': {
            'text': {'runs': [{'text': text}]}}} for text in (name, '@handle')]}}


def landing():
    return page(header={'chipCloudRenderer': {'chips': [{'chipCloudChipRenderer': {
        'text': {'runs': [{'text': 'Libovolný jazyk'}]},
        'navigationEndpoint': {'commandExecutorCommand': {'commands': [
            {'browseEndpoint': {'browseId': profiles.PROFILE_FILTER, 'params': 'SERVER_PARAMS'}},
            {'musicLibraryPersistLaunchNavigationCommand': {'command': {
                'browseEndpoint': {'browseId': 'WRONG', 'params': 'NOT_FOR_REQUEST'}}}}]}}
    }}]}})


class ProfilesParserTests(TestCase):
    def test_issued_profiles_filter_exact_params_and_continuation(self):
        api = Mock()
        api._send_request.side_effect = [landing(),
            page([{'musicShelfRenderer': {'contents': [profile_row('Napalm', 'UC1')],
                'continuations': [{'nextContinuationData': {'continuation': 'NEXT'}}]}}]),
            {'continuationContents': {'musicShelfContinuation': {'contents': [
                profile_row('Napalm', 'UC1'), profile_row('Rock', 'UC2')]}}}]
        self.assertEqual([x['artist'] for x in profiles.load_library_profiles(api)], ['Napalm', 'Rock'])
        self.assertEqual([x.args for x in api._send_request.call_args_list], [
            ('browse', {'browseId': 'FEmusic_library_landing'}),
            ('browse', {'browseId': profiles.PROFILE_FILTER, 'params': 'SERVER_PARAMS'}),
            ('browse', {'continuation': 'NEXT'})])
        api.get_library_channels.assert_not_called()

    def test_missing_filter_or_contents_do_not_become_empty_success(self):
        for responses in ([page()], [landing(), {}]):
            api = Mock(); api._send_request.side_effect = responses
            with self.assertRaises(ValueError):
                profiles.load_library_profiles(api)

    def test_explicit_empty_profiles_message_is_valid(self):
        api = Mock(); api._send_request.side_effect = [landing(), page([{'messageRenderer': {'text': {'runs': [{'text': 'Empty'}]}}}])]
        self.assertEqual(profiles.load_library_profiles(api), [])

    def test_artist_rows_are_never_mislabeled_as_profiles(self):
        api = Mock(); api._send_request.side_effect = [landing(), page([{'musicShelfRenderer': {'contents': [
            profile_row('Artist', 'UCa', 'MUSIC_PAGE_TYPE_ARTIST')]}}])]
        with self.assertRaises(ValueError): profiles.load_library_profiles(api)

    def test_repeated_continuation_fails_instead_of_looping(self):
        api = Mock()
        block = {'contents': [profile_row('Napalm', 'UC1')], 'continuations': [
            {'nextContinuationData': {'continuation': 'LOOP'}}]}
        api._send_request.side_effect = [landing(), page([{'musicShelfRenderer': block}]),
                                       {'continuationContents': {'musicShelfContinuation': block}}]
        with self.assertRaises(ValueError): profiles.load_library_profiles(api)
        self.assertEqual(api._send_request.call_count, 3)

    def test_profile_header_and_not_podcast_channel(self):
        api = Mock()
        response = page(); response['header'] = {'musicVisualHeaderRenderer': {'title': {'runs': [{'text': 'Napalm'}]}}}
        api._send_request.return_value = response
        api.parser.parse_channel_contents.return_value = {'videos': {'results': []}, 'playlists': {'results': []}}
        self.assertEqual(profiles.load_profile(api, 'UC1')['name'], 'Napalm')
        api.get_channel.assert_not_called()
        response['header'] = {'musicImmersiveHeaderRenderer': {'title': {'runs': [{'text': 'Artist'}]}}}
        with self.assertRaises(ValueError): profiles.load_profile(api, 'UC1')

    def test_profile_page_preserves_params_and_consumes_one_page(self):
        api = Mock()
        grid = {'items': [], 'continuations': [{'nextContinuationData': {'continuation': 'N'}}]}
        api._send_request.side_effect = [page([{'gridRenderer': grid}]),
            {'continuationContents': {'gridContinuation': {'items': []}}}]
        items, state = profiles.load_profile_page(api, 'UC1', 'videos', {'params': 'V'})
        self.assertFalse(state['complete'])
        _, state = profiles.load_profile_page(api, 'UC1', 'videos', state)
        self.assertTrue(state['complete'])
        self.assertEqual(api._send_request.call_args_list[0].args[1], {'browseId': 'UC1', 'params': 'V'})
        self.assertEqual(api._send_request.call_args_list[1].args[1], {'continuation': 'N'})

    def test_unknown_profile_renderers_are_errors_not_empty_lists(self):
        api = Mock()
        api._send_request.side_effect = [landing(), page([{'musicShelfRenderer': {
            'contents': [{'newUnknownRenderer': {}}]}}])]
        with self.assertRaises(ValueError): profiles.load_library_profiles(api)
        api._send_request.side_effect = None
        api._send_request.return_value = page([{'gridRenderer': {'items': [{'newUnknownRenderer': {}}]}}])
        with self.assertRaises(ValueError): profiles.load_profile_page(api, 'UC1', 'videos', {'params': 'V'})


class ProfilesBackendTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock()
        self.b._ytmusic = self.api
        self.data = {'name': 'Profile',
            'videos': {'results': [{'title': 'Video A', 'videoId': 'A', 'duration': '3:00'}]},
            'playlists': {'results': [{'title': 'Collection', 'playlistId': 'PLtest'}]}}

    def open_profile(self, data=None):
        with patch.object(support.backend, 'load_profile', return_value=deepcopy(data or self.data)):
            self.b.openLibraryItem('profile', 'UCprofile', '', 'Profile')
            self.until(lambda: not self.b.busy)

    def test_library_profiles_sorted_without_podcast_endpoint(self):
        with patch.object(support.backend, 'load_library_profiles', return_value=[
            {'artist': 'Rock', 'browseId': 'UC2'}, {'artist': 'Napalm', 'browseId': 'UC1'}]):
            self.b.loadLibrarySection('channels', 'a_to_z')
            self.until(lambda: not self.b.busy)
        self.assertEqual([r['title'] for r in self.b.libraryItemsModel.snapshot()], ['Napalm', 'Rock'])
        self.assertTrue(all(r['kind'] == 'profile' for r in self.b.libraryItemsModel.snapshot()))
        self.api.get_library_channels.assert_not_called()

    def test_profile_tabs_playlist_back_and_playback_are_independent(self):
        self.start('OLD', 'NEXT'); queue = self.b._queue; stops = len(self.stops)
        self.open_profile()
        self.assertEqual(self.b.detailTracksModel.snapshot()[0]['videoId'], 'A')
        self.b.selectProfileSection('playlists')
        self.assertEqual(self.b.detailTracksModel.snapshot()[0]['playlistId'], 'PLtest')
        self.api.get_playlist.return_value = {'title': 'Collection', 'tracks': [{'title': 'Song', 'videoId': 'P'}]}
        self.b.openDetailItem(0, {'page': 1, 'librarySection': 'channels', 'libraryLabel': 'Profily'})
        self.until(lambda: not self.b.busy)
        self.assertEqual(self.b.detailMeta['kind'], 'playlist')
        self.b.backDetail()
        self.assertEqual(self.b.detailMeta['kind'], 'profile')
        self.assertEqual(self.b.detailMeta['section'], 'playlists')
        self.assertIs(self.b._queue, queue); self.assertEqual(len(self.stops), stops)
        self.b.selectProfileSection('videos'); self.b.playFrom('detail', 0)
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerTitle, 'Video A')
        self.assertFalse(self.errors)

    def test_page_append_and_failure_preserve_loaded_rows_and_audio(self):
        data = deepcopy(self.data); data['videos']['params'] = 'FIRST'
        with patch.object(support.backend, 'load_profile_page', return_value=(
                [{'title': 'First', 'videoId': 'A'}], {'started': True, 'complete': False, 'token': 'N'})):
            self.open_profile(data)
        with patch.object(support.backend, 'load_profile_page', side_effect=KeyError('PRIVATE_RESPONSE_BODY')):
            self.b.loadMoreProfile(); self.until(lambda: not self.b.busy)
        self.assertEqual(len(self.errors), 1); self.assertNotIn('PRIVATE_RESPONSE_BODY', self.errors[0])
        self.assertEqual(self.b.detailTracksModel.snapshot()[0]['videoId'], 'A')
        with patch.object(support.backend, 'load_profile_page', return_value=(
                [{'title': 'Again', 'videoId': 'A'}, {'title': 'Second', 'videoId': 'B'}],
                {'started': True, 'complete': True})):
            self.b.loadMoreProfile(); self.until(lambda: not self.b.busy)
        self.assertEqual([x['videoId'] for x in self.b.detailTracksModel.snapshot()], ['A', 'B'])

    def test_profile_read_errors_are_short_and_search_profiles_use_same_loader(self):
        with patch.object(support.backend, 'load_library_profiles', side_effect=KeyError('PRIVATE_BODY'*200)):
            self.b.loadLibrarySection('channels', 'recently_added'); self.until(lambda: not self.b.busy)
        self.assertLess(len(self.errors[-1]), 100)
        self.b._search_results_model.set_items([dict(kind='profile', browseId='UCprofile', title='Profile')])
        with patch.object(support.backend, 'load_profile', return_value=deepcopy(self.data)) as load:
            self.b.openSearchResult(0); self.until(lambda: not self.b.busy)
            load.assert_called_once_with(self.api, 'UCprofile')
        self.assertEqual(self.b.detailMeta['kind'], 'profile')

    def test_leaving_during_profile_read_does_not_restore_late_detail(self):
        entered, release = Event(), Event()
        def blocked(*args):
            entered.set()
            if not release.wait(3):
                raise AssertionError('test did not release profile read')
            return deepcopy(self.data)
        with patch.object(support.backend, 'load_profile', side_effect=blocked):
            try:
                self.b.openLibraryItem('profile', 'UCprofile', '', 'Profile')
                self.assertTrue(entered.wait(2))
                self.b.clearDetail()
            finally:
                release.set()
            self.until(lambda: not self.b.busy)
        self.assertEqual(self.b.detailTitle, '')
        self.assertEqual(self.b.detailTracksModel.count, 0)
        self.assertFalse(self.errors)
