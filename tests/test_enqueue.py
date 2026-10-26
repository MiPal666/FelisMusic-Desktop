"""Noninterrupting queue insertion, prefetch retargeting and mixed origins."""
import test_prefetch as support


class EnqueueTests(support.AudioPlaybackTestCase):
    def other(self, video='X', title='X'):
        self.b._detail_title = 'Other album'
        self.b._detail_tracks_model.set_items([
            dict(title=title, videoId=video, artists='Other artist', album='Other album', likeStatus='LIKE')
        ])
        return {'page': 1, 'librarySection': 'upload_albums', 'libraryLabel': 'Nahraná alba'}

    def ids(self):
        return [s['videoId'] for s in self.b._queue.tracks]

    def test_play_next_preserves_audio_position_queue_and_inserts_model_row(self):
        self.start('A', 'B', 'C')
        self.until(lambda: 'B' in support.core.LOCAL_AUDIO_CACHE)
        queue = self.b._queue
        stops = len(self.stops)
        self.b._player_position = 42
        context = self.other()
        resets=[]
        self.b.playingTracksModel.modelReset.connect(lambda: resets.append(True))
        self.assertTrue(self.b.enqueueFrom('detail', 0, True, context))
        self.assertIs(self.b._queue, queue)
        self.assertEqual(self.ids(), ['A', 'X', 'B', 'C'])
        self.assertEqual(self.b.playerQueueIndex, 0)
        self.assertEqual(self.b.playerPosition, 42)
        self.assertEqual(self.b.playerTitle, 'A')
        self.assertEqual(self.b.playerState, 'playing')
        self.assertEqual(self.played, ['A'])
        self.assertEqual(len(self.stops), stops)
        self.assertFalse(resets)
        self.assertEqual([x['videoId'] for x in self.b.playingTracksModel.snapshot()], self.ids())

    def test_append_does_not_cancel_running_prefetch_of_same_successor(self):
        self.blocked.add('B')
        self.start('A', 'B')
        self.until(lambda: self.downloads['B']==1)
        self.assertTrue(self.b.enqueueFrom('detail', 0, False, self.other()))
        self.assertEqual(self.ids(), ['A', 'B', 'X'])
        self.release.set()
        self.until(lambda: 'B' in support.core.LOCAL_AUDIO_CACHE)
        self.assertNotIn('B', self.cancelled)
        self.assertEqual(self.downloads['B'], 1)
        self.assertEqual(self.played, ['A'])

    def test_play_next_cancels_old_prefetch_and_downloads_new_successor(self):
        self.blocked.add('B')
        self.start('A', 'B')
        self.until(lambda: self.downloads['B']==1)
        self.assertTrue(self.b.enqueueFrom('detail', 0, True, self.other()))
        self.until(lambda: 'X' in support.core.LOCAL_AUDIO_CACHE)
        self.assertIn('B', self.cancelled)
        self.assertEqual(self.played, ['A'])
        self.eos()
        self.until(lambda: self.b.playerState=='playing')
        self.assertEqual(self.played, ['A','X'])
        self.assertEqual(self.downloads['X'],1)

    def test_mixed_origins_restore_correct_collection_then_original_source(self):
        self.start('A', 'B')
        self.b.setPlaybackSourceContext({'page':1,'librarySection':'songs'})
        context=self.other()
        self.b._library_items_model.set_items([dict(title='Parent of upload',kind='album',browseId='parent')])
        self.b.enqueueFrom('detail', 0, True, context)
        self.b.clearDetail()
        self.eos();self.until(lambda:self.b.playerState=='playing')
        self.assertEqual(self.b.playerQueueSource,'detail')
        self.assertEqual(self.b.playerSourceIndex,0)
        self.assertEqual(self.b.playerSourceContext,context)
        self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual(self.b.detailTitle,'Other album')
        self.assertEqual(self.b.detailTracksModel.snapshot()[0]['videoId'],'X')
        self.assertEqual(self.b.libraryItemsModel.snapshot()[0]['title'],'Parent of upload')
        self.eos();self.until(lambda:self.b.playerState=='playing')
        self.assertEqual(self.b.playerQueueSource,'library')
        self.assertEqual(self.b.playerSourceIndex,1)
        self.assertEqual(self.b.playerSourceContext['librarySection'],'songs')
        self.b.restorePlayingSource(1)
        self.assertEqual([i['videoId'] for i in self.b.libraryItemsModel.snapshot()],['A','B'])
        self.assertFalse(self.b.detailTitle)

    def test_adding_to_empty_queue_does_not_start_audio(self):
        context=self.other()
        self.assertTrue(self.b.enqueueFrom('detail',0,True,context))
        self.assertEqual(self.ids(),['X'])
        self.assertEqual(self.b.playerState,'idle')
        self.assertEqual(self.b.playerSourceContext,context)
        self.assertFalse(self.stops)
        self.assertFalse(self.played)
        self.b.togglePlayPause();self.until(lambda:self.b.playerState=='playing')
        self.assertEqual(self.played,['X'])

    def test_adding_copy_of_queue_row_preserves_its_origin_and_duplicates(self):
        self.start('A','B')
        self.b.setPlaybackSourceContext({'page':1,'librarySection':'songs'})
        self.b.enqueueFrom('playing',1,False,{'page':5})
        self.assertEqual(self.ids(),['A','B','B'])
        self.b.playFrom('playing',2);self.until(lambda:self.b.playerState=='playing')
        self.assertEqual(self.b.playerSourceIndex,1)
        self.assertEqual(self.b.playerSourceContext['page'],1)

    def test_last_requested_next_is_immediately_next_and_duplicates_stay_distinct(self):
        self.start('A','B')
        self.b.enqueueFrom('detail',0,True,self.other('X','First X'))
        self.b.enqueueFrom('detail',0,True,self.other('X','Second X'))
        self.assertEqual([s['title'] for s in self.b._queue.tracks],['A','Second X','First X','B'])
        self.assertEqual(self.b.playerQueueCount,4)

    def test_insert_while_paused_or_stopped_does_not_start_audio(self):
        self.start('A')
        self.b._player_state='paused'
        self.status.player_state='PAUSED'
        self.b._player_position=42
        self.b.enqueueFrom('detail',0,True,self.other())
        self.assertEqual(self.b.playerState,'paused')
        self.assertEqual(self.b.playerPosition,42)
        self.assertEqual(self.played,['A'])
        self.b.stopPlayback()
        self.b.enqueueFrom('detail',0,False,self.other('Y'))
        self.assertEqual(self.b.playerState,'idle')
        self.assertEqual(self.played,['A'])

    def test_loading_invalid_sources_and_nontracks_are_rejected(self):
        self.start('A')
        self.b._detail_tracks_model.set_items([dict(title='Album',kind='album',browseId='album')])
        before=self.ids()
        for source,index in [('missing',0),('detail',-1),('detail',99),('detail',0)]:
            self.assertFalse(self.b.enqueueFrom(source,index,True,{}))
        self.b._playback_transitioning=True
        self.assertFalse(self.b.enqueueFrom('detail',0,False,self.other()))
        self.b._playback_transitioning=False
        self.assertEqual(self.ids(),before)
        self.assertEqual(self.played,['A'])

    def test_like_changes_are_propagated_to_inserted_origin_snapshot(self):
        self.start('A')
        self.b.enqueueFrom('detail',0,True,self.other())
        self.b._propagate_like_status('X','DISLIKE')
        self.b.nextTrack();self.until(lambda:self.b.playerState=='playing')
        self.b.clearDetail();self.b.restorePlayingSource(1)
        self.assertEqual(self.b.detailTracksModel.snapshot()[0]['likeStatus'],'DISLIKE')

    def test_append_at_end_retargets_repeat_all_wrap_prefetch(self):
        self.start('A', 'B')
        self.b.cycleRepeat()
        self.until(lambda: 'B' in support.core.LOCAL_AUDIO_CACHE)
        self.b.nextTrack(); self.until(lambda: self.b.playerState == 'playing')
        self.assertTrue(self.b.enqueueFrom('detail', 0, False, self.other()))
        self.until(lambda: 'X' in support.core.LOCAL_AUDIO_CACHE)
        self.assertEqual(self.ids(), ['A', 'B', 'X'])
        self.assertEqual(self.b.playerQueueIndex, 1)
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['A', 'B', 'X'])
        self.assertEqual(self.downloads['X'], 1)

    def test_repeat_one_is_preserved_after_inserting_next(self):
        self.start('A', 'B')
        self.b.cycleRepeat(); self.b.cycleRepeat()
        self.b.enqueueFrom('detail', 0, True, self.other())
        self.assertEqual(self.b.playerRepeatMode, 'one')
        self.assertNotIn('X', self.downloads)
        self.eos(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['A', 'A'])
        self.b.nextTrack(); self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.played, ['A', 'A', 'X'])
