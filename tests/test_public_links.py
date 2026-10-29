"""Public links use the selected entity, without account or playback changes."""
from copy import deepcopy
from unittest.mock import Mock, patch
import test_prefetch as support
from felismusic_gui.public_links import public_link, valid_public_link


class PublicLinkTests(support.AudioPlaybackTestCase):
    def test_entity_links_and_library_aliases(self):
        cases = [
            (dict(kind='song',videoId='track_123-45'), 'watch?v=track_123-45'),
            (dict(kind='video',videoId='video_123-45'), 'watch?v=video_123-45'),
            (dict(kind='album',browseId='MPREbalbum',playlistId='OLAK5uyother'), 'browse/MPREbalbum'),
            (dict(kind='single',browseId='MPREbsingle'), 'browse/MPREbsingle'),
            (dict(kind='ep',browseId='MPREbep'), 'browse/MPREbep'),
            (dict(kind='artist',browseId='MPLAUCartist'), 'channel/UCartist'),
            (dict(kind='playlist',playlistId='VLPLlist'), 'playlist?list=PLlist'),
            (dict(kind='playlist',playlistId='OLAK5uyalbum'), 'playlist?list=OLAK5uyalbum'),
        ]
        for item,path in cases:
            with self.subTest(item=item):
                self.b._search_results_model.set_items([item])
                self.assertEqual(self.b.publicLinkFrom('search',0),'https://music.youtube.com/'+path)
                self.b._detail_meta=item
                self.assertEqual(self.b.detailPublicLink,public_link(item))

    def test_uploads_missing_ids_special_lists_and_invalid_urls_have_no_actions(self):
        for item in [
            dict(kind='upload_song',videoId='private'),dict(kind='upload_album',browseId='MPREbprivate'),
            dict(kind='upload_artist',browseId='UCprivate'),dict(kind='song',videoId='private',entityId='private'),
            dict(kind='song',videoId='private',album={'id':'FEmusic_library_privately_owned_release_detailX'}),
            dict(kind='artist',browseId='FEmusic_library_privately_owned_artistX'),
            dict(kind='playlist',playlistId='LM'),dict(kind='playlist',playlistId='VLSE'),
            dict(kind='playlist',playlistId='RDMix',dynamicMix=True),
            dict(kind='dynamic_mix',playlistId='PLlist'),dict(kind='profile',browseId='UCprofile'),
            dict(kind='podcast',playlistId='PLpodcast'),dict(kind='song'),
            dict(kind='song',videoId='X&list=private'),dict(kind='album',browseId='MPREb../private'),
        ]:
            with self.subTest(item=item):
                self.b._library_items_model.set_items([item])
                self.assertEqual(self.b.publicLinkFrom('library',0),'')
        for source,index in [('unknown',0),('library',-1),('library',99)]:
            self.assertEqual(self.b.publicLinkFrom(source,index),'')
        with patch.object(support.backend.QDesktopServices,'openUrl') as open_url, \
             patch.object(support.backend.QGuiApplication,'clipboard') as clipboard:
            for url in ['https://evil.example/watch?v=X','javascript:alert(1)',
                        'https://music.youtube.com.evil.example/watch?v=X',
                        'https://music.youtube.com/watch?v=X#private','https://music.youtube.com/playlist?list=LM','']:
                self.assertFalse(valid_public_link(url));self.assertFalse(self.b.copyPublicLink(url))
                self.assertFalse(self.b.openPublicLink(url))
            open_url.assert_not_called();clipboard.assert_not_called()

    def test_copy_and_open_snapshot_offline_preserves_selected_occurrence_audio_and_account(self):
        self.start('A','B','A');self.b._player_position=42
        self.b._ytmusic=Mock();self.b._set_connected(False)
        queue=self.b._queue;current=queue.current();rows=deepcopy(self.b._playing_tracks_model.snapshot())
        played,stops=list(self.played),list(self.stops)
        for source in ('library','liked','history','search','detail','playing'):
            self.b._source_model(source).set_items(rows)
            self.assertEqual(self.b.publicLinkFrom(source,1),'https://music.youtube.com/watch?v=B')
        url=self.b.publicLinkFrom('playing',1)
        # The popup captured B before the model changed underneath it.
        self.b._playing_tracks_model.set_items([rows[1],rows[0],rows[2]])
        self.b.selectTrack('playing',2,False,False)
        clipboard=Mock()
        with patch.object(support.backend.QGuiApplication,'clipboard',return_value=clipboard), \
             patch.object(support.backend.QDesktopServices,'openUrl',return_value=True) as browser:
            self.assertTrue(self.b.copyPublicLink(url));clipboard.setText.assert_called_once_with(url)
            self.assertTrue(self.b.openPublicLink(url));self.assertEqual(browser.call_args.args[0].toString(),url)
        self.assertIs(self.b._queue,queue);self.assertIs(queue.current(),current)
        self.assertEqual(self.b.playerPosition,42);self.assertEqual(self.played,played);self.assertEqual(self.stops,stops)
        self.assertEqual(self.b.selectedTrackIndices,[2]);self.assertFalse(self.b._ytmusic.mock_calls)

    def test_collection_link_survives_history_and_does_not_depend_on_loaded_tracks(self):
        for meta in [dict(kind='album',browseId='MPREbalbum'),dict(kind='playlist',playlistId='PLlist'),
                     dict(kind='artist',browseId='MPLAUCartist')]:
            self.b._detail_meta=meta;self.b._detail_tracks_model.clear()
            url=self.b.detailPublicLink;state=self.b._detail_state()
            self.b._detail_meta=dict(kind='upload_album',browseId='private')
            self.assertEqual(self.b.detailPublicLink,'')
            self.b._restore_detail_state(state)
            self.assertEqual(self.b.detailPublicLink,url)

    def test_browser_failure_missing_clipboard_and_shutdown_do_not_claim_success(self):
        url='https://music.youtube.com/watch?v=X'
        with patch.object(support.backend.QDesktopServices,'openUrl',return_value=False):
            self.assertFalse(self.b.openPublicLink(url));self.assertIn('nepodařilo',self.b.status)
        with patch.object(support.backend.QGuiApplication,'clipboard',return_value=None):
            self.assertFalse(self.b.copyPublicLink(url));self.assertIn('není dostupná',self.b.status)
        self.b._closing.set()
        try:
            with patch.object(support.backend.QDesktopServices,'openUrl') as browser, \
                 patch.object(support.backend.QGuiApplication,'clipboard') as clipboard:
                self.assertFalse(self.b.copyPublicLink(url));self.assertFalse(self.b.openPublicLink(url))
                browser.assert_not_called();clipboard.assert_not_called()
        finally:
            self.b._closing.clear()
