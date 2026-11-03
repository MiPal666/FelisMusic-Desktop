"""Search failures are concise, typed, and recover without restarting playback."""
import socket
from threading import Event
from unittest.mock import Mock
from requests.exceptions import ConnectionError, HTTPError, ReadTimeout
from PySide6.QtCore import QTimer
import test_prefetch as support


class SearchErrorTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        self.api = Mock()
        self.b._ytmusic = self.api
        self.rows = [dict(resultType='song', videoId='result', title='Result')]
        self.api.search.return_value = self.rows

    def search(self, scope='catalog'):
        self.b.search('query', 'songs', scope)
        self.until(lambda: not self.b.busy)

    def test_dns_connection_and_timeout_errors_are_concise_for_every_scope(self):
        for scope, error in (('catalog', ReadTimeout('PRIVATE_URL read timeout=30')),
                             ('library', ConnectionError('PRIVATE_HEADERS')),
                             ('uploads', socket.gaierror(-3, 'PRIVATE_DNS'))):
            with self.subTest(scope=scope):
                self.api.search.side_effect = error
                self.search(scope)
                self.assertIn('spojení', self.errors[-1])
                self.assertIn('Zkontroluj připojení', self.errors[-1])
                self.assertIn('zkus hledání znovu', self.errors[-1])
                self.assertNotIn('PRIVATE', self.errors[-1])
                self.assertNotIn(type(error).__name__, self.errors[-1])

    def test_failed_search_preserves_results_audio_queue_and_retries_same_session(self):
        self.start('A', 'B'); self.b._player_position = 42
        queue = self.b._queue; current = queue.current(); played = list(self.played); stops = list(self.stops)
        self.search(); before = self.b.searchResultsModel.snapshot()
        self.api.search.side_effect = ReadTimeout('PRIVATE_URL')
        self.search()
        self.assertEqual(self.b.searchResultsModel.snapshot(), before)
        self.assertIs(self.b._queue, queue); self.assertIs(queue.current(), current)
        self.assertEqual(self.played, played); self.assertEqual(self.stops, stops)
        self.assertEqual(self.b.playerPosition, 42)
        self.assertIs(self.b._ytmusic, self.api)
        self.api.search.side_effect = None
        self.api.search.return_value = [dict(resultType='song', videoId='new', title='New')]
        self.search()
        self.assertEqual(self.b.searchResultsModel.snapshot()[0]['videoId'], 'new')
        self.assertIs(self.b._queue, queue)

    def test_parser_http_and_text_only_offline_errors_are_not_reported_as_network(self):
        for error in (KeyError('PRIVATE_RESPONSE'), HTTPError('503 PRIVATE_URL'),
                      RuntimeError('offline PRIVATE_HEADERS')):
            with self.subTest(error=type(error).__name__):
                self.api.search.side_effect = error
                self.search()
                self.assertEqual(self.errors[-1], 'Vyhledávání se nepodařilo dokončit. Zkus to prosím znovu.')

    def test_waiting_search_keeps_gui_alive_and_stop_available(self):
        self.start('A', 'B')
        entered = Event()
        def blocked(*args, **kwargs):
            entered.set(); self.release.wait(3)
            raise ReadTimeout('PRIVATE_URL')
        self.api.search.side_effect = blocked
        self.b.search('query', 'songs', 'catalog'); self.until(entered.is_set)
        tick = Event(); QTimer.singleShot(0, tick.set); self.app.processEvents()
        self.assertTrue(tick.is_set()); self.assertTrue(self.b.busy)
        self.b.stopPlayback(); self.assertEqual(self.b.playerState, 'idle')
        self.release.set(); self.until(lambda: not self.b.busy)
        self.assertIn('Zkontroluj připojení', self.errors[-1])
        self.assertEqual(self.b.playerState, 'idle')

    def test_detail_network_error_uses_shared_connection_message_and_can_retry(self):
        self.api.get_artist.side_effect = ConnectionError('PRIVATE_URL')
        self.b.openLibraryItem('artist', 'UCtest', '', 'Test')
        self.until(lambda: not self.b.busy)
        self.assertEqual(self.errors[-1], 'Nepodařilo se spojit s YouTube Music. Zkontroluj připojení.')
        self.assertIsNone(self.b._pending_detail_parent)
        self.api.get_artist.side_effect = None
        self.api.get_artist.return_value = dict(name='Test', songs={}, albums={}, singles={})
        self.b.openLibraryItem('artist', 'UCtest', '', 'Test'); self.until(lambda: not self.b.busy)
        self.assertEqual(self.b.detailTitle, 'Test')
