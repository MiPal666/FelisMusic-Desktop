"""MPRIS2 adapter. D-Bus callbacks run on the Qt GUI thread via GLib polling."""
import logging
import math
import time

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from PySide6.QtCore import QTimer

ROOT = 'org.mpris.MediaPlayer2'
PLAYER = ROOT + '.Player'
PROPS = 'org.freedesktop.DBus.Properties'
PATH = '/org/mpris/MediaPlayer2'
NAME = ROOT + '.felismusic'
NO_TRACK = PATH + '/TrackList/NoTrack'


class MprisService(dbus.service.Object):
    def __init__(self, backend, app, window, bus=None):
        self.backend, self.app, self.window = backend, app, window
        self._revision = 1
        self._bus = bus or dbus.SessionBus(mainloop=DBusGMainLoop(), private=True)
        try:
            self._name = dbus.service.BusName(NAME, self._bus, do_not_queue=True)
        except Exception:
            self._bus.close()
            raise
        super().__init__(self._name, PATH)
        self._last = self._player_properties()
        self._position_sample = (backend.playerPosition, time.monotonic(), self._track_id(), backend.playerState)
        backend.playerChanged.connect(self.refresh)
        backend.playerTrackChanged.connect(self._track_changed)
        backend.playerSeeked.connect(self._seeked)
        self.timer = QTimer(backend)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self._dispatch)
        self.timer.start()

    def _dispatch(self):
        context = GLib.MainContext.default()
        # Bound work so a noisy bus cannot starve Qt.
        for _ in range(16):
            if not context.pending():
                break
            context.iteration(False)

    def close(self):
        if self._name is None:
            return
        self.timer.stop()
        self.backend.playerChanged.disconnect(self.refresh)
        self.backend.playerTrackChanged.disconnect(self._track_changed)
        self.backend.playerSeeked.disconnect(self._seeked)
        self.remove_from_connection()
        # BusName releases its name in __del__, while the bus is still open.
        self._name = None
        self._bus.close()

    def _track_id(self):
        return dbus.ObjectPath(f'/com/feliscatus/FelisMusic/track/{self._revision}'
                               if self.backend.playerHasTrack else NO_TRACK)

    def _metadata(self):
        b = self.backend
        result = {'mpris:trackid': self._track_id()}
        if b.playerHasTrack:
            result.update({'xesam:title': b.playerTitle,
                           'xesam:artist': dbus.Array([b.playerArtist] if b.playerArtist else [], signature='s'),
                           'xesam:album': b.playerAlbum,
                           'mpris:length': dbus.Int64(max(0, int(b.playerDuration * 1_000_000)))})
            if b.playerThumbnail:
                result['mpris:artUrl'] = b.playerThumbnail
        return dbus.Dictionary(result, signature='sv')

    def _player_properties(self):
        b = self.backend
        ready = bool(b.playbackOutputAvailable and b.playerHasTrack and not b._playback_transitioning)
        return {'PlaybackStatus': {'playing': 'Playing', 'paused': 'Paused'}.get(b.playerState, 'Stopped'),
                'LoopStatus': {'off': 'None', 'all': 'Playlist', 'one': 'Track'}[b.playerRepeatMode],
                'Rate': dbus.Double(1), 'MinimumRate': dbus.Double(1), 'MaximumRate': dbus.Double(1),
                'Metadata': self._metadata(),
                'Volume': dbus.Double(0 if b.playerMuted else b.playerVolume / 100),
                'Position': dbus.Int64(max(0, int(b.playerPosition * 1_000_000))),
                'CanGoNext': dbus.Boolean(b.playerCanNext), 'CanGoPrevious': dbus.Boolean(b.playerCanPrevious),
                'CanPlay': dbus.Boolean(ready), 'CanPause': dbus.Boolean(ready),
                'CanSeek': dbus.Boolean(b.playerCanSeek), 'CanControl': dbus.Boolean(True)}

    def _properties(self, interface):
        if interface == PLAYER:
            return self._player_properties()
        if interface == ROOT:
            return {'CanQuit': dbus.Boolean(True), 'CanRaise': dbus.Boolean(True),
                    'HasTrackList': dbus.Boolean(False), 'Identity': 'FelisMusic',
                    'SupportedUriSchemes': dbus.Array([], signature='s'),
                    'SupportedMimeTypes': dbus.Array([], signature='s')}
        raise dbus.exceptions.DBusException('Unknown interface', name='org.freedesktop.DBus.Error.UnknownInterface')

    @dbus.service.method(PROPS, in_signature='ss', out_signature='v')
    def Get(self, interface, name):
        props = self._properties(interface)
        if name not in props:
            raise dbus.exceptions.DBusException('Unknown property', name='org.freedesktop.DBus.Error.UnknownProperty')
        return props[name]

    @dbus.service.method(PROPS, in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        return self._properties(interface)

    @dbus.service.method(PROPS, in_signature='ssv', out_signature='')
    def Set(self, interface, name, value):
        self.Get(interface, name)
        b = self.backend
        if interface == PLAYER and name == 'Volume' and isinstance(value, dbus.Double) and math.isfinite(value):
            b.setVolume(round(max(0, min(1, float(value))) * 100))
            if b.playerMuted and value > 0:
                b.toggleMute()
        elif interface == PLAYER and name == 'LoopStatus' and str(value) in ('None', 'Playlist', 'Track'):
            target = {'None': 'off', 'Playlist': 'all', 'Track': 'one'}[str(value)]
            for _ in range(3):
                if b.playerRepeatMode == target:
                    break
                b.cycleRepeat()
        elif interface == PLAYER and name == 'Rate' and value == 1:
            return
        else:
            raise dbus.exceptions.DBusException('Read-only property or invalid value',
                                                name='org.freedesktop.DBus.Error.InvalidArgs')

    @dbus.service.signal(PROPS, signature='sa{sv}as')
    def PropertiesChanged(self, interface, changed, invalidated):
        pass

    @dbus.service.signal(PLAYER, signature='x')
    def Seeked(self, position):
        pass

    def _seeked(self, seconds):
        self.Seeked(dbus.Int64(seconds * 1_000_000))
        self._position_sample = (seconds, time.monotonic(), self._track_id(), self.backend.playerState)

    def _track_changed(self):
        self._revision += 1
        self.refresh()

    def refresh(self):
        current = self._player_properties()
        changed = {k: v for k, v in current.items() if k != 'Position' and self._last.get(k) != v}
        self._last = current
        if changed:
            self.PropertiesChanged(PLAYER, changed, [])
        # Also report discontinuities caused by Stop, output handoff, or remote seek.
        b = self.backend
        pos, stamp, track, state = self._position_sample
        now = time.monotonic()
        expected = pos + (now - stamp if state == 'playing' else 0)
        if track == self._track_id() and abs(b.playerPosition - expected) > 2:
            self.Seeked(current['Position'])
        self._position_sample = (b.playerPosition, now, self._track_id(), b.playerState)

    @dbus.service.method(ROOT)
    def Raise(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.requestActivate()

    @dbus.service.method(ROOT)
    def Quit(self):
        self.app.quit()

    @dbus.service.method(PLAYER)
    def Play(self):
        if self.backend.playerState != 'playing':
            self.backend.togglePlayPause()

    @dbus.service.method(PLAYER)
    def Pause(self):
        if self.backend.playerState == 'playing':
            self.backend.togglePlayPause()

    @dbus.service.method(PLAYER)
    def PlayPause(self):
        self.backend.togglePlayPause()

    @dbus.service.method(PLAYER)
    def Stop(self):
        self.backend.stopPlayback()

    @dbus.service.method(PLAYER)
    def Next(self):
        if self.backend.playerCanNext:
            self.backend.nextTrack()

    @dbus.service.method(PLAYER)
    def Previous(self):
        if self.backend.playerCanPrevious:
            self.backend.previousTrack()

    @dbus.service.method(PLAYER, in_signature='x')
    def Seek(self, offset):
        b = self.backend
        if b.playerCanSeek:
            if b.playerPosition + offset / 1_000_000 > b.playerDuration:
                self.Next()
            else:
                b.seekRelative(offset / 1_000_000)

    @dbus.service.method(PLAYER, in_signature='ox')
    def SetPosition(self, track, position):
        b = self.backend
        if b.playerCanSeek and track == self._track_id() and track != NO_TRACK and 0 <= position <= b.playerDuration * 1_000_000:
            b.seekTo(position / 1_000_000)

    @dbus.service.method(PLAYER, in_signature='s')
    def OpenUri(self, uri):
        raise dbus.exceptions.DBusException('Opening URIs is not supported', name='org.freedesktop.DBus.Error.NotSupported')


def start_mpris(backend, app, window):
    try:
        return MprisService(backend, app, window)
    except Exception as exc:
        logging.getLogger(__name__).warning('MPRIS unavailable (%s)', type(exc).__name__)
        return None
