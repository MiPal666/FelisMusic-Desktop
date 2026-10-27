"""Collection-seeded radio (RDAMPL), distinct from song/artist radio."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock, patch
import test_prefetch as support


class CollectionRadioTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock(); self.b._ytmusic = self.api
        self.source = [self.song('source-first'), self.song('source-second')]
        self.api.get_playlist.return_value = dict(title='Playlist', owned=True, tracks=self.source)
        self.api.get_album.return_value = dict(title='Album', audioPlaylistId='OLAKalbum', tracks=self.source)
        self.block = [self.song(f'R{i}') for i in range(8)]
        self.entered = Event(); self.block_request = False; self.fail = False
        self.api.get_watch_playlist.side_effect = self.watch
        self.started = []; self.b.radioStarted.connect(lambda: self.started.append(True))

    @staticmethod
    def song(vid):
        return dict(videoId=vid, title=vid, duration='3:00', likeStatus='LIKE')

    def watch(self, **kwargs):
        self.entered.set()
        if self.block_request:
            self.release.wait(3)
        if self.fail:
            raise RuntimeError('Offline')
        return {'tracks': deepcopy(self.block)}

    def ready(self):
        self.until(lambda: not self.b.busy)

    def open_collection(self, album=False, playlist_id='PLsource'):
        if album:
            self.b.openLibraryItem('album', 'MPREalbum', '', 'Album')
        else:
            self.b.loadPlaylistTracks(playlist_id, 'Playlist')
        self.ready()

    def play_mix(self):
        self.assertTrue(self.b.startCollectionRadio()); self.ready()
        self.until(lambda: self.b.playerState == 'playing')

    def ids(self):
        return [x['videoId'] for x in self.b._queue.tracks]

    def test_playlist_is_the_seed_not_its_first_song(self):
        self.open_collection(); self.play_mix()
        self.api.get_watch_playlist.assert_called_once_with(playlistId='RDAMPLPLsource', limit=support.core.MIX_LIMIT, radio=True)
        self.assertEqual(self.ids(), [f'R{i}' for i in range(8)])
        self.assertNotIn('source-first', self.ids())
        self.assertTrue(self.b._queue.radio_active); self.assertFalse(self.b._queue.shuffle_active)
        self.assertEqual(self.b.playingListTitle, 'Mix: Playlist')
        self.assertEqual(self.b.playerQueueSource, 'playing')
        self.assertEqual(self.b.playerSourceContext, {'page': 5})
        self.assertEqual(self.started, [True])

    def test_album_uses_audio_playlist_id_not_browse_id_or_first_song(self):
        self.open_collection(album=True); self.play_mix()
        self.api.get_watch_playlist.assert_called_once_with(playlistId='RDAMPLOLAKalbum', limit=support.core.MIX_LIMIT, radio=True)
        self.assertEqual(self.b.playingListTitle, 'Mix: Album')

    def test_vl_prefix_is_removed_and_existing_radio_prefix_is_not_doubled(self):
        for source, expected in (('VLPLsource', 'RDAMPLPLsource'), ('RDAMPLPLexisting', 'RDAMPLPLexisting')):
            with self.subTest(source=source):
                self.open_collection(playlist_id=source); self.play_mix()
                self.api.get_watch_playlist.assert_called_with(playlistId=expected, limit=support.core.MIX_LIMIT, radio=True)

    def test_background_refill_and_eos_follow_collection_mix(self):
        self.open_collection(); self.play_mix()
        self.b.playFrom('playing', 7); self.until(lambda: self.b.playerState == 'playing')
        self.block = [self.song('R7'), self.song('R0'), self.song('new'), self.song('new'), self.song('next')]
        self.b._maybe_refill_radio(); self.until(lambda: not self.b._radio_refill_pending)
        self.api.get_watch_playlist.assert_called_with(videoId='R7', limit=support.core.MIX_LIMIT, radio=True)
        self.assertEqual(self.ids()[-2:], ['new', 'next'])
        self.until(lambda: 'new' in support.core.LOCAL_AUDIO_CACHE)
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, 'new')

    def test_filtering_duplicates_unavailable_missing_ids_and_test_limit(self):
        self.open_collection()
        self.block = [self.song('A'), self.song('A'), dict(self.song('bad'), isAvailable=False),
                      {'title': 'No ID'}, self.song('B'), self.song('C')]
        with patch.object(support.core, 'MIX_TEST_MAX_TRACKS', 2):
            self.play_mix()
        self.assertEqual(self.ids(), ['A', 'B'])

    def test_disabled_for_missing_album_id_empty_collection_upload_artist_and_deleted_playlist(self):
        self.api.get_album.return_value.pop('audioPlaylistId')
        self.open_collection(album=True); self.assertFalse(self.b.startCollectionRadio())
        self.api.get_playlist.return_value['tracks'] = []
        self.open_collection(); self.assertFalse(self.b.startCollectionRadio())
        self.api.get_playlist.return_value['tracks'] = self.source
        self.open_collection()
        self.b._deleted_playlists.add('PLsource'); self.assertFalse(self.b.startCollectionRadio())
        self.b._deleted_playlists.clear()
        for kind in ('upload_album', 'upload_artist', 'artist', 'podcast'):
            self.b._detail_meta['kind'] = kind
            self.assertFalse(self.b.detailCanCollectionRadio); self.assertFalse(self.b.startCollectionRadio())
        self.api.get_watch_playlist.assert_not_called()

    def test_old_queue_audio_and_repeat_until_success_then_new_repeat_is_off(self):
        self.start('old', 'next'); old = self.b._queue; self.b.cycleRepeat()
        self.open_collection(); self.block_request = True
        self.b.startCollectionRadio(); self.until(self.entered.is_set)
        self.assertIs(self.b._queue, old); self.assertEqual(self.played, ['old'])
        self.assertEqual(self.b.playerRepeatMode, 'all')
        self.assertFalse(self.b.startCollectionRadio())
        self.release.set(); self.ready(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['old', 'R0']); self.assertEqual(self.b.playerRepeatMode, 'off')
        self.assertIsNot(self.b._queue, old)

    def test_failure_or_no_usable_results_preserve_old_playback(self):
        self.start('old'); old = self.b._queue; self.b.cycleRepeat(); self.open_collection()
        self.fail = True; self.b.startCollectionRadio(); self.ready()
        self.fail = False; self.block = [dict(self.song('bad'), isAvailable=False)]
        self.b.startCollectionRadio(); self.ready()
        self.assertIs(self.b._queue, old); self.assertEqual(self.played, ['old'])
        self.assertEqual(self.b.playerRepeatMode, 'all'); self.assertEqual(len(self.errors), 2)
        self.assertFalse(self.started)

    def test_stop_next_new_playback_queue_edit_and_navigation_ignore_late_result(self):
        for change in ('stop', 'next', 'new', 'enqueue', 'navigate'):
            with self.subTest(change=change):
                self.start('old', 'next'); self.open_collection()
                self.release.clear(); self.entered.clear(); self.block_request = True
                self.b.startCollectionRadio(); self.until(self.entered.is_set)
                if change == 'stop':
                    self.b.stopPlayback()
                elif change == 'next':
                    self.b.nextTrack(); self.until(lambda: self.b.playerState == 'playing')
                elif change == 'new':
                    self.b.playFrom('detail', 0); self.until(lambda: self.b.playerState == 'playing')
                elif change == 'enqueue':
                    self.b.enqueueFrom('detail', 0, False, {})
                else:
                    self.b.clearDetail()
                queue = self.b._queue
                self.release.set(); self.ready()
                self.assertIs(self.b._queue, queue); self.assertFalse(self.started)

    def test_stale_error_after_stop_is_silent(self):
        self.start('old'); self.open_collection(); self.block_request = True; self.fail = True
        self.b.startCollectionRadio(); self.until(self.entered.is_set)
        self.b.stopPlayback(); self.release.set(); self.ready()
        self.assertFalse(self.errors)

    def test_new_collection_mix_takes_priority_over_pending_old_refill(self):
        self.open_collection(); self.play_mix(); old = self.b._queue
        self.b.playFrom('playing', 7); self.until(lambda: self.b.playerState == 'playing')
        self.block_request = True; self.entered.clear()
        self.b._maybe_refill_radio(); self.until(self.entered.is_set)
        self.assertTrue(self.b.startCollectionRadio())
        self.release.set(); self.until(lambda: not self.b._radio_refill_pending); self.ready()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertIsNot(self.b._queue, old); self.assertEqual(old.count(), 8)
        self.assertEqual(self.ids(), [f'R{i}' for i in range(8)])

    def test_cover_points_to_generated_fronta_and_browsing_collection_stays_unchanged(self):
        self.open_collection(album=True); original = self.b.detailTracksModel.snapshot()
        self.play_mix()
        self.assertEqual(self.b.detailTracksModel.snapshot(), original)
        self.b.clearDetail(); self.assertTrue(self.b.restorePlayingSource(5))
        self.assertEqual(self.b.playerQueueSource, 'playing')
        self.assertEqual(self.b.playerVideoId, 'R0')
