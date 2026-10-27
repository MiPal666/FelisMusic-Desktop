"""In-place local shuffle with exact GUI occurrences and fake audio/API."""
from threading import Event
from unittest.mock import Mock, patch
import test_prefetch as support


class QueueShuffleTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock(); self.b._ytmusic = self.api
        self.songs = [dict(videoId=v, title=v, setVideoId='set-'+str(i),
                           duration='3:00', likeStatus='LIKE')
                      for i, v in enumerate(('A', 'B', 'C', 'D'))]
        self.api.get_playlist.return_value = dict(title='Mine', owned=True, tracks=self.songs)
        self.api.get_album.return_value = dict(title='Album', audioPlaylistId='OLAKalbum', tracks=self.songs)
        self.entered = Event(); self.block_request = False; self.fail_shuffle = False
        mixer = patch.object(support.backend.random, 'shuffle', side_effect=self.mix)
        mixer.start(); self.addCleanup(mixer.stop)

    def mix(self, rows):
        self.entered.set()
        if self.block_request:
            self.release.wait(3)
        if self.fail_shuffle:
            raise RuntimeError('Test failure')
        rows.reverse()

    @staticmethod
    def song(vid):
        return dict(videoId=vid, title=vid)

    def ready(self):
        self.until(lambda: not self.b.busy)

    def play_detail(self, index=1, album=False):
        if album:
            self.b.openLibraryItem('album', 'MPREalbum', '', 'Album')
        else:
            self.b.loadPlaylistTracks('PLmine', 'Mine')
        self.ready(); self.b.playFrom('detail', index)
        self.until(lambda: self.b.playerState == 'playing')

    def ids(self):
        return [x['videoId'] for x in self.b._queue.tracks]

    def test_keep_current_audio_time_rating_repeat_origin_and_retarget_prefetch(self):
        self.blocked.add('C'); self.play_detail()
        self.until(lambda: self.downloads['C'] == 1)
        queue = self.b._queue; current = queue.current(); origin = current['_guiOrigin']
        self.b._player_position = 67; self.b._player_like_status = 'DISLIKE'
        self.b.cycleRepeat()
        events = []; self.b.playerTrackChanged.connect(lambda: events.append(True))
        before = (len(self.stops), len(self.played), self.b._playback_generation)
        self.assertTrue(self.b.shuffleQueue()); self.ready()
        self.assertIs(self.b._queue, queue); self.assertIs(queue.current(), current)
        self.assertEqual(self.ids(), ['B', 'D', 'C', 'A'])
        self.assertEqual(self.b.playerQueueIndex, 0)
        self.assertEqual(self.b.playerSourceIndex, 1)
        self.assertEqual(self.b.playerPosition, 67)
        self.assertEqual(self.b._player_like_status, 'DISLIKE')
        self.assertEqual(self.b.playerRepeatMode, 'all')
        self.assertIs(current['_guiOrigin'], origin)
        self.assertEqual((len(self.stops), len(self.played), self.b._playback_generation), before)
        self.assertFalse(events)
        self.api.get_watch_playlist.assert_not_called()
        self.until(lambda: 'C' in self.cancelled)
        self.until(lambda: 'D' in support.core.LOCAL_AUDIO_CACHE)
        self.b.clearDetail(); self.b.restorePlayingSource(1)
        self.assertEqual([x['videoId'] for x in self.b.detailTracksModel.snapshot()], ['A', 'B', 'C', 'D'])
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['B', 'D'])

    def test_paused_album_keeps_pause_and_repeat_one(self):
        self.play_detail(album=True)
        self.status.player_state = 'PAUSED'; self.b._player_state = 'paused'
        self.b._player_position = 37; self.b.cycleRepeat(); self.b.cycleRepeat()
        self.assertTrue(self.b.shuffleQueue()); self.ready()
        self.assertEqual(self.b.playerState, 'paused')
        self.assertEqual(self.b.playerPosition, 37)
        self.assertEqual(self.b.playerRepeatMode, 'one')
        self.assertEqual(self.played, ['B'])
        self.api.get_watch_playlist.assert_not_called()

    def test_stopped_queue_is_reordered_without_starting_audio(self):
        self.play_detail(); self.b.stopPlayback(); self.b.cycleRepeat()
        self.assertTrue(self.b.shuffleQueue()); self.ready()
        self.assertEqual(self.b.playerState, 'idle'); self.assertEqual(self.b.playerPosition, 0)
        self.assertEqual(self.b.playerRepeatMode, 'all'); self.assertEqual(self.played, ['B'])

    def test_manual_insertions_and_duplicates_keep_exact_objects(self):
        self.songs.insert(2, dict(self.songs[1], setVideoId='duplicate-B'))
        self.play_detail()
        self.b._search_results_model.set_items([dict(kind='song', videoId='B', title='Manual B'),
                                                dict(kind='song', videoId='X', title='Manual X')])
        self.b.enqueueFrom('search', 0, True, {'page': 0})
        self.b.enqueueFrom('search', 1, False, {'page': 0})
        originals = list(self.b._queue.tracks); current = self.b._queue.current()
        with patch.object(support.backend.random, 'shuffle', side_effect=lambda items: items.reverse()):
            self.assertTrue(self.b.shuffleQueue()); self.ready()
        self.assertEqual(self.ids(), ['B', 'X', 'D', 'C', 'B', 'B', 'A'])
        self.assertEqual({id(x) for x in self.b._queue.tracks}, {id(x) for x in originals})
        self.assertIs(self.b._queue.current(), current)
        self.assertEqual([x['setVideoId'] for x in self.b._queue.tracks if x.get('setVideoId')],
                         ['set-1', 'set-3', 'set-2', 'duplicate-B', 'set-0'])
        self.assertTrue(all(x['_guiOrigin']['context'] == {'page': 0}
                            for x in self.b._queue.tracks if x.get('_guiManualEnqueue')))

    def test_manual_items_join_shuffle_for_normal_shuffled_playing_paused_and_stopped_queues(self):
        for already_shuffled in (False, True):
            for state in ('playing', 'paused', 'idle'):
                with self.subTest(already_shuffled=already_shuffled, state=state):
                    self.play_detail()
                    if already_shuffled:
                        self.b.shuffleQueue(); self.ready()
                    self.b._search_results_model.set_items([
                        dict(kind='song', title=vid, videoId=vid) for vid in ('X', 'Y')])
                    self.b.enqueueFrom('search', 0, True, {'page': 0})
                    self.assertEqual(self.b._queue.tracks[self.b._queue.index + 1]['videoId'], 'X')
                    self.b.enqueueFrom('search', 1, False, {'page': 0})
                    self.assertEqual(self.b._queue.tracks[-1]['videoId'], 'Y')
                    self.b.cycleRepeat(); self.b.cycleRepeat()
                    self.b._player_position = 41
                    if state == 'paused':
                        self.status.player_state = 'PAUSED'; self.b._player_state = 'paused'
                    elif state == 'idle':
                        self.b.stopPlayback()
                    queue = self.b._queue; current = queue.current()
                    originals = {id(x) for x in queue.tracks}
                    before = (len(self.played), len(self.stops), self.b.playerPosition)
                    expected = [current, *reversed([song for song in queue.tracks if song is not current])]
                    with patch.object(support.backend.random, 'shuffle', side_effect=lambda items: items.reverse()):
                        self.assertTrue(self.b.shuffleQueue()); self.ready()
                    self.assertEqual(queue.tracks, expected)
                    self.assertIs(self.b._queue, queue); self.assertIs(queue.current(), current)
                    self.assertEqual({id(x) for x in queue.tracks}, originals)
                    self.assertEqual(self.b.playerState, state)
                    self.assertEqual(self.b.playerRepeatMode, 'one')
                    self.assertEqual((len(self.played), len(self.stops), self.b.playerPosition), before)

    def test_current_manual_occurrence_is_pinned_while_other_manual_copies_mix(self):
        self.play_detail()
        self.b._search_results_model.set_items([dict(kind='song', title='Manual', videoId='X')])
        self.b.enqueueFrom('search', 0, True, {})
        self.b.enqueueFrom('search', 0, False, {})
        self.b.nextTrack(); self.until(lambda: self.b.playerState == 'playing')
        queue = self.b._queue; current = queue.current()
        originals = {id(x) for x in queue.tracks}; plays = len(self.played)
        self.b.shuffleQueue(); self.ready()
        self.assertIs(queue.current(), current)
        self.assertEqual(self.ids(), ['X', 'X', 'D', 'C', 'B', 'A'])
        self.assertEqual({id(x) for x in queue.tracks}, originals)
        self.assertEqual(len(self.played), plays)

    def test_repeat_shuffle_uses_same_queue_and_occurrences_each_time(self):
        self.play_detail(); queue = self.b._queue
        original = {id(x) for x in queue.tracks}
        for _ in range(2):
            expected = ['B', *reversed([song['videoId'] for i, song in enumerate(queue.tracks) if i != queue.index])]
            self.assertTrue(self.b.shuffleQueue()); self.ready()
            self.assertEqual(self.ids(), expected)
            self.assertIs(self.b._queue, queue)
            self.assertEqual({id(x) for x in queue.tracks}, original)
        self.assertEqual(self.played, ['B'])

    def test_duplicate_occurrences_retain_their_edit_identity(self):
        self.songs.insert(2, dict(self.songs[0], setVideoId='duplicate-A'))
        self.play_detail(); self.b.shuffleQueue(); self.ready()
        self.assertEqual(self.ids(), ['B', 'D', 'C', 'A', 'A'])
        self.assertEqual([x['setVideoId'] for x in self.b._queue.tracks],
                         ['set-1', 'set-3', 'set-2', 'duplicate-A', 'set-0'])

    def test_already_random_collection_can_be_reshuffled(self):
        self.b.loadPlaylistTracks('PLmine', 'Mine'); self.ready()
        with patch.object(support.backend.random, 'shuffle', side_effect=lambda rows: rows.reverse()):
            self.b.shuffleDetail(); self.ready(); self.until(lambda: self.b.playerState == 'playing')
        current = self.b._queue.current()
        self.b.shuffleQueue(); self.ready()
        self.assertIs(self.b._queue.current(), current)
        self.assertEqual(self.ids(), ['D', 'A', 'B', 'C'])
        self.assertEqual(self.played, ['D'])

    def test_failure_preserves_queue_audio_and_repeat(self):
        self.play_detail(); queue = self.b._queue; original = list(queue.tracks)
        self.b.cycleRepeat(); self.fail_shuffle = True
        self.b.shuffleQueue(); self.ready()
        self.assertIs(self.b._queue, queue); self.assertEqual(queue.tracks, original)
        self.assertEqual(queue.index, 1); self.assertEqual(self.b.playerRepeatMode, 'all')
        self.assertEqual(len(self.errors), 1); self.assertEqual(self.played, ['B'])

    def test_stop_next_new_playback_and_enqueue_supersede_pending_result(self):
        for change in ('stop', 'next', 'new', 'enqueue'):
            with self.subTest(change=change):
                self.release.clear(); self.entered.clear(); self.block_request = True
                self.play_detail(); queue = self.b._queue
                self.b.shuffleQueue(); self.until(self.entered.is_set)
                self.assertFalse(self.b.shuffleQueue())
                if change == 'stop':
                    self.b.stopPlayback()
                elif change == 'next':
                    self.b.nextTrack(); self.until(lambda: self.b.playerState == 'playing')
                elif change == 'new':
                    self.b.playFrom('detail', 0); self.until(lambda: self.b.playerState == 'playing')
                else:
                    self.b.enqueueFrom('detail', 0, False, {})
                expected = list(self.b._queue.tracks)
                self.release.set(); self.ready()
                self.assertEqual(self.b._queue.tracks, expected)
                self.assertFalse(queue.shuffle_active)

    def test_navigation_and_pause_during_lookup_do_not_cancel_shuffle(self):
        self.play_detail(); self.block_request = True
        self.b.shuffleQueue(); self.until(self.entered.is_set)
        self.b.clearDetail(); self.status.player_state = 'PAUSED'; self.b._player_state = 'paused'
        self.release.set(); self.ready()
        self.assertEqual(self.ids(), ['B', 'D', 'C', 'A'])
        self.assertEqual(self.b.playerState, 'paused')

    def test_stale_failure_is_silent(self):
        self.play_detail(); self.block_request = True; self.fail_shuffle = True
        self.b.shuffleQueue(); self.until(self.entered.is_set)
        self.b.stopPlayback(); self.release.set(); self.ready()
        self.assertFalse(self.errors)

    def test_local_sources_supported_but_radio_deleted_and_transition_are_disabled(self):
        self.assertFalse(self.b.shuffleQueue())
        self.start('A', 'B'); self.assertTrue(self.b.playerCanShuffle)
        self.play_detail(); queue = self.b._queue
        for pid in (None, '', 'RDCLAKunsupported'):
            queue.source_playlist_id = pid
            self.assertTrue(self.b.playerCanShuffle)
        queue.source_playlist_id = 'PLmine'
        queue.radio_active = True; self.assertFalse(self.b.shuffleQueue())
        queue.radio_active = False
        self.b._deleted_playlists.add('PLmine'); self.assertFalse(self.b.shuffleQueue())
        self.b._deleted_playlists.clear()
        self.b._playback_transitioning = True; self.assertFalse(self.b.shuffleQueue())
        self.b._playback_transitioning = False
        queue.current()['_guiRemoveAfterPlayback'] = True; self.assertFalse(self.b.shuffleQueue())
        self.api.get_watch_playlist.assert_not_called()

    def test_saved_playlist_reorder_does_not_undo_shuffle_but_exact_removal_still_syncs(self):
        self.play_detail(); self.b.shuffleQueue(); self.ready()
        self.api.edit_playlist.return_value = 'STATUS_SUCCEEDED'
        self.api.remove_playlist_items.return_value = 'STATUS_SUCCEEDED'
        self.b.moveDetailPlaylistItem('A', 'set-0', 1); self.ready()
        self.assertEqual(self.ids(), ['B', 'D', 'C', 'A'])
        self.b.removeDetailPlaylistItem('A', 'set-0'); self.ready()
        self.assertEqual(self.ids(), ['B', 'D', 'C'])
        self.assertEqual(self.played, ['B'])

    def test_artist_or_manual_queue_without_source_id_can_be_shuffled_without_api(self):
        self.play_detail(); self.b._queue.source_playlist_id = None
        self.b._ytmusic = None
        self.assertTrue(self.b.playerCanShuffle)
        self.assertTrue(self.b.shuffleQueue()); self.ready()
        self.assertEqual(self.ids(), ['B', 'D', 'C', 'A'])
        self.api.get_watch_playlist.assert_not_called()

    def test_large_queue_keeps_all_objects_and_bindings_without_network(self):
        self.songs[:] = [dict(videoId=str(i % 2000), title=str(i),
                             setVideoId=f'set-{i}', likeStatus='LIKE') for i in range(2200)]
        self.play_detail(index=300)
        queue = self.b._queue; current = queue.current(); original = list(queue.tracks)
        before = (len(self.played), len(self.stops), self.b._playback_generation)
        self.assertTrue(self.b.shuffleQueue()); self.ready()
        self.assertIs(queue.current(), current)
        expected = [current, *reversed(original[:300] + original[301:])]
        self.assertTrue(all(a is b for a, b in zip(queue.tracks, expected)))
        self.assertEqual(queue.count(), 2200)
        self.assertEqual(len({x['_guiPlaylistBinding'] for x in queue.tracks}), 2200)
        self.assertEqual((len(self.played), len(self.stops), self.b._playback_generation), before)
        self.api.get_playlist.assert_called_once()
        self.api.get_watch_playlist.assert_not_called()

    def test_loading_and_incomplete_queues_are_not_shuffled(self):
        self.play_detail()
        for state in ('loading', 'error'):
            self.b._watch_stream = dict(queue=self.b._queue, state=state)
            self.assertFalse(self.b.playerCanShuffle)
            self.assertFalse(self.b.shuffleQueue())
        self.b._watch_stream = None
