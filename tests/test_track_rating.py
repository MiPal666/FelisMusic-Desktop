"""Selected-song writes through a fake account; never use real account/audio."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock, patch
import test_prefetch as support


class TrackRatingTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock(); self.api.rate_song.return_value = {}
        self.b._ytmusic = self.api; self.b._set_connected(True)

    def row(self, vid='X', status='INDIFFERENT', kind='song'):
        return dict(videoId=vid, title=vid, kind=kind, duration='3:00', likeStatus=status)

    def done(self):
        self.until(lambda: not self.b.trackRatingBusy)

    def test_other_song_updates_duplicates_models_and_origins_without_audio_change(self):
        self.start('A', 'X', 'X'); self.b._player_position = 42
        for source in ('detail', 'liked', 'history', 'search'):
            self.b._source_model(source).set_items([self.row()])
        self.b._detail_meta = dict(sections=dict(songs=[self.row()]))
        played, stops = list(self.played), list(self.stops)
        queue = self.b._queue
        self.assertTrue(self.b.rateTrackFrom('detail', 0, 'DISLIKE')); self.done()
        self.api.rate_song.assert_called_once_with('X', support.core.LikeStatus.DISLIKE)
        self.assertEqual(self.b.playerTitle, 'A'); self.assertEqual(self.b.playerLikeStatus, 'LIKE')
        self.assertEqual(self.b.playerPosition, 42); self.assertIs(self.b._queue, queue)
        self.assertEqual(self.played, played); self.assertEqual(self.stops, stops)
        self.assertEqual([x['likeStatus'] for x in queue.tracks], ['LIKE', 'DISLIKE', 'DISLIKE'])
        for source in ('detail', 'liked', 'history', 'search'):
            self.assertEqual(self.b._source_items(source)[0]['likeStatus'], 'DISLIKE')
        self.b.clearDetail(); self.b.restorePlayingSource(1)
        self.assertEqual([x['likeStatus'] for x in self.b._source_items('library')], ['LIKE', 'DISLIKE', 'DISLIKE'])

    def test_explicit_like_dislike_clear_and_unknown_do_not_need_lookup_or_playback(self):
        self.b._search_results_model.set_items([self.row(status='')])
        for status in ('LIKE', 'LIKE', 'DISLIKE', 'INDIFFERENT'):
            self.assertTrue(self.b.rateTrackFrom('search', 0, status)); self.done()
            self.assertEqual(self.b._source_items('search')[0]['likeStatus'], status)
        self.assertEqual([call.args[1] for call in self.api.rate_song.call_args_list],
                         [support.core.LikeStatus.LIKE, support.core.LikeStatus.LIKE,
                          support.core.LikeStatus.DISLIKE, support.core.LikeStatus.INDIFFERENT])
        self.api.get_watch_playlist.assert_not_called(); self.assertFalse(self.played)

    def block_write(self):
        entered = Event()
        def write(*args):
            entered.set(); self.release.wait(3); return {}
        self.api.rate_song.side_effect = write
        return entered

    def test_pending_write_targets_original_id_despite_navigation_and_current_change(self):
        self.start('A', 'X'); self.b._detail_tracks_model.set_items([self.row(status='')])
        entered = self.block_write()
        self.assertTrue(self.b.rateTrackFrom('detail', 0, 'DISLIKE')); self.until(entered.is_set)
        self.assertEqual(self.b._source_items('detail')[0]['likeStatus'], '')
        self.assertFalse(self.b.rateTrackFrom('library', 0, 'LIKE'))
        self.b.toggleRating('DISLIKE'); self.assertEqual(self.api.rate_song.call_count, 1)
        self.b.clearDetail(); self.b.playFrom('playing', 1)
        self.until(lambda: self.b.playerState == 'playing')
        self.assertFalse(self.b.playerCanRate)
        self.release.set(); self.done()
        self.assertEqual(self.b.playerTitle, 'X'); self.assertEqual(self.b.playerLikeStatus, 'DISLIKE')
        self.assertTrue(self.b.playerCanRate)
        self.api.rate_song.assert_called_once_with('X', support.core.LikeStatus.DISLIKE)

    def test_failure_keeps_unknown_or_known_status_and_unlocks_actions(self):
        self.b._search_results_model.set_items([self.row(status='')])
        for response in (RuntimeError('offline'), {'status': 'STATUS_FAILED'}):
            if isinstance(response, Exception): self.api.rate_song.side_effect = response
            else: self.api.rate_song.side_effect = None; self.api.rate_song.return_value = response
            self.assertTrue(self.b.rateTrackFrom('search', 0, 'LIKE')); self.done()
            self.assertEqual(self.b._source_items('search')[0]['likeStatus'], '')
            self.assertTrue(self.errors)
        self.api.rate_song.side_effect = None; self.api.rate_song.return_value = {}
        self.assertTrue(self.b.rateTrackFrom('search', 0, 'DISLIKE')); self.done()
        self.assertEqual(self.b._source_items('search')[0]['likeStatus'], 'DISLIKE')

    def test_top_buttons_keep_toggle_optimism_and_rollback_and_share_pending_guard(self):
        self.start('A', 'B'); entered = self.block_write()
        self.b.toggleRating('LIKE'); self.until(entered.is_set)
        self.assertEqual(self.b.playerLikeStatus, 'INDIFFERENT')
        self.assertFalse(self.b.rateTrackFrom('playing', 1, 'DISLIKE'))
        self.b.toggleRating('DISLIKE'); self.assertEqual(self.api.rate_song.call_count, 1)
        self.release.set(); self.done()
        self.assertEqual(self.b.playerLikeStatus, 'INDIFFERENT')
        self.api.rate_song.side_effect = RuntimeError('offline')
        self.b.toggleRating('DISLIKE'); self.done()
        self.assertEqual(self.b.playerLikeStatus, 'INDIFFERENT')
        self.assertTrue(self.b.playerCanRate); self.assertTrue(self.errors)

    def test_old_rating_probe_cannot_replace_a_confirmed_write(self):
        self.start('A'); generation = self.b._rating_generation
        self.assertTrue(self.b.rateTrackFrom('playing', 0, 'DISLIKE')); self.done()
        self.b._apply_rating_status(generation, 'A', 'LIKE')
        self.assertEqual(self.b.playerLikeStatus, 'DISLIKE')
        self.assertEqual(self.b.trackInfoFrom('playing', 0)['likeStatus'], 'DISLIKE')

    def test_unrelated_current_rating_probe_is_not_lost_during_other_song_write(self):
        self.start('A', 'B'); generation = self.b._rating_generation
        entered = self.block_write()
        self.assertTrue(self.b.rateTrackFrom('playing', 1, 'DISLIKE')); self.until(entered.is_set)
        self.b._apply_rating_status(generation, 'A', 'INDIFFERENT')
        self.assertEqual(self.b.playerLikeStatus, 'INDIFFERENT')
        self.release.set(); self.done()
        self.assertEqual(self.b.playerLikeStatus, 'INDIFFERENT')
        self.assertEqual(self.b._queue.tracks[1]['likeStatus'], 'DISLIKE')

    def test_active_load_snapshots_and_liked_refresh_are_updated(self):
        self.start('A', 'X'); load = dict(items=[self.row()], meta={})
        self.b._upload_load = self.b._upload_view_load = load
        self.b._liked_default_items = [self.row()]
        with patch.object(self.b, 'loadLiked') as refresh:
            self.assertTrue(self.b.rateTrackFrom('library', 1, 'LIKE')); self.done()
            refresh.assert_called_once_with()
        self.assertEqual(load['items'][0]['likeStatus'], 'LIKE')
        self.assertEqual(self.b._liked_default_items[0]['likeStatus'], 'LIKE')
        self.b._upload_load = self.b._upload_view_load = None

    def test_invalid_targets_offline_closing_and_unsupported_types_never_write(self):
        self.b._detail_tracks_model.set_items([self.row(kind='album'), dict(kind='song'), self.row()])
        for source, index, status in (('bad',0,'LIKE'),('detail',-1,'LIKE'),('detail',3,'LIKE'),
                                      ('detail',0,'LIKE'),('detail',1,'LIKE'),('detail',2,'bad')):
            self.assertFalse(self.b.rateTrackFrom(source,index,status))
        self.b._set_connected(False); self.assertFalse(self.b.rateTrackFrom('detail',2,'LIKE'))
        self.b._set_connected(True); self.b._closing.set()
        self.assertFalse(self.b.rateTrackFrom('detail',2,'LIKE')); self.b._closing.clear()
        self.api.rate_song.assert_not_called()
