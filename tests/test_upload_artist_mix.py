"""Server-selected uploaded artist mixes, finite watch pages, no catalog reseed."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock, patch
import test_prefetch as support


class UploadArtistMixTests(support.AudioPlaybackTestCase):
    ARTIST = 'FEmusic_library_privately_owned_artist_detaila_po_mix'
    RADIO = 'MLPAa_po_server_returned_id'

    def setUp(self):
        super().setUp()
        self.api = Mock(); self.b._ytmusic = self.api
        self.rows = [dict(videoId=v, title=v, entityId=f'entity-{i}', likeStatus='LIKE',
                          artists=[dict(name='Artist', id=self.ARTIST)]) for i,v in enumerate(('A','A','B','C'))]
        self.api.get_library_upload_artists.return_value = [dict(browseId=self.ARTIST, artist='Artist', radioId=self.RADIO)]
        self.api.get_library_upload_artist.return_value = deepcopy(self.rows)
        self.pages = [([self.rows[3], self.rows[0], self.rows[1], self.rows[2]], False)]
        self.entered = Event(); self.block_page = -1; self.fail_page = -1
        self.calls = []; self.started = []
        self.b.artistPlaybackStarted.connect(lambda: self.started.append(True))
        self.b.playbackSourceCaptured.connect(lambda: self.b.setPlaybackSourceContext(
            dict(page=1, librarySection='upload_artists', libraryLabel='Nahraní interpreti')))
        case = self
        class Pages:
            def __init__(self, api, pid, *, shuffle, limit):
                case.calls.append((pid, shuffle, limit)); self.index = 0
            def next_page(self):
                i = self.index; self.index += 1
                if i == case.block_page:
                    case.entered.set(); case.release.wait(3)
                if i == case.fail_page: raise RuntimeError('offline')
                tracks, more = case.pages[i]
                return deepcopy(tracks), more
        p = patch.object(support.backend, 'WatchPages', Pages); p.start(); self.addCleanup(p.stop)

    def ready(self): self.until(lambda: not self.b.busy)

    def load(self, cards=True):
        if cards:
            self.b.loadLibrarySection('upload_artists','a_to_z'); self.ready()
        self.b.openLibraryItem('upload_artist',self.ARTIST,'','Artist'); self.ready()

    def play(self):
        self.assertTrue(self.b.startUploadArtistMix()); self.ready()
        self.until(lambda:self.b.playerState=='playing')

    def test_card_radio_id_server_order_occurrences_cover_repeat_and_natural_end(self):
        self.load(); state=self.b._detail_state(); self.play()
        self.assertEqual(self.calls,[(self.RADIO,False,None)])
        self.api.get_library_upload_artists.assert_called_once_with(limit=None,order='a_to_z')
        self.assertEqual([x['videoId'] for x in self.b._queue.tracks],['C','A','A','B'])
        self.assertEqual(self.b._queue_source_indices,[3,0,1,2])
        self.assertTrue(all(x['_guiKind']=='upload_song' for x in self.b._queue.tracks))
        self.assertFalse(self.b._queue.radio_active); self.assertFalse(self.b.playerQueueLoading)
        self.assertFalse(self.b._maybe_refill_radio())
        self.assertEqual(self.b._queue.source_playlist_id,self.RADIO)
        self.b.cycleRepeat(); self.b.cycleRepeat(); self.eos()
        self.until(lambda:self.b.playerState=='playing'); self.assertEqual(self.b.playerVideoId,'C')
        self.b.cycleRepeat(); self.b.cycleRepeat()
        self.b.playFrom('playing',3); self.until(lambda:self.b.playerState=='playing')
        self.eos(); self.until(lambda:self.b.playerState=='playing'); self.assertEqual(self.b.playerVideoId,'C')
        queue=self.b._queue; played=list(self.played)
        self.b.clearDetail(); self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual(self.b._detail_state(),state); self.assertIs(self.b._queue,queue); self.assertEqual(self.played,played)
        self.b.cycleRepeat(); self.b.cycleRepeat(); self.b.playFrom('playing',3); self.until(lambda:self.b.playerState=='playing')
        self.eos(); self.assertEqual(self.b.playerState,'idle')
        self.api.get_watch_playlist.assert_not_called(); self.api.get_artist.assert_not_called()

    def test_navigation_entry_exact_id_lookup_is_cached_and_missing_radio_disables_mix(self):
        self.load(cards=False)
        self.assertTrue(self.b.detailCanUploadArtistMix)
        self.api.get_library_upload_artists.assert_called_once_with(limit=None)
        self.b.openLibraryItem('upload_artist',self.ARTIST,'','Artist'); self.ready()
        self.assertEqual(self.api.get_library_upload_artists.call_count,1)
        self.b._detail_meta['radioId']=''; self.assertFalse(self.b.startUploadArtistMix())
        self.api.search.assert_not_called()

    def test_continuation_keeps_manual_rows_duplicates_metadata_and_no_catalog_refill(self):
        self.load(); self.pages=[([self.rows[3],self.rows[0],self.rows[1]],True),([self.rows[2],self.rows[3]],False)]
        self.block_page=1; self.play(); self.until(self.entered.is_set)
        self.assertTrue(self.b.playerQueueLoading)
        self.b.searchResultsModel.set_items([dict(videoId='manual',title='Manual',kind='song',likeStatus='LIKE')])
        self.assertTrue(self.b.enqueueFrom('search',0,False,dict(page=0)))
        queue=self.b._queue; played=list(self.played)
        self.b._player_state='paused'; self.release.set(); self.until(lambda:not self.b.playerQueueLoading)
        self.assertIs(self.b._queue,queue); self.assertEqual(self.played,played); self.assertEqual(self.b.playerState,'paused')
        self.assertEqual([x['videoId'] for x in queue.tracks],['C','A','A','manual','B','C'])
        self.assertEqual([x['_guiOrigin']['index'] for x in queue.tracks[-2:]],[2,-1])
        self.assertTrue(all(x['_guiKind']=='upload_song' for x in queue.tracks[-2:]))
        self.assertFalse(self.b._maybe_refill_radio())

    def test_eos_waits_for_continuation_and_stop_cancels_automatic_resume(self):
        self.load(); self.pages=[([self.rows[0]],True),([self.rows[2]],False)]
        self.block_page=1; self.play(); self.until(self.entered.is_set)
        self.eos(); self.assertEqual(self.b.playerState,'idle')
        self.b.stopPlayback(); played=list(self.played)
        self.release.set(); self.until(lambda:not self.b.playerQueueLoading)
        self.assertEqual(self.b.playerState,'idle'); self.assertEqual(self.played,played)
        self.assertEqual(self.b.playerQueueCount,2)

    def test_late_first_result_after_stop_navigation_or_new_queue_is_ignored(self):
        for action in ('stop','navigate','new'):
            with self.subTest(action=action):
                self.start('old','next'); self.load(); self.block_page=0; self.entered.clear(); self.release.clear()
                self.assertTrue(self.b.startUploadArtistMix()); self.until(self.entered.is_set)
                if action=='stop': self.b.stopPlayback()
                elif action=='navigate': self.b.clearDetail()
                else:
                    self.b.playFrom('detail',2); self.until(lambda:self.b.playerState=='playing')
                queue=self.b._queue; count=len(self.started)
                self.release.set(); self.ready(); self.assertIs(self.b._queue,queue)
                self.assertEqual(len(self.started),count)

    def test_transport_empty_first_page_and_continuation_errors_preserve_safe_state(self):
        self.start('old'); self.load(); queue=self.b._queue; self.b.cycleRepeat()
        self.fail_page=0; self.assertTrue(self.b.startUploadArtistMix()); self.ready()
        self.assertIs(self.b._queue,queue); self.assertEqual(self.b.playerRepeatMode,'all')
        self.fail_page=-1; self.pages=[([],False)]
        self.assertTrue(self.b.startUploadArtistMix()); self.ready(); self.assertIs(self.b._queue,queue)
        self.pages=[([self.rows[0]],True)]; self.fail_page=1
        self.play(); self.until(lambda:self.b.playerQueueIncomplete)
        self.assertEqual(self.b.playerQueueCount,1); self.assertFalse(self.b.playerQueueLoading)

    def test_lookup_failure_does_not_break_artist_navigation_or_local_shuffle(self):
        self.api.get_library_upload_artists.side_effect=RuntimeError('offline')
        self.load(cards=False); self.assertEqual(self.b.detailTracksModel.count,4)
        self.assertFalse(self.b.detailCanUploadArtistMix); self.assertTrue(self.b.detailCanShuffle)
        self.assertFalse(self.errors)

    def test_eos_resumes_next_upload_from_same_cursor(self):
        self.load(); self.pages=[([self.rows[0]],True),([self.rows[2]],False)]
        self.block_page=1; self.play(); self.until(self.entered.is_set)
        self.eos(); self.assertEqual(self.b.playerState,'idle')
        self.release.set(); self.until(lambda:self.b.playerState=='playing' and self.b.playerVideoId=='B')
        self.assertFalse(self.b.playerQueueLoading); self.assertEqual(self.calls,[(self.RADIO,False,None)])
        self.assertFalse(self.b._maybe_refill_radio())

    def test_pending_page_cannot_append_after_queue_replacement(self):
        self.load(); self.pages=[([self.rows[0]],True),([self.rows[2]],False)]
        self.block_page=1; self.play(); self.until(self.entered.is_set)
        old=self.b._queue
        self.b.playFrom('detail',3); self.until(lambda:self.b.playerState=='playing')
        queue=self.b._queue; count=queue.count()
        self.release.set(); self.b._executor.submit(lambda:None).result(timeout=3)
        self.app.processEvents()
        self.assertIs(self.b._queue,queue); self.assertEqual(queue.count(),count)
        self.assertEqual(old.count(),1)
