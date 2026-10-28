"""Progressive upload-song browsing/playback, without account/network/audio."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock, patch
import test_prefetch as support


class UploadPagingTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api=Mock();self.b._ytmusic=self.api
        self.api.get_library_albums.return_value=[]
        self.api.get_library_upload_album.return_value=dict(title='Album',tracks=[])
        self.rows=[dict(videoId=v,title=f'{i}-{v}',entityId=f'entity-{i}',likeStatus='LIKE',
            album=dict(name='Album',id='FEmusic_library_privately_owned_release_detailb_po_album'),
            artists=[dict(name='Artist',id='FEmusic_library_privately_owned_artist_detaila_po_artist')])
            for i,v in enumerate(('A','A','B','C','D'))]
        self.pages=[self.rows[:2],self.rows[2:4],self.rows[4:]]
        self.entered=Event();self.block_page=1;self.fail_page=-1;self.calls=[];self.pagers=[]
        case=self
        class Pages:
            def __init__(self,api,order=None):
                self.order=order;self.index=0;case.pagers.append(self)
            def next_page(self):
                index=self.index;self.index+=1;case.calls.append((self.order,index))
                if index==case.block_page:
                    case.entered.set();case.release.wait(3)
                if index==case.fail_page:raise RuntimeError('offline')
                return deepcopy(case.pages[index]),index<len(case.pages)-1
        p=patch.object(support.backend,'UploadSongPages',Pages);p.start();self.addCleanup(p.stop)
        self.b.playbackSourceCaptured.connect(lambda:self.b.setPlaybackSourceContext(
            dict(page=1,librarySection='upload_songs',libraryOrder='a_to_z')))

    def load(self,order='a_to_z'):
        self.b.loadLibrarySection('upload_songs',order);self.until(lambda:not self.b.busy)
    def complete(self):
        self.release.set();self.until(lambda:self.b.uploadSongsComplete)
    def play(self,index=0):
        self.b.playFrom('library',index);self.until(lambda:self.b.playerState=='playing')

    def test_first_block_is_usable_before_background_and_whole_actions_wait(self):
        self.load();self.until(self.entered.is_set)
        self.assertEqual(self.b.libraryItemsModel.count,2);self.assertTrue(self.b.uploadSongsLoading)
        self.b.selectTrack('library',1,False,False);self.assertEqual(self.b.selectedTrackIndices,[1])
        self.b.selectTrack('library',0,True,False);self.assertEqual(self.b.selectedTrackIndices,[1])
        self.assertFalse(self.b.shuffleUploadSongs());self.assertFalse(self.b.openUploadSongsPlaylistSave())
        self.assertFalse(self.b.enqueueUploadCollection('library',False,{}))
        self.assertFalse(self.b.enqueueFrom('library',0,False,{}))
        self.play(1);self.assertEqual(self.played,['A']);self.assertTrue(self.b.playerQueueLoading)
        self.complete();self.assertEqual(self.b.libraryItemsModel.count,5)
        self.assertEqual(self.b.playerQueueCount,5);self.assertFalse(self.b.playerQueueLoading)
        self.assertEqual([x['videoId'] for x in self.b._queue.tracks],['A','A','B','C','D'])
        self.assertTrue(all(x['_guiKind']=='upload_song' for x in self.b._queue.tracks))
        self.assertEqual(self.b.playerSourceIndex,1)

    def test_append_preserves_audio_prefetch_repeat_manual_rows_and_cover_snapshot(self):
        self.load();self.until(self.entered.is_set);self.play(1)
        queue=self.b._queue;self.b._player_position=42;self.b.cycleRepeat();played=list(self.played)
        self.b.searchResultsModel.set_items([dict(videoId='manual',title='Manual',likeStatus='LIKE')])
        self.assertTrue(self.b.enqueueFrom('search',0,False,dict(page=0)))
        self.complete();self.assertIs(self.b._queue,queue);self.assertEqual(self.played,played)
        self.assertEqual(self.b.playerPosition,42);self.assertEqual(self.b.playerRepeatMode,'all')
        self.assertEqual([x['videoId'] for x in queue.tracks],['A','A','manual','B','C','D'])
        self.b.loadLibrarySection('albums','a_to_z');self.until(lambda:not self.b.busy)
        self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual(self.b.libraryItemsModel.count,5);self.assertTrue(self.b.uploadSongsComplete)
        self.assertEqual(self.b.playerVisibleSourceIndex,1)

    def test_eos_waits_and_resumes_with_next_page_while_repeat_all_does_not_wrap_prefix(self):
        self.load();self.until(self.entered.is_set);self.play(1);self.b.cycleRepeat()
        self.eos();self.assertEqual(self.b.playerState,'idle')
        self.assertTrue(self.b._upload_stream['waiting'])
        self.complete();self.until(lambda:self.b.playerState=='playing' and self.b.playerVideoId=='B')
        self.assertEqual(self.played,['A','B'])

    def test_stop_during_eos_waiting_does_not_resume_after_append(self):
        self.load();self.until(self.entered.is_set);self.play(1);self.eos();self.b.stopPlayback()
        played=list(self.played);self.complete()
        self.assertEqual(self.b.playerState,'idle');self.assertEqual(self.played,played)
        self.assertEqual(self.b.playerQueueCount,5)

    def test_pause_and_repeat_one_survive_new_pages(self):
        self.load();self.until(self.entered.is_set);self.play(1)
        self.b.cycleRepeat();self.b.cycleRepeat();self.eos();self.until(lambda:self.b.playerState=='playing')
        self.assertEqual(self.b.playerSourceIndex,1)
        self.b._player_state='paused';played=list(self.played);self.complete()
        self.assertEqual(self.b.playerState,'paused');self.assertEqual(self.played,played)
        self.assertEqual(self.b.playerRepeatMode,'one')

    def test_navigation_keeps_playing_load_without_overwriting_other_library(self):
        self.load();self.until(self.entered.is_set);self.play()
        self.b.loadLibrarySection('albums','a_to_z');self.release.set();self.until(lambda:not self.b.busy)
        self.until(lambda:not self.b.playerQueueLoading)
        self.assertEqual(self.b.libraryItemsModel.count,0)
        self.assertTrue(self.b.restorePlayingSource(1));self.assertEqual(self.b.libraryItemsModel.count,5)

    def test_unplayed_abandoned_load_stops_and_new_foreground_load_wins(self):
        self.load();self.until(self.entered.is_set)
        old=self.b._upload_load
        self.b.loadLibrarySection('albums','a_to_z');self.release.set();self.until(lambda:not self.b.busy)
        self.b._executor.submit(lambda:None).result(timeout=3);self.app.processEvents()
        self.assertEqual(self.b._library_section,'albums');self.assertEqual(self.b.libraryItemsModel.count,0)
        self.assertLessEqual(len(old['items']),4)
        self.assertFalse(any(index==2 for _,index in self.calls))

    def test_reload_different_order_does_not_append_old_pages_to_new_queue_or_view(self):
        self.load();self.until(self.entered.is_set);self.play()
        old=self.b._queue
        self.b.loadLibrarySection('upload_songs','z_to_a');self.release.set();self.until(lambda:not self.b.busy)
        self.until(lambda:self.b.uploadSongsComplete)
        self.assertEqual(old.count(),2);self.assertTrue(self.b.playerQueueIncomplete)
        self.assertEqual(self.b._library_order,'z_to_a');self.assertEqual(self.b.libraryItemsModel.count,5)
        self.assertEqual(self.pagers[-1].order,'z_to_a')

    def test_first_and_later_failures_are_local_and_keep_prefix(self):
        self.fail_page=1;self.load();self.until(self.entered.is_set);self.play();self.release.set()
        self.until(lambda:not self.b.uploadSongsLoading)
        self.assertFalse(self.b.uploadSongsComplete);self.assertEqual(self.b.libraryItemsModel.count,2)
        self.assertTrue(self.b.playerQueueIncomplete);self.assertEqual(self.played,['A']);self.assertFalse(self.errors)
        self.b.playFrom('library',1);self.assertEqual(self.played,['A'])
        self.fail_page=0;self.load()
        self.assertFalse(self.b.uploadSongsLoading);self.assertFalse(self.b.uploadSongsComplete)
        self.assertEqual(self.b.libraryItemsModel.count,0);self.assertFalse(self.b.busy)

    def test_empty_middle_pages_and_large_duplicates_are_kept_until_real_end(self):
        self.pages=[self.rows[:2],[],[dict(self.rows[i%5],title=str(i)) for i in range(2500)]]
        self.load();self.until(self.entered.is_set);self.play();self.complete()
        self.assertEqual(self.b.libraryItemsModel.count,2502);self.assertEqual(self.b.playerQueueCount,2502)
        self.assertEqual(len(self.calls),3)

    def test_single_empty_page_completes_without_continuation(self):
        self.pages=[[]];self.load()
        self.assertTrue(self.b.uploadSongsComplete);self.assertFalse(self.b.uploadSongsLoading)
        self.assertEqual(self.b.libraryItemsModel.count,0);self.assertFalse(self.b.shuffleUploadSongs())

    def test_navigation_from_prefix_and_back_resumes_same_load(self):
        self.load();self.until(self.entered.is_set)
        self.assertTrue(self.b.openUploadTrackTarget('library',0,'album','',
            dict(page=1,librarySection='upload_songs',libraryOrder='a_to_z')))
        self.release.set();self.until(lambda:not self.b.busy)
        self.assertEqual(self.b.detailMeta['kind'],'upload_album')
        self.b.backDetail();self.until(lambda:self.b.uploadSongsComplete)
        self.assertEqual(self.b.libraryItemsModel.count,5)

    def test_new_queue_is_not_extended_by_old_upload_pages(self):
        self.load();self.until(self.entered.is_set);self.play();old=self.b._queue
        self.b.searchResultsModel.set_items([dict(videoId='new',title='New',likeStatus='LIKE')])
        self.b.playFrom('search',0);self.until(lambda:self.b.playerState=='playing' and self.b.playerVideoId=='new')
        self.complete();self.assertEqual(old.count(),2);self.assertEqual(self.b.playerQueueCount,1)

    def test_complete_shuffle_cover_remains_complete_after_a_later_reload(self):
        self.load();self.until(self.entered.is_set);self.complete()
        self.assertEqual(len(self.b._upload_collection_items('library')),5)
        self.assertTrue(self.b.shuffleUploadSongs());self.until(lambda:not self.b.busy and self.b.playerState=='playing')
        self.assertEqual(self.b.playerQueueCount,5)
        self.assertEqual(sorted(self.b._queue_source_indices),list(range(5)))
        queue=self.b._queue;source=self.b.libraryItemsModel.snapshot()
        self.load('z_to_a');self.complete()
        self.assertTrue(self.b.restorePlayingSource(1))
        self.assertTrue(self.b.uploadSongsComplete);self.assertEqual(self.b.libraryItemsModel.snapshot(),source)
        self.assertIs(self.b._queue,queue)
