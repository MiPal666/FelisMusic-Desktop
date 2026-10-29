"""Foreign playlist bookmarks, separate from editing/deleting owned playlists."""
from copy import deepcopy
from threading import Event
from unittest.mock import Mock, patch
import test_prefetch as support
from test_album_library import AlbumAPI, response
from felismusic_gui.playlist_library import load_library_playlist, playlist_library_controls


class PlaylistAPI(AlbumAPI):
    def __init__(self):
        super().__init__();self.target='PLforeign';self.owned=False
        self.delete_playlist=Mock();self.edit_playlist=Mock();self.remove_playlist_items=Mock()

    def get_playlist(self, playlist_id, limit=0):
        self._send_request('browse', dict(browseId='VL'+playlist_id.removeprefix('VL')))
        return dict(title='Foreign',id=playlist_id,owned=self.owned,tracks=[
            dict(videoId=vid,title=vid,duration='3:00',setVideoId=f'set-{i}',likeStatus='LIKE')
            for i,vid in enumerate(('X','Y','X'))])

    def get_library_playlists(self, **kwargs):
        return [dict(title='Own',playlistId='PLown')] + ([dict(title='Foreign',playlistId='PLforeign')] if self.member else [])


class PlaylistLibraryTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp();self.api=PlaylistAPI();self.b._ytmusic=self.api;self.b._set_connected(True)
        self.b._library_section='playlists'
        class Pages:
            def __init__(self, api, pid, **kwargs):self.api,self.pid,self.metadata=api,pid,{}
            def next_page(self):
                data=load_library_playlist(self.api,self.pid)
                self.metadata={k:v for k,v in data.items() if k!='tracks'}
                return data['tracks'],False
        pager=patch.object(support.backend,'PlaylistPages',Pages);pager.start();self.addCleanup(pager.stop)

    def open(self, pid='PLforeign'):
        self.b.loadPlaylistTracks(pid,'Foreign');self.until(lambda:not self.b.busy)

    def change(self):
        self.assertTrue(self.b.changePlaylistLibrary());self.until(lambda:not self.b.busy)

    def test_add_remove_foreign_playlist_keeps_exact_queue_audio_and_cover_and_own_cards(self):
        self.open();self.b.playFrom('detail',2);self.until(lambda:self.b.playerState=='playing')
        before=deepcopy(self.b.detailTracksModel.snapshot());queue=self.b._queue;current=queue.current()
        self.b._player_position=42;played=list(self.played);stops=list(self.stops)
        self.change();self.assertTrue(self.b.detailMeta['playlistLibrary']['inLibrary'])
        self.assertEqual({x['playlistId'] for x in self.b.libraryItemsModel.snapshot()},{'PLown','PLforeign'})
        self.api.rate_playlist.assert_called_with('PLforeign',support.core.LikeStatus.LIKE)
        self.change();self.assertFalse(self.b.detailMeta['playlistLibrary']['inLibrary'])
        self.api.rate_playlist.assert_called_with('PLforeign',support.core.LikeStatus.INDIFFERENT)
        self.assertEqual([x['playlistId'] for x in self.b.libraryItemsModel.snapshot()],['PLown'])
        self.assertEqual(self.b.detailTracksModel.snapshot(),before)
        self.assertIs(self.b._queue,queue);self.assertIs(queue.current(),current)
        self.assertEqual(self.b.playerPosition,42);self.assertEqual(self.played,played);self.assertEqual(self.stops,stops)
        self.assertEqual([x['setVideoId'] for x in queue.tracks],['set-0','set-1','set-2'])
        self.b.clearDetail();self.b.restorePlayingSource(1)
        self.assertFalse(self.b.detailMeta['playlistLibrary']['inLibrary']);self.assertEqual(self.b.playerSourceIndex,2)
        self.assertEqual([x['playlistId'] for x in self.b.libraryItemsModel.snapshot()],['PLown'])
        self.api.delete_playlist.assert_not_called();self.api.edit_playlist.assert_not_called()
        self.api.remove_playlist_items.assert_not_called();self.api.rate_song.assert_not_called()

    def test_own_playlist_and_special_sources_have_no_bookmark_action(self):
        self.api.owned=True;self.open();self.assertFalse(self.b.detailCanPlaylistLibrary)
        self.assertFalse(self.b.changePlaylistLibrary())
        self.api.owned=False;self.open()
        for pid in ('LM','SE','HL','RDmix','OLAKalbum','MLprivate'):
            self.b._detail_meta.update(playlistId=pid,playlistLibrary=dict(playlistId=pid,inLibrary=False))
            self.assertFalse(self.b.detailCanPlaylistLibrary);self.assertFalse(self.b.changePlaylistLibrary())
        self.api.rate_playlist.assert_not_called()

    def test_fresh_ownership_or_target_changes_prevent_write_and_require_reopen(self):
        for own in (True,False):
            self.api.owned=False;self.api.target='PLforeign';self.open()
            if own:self.api.owned=True
            else:self.api.target='PLother'
            self.change();self.assertFalse(self.b.detailCanPlaylistLibrary)
            self.api.rate_playlist.assert_not_called();self.assertTrue(self.errors)

    def test_vl_alias_and_external_change_are_idempotent(self):
        self.open('VLPLforeign');self.api.member=True;self.change()
        self.api.rate_playlist.assert_not_called();self.assertTrue(self.b.detailMeta['playlistLibrary']['inLibrary'])

    def test_pending_write_preserves_target_across_navigation_and_blocks_repetition(self):
        self.open();entered=Event()
        def write(*args):entered.set();self.release.wait(3);return self.api.write(*args)
        self.api.rate_playlist.side_effect=write
        self.assertTrue(self.b.changePlaylistLibrary());self.until(entered.is_set)
        self.assertFalse(self.b.changePlaylistLibrary())
        self.b._detail_meta=dict(kind='playlist',playlistId='PLother')
        self.release.set();self.until(lambda:not self.b.busy)
        self.assertEqual(self.b.detailMeta,dict(kind='playlist',playlistId='PLother'))
        self.api.rate_playlist.assert_called_once_with('PLforeign',support.core.LikeStatus.LIKE)

    def test_write_failure_and_readback_mismatch_never_delete_or_repeat(self):
        for error in (True,False):
            self.api.missing=False;self.open();self.api.ignore_write=not error
            self.api.rate_playlist.side_effect=RuntimeError('offline') if error else self.api.write
            before=self.api.rate_playlist.call_count
            self.change();self.assertFalse(self.b.detailCanPlaylistLibrary)
            self.assertFalse(self.b.changePlaylistLibrary());self.assertEqual(self.api.rate_playlist.call_count,before+1)
        self.api.delete_playlist.assert_not_called()

    def test_verified_state_survives_overview_failure_and_new_pending_own_playlist_is_retained(self):
        self.b._pending_created_playlists['PLnew']=dict(kind='playlist',playlistId='PLnew',title='New')
        self.open();self.change()
        self.assertIn('PLnew',[x['playlistId'] for x in self.b.libraryItemsModel.snapshot()])
        self.api.get_library_playlists=Mock(side_effect=RuntimeError('offline overview'))
        self.change();self.assertFalse(self.b.detailMeta['playlistLibrary']['inLibrary'])
        self.assertIn('Přehled Playlistů',self.b.status)

    def test_offline_closing_and_missing_controls_never_write(self):
        self.api.missing=True;self.open();self.assertFalse(self.b.changePlaylistLibrary())
        self.api.missing=False;self.open();self.b._set_connected(False)
        self.assertFalse(self.b.changePlaylistLibrary());self.b._set_connected(True)
        self.b._closing.set();self.assertFalse(self.b.changePlaylistLibrary());self.b._closing.clear()
        self.api.rate_playlist.assert_not_called()

    def test_bookmarked_state_is_kept_in_live_load_metadata_and_cover_restoration(self):
        self.open();self.b.playFrom('detail',0);self.until(lambda:self.b.playerState=='playing')
        self.change()
        self.assertTrue(self.b._playlist_load['meta']['playlistLibrary']['inLibrary'])
        self.b.clearDetail();self.b.restorePlayingSource(1)
        self.assertTrue(self.b.detailMeta['playlistLibrary']['inLibrary'])


class PlaylistLibraryParserTests(support.unittest.TestCase):
    def test_exact_foreign_target_one_read_and_missing_controls_are_not_membership(self):
        api=PlaylistAPI();send=api._send_request
        for member in (True,False):
            api.member=member
            self.assertEqual(load_library_playlist(api,'PLforeign')['_playlistLibraryControls'],
                             dict(playlistId='PLforeign',inLibrary=member))
            self.assertEqual(api._send_request,send)
        self.assertEqual(len(api.calls),2)
        for owned in (True,None):
            self.assertIsNone(playlist_library_controls(response(target='PLforeign'),'PLforeign',dict(owned=owned)))
        self.assertIsNone(playlist_library_controls(response(target='PLforeign'),'PLforeign',dict(owned=False,id='PLother')))
