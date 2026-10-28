"""Page adapter checks using installed ytmusicapi continuation/song parsers."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import Mock, patch
from ytmusicapi import YTMusic
import test_prefetch  # desktop import path
from felismusic_gui.paging import PlaylistPages
from ytmusicapi.parsers.playlists import parse_playlist_items


def token(value):
    return {'continuationItemRenderer': {'continuationEndpoint': {'continuationCommand': {'token': value}}}}


def song(vid):
    return {'musicResponsiveListItemRenderer': {
        'flexColumns': [{'musicResponsiveListItemFlexColumnRenderer': {'text': {'runs': [
            {'text': vid, 'navigationEndpoint': {'watchEndpoint': {'videoId': vid}}}]}}}],
        'overlay': {'musicItemThumbnailOverlayRenderer': {'content': {'musicPlayButtonRenderer': {
            'playNavigationEndpoint': {'watchEndpoint': {'videoId': vid}}}}}}}}


def initial(contents):
    return {'contents': {'twoColumnBrowseResultsRenderer': {'secondaryContents': {
        'sectionListRenderer': {'contents': [{'musicPlaylistShelfRenderer': {'contents': contents}}]}}}}}


def continuation(contents):
    return {'onResponseReceivedActions': [{'appendContinuationItemsAction': {'continuationItems': contents}}]}


class Client:
    def __init__(self, responses):
        self._send_request = Mock(side_effect=deepcopy(responses))
        self._check_auth = Mock()
        self.session = object()
        self.calls = []

    def get_playlist(self, pid, limit):
        self.calls.append((pid, limit, self.session))
        response = self._send_request('browse', {'browseId': 'VL' + pid}, '')
        contents = response['contents']['twoColumnBrowseResultsRenderer']['secondaryContents']['sectionListRenderer']['contents'][0]['musicPlaylistShelfRenderer']['contents']
        return {'tracks': parse_playlist_items(contents)}


class PlaylistPagesTests(TestCase):
    def test_exact_cursors_one_request_per_page_and_shared_client_unchanged(self):
        api = Client([initial([song('A'), token('one')]),
                      continuation([song('B'), token('two')]), continuation([song('A')])])
        request = api._send_request
        pages = PlaylistPages(api, 'LM', liked=True)
        self.assertEqual(pages.next_page()[1], True)
        self.assertEqual(api.calls, [('LM', 0, api.session)])
        self.assertIs(api._send_request, request)
        self.assertEqual(api._send_request.call_count, 1)
        tracks, more = pages.next_page()
        self.assertEqual([x['videoId'] for x in tracks], ['B']); self.assertTrue(more)
        tracks, more = pages.next_page()
        self.assertEqual([x['videoId'] for x in tracks], ['A']); self.assertFalse(more)
        self.assertEqual(pages.next_page(), ([], False))
        self.assertEqual(api._send_request.call_count, 3)
        self.assertEqual(api._send_request.call_args_list[1].args, ('browse', {'continuation': 'one'}))
        self.assertEqual(api._send_request.call_args_list[2].args, ('browse', {'continuation': 'two'}))
        api._check_auth.assert_called_once()

    def test_empty_and_single_page_finish_without_extra_request(self):
        for contents in ([], [song('A')]):
            api = Client([initial(contents)])
            pages = PlaylistPages(api, 'PLtest')
            tracks, more = pages.next_page()
            self.assertEqual(len(tracks), len(contents)); self.assertFalse(more)
            self.assertEqual(pages.next_page(), ([], False))
            self.assertEqual(api._send_request.call_count, 1)
            api._check_auth.assert_not_called()

    def test_repeated_cursor_rejected_instead_of_infinite_loop(self):
        api = Client([initial([song('A'), token('same')]), continuation([song('B'), token('same')])])
        pages = PlaylistPages(api, 'PLtest'); pages.next_page()
        with self.assertRaises(RuntimeError): pages.next_page()
        self.assertEqual(api._send_request.call_count, 2)

    def test_malformed_response_is_error_not_successful_truncation(self):
        api = Client([initial([song('A'), token('next')]), {}])
        pages = PlaylistPages(api, 'PLtest'); pages.next_page()
        with self.assertRaises(Exception): pages.next_page()
        self.assertEqual(pages.token, 'next')

    def test_error_keeps_cursor_for_retry(self):
        api = Client([initial([song('A'), token('next')]), TimeoutError(), continuation([song('B')])])
        pages = PlaylistPages(api, 'PLtest'); pages.next_page()
        with self.assertRaises(TimeoutError): pages.next_page()
        self.assertEqual(pages.next_page()[0][0]['videoId'], 'B')

    def test_installed_public_playlist_method_really_stops_after_first_shelf(self):
        response = initial([song('A'), token('next')])
        renderer = response['contents']['twoColumnBrowseResultsRenderer']
        renderer['tabs'] = [{'tabRenderer': {'content': {'sectionListRenderer': {'contents': [
            {'musicResponsiveHeaderRenderer': {'subtitle': {'runs': []}}}]}}}}]
        api = YTMusic.__new__(YTMusic)
        api._send_request = Mock(return_value=response)
        api._check_auth = Mock()
        pages = PlaylistPages(api, 'LM', liked=True)
        with patch('ytmusicapi.mixins.playlists.parse_playlist_header_meta', return_value={'title': 'Liked'}):
            tracks, more = pages.next_page()
        self.assertTrue(more)
        self.assertEqual(tracks[0]['videoId'], 'A')
        self.assertEqual(pages.metadata['title'], 'Liked')
        self.assertNotIn('tracks', pages.metadata)
        api._send_request.assert_called_once_with('browse', {'browseId': 'VLLM'}, '')


class WatchPagesTests(TestCase):
    @staticmethod
    def track(vid):
        return {'playlistPanelVideoRenderer': {'videoId': vid, 'title': {'runs': [{'text': vid}]},
            'menu': {'menuRenderer': {'items': []}}, 'longBylineText': {'runs': []}}}

    @staticmethod
    def panel(contents, cursor=None, radio=False):
        result = {'contents': contents}
        if cursor:
            result['continuations'] = [{'nextRadioContinuationData' if radio else 'nextContinuationData': {'continuation': cursor}}]
        return result

    @staticmethod
    def first(panel):
        return {'contents': {'singleColumnMusicWatchNextResultsRenderer': {'tabbedRenderer': {
            'watchNextTabbedResultsRenderer': {'tabs': [{'tabRenderer': {'content': {
                'musicQueueRenderer': {'content': {'playlistPanelRenderer': panel}}}}}]}}}}}

    def client(self, responses):
        api = YTMusic.__new__(YTMusic)
        api._send_request = Mock(side_effect=responses)
        return api

    def test_real_initial_parser_and_exact_continuations_for_playlist_album_and_liked(self):
        from felismusic_gui.paging import WatchPages
        for pid in ('PLsource', 'OLAKalbum', 'LL'):
            radio = pid == 'LL'
            api = self.client([self.first(self.panel([self.track('A')], 'one', radio)),
                {'continuationContents': {'playlistPanelContinuation': self.panel([self.track('B')], 'two', radio)}},
                {'continuationContents': {'playlistPanelContinuation': self.panel([self.track('A')])}}])
            request = api._send_request
            pager = WatchPages(api, pid)
            self.assertEqual(pager.next_page()[0][0]['videoId'], 'A')
            self.assertEqual(request.call_count, 1)
            self.assertIs(api._send_request, request)
            self.assertEqual(pager.next_page()[0][0]['videoId'], 'B')
            tracks, more = pager.next_page()
            self.assertEqual(tracks[0]['videoId'], 'A'); self.assertFalse(more)
            self.assertEqual(pager.next_page(), ([], False))
            calls = request.call_args_list
            body = calls[0].args[1]
            self.assertEqual(body['playlistId'], pid)
            self.assertEqual(body['params'], 'wAEB8gECKAE%3D')
            self.assertEqual(calls[1].args, ('next', body, '&ctoken=one&continuation=one'))
            self.assertEqual(calls[2].args, ('next', body, '&ctoken=two&continuation=two'))

    def test_artist_id_uses_original_body_without_extra_shuffle_params(self):
        from felismusic_gui.paging import WatchPages
        api = self.client([self.first(self.panel([self.track('A')], 'one', True)),
            {'continuationContents': {'playlistPanelContinuation': self.panel([self.track('B')])}}])
        pager = WatchPages(api, 'RDAartist', shuffle=False)
        pager.next_page(); pager.next_page()
        self.assertNotIn('params', api._send_request.call_args_list[0].args[1])
        self.assertEqual(api._send_request.call_args.args[2], '&ctoken=one&continuation=one')

    def test_repeated_cursor_and_malformed_response_are_errors(self):
        from felismusic_gui.paging import WatchPages
        for response in ({}, {'continuationContents': {'playlistPanelContinuation': self.panel([self.track('B')], 'one')}}):
            api = self.client([self.first(self.panel([self.track('A')], 'one')), response])
            pager = WatchPages(api, 'PLsource'); pager.next_page()
            with self.assertRaises(Exception): pager.next_page()

    def test_empty_page_with_continuation_is_not_treated_as_end(self):
        from felismusic_gui.paging import WatchPages
        api = self.client([self.first(self.panel([self.track('A')], 'one')),
            {'continuationContents': {'playlistPanelContinuation': self.panel([], 'two')}}])
        pager = WatchPages(api, 'PLsource'); pager.next_page()
        self.assertEqual(pager.next_page(), ([], True))

    def test_known_target_bounds_radio_style_tokens_without_cutting_occurrences(self):
        from felismusic_gui.paging import WatchPages
        api = self.client([self.first(self.panel([self.track('A')], 'one', True)),
            {'continuationContents': {'playlistPanelContinuation': self.panel([self.track('B'), self.track('A')], 'two', True)}}])
        pager = WatchPages(api, 'LL', limit=2)
        self.assertTrue(pager.next_page()[1])
        tracks, more = pager.next_page()
        self.assertFalse(more); self.assertEqual([x['videoId'] for x in tracks], ['B', 'A'])
        self.assertEqual(pager.next_page(), ([], False))
        self.assertEqual(api._send_request.call_count, 2)

    def test_repeat_diagnostic_distinguishes_replayed_and_new_rows_without_leaking_tokens(self):
        import io, json
        from contextlib import redirect_stdout
        from felismusic_gui.paging import WatchPages
        from felismusic_gui.diagnostics import Trace
        for repeated_row in (True, False):
            first = 'VIDEO_SECRET_A'; second = first if repeated_row else 'VIDEO_SECRET_B'
            api = self.client([self.first(self.panel([self.track(first)], 'CURSOR_SECRET')),
                {'continuationContents': {'playlistPanelContinuation': self.panel([self.track(second)], 'CURSOR_SECRET')}}])
            pager = WatchPages(api, 'PLsource', limit=100)
            output = io.StringIO()
            with patch('felismusic_gui.paging.current_trace', return_value=Trace('api.shuffle_page')), redirect_stdout(output):
                pager.next_page()
                with self.assertRaises(RuntimeError): pager.next_page()
            raw = output.getvalue()
            for secret in ('VIDEO_SECRET_A', 'VIDEO_SECRET_B', 'CURSOR_SECRET'): self.assertNotIn(secret, raw)
            records = [json.loads(line.split('] ', 1)[1]) for line in raw.splitlines()]
            error = records[-1]
            self.assertEqual(error['event'], 'shuffle.page_error')
            self.assertEqual(error['reason'], 'repeated_continuation')
            self.assertEqual(error['phase'], 'continuation_check')
            self.assertEqual(error['page'], 2); self.assertEqual(error['total_before'], 1)
            self.assertEqual(error['returned_total'], 2); self.assertEqual(error['page_tracks'], 1)
            self.assertEqual(error['repeated_from_page'], 1)
            self.assertEqual(error['unique_new'], 0 if repeated_row else 1)
            self.assertEqual(error['same_as_previous'], repeated_row)
            self.assertEqual(pager.count, 1)  # rejected page still cannot mutate the queue/cursor

    def test_diagnostic_distinguishes_transport_and_response_parse_error(self):
        import io, json
        from contextlib import redirect_stdout
        from felismusic_gui.paging import WatchPages
        from felismusic_gui.diagnostics import Trace
        for response, phase in ((TimeoutError('AUTH_SECRET signed?token=SECRET'), 'continuation_request'),
                                ({}, 'continuation_parse')):
            api = self.client([self.first(self.panel([self.track('A')], 'CURSOR_SECRET')), response])
            pager = WatchPages(api, 'PLsource'); pager.next_page()
            output = io.StringIO()
            with patch('felismusic_gui.paging.current_trace', return_value=Trace('api.shuffle_page')), redirect_stdout(output):
                with self.assertRaises(Exception): pager.next_page()
            self.assertNotIn('SECRET', output.getvalue())
            error = json.loads(output.getvalue().split('] ', 1)[1])
            self.assertEqual(error['event'], 'shuffle.page_error')
            self.assertEqual(error['reason'], 'request_or_parse'); self.assertEqual(error['phase'], phase)
            self.assertEqual(error['total_before'], 1)

    def test_diagnostic_target_completion_and_disabled_trace_leave_behavior_unchanged(self):
        import io, json
        from contextlib import redirect_stdout
        from felismusic_gui.paging import WatchPages
        from felismusic_gui.diagnostics import Trace
        api = self.client([self.first(self.panel([self.track('A')], 'CURSOR_SECRET')),
            {'continuationContents': {'playlistPanelContinuation': self.panel([self.track('A')], 'CURSOR_SECRET')}}])
        pager = WatchPages(api, 'PLsource', limit=2)
        output = io.StringIO()
        with patch('felismusic_gui.paging.current_trace', return_value=None), redirect_stdout(output):
            self.assertTrue(pager.next_page()[1])
        self.assertEqual(output.getvalue(), '')
        with patch('felismusic_gui.paging.current_trace', return_value=Trace('api.shuffle_page')), redirect_stdout(output):
            tracks, more = pager.next_page()
        self.assertEqual(len(tracks), 1); self.assertFalse(more)
        event = json.loads(output.getvalue().split('] ', 1)[1])
        self.assertEqual(event['event'], 'shuffle.page')
        self.assertTrue(event['target_reached']); self.assertTrue(event['repeated_continuation'])
        self.assertNotIn('CURSOR_SECRET', output.getvalue())
