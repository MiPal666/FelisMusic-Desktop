"""Remove exact selected playlist occurrences in a single validated batch."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock
import test_prefetch as support


class PlaylistRemoveSelectionTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api=Mock();self.b._ytmusic=self.api
        self.data=dict(title='Mine',owned=True,tracks=[dict(videoId=v,title=v,setVideoId=s,likeStatus='LIKE')
            for v,s in [('A','a1'),('A','a2'),('B','b'),('C','c'),('A','a3')]])
        self.api.get_playlist.side_effect=lambda *a,**kw:deepcopy(self.data)
        self.api.remove_playlist_items.side_effect=self.remove
        self.dialogs=[];self.b.playlistBatchRemoveRequested.connect(lambda count,title:self.dialogs.append((count,title)))

    def remove(self,pid,videos):
        ids={x['setVideoId'] for x in videos}
        self.data['tracks']=[x for x in self.data['tracks'] if x['setVideoId'] not in ids]
        return {'status':'STATUS_SUCCEEDED'}
    def ready(self):self.until(lambda:not self.b.busy)
    def load(self):self.b.loadPlaylistTracks('mine','Mine');self.ready()
    def select(self,*indices):
        self.b.clearTrackSelection()
        for i,index in enumerate(indices):self.b.selectTrack('detail',index,i>0,False)
    def confirm(self):
        self.assertTrue(self.b.openSelectedPlaylistRemove())
        self.assertTrue(self.b.removeSelectedPlaylistItems());self.ready()
    def sids(self):return [x['setVideoId'] for x in self.b.detailTracksModel.snapshot()]
    def queue_sids(self):return [x.get('setVideoId') for x in self.b._queue.tracks]
    def play(self,index=0):
        self.b.playFrom('detail',index);self.until(lambda:self.b.playerState=='playing')

    def test_exact_duplicate_occurrences_single_batch_and_selection_clears(self):
        self.load();self.select(0,1);self.confirm()
        self.api.remove_playlist_items.assert_called_once_with('mine',[
            {'videoId':'A','setVideoId':'a1'},{'videoId':'A','setVideoId':'a2'}])
        self.assertEqual(self.sids(),['b','c','a3'])
        self.assertEqual(self.b.selectedTrackIndices,[]);self.assertEqual(self.dialogs,[(2,'Mine')])
        self.assertEqual(self.b._pending_removed_playlist_items['mine'],{'a1','a2'})

    def test_cancel_and_changed_selection_or_playlist_do_not_write(self):
        self.load();self.select(0,2)
        self.assertTrue(self.b.openSelectedPlaylistRemove());self.b.cancelSelectedPlaylistRemove()
        self.assertFalse(self.b.removeSelectedPlaylistItems());self.assertEqual(self.b.selectedTrackIndices,[0,2])
        self.assertTrue(self.b.openSelectedPlaylistRemove());self.select(1,3)
        self.assertFalse(self.b.removeSelectedPlaylistItems())
        self.assertTrue(self.b.openSelectedPlaylistRemove());self.b._detail_meta['playlistId']='other'
        self.assertFalse(self.b.removeSelectedPlaylistItems());self.api.remove_playlist_items.assert_not_called()

    def test_fresh_ownership_or_any_mismatch_prevents_entire_write(self):
        for change in ('foreign','wrong_video','ambiguous'):
            with self.subTest(change=change):
                self.data['owned']=True;self.data['tracks']=[dict(videoId=v,title=v,setVideoId=s,likeStatus='LIKE')
                    for v,s in [('A','a1'),('A','a2'),('B','b'),('C','c'),('A','a3')]]
                self.load();self.select(0,2)
                if change=='foreign':self.data['owned']=False
                elif change=='wrong_video':self.data['tracks'][2]['videoId']='changed'
                else:self.data['tracks'].append(deepcopy(self.data['tracks'][2]))
                self.confirm();self.api.remove_playlist_items.assert_not_called()
                self.assertEqual(self.sids(),['a1','a2','b','c','a3'])
                self.assertEqual(self.b.selectedTrackIndices,[0,2])

    def test_already_missing_selected_rows_skip_only_those_ids(self):
        self.load();self.select(0,2);self.data['tracks']=[x for x in self.data['tracks'] if x['setVideoId']!='a1']
        self.confirm()
        self.api.remove_playlist_items.assert_called_once_with('mine',[{'videoId':'B','setVideoId':'b'}])
        self.assertEqual(self.sids(),['a2','c','a3'])

    def test_failure_after_attempt_keeps_selection_and_does_not_auto_retry(self):
        self.load();self.select(0,2)
        self.api.remove_playlist_items.side_effect=RuntimeError('private response')
        self.confirm();self.assertEqual(self.b.selectedTrackIndices,[0,2])
        self.assertEqual(self.api.remove_playlist_items.call_count,1)
        self.assertNotIn('private response',self.errors[-1]);self.assertFalse(self.b.removeSelectedPlaylistItems())

    def test_batch_sync_preserves_audio_current_manual_copy_and_other_duplicate(self):
        self.load();self.play(1);queue=self.b._queue
        self.b._player_position=44;played=list(self.played)
        self.assertTrue(self.b.enqueueFrom('detail',2,False,{}));manual=self.b._queue.tracks[-1]
        self.select(0,2);self.confirm()
        self.assertIs(self.b._queue,queue);self.assertEqual(self.queue_sids(),['a2','c','a3','b'])
        self.assertIs(self.b._queue.tracks[-1],manual);self.assertEqual(self.played,played)
        self.assertEqual(self.b.playerPosition,44);self.assertEqual(self.b.playerQueueIndex,0)
        self.b.clearDetail();self.assertTrue(self.b.restorePlayingSource(1));self.assertEqual(self.sids(),['a2','c','a3'])

    def test_selected_current_finishes_once_then_next_survivor_even_repeat_one(self):
        self.load();self.play(1);self.b.cycleRepeat();self.b.cycleRepeat()
        self.select(1,2);self.confirm()
        self.assertEqual(self.queue_sids(),['a1','a2','c','a3'])
        self.assertTrue(self.b._queue.current()['_guiRemoveAfterPlayback']);self.assertEqual(self.played,['A'])
        self.eos();self.until(lambda:self.b.playerState=='playing' and self.b.playerVideoId=='C')
        self.assertEqual(self.queue_sids(),['a1','c','a3']);self.assertEqual(self.b.playerRepeatMode,'one')

    def test_select_all_removes_playlist_contents_but_keeps_playing_current_until_finish(self):
        self.load();self.play();self.b.selectAllTracks('detail');self.confirm()
        self.assertEqual(self.b.detailTracksModel.count,0);self.assertTrue(self.b.detailCanEditPlaylist)
        self.assertEqual(self.queue_sids(),['a1'])
        self.eos();self.assertFalse(self.b.playerHasTrack);self.assertEqual(self.b.playingTracksModel.count,0)

    def test_stale_server_rows_do_not_resurrect_batch_removals(self):
        self.load();self.select(0,2)
        self.api.remove_playlist_items.side_effect=None;self.api.remove_playlist_items.return_value='STATUS_SUCCEEDED'
        self.confirm();self.load();self.assertEqual(self.sids(),['a2','c','a3'])
        self.data['tracks']=[x for x in self.data['tracks'] if x['setVideoId'] not in ('a1','b')]
        self.load();self.assertNotIn('mine',self.b._pending_removed_playlist_items)

    def test_delayed_request_does_not_retarget_new_detail_or_clear_its_selection(self):
        self.load();self.select(0,2);entered=Event()
        def slow(*args):entered.set();self.release.wait(3);return self.remove(*args)
        self.api.remove_playlist_items.side_effect=slow
        self.assertTrue(self.b.openSelectedPlaylistRemove());self.assertTrue(self.b.removeSelectedPlaylistItems())
        self.until(entered.is_set);self.assertFalse(self.b.removeSelectedPlaylistItems())
        self.b._detail_meta=dict(kind='playlist',playlistId='other',owned=True)
        self.b._detail_title='Other';self.select(1,3)
        self.release.set();self.ready()
        self.assertEqual(self.b.detailTitle,'Other');self.assertEqual(self.b.selectedTrackIndices,[1,3])
        self.api.remove_playlist_items.assert_called_once_with('mine',[
            {'videoId':'A','setVideoId':'a1'},{'videoId':'B','setVideoId':'b'}])

    def test_guards_for_single_row_foreign_album_missing_ids_and_duplicate_set_ids(self):
        self.load();self.select(0);self.assertFalse(self.b.selectionCanRemovePlaylist)
        self.select(0,1);self.assertTrue(self.b.selectionCanRemovePlaylist)
        for meta in (dict(kind='playlist',owned=False,playlistId='mine'),dict(kind='album',owned=True,playlistId='mine'),
                     dict(kind='playlist',owned=True,playlistId='mine',playlistLoadState='loading')):
            self.b._detail_meta=meta;self.assertFalse(self.b.openSelectedPlaylistRemove())
        self.b._detail_meta=dict(kind='playlist',owned=True,playlistId='mine')
        rows=self.b.detailTracksModel.snapshot();rows[1]['setVideoId']='a1'
        self.b.detailTracksModel.set_items(rows);self.select(0,1);self.assertFalse(self.b.selectionCanRemovePlaylist)
        rows[1]['setVideoId']='';self.b.detailTracksModel.set_items(rows);self.select(0,1)
        self.assertFalse(self.b.openSelectedPlaylistRemove());self.api.remove_playlist_items.assert_not_called()
