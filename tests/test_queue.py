"""Actual playback queue, metadata, and explicit Stop behavior."""
import test_prefetch as support


class QueueTests(support.AudioPlaybackTestCase):
    def test_empty_queue_info_and_stop_are_safe(self):
        self.assertEqual(self.b.playingTracksModel.count, 0)
        self.assertEqual(self.b.playerQueueIndex, -1)
        self.assertEqual(self.b.playerQueueCount, 0)
        self.assertEqual(self.b.playerArtist, '')
        self.assertEqual(self.b.playerAlbum, '')
        self.b.stopPlayback()
        self.b.playFrom('playing', 0)
        self.assertFalse(self.stops)
        self.assertFalse(self.errors)

    def test_queue_filters_nonplayable_rows_and_preserves_duplicate_occurrences(self):
        rows = [
            dict(title='First A', videoId='A', artists='Artist A', album='Album A'),
            dict(title='Not a track', kind='album', browseId='album'),
            dict(title='B', videoId='B', artists='Artist B', album='Album B'),
            dict(title='Second A', videoId='A', artists='Artist A', album='Album A'),
        ]
        self.b._library_items_model.set_items(rows)
        self.b.playFrom('library', 3)
        self.until(lambda: self.b.playerState == 'playing')
        queue = self.b._queue
        self.assertEqual(self.b.playerQueueIndex, 2)
        self.assertEqual(self.b.playerSourceIndex, 3)
        self.assertEqual(self.b.playerQueueCount, 3)
        self.assertEqual([x['title'] for x in self.b.playingTracksModel.snapshot()], ['First A', 'B', 'Second A'])
        self.b.playFrom('playing', 1)
        self.until(lambda: self.b.playerState == 'playing')
        self.assertIs(self.b._queue, queue)
        self.assertEqual(self.b.playerQueueSource, 'library')
        self.assertEqual(self.b.playerSourceIndex, 2)
        self.assertEqual(self.b.playerArtist, 'Artist B')
        self.assertEqual(self.b.playerAlbum, 'Album B')

    def test_browsing_another_collection_does_not_replace_queue_or_metadata(self):
        self.b._detail_title = 'Original album'
        self.b._detail_tracks_model.set_items([
            dict(title='Upload', kind='upload_song', videoId='A', artists='My artist',
                 album='My album', thumbnail='https://example.test/private-cover', likeStatus='LIKE')
        ])
        self.b.playFrom('detail', 0)
        self.until(lambda: self.b.playerState == 'playing')
        original = self.b.playingTracksModel.snapshot()
        self.b.clearDetail()
        self.b._library_items_model.set_items([dict(title='Other', videoId='other')])
        self.assertEqual(self.b.playingTracksModel.snapshot(), original)
        self.assertEqual(self.b.playingListTitle, 'Original album')
        self.assertEqual(self.b.playerArtist, 'My artist')
        self.assertEqual(self.b.playerAlbum, 'My album')
        self.assertEqual(original[0]['thumbnail'], 'https://example.test/private-cover')
        self.b._propagate_like_status('A', 'DISLIKE')
        self.assertEqual(self.b.playingTracksModel.snapshot()[0]['likeStatus'], 'DISLIKE')

    def test_queue_model_follows_actual_order_not_the_source_model(self):
        self.start('A', 'B', 'C')
        self.b._queue.tracks.reverse()
        self.b._sync_queue_model()
        self.assertEqual([x['videoId'] for x in self.b.playingTracksModel.snapshot()], ['C', 'B', 'A'])
        self.assertEqual([x['videoId'] for x in self.b.libraryItemsModel.snapshot()], ['A', 'B', 'C'])

    def test_stop_keeps_selection_queue_repeat_and_play_restarts_current_track(self):
        self.start('A', 'B')
        self.until(lambda: 'B' in support.core.LOCAL_AUDIO_CACHE)
        self.b.nextTrack()
        self.until(lambda: self.b.playerState == 'playing')
        self.b.cycleRepeat()
        queue = self.b._queue
        self.b._player_position = 42
        self.b.stopPlayback()
        self.assertEqual(self.b.playerState, 'idle')
        self.assertEqual(self.b.playerPosition, 0)
        self.assertFalse(self.b.playerCanSeek)
        self.assertIs(self.b._queue, queue)
        self.assertEqual(self.b.playerQueueIndex, 1)
        self.assertEqual(self.b.playerRepeatMode, 'all')
        self.assertTrue(self.stops[-1])
        self.b.togglePlayPause()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['A', 'B', 'B'])
        self.assertEqual(self.downloads['B'], 1)
        self.assertEqual(self.b.playerPosition, 0)

    def test_stop_during_loading_prevents_late_playback(self):
        self.blocked.add('A')
        self.b._library_items_model.set_items([dict(title='A', videoId='A')])
        self.b.playFrom('library', 0)
        self.until(lambda: self.downloads['A'] == 1)
        self.b.stopPlayback()
        self.until(lambda: 'A' in self.cancelled)
        self.assertEqual(self.b.playerState, 'idle')
        self.assertEqual(self.b.playerPosition, 0)
        self.assertFalse(self.played)
        self.assertFalse(self.errors)
        self.release.set()
        self.b.togglePlayPause()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['A'])

    def test_stop_cancels_prefetch_of_current_track_in_repeat_all(self):
        self.blocked.add('A')
        # The actual playing file exists; force a speculative cache miss later.
        self.release.set()
        self.start('A')
        self.release.clear()
        support.core.LOCAL_AUDIO_CACHE.pop('A')
        self.b.cycleRepeat()
        self.until(lambda: self.downloads['A'] == 2)
        self.b.stopPlayback()
        self.until(lambda: 'A' in self.cancelled)
        self.assertEqual(self.played, ['A'])
        self.assertFalse(self.errors)

    def test_queue_selection_while_loading_invalidates_previous_request(self):
        self.blocked.add('A')
        self.b._library_items_model.set_items([
            dict(title='A', videoId='A'), dict(title='B', videoId='B')
        ])
        self.b.playFrom('library', 0)
        self.until(lambda: self.downloads['A'] == 1)
        queue = self.b._queue
        self.b.playFrom('playing', 1)
        self.until(lambda: self.b.playerState == 'playing')
        self.assertIs(self.b._queue, queue)
        self.assertEqual(self.played, ['B'])
        self.assertIn('A', self.cancelled)
