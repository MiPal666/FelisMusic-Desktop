"""Exact album header controls and verified writes, with synthetic account/audio."""
import unittest
from copy import deepcopy
from threading import Event
from unittest.mock import Mock
import test_prefetch as support
from felismusic_gui.album_library import (load_catalog_album, album_library_controls,
    TWO_COLUMN_RENDERER, TAB_CONTENT, SECTION_LIST_ITEM, RESPONSIVE_HEADER)


def response(status='LIKE', target='OLAKalbum', duplicate=False, missing=False, missing_toggle=False):
    # Real YTM keeps these actions fixed, even after the album has been saved.
    button = dict(toggleButtonRenderer=dict(isToggled=status == 'INDIFFERENT', defaultServiceEndpoint=dict(
        likeEndpoint=dict(status='DISLIKE' if status == 'DISLIKE' else 'LIKE', target=dict(playlistId=target))),
        toggledServiceEndpoint=dict(likeEndpoint=dict(status='INDIFFERENT', target=dict(playlistId=target)))))
    if missing_toggle:
        button['toggleButtonRenderer'].pop('isToggled')
    header = dict(buttons=[] if missing else [button, deepcopy(button)] if duplicate else [button])
    for key in reversed([*TWO_COLUMN_RENDERER, *TAB_CONTENT, *SECTION_LIST_ITEM, *RESPONSIVE_HEADER]):
        if isinstance(key, int):
            value = [None] * (key + 1); value[key] = header; header = value
        else: header = {key: header}
    return header


class AlbumAPI:
    def __init__(self):
        self.member = False; self.calls = []; self.missing = False
        self.target = 'OLAKalbum'; self.ignore_write = False
        self.rate_playlist = Mock(side_effect=self.write)
        self.rate_song = Mock(); self.edit_song_library_status = Mock()

    def _send_request(self, endpoint, body):
        self.calls.append((endpoint, dict(body)))
        return response('INDIFFERENT' if self.member else 'LIKE', self.target, missing=self.missing)

    def get_album(self, browse_id):
        self._send_request('browse', dict(browseId=browse_id))
        return dict(title='Album', audioPlaylistId='OLAKalbum', likeStatus='INDIFFERENT',
                    artists=[dict(name='Artist')], year='2024', tracks=[
                        dict(videoId='X', title='Song', duration='3:00', likeStatus='LIKE')])

    def get_library_albums(self, **kwargs):
        return [dict(title='Album',browseId='MPREalbum')] if self.member else []

    def write(self, playlist_id, rating):
        if not self.ignore_write: self.member = rating == support.core.LikeStatus.LIKE
        return {}


class AlbumLibraryParserTests(unittest.TestCase):
    def test_same_request_exact_header_target_and_actual_state_without_shared_client_patch(self):
        api = AlbumAPI(); send = api._send_request
        for member in (False, True):
            api.member = member
            data = load_catalog_album(api, 'MPREalbum')
            self.assertEqual(data['_albumLibraryControls'], dict(playlistId='OLAKalbum', inLibrary=member))
            self.assertEqual(api._send_request, send)
        self.assertEqual(api.calls, [('browse',dict(browseId='MPREalbum'))]*2)

    def test_missing_ambiguous_mismatched_or_unsupported_controls_do_not_infer_membership(self):
        for raw in (response(missing=True), response(duplicate=True), response(target='other'), response(status='DISLIKE'), response(missing_toggle=True), {}):
            self.assertIsNone(album_library_controls(raw, 'OLAKalbum'))
        api=AlbumAPI();api.missing=True
        self.assertIsNone(load_catalog_album(api,'MPREalbum')['_albumLibraryControls'])

    def test_saved_album_uses_toggled_action_despite_unchanged_default_like_endpoint(self):
        self.assertEqual(album_library_controls(response('LIKE'), 'OLAKalbum')['inLibrary'], False)
        self.assertEqual(album_library_controls(response('INDIFFERENT'), 'OLAKalbum')['inLibrary'], True)


class AlbumLibraryTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp(); self.api=AlbumAPI();self.b._ytmusic=self.api;self.b._set_connected(True)
        self.b._library_section='albums'

    def open(self):
        self.b.openLibraryItem('album','MPREalbum','','Album');self.until(lambda:not self.b.busy)

    def change(self):
        self.assertTrue(self.b.changeAlbumLibrary());self.until(lambda:not self.b.busy)

    def test_add_remove_updates_cards_and_cover_metadata_without_audio_or_song_rating_changes(self):
        self.start('A','B');self.b._library_items_model.clear();self.open()
        self.b._player_position=42;queue=self.b._queue;played=list(self.played);stops=list(self.stops)
        self.assertTrue(self.b.detailCanAlbumLibrary);self.change()
        self.assertTrue(self.b.detailMeta['albumLibrary']['inLibrary'])
        self.assertEqual(self.b.libraryItemsModel.snapshot()[0]['browseId'],'MPREalbum')
        self.api.rate_playlist.assert_called_with('OLAKalbum',support.core.LikeStatus.LIKE)
        # Start the album once, then remove membership while it keeps playing.
        self.b.playFrom('detail',0);self.until(lambda:self.b.playerState=='playing')
        self.b._player_position=37;queue=self.b._queue;played=list(self.played);stops=list(self.stops)
        self.change();self.assertFalse(self.b.detailMeta['albumLibrary']['inLibrary'])
        self.api.rate_playlist.assert_called_with('OLAKalbum',support.core.LikeStatus.INDIFFERENT)
        self.assertEqual(self.b.libraryItemsModel.snapshot(),[])
        self.assertIs(self.b._queue,queue);self.assertEqual(self.b.playerPosition,37)
        self.assertEqual(self.played,played);self.assertEqual(self.stops,stops)
        self.assertEqual(self.b.playerLikeStatus,'LIKE')
        self.api.rate_song.assert_not_called();self.api.edit_song_library_status.assert_not_called()
        self.b.clearDetail();self.assertTrue(self.b.restorePlayingSource(1))
        self.assertFalse(self.b.detailMeta['albumLibrary']['inLibrary'])
        self.assertEqual(self.b.libraryItemsModel.snapshot(),[])

    def test_missing_or_changed_identity_prevents_write_and_invalidates_action(self):
        self.api.missing=True;self.open();self.assertFalse(self.b.detailCanAlbumLibrary)
        self.assertFalse(self.b.changeAlbumLibrary())
        self.api.missing=False;self.open();self.api.target='other';self.change()
        self.api.rate_playlist.assert_not_called();self.assertFalse(self.b.detailCanAlbumLibrary)
        self.assertTrue(self.errors)

    def test_external_membership_change_is_idempotent_not_toggled_back(self):
        self.open();self.api.member=True;self.change()
        self.api.rate_playlist.assert_not_called();self.assertTrue(self.b.detailMeta['albumLibrary']['inLibrary'])

    def test_write_failure_or_unverified_readback_does_not_claim_success_or_repeat(self):
        for failed in (True,False):
            with self.subTest(failed=failed):
                self.open();self.api.ignore_write=not failed
                self.api.rate_playlist.side_effect=RuntimeError('offline') if failed else self.api.write
                before=self.api.rate_playlist.call_count
                self.change();self.assertFalse(self.b.detailCanAlbumLibrary)
                self.assertFalse(self.b.changeAlbumLibrary())
                self.assertEqual(self.api.rate_playlist.call_count,before+1)
                self.assertEqual(self.b.libraryItemsModel.count,0);self.assertTrue(self.errors)

    def test_pending_write_targets_original_album_and_guards_repeat_offline_and_upload(self):
        self.open();entered=Event()
        def write(*args):entered.set();self.release.wait(3);return self.api.write(*args)
        self.api.rate_playlist.side_effect=write
        self.assertTrue(self.b.changeAlbumLibrary());self.until(entered.is_set)
        self.assertFalse(self.b.changeAlbumLibrary())
        self.b._detail_meta=dict(kind='album',browseId='MPREother')
        self.release.set();self.until(lambda:not self.b.busy)
        self.assertEqual(self.b.detailMeta,dict(kind='album',browseId='MPREother'))
        self.api.rate_playlist.assert_called_once_with('OLAKalbum',support.core.LikeStatus.LIKE)
        self.open();self.b._set_connected(False);self.assertFalse(self.b.changeAlbumLibrary())
        self.b._set_connected(True);self.b._detail_meta['kind']='upload_album'
        self.assertFalse(self.b.changeAlbumLibrary())

    def test_snapshot_of_empty_album_overview_gains_new_member_and_keeps_its_sort_order(self):
        self.b._library_items_model.clear();self.open()
        self.b.playFrom('detail',0);self.until(lambda:self.b.playerState=='playing')
        self.b.setPlaybackSourceContext(dict(page=1,librarySection='albums',libraryOrder='a_to_z'))
        self.change();self.b.clearDetail();self.b.restorePlayingSource(1)
        self.assertTrue(self.b.detailMeta['albumLibrary']['inLibrary'])
        self.assertEqual(self.b.libraryItemsModel.snapshot()[0]['browseId'],'MPREalbum')

    def test_overview_remains_authoritative_when_album_stays_due_to_individual_songs(self):
        self.api.member=True;self.open()
        self.api.get_library_albums=Mock(return_value=[dict(title='Album',browseId='MPREalbum')])
        self.change()
        self.assertFalse(self.b.detailMeta['albumLibrary']['inLibrary'])
        self.assertEqual(self.b.libraryItemsModel.snapshot()[0]['browseId'],'MPREalbum')

    def test_verified_write_survives_overview_refresh_failure_without_repeating_it(self):
        self.open();self.api.get_library_albums=Mock(side_effect=RuntimeError('offline overview'))
        self.change()
        self.assertTrue(self.b.detailMeta['albumLibrary']['inLibrary'])
        self.assertTrue(self.b.detailCanAlbumLibrary)
        self.assertIn('Přehled Alb',self.b.status)
        self.api.rate_playlist.assert_called_once_with('OLAKalbum',support.core.LikeStatus.LIKE)
