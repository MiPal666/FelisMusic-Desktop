"""Read-only metadata snapshots for songs that need not be playing."""
from copy import deepcopy
from unittest.mock import Mock
import test_prefetch as support


class TrackInfoTests(support.AudioPlaybackTestCase):
    def test_all_sources_and_uploads_without_playback_or_network(self):
        self.b._ytmusic = Mock()
        for source in ('library', 'liked', 'history', 'search', 'detail'):
            for kind in ('song', 'video', 'upload_song'):
                with self.subTest(source=source, kind=kind):
                    row = dict(title='Selected', kind=kind, videoId='X', artists='Artist',
                               album='Album', duration='3:21', likeStatus='DISLIKE', thumbnail='')
                    self.b._source_model(source).set_items([row])
                    info = self.b.trackInfoFrom(source, 0)
                    self.assertEqual(info['title'], 'Selected')
                    self.assertEqual(info['artist'], 'Artist'); self.assertEqual(info['album'], 'Album')
                    self.assertEqual(info['duration'], 201); self.assertEqual(info['likeStatus'], 'DISLIKE')
                    self.assertFalse(info['inQueue']); self.assertEqual(info['queueIndex'], -1)
        self.assertFalse(self.played); self.assertFalse(self.stops)
        self.assertFalse(self.b._ytmusic.mock_calls); self.assertFalse(self.b.playerHasTrack)

    def test_exact_duplicate_queue_occurrence_and_current_runtime_metadata(self):
        self.b._library_items_model.set_items([
            dict(kind='song', videoId='A', title='First', duration='3:00', likeStatus='LIKE'),
            dict(kind='song', videoId='A', title='Second', duration='4:00', likeStatus='DISLIKE')])
        self.b.playFrom('library', 0); self.until(lambda: self.b.playerState == 'playing')
        self.b._player_duration = 181; self.b._player_like_status = 'INDIFFERENT'
        current = self.b.trackInfoFrom('playing', 0)
        other = self.b.trackInfoFrom('playing', 1)
        self.assertEqual(current['duration'], 181); self.assertEqual(current['likeStatus'], 'INDIFFERENT')
        self.assertEqual(other['title'], 'Second'); self.assertEqual(other['duration'], 240)
        self.assertEqual(other['likeStatus'], 'DISLIKE'); self.assertEqual(other['queueIndex'], 1)
        self.assertTrue(other['inQueue']); self.assertEqual(other['queueCount'], 2)
        self.b.moveQueueItem(1, -1)
        self.assertEqual(other['queueIndex'], 1)  # Snapshot stays tied to the opening moment.
        self.assertEqual(other['title'], 'Second')

    def test_info_does_not_change_audio_queue_selection_or_source(self):
        self.start('A', 'B', 'C'); self.b._player_position = 42
        self.b.selectTrack('library', 2, False, False)
        queue, current = self.b._queue, self.b._queue.current()
        before = deepcopy(self.b._library_items_model.snapshot())
        played, stops = list(self.played), list(self.stops)
        info = self.b.trackInfoFrom('library', 2)
        self.assertEqual(info['title'], 'C'); self.assertIs(self.b._queue, queue)
        self.assertIs(queue.current(), current); self.assertEqual(self.b.playerPosition, 42)
        self.assertEqual(self.b.selectedTrackIndices, [2]); self.assertEqual(self.played, played)
        self.assertEqual(self.stops, stops); self.assertEqual(self.b._library_items_model.snapshot(), before)
        self.b._library_items_model.clear(); self.assertEqual(info['title'], 'C')

    def test_missing_values_and_invalid_sources_rows_are_safe(self):
        for source, index in (('unknown', 0), ('playing', 0), ('library', -1), ('library', 100)):
            self.assertEqual(self.b.trackInfoFrom(source, index), {})
        self.b._detail_tracks_model.set_items([dict(kind='album', videoId='X'), dict(kind='song'), dict(kind='song', videoId='X')])
        self.assertEqual(self.b.trackInfoFrom('detail', 0), {})
        self.assertEqual(self.b.trackInfoFrom('detail', 1), {})
        info = self.b.trackInfoFrom('detail', 2)
        self.assertEqual(info['title'], 'Bez názvu'); self.assertEqual(info['duration'], 0)
        self.assertEqual(info['likeStatus'], 'UNKNOWN'); self.assertEqual(info['artist'], '')
