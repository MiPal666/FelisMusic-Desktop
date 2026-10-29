"""Whole catalog album insertion through the existing noninterrupting queue path."""
from copy import deepcopy
from unittest.mock import Mock
import test_prefetch as support


class AlbumEnqueueTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp(); self.api = Mock(); self.b._ytmusic = self.api
        self.context = dict(page=1, librarySection='albums', libraryLabel='Alba', libraryOrder='a_to_z')
        self.rows = [dict(videoId=vid, title=f'Track {i}', duration='3:00', likeStatus='LIKE',
            artists=[dict(id='UCartist', name='Artist')]) for i, vid in enumerate(('X','Y','X'))]
        self.api.get_album.return_value = dict(title='Online Album', tracks=deepcopy(self.rows), audioPlaylistId='OLAKalbum')

    def open_album(self):
        self.b._library_section = 'albums'
        self.b._library_items_model.set_items([dict(kind='album', browseId='MPREalbum', title='Online Album')])
        self.b.openLibraryItem('album','MPREalbum','','Online Album')
        self.until(lambda:not self.b.busy)

    def ids(self):return [x['videoId'] for x in self.b._queue.tracks]

    def test_next_and_append_preserve_current_audio_position_repeat_and_album_order(self):
        for next_ in (True,False):
            with self.subTest(next=next_):
                self.start('A','B','C'); self.b.nextTrack();self.until(lambda:self.b.playerState=='playing')
                self.b._repeat_mode='one';self.b._queue.radio_active=True
                self.open_album();before=self.b._detail_state();queue=self.b._queue
                self.b._player_position=42;played=list(self.played);stops=list(self.stops);calls=list(self.api.mock_calls)
                self.assertTrue(self.b.detailCanEnqueueAlbum)
                self.assertTrue(self.b.enqueueAlbumCollection(next_,self.context))
                expected=['A','B','X','Y','X','C'] if next_ else ['A','B','C','X','Y','X']
                self.assertEqual(self.ids(),expected)
                self.assertEqual([x['videoId'] for x in self.b.playingTracksModel.snapshot()],expected)
                self.assertIs(self.b._queue,queue);self.assertEqual(self.b.playerQueueIndex,1)
                self.assertEqual(self.b.playerTitle,'B');self.assertEqual(self.b.playerPosition,42)
                self.assertEqual(self.b.playerState,'playing');self.assertEqual(self.b.playerRepeatMode,'one')
                self.assertTrue(queue.radio_active);self.assertEqual(self.played,played);self.assertEqual(self.stops,stops)
                self.assertEqual(self.b._detail_state(),before);self.assertEqual(self.api.mock_calls,calls)

    def test_inserted_occurrence_keeps_album_links_and_cover_source(self):
        self.start('A','B');self.open_album();state=self.b._detail_state()
        self.b.enqueueAlbumCollection(True,self.context)
        inserted=self.b._queue.tracks[1:4]
        self.assertEqual([x['_guiOrigin']['index'] for x in inserted],[0,1,2])
        self.assertTrue(all(x['_guiManualEnqueue'] for x in inserted))
        self.assertEqual(inserted[2]['albumId'],'MPREalbum')
        self.assertEqual(inserted[2]['_guiArtistLinks'],[dict(id='UCartist',name='Artist')])
        self.b.playFrom('playing',3);self.until(lambda:self.b.playerState=='playing')
        self.b.clearDetail();self.assertTrue(self.b.restorePlayingSource(1))
        self.assertEqual(self.b._detail_state(),state);self.assertEqual(self.b.playerSourceIndex,2)
        self.assertEqual(self.b.playerSourceContext,self.context)
        self.api.get_album.assert_called_once_with('MPREalbum')

    def test_empty_queue_is_prepared_without_starting_then_plays(self):
        self.open_album();self.assertTrue(self.b.enqueueAlbumCollection(True,self.context))
        self.assertEqual(self.ids(),['X','Y','X']);self.assertFalse(self.played);self.assertFalse(self.stops)
        self.assertEqual(self.b.playerState,'idle');self.assertEqual(self.b.playingListTitle,'Online Album')
        self.b.togglePlayPause();self.until(lambda:self.b.playerState=='playing');self.assertEqual(self.played,['X'])

    def test_pause_and_stop_are_preserved(self):
        self.start('A','B');self.open_album();self.b._player_state='paused'
        played=list(self.played);self.assertTrue(self.b.enqueueAlbumCollection(False,self.context))
        self.assertEqual(self.b.playerState,'paused');self.assertEqual(self.played,played)
        self.b.stopPlayback();self.assertTrue(self.b.enqueueAlbumCollection(True,self.context))
        self.assertEqual(self.b.playerState,'idle');self.assertEqual(self.played,played)

    def test_other_sections_incomplete_empty_busy_and_transition_do_not_insert(self):
        self.start('A');self.open_album();ids=self.ids()
        for kind in ('playlist','artist','upload_album','upload_artist',''):
            self.b._detail_meta['kind']=kind
            self.assertFalse(self.b.detailCanEnqueueAlbum);self.assertFalse(self.b.enqueueAlbumCollection(True,self.context))
        self.b._detail_meta['kind']='album'
        for state in ('loading','error'):
            self.b._detail_meta['playlistLoadState']=state
            self.assertFalse(self.b.enqueueAlbumCollection(True,self.context))
        self.b._detail_meta.pop('playlistLoadState')
        self.b._busy=True;self.assertFalse(self.b.enqueueAlbumCollection(True,self.context));self.b._busy=False
        self.b._playback_transitioning=True;self.assertFalse(self.b.enqueueAlbumCollection(True,self.context));self.b._playback_transitioning=False
        self.b._detail_tracks_model.clear();self.assertFalse(self.b.detailCanEnqueueAlbum)
        self.assertFalse(self.b.enqueueAlbumCollection(True,self.context));self.assertEqual(self.ids(),ids)

    def test_unavailable_rows_are_skipped_and_duplicate_occurrences_remain(self):
        self.api.get_album.return_value['tracks'] += [dict(title='Unavailable',videoId='bad',isAvailable=False),dict(title='No ID')]
        self.open_album();self.assertTrue(self.b.enqueueAlbumCollection(False,self.context))
        self.assertEqual(self.ids(),['X','Y','X'])
