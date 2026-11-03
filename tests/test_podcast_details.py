"""Podcast details distinguish saved episodes from podcast subscriptions."""
from unittest.mock import Mock

import test_prefetch as support


class PodcastDetailTests(support.AudioPlaybackTestCase):
    def test_episode_collections_use_their_own_endpoints(self):
        cases = (
            ('VLSE', 'SE', 'get_saved_episodes', (), {'limit': None}, 'tracks', []),
            ('VLSE', '', 'get_saved_episodes', (), {'limit': None}, 'tracks', [{'videoId': 'saved'}]),
            ('VLRDPN', 'RDPN', 'get_episodes_playlist', ('RDPN',), {}, 'episodes', [{'videoId': 'new'}]),
            ('MPSPPLpodcast', 'PLpodcast', 'get_podcast', ('PLpodcast',), {'limit': None},
             'episodes', [{'videoId': 'podcast'}]),
        )
        for browse_id, playlist_id, endpoint, args, kwargs, key, rows in cases:
            with self.subTest(endpoint=endpoint, rows=rows):
                api = Mock()
                self.b._ytmusic = api
                getattr(api, endpoint).return_value = {'title': 'Episode collection', key: rows}
                self.b.openLibraryItem('podcast', browse_id, playlist_id, 'Podcast')
                self.until(lambda: not self.b.busy)
                self.assertEqual(self.b.detailTitle, 'Episode collection')
                self.assertEqual([row['videoId'] for row in self.b.detailTracksModel.snapshot()],
                                 [row['videoId'] for row in rows])
                getattr(api, endpoint).assert_called_once_with(*args, **kwargs)
                self.assertFalse(self.errors)
