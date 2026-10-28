"""Online library songs: progressive browsing/playback and local full shuffle."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock,patch
import test_prefetch as support


class LibrarySongTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp();self.api=Mock();self.b._ytmusic=self.api
        self.rows=[dict(videoId=v,title=f'{i}-{v}',likeStatus='LIKE',duration='3:00',
                       artists=[dict(name='Artist',id='UCartist')],album=dict(name='Album',id='MPREalbum'))
                   for i,v in enumerate(('A','A','B','C','D'))]
        self.pages=[self.rows[:2],self.rows[2:4],self.rows[4:]]
        self.api.get_library_albums.return_value=[]
        self.api.get_library_upload_songs.return_value=[dict(videoId='upload',title='Upload',entityId='entity',likeStatus='LIKE')]
        self.entered=Event();self.block_page=1;self.fail_page=-1;self.calls=[]
        self.shuffle_entered=Event();case=self
        class Pages:
            def __init__(self,api,order=None):self.order=order;self.index=0
            def next_page(self):
                i=self.index;self.index+=1;case.calls.append((self.order,i))
                if i==case.block_page:case.entered.set();case.release.wait(3)
                if i==case.fail_page:raise RuntimeError('offline')
                return deepcopy(case.pages[i]),i<len(case.pages)-1
        p=patch.object(support.backend,'LibrarySongPages',Pages);p.start();self.addCleanup(p.stop)
        self.b.playbackSourceCaptured.connect(lambda:self.b.setPlaybackSourceContext(
            dict(page=1,librarySection='songs',libraryLabel='Skladby',libraryOrder='a_to_z')))

    def ready(self):self.until(lambda:not self.b.busy)
    def load(self,order='a_to_z'):self.b.loadLibrarySection('songs',order);self.ready()
    def complete(self):self.release.set();self.until(lambda:self.b.librarySongsComplete)
    def play(self,index=1):self.b.playFrom('library',index);self.until(lambda:self.b.playerState=='playing')
    def shuffle(self):self.assertTrue(self.b.shuffleLibrarySongs());self.until(lambda:not self.b.busy and self.b.playerState=='playing')

    def test_first_page_playable_actions_wait_and_full_queue_keeps_catalog_metadata(self):
        self.load();self.until(self.entered.is_set)
        self.assertTrue(self.b.librarySongsLoading);self.assertEqual(self.b.libraryItemsModel.count,2)
        self.b.selectTrack('library',1,False,False);self.assertEqual(self.b.selectedTrackIndices,[1])
        self.b.selectAllTracks('library');self.assertEqual(self.b.selectedTrackIndices,[1])
        self.assertFalse(self.b.shuffleLibrarySongs());self.assertFalse(self.b.shuffleUploadSongs())
        self.assertFalse(self.b.enqueueUploadCollection('library',True,{}))
        self.assertFalse(self.b.openUploadSongsPlaylistSave())
        self.play();self.complete();self.assertEqual(self.b.playerQueueCount,5)
        self.assertTrue(all(x['_guiKind']=='song' for x in self.b._queue.tracks))
        self.assertTrue(all(x['albumId']=='MPREalbum' for x in self.b._queue.tracks))
        self.assertEqual(self.b.playerSourceIndex,1);self.assertFalse(self.b._maybe_refill_radio())

    def test_local_shuffle_all_occurrences_exact_origins_and_cover_no_reload(self):
        self.load();self.until(self.entered.is_set);self.complete()
        before=self.b.libraryItemsModel.snapshot();calls=list(self.calls)
        with patch.object(support.backend.random,'shuffle',side_effect=lambda rows:rows.reverse()):self.shuffle()
        self.assertEqual([x['videoId'] for x in self.b._queue.tracks],['D','C','B','A','A'])
        self.assertEqual(self.b._queue_source_indices,[4,3,2,1,0])
        self.assertTrue(self.b._queue.shuffle_active);self.assertFalse(self.b._queue.radio_active)
        self.assertFalse(self.b._queue.source_playlist_id)
        self.assertEqual(self.b.libraryItemsModel.snapshot(),before);self.assertEqual(self.calls,calls)
        queue=self.b._queue;played=list(self.played)
        self.b.loadLibrarySection('albums','a_to_z');self.ready()
        self.assertTrue(self.b.restorePlayingSource(1));self.assertEqual(self.b.libraryItemsModel.snapshot(),before)
        self.assertEqual(self.b.playerVisibleSourceIndex,4);self.assertIs(self.b._queue,queue);self.assertEqual(self.played,played)
        self.api.get_watch_playlist.assert_not_called();self.api.get_liked_songs.assert_not_called()

    def test_shuffle_resets_repeat_and_finite_eos_repeat_one_all(self):
        self.load();self.until(self.entered.is_set);self.complete()
        self.play();self.b.cycleRepeat()
        with patch.object(support.backend.random,'shuffle',side_effect=lambda rows:rows.reverse()):self.shuffle()
        self.assertEqual(self.b.playerRepeatMode,'off')
        self.b.cycleRepeat();self.b.cycleRepeat();self.eos();self.until(lambda:self.b.playerState=='playing')
        self.assertEqual(self.b.playerVideoId,'D')
        self.b.cycleRepeat();self.b.cycleRepeat()
        self.b.playFrom('playing',4);self.until(lambda:self.b.playerState=='playing')
        self.eos();self.until(lambda:self.b.playerState=='playing');self.assertEqual(self.b.playerVideoId,'D')
        self.b.cycleRepeat();self.b.cycleRepeat()
        self.b.playFrom('playing',4);self.until(lambda:self.b.playerState=='playing');self.eos()
        self.assertEqual(self.b.playerState,'idle')

    def test_eos_wait_stop_and_manual_rows_preserve_audio_state(self):
        self.load();self.until(self.entered.is_set);self.play();self.eos()
        self.assertEqual(self.b.playerState,'idle');self.assertTrue(self.b._upload_stream['waiting'])
        self.b.stopPlayback();played=list(self.played);self.complete()
        self.assertEqual(self.b.playerState,'idle');self.assertEqual(self.played,played)
        self.assertEqual(self.b.playerQueueCount,5)

    def test_other_library_and_uploaded_song_load_do_not_cancel_playing_online_source(self):
        self.load();self.until(self.entered.is_set);self.play();queue=self.b._queue
        self.b.loadLibrarySection('upload_songs','a_to_z');self.release.set();self.ready()
        self.until(lambda:not self.b.playerQueueLoading)
        self.assertEqual(self.b.libraryItemsModel.snapshot()[0]['videoId'],'upload')
        self.assertEqual(queue.count(),5);self.assertFalse(self.b.playerQueueIncomplete)
        self.assertTrue(self.b.restorePlayingSource(1));self.assertEqual(self.b._library_section,'songs')
        self.assertEqual(self.b.libraryItemsModel.count,5)

    def test_new_online_order_invalidates_old_prefix_and_uses_requested_server_order(self):
        self.load();self.until(self.entered.is_set);self.play();old=self.b._queue
        self.b.loadLibrarySection('songs','z_to_a');self.release.set();self.ready()
        self.until(lambda:self.b.librarySongsComplete)
        self.assertEqual(old.count(),2);self.assertTrue(self.b.playerQueueIncomplete)
        self.assertIn(('z_to_a',0),self.calls);self.assertEqual(self.b.libraryItemsModel.count,5)

    def test_page_failure_keeps_prefix_and_disables_partial_shuffle(self):
        self.fail_page=1;self.load();self.until(self.entered.is_set);self.play();self.release.set()
        self.until(lambda:not self.b.librarySongsLoading)
        self.assertFalse(self.b.librarySongsComplete);self.assertEqual(self.b.libraryItemsModel.count,2)
        self.assertTrue(self.b.playerQueueIncomplete);self.assertFalse(self.b.shuffleLibrarySongs())
        self.assertEqual(self.played,['A']);self.assertFalse(self.errors)

    def test_late_shuffle_after_stop_and_failure_preserve_queue_and_repeat(self):
        self.load();self.until(self.entered.is_set);self.complete();self.play();self.b.cycleRepeat();queue=self.b._queue
        with patch.object(support.backend.random,'shuffle',side_effect=RuntimeError('offline')):
            self.assertTrue(self.b.shuffleLibrarySongs());self.ready()
        self.assertIs(self.b._queue,queue);self.assertEqual(self.b.playerRepeatMode,'all')
        self.release.clear()
        def hold(rows):self.shuffle_entered.set();self.release.wait(3);rows.reverse()
        with patch.object(support.backend.random,'shuffle',side_effect=hold):
            self.assertTrue(self.b.shuffleLibrarySongs());self.until(self.shuffle_entered.is_set)
            self.b.stopPlayback();self.release.set();self.ready()
        self.assertIs(self.b._queue,queue);self.assertEqual(self.b.playerState,'idle')

    def test_library_membership_update_is_not_undone_by_cover_hydration(self):
        self.load();self.until(self.entered.is_set);self.complete();self.play()
        item=self.b.libraryItemsModel.snapshot()[2]
        self.b._update_song_library_snapshots(item,False)
        self.assertEqual(self.b.libraryItemsModel.count,4)
        self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual(self.b.libraryItemsModel.count,4)
        self.assertNotIn('B',[x['videoId'] for x in self.b.libraryItemsModel.snapshot()])

    def test_empty_single_page_and_wrong_source_shuffle_guards(self):
        self.pages=[[]];self.load();self.assertTrue(self.b.librarySongsComplete)
        self.assertFalse(self.b.shuffleLibrarySongs())
        self.b._library_section='upload_songs';self.assertFalse(self.b.shuffleLibrarySongs())
