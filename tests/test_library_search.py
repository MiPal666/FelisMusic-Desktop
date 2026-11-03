"""Real ytmusicapi parser with the tab structure captured from Library search."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import Mock
from ytmusicapi.mixins.search import SearchMixin
from requests.exceptions import ReadTimeout
import test_prefetch as support
from felismusic_gui.search import search_music


def empty_sections():
    return {'sectionListRenderer': {'contents': [{'itemSectionRenderer': {
        'contents': [{'messageRenderer': {'text': {'runs': [{'text': 'No results'}]}}}]}}]}}


def tabs_response(content=None, selected=1):
    # Exact structural shape from the user's probe: only the selected tab has
    # contents; the other two are reload-only placeholders with continuations.
    tabs = [{'tabRenderer': {'selected': False, 'content': {'sectionListRenderer': {
        'continuations': [{'nextContinuationData': {'continuation': 'UNSELECTED'}}]}}}} for _ in range(3)]
    tabs[selected] = {'tabRenderer': {'selected': True, 'content': content or empty_sections()}}
    return {'contents': {'tabbedSearchResultsRenderer': {'tabs': tabs}}}


def artist_row(ident='UCartist', name='Artist'):
    return {'musicResponsiveListItemRenderer': {
        'navigationEndpoint': {'browseEndpoint': {'browseId': ident}},
        'flexColumns': [{'musicResponsiveListItemFlexColumnRenderer': {
            'text': {'runs': [{'text': name}]}}}]}}


class SearchResponseAPI(SearchMixin):
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def _send_request(self, *args, **kwargs):
        self.calls.append((deepcopy(args), deepcopy(kwargs)))
        return self.responses.pop(0)


class LibrarySearchParserTests(TestCase):
    def test_actual_empty_tab_shape_fails_upstream_but_is_empty_for_all_library_filters(self):
        for category in ('songs', 'albums', 'artists'):
            with self.subTest(category=category):
                response = tabs_response()
                with self.assertRaises(KeyError):
                    SearchResponseAPI(deepcopy(response)).search('query', scope='library', filter=category)
                api = SearchResponseAPI(response); before = deepcopy(response)
                original_send = api._send_request
                self.assertEqual(search_music(api, 'query', scope='library', filter=category), [])
                self.assertEqual(response, before)
                self.assertEqual(api._send_request, original_send)
                self.assertEqual(len(api.calls), 1)

    def test_selected_populated_tab_returns_library_rows_instead_of_catalog_rows(self):
        content = {'sectionListRenderer': {'contents': [{'musicShelfRenderer': {
            'contents': [artist_row()]}}]}}
        response = tabs_response(content)
        response['contents']['tabbedSearchResultsRenderer']['tabs'][0] = {
            'tabRenderer': {'selected': False, 'content': {'sectionListRenderer': {'contents': [
                {'musicShelfRenderer': {'contents': [artist_row('UCcatalog', 'Catalog')]}}]}}}}
        api = SearchResponseAPI(response)
        result = search_music(api, 'query', scope='library', filter='artists')
        self.assertEqual([row['browseId'] for row in result], ['UCartist'])

    def test_continuation_is_parsed_by_original_parser_with_same_request(self):
        content = {'sectionListRenderer': {'contents': [{'musicShelfRenderer': {
            'contents': [artist_row()], 'continuations': [
                {'nextContinuationData': {'continuation': 'NEXT'}}]}}]}}
        api = SearchResponseAPI(tabs_response(content), {'continuationContents': {
            'musicShelfContinuation': {'contents': [artist_row('UCsecond', 'Second')]}}})
        result = search_music(api, 'query', scope='library', filter='artists', limit=2)
        self.assertEqual([row['browseId'] for row in result], ['UCartist', 'UCsecond'])
        self.assertEqual(len(api.calls), 2)
        self.assertEqual(api.calls[0][0][:2], api.calls[1][0][:2])
        self.assertIn('NEXT', api.calls[1][0][2])

    def test_already_first_selected_tab_and_legacy_single_tab_still_work(self):
        for response in (tabs_response(selected=0), {'contents': empty_sections()}):
            api = SearchResponseAPI(response)
            self.assertEqual(search_music(api, 'query', scope='library', filter='songs'), [])

    def test_other_scopes_and_unfiltered_search_use_unchanged_public_call(self):
        for kwargs in ({'scope': 'uploads'}, {'filter': 'songs'}, {'scope': 'library'}):
            api = Mock(); api.search.return_value = [{'videoId': 'song'}]
            self.assertEqual(search_music(api, 'query', **kwargs), [{'videoId': 'song'}])
            api.search.assert_called_once_with('query', **kwargs)
            api._send_request.assert_not_called()

    def test_malformed_ambiguous_and_network_errors_are_not_empty_success(self):
        malformed = tabs_response(); malformed['contents']['tabbedSearchResultsRenderer']['tabs'][1]['tabRenderer']['content'] = {}
        ambiguous = tabs_response(); ambiguous['contents']['tabbedSearchResultsRenderer']['tabs'][0]['tabRenderer']['selected'] = True
        for response, error_type in ((malformed, KeyError), (ambiguous, ValueError)):
            with self.subTest(error=error_type.__name__):
                with self.assertRaises(error_type):
                    search_music(SearchResponseAPI(response), 'query', scope='library', filter='songs')
        api = Mock(); api.search.side_effect = ReadTimeout('network error')
        with self.assertRaises(ReadTimeout):
            search_music(api, 'query', scope='library', filter='songs')


class LibrarySearchBackendTests(support.AudioPlaybackTestCase):
    def test_empty_result_clears_previous_rows_without_dialog_or_audio_changes(self):
        self.start('A', 'B'); queue = self.b._queue; current = queue.current()
        self.b._player_position = 42; played = list(self.played); stops = list(self.stops)
        for category in ('songs', 'albums', 'artists'):
            with self.subTest(category=category):
                self.b._search_results_model.set_items([dict(kind='song', videoId='old', title='Old')])
                self.b._ytmusic = SearchResponseAPI(tabs_response())
                self.b.search('query', category, 'library'); self.until(lambda: not self.b.busy)
                self.assertEqual(self.b.searchResultsModel.count, 0)
                self.assertFalse(self.errors)
                self.assertIs(self.b._queue, queue); self.assertIs(queue.current(), current)
                self.assertEqual(self.played, played); self.assertEqual(self.stops, stops)
                self.assertEqual(self.b.playerPosition, 42)
