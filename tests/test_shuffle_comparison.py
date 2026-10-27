"""The old helper and new adapter consume exactly the same mock responses."""
import importlib.util
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch
import test_prefetch
import test_paging
from ytmusicapi import YTMusic

spec = importlib.util.spec_from_file_location('shuffle_comparison', Path(__file__).resolve().parents[1] / 'tools/compare_shuffle.py')
comparison = importlib.util.module_from_spec(spec); spec.loader.exec_module(comparison)


class ComparisonTests(TestCase):
    def client(self, cycle):
        fixture = test_paging.WatchPagesTests()
        track, panel = fixture.track, fixture.panel
        api = YTMusic.__new__(YTMusic)
        def send(endpoint, body, *args, **kwargs):
            if not args:
                return fixture.first(panel([track('A'), track('B')], 'TOKEN_SECRET_ONE'))
            if 'TOKEN_SECRET_ONE' in args[0]:
                return {'continuationContents': {'playlistPanelContinuation': panel(
                    [track('C'), track('D')], 'TOKEN_SECRET_TWO' if cycle else None)}}
            return {'continuationContents': {'playlistPanelContinuation': panel(
                [track('A'), track('B')], 'TOKEN_SECRET_ONE')}}
        api._send_request = Mock(side_effect=send)
        return api

    def test_repeating_server_sequence_is_also_repeated_by_legacy_helper(self):
        api = self.client(True); output = []
        result = comparison.compare(api, 'PLtest', 25, emit=output.append)
        self.assertEqual(result['old_count'], 26); self.assertEqual(result['old_unique'], 4)
        self.assertEqual(result['new_count'], 4); self.assertTrue(result['same_order_prefix'])
        self.assertEqual(result['error']['reason'], 'repeated_continuation')
        self.assertEqual(result['error']['unique_new'], 0)
        self.assertEqual(api._send_request.call_count, result['old_requests'])
        self.assertGreater(result['repeated_requests'], 0)
        self.assertNotIn('TOKEN_SECRET', str(output) + str(result))

    def test_finite_sequence_has_identical_result_without_second_network_run(self):
        api = self.client(False)
        result = comparison.compare(api, 'PLtest', 25, emit=lambda _: None)
        self.assertEqual(result['old_count'], 4); self.assertEqual(result['new_count'], 4)
        self.assertEqual(result['old_requests'], 2); self.assertEqual(api._send_request.call_count, 2)
        self.assertIsNone(result['error']); self.assertTrue(result['same_order_prefix'])

    def test_request_mismatch_is_reported_instead_of_comparing_different_orders(self):
        api = self.client(False)
        class WrongPager:
            def __init__(self, replay, *args, **kwargs): self.api = replay
            def next_page(self): return self.api._send_request('next', {'wrong': 'SECRET'}), False
        with patch.object(comparison, 'WatchPages', WrongPager):
            with self.assertRaises(comparison.ComparisonFailure) as error:
                comparison.compare(api, 'PLtest', 25, emit=lambda _: None)
        self.assertEqual(str(error.exception), 'replay_request_mismatch')
        self.assertNotIn('SECRET', str(error.exception))

    def test_request_limit_stops_unbounded_capture(self):
        with self.assertRaises(comparison.ComparisonFailure) as error:
            comparison.compare(self.client(True), 'PLtest', 1635, max_requests=3, emit=lambda _: None)
        self.assertEqual(error.exception.reason, 'request_limit')

    def test_replay_reproduces_real_send_request_context_mutation(self):
        api = self.client(True)
        send = api._send_request.side_effect
        def mutating_send(endpoint, body, *args, **kwargs):
            body.update({'context': {'client': {'clientName': 'WEB_REMIX',
                                                'visitorData': 'VISITOR_SECRET'}}})
            return send(endpoint, body, *args, **kwargs)
        api._send_request.side_effect = mutating_send
        output = []
        result = comparison.compare(api, 'PLtest', 25, emit=output.append)
        self.assertTrue(result['same_order_prefix'])
        self.assertEqual(result['error']['reason'], 'repeated_continuation')
        self.assertEqual(result['old_count'], 26)
        self.assertEqual(result['new_count'], 4)
        self.assertEqual(api._send_request.call_count, result['old_requests'])
        self.assertNotIn('VISITOR_SECRET', str(output) + str(result))


class OrdinaryPlaylistTests(TestCase):
    def client(self, cycle=False, extra_rows=()):
        first = test_paging.initial([test_paging.song('A'), test_paging.token('CURSOR_SECRET')])
        first['contents']['twoColumnBrowseResultsRenderer']['tabs'] = [
            {'tabRenderer': {'content': {'sectionListRenderer': {'contents': [
                {'musicResponsiveHeaderRenderer': {'subtitle': {'runs': []}}}]}}}}]
        last = [test_paging.song('A'), test_paging.song('B')]
        last.extend(extra_rows)
        if cycle:
            last.append(test_paging.token('CURSOR_SECRET'))
        responses = iter([first, test_paging.continuation(last)])
        api = YTMusic.__new__(YTMusic)
        def send(endpoint, body, *args, **kwargs):
            body.update({'context': {'visitorData': 'VISITOR_SECRET'}})
            return next(responses)
        api._send_request = Mock(side_effect=send)
        return api

    def test_real_public_parser_loads_all_rows_and_preserves_duplicates(self):
        api = self.client(); output = []
        with patch('ytmusicapi.mixins.playlists.parse_playlist_header_meta',
                   return_value={'title': 'PRIVATE_TITLE', 'trackCount': 1675}):
            result = comparison.inspect_playlist(api, 'PLtest', emit=output.append)
        self.assertEqual(result['rows'], 3)
        self.assertEqual(result['unique_videos'], 2)
        self.assertEqual(result['duplicate_rows'], 1)
        self.assertEqual(result['reported_count'], 1675)
        self.assertEqual(result['requests'], 2)
        self.assertEqual(result['raw_song_rows'], 3)
        self.assertEqual(result['raw_continuations'], 1)
        self.assertEqual(result['raw_other_rows'], 0)
        self.assertEqual(result['parser_skipped_rows'], 0)
        self.assertEqual(result['raw_parsed_rows'], result['rows'])
        self.assertEqual(api._send_request.call_count, 2)
        self.assertNotIn('SECRET', str(result) + str(output))
        self.assertNotIn('PRIVATE_TITLE', str(result) + str(output))

    def test_cycle_stops_before_repeating_network_request(self):
        api = self.client(cycle=True)
        with patch('ytmusicapi.mixins.playlists.parse_playlist_header_meta', return_value={}):
            with self.assertRaises(comparison.ComparisonFailure) as error:
                comparison.inspect_playlist(api, 'PLtest', emit=lambda _: None)
        self.assertEqual(error.exception.reason, 'ordinary_repeated_request')
        self.assertEqual(api._send_request.call_count, 2)

    def test_request_bound_is_not_silent_success(self):
        api = self.client()
        with patch('ytmusicapi.mixins.playlists.parse_playlist_header_meta', return_value={}):
            with self.assertRaises(comparison.ComparisonFailure) as error:
                comparison.inspect_playlist(api, 'PLtest', max_requests=1, emit=lambda _: None)
        self.assertEqual(error.exception.reason, 'ordinary_request_limit')
        self.assertEqual(api._send_request.call_count, 1)

    def test_rows_without_video_and_unavailable_rows_are_counted_separately(self):
        class Api:
            def get_playlist(self, pid, limit):
                assert limit is None
                return {'trackCount': '4', 'tracks': [
                    {'videoId': 'A'}, {'videoId': 'A'}, {},
                    {'videoId': 'B', 'isAvailable': False}]}
        result = comparison.inspect_playlist(Api(), 'PLtest')
        self.assertEqual(result['rows'], 4)
        self.assertEqual(result['missing_video_rows'], 1)
        self.assertEqual(result['usable_rows'], 2)
        self.assertEqual(result['reported_count'], 4)

    def test_ordinary_mode_rejects_manual_target_before_authentication(self):
        with patch.object(comparison, 'YTMusic') as auth:
            with self.assertRaises(SystemExit), patch('sys.stderr'):
                comparison.main(['--ordinary', '--limit', '1635'])
        auth.assert_not_called()

    def test_deleted_and_grey_rows_are_counted_before_real_parser(self):
        deleted = test_paging.song('Song deleted')
        grey = test_paging.song('Unavailable')
        renderer = grey['musicResponsiveListItemRenderer']
        renderer['musicItemRendererDisplayPolicy'] = 'MUSIC_ITEM_RENDERER_DISPLAY_POLICY_GREY_OUT'
        renderer['flexColumns'] *= 3
        api = self.client(extra_rows=[deleted, grey, {'unknownRenderer': {'secret': 'PRIVATE'}}])
        output = []
        with patch('ytmusicapi.mixins.playlists.parse_playlist_header_meta', return_value={'trackCount': 5}):
            result = comparison.inspect_playlist(api, 'PLtest', emit=output.append)
        self.assertEqual(result['raw_song_rows'], 5)
        self.assertEqual(result['parser_skipped_rows'], 1)
        self.assertEqual(result['raw_grey_rows'], 1)
        self.assertEqual(result['raw_other_rows'], 1)
        self.assertEqual(result['rows'], 4)
        self.assertEqual(result['raw_parsed_rows'], 4)
        self.assertEqual(result['usable_rows'], 3)
        self.assertEqual(api._send_request.call_count, 2)
        self.assertNotIn('PRIVATE', str(result) + str(output))

    def test_unknown_response_schema_cannot_look_like_zero_missing_rows(self):
        api = self.client()
        api._send_request = Mock(return_value={'unexpected': 'PRIVATE_SECRET'})
        with self.assertRaises(comparison.ComparisonFailure) as error:
            comparison.inspect_playlist(api, 'PLtest', emit=lambda _: None)
        self.assertEqual(error.exception.reason, 'ordinary_unrecognized_raw_page')
        self.assertNotIn('PRIVATE', str(error.exception))
