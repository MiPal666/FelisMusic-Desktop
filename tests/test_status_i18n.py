"""Status presentation follows an explicit flag, independent of translated text."""
from threading import Event
from unittest.mock import Mock
from PySide6.QtCore import QTranslator
import test_prefetch as support


class EnglishErrorCatalog(QTranslator):
    def isEmpty(self):
        return False

    def translate(self, context, source, disambiguation=None, n=-1):
        if context == 'BackendBridge' and source == 'Chyba při načítání':
            return 'Loading failed'
        return ''


class StatusTranslationTests(support.AudioPlaybackTestCase):
    def test_translated_failure_retains_error_flag_without_czech_keyword(self):
        translator = EnglishErrorCatalog()
        self.assertTrue(self.app.installTranslator(translator))
        self.addCleanup(self.app.removeTranslator, translator)
        self.b._apply_error('search', 'Search failed')
        self.assertEqual(self.b.status, 'Loading failed')
        self.assertTrue(self.b.statusIsError)
        self.assertFalse(self.b.busy)
        self.assertEqual(self.errors, ['Search failed'])

    def test_song_title_containing_chyba_does_not_mark_success_as_error(self):
        self.start('Chyba')
        self.assertIn('Chyba', self.b.status)
        self.assertFalse(self.b.statusIsError)
        self.assertEqual(self.b.playerState, 'playing')

    def test_new_search_clears_error_presentation_while_request_is_pending(self):
        self.b._ytmusic = Mock()
        self.b._ytmusic.search.side_effect = RuntimeError('failed')
        self.b.search('query', 'songs', 'catalog')
        self.until(lambda: not self.b.busy)
        self.assertTrue(self.b.statusIsError)
        entered = Event()
        def waiting(*args, **kwargs):
            entered.set(); self.release.wait(3)
            return []
        self.b._ytmusic.search.side_effect = waiting
        self.b.search('query', 'songs', 'catalog'); self.until(entered.is_set)
        self.assertFalse(self.b.statusIsError)
        self.release.set(); self.until(lambda: not self.b.busy)
        self.assertFalse(self.b.statusIsError)
        self.assertEqual(self.b.searchResultsModel.count, 0)

    def test_same_text_with_new_severity_notifies_qml_binding(self):
        notifications = []
        self.b.statusChanged.connect(lambda: notifications.append(self.b.statusIsError))
        self.b._set_status('Message', error=True)
        self.b._set_status('Message', error=False)
        self.assertEqual(notifications, [True, False])
        self.assertFalse(self.b.statusIsError)
