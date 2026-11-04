"""Displayed playback markers follow source occurrences across sorting only."""
from copy import deepcopy
from unittest.mock import Mock, patch
import test_prefetch as support


class SourceMarkerTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock(); self.b._ytmusic = self.api
        self.rows = [dict(videoId=vid, title=title, duration='3:00', likeStatus='LIKE')
                     for vid, title in (('Z', 'Zulu'), ('A', 'Alpha'), ('A', 'Alpha'), ('B', 'Beta'))]
        self.api.get_artist.return_value = dict(name='Artist', songs={'results': deepcopy(self.rows)}, albums={}, singles={})
        self.api.get_library_upload_artist.return_value = deepcopy(self.rows)
        self.api.get_library_songs.side_effect = self.library_rows
        self.api.get_library_upload_songs.side_effect = self.library_rows
        self.track_changes = []
        self.b.playerTrackChanged.connect(lambda: self.track_changes.append(True))

    def library_rows(self, limit=None, order=None):
        rows = deepcopy(self.rows)
        if order in ('a_to_z', 'z_to_a'):
            rows.sort(key=lambda row: row['title'], reverse=order == 'z_to_a')
        return rows

    def ready(self):
        self.until(lambda: not self.b.busy)

    def load(self, kind):
        if kind in ('songs', 'upload_songs'):
            self.b.loadLibrarySection(kind, 'a_to_z')
        else:
            self.b.openLibraryItem(kind, 'artist-source', '', 'Artist')
        self.ready()
        if kind in ('artist', 'upload_artist'):
            self.b.setArtistOrder('a_to_z')
        return 'library' if kind in ('songs', 'upload_songs') else 'detail'

    def order(self, kind, order):
        if kind in ('songs', 'upload_songs'):
            self.b.loadLibrarySection(kind, order); self.ready()
        else: self.b.setArtistOrder(order)

    def test_four_views_follow_second_duplicate_without_touching_queue_audio_or_origin(self):
        for kind in ('artist', 'upload_artist', 'songs', 'upload_songs'):
            with self.subTest(kind=kind):
                source = self.load(kind)
                self.b.playFrom(source, 1); self.until(lambda: self.b.playerState == 'playing')
                self.assertEqual(self.b.playerVisibleSourceIndex, 1)
                queue = self.b._queue; origins = deepcopy([x['_guiOrigin'] for x in queue.tracks])
                ids = [x['videoId'] for x in queue.tracks]; played = list(self.played)
                self.b._player_position = 42; changes = len(self.track_changes)
                for order, expected in (('z_to_a', 3), ('default', 2), ('a_to_z', 1)):
                    self.order(kind, order)
                    self.assertEqual(self.b.playerVisibleSourceIndex, expected)
                    self.assertEqual(self.b.playerSourceIndex, 1)
                    self.assertIs(self.b._queue, queue)
                    self.assertEqual([x['videoId'] for x in queue.tracks], ids)
                    self.assertEqual([x['_guiOrigin'] for x in queue.tracks], origins)
                    self.assertEqual(self.played, played); self.assertEqual(self.b.playerPosition, 42)
                    self.assertEqual(len(self.track_changes), changes)

    def test_other_artist_or_other_library_section_with_same_video_is_not_marked(self):
        source = self.load('artist'); self.b.playFrom(source, 0); self.until(lambda: self.b.playerState == 'playing')
        self.b.openLibraryItem('artist', 'another-artist', '', 'Another'); self.ready()
        self.assertEqual(self.b.playerVisibleSourceIndex, -1)
        self.assertTrue(self.b.restorePlayingSource(1)); self.assertEqual(self.b.playerVisibleSourceIndex, 0)
        source = self.load('songs'); self.b.playFrom(source, 0); self.until(lambda: self.b.playerState == 'playing')
        self.b.loadLibrarySection('upload_songs', 'a_to_z'); self.ready()
        self.assertEqual(self.b.playerVisibleSourceIndex, -1)
        self.b.loadLibrarySection('songs', 'z_to_a'); self.ready()
        self.assertEqual(self.b.playerVisibleSourceIndex, 2)

    def test_missing_occurrence_is_not_replaced_by_another_duplicate(self):
        source = self.load('upload_artist'); self.b.playFrom(source, 1); self.until(lambda: self.b.playerState == 'playing')
        items = self.b.detailTracksModel.snapshot(); del items[1]
        self.b.detailTracksModel.set_items(items)
        self.assertEqual(self.b.playerVisibleSourceIndex, -1)

    def test_pause_stop_next_and_cover_keep_marker_attached_to_original_occurrence(self):
        source = self.load('upload_artist'); self.b.playFrom(source, 1); self.until(lambda: self.b.playerState == 'playing')
        self.b._player_state = 'paused'; self.order('upload_artist', 'z_to_a')
        self.assertEqual(self.b.playerVisibleSourceIndex, 3); self.assertEqual(self.b.playerState, 'paused')
        self.b.stopPlayback(); self.assertEqual(self.b.playerVisibleSourceIndex, 3)
        self.b.nextTrack(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVisibleSourceIndex, 1)
        self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual(self.b.playerVisibleSourceIndex, self.b.playerSourceIndex)

    def test_manual_enqueue_and_upload_shuffle_keep_occurrence_marker(self):
        source = self.load('upload_artist')
        self.assertTrue(self.b.enqueueFrom(source, 1, False, {'page': 1}))
        self.order('upload_artist', 'z_to_a')
        self.assertEqual(self.b.playerVisibleSourceIndex, 3)
        self.b.clearDetail(); self.assertTrue(self.b.restorePlayingSource(1))
        with patch.object(support.backend.random, 'shuffle', side_effect=lambda rows: rows.reverse()):
            self.assertTrue(self.b.shuffleDetail()); self.ready()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerSourceIndex, 3)
        self.order('upload_artist', 'z_to_a')
        self.assertEqual(self.b.playerVisibleSourceIndex, 0)

    def test_lookup_is_cached_for_multiple_delegates_and_invalidated_after_sort(self):
        source = self.load('upload_artist'); self.b.playFrom(source, 1); self.until(lambda: self.b.playerState == 'playing')
        self.b._invalidate_playing_source_view()
        with patch.object(self.b, '_source_items', wraps=self.b._source_items) as items:
            for _ in range(50): self.assertEqual(self.b.playerVisibleSourceIndex, 1)
            self.assertEqual(items.call_count, 1)
        self.order('upload_artist', 'z_to_a')
        self.assertEqual(self.b.playerVisibleSourceIndex, 3)
