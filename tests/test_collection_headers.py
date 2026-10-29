"""Collection headers use metadata and complete, known song lengths only."""
from copy import deepcopy
from unittest.mock import Mock, patch
import test_prefetch as support


class CollectionHeaderTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp(); self.api = Mock(); self.b._ytmusic = self.api
        self.data = dict(title='Collection', artists=[dict(name='Artist', id='UCartist')],
                         author=dict(name='Owner'), year='2024', trackCount=3,
                         thumbnails=[dict(url='https://example.test/cover.png')],
                         tracks=[dict(videoId=vid, title=vid, duration=duration, likeStatus='LIKE')
                                 for vid, duration in [('X','1:00'),('Y','2:00'),('X','1:00')]])
        self.api.get_album.return_value = self.data
        self.api.get_playlist.return_value = self.data

    def album(self):
        self.b.openLibraryItem('album','MPREalbum','','Collection')
        self.until(lambda:not self.b.busy)

    def test_album_uses_collection_artist_year_cover_exact_duration_and_duplicates(self):
        self.album()
        self.assertEqual(self.b.detailHeaderSummary, 'Artist · 2024 · 3 skladby · Délka 04:00')
        self.assertEqual(self.b.detailMeta['header']['thumbnail'], 'https://example.test/cover.png')
        self.api.get_album.assert_called_once_with('MPREalbum')

    def test_playlist_owner_differs_from_track_artist_and_cover_survives_playback_restore(self):
        self.b.loadPlaylistTracks('PLsource','Collection'); self.until(lambda:not self.b.busy)
        self.assertEqual(self.b.detailHeaderSummary, 'Owner · 2024 · 3 skladby · Délka 04:00')
        self.b.playFrom('detail',2); self.until(lambda:self.b.playerState=='playing')
        before = self.b.detailHeaderSummary; header=deepcopy(self.b.detailMeta['header'])
        played=list(self.played);self.b.clearDetail();self.b.restorePlayingSource(1)
        self.assertEqual(self.b.detailHeaderSummary,before);self.assertEqual(self.b.detailMeta['header'],header)
        self.assertEqual(self.played,played);self.assertEqual(self.b.playerSourceIndex,2)

    def test_missing_duration_is_not_treated_as_zero_or_partial_total(self):
        self.data['tracks'][1].pop('duration'); self.data['duration_seconds']=60
        self.album();self.assertEqual(self.b.detailHeaderSummary,'Artist · 2024 · 3 skladby')
        self.data['duration']='About 4 minutes'
        self.album();self.assertIn('Délka About 4 minutes',self.b.detailHeaderSummary)

    def test_unavailable_rows_distinguish_available_count_and_duration(self):
        self.data['tracks'][1]['isAvailable']=False
        self.album()
        self.assertEqual(self.b.detailHeaderSummary,'Artist · 2024 · Dostupné: 2 z 3 skladeb · Délka dostupných 02:00')

    def test_upload_album_has_only_available_header_metadata(self):
        data = deepcopy(self.data);data.pop('artists');data.pop('year');data.pop('author')
        with patch.object(support.backend, 'load_upload_album', return_value=data):
            self.b.openLibraryItem('upload_album','FEmusic_library_privately_owned_release_detailX','','Collection')
            self.until(lambda:not self.b.busy)
        self.assertEqual(self.b.detailHeaderSummary,'3 skladby · Délka 04:00')
        self.assertEqual(self.b.detailMeta['header']['thumbnail'], 'https://example.test/cover.png')

    def test_invalid_year_count_and_missing_values_are_not_invented(self):
        self.data.update(year='Artist name', trackCount=True, artists=None, thumbnails=[], tracks=[])
        self.album(); self.assertEqual(self.b.detailHeaderSummary,'0 skladeb')
        self.assertEqual(self.b.detailMeta['header']['thumbnail'],'')
        self.b._detail_meta=dict(kind='artist');self.assertEqual(self.b.detailHeaderSummary,'')
        self.b._detail_meta=dict(kind='dynamic_mix',dynamicMix=True);self.assertEqual(self.b.detailHeaderSummary,'')

    def test_playlist_move_and_remove_keep_header_and_recalculate_count_and_length(self):
        self.data['owned'] = True
        self.data['duration'] = 'Old server duration'
        for i, song in enumerate(self.data['tracks']): song['setVideoId'] = f'set-{i}'
        self.api.edit_playlist.return_value = 'STATUS_SUCCEEDED'
        self.api.remove_playlist_items.return_value = 'STATUS_SUCCEEDED'
        self.b.loadPlaylistTracks('PLsource','Collection');self.until(lambda:not self.b.busy)
        self.assertTrue(self.b.moveDetailPlaylistItem('X','set-2',-1));self.until(lambda:not self.b.busy)
        self.assertEqual(self.b.detailHeaderSummary,'Owner · 2024 · 3 skladby · Délka 04:00')
        self.assertTrue(self.b.removeDetailPlaylistItem('Y','set-1'));self.until(lambda:not self.b.busy)
        self.assertEqual(self.b.detailHeaderSummary,'Owner · 2024 · 2 skladby · Délka 02:00')
