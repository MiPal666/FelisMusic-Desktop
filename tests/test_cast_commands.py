"""A stalled Cast command must not hold the Qt event loop or revive stale state."""
from threading import Event, get_ident
from types import SimpleNamespace
from PySide6.QtCore import QTimer
from test_cast_output import CastOutputFixture


class CastCommandTests(CastOutputFixture):
    def block_command(self, method, fail=False):
        entered = Event()
        gui_thread = get_ident()
        original = method.side_effect
        def blocked(*args, **kwargs):
            self.assertNotEqual(get_ident(), gui_thread)
            entered.set()
            self.release.wait(3)
            if fail:
                raise RuntimeError('PRIVATE_URL')
            if callable(original):
                return original(*args, **kwargs)
        method.side_effect = blocked
        return entered

    def test_every_transport_command_returns_while_sdk_waits_and_qt_keeps_running(self):
        for name in ('pause', 'play', 'stop', 'seek', 'volume', 'mute', 'next', 'previous'):
            with self.subTest(command=name):
                self.start('A', 'B', 'C')
                if self.b._cast_output is None:
                    self.switch()
                self.b._queue.index = 1
                self.b._set_player_from_queue()
                self.b._player_state = 'paused' if name == 'play' else 'playing'
                self.release.clear()
                method = {'pause': self.remote.pause, 'play': self.remote.play,
                          'stop': self.remote.stop, 'seek': self.remote.seek,
                          'volume': self.cast.set_volume, 'mute': self.cast.set_volume_muted,
                          'next': self.remote.stop, 'previous': self.remote.stop}[name]
                original = method.side_effect
                entered = self.block_command(method)
                action = {'pause': self.b.togglePlayPause, 'play': self.b.togglePlayPause,
                          'stop': self.b.stopPlayback, 'seek': lambda: self.b.seekTo(42),
                          'volume': lambda: self.b.setVolume(20), 'mute': self.b.toggleMute,
                          'next': self.b.nextTrack, 'previous': self.b.previousTrack}[name]
                action()
                self.until(entered.is_set)
                tick = Event()
                QTimer.singleShot(0, tick.set)
                self.app.processEvents()
                self.assertTrue(tick.is_set())
                self.assertFalse(self.release.is_set())
                self.release.set()
                self.until(lambda: not self.b._cast_commands and not self.b._playback_transitioning)
                method.side_effect = original

    def test_loss_processed_while_sdk_waits_and_late_failure_is_ignored(self):
        self.start('A', 'B', 'A'); self.switch()
        self.b._queue.index = 2; self.b._set_player_from_queue()
        queue = self.b._queue; current = queue.current()
        entered = self.block_command(self.remote.pause, fail=True)
        self.b.togglePlayPause(); self.until(entered.is_set)
        output = self.b._cast_output
        output.new_connection_status(SimpleNamespace(status='LOST'))
        self.b._poll_player()
        self.assertTrue(self.b.castState['disconnected'])
        self.assertEqual(self.b.playerState, 'idle')
        self.assertIs(queue.current(), current)
        self.release.set(); self.until(lambda: not self.b._cast_commands)
        self.assertEqual(self.b.playerState, 'idle'); self.assertFalse(self.errors)
        self.assertFalse(self.recoveries)

    def test_ordered_commands_and_stop_cancel_queued_commands(self):
        self.start('A', 'B'); self.switch()
        entered = self.block_command(self.remote.pause)
        self.b.togglePlayPause(); self.until(entered.is_set)
        self.b.setVolume(25)
        self.b.stopPlayback()
        self.assertEqual(self.b.playerState, 'idle')
        self.release.set(); self.until(lambda: not self.b._cast_commands)
        self.cast.set_volume.assert_not_called()
        self.remote.stop.assert_called_once()
        self.assertEqual(self.b.playerState, 'idle')

    def test_late_seek_result_cannot_modify_new_generation(self):
        self.start('A', 'B'); self.switch()
        entered = self.block_command(self.remote.seek)
        self.b.seekTo(90); self.until(entered.is_set)
        self.b.stopPlayback()
        self.release.set(); self.until(lambda: not self.b._cast_commands)
        self.assertEqual(self.b.playerPosition, 0)
        self.assertEqual(self.b.playerState, 'idle')

    def test_command_error_is_concise_and_does_not_skip_queue(self):
        self.start('A', 'B'); self.switch()
        self.remote.pause.side_effect = RuntimeError('PRIVATE_URL')
        self.b.togglePlayPause(); self.until(lambda: bool(self.errors))
        self.assertNotIn('PRIVATE', self.errors[-1])
        self.assertEqual(self.b._queue.index, 0)
        self.remote.play_media.assert_called_once()

    def test_rapid_pause_play_volume_and_mute_keep_submission_order(self):
        self.start('A', 'B'); self.switch()
        order = []
        entered = self.block_command(self.remote.pause)
        self.b.togglePlayPause(); self.until(entered.is_set)
        self.remote.play.side_effect = lambda: order.append('play')
        def volume(level):
            order.append(level)
            return self.volume(level)
        self.cast.set_volume.side_effect = volume
        self.cast.set_volume_muted.side_effect = lambda muted: order.append(muted)
        self.b.togglePlayPause()
        self.b.changeVolume(5); self.b.changeVolume(5)
        self.b.toggleMute(); self.b.toggleMute()
        self.b._poll_player()
        self.assertEqual(self.b.playerState, 'playing')
        self.release.set(); self.until(lambda: not self.b._cast_commands)
        self.assertEqual(order, ['play', .4, .45, False, True])
        self.assertEqual(self.b.playerVolume, 45)
        self.assertTrue(self.b.playerMuted)

    def test_switch_waits_off_gui_and_discards_old_command_error(self):
        self.start('A', 'B'); self.switch()
        entered = self.block_command(self.cast.set_volume, fail=True)
        self.b.setVolume(10); self.until(entered.is_set)
        self.assertTrue(self.b.selectLocalOutput())
        tick = Event(); QTimer.singleShot(0, tick.set)
        self.app.processEvents(); self.assertTrue(tick.is_set())
        self.release.set()
        self.until(lambda: not self.b._output_switching and not self.b._cast_commands)
        self.assertIsNone(self.b._cast_output)
        self.assertFalse(self.errors)
        self.assertEqual(self.b.outputName, 'Toto zařízení')
