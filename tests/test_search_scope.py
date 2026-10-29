"""Scope-specific search filters, without account/network dependencies."""
from unittest.mock import Mock
import test_prefetch as support


class SearchScopeTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp();self.api=Mock();self.b._ytmusic=self.api
        self.api.search.return_value=[dict(resultType='song',videoId='X',title='X')]

    def search(self, mode, scope):
        self.b.search(' metal ',mode,scope);self.until(lambda:not self.b.busy)

    def test_library_rejects_catalog_only_filters_without_leaking_into_global_search(self):
        for mode in ('videos','playlists','profiles','podcasts','episodes','unknown'):
            with self.subTest(mode=mode):
                self.api.search.reset_mock();self.search(mode,'library')
                self.api.search.assert_called_once_with('metal',limit=support.core.SEARCH_LIMIT,scope='library')
                self.assertEqual(self.b.searchResultsModel.snapshot()[0]['kind'],'song')
        self.assertFalse(self.errors)

    def test_supported_library_filters_pass_to_api(self):
        for mode in ('songs','albums','artists'):
            self.api.search.reset_mock();self.search(mode,'library')
            self.api.search.assert_called_once_with('metal',limit=support.core.SEARCH_LIMIT,scope='library',filter=mode)

    def test_all_catalog_filters_remain_available(self):
        for mode in ('videos','playlists','profiles','podcasts','episodes','songs','albums','artists'):
            self.api.search.reset_mock();self.search(mode,'catalog')
            self.api.search.assert_called_once_with('metal',limit=support.core.SEARCH_LIMIT,filter=mode)

    def test_uploads_still_search_without_any_filter(self):
        self.search('videos','uploads')
        self.api.search.assert_called_once_with('metal',limit=support.core.SEARCH_LIMIT,scope='uploads')
        self.assertEqual(self.b.searchResultsModel.snapshot()[0]['kind'],'upload_song')

    def test_genuine_failure_is_reported_and_empty_result_is_allowed(self):
        self.api.search.return_value=[];self.search('songs','library')
        self.assertEqual(self.b.searchResultsModel.count,0)
        self.api.search.side_effect=RuntimeError('offline');self.search('songs','library')
        self.assertTrue(self.errors)
