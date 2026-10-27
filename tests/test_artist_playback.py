"""Artist radio/shuffle endpoints through CLI helpers; mocked account/audio."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock, patch
import test_prefetch as support


class ArtistPlaybackTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock(); self.b._ytmusic = self.api
        self.artist = dict(name='Artist', radioId='RDEMartist', shuffleId='RDAartist',
                          songs={'results': [self.song(v) for v in ('Y', 'X', 'Z')]},
                          albums={'results': [dict(title='Album', browseId='album')]}, singles={})
        self.api.get_artist.side_effect = lambda *args: deepcopy(self.artist)
        self.api.get_album.return_value = dict(title='Album', audioPlaylistId='OLAKalbum', tracks=[self.song('album-song')])
        self.radio_block = [self.song(f'R{i}') for i in range(8)]
        self.shuffle_block = [self.song(v) for v in ('Y', 'X', 'Z')]
        self.entered = Event(); self.block_request = False; self.fail = False
        self.block_shuffle = False
        mixer = patch.object(support.backend.random, 'shuffle', side_effect=self.mix)
        mixer.start(); self.addCleanup(mixer.stop)
        self.api.get_watch_playlist.side_effect = self.watch
        self.started = []; self.b.artistPlaybackStarted.connect(lambda: self.started.append(True))

    def mix(self, indices):
        if self.block_shuffle:
            self.entered.set(); self.release.wait(3)
        if len(indices) > 1:
            indices[0], indices[1] = indices[1], indices[0]

    @staticmethod
    def song(vid):
        return dict(videoId=vid, title=vid, duration='3:00', likeStatus='LIKE')

    def watch(self, **kwargs):
        self.entered.set()
        if self.block_request:
            self.release.wait(3)
        if self.fail:
            raise RuntimeError('Offline')
        if kwargs.get('playlistId') == 'RDEMartist':
            return {'tracks': deepcopy(self.radio_block)}
        if kwargs.get('playlistId') == 'RDAartist':
            return {'tracks': deepcopy(self.shuffle_block)}
        return {'tracks': [self.song(f'N{i}') for i in range(8)]}

    def ready(self):
        self.until(lambda: not self.b.busy)

    def open_artist(self):
        self.b.openLibraryItem('artist', 'UCartist', '', 'Artist'); self.ready()

    def play(self, mode):
        self.assertTrue(self.b.startArtistPlayback(mode)); self.ready()
        self.until(lambda: self.b.playerState == 'playing')

    def ids(self):
        return [x['videoId'] for x in self.b._queue.tracks]

    def test_radio_uses_artist_radio_id_and_continues_through_background_refill(self):
        self.open_artist(); self.play('radio')
        self.api.get_watch_playlist.assert_called_once_with(playlistId='RDEMartist', limit=support.core.MIX_LIMIT)
        self.assertEqual(self.ids(), [f'R{i}' for i in range(8)])
        self.assertTrue(self.b._queue.radio_active); self.assertFalse(self.b._queue.shuffle_active)
        self.assertEqual(self.b.playingListTitle, 'Artist - Mix / rádio')
        self.assertEqual(self.b.playerSourceContext, {'page': 5})
        self.assertEqual(self.started, [True])
        self.b.playFrom('playing', 7); self.until(lambda: self.b.playerState == 'playing')
        self.b._maybe_refill_radio(); self.until(lambda: not self.b._radio_refill_pending)
        self.api.get_watch_playlist.assert_called_with(videoId='R7', limit=support.core.MIX_LIMIT, radio=True)
        self.assertEqual(self.ids()[-8:], [f'N{i}' for i in range(8)])
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, 'N0')

    def test_shuffle_uses_loaded_artist_songs_locally_and_is_finite(self):
        self.open_artist(); self.play('shuffle')
        self.api.get_watch_playlist.assert_not_called()
        self.assertEqual(self.ids(), ['Y', 'X', 'Z'])
        self.assertTrue(self.b._queue.shuffle_active); self.assertFalse(self.b._queue.radio_active)
        self.assertEqual(self.b.playingListTitle, 'Artist - Náhodně')
        self.assertFalse(self.b._maybe_refill_radio())
        self.until(lambda: 'X' in support.core.LOCAL_AUDIO_CACHE)
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['Y', 'X'])

    def test_radio_filters_unavailable_missing_and_duplicate_ids(self):
        self.radio_block = [self.song('A'), self.song('A'), dict(self.song('bad'), isAvailable=False),
                            {'title': 'No ID'}, self.song('B')]
        self.open_artist(); self.play('radio')
        self.assertEqual(self.ids(), ['A', 'B'])

    def test_shuffle_cover_restores_artist_tab_after_browsing_elsewhere(self):
        self.open_artist()
        self.b.selectArtistSection('albums'); self.ready()
        self.b.playbackSourceCaptured.connect(lambda: self.b.setPlaybackSourceContext(
            {'page': 1, 'librarySection': 'artists', 'libraryLabel': 'Interpreti'}))
        self.play('shuffle')
        self.assertEqual(self.b.playerQueueSource, 'detail')
        self.assertEqual(self.b.playerSourceIndex, -1)
        self.assertEqual(self.b.playerSourceContext['page'], 1)
        queue = self.b._queue
        self.b.openLibraryItem('album', 'other', '', 'Other'); self.ready()
        self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual(self.b.detailMeta['browseId'], 'UCartist')
        self.assertEqual(self.b.detailMeta['section'], 'albums')
        self.assertIs(self.b._queue, queue)
        self.assertEqual(self.b.playerVideoId, 'Y')
        self.b.playFrom('playing', 1); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerSourceContext['page'], 1)

    def test_shuffle_preserves_available_duplicate_occurrences(self):
        self.artist['songs']['results'] = [self.song('A'), self.song('A'), self.song('B')]
        self.open_artist(); self.play('shuffle')
        self.assertEqual(self.ids(), ['A', 'A', 'B'])
        self.assertEqual(self.b._queue_source_indices, [1, 0, 2])

    def test_shuffle_no_longer_requires_server_shuffle_id(self):
        self.artist['shuffleId'] = None
        self.open_artist(); self.assertTrue(self.b.detailCanArtistShuffle)
        self.play('shuffle')
        self.assertEqual(self.ids(), ['Y', 'X', 'Z'])
        self.api.get_watch_playlist.assert_not_called()

    def test_full_catalog_loaded_once_and_not_limited_to_mix_block(self):
        self.artist['songs'] = {'results': [self.song('preview')], 'browseId': 'VLcatalog'}
        catalog = [dict(self.song(str(i % 200)), title=f'{i:04d}') for i in range(205)]
        catalog += [dict(self.song('bad'), isAvailable=False), {'title': 'No ID'}]
        self.api.get_playlist.return_value = {'tracks': catalog}
        self.open_artist(); self.assertEqual(self.b.detailTracksModel.count, 205)
        self.play('shuffle')
        self.assertEqual(self.b.playerQueueCount, 205)
        self.assertEqual(len(set(self.ids())), 200)
        self.assertNotIn('preview', self.ids())
        self.assertEqual(sorted(self.b._queue_source_indices), list(range(205)))
        self.api.get_playlist.assert_called_once_with('VLcatalog', limit=None)
        self.api.get_artist.assert_called_once()
        self.api.get_watch_playlist.assert_not_called()

    def test_song_tab_has_exact_indices_and_cover_after_browsing(self):
        self.open_artist(); before = self.b.detailTracksModel.snapshot()
        self.play('shuffle')
        self.assertEqual(self.b._queue_source_indices, [1, 0, 2])
        self.assertEqual(self.b.playerSourceIndex, 1)
        self.b.clearDetail(); self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual(self.b.detailTracksModel.snapshot(), before)
        self.assertEqual(self.b.detailMeta['section'], 'songs')
        self.b.playFrom('playing', 1); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerSourceIndex, 0)

    def test_each_start_randomizes_again_repeat_and_end_are_finite(self):
        self.open_artist()
        with patch.object(support.backend.random, 'shuffle', side_effect=lambda rows: rows.reverse()) as mix:
            self.play('shuffle'); first = self.b._queue
            self.b.cycleRepeat(); self.play('shuffle')
        self.assertIsNot(self.b._queue, first); self.assertEqual(mix.call_count, 2)
        self.assertEqual(self.b.playerRepeatMode, 'off')
        self.b.cycleRepeat(); self.b.cycleRepeat()
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerVideoId, 'Z')
        self.b.cycleRepeat()
        self.b.playFrom('playing', 2); self.until(lambda: self.b.playerState == 'playing')
        self.eos(); self.assertEqual(self.b.playerState, 'idle')
        self.assertFalse(self.b.playerQueueLoading); self.assertFalse(self.b.playerQueueIncomplete)
        self.api.get_watch_playlist.assert_not_called()

    def test_local_result_discarded_after_stop_or_tab_change(self):
        for change in ('stop', 'tab'):
            with self.subTest(change=change):
                self.start('old'); old = self.b._queue; self.open_artist()
                self.block_shuffle = True; self.entered.clear(); self.release.clear()
                before = len(self.started)
                self.assertTrue(self.b.startArtistPlayback('shuffle')); self.until(self.entered.is_set)
                self.assertFalse(self.b.startArtistPlayback('shuffle'))
                if change == 'stop': self.b.stopPlayback()
                else: self.b._detail_meta['section'] = 'albums'
                self.release.set(); self.ready(); self.block_shuffle = False
                self.assertIs(self.b._queue, old)
                self.assertEqual(len(self.started), before)

    def test_ids_survive_tabs_nested_album_and_back(self):
        self.open_artist()
        for section in ('albums', 'singles', 'songs'):
            self.b.selectArtistSection(section); self.ready()
            self.assertTrue(self.b.detailCanArtistRadio); self.assertTrue(self.b.detailCanArtistShuffle)
        self.b.selectArtistSection('albums'); self.b.openDetailItem(0); self.ready()
        self.assertFalse(self.b.detailCanArtistRadio); self.assertFalse(self.b.detailCanArtistShuffle)
        self.b.backDetail()
        self.assertEqual(self.b.detailMeta['browseId'], 'UCartist')
        self.assertEqual(self.b.detailMeta['radioId'], 'RDEMartist')
        self.assertEqual(self.b.detailMeta['shuffleId'], 'RDAartist')

    def test_ids_are_independent_and_empty_catalog_can_still_start_radio(self):
        self.artist = dict(name='Empty', radioId=' RDEMartist ', shuffleId=None)
        self.open_artist()
        self.assertEqual(self.b.detailTracksModel.count, 0)
        self.assertTrue(self.b.detailCanArtistRadio); self.assertFalse(self.b.detailCanArtistShuffle)
        self.assertFalse(self.b.startArtistPlayback('shuffle'))
        self.play('radio')
        self.assertEqual(self.b.playerVideoId, 'R0')

    def test_missing_ids_invalid_kind_mode_busy_and_loading_reject_without_request(self):
        self.open_artist()
        self.assertFalse(self.b.startArtistPlayback('invalid'))
        self.b._set_busy(True); self.assertFalse(self.b.startArtistPlayback('radio')); self.b._set_busy(False)
        self.b._playback_transitioning = True; self.assertFalse(self.b.startArtistPlayback('radio'))
        self.b._playback_transitioning = False
        self.b._detail_meta['radioId'] = ''; self.assertFalse(self.b.startArtistPlayback('radio'))
        self.b._detail_meta['kind'] = 'upload_artist'; self.assertFalse(self.b.startArtistPlayback('shuffle'))
        self.api.get_watch_playlist.assert_not_called()

    def test_old_audio_and_repeat_remain_until_success_then_new_playback_resets_repeat(self):
        self.start('old', 'next'); old = self.b._queue
        self.b.cycleRepeat(); self.open_artist(); self.block_shuffle = True
        self.b.startArtistPlayback('shuffle'); self.until(self.entered.is_set)
        self.assertIs(self.b._queue, old); self.assertEqual(self.played, ['old'])
        self.assertEqual(self.b.playerRepeatMode, 'all')
        self.release.set(); self.ready(); self.until(lambda: self.b.playerState == 'playing')
        self.assertIsNot(self.b._queue, old); self.assertEqual(self.played, ['old', 'Y'])
        self.assertEqual(self.b.playerRepeatMode, 'off'); self.assertTrue(self.stops[-1])

    def test_network_or_empty_response_keeps_old_audio_queue_and_repeat(self):
        self.start('old'); old = self.b._queue; self.b.cycleRepeat(); self.open_artist()
        self.fail = True
        self.b.startArtistPlayback('radio'); self.ready()
        self.fail = False
        with patch.object(support.backend.random, 'shuffle', side_effect=RuntimeError('Test failure')):
            self.b.startArtistPlayback('shuffle'); self.ready()
        self.assertIs(self.b._queue, old); self.assertEqual(self.played, ['old'])
        self.assertEqual(self.b.playerRepeatMode, 'all'); self.assertEqual(len(self.errors), 2)
        self.assertFalse(self.started)

    def test_stop_next_new_audio_enqueue_and_navigation_discard_pending_result(self):
        for change in ('stop', 'next', 'new', 'enqueue', 'navigate'):
            with self.subTest(change=change):
                self.start('old', 'next'); old = self.b._queue; self.open_artist()
                self.release.clear(); self.entered.clear(); self.block_request = True
                self.assertTrue(self.b.startArtistPlayback('radio')); self.until(self.entered.is_set)
                self.assertFalse(self.b.startArtistPlayback('radio'))
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

    def test_late_error_after_stop_is_silent(self):
        self.start('old'); self.open_artist(); self.fail = True; self.block_request = True
        self.b.startArtistPlayback('radio'); self.until(self.entered.is_set)
        self.b.stopPlayback(); self.release.set(); self.ready()
        self.assertFalse(self.errors); self.assertFalse(self.started)

    def test_artist_action_wins_over_old_pending_radio_refill(self):
        self.open_artist(); self.play('radio'); old = self.b._queue
        self.b.playFrom('playing', 7); self.until(lambda: self.b.playerState == 'playing')
        self.entered.clear(); self.block_request = True
        self.b._maybe_refill_radio(); self.until(self.entered.is_set)
        self.assertTrue(self.b.startArtistPlayback('shuffle'))
        self.release.set(); self.until(lambda: not self.b._radio_refill_pending); self.ready()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(old.count(), 8); self.assertEqual(self.ids(), ['Y', 'X', 'Z'])
        self.assertFalse(self.b._queue.radio_active)

    def test_radio_cover_uses_generated_queue_not_visible_artist_tab(self):
        self.open_artist(); self.b.selectArtistSection('albums'); self.play('radio')
        self.b.clearDetail()
        self.assertTrue(self.b.restorePlayingSource(5))
        self.assertEqual(self.b.playerQueueSource, 'playing')
        self.assertEqual(self.b.playingTracksModel.count, 8)
