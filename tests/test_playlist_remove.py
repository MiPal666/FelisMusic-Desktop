"""Remove one exact playlist occurrence; preserve playback and browsing origins."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock
import test_prefetch as support


class PlaylistRemoveTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock(); self.b._ytmusic = self.api
        self.data = dict(title='Mine', owned=True, tracks=[
            dict(videoId='A', title='Same', setVideoId='first'),
            dict(videoId='hidden', title='Unavailable', setVideoId='hidden', isAvailable=False),
            dict(videoId='A', title='Same', setVideoId='second'),
            dict(videoId='B', title='Other', setVideoId='third')])
        self.api.get_playlist.side_effect = lambda *a, **kw: deepcopy(self.data)
        self.api.remove_playlist_items.side_effect = self.remove

    def remove(self, playlist_id, videos):
        ids = {x['setVideoId'] for x in videos}
        self.data['tracks'] = [x for x in self.data['tracks'] if x['setVideoId'] not in ids]
        return 'STATUS_SUCCEEDED'

    def ready(self):
        self.until(lambda: not self.b.busy)

    def load(self):
        self.b.loadPlaylistTracks('mine', 'Mine'); self.ready()

    def test_exact_duplicate_after_filtering_unavailable_rows(self):
        self.load()
        rows = self.b.detailTracksModel.snapshot()
        self.assertEqual([x['setVideoId'] for x in rows], ['first', 'second', 'third'])
        resets = []; self.b.detailTracksModel.modelReset.connect(lambda: resets.append(True))
        self.assertTrue(self.b.removeDetailPlaylistItem('A', 'second')); self.ready()
        self.assertFalse(resets)
        self.api.remove_playlist_items.assert_called_once_with('mine', [{'videoId': 'A', 'setVideoId': 'second'}])
        self.assertEqual([x['setVideoId'] for x in self.data['tracks']], ['first', 'hidden', 'third'])
        self.assertEqual([x['setVideoId'] for x in self.b.detailTracksModel.snapshot()], ['first', 'third'])
        self.assertTrue(self.b.detailCanEditPlaylist)

    def test_no_queue_or_audio_changes_and_cover_restores_updated_list(self):
        self.load(); self.b.playFrom('detail', 1); self.until(lambda: self.b.playerState == 'playing')
        queue = self.b._queue; stops = len(self.stops)
        self.b._player_position = 44
        original_tracks = list(queue.tracks)
        self.b.removeDetailPlaylistItem('A', 'second'); self.ready()
        self.assertIs(self.b._queue, queue)
        self.assertEqual(queue.tracks, original_tracks)
        self.assertEqual(self.b.playerPosition, 44)
        self.assertEqual(self.b.playerSourceIndex, -1)
        self.assertEqual(self.b.playerQueueIndex, 1)
        self.assertEqual(self.played, ['A']); self.assertEqual(len(self.stops), stops)
        self.assertEqual(queue.tracks[0]['_guiOrigin']['index'], 0)
        self.assertEqual(queue.tracks[2]['_guiOrigin']['index'], 1)
        self.b.clearDetail()
        self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual([x['setVideoId'] for x in self.b.detailTracksModel.snapshot()], ['first', 'third'])
        self.assertEqual(self.b.detailTitle, 'Mine')
        self.assertEqual(self.b.playingTracksModel.count, 3)

    def test_fresh_ownership_and_occurrence_match_required(self):
        self.load()
        for mutate in ('foreign', 'changed_video', 'duplicate_id'):
            original = deepcopy(self.data)
            if mutate == 'foreign': self.data['owned'] = False
            elif mutate == 'changed_video': self.data['tracks'][2]['videoId'] = 'Different'
            else: self.data['tracks'].append(deepcopy(self.data['tracks'][2]))
            self.assertTrue(self.b.removeDetailPlaylistItem('A', 'second')); self.ready()
            self.api.remove_playlist_items.assert_not_called()
            self.assertEqual(self.b.detailTracksModel.count, 3)
            self.assertTrue(self.errors)
            self.data = original

    def test_missing_occurrence_only_refreshes_and_never_deletes_same_video(self):
        self.load()
        self.data['tracks'] = [x for x in self.data['tracks'] if x['setVideoId'] != 'second']
        self.b.removeDetailPlaylistItem('A', 'second'); self.ready()
        self.api.remove_playlist_items.assert_not_called()
        self.assertEqual([x['setVideoId'] for x in self.b.detailTracksModel.snapshot()], ['first', 'third'])

    def test_invalid_source_or_missing_identity_never_writes(self):
        self.load()
        for vid, sid in [('', 'first'), ('A', ''), ('B', 'first'), ('A', 'absent')]:
            self.assertFalse(self.b.removeDetailPlaylistItem(vid, sid))
        self.b._detail_meta['owned'] = False
        self.assertFalse(self.b.removeDetailPlaylistItem('A', 'first'))
        self.b._detail_meta = dict(kind='album', owned=True, playlistId='mine')
        self.assertFalse(self.b.removeDetailPlaylistItem('A', 'first'))
        self.api.remove_playlist_items.assert_not_called()

    def test_failed_read_status_and_unknown_write_do_not_change_display(self):
        self.load(); before = self.b.detailTracksModel.snapshot()
        self.api.get_playlist.side_effect = RuntimeError('private server response')
        self.b.removeDetailPlaylistItem('A', 'second'); self.ready()
        self.api.remove_playlist_items.assert_not_called()
        self.api.get_playlist.side_effect = lambda *a, **kw: deepcopy(self.data)
        for response in ('STATUS_FAILED', {'status': 'STATUS_FAILED'}, RuntimeError('private server response')):
            if isinstance(response, Exception): self.api.remove_playlist_items.side_effect = response
            else:
                self.api.remove_playlist_items.side_effect = None
                self.api.remove_playlist_items.return_value = response
            self.b.removeDetailPlaylistItem('A', 'second'); self.ready()
            self.assertEqual(self.b.detailTracksModel.snapshot(), before)
            self.assertNotIn('private server response', self.errors[-1])

    def test_double_submit_and_navigation_do_not_retarget_request(self):
        self.load(); entered = Event()
        def slow(*args, **kw):
            entered.set(); self.release.wait(3); return self.remove(*args, **kw)
        self.api.remove_playlist_items.side_effect = slow
        self.b.removeDetailPlaylistItem('A', 'second'); self.until(entered.is_set)
        self.assertFalse(self.b.removeDetailPlaylistItem('A', 'first'))
        # Simulate a view change while preserving the in-flight captured ID.
        self.b._detail_meta = dict(kind='playlist', playlistId='other', owned=True)
        self.b._detail_title = 'Other'
        self.release.set(); self.ready()
        self.api.remove_playlist_items.assert_called_once_with('mine', [{'videoId': 'A', 'setVideoId': 'second'}])
        self.assertEqual(self.b.detailTitle, 'Other')
        self.assertEqual(self.b.detailTracksModel.count, 3)

    def test_delayed_response_does_not_resurrect_removed_occurrence(self):
        self.load()
        self.api.remove_playlist_items.side_effect = None
        self.api.remove_playlist_items.return_value = {'status': 'STATUS_SUCCEEDED'}
        self.b.removeDetailPlaylistItem('A', 'second'); self.ready()
        self.load()  # Server still returns the old list.
        self.assertEqual([x['setVideoId'] for x in self.b.detailTracksModel.snapshot()], ['first', 'third'])
        self.data['tracks'] = [x for x in self.data['tracks'] if x['setVideoId'] != 'second']
        self.load()
        self.assertNotIn('mine', self.b._pending_removed_playlist_items)
        self.data['tracks'].append(dict(videoId='A', setVideoId='new-occurrence', title='Same'))
        self.load()
        self.assertEqual(self.b.detailTracksModel.snapshot()[-1]['setVideoId'], 'new-occurrence')

    def test_remove_last_song_keeps_empty_owned_detail(self):
        self.data['tracks'] = [self.data['tracks'][0]]; self.load()
        self.b.removeDetailPlaylistItem('A', 'first'); self.ready()
        self.assertEqual(self.b.detailTracksModel.count, 0)
        self.assertEqual(self.b.detailTitle, 'Mine')
        self.assertTrue(self.b.detailCanEditPlaylist)
        self.assertFalse(self.b.detailCanSavePlaylist)

    def test_uploaded_track_occurrence_is_also_removable(self):
        self.data['tracks'] = [dict(videoId='upload-id', setVideoId='upload-occurrence',
                                    title='Uploaded', resultType='upload_song')]
        self.load()
        self.assertTrue(self.b.removeDetailPlaylistItem('upload-id', 'upload-occurrence')); self.ready()
        self.api.remove_playlist_items.assert_called_once_with('mine', [
            {'videoId': 'upload-id', 'setVideoId': 'upload-occurrence'}])
        self.assertEqual(self.b.detailTracksModel.count, 0)

    def play_detail(self, index=0):
        self.load(); self.b.playFrom('detail', index)
        self.until(lambda: self.b.playerState == 'playing')

    def queue_ids(self):
        return [x['setVideoId'] for x in self.b._queue.tracks]

    def test_remove_waiting_occurrence_and_keep_manual_copy_of_same_song(self):
        self.play_detail()
        self.assertTrue(self.b.enqueueFrom('detail', 1, False, {}))
        manual = self.b._queue.tracks[-1]
        self.assertNotIn('_guiPlaylistBinding', manual)
        self.b._player_position = 45; stops = len(self.stops)
        self.b.removeDetailPlaylistItem('A', 'second'); self.ready()
        self.assertEqual(self.queue_ids(), ['first', 'third', 'second'])
        self.assertIs(self.b._queue.tracks[-1], manual)
        self.assertEqual(self.b.playerPosition, 45)
        self.assertEqual(self.played, ['A']); self.assertEqual(len(self.stops), stops)
        self.assertEqual(self.b.playingTracksModel.count, 3)
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['A', 'B'])

    def test_removing_row_before_current_preserves_audio_time_and_marker(self):
        self.play_detail(2); self.b._player_position = 67
        marker_events = []; self.b.playerTrackChanged.connect(lambda: marker_events.append(True))
        self.b.removeDetailPlaylistItem('A', 'first'); self.ready()
        self.assertEqual(self.queue_ids(), ['second', 'third'])
        self.assertEqual(self.b.playerQueueIndex, 1)
        self.assertEqual(self.b.playerPosition, 67)
        self.assertEqual(self.played, ['B'])
        self.assertFalse(marker_events)
        self.assertEqual(self.b._player_track_marker[1:], (1, 'B'))

    def test_current_finishes_once_even_in_repeat_one(self):
        self.play_detail(1)
        self.b.cycleRepeat(); self.b.cycleRepeat()
        self.b.removeDetailPlaylistItem('A', 'second'); self.ready()
        self.assertEqual(self.queue_ids(), ['first', 'second', 'third'])
        self.assertEqual(self.b._next_prefetch_id(), 'B')
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.queue_ids(), ['first', 'third'])
        self.assertEqual(self.played, ['A', 'B'])
        self.assertEqual(self.b.playerQueueIndex, 1)
        self.assertEqual(self.b.playerRepeatMode, 'one')
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['A', 'B', 'B'])

    def test_removed_last_track_wraps_in_repeat_all(self):
        self.play_detail(2); self.b.cycleRepeat()
        self.b.removeDetailPlaylistItem('B', 'third'); self.ready()
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.queue_ids(), ['first', 'second'])
        self.assertEqual(self.played, ['B', 'A'])
        self.assertEqual(self.b.playerQueueIndex, 0)

    def test_removed_last_track_does_not_replay_previous_in_repeat_off(self):
        self.play_detail(2)
        self.b.removeDetailPlaylistItem('B', 'third'); self.ready()
        self.eos()
        self.assertEqual(self.b.playerState, 'idle')
        self.assertEqual(self.queue_ids(), ['first', 'second'])
        self.assertEqual(self.played, ['B'])

    def test_removing_only_current_clears_queue_after_finish(self):
        self.data['tracks'] = [self.data['tracks'][0]]
        self.play_detail(); self.b.cycleRepeat()
        self.b.removeDetailPlaylistItem('A', 'first'); self.ready()
        self.assertTrue(self.b.playerHasTrack)
        self.eos()
        self.assertFalse(self.b.playerHasTrack)
        self.assertEqual(self.b.playerState, 'idle')
        self.assertEqual(self.b.playingTracksModel.count, 0)
        self.assertEqual(self.played, ['A'])

    def test_manual_next_previous_and_queue_selection_drop_departed_current(self):
        for action, expected in [('next', 'B'), ('previous', 'A'), ('select', 'B')]:
            # Each pass reloads a fresh occurrence for the independent queue.
            self.data['tracks'] = [dict(videoId=v, title=v, setVideoId=s)
                                   for v, s in [('A', 'first'), ('A', 'second'), ('B', 'third')]]
            self.load()  # Retire an earlier confirmed tombstone if necessary below.
            self.b._pending_removed_playlist_items.clear()
            self.play_detail(1)
            self.b.removeDetailPlaylistItem('A', 'second'); self.ready()
            count = len(self.played)
            if action == 'next': self.b.nextTrack()
            elif action == 'previous': self.b.previousTrack()
            else: self.b.playFrom('playing', 2)
            self.until(lambda: self.b.playerState == 'playing')
            self.assertEqual(self.played[count:], [expected])
            self.assertEqual(self.queue_ids(), ['first', 'third'])

    def test_paused_current_is_retained_until_stop_without_resuming(self):
        self.play_detail(1)
        self.b._player_state = 'paused'; self.status.player_state = 'PAUSED'
        self.b._player_position = 36
        self.b.removeDetailPlaylistItem('A', 'second'); self.ready()
        self.assertEqual(self.b.playerState, 'paused')
        self.assertEqual(self.b.playerPosition, 36)
        self.assertEqual(self.queue_ids(), ['first', 'second', 'third'])
        self.b.stopPlayback()
        self.assertEqual(self.queue_ids(), ['first', 'third'])
        self.assertEqual(self.b.playerState, 'idle')
        self.assertEqual(self.played, ['A'])

    def test_idle_current_removed_immediately_and_other_playlist_queue_untouched(self):
        self.play_detail(1); self.b.stopPlayback()
        self.b.removeDetailPlaylistItem('A', 'second'); self.ready()
        self.assertEqual(self.queue_ids(), ['first', 'third'])
        self.assertEqual(self.b.playerState, 'idle')
        self.assertEqual(self.played, ['A'])
        # Same occurrence ID in another playlist must not affect this queue.
        self.b._detail_meta['playlistId'] = 'different'
        self.b.removeDetailPlaylistItem('A', 'first'); self.ready()
        self.assertEqual(self.queue_ids(), ['first', 'third'])

    def test_deleted_prefetch_is_cancelled_and_successor_prepared(self):
        self.data['tracks'] = [dict(videoId=v, title=v, setVideoId=s)
                               for v, s in [('A', 'first'), ('B', 'second'), ('C', 'third')]]
        self.blocked.add('B'); self.play_detail()
        self.until(lambda: self.downloads['B'] == 1)
        self.b.removeDetailPlaylistItem('B', 'second'); self.ready()
        self.until(lambda: 'B' in self.cancelled)
        self.until(lambda: 'C' in support.core.LOCAL_AUDIO_CACHE)
        self.assertEqual(self.queue_ids(), ['first', 'third'])
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['A', 'C'])

    def test_loading_current_can_finish_preparation_then_play_once(self):
        self.blocked.add('A'); self.load(); self.b.playFrom('detail', 0)
        self.until(lambda: self.downloads['A'] == 1)
        self.b.removeDetailPlaylistItem('A', 'first'); self.ready()
        self.assertEqual(self.b.playerState, 'loading')
        self.assertEqual(self.queue_ids(), ['first', 'second', 'third'])
        self.release.set(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['A'])
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.queue_ids(), ['second', 'third'])
        self.assertEqual(self.b.playerQueueIndex, 0)
        self.assertEqual(self.played, ['A', 'A'])
