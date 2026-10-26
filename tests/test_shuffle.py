"""YTM collection shuffle: real helper, mocked account and audio transport."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock
import test_prefetch as support


class ShuffleTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock()
        self.b._ytmusic = self.api
        self.songs = [self.song(v) for v in ('A', 'B', 'C')]
        self.api.get_playlist.return_value = dict(title='Playlist', owned=True, tracks=self.songs)
        self.api.get_album.return_value = dict(title='Album', audioPlaylistId='OLAKalbum', tracks=self.songs)
        self.block = [self.song(v) for v in ('C', 'A', 'B')]
        self.entered = Event()
        self.block_request = False
        self.api.get_watch_playlist.side_effect = self.watch

    @staticmethod
    def song(vid):
        return dict(videoId=vid, title=vid, duration='3:00', likeStatus='LIKE')

    def watch(self, **kwargs):
        self.entered.set()
        if self.block_request:
            self.release.wait(3)
        return {'tracks': deepcopy(self.block)}

    def ready(self):
        self.until(lambda: not self.b.busy)

    def playlist(self, pid='PLsource'):
        self.b.loadPlaylistTracks(pid, 'Playlist')
        self.ready()

    def ids(self):
        return [x['videoId'] for x in self.b._queue.tracks]

    def shuffle(self):
        self.assertTrue(self.b.shuffleDetail())
        self.ready()
        self.until(lambda: self.b.playerState == 'playing')

    def test_server_order_queue_mapping_cover_prefetch_and_repeat(self):
        self.playlist()
        self.b._repeat_mode = 'all'
        self.shuffle()
        self.api.get_watch_playlist.assert_called_once_with(playlistId='PLsource', limit=25, shuffle=True)
        self.assertEqual(self.ids(), ['C', 'A', 'B'])
        self.assertEqual([x['videoId'] for x in self.b.playingTracksModel.snapshot()], self.ids())
        self.assertEqual(self.b.playerSourceIndex, 2)
        self.assertEqual(self.b.playerQueueIndex, 0)
        self.assertEqual(self.b._queue.source_playlist_id, 'PLsource')
        self.assertTrue(self.b._queue.shuffle_active)
        self.assertFalse(self.b._queue.radio_active)
        self.assertEqual(self.b.playerRepeatMode, 'all')
        self.until(lambda: 'A' in support.core.LOCAL_AUDIO_CACHE)
        self.b.clearDetail()
        self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual(self.b.detailTitle, 'Playlist')
        self.assertEqual([x['videoId'] for x in self.b.detailTracksModel.snapshot()], ['A', 'B', 'C'])
        for expected in ('A', 'B', 'C'):
            self.eos()
            self.until(lambda: self.b.playerState == 'playing')
            self.assertEqual(self.b.playerVideoId, expected)
        self.assertEqual(self.played, ['C', 'A', 'B', 'C'])

    def test_album_uses_audio_playlist_id_and_previous_selection_repeat_one(self):
        self.b.openLibraryItem('album', 'MPREalbum', '', 'Album'); self.ready()
        self.assertTrue(self.b.detailCanShuffle)
        self.b._repeat_mode = 'one'
        self.shuffle()
        self.api.get_watch_playlist.assert_called_once_with(playlistId='OLAKalbum', limit=25, shuffle=True)
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['C', 'C'])
        self.b.playFrom('playing', 2); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, 'B')
        self.b.previousTrack(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, 'A')
        self.assertEqual(self.ids(), ['C', 'A', 'B'])

    def test_replaces_audio_only_after_success_and_keeps_repeat(self):
        self.start('old', 'next'); old = self.b._queue
        self.playlist(); self.b._repeat_mode = 'one'
        self.block_request = True
        self.assertTrue(self.b.shuffleDetail()); self.until(self.entered.is_set)
        self.assertIs(self.b._queue, old)
        self.assertEqual(self.played, ['old'])
        self.release.set(); self.ready(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['old', 'C'])
        self.assertEqual(self.b.playerRepeatMode, 'one')
        self.assertIn(True, self.stops)

    def test_empty_and_failed_response_leave_old_audio_and_queue(self):
        self.start('old', 'next'); old = self.b._queue
        self.playlist()
        self.block = []
        self.b.shuffleDetail(); self.ready()
        self.api.get_watch_playlist.side_effect = RuntimeError('Offline')
        self.b.shuffleDetail(); self.ready()
        self.assertIs(self.b._queue, old)
        self.assertEqual(self.played, ['old'])
        self.assertEqual(len(self.errors), 2)

    def test_server_filtering_duplicates_and_unmatched_source_index(self):
        self.playlist()
        self.block = [self.song('C'), dict(self.song('bad'), isAvailable=False),
                      {'title': 'No ID'}, self.song('C'), self.song('X')]
        self.shuffle()
        self.assertEqual(self.ids(), ['C', 'C', 'X'])
        self.assertEqual(self.b._queue_source_indices, [2, -1, -1])
        self.assertTrue(all('_guiPlaylistBinding' not in x for x in self.b._queue.tracks))

    def test_unsupported_curated_empty_missing_album_id_upload_and_artist(self):
        self.playlist('RDCLAKunsupported')
        self.assertFalse(self.b.detailCanShuffle)
        self.assertFalse(self.b.shuffleDetail())
        self.api.get_album.return_value.pop('audioPlaylistId')
        self.b.openLibraryItem('album', 'MPRE', '', 'Album'); self.ready()
        self.assertFalse(self.b.detailCanShuffle)
        for meta in ({'kind': 'upload_album', 'shufflePlaylistId': 'fake'},
                     {'kind': 'artist', 'shufflePlaylistId': 'fake'}):
            self.b._detail_meta = meta
            self.assertFalse(self.b.shuffleDetail())
        self.api.get_playlist.return_value['tracks'] = []
        self.playlist()
        self.assertFalse(self.b.detailCanShuffle)
        self.assertFalse(self.b.shuffleDetail())
        self.api.get_watch_playlist.assert_not_called()

    def test_busy_and_double_submission(self):
        self.playlist(); self.block_request = True
        self.assertTrue(self.b.shuffleDetail()); self.until(self.entered.is_set)
        self.assertFalse(self.b.shuffleDetail())
        self.release.set(); self.ready()
        self.assertEqual(self.api.get_watch_playlist.call_count, 1)

    def test_long_playlist_requests_its_size_and_repeat_off_stops_at_end(self):
        self.api.get_playlist.return_value['tracks'] = [self.song(str(i)) for i in range(80)]
        self.block = [self.song('79'), self.song('42')]
        self.playlist(); self.shuffle()
        self.api.get_watch_playlist.assert_called_once_with(playlistId='PLsource', limit=80, shuffle=True)
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, '42')
        self.eos()
        self.assertEqual(self.b.playerState, 'idle')
        self.assertEqual(self.ids(), ['79', '42'])

    def test_stop_next_queue_edit_and_navigation_supersede_pending_result(self):
        for change in ('stop', 'next', 'enqueue', 'navigate'):
            with self.subTest(change=change):
                self.start('old', 'next'); old = self.b._queue
                self.playlist(); self.entered.clear(); self.release.clear()
                self.block_request = True
                self.b.shuffleDetail(); self.until(self.entered.is_set)
                if change == 'stop':
                    self.b.stopPlayback()
                elif change == 'next':
                    self.b.nextTrack(); self.until(lambda: self.b.playerState == 'playing')
                elif change == 'enqueue':
                    self.b.enqueueFrom('detail', 1, False, {})
                else:
                    self.b.clearDetail()
                self.release.set(); self.ready()
                self.assertIs(self.b._queue, old)
                self.assertNotIn('C', self.played)

    def test_stale_failure_is_silent(self):
        self.start('old'); self.playlist(); self.block_request = True; self.block = []
        self.b.shuffleDetail(); self.until(self.entered.is_set)
        self.b.stopPlayback(); self.release.set(); self.ready()
        self.assertFalse(self.errors)
