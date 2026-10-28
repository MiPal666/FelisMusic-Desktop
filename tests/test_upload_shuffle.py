"""Local shuffle of uploaded songs, albums and artists; no live account/audio."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock, patch
import test_prefetch as support


class UploadShuffleTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock(); self.b._ytmusic = self.api
        self.source = [dict(videoId=vid, title=f'Upload {i}', entityId=f'entity-{i}', likeStatus='LIKE',
                            artists=[{'name': 'Uploaded Artist'}], album={'name': 'Uploaded Album', 'id': 'upload-album'},
                            thumbnails=[{'url': 'https://example.invalid/art.jpg'}], duration='3:00')
                       for i, vid in enumerate(('A', 'B', 'A', 'C'))]
        self.api.get_library_upload_songs.return_value = deepcopy(self.source)
        self.api.get_library_upload_album.return_value = dict(title='Uploaded Album', tracks=deepcopy(self.source))
        self.api.get_library_upload_artist.return_value = deepcopy(self.source)
        self.started = []
        self.b.collectionShuffleStarted.connect(lambda: self.started.append(True))
        self.b.playbackSourceCaptured.connect(lambda: self.b.setPlaybackSourceContext(
            {'page': 1, 'librarySection': self.b._library_section, 'libraryOrder': 'a_to_z'}))

    def load(self, kind):
        section = {'songs': 'upload_songs', 'album': 'upload_albums', 'artist': 'upload_artists'}[kind]
        if kind == 'songs':
            self.b.loadLibrarySection(section, 'a_to_z')
        else:
            self.b._library_section = section
            self.b.openLibraryItem('upload_' + kind, 'upload-' + kind, '', 'Uploaded ' + kind)
        self.until(lambda: not self.b.busy)

    def shuffle(self, kind):
        return self.b.shuffleUploadSongs() if kind == 'songs' else self.b.shuffleDetail()

    def play_shuffle(self, kind):
        with patch.object(support.backend.random, 'shuffle', side_effect=lambda rows: rows.reverse()):
            self.assertTrue(self.shuffle(kind))
            self.until(lambda: not self.b.busy and self.b.playerState == 'playing')

    def test_all_three_sources_preserve_exact_occurrences_metadata_and_cover_without_reload(self):
        for kind in ('songs', 'album', 'artist'):
            with self.subTest(kind=kind):
                self.load(kind)
                source = 'library' if kind == 'songs' else 'detail'
                before = self.b._source_items(source)
                state = self.b._detail_state()
                calls = list(self.api.mock_calls)
                self.play_shuffle(kind)
                self.assertEqual(self.b.playerQueueCount, 4)
                self.assertEqual(self.b._queue_source_indices, [3, 2, 1, 0])
                self.assertEqual([x['videoId'] for x in self.b._queue.tracks], ['C', 'A', 'B', 'A'])
                self.assertTrue(all(x['_guiKind'] == 'upload_song' for x in self.b._queue.tracks))
                self.assertTrue(all(x['_guiThumbnail'] == 'https://example.invalid/art.jpg' for x in self.b._queue.tracks))
                self.assertTrue(all('_guiPlaylistBinding' not in x for x in self.b._queue.tracks))
                self.assertFalse(self.b._queue.source_playlist_id)
                self.assertTrue(self.b._queue.shuffle_active); self.assertFalse(self.b._queue.radio_active)
                self.assertFalse(self.b.playerQueueLoading)
                self.assertEqual(self.b._source_items(source), before)
                queue = self.b._queue
                self.b.clearDetail(); self.b._library_items_model.set_items([])
                played = list(self.played)
                self.assertTrue(self.b.restorePlayingSource(1))
                self.assertEqual(self.b._source_items(source), before)
                self.assertEqual(self.b._detail_state(), state)
                self.assertEqual(self.b.playerQueueSource, source)
                self.assertEqual(self.b.playerSourceIndex, 3)
                self.assertEqual(self.b.playerSourceContext['librarySection'], self.b._library_section)
                self.assertIs(self.b._queue, queue); self.assertEqual(self.played, played)
                self.assertEqual(self.api.mock_calls, calls)
        self.api.get_library_upload_artist.assert_called_once_with('upload-artist', limit=None)

    def test_repeat_next_previous_stop_and_new_shuffle_reset(self):
        for kind in ('songs', 'album', 'artist'):
            with self.subTest(kind=kind):
                self.load(kind); self.play_shuffle(kind)
                self.until(lambda: 'A' in support.core.LOCAL_AUDIO_CACHE)
                self.b.nextTrack(); self.until(lambda: self.b.playerState == 'playing')
                self.assertEqual(self.b.playerSourceIndex, 2)
                self.b.previousTrack(); self.until(lambda: self.b.playerState == 'playing')
                self.assertEqual(self.b.playerSourceIndex, 3)
                self.b.cycleRepeat(); self.b.cycleRepeat()
                self.eos(); self.until(lambda: self.b.playerState == 'playing')
                self.assertEqual(self.b.playerVideoId, 'C')
                self.b.cycleRepeat(); self.b.cycleRepeat()
                self.b.playFrom('playing', 3); self.until(lambda: self.b.playerState == 'playing')
                self.eos(); self.until(lambda: self.b.playerState == 'playing')
                self.assertEqual(self.b.playerSourceIndex, 3)
                self.b.stopPlayback(); self.assertEqual(self.b.playerState, 'idle')
                self.play_shuffle(kind); self.assertEqual(self.b.playerRepeatMode, 'off')
                self.b.playFrom('playing', 3); self.until(lambda: self.b.playerState == 'playing')
                self.eos(); self.assertEqual(self.b.playerState, 'idle')
        self.api.get_watch_playlist.assert_not_called()

    def test_failure_preserves_old_queue_audio_and_repeat(self):
        for kind in ('songs', 'album', 'artist'):
            with self.subTest(kind=kind):
                self.load(kind); self.play_shuffle(kind)
                old = self.b._queue; self.b.cycleRepeat()
                with patch.object(support.backend.random, 'shuffle', side_effect=RuntimeError('test')):
                    self.assertTrue(self.shuffle(kind)); self.until(lambda: not self.b.busy)
                self.assertIs(self.b._queue, old)
                self.assertEqual(self.b.playerRepeatMode, 'all')
                self.assertEqual(self.b.playerState, 'playing')
        self.assertEqual(len(self.errors), 3)

    def test_delayed_result_is_discarded_after_stop_new_queue_or_navigation(self):
        for kind in ('songs', 'album', 'artist'):
            for change in ('stop', 'new', 'navigate'):
                with self.subTest(kind=kind, change=change):
                    self.load(kind); self.play_shuffle(kind)
                    entered = Event(); self.release.clear()
                    def hold(rows):
                        entered.set(); self.release.wait(3); rows.reverse()
                    with patch.object(support.backend.random, 'shuffle', side_effect=hold):
                        self.assertTrue(self.shuffle(kind)); self.until(entered.is_set)
                        self.assertFalse(self.shuffle(kind))
                        if change == 'stop': self.b.stopPlayback()
                        elif change == 'new':
                            self.b.playFrom('playing', 1); self.until(lambda: self.b.playerState == 'playing')
                        elif kind == 'songs': self.b._library_section = 'songs'
                        else: self.b.clearDetail()
                        queue = self.b._queue; count = len(self.started)
                        self.release.set(); self.until(lambda: not self.b.busy)
                    self.assertIs(self.b._queue, queue)
                    self.assertEqual(len(self.started), count)

    def test_large_artist_retains_more_than_previous_library_limit(self):
        self.api.get_library_upload_artist.return_value = [dict(self.source[i % 4], title=str(i)) for i in range(2101)]
        self.load('artist'); self.play_shuffle('artist')
        self.assertEqual(self.b.playerQueueCount, 2101)
        self.assertEqual(sorted(self.b._queue_source_indices), list(range(2101)))
        self.api.get_library_upload_artist.assert_called_once_with('upload-artist', limit=None)
        self.api.get_watch_playlist.assert_not_called()

    def test_unavailable_and_missing_id_are_excluded_and_empty_sources_disabled(self):
        for kind in ('songs', 'album', 'artist'):
            with self.subTest(kind=kind):
                rows = [self.source[0], dict(self.source[1], isAvailable=False), {'title': 'No ID'}]
                self.api.get_library_upload_songs.return_value = rows
                self.api.get_library_upload_album.return_value['tracks'] = rows
                self.api.get_library_upload_artist.return_value = rows
                self.load(kind); self.play_shuffle(kind)
                self.assertEqual(self.b.playerQueueCount, 1)
                self.b._source_model('library' if kind == 'songs' else 'detail').clear()
                self.assertFalse(self.shuffle(kind))
        self.b._library_section = 'songs'; self.b.clearDetail()
        self.assertFalse(self.b.shuffleUploadSongs())
