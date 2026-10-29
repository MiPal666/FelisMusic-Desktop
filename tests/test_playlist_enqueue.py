"""Whole finite playlist insertion, without API writes or audio interruption."""
from copy import deepcopy
from unittest.mock import Mock
import test_prefetch as support


class PlaylistEnqueueTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock()
        self.b._ytmusic = self.api
        self.context = dict(page=1, librarySection='playlists', libraryLabel='Playlisty')
        self.rows = [dict(videoId=vid, title=vid, setVideoId=f'set-{i}', likeStatus='LIKE',
                          artists=[dict(id='UCartist', name='Artist')])
                     for i, vid in enumerate(('X', 'Y', 'X'))]
        self.api.get_playlist.return_value = dict(title='Playlist', owned=False, tracks=deepcopy(self.rows))

    def open_playlist(self):
        self.b.loadPlaylistTracks('PLsource', 'Playlist')
        self.until(lambda: not self.b.busy and self.b.detailComplete)

    def ids(self):
        return [x['videoId'] for x in self.b._queue.tracks]

    def test_next_append_duplicates_and_audio_unchanged(self):
        for next_ in (True, False):
            with self.subTest(next=next_):
                self.start('A', 'B', 'C')
                self.b.nextTrack(); self.until(lambda: self.b.playerState == 'playing')
                self.open_playlist()
                self.b._player_position = 42
                self.b._repeat_mode = 'one'; self.b._queue.radio_active = True
                queue = self.b._queue
                played, stops, calls = list(self.played), list(self.stops), list(self.api.mock_calls)
                self.assertTrue(self.b.detailCanEnqueuePlaylist)
                self.assertTrue(self.b.enqueuePlaylistCollection(next_, self.context))
                self.assertEqual(self.ids(), ['A', 'B', 'X', 'Y', 'X', 'C'] if next_ else ['A', 'B', 'C', 'X', 'Y', 'X'])
                self.assertIs(self.b._queue, queue)
                self.assertEqual(self.b.playerQueueIndex, 1)
                self.assertEqual(self.b.playerPosition, 42)
                self.assertEqual(self.b.playerRepeatMode, 'one')
                self.assertTrue(queue.radio_active)
                self.assertEqual(self.played, played); self.assertEqual(self.stops, stops)
                self.assertEqual(self.api.mock_calls, calls)

    def test_cover_restores_exact_duplicate_and_playlist_without_reload(self):
        self.start('A', 'B'); self.open_playlist()
        state = self.b._detail_state()
        self.assertTrue(self.b.enqueuePlaylistCollection(True, self.context))
        self.assertEqual([x['setVideoId'] for x in self.b._queue.tracks[1:4]], ['set-0', 'set-1', 'set-2'])
        self.b.playFrom('playing', 3); self.until(lambda: self.b.playerState == 'playing')
        self.b.clearDetail(); self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual(self.b._detail_state(), state)
        self.assertEqual(self.b.playerSourceIndex, 2)
        self.assertEqual(self.b.playerSourceContext, self.context)
        self.api.get_playlist.assert_called_once_with('PLsource', limit=0)

    def test_empty_queue_pause_stop_and_repeated_insertions(self):
        self.open_playlist()
        self.assertTrue(self.b.enqueuePlaylistCollection(False, self.context))
        self.assertEqual(self.ids(), ['X', 'Y', 'X'])
        self.assertFalse(self.played); self.assertEqual(self.b.playerState, 'idle')
        self.b.togglePlayPause(); self.until(lambda: self.b.playerState == 'playing')
        self.b._player_state = 'paused'; played = list(self.played)
        self.assertTrue(self.b.enqueuePlaylistCollection(True, self.context))
        self.assertEqual(self.b.playerState, 'paused'); self.assertEqual(self.played, played)
        self.b.stopPlayback()
        self.assertTrue(self.b.enqueuePlaylistCollection(False, self.context))
        self.assertEqual(self.b.playerState, 'idle'); self.assertEqual(self.played, played)
        self.assertEqual(len(self.ids()), 9)

    def test_guards_incomplete_error_dynamic_wrong_kind_empty_and_transport(self):
        self.start('A'); self.open_playlist()
        for change in (dict(playlistLoadState='loading'), dict(playlistLoadState='error'),
                       dict(dynamicMix=True), dict(kind='album'), dict(kind='upload_album'), dict(kind='artist')):
            original = deepcopy(self.b._detail_meta)
            self.b._detail_meta.update(change)
            self.assertFalse(self.b.detailCanEnqueuePlaylist)
            self.assertFalse(self.b.enqueuePlaylistCollection(True, self.context))
            self.b._detail_meta = original
        for attr in ('_busy', '_playback_transitioning'):
            setattr(self.b, attr, True)
            self.assertFalse(self.b.enqueuePlaylistCollection(False, self.context))
            setattr(self.b, attr, False)
        self.b._detail_tracks_model.clear()
        self.assertFalse(self.b.detailCanEnqueuePlaylist)
        self.assertFalse(self.b.enqueuePlaylistCollection(False, self.context))
        self.assertEqual(self.ids(), ['A'])
