"""Song radio through inherited CLI helpers; no network or audio device."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock
import test_prefetch as support


class RadioTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock()
        self.b._ytmusic = self.api
        self.block_radio = False
        self.radio_entered = Event()
        self.block = [self.song('A'), self.song('X'), self.song('Y')]
        self.api.get_watch_playlist.side_effect = self.watch
        self.started = []
        self.b.radioStarted.connect(lambda: self.started.append(True))

    @staticmethod
    def song(vid):
        return dict(title=vid, videoId=vid, duration='3:00', likeStatus='LIKE')

    def watch(self, **kwargs):
        self.radio_entered.set()
        if self.block_radio:
            self.release.wait(3)
        return {'tracks': deepcopy(self.block)}

    def ready(self):
        self.until(lambda: not self.b.busy)

    def ids(self):
        return [song['videoId'] for song in self.b._queue.tracks]

    def test_current_seed_keeps_audio_time_and_prefetches_radio_successor(self):
        self.start('A', 'B', 'C')
        self.until(lambda: 'B' in support.core.LOCAL_AUDIO_CACHE)
        self.b._player_position = 45
        stops = len(self.stops)
        self.assertTrue(self.b.startRadioFrom('library', 0)); self.ready()
        self.assertEqual(self.ids(), ['A', 'X', 'Y'])
        self.assertEqual(self.b.playingListTitle, 'Mix: A')
        self.assertTrue(self.b._queue.radio_active)
        self.assertEqual(self.b.playerPosition, 45)
        self.assertEqual(self.played, ['A'])
        self.assertEqual(len(self.stops), stops)
        self.api.get_watch_playlist.assert_called_once_with(videoId='A', limit=support.core.MIX_LIMIT, radio=True)
        self.until(lambda: 'X' in support.core.LOCAL_AUDIO_CACHE)
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['A', 'X'])
        self.assertEqual(self.b.playerSourceContext, {'page': 5})
        self.assertTrue(self.b.restorePlayingSource(5))
        self.assertEqual(self.b.playingTracksModel.count, 3)

    def test_paused_current_seed_keeps_pause_but_new_radio_resets_repeat(self):
        self.start('A', 'B')
        self.b._player_state = 'paused'
        self.b._player_position = 37
        self.b._repeat_mode = 'one'
        stops = len(self.stops)
        self.b.startRadioFrom('playing', 0); self.ready()
        self.assertEqual(self.b.playerState, 'paused')
        self.assertEqual(self.b.playerPosition, 37)
        self.assertEqual(self.b.playerRepeatMode, 'off')
        self.assertEqual(self.played, ['A'])
        self.assertEqual(len(self.stops), stops)

    def test_other_seed_starts_selected_song_and_replaces_only_on_success(self):
        self.start('A', 'B')
        self.b.cycleRepeat()
        self.b.searchResultsModel.set_items([dict(self.song('S'), kind='song'), dict(self.song('unselected'), kind='song')])
        self.block = [self.song('X'), self.song('S'), self.song('Y')]
        self.block_radio = True
        self.b.startRadioFrom('search', 0)
        self.until(self.radio_entered.is_set)
        self.assertEqual(self.ids(), ['A', 'B'])
        self.assertEqual(self.b.playerTitle, 'A')
        self.assertEqual(self.b.playerRepeatMode, 'all')
        self.release.set(); self.ready()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.ids(), ['S', 'X', 'Y'])
        self.assertEqual(self.played, ['A', 'S'])
        self.assertEqual(self.b.playerQueueIndex, 0)
        self.assertEqual(self.b.playerRepeatMode, 'off')

    def test_filtering_unavailable_missing_ids_duplicates_and_seed(self):
        self.b.searchResultsModel.set_items([dict(self.song('S'), kind='video')])
        self.block = [self.song('S'), self.song('X'), self.song('X'),
                      dict(self.song('bad'), isAvailable=False), {'title': 'missing'}, self.song('Y'), self.song('S')]
        self.b.startRadioFrom('search', 0); self.ready()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.ids(), ['S', 'X', 'Y'])
        self.assertEqual(self.b.playerQueueSource, 'playing')
        self.assertEqual(self.started, [True])

    def test_failure_or_only_seed_does_not_change_queue_or_audio(self):
        self.start('A', 'B'); queue = self.b._queue; stops = len(self.stops)
        self.b.cycleRepeat(); self.b.cycleRepeat()
        for block in ([], [self.song('A')]):
            self.block = block
            self.b.startRadioFrom('library', 0); self.ready()
            self.assertIs(self.b._queue, queue)
        self.api.get_watch_playlist.side_effect = RuntimeError('Offline')
        self.b.startRadioFrom('library', 0); self.ready()
        self.assertIs(self.b._queue, queue)
        self.assertEqual(self.played, ['A'])
        self.assertEqual(len(self.stops), stops)
        self.assertEqual(len(self.errors), 3)
        self.assertFalse(self.started)
        self.assertEqual(self.b.playerRepeatMode, 'one')

    def test_stop_supersedes_pending_radio(self):
        self.start('A', 'B'); queue = self.b._queue
        self.block_radio = True
        self.b.startRadioFrom('library', 0); self.until(self.radio_entered.is_set)
        self.b.stopPlayback(); self.release.set(); self.ready()
        self.assertIs(self.b._queue, queue)
        self.assertEqual(self.b.playerState, 'idle')
        self.assertFalse(self.started)
        self.assertEqual(self.played, ['A'])

    def test_manual_next_supersedes_pending_radio(self):
        self.start('A', 'B'); queue = self.b._queue
        self.block_radio = True
        self.b.startRadioFrom('library', 0); self.until(self.radio_entered.is_set)
        self.b.nextTrack(); self.until(lambda: self.b.playerState == 'playing')
        self.release.set(); self.ready()
        self.assertIs(self.b._queue, queue)
        self.assertEqual(self.played, ['A', 'B'])
        self.assertFalse(self.started)

    def test_queue_insertion_supersedes_pending_radio(self):
        self.start('A', 'B'); queue = self.b._queue
        self.block_radio = True
        self.b.startRadioFrom('library', 0); self.until(self.radio_entered.is_set)
        self.b.enqueueFrom('library', 1, False, {})
        self.release.set(); self.ready()
        self.assertIs(self.b._queue, queue)
        self.assertEqual(self.ids(), ['A', 'B', 'B'])
        self.assertFalse(self.started)

    def test_rejects_private_upload_episode_invalid_and_busy(self):
        self.b.searchResultsModel.set_items([
            dict(self.song('private'), kind='upload_song'),
            dict(self.song('episode'), kind='episode'),
            dict(self.song('privateId'), kind='song', browseId='privately_owned_release_detail_x'),
            dict(kind='album', browseId='album')])
        for i in (-1, 0, 1, 2, 3, 4):
            self.assertFalse(self.b.startRadioFrom('search', i))
        self.b._set_busy(True)
        self.assertFalse(self.b.startRadioFrom('search', 0))
        self.api.get_watch_playlist.assert_not_called()

    def test_superseded_failure_does_not_report_stale_error(self):
        self.start('A', 'B')
        self.block = []
        self.block_radio = True
        self.b.startRadioFrom('library', 0); self.until(self.radio_entered.is_set)
        self.b.stopPlayback(); self.release.set(); self.ready()
        self.assertFalse(self.errors)
        self.assertEqual(self.b.playerState, 'idle')
