"""Offline backend and wire-level MPRIS tests; run under dbus-run-session."""
import os
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_prefetch as support
import dbus
from felismusic_gui import mpris


class MprisTests(support.AudioPlaybackTestCase):
    def setUp(self):
        super().setUp()
        if os.environ.get('FELISMUSIC_TEST_DBUS') == '1':
            self.service = mpris.MprisService(self.b, self.app, Mock())
        else:
            # Transport tests below require a real isolated bus; these tests
            # exercise the real backend with only D-Bus export mocked.
            for name, replacement in [('__init__', lambda *args: None),
                                      ('remove_from_connection', Mock())]:
                p = patch.object(dbus.service.Object, name, replacement)
                p.start()
                self.addCleanup(p.stop)
            for name in ('PropertiesChanged', 'Seeked'):
                p = patch.object(mpris.MprisService, name, Mock())
                p.start()
                self.addCleanup(p.stop)
            with patch.object(dbus.service, 'BusName', return_value=Mock()):
                self.service = mpris.MprisService(self.b, self.app, Mock(), bus=Mock())
        self.addCleanup(self.service.close)
        self.mc.pause = Mock()
        self.mc.play = Mock()
        self.mc.seek = Mock()
        self.b._local_output.set_volume = lambda value: value
        self.b._local_output.set_volume_muted = lambda value: value

    def tearDown(self):
        self.doCleanups()
        super().tearDown()

    def load(self):
        self.b._library_items_model.set_items([
            dict(title='First', videoId='A', artists='Artist', album='Album', duration_seconds=180),
            dict(title='Duplicate', videoId='A', artists='Artist')])
        self.b.playFrom('library', 0)
        self.until(lambda: self.b.playerState == 'playing')

    def wire(self, code):
        p = subprocess.Popen([sys.executable, '-c',
            'import dbus; b=dbus.SessionBus(); o=b.get_object("' + mpris.NAME + '", "' + mpris.PATH + '"); ' + code],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.until(lambda: p.poll() is not None)
            out, err = p.communicate(timeout=1)
            self.assertEqual(p.returncode, 0, err)
            return out.strip()
        finally:
            if p.poll() is None:
                p.kill()
                p.communicate()

    @unittest.skipUnless(os.environ.get('FELISMUSIC_TEST_DBUS') == '1', 'requires isolated dbus-run-session')
    def test_wire_types_metadata_introspection_and_controls(self):
        self.load()
        out = self.wire('p=dbus.Interface(o,"' + mpris.PROPS + '"); '
                        'v=p.GetAll("' + mpris.PLAYER + '"); '
                        'assert isinstance(v["Position"],dbus.Int64); '
                        'assert isinstance(v["Metadata"]["mpris:trackid"],dbus.ObjectPath); '
                        'assert v["PlaybackStatus"]=="Playing"; '
                        'print(v["Metadata"]["xesam:title"]); '
                        'dbus.Interface(o,"' + mpris.PLAYER + '").Pause()')
        self.assertEqual(out, 'First')
        self.assertEqual(self.b.playerState, 'paused')
        self.mc.pause.assert_called_once()
        xml = self.wire('print(dbus.Interface(o,"org.freedesktop.DBus.Introspectable").Introspect())')
        self.assertIn('SetPosition', xml)
        self.assertIn('type="x"', xml)

    def test_play_pause_are_idempotent_and_stop_preserves_queue(self):
        self.load()
        queue = self.b._queue
        self.service.Play()
        self.mc.pause.assert_not_called()
        self.service.Pause()
        self.service.Pause()
        self.mc.pause.assert_called_once()
        self.service.Play()
        self.service.Play()
        self.mc.play.assert_called_once()
        self.service.Stop()
        self.assertIs(self.b._queue, queue)
        self.assertEqual(self.service.Get(mpris.PLAYER, 'PlaybackStatus'), 'Stopped')
        self.assertEqual(self.b.playerPosition, 0)

    def test_occurrences_have_distinct_ids_and_stale_seek_is_ignored(self):
        self.load()
        old = self.service._track_id()
        self.service.Next()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertNotEqual(old, self.service._track_id())
        self.service.SetPosition(old, 10_000_000)
        self.mc.seek.assert_not_called()
        self.service.Previous()
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerTitle, 'First')

    def test_seek_bounds_units_and_signal(self):
        self.load()
        self.b._player_duration = 180
        with patch.object(self.service, 'Seeked') as signal:
            self.service.SetPosition(self.service._track_id(), 20_000_000)
            self.assertEqual(self.b.playerPosition, 20)
            signal.assert_called_with(20_000_000)
        self.mc.seek.reset_mock()
        self.service.SetPosition(self.service._track_id(), -1)
        self.service.SetPosition(self.service._track_id(), 181_000_000)
        self.mc.seek.assert_not_called()
        self.service.Seek(200_000_000)
        self.until(lambda: self.b.playerState == 'playing')
        self.assertEqual(self.b.playerTitle, 'Duplicate')

    def test_volume_repeat_and_property_errors(self):
        self.service.Set(mpris.PLAYER, 'Volume', dbus.Double(.42))
        self.assertEqual(self.b.playerVolume, 42)
        self.service.Set(mpris.PLAYER, 'Volume', dbus.Double(-1))
        self.assertEqual(self.b.playerVolume, 0)
        self.b._player_muted = True
        self.service.Set(mpris.PLAYER, 'Volume', dbus.Double(.5))
        self.assertFalse(self.b.playerMuted)
        for value, mode in [('Track', 'one'), ('Playlist', 'all'), ('None', 'off')]:
            self.service.Set(mpris.PLAYER, 'LoopStatus', dbus.String(value))
            self.assertEqual(self.b.playerRepeatMode, mode)
        with self.assertRaises(dbus.DBusException):
            self.service.Set(mpris.PLAYER, 'Position', dbus.Int64(5))
        with self.assertRaises(dbus.DBusException):
            self.service.Get(mpris.PLAYER, 'Unknown')

    def test_signals_exclude_position_and_follow_gui(self):
        self.load()
        with patch.object(self.service, 'PropertiesChanged') as signal:
            self.b._player_position = 1
            self.b.playerChanged.emit()
            signal.assert_not_called()
            self.b._set_player_state('paused')
            self.assertEqual(signal.call_args.args[1]['PlaybackStatus'], 'Paused')
            self.assertNotIn('Position', signal.call_args.args[1])

    def test_cast_transport_uses_selected_output(self):
        self.load()
        cast_mc = SimpleNamespace(play=Mock(), pause=Mock(), stop=Mock())
        cast = SimpleNamespace(media_controller=cast_mc, set_volume=Mock(return_value=.25))
        with patch.object(self.b, '_active_output', return_value=cast), patch.object(self.b, '_check_output_connection', return_value=True):
            self.service.Pause()
            self.service.Play()
            self.service.Set(mpris.PLAYER, 'Volume', dbus.Double(.25))
            self.service.Stop()
        cast_mc.pause.assert_called_once()
        cast_mc.play.assert_called_once()
        cast_mc.stop.assert_called_once_with(keep_output=True)
        cast.set_volume.assert_called_once_with(.25)

    @unittest.skipUnless(os.environ.get('FELISMUSIC_TEST_DBUS') == '1', 'requires isolated dbus-run-session')
    def test_name_collision_and_release(self):
        self.assertIsNone(mpris.start_mpris(self.b, self.app, Mock()))
        self.service.close()
        self._cleanups.clear()
        self.service = mpris.MprisService(self.b, self.app, Mock())
        self.addCleanup(self.service.close)
