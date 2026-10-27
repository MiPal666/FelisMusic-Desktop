"""Finite shuffled watch stream: account/audio mocked, real GUI queue logic."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock, patch
import test_prefetch as support


class ShufflePagingTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock(); self.b._ytmusic = self.api
        self.source = [self.song(v) for v in ('A', 'B', 'C')]
        self.pages = [([self.song('C'), self.song('A')], True),
                      ([self.song('B'), self.song('C')], True), ([self.song('D')], False)]
        self.entered = Event(); self.reads = []
        self.api.get_playlist.return_value = dict(title='Playlist', tracks=self.source)
        self.api.get_album.return_value = dict(title='Album', audioPlaylistId='OLAKalbum', tracks=self.source)
        self.api.get_artist.return_value = dict(name='Artist', shuffleId='RDAartist', songs={'results': self.source})
        self.api.get_watch_playlist.side_effect = lambda **kwargs: {'tracks': deepcopy(self.pages[0][0])}
        owner = self
        class Pages:
            def __init__(self, api, pid, *, shuffle=True, limit=None):
                self.api, self.pid, self.shuffle, self.index = api, pid, shuffle, 0
            def next_page(self):
                owner.reads.append((self.pid, self.index))
                if self.index == 0:
                    kwargs = dict(playlistId=self.pid, limit=0)
                    if self.shuffle: kwargs['shuffle'] = True
                    self.api.get_watch_playlist(**kwargs)
                else:
                    owner.entered.set(); owner.release.wait(3)
                value = owner.pages[self.index]; self.index += 1
                if isinstance(value, Exception): raise value
                return deepcopy(value)
        patcher = patch.object(support.backend, 'WatchPages', Pages)
        patcher.start(); self.addCleanup(patcher.stop)

    @staticmethod
    def song(vid):
        return dict(videoId=vid, title=vid, duration='3:00', likeStatus='LIKE')

    def start_shuffle(self, source='album'):
        if source == 'liked':
            self.b._liked_model.set_items([self.b._track(x) for x in self.source])
            self.assertTrue(self.b.startLikedPlayback('shuffle'))
        elif source == 'artist':
            self.b.openLibraryItem('artist', 'UCartist', '', 'Artist')
            self.until(lambda: not self.b.busy)
            self.assertTrue(self.b.startArtistPlayback('shuffle'))
        else:
            if source == 'album': self.b.openLibraryItem('album', 'MPREalbum', '', 'Album')
            else: self.b.loadPlaylistTracks('PLsource', 'Playlist')
            self.until(lambda: not self.b.busy)
            self.assertTrue(self.b.shuffleDetail())
        self.until(lambda: self.entered.is_set() and not self.b.busy and self.b.playerState == 'playing')

    def finish(self):
        self.release.set(); self.until(lambda: not self.b.playerQueueLoading)

    def ids(self):
        return [x['videoId'] for x in self.b._queue.tracks]

    def test_first_block_starts_before_second_and_all_sources_keep_exact_order(self):
        for source, pid in (('album', 'OLAKalbum'), ('artist', 'RDAartist')):
            with self.subTest(source=source):
                self.release.clear(); self.entered.clear(); self.reads.clear(); self.api.get_watch_playlist.reset_mock()
                self.start_shuffle(source)
                self.assertEqual(self.ids(), ['C', 'A'])
                self.assertTrue(self.b.playerQueueLoading); self.assertFalse(self.b.playerCanShuffle)
                queue = self.b._queue; current = queue.current(); self.b._player_position = 42
                self.b.cycleRepeat(); repeat = self.b.playerRepeatMode
                self.finish()
                self.assertIs(self.b._queue, queue); self.assertIs(queue.current(), current)
                self.assertEqual(self.ids(), ['C', 'A', 'B', 'C', 'D'])
                self.assertEqual(self.b.playerPosition, 42); self.assertEqual(self.b.playerRepeatMode, repeat)
                self.assertFalse(queue.radio_active)
                self.assertEqual(self.reads, [(pid, 0), (pid, 1), (pid, 2)])
                self.assertEqual(self.api.get_watch_playlist.call_count, 1)
                self.b.stopPlayback()

    def test_cover_and_duplicate_occurrence_mapping_across_pages(self):
        self.b.playbackSourceCaptured.connect(lambda: self.b.setPlaybackSourceContext({'page': 1}))
        self.start_shuffle(); self.finish()
        self.assertEqual([x['_guiOrigin']['index'] for x in self.b._queue.tracks], [2, 0, 1, -1, -1])
        self.b.clearDetail(); self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual(self.b.detailTitle, 'Album')
        self.assertEqual([x['videoId'] for x in self.b.detailTracksModel.snapshot()], ['A', 'B', 'C'])
        self.b.playFrom('playing', 2); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerSourceContext['page'], 1)
        self.assertEqual(self.b.playerSourceIndex, 1)

    def test_tail_waits_and_next_block_resumes(self):
        self.start_shuffle(); self.b.playFrom('playing', 1); self.until(lambda: self.b.playerState == 'playing')
        self.eos(); self.assertTrue(self.b.playerWaitingForTracks)
        self.release.set(); self.until(lambda: self.b.playerVideoId == 'B' and self.b.playerState == 'playing')
        self.assertFalse(self.b.playerWaitingForTracks)

    def test_stop_cancels_wait_but_keeps_loading(self):
        self.start_shuffle(); self.b.playFrom('playing', 1); self.until(lambda: self.b.playerState == 'playing')
        self.eos(); self.b.stopPlayback(); self.finish()
        self.assertEqual(self.b.playerState, 'idle'); self.assertEqual(self.b.playerVideoId, 'A')
        self.assertEqual(self.ids(), ['C', 'A', 'B', 'C', 'D'])

    def test_paused_audio_and_manual_insertions_survive(self):
        self.start_shuffle(); current = self.b._queue.current()
        self.b._set_player_state('paused')
        self.b._library_items_model.set_items([self.b._track(self.song('manual'))])
        self.assertTrue(self.b.enqueueFrom('library', 0, True, {'page': 1}))
        manual = self.b._queue.tracks[1]
        self.finish()
        self.assertIs(self.b._queue.current(), current); self.assertIs(self.b._queue.tracks[1], manual)
        self.assertEqual(self.b.playerState, 'paused')
        self.assertEqual(self.ids(), ['C', 'manual', 'A', 'B', 'C', 'D'])

    def test_error_marks_prefix_incomplete_without_modal_or_autostart(self):
        self.pages[1] = TimeoutError('secret')
        self.start_shuffle(); self.b.playFrom('playing', 1); self.until(lambda: self.b.playerState == 'playing')
        self.eos(); self.finish()
        self.assertTrue(self.b.playerQueueIncomplete); self.assertFalse(self.b.playerWaitingForTracks)
        self.assertFalse(self.b.playerCanShuffle); self.assertFalse(self.errors)
        self.assertEqual(self.b.playerState, 'idle')

    def test_replacement_ignores_old_page_and_does_not_start_old_audio(self):
        self.start_shuffle(); self.start('other')
        queue = self.b._queue
        self.release.set(); self.until(lambda: self.reads[-1][1] == 1)
        for _ in range(10): self.app.processEvents()
        self.assertIs(self.b._queue, queue); self.assertEqual(self.ids(), ['other'])
        self.assertFalse(self.b.playerQueueLoading)

    def test_background_page_defers_while_foreground_busy_and_preserves_marker(self):
        self.start_shuffle(); marker = self.b._radio_queue_marker()
        self.b._set_busy(True)
        self.release.set(); self.until(lambda: self.reads[-1][1] == 1)
        for _ in range(10): self.app.processEvents()
        self.assertEqual(self.b._radio_queue_marker(), marker); self.assertTrue(self.b.busy)
        self.b._set_busy(False); self.until(lambda: not self.b.playerQueueLoading)
        self.assertEqual(self.ids(), ['C', 'A', 'B', 'C', 'D'])

    def test_repeat_all_waits_at_temporary_end_and_one_repeats_current(self):
        self.start_shuffle(); self.b.cycleRepeat()
        self.b.playFrom('playing', 1); self.until(lambda: self.b.playerState == 'playing')
        self.eos(); self.assertTrue(self.b.playerWaitingForTracks)
        self.release.set(); self.until(lambda: self.b.playerVideoId == 'B' and self.b.playerState == 'playing')
        self.until(lambda: not self.b.playerQueueLoading)
        self.b.playFrom('playing', 4); self.until(lambda: self.b.playerState == 'playing')
        self.eos(); self.until(lambda: self.b.playerVideoId == 'C' and self.b.playerState == 'playing')
        self.b.cycleRepeat(); self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, 'C'); self.assertEqual(self.b.playerRepeatMode, 'one')

    def test_empty_final_page_finishes_wait_without_restarting(self):
        self.pages[1] = ([], False)
        self.start_shuffle(); self.b.playFrom('playing', 1); self.until(lambda: self.b.playerState == 'playing')
        self.eos(); self.finish()
        self.assertFalse(self.b.playerWaitingForTracks); self.assertFalse(self.b.playerQueueIncomplete)
        self.assertEqual(self.b.playerState, 'idle')

    def test_empty_intermediate_and_unavailable_rows_keep_following_cursor(self):
        self.pages[1] = ([dict(self.song('bad'), isAvailable=False)], True)
        self.start_shuffle(); self.finish()
        self.assertEqual(self.ids(), ['C', 'A', 'D'])

    def test_first_failure_preserves_previous_audio_and_repeat(self):
        self.start('old'); queue = self.b._queue; self.b.cycleRepeat()
        self.pages[0] = ([], False)
        self.b.openLibraryItem('album', 'MPREalbum', '', 'Album'); self.until(lambda: not self.b.busy)
        self.assertTrue(self.b.shuffleDetail()); self.until(lambda: not self.b.busy)
        self.assertIs(self.b._queue, queue); self.assertEqual(self.b.playerRepeatMode, 'all')
        self.assertEqual(self.b.playerVideoId, 'old')

    def test_new_shuffle_wins_over_buffered_old_continuation(self):
        self.start_shuffle(); old = self.b._queue
        self.assertTrue(self.b.shuffleDetail())
        self.release.set()
        self.until(lambda: not self.b.busy and self.b._queue is not old and not self.b.playerQueueLoading)
        self.assertEqual(old.count(), 2)
        self.assertEqual(self.ids(), ['C', 'A', 'B', 'C', 'D'])
        self.assertEqual(self.api.get_watch_playlist.call_count, 2)

    def test_three_thousand_shuffled_rows_load_without_replacing_current(self):
        self.source = [self.song(str(i)) for i in range(3000)]
        self.api.get_album.return_value = dict(title='Large', audioPlaylistId='OLAKalbum', tracks=self.source)
        order = list(reversed(self.source))
        self.pages = [(order[n:n+100], n < 2900) for n in range(0, 3000, 100)]
        self.start_shuffle(); queue = self.b._queue; current = queue.current()
        self.assertEqual(queue.count(), 100)
        self.finish()
        self.assertIs(self.b._queue, queue); self.assertIs(queue.current(), current)
        self.assertEqual(self.ids(), [str(i) for i in reversed(range(3000))])
        self.assertEqual(self.api.get_watch_playlist.call_count, 1)
        self.assertEqual(self.b.playerSourceIndex, 2999)
