"""Translated status templates keep metadata, queue semantics and API keys intact."""
from pathlib import Path
import shutil
import subprocess
import tempfile
from unittest.mock import Mock
import unittest
from PySide6.QtCore import QLocale
import test_prefetch as support
from felismusic_gui.i18n import install_translation


class StatusMessageTranslationTests(support.AudioPlaybackTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        compiler = next((shutil.which(name) for name in ('pyside6-lrelease', 'lrelease6', 'lrelease')
                         if shutil.which(name)), None)
        if compiler is None:
            raise unittest.SkipTest('Qt Linguist required for catalog integration')
        cls.catalog_dir = tempfile.TemporaryDirectory()
        source = Path(cls.catalog_dir.name) / 'felismusic_en.ts'
        source.write_text('''<?xml version="1.0" encoding="utf-8"?>
<TS version="2.1" language="en" sourcelanguage="cs_CZ"><context><name>BackendBridge</name>
<message><source>Přehrávám · {title}</source><translation>Now playing: {title}</translation></message>
<message><source>Připravuji audio · {title}…</source><translation>Loading {title}…</translation></message>
<message><source>Výsledků hledání · {count}</source><translation>{count} search results</translation></message>
<message numerus="yes"><source>%n skladba</source><translation><numerusform>%n track</numerusform><numerusform>%n tracks</numerusform></translation></message>
<message><source>Přidáno jako další · {count}</source><translation>Queued next: {count}</translation></message>
<message><source>Přidáno do fronty · {count}</source><translation>Appended {count}</translation></message>
<message><source>Přehrávání zastaveno</source><translation>Playback stopped</translation></message>
<message><source>Playlisty · {count}</source><translation>{count} playlists</translation></message>
<message><source>{label} · {count}</source><translation>{count} items in {label}</translation></message>
<message><source>Knihovna</source><translation>Library</translation></message>
<message><source>Skladby</source><translation>Songs</translation></message>
<message><source>Fronta zamíchána · aktuální skladba pokračuje</source><translation>Queue shuffled; current track continues</translation></message>
<message><source>Vyber prohlížeč pro samostatné přihlašovací okno.</source><translation>Choose a browser for sign-in.</translation></message>
<message><source>Vyhledávání se nepodařilo dokončit. Zkus to prosím znovu.</source><translation>Search failed. Please try again.</translation></message>
</context></TS>''')
        subprocess.run([compiler, str(source), '-qm', str(source.with_suffix('.qm'))],
                       check=True, stdout=subprocess.DEVNULL)

    @classmethod
    def tearDownClass(cls):
        cls.catalog_dir.cleanup()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.translator = install_translation(self.app, locale=QLocale('en_GB'), directory=self.catalog_dir.name)
        self.assertIsNotNone(self.translator)
        self.addCleanup(self.app.removeTranslator, self.translator)

    def test_loading_playing_and_stop_translate_without_interpreting_song_title(self):
        title = 'Knihovna {count} %1 Chyba'
        observed = []
        self.b.statusChanged.connect(lambda: observed.append(self.b.status))
        self.start(title, 'Next')
        self.assertIn('Loading ' + title + '…', observed)
        self.assertEqual(self.b.status, 'Now playing: ' + title)
        self.assertEqual(self.b.playerTitle, title)
        self.assertEqual(self.b.playerState, 'playing')
        self.assertFalse(self.b.statusIsError)
        queue = self.b._queue
        self.b.stopPlayback()
        self.assertEqual(self.b.status, 'Playback stopped')
        self.assertEqual(self.b.playerState, 'idle'); self.assertIs(self.b._queue, queue)

    def test_search_count_template_for_all_scopes_keeps_query_and_scope_keys(self):
        api = Mock(); self.b._ytmusic = api
        for scope in ('catalog', 'library', 'uploads'):
            with self.subTest(scope=scope):
                api.search.reset_mock(); api.search.return_value = []
                self.b.search('Knihovna {count}', 'songs', scope)
                self.until(lambda: not self.b.busy)
                self.assertEqual(self.b.status, '0 search results')
                self.assertEqual(api.search.call_args.args, ('Knihovna {count}',))
                self.assertEqual(api.search.call_args.kwargs.get('scope'), None if scope == 'catalog' else scope)
                self.assertFalse(self.errors)
                api.search.return_value = [dict(resultType='song', videoId='raw-id', title='Knihovna')]
                self.b.search('Knihovna {count}', 'songs', scope)
                self.until(lambda: not self.b.busy)
                self.assertEqual(self.b.status, '1 search results')
                self.assertEqual(self.b.searchResultsModel.snapshot()[0]['title'], 'Knihovna')

    def test_enqueue_templates_keep_exact_occurrences_audio_and_positions(self):
        self.start('A', 'B'); self.b._player_position = 42
        queue = self.b._queue; played = list(self.played)
        self.b._library_items_model.set_items([dict(kind='song', videoId='C', title='Knihovna {count}')])
        self.assertTrue(self.b.enqueueFrom('library', 0, True, {}))
        self.assertEqual(self.b.status, 'Queued next: 1 track')
        self.assertEqual([x['videoId'] for x in queue.tracks], ['A', 'C', 'B'])
        self.assertTrue(self.b.enqueueFrom('library', 0, False, {}))
        self.assertEqual(self.b.status, 'Appended 1 track')
        self.assertEqual([x['videoId'] for x in queue.tracks], ['A', 'C', 'B', 'C'])
        self.assertEqual(self.b.playerPosition, 42); self.assertEqual(self.played, played)
        self.assertIs(self.b._queue, queue)

    def test_library_label_is_translated_but_user_item_title_is_not(self):
        self.b._apply_result('library:songs', [dict(kind='song', videoId='id', title='Knihovna')])
        self.assertEqual(self.b.status, '1 items in Songs')
        self.assertEqual(self.b.libraryItemsModel.snapshot()[0]['title'], 'Knihovna')
        self.assertFalse(self.errors)

    def test_login_prompt_translates_without_changing_browser_id_or_name(self):
        browser = dict(id='browser-id', name='Knihovna %1')
        self.b._apply_login_result(self.b._login_generation, 'browsers', [browser])
        self.assertEqual(self.b.loginState['phase'], 'choose')
        self.assertEqual(self.b.loginState['message'], 'Choose a browser for sign-in.')
        self.assertEqual(self.b.loginState['browsers'], [browser])

    def test_worker_search_failure_translates_without_exposing_response(self):
        api = Mock()
        self.b._ytmusic = api
        api.search.side_effect = ValueError('private response')
        self.b.search('Knihovna %1', 'songs', 'catalog')
        self.until(lambda: not self.b.busy)
        self.assertEqual(self.errors, ['Search failed. Please try again.'])
        self.assertTrue(self.b.statusIsError)
        self.assertEqual(api.search.call_args.args, ('Knihovna %1',))
