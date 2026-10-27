from collections import Counter
import random
from copy import deepcopy
from threading import Event, Lock, Thread
from time import monotonic
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    Property,
    Qt,
    Signal,
    Slot,
    QTimer,
)
from ytmusicapi import YTMusic
from ytmusicapi.parsers.library import get_library_contents
from ytmusicapi.parsers.browsing import parse_content_list, parse_playlist
from ytmusicapi.exceptions import YTMusicServerError

from . import legacy_core as core
from .paging import PlaylistPages, WatchPages
from .diagnostics import DiagnosticExecutor as ThreadPoolExecutor, current_trace, instrument_ytmusic


class DictListModel(QAbstractListModel):
    """Small, predictable QML model for normalized FelisMusic dictionaries.

    0.2-dev exposed Python ``QVariantList`` objects directly.  Depending on the
    Qt/PySide combination QML then did not consistently provide ``modelData``
    for dictionaries.  A real QAbstractListModel gives the delegates explicit
    roles and avoids that ambiguity.
    """

    countChanged = Signal()

    ROLE_NAMES = (
        "kind",
        "title",
        "subtitle",
        "artists",
        "album",
        "duration",
        "videoId",
        "playlistId",
        "browseId",
        "thumbnail",
        "likeStatus",
        "setVideoId",
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._roles = {
            int(Qt.ItemDataRole.UserRole) + index + 1: name
            for index, name in enumerate(self.ROLE_NAMES)
        }
        self._role_names = {
            role: QByteArray(name.encode("utf-8"))
            for role, name in self._roles.items()
        }

    def roleNames(self):
        return self._role_names

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._items)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        if row < 0 or row >= len(self._items):
            return None

        name = self._roles.get(int(role))
        if name is None:
            return None

        value = self._items[row].get(name, "")
        return "" if value is None else value

    @Property(int, notify=countChanged)
    def count(self):
        return len(self._items)

    def set_items(self, items):
        old_count = len(self._items)
        self.beginResetModel()
        self._items = list(items or [])
        self.endResetModel()
        if len(self._items) != old_count:
            self.countChanged.emit()

    def clear(self):
        self.set_items([])

    def insert_item(self, row, item):
        self.beginInsertRows(QModelIndex(), row, row)
        self._items.insert(row, dict(item))
        self.endInsertRows()
        self.countChanged.emit()

    def append_items(self, items):
        items = list(items)
        if not items:
            return
        row = len(self._items)
        self.beginInsertRows(QModelIndex(), row, row + len(items) - 1)
        self._items.extend(items)
        self.endInsertRows()
        self.countChanged.emit()

    def remove_item(self, row):
        self.beginRemoveRows(QModelIndex(), row, row)
        self._items.pop(row)
        self.endRemoveRows()
        self.countChanged.emit()

    def move_item(self, source, target):
        if source == target:
            return
        self.beginMoveRows(QModelIndex(), source, source, QModelIndex(), target + (target > source))
        self._items.insert(target, self._items.pop(source))
        self.endMoveRows()

    def snapshot(self):
        return [dict(item) for item in self._items]

    def update_role_by_video_id(self, video_id, role_name, value):
        if role_name not in self.ROLE_NAMES:
            return
        video_id = str(video_id or "")
        if not video_id:
            return

        role = next(
            (key for key, name in self._roles.items() if name == role_name),
            None,
        )
        if role is None:
            return

        for row, item in enumerate(self._items):
            if str(item.get("videoId") or "") != video_id:
                continue
            item[role_name] = value
            index = self.index(row, 0)
            self.dataChanged.emit(index, index, [role])


class BackendBridge(QObject):
    """Desktop adapter above the proven FelisMusic core.

    Data loading stays asynchronous and 0.3-dev adds the first real desktop
    playback path: a persistent local GStreamer output controlled from QML.
    """

    statusChanged = Signal()
    accountNameChanged = Signal()
    busyChanged = Signal()
    connectedChanged = Signal()
    detailTitleChanged = Signal()
    errorOccurred = Signal(str)
    initialized = Signal()
    playerChanged = Signal()
    playerTrackChanged = Signal()
    playbackSourceCaptured = Signal()
    radioStarted = Signal()
    queueShuffled = Signal()
    artistPlaybackStarted = Signal()
    collectionShuffleStarted = Signal()
    songLibraryMenuChanged = Signal()
    songLibraryChanged = Signal()
    playlistSaveChanged = Signal()
    playlistSaveRequested = Signal()
    emptyPlaylistChanged = Signal()
    emptyPlaylistRequested = Signal()
    playlistEditChanged = Signal()
    playlistEditRequested = Signal()
    playlistsChanged = Signal(str)
    trackSelectionChanged = Signal()
    playlistDeleteChanged = Signal()
    playlistDeleteRequested = Signal()
    playlistDeleted = Signal(str, bool)

    _songLibraryProbeReady = Signal(int, object, str)
    _resultReady = Signal(str, object)
    _errorReady = Signal(str, str)
    _playbackReady = Signal(int)
    _playbackFailed = Signal(int, str)
    _ratingStatusReady = Signal(int, str, str)
    _ratingActionReady = Signal(int, str, str, str, str)
    _radioRefillReady = Signal(object)
    _likedPageReady = Signal(object)
    _watchPageReady = Signal(object)
    likedLoadChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="felismusic-gui",
        )
        self._playback_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="felismusic-playback",
        )
        self._closing = Event()
        self._transport_lock = Lock()
        self._prefetch_future = None
        self._prefetch_revision = 0
        self._radio_refill_pending = False
        self._radio_refill_revision = 0
        self._radio_waiting_for_tracks = None
        self._liked_stream = None
        self._watch_stream = None
        self._ytmusic = None
        self._status = "Připravuji backend…"
        self._account_name = "YouTube Music"
        self._busy = False
        self._connected = False
        self._library_probe_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="felismusic-library-probe")
        self._library_probe_api = None
        self._library_probe_headers = {}
        self._library_probe_future = None
        self._library_probe_generation = 0
        self._song_library_action_pending = False
        self._song_library_menu = {}
        self._song_library_token = ""
        self._empty_playlist_state = {}
        self._playlist_edit_state = {}
        self._playlist_delete_state = {}
        self._playlist_delete_verification = None
        self._deleted_playlists = set()
        self._pending_removed_playlist_items = {}
        self._pending_playlist_moves = {}
        # Confirmed creations may precede their appearance in YTM's library.
        # Keep their cards until a library response contains the actual IDs.
        self._pending_created_playlists = {}
        self._playlist_save_state = {}
        self._playlist_save_items = []
        self._playlist_save_item = {}
        self._song_library_item = {}
        self._selection_revision = 0
        self._playlist_save_selection = None
        self._selection_source = ""
        self._selection_indices = []
        self._selection_anchor = -1
        self._selection_focus = -1
        self._library_section = ""
        self._library_order = ""
        self._detail_title = ""
        self._detail_meta = {}
        self._detail_history = []
        self._pending_detail_parent = None

        self._local_output = core.create_local_output()
        self._queue = None
        # Source model and original row indexes used to build the current
        # playback queue.  The queue itself contains only playable rows, so we
        # keep this mapping to highlight/follow the matching row in QML.
        self._queue_source = ""
        self._queue_source_indices = []
        self._playing_browse_snapshots = {}
        self._playing_detail_title = ""
        self._playing_liked_order = ""
        self._player_state = "idle"
        self._repeat_mode = "off"
        self._player_title = ""
        self._player_subtitle = ""
        self._player_thumbnail = ""
        self._player_position = 0.0
        self._player_duration = 0.0
        self._player_volume = 100
        self._player_muted = False
        self._player_like_status = "UNKNOWN"
        self._player_rating_busy = False
        self._rating_generation = 0
        self._playback_generation = 0
        self._playback_transitioning = False
        self._player_track_marker = None

        # GStreamer playbin keeps volume/mute independently of whether a
        # track is currently loaded. Mirror that state into QML from start.
        if self._local_output is not None:
            try:
                output_status = self._local_output.status
                self._player_volume = int(round(
                    max(0.0, min(1.0, float(output_status.volume_level))) * 100
                ))
                self._player_muted = bool(output_status.volume_muted)
            except Exception:
                pass

        self._mixes_model = DictListModel(self)
        self._liked_model = DictListModel(self)
        self._history_model = DictListModel(self)
        self._playlists_model = DictListModel(self)
        self._library_items_model = DictListModel(self)
        self._search_results_model = DictListModel(self)
        self._detail_tracks_model = DictListModel(self)
        # Keep the playing list independent of subsequent browsing/searches.
        self._playing_tracks_model = DictListModel(self)
        for source in ("library", "liked", "history", "search", "detail", "playing"):
            model = self._source_model(source)
            for signal in (model.modelReset, model.rowsInserted, model.rowsRemoved, model.rowsMoved):
                signal.connect(lambda *args, source=source: self._invalidate_selection(source))


        # Original YT Music order for client-side re-sorting.
        # We keep the untouched baseline so switching back to
        # "Výchozí YTM" never requires another network request.
        self._liked_default_items = []
        self._liked_order = ""
        self._liked_load_revision = 0
        self._liked_load_state = "complete"

        self._watchPageReady.connect(self._apply_watch_page, Qt.ConnectionType.QueuedConnection)
        self._likedPageReady.connect(self._apply_liked_page, Qt.ConnectionType.QueuedConnection)
        self._songLibraryProbeReady.connect(self._apply_song_library_probe, Qt.ConnectionType.QueuedConnection)
        self._radioRefillReady.connect(self._apply_radio_refill, Qt.ConnectionType.QueuedConnection)
        self._resultReady.connect(
            self._apply_result,
            Qt.ConnectionType.QueuedConnection,
        )
        self._errorReady.connect(
            self._apply_error,
            Qt.ConnectionType.QueuedConnection,
        )
        self._playbackReady.connect(
            self._apply_playback_ready,
            Qt.ConnectionType.QueuedConnection,
        )
        self._playbackFailed.connect(
            self._apply_playback_failed,
            Qt.ConnectionType.QueuedConnection,
        )
        self._ratingStatusReady.connect(
            self._apply_rating_status,
            Qt.ConnectionType.QueuedConnection,
        )
        self._ratingActionReady.connect(
            self._apply_rating_action,
            Qt.ConnectionType.QueuedConnection,
        )

        self._player_timer = QTimer(self)
        self._player_timer.setInterval(500)
        self._player_timer.timeout.connect(self._poll_player)
        self._player_timer.start()

    # ------------------------------------------------------------------
    # Qt properties
    # ------------------------------------------------------------------

    @Property(str, notify=statusChanged)
    def status(self):
        return self._status

    @Property(str, notify=accountNameChanged)
    def accountName(self):
        return self._account_name

    @Property(bool, notify=busyChanged)
    def busy(self):
        return self._busy

    @Property(bool, notify=connectedChanged)
    def connected(self):
        return self._connected

    @Property(QObject, constant=True)
    def mixesModel(self):
        return self._mixes_model

    @Property(QObject, constant=True)
    def likedModel(self):
        return self._liked_model

    @Property(QObject, constant=True)
    def historyModel(self):
        return self._history_model

    @Property(QObject, constant=True)
    def playlistsModel(self):
        return self._playlists_model

    @Property(QObject, constant=True)
    def libraryItemsModel(self):
        return self._library_items_model

    @Property(QObject, constant=True)
    def searchResultsModel(self):
        return self._search_results_model

    @Property(QObject, constant=True)
    def detailTracksModel(self):
        return self._detail_tracks_model

    @Property(QObject, constant=True)
    def playingTracksModel(self):
        return self._playing_tracks_model

    @Property(str, notify=playerChanged)
    def playingListTitle(self):
        return self._queue.name if self._queue is not None else ""

    @Property(str, notify=playerChanged)
    def playerState(self):
        return self._player_state

    @Property(str, notify=playerChanged)
    def playerTitle(self):
        return self._player_title

    @Property(str, notify=playerChanged)
    def playerSubtitle(self):
        return self._player_subtitle

    @Property(str, notify=playerChanged)
    def playerArtist(self):
        song = self._queue.current() if self.playerHasTrack else None
        return core.artist_names(song) if song is not None else ""

    @Property(str, notify=playerChanged)
    def playerAlbum(self):
        song = self._queue.current() if self.playerHasTrack else None
        return self._album(song) if song is not None else ""

    @Property(str, notify=playerChanged)
    def playerThumbnail(self):
        return self._player_thumbnail

    @Property(float, notify=playerChanged)
    def playerPosition(self):
        return float(self._player_position)

    @Property(float, notify=playerChanged)
    def playerDuration(self):
        return float(self._player_duration)

    @Property(int, notify=playerChanged)
    def playerVolume(self):
        return int(self._player_volume)

    @Property(bool, notify=playerChanged)
    def playerMuted(self):
        return bool(self._player_muted)

    @Property(str, notify=playerChanged)
    def playerLikeStatus(self):
        return self._player_like_status

    @Property(bool, notify=playerChanged)
    def playerRatingBusy(self):
        return bool(self._player_rating_busy)

    @Property(bool, notify=playerChanged)
    def playerCanRate(self):
        song = self._queue.current() if self._queue is not None else None
        return bool(
            self._connected
            and song is not None
            and song.get("videoId")
            and not self._player_rating_busy
        )

    @Property(bool, notify=playerChanged)
    def playerCanSeek(self):
        return (
            self._local_output is not None
            and self._queue is not None
            and not self._queue.empty()
            and self._player_duration > 0.0
            and not self._playback_transitioning
            and self._player_state in ("playing", "paused")
        )

    @Property(bool, notify=playerChanged)
    def playerHasTrack(self):
        return self._queue is not None and not self._queue.empty()

    @Property(str, notify=playerChanged)
    def playerRepeatMode(self):
        return self._repeat_mode

    @Property(bool, notify=playerChanged)
    def playerWaitingForRadio(self):
        return self._queue is not None and self._radio_waiting_for_tracks is self._queue

    def _active_queue_stream(self):
        for stream in (self._watch_stream, self._liked_stream):
            if stream and stream["queue"] is self._queue:
                return stream
        return None

    @Property(bool, notify=playerChanged)
    def playerQueueLoading(self):
        stream = self._active_queue_stream()
        return bool(stream and stream["state"] == "loading")

    @Property(bool, notify=playerChanged)
    def playerQueueIncomplete(self):
        stream = self._active_queue_stream()
        return bool(stream and stream["state"] == "error")

    @Property(bool, notify=playerChanged)
    def playerWaitingForTracks(self):
        stream = self._active_queue_stream()
        return self.playerWaitingForRadio or bool(
            stream and stream["state"] == "loading" and stream["waiting"])

    @Slot()
    def cycleRepeat(self):
        self._repeat_mode = core.cycle_repeat_mode(self._repeat_mode)
        self._prefetch_revision += 1
        if self._prefetch_future is not None:
            self._prefetch_future.cancel()
        self.playerChanged.emit()
        # Changing repeat never starts/resumes playback. Refresh speculation
        # only for an active session, using the new automatic successor.
        if not self._playback_transitioning and self._player_state in ("playing", "paused"):
            self._prefetch_next_track()

    @Property(str, notify=playerChanged)
    def playerQueueSource(self):
        return self._current_origin().get("source", self._queue_source)

    @Property("QVariantMap", notify=playerChanged)
    def playerSourceContext(self):
        return self._current_origin().get("context", {})

    @Property(str, notify=playerChanged)
    def playerVideoId(self):
        return self._current_video_id()

    @Property(bool, notify=playerChanged)
    def playerCanEditQueue(self):
        return not self._closing.is_set() and not self._playback_transitioning

    @Property(int, notify=playerChanged)
    def playerQueueIndex(self):
        if self._queue is None or self._queue.empty():
            return -1
        return int(self._queue.index)

    @Property(int, notify=playerChanged)
    def playerQueueCount(self):
        if self._queue is None or self._queue.empty():
            return 0
        return int(self._queue.count())

    @Property(int, notify=playerChanged)
    def playerSourceIndex(self):
        if self._queue is None or self._queue.empty():
            return -1
        origin = self._current_origin()
        if origin:
            return int(origin["index"])
        queue_index = int(self._queue.index)
        if 0 <= queue_index < len(self._queue_source_indices):
            return int(self._queue_source_indices[queue_index])
        return -1

    @Property(bool, notify=playerChanged)
    def playerCanPrevious(self):
        return (
            self._queue is not None
            and not self._queue.empty()
            and (self._queue.index > 0 or (self._repeat_mode == "all" and not self.playerQueueLoading))
            and not self._playback_transitioning
        )

    @Property(bool, notify=playerChanged)
    def playerCanNext(self):
        return (
            self._queue is not None
            and not self._queue.empty()
            and (self._queue.index + 1 < self._queue.count() or (self._repeat_mode == "all" and not self.playerQueueLoading))
            and not self._playback_transitioning
        )

    @Property(bool, notify=playerChanged)
    def localPlaybackAvailable(self):
        return self._local_output is not None

    @Property(str, notify=detailTitleChanged)
    def detailTitle(self):
        return self._detail_title

    @Property("QVariantMap", notify=detailTitleChanged)
    def detailMeta(self):
        return self._detail_meta

    def _detail_state(self):
        return deepcopy({"title": self._detail_title,
                         "tracks": self._detail_tracks_model.snapshot(),
                         "meta": self._detail_meta, "history": self._detail_history})

    def _restore_detail_state(self, state):
        self._detail_title = state.get("title", "")
        self._detail_meta = deepcopy(state.get("meta", {}))
        self._detail_history = deepcopy(state.get("history", []))
        self._detail_tracks_model.set_items(state.get("tracks", []))
        self.detailTitleChanged.emit()

    @Slot()
    def backDetail(self):
        if self._busy:
            return
        if self._detail_history:
            self._restore_detail_state(self._detail_history[-1])
        else:
            self.clearDetail()

    @Slot(int)
    def openDetailItem(self, index):
        items = self._detail_tracks_model.snapshot()
        if self._busy or not 0 <= index < len(items):
            return
        item = items[index]
        if item.get("kind") != "album" or not item.get("browseId"):
            return
        self._pending_detail_parent = self._detail_state()
        self.openLibraryItem("album", item["browseId"], "", item["title"])

    @classmethod
    def _artist_sorted_items(cls, meta):
        section = meta["section"]
        items = meta["sections"].get(section, [])
        order = meta.get("orders", {}).get(section, "a_to_z")
        if order not in ("newest", "oldest"):
            return cls._sort_normalized(items, order)
        # Missing dates stay last in both directions; equal years retain YTM order.
        dated, undated = [], []
        for item in items:
            year = str(item.get("year") or "")
            (dated if year.isdigit() else undated).append(item)
        dated.sort(key=lambda item: int(item["year"]), reverse=order == "newest")
        return dated + undated

    def _load_artist_section(self, api, meta, section):
        pointer = meta.get("pointers", {}).get(section, {})
        if pointer.get("browseId"):
            if section == "songs":
                data = api.get_playlist(pointer["browseId"], limit=None)
                items = [self._track(x) for x in core.usable_tracks(data.get("tracks") or [])]
            else:
                data = api.get_artist_albums(pointer["browseId"], pointer["params"], limit=None)
                items = [self._album_item(x) for x in data if x.get("browseId")]
            meta["sections"][section] = items
            meta["pointers"].pop(section, None)
        meta["section"] = section
        return self._artist_sorted_items(meta)

    @Slot(str)
    def selectArtistSection(self, section):
        if self._busy or self._detail_meta.get("kind") != "artist":
            return
        if section not in ("songs", "albums", "singles"):
            return
        meta = deepcopy(self._detail_meta)
        title = self._detail_title
        if section in meta.get("pointers", {}):
            def task():
                items = self._load_artist_section(self._require_ytmusic(), meta, section)
                return {"title": title, "tracks": items, "meta": meta}
            self._submit("detail", "Načítám celý seznam…", task)
        else:
            meta["section"] = section
            self._detail_meta = meta
            self._detail_tracks_model.set_items(self._artist_sorted_items(meta))
            self.detailTitleChanged.emit()

    @Slot(str)
    def setArtistOrder(self, order):
        if self._busy or self._detail_meta.get("kind") != "artist":
            return
        section = self._detail_meta["section"]
        allowed = {"a_to_z", "z_to_a", "default"}
        if section != "songs":
            allowed.update(("newest", "oldest"))
        if order not in allowed:
            return
        self._detail_meta.setdefault("orders", {})[section] = order
        self._detail_tracks_model.set_items(self._artist_sorted_items(self._detail_meta))
        self.detailTitleChanged.emit()

    # ------------------------------------------------------------------
    # Local playback
    # ------------------------------------------------------------------

    @staticmethod
    def _playback_track(item):
        artists = str(item.get("artists") or "")
        album = str(item.get("album") or "")
        thumbnail = str(item.get("thumbnail") or "")
        track = {
            "title": str(item.get("title") or "Bez názvu"),
            "artists": ([{"name": artists}] if artists else []),
            "album": ({"name": album, "id": item.get("albumId") or ""} if album else None),
            "albumId": str(item.get("albumId") or ""),
            "duration": str(item.get("duration") or ""),
            "videoId": str(item.get("videoId") or ""),
            "setVideoId": str(item.get("setVideoId") or ""),
            "playlistId": str(item.get("playlistId") or ""),
            "browseId": str(item.get("browseId") or ""),
            "isAvailable": True,
            "likeStatus": (str(item.get("likeStatus") or "").upper() or None),
            "_guiSubtitle": str(item.get("subtitle") or ""),
            "_guiThumbnail": thumbnail,
            "_guiKind": str(item.get("kind") or "song"),
        }
        return track

    def _sync_queue_model(self):
        """Expose the real playback order, independently of browsing models."""
        if self._liked_stream and self._liked_stream["queue"] is not self._queue:
            self._liked_stream = None
        if self._watch_stream and self._watch_stream["queue"] is not self._queue:
            self._watch_stream = None
        items = []
        for song in self._queue.tracks if self._queue is not None else []:
            item = self._track(song, upload=str(song.get("_guiKind") or "").startswith("upload_"))
            item["kind"] = song.get("_guiKind") or "song"
            item["subtitle"] = song.get("_guiSubtitle") or ""
            item["thumbnail"] = song.get("_guiThumbnail") or ""
            items.append(item)
        self._playing_tracks_model.set_items(items)

    def _source_model(self, source):
        models = {
            "library": self._library_items_model,
            "liked": self._liked_model,
            "history": self._history_model,
            "search": self._search_results_model,
            "detail": self._detail_tracks_model,
            "playing": self._playing_tracks_model,
        }
        return models.get(source)

    def _source_items(self, source):
        model = self._source_model(source)
        return model.snapshot() if model is not None else []

    @Property(str, notify=trackSelectionChanged)
    def selectionSource(self):
        return self._selection_source

    @Property("QVariantList", notify=trackSelectionChanged)
    def selectedTrackIndices(self):
        return list(self._selection_indices)

    @Slot()
    def clearTrackSelection(self):
        if not self._selection_source:
            return
        self._selection_revision += 1
        self._selection_source = ""
        self._selection_indices = []
        self._selection_anchor = self._selection_focus = -1
        self.trackSelectionChanged.emit()

    def _invalidate_selection(self, source):
        if source == self._selection_source:
            self.clearTrackSelection()

    @Slot(str, int, bool, bool)
    def selectTrack(self, source, index, control, shift):
        if source == "liked" and not self.likedComplete and (
                not self.likedLoading or control or shift or self._busy):
            return
        items = self._source_items(source)
        if not 0 <= index < len(items) or not items[index].get("videoId"):
            return
        same = source == self._selection_source
        selected = set(self._selection_indices) if same else set()
        anchor = self._selection_anchor if same else -1
        if shift and anchor >= 0:
            span = {i for i in range(min(anchor, index), max(anchor, index) + 1) if items[i].get("videoId")}
            selected = selected | span if control else span
        elif control:
            selected.symmetric_difference_update({index})
            anchor = index
        else:
            selected = {index}
            anchor = index
        self._selection_revision += 1
        self._selection_source = source
        self._selection_indices = sorted(selected)
        self._selection_anchor = anchor
        self._selection_focus = index
        self.trackSelectionChanged.emit()

    @Slot(str)
    def selectAllTracks(self, source):
        if source == "liked" and not self.likedComplete:
            return
        self._selection_revision += 1
        self._selection_source = source
        self._selection_indices = [i for i, x in enumerate(self._source_items(source)) if x.get("videoId")]
        self._selection_anchor = self._selection_indices[0] if self._selection_indices else -1
        self._selection_focus = self._selection_anchor
        self.trackSelectionChanged.emit()

    @Slot()
    def playSelectedTrack(self):
        if self._selection_focus in self._selection_indices:
            self.playFrom(self._selection_source, self._selection_focus)

    @Slot(result=bool)
    def openSelectedPlaylistSave(self):
        if self._selection_source == "liked" and not self.likedComplete:
            return False
        if self._busy or self._closing.is_set() or self._ytmusic is None:
            return False
        source = self._source_items(self._selection_source)
        items = [dict(source[i]) for i in self._selection_indices if i < len(source)]
        if not items or not all(self._playlist_song_supported(x) for x in items):
            return False
        revision = self._selection_revision
        opened = self._open_playlist_selection(items, f"Vybrané skladby: {len(items)}", len(items) > 1)
        if opened:
            self._playlist_save_selection = revision
        return opened

    @Property(bool, notify=trackSelectionChanged)
    def selectionCanSavePlaylist(self):
        source = self._source_items(self._selection_source)
        return bool(self._selection_indices) and all(
            i < len(source) and self._playlist_song_supported(source[i]) for i in self._selection_indices)

    @Slot(bool, "QVariantMap", result=bool)
    def enqueueSelection(self, play_next, context):
        revision = self._selection_revision
        added = self._enqueue_items(self._selection_source, list(self._selection_indices), play_next, context)
        if added and revision == self._selection_revision:
            self.clearTrackSelection()
        return added

    def _current_origin(self):
        song = self._queue.current() if self.playerHasTrack else None
        return song.get("_guiOrigin", {}) if song is not None else {}

    def _make_origin(self, source, index, items, context=None):
        snapshots = {source: items}
        if source == "detail":
            for parent in ("library", "search"):
                snapshots[parent] = self._source_items(parent)
        return {
            "source": source, "index": index, "snapshots": snapshots,
            "detail_title": self._detail_title if source == "detail" else "",
            "detail_state": self._detail_state() if source == "detail" else {},
            "liked_order": self._liked_order, "context": dict(context or {}),
        }

    @Slot("QVariantMap")
    def setPlaybackSourceContext(self, context):
        if self._queue is not None:
            for song in self._queue.tracks:
                if "_guiOrigin" in song:
                    song["_guiOrigin"]["context"] = dict(context)

    @Slot(int, result=bool)
    def restorePlayingSource(self, page):
        """Restore browsing data without rebuilding or restarting playback."""
        if not self.playerHasTrack or self._busy:
            return False
        origin = self._current_origin()
        source_key = self.playerQueueSource
        if source_key == "playing":
            return True
        if page == 1:
            context = origin.get("context", {})
            self._library_section = context.get("librarySection", "")
            self._library_order = context.get("libraryOrder", "")
        snapshots = origin.get("snapshots", self._playing_browse_snapshots)
        sources = [source_key]
        if source_key == "detail":
            if page == 1:
                sources.append("library")
            elif page == 0:
                sources.append("search")
        for source in sources:
            model = self._source_model(source)
            if model is not None:
                model.set_items(snapshots.get(source, []))
        title = origin.get("detail_title", self._playing_detail_title) if source_key == "detail" else ""
        state = {}
        if source_key == "detail":
            state = origin.get("detail_state") or {"title": title, "tracks": snapshots.get("detail", [])}
        self._restore_detail_state(state)
        if source_key == "liked":
            self._liked_order = origin.get("liked_order", self._playing_liked_order)
        return True

    def _queue_name_for_source(self, source):
        if source == "liked":
            return "Oblíbená hudba"
        if source == "history":
            return "Historie"
        if source == "search":
            return "Hledání"
        if source == "detail":
            return self._detail_title or "Fronta"
        return "Knihovna"

    def _prune_removed_queue_tracks(self, drop_current=False, direction=1, preserve_audio=False):
        """Drop playlist removals without rebuilding queue songs or their order."""
        if self._queue is None or self._queue.empty():
            return False
        queue = self._queue
        current = queue.current()
        old_index = queue.index
        removed = [i for i, song in enumerate(queue.tracks)
                   if song.get("_guiRemoveAfterPlayback") and (drop_current or song is not current)]
        if not removed:
            return False
        removed_set = set(removed)
        kept = [song for i, song in enumerate(queue.tracks) if i not in removed_set]
        indices = [self._queue_source_indices[i] if i < len(self._queue_source_indices) else -1
                   for i in range(queue.count()) if i not in removed_set]
        current_removed = old_index in removed_set
        if current_removed:
            # Forward successor shifts into the removed current row's position.
            insertion = sum(i < old_index for i in range(queue.count()) if i not in removed_set)
            target = insertion if direction > 0 else insertion - 1
            moved = 0 <= target < len(kept)
            if not moved and kept and self._repeat_mode == "all":
                target = 0 if direction > 0 else len(kept) - 1
                moved = True
            queue.index = max(0, min(target, len(kept) - 1))
        else:
            queue.index = next(i for i, song in enumerate(kept) if song is current)
            moved = True
        queue.tracks[:] = kept
        self._queue_source_indices = indices
        self._prefetch_revision += 1
        if self._prefetch_future is not None:
            self._prefetch_future.cancel()
        self._sync_queue_model()
        # A shifted row index does not mean that audio/time/rating changed.
        if preserve_audio and not current_removed:
            self._player_track_marker = (id(queue), queue.index if kept else -1,
                                         self._current_video_id())
        self.playerChanged.emit()
        return moved

    def _sync_removed_playlist_queue_item(self, playlist_id, set_video_id):
        if self._queue is None:
            return
        changed = False
        current = self._queue.current()
        keep_current = self._player_state in ("playing", "paused", "loading")
        for song in self._queue.tracks:
            if song.get("_guiPlaylistBinding") == (playlist_id, set_video_id):
                song["_guiRemoveAfterPlayback"] = True
                changed = True
        if not changed:
            return
        current_removed = bool(current and current.get("_guiRemoveAfterPlayback") and not keep_current)
        self._prune_removed_queue_tracks(drop_current=not keep_current, preserve_audio=True)
        if current_removed:
            self._set_player_from_queue()
        # Deferring just the current row also changes repeat-one's successor.
        self._prefetch_revision += 1
        if self._prefetch_future is not None:
            self._prefetch_future.cancel()
        if not self._playback_transitioning and self._player_state in ("playing", "paused"):
            self._prefetch_next_track()
        self.playerChanged.emit()

    def _leave_removed_current(self, direction, stop_current=False):
        moved = self._prune_removed_queue_tracks(drop_current=True, direction=direction)
        self._set_player_from_queue()
        if moved:
            self._start_current_async(direction=direction, stop_current=stop_current)
        else:
            if stop_current and self._local_output is not None:
                self._local_output.media_controller.stop(keep_output=True)
            self._set_player_state("idle")

    def _set_player_from_queue(self):
        self._prune_removed_queue_tracks()
        song = self._queue.current() if self._queue is not None else None

        # playerChanged se používá i pro čas/hlasitost a běží několikrát za
        # sekundu. Zvláštní marker/signál proto rozlišuje skutečnou změnu
        # skladby. QML pak může autoscrollovat jen při Next/Previous/EOS a
        # během normálního přehrávání nechá uživatele seznam volně rolovat.
        queue_index = (
            int(self._queue.index)
            if self._queue is not None and not self._queue.empty()
            else -1
        )
        marker = (
            id(self._queue) if self._queue is not None else 0,
            queue_index,
            str(song.get("videoId") or "") if song is not None else "",
        )
        track_changed = marker != self._player_track_marker
        self._player_track_marker = marker

        # Každá změna skladby zneplatní případný starší dotaz na hodnocení.
        self._rating_generation += 1
        rating_generation = self._rating_generation
        self._player_rating_busy = False

        if song is None:
            self._player_title = ""
            self._player_subtitle = ""
            self._player_thumbnail = ""
            self._player_position = 0.0
            self._player_duration = 0.0
            self._player_like_status = "UNKNOWN"
        else:
            self._player_title = str(song.get("title") or "Bez názvu")
            self._player_subtitle = str(song.get("_guiSubtitle") or "")
            self._player_thumbnail = str(song.get("_guiThumbnail") or "")
            self._player_position = 0.0
            self._player_duration = float(core.song_duration_seconds(song) or 0.0)

            raw_status = song.get("likeStatus")
            if raw_status in (None, ""):
                self._player_like_status = "UNKNOWN"
            else:
                self._player_like_status = core.normalize_like_status(raw_status)

        self.playerChanged.emit()
        if track_changed:
            self.playerTrackChanged.emit()

        # Playlisty/alba někdy likeStatus neposílají. Stav doplníme na pozadí,
        # aby se kvůli němu nikdy nezdržovalo samotné spuštění skladby.
        if (
            song is not None
            and self._player_like_status == "UNKNOWN"
            and song.get("videoId")
            and self._ytmusic is not None
        ):
            self._resolve_rating_async(str(song.get("videoId")), rating_generation)

    def _current_video_id(self):
        song = self._queue.current() if self._queue is not None else None
        return str(song.get("videoId") or "") if song is not None else ""

    def _propagate_like_status(self, video_id, status):
        """Keep the current queue and already loaded GUI models consistent."""
        video_id = str(video_id or "")
        status = core.normalize_like_status(status)
        if not video_id:
            return

        if self._queue is not None:
            for song in self._queue.tracks:
                if str(song.get("videoId") or "") == video_id:
                    song["likeStatus"] = status

        for model in (
            self._liked_model,
            self._history_model,
            self._library_items_model,
            self._search_results_model,
            self._detail_tracks_model,
            self._playing_tracks_model,
        ):
            model.update_role_by_video_id(video_id, "likeStatus", status)

        for item in self._liked_default_items:
            if str(item.get("videoId") or "") == video_id:
                item["likeStatus"] = status

        snapshots = [self._playing_browse_snapshots]
        if self._queue is not None:
            snapshots.extend(song.get("_guiOrigin", {}).get("snapshots", {}) for song in self._queue.tracks)
        unique_items = {
            id(items): items for snapshot in snapshots for items in snapshot.values()
        }
        for items in unique_items.values():
            for item in items:
                if str(item.get("videoId") or "") == video_id:
                    item["likeStatus"] = status

        # Artist tabs and navigation history contain additional song snapshots.
        seen = set()
        def update_detail(value):
            if not isinstance(value, (dict, list)) or id(value) in seen:
                return
            seen.add(id(value))
            if isinstance(value, dict):
                if str(value.get("videoId") or "") == video_id:
                    value["likeStatus"] = status
                for child in value.values():
                    update_detail(child)
            else:
                for child in value:
                    update_detail(child)
        update_detail(self._detail_meta)
        update_detail(self._detail_history)
        update_detail(self._pending_detail_parent)
        if self._queue is not None:
            for song in self._queue.tracks:
                update_detail(song.get("_guiOrigin", {}).get("detail_state"))

    def _resolve_rating_async(self, video_id, generation):
        ytmusic = self._ytmusic
        if ytmusic is None or not video_id:
            return

        def work():
            probe = {"videoId": video_id}
            try:
                status = core.ensure_song_like_status(ytmusic, probe)
            except Exception:
                status = "INDIFFERENT"
            self._ratingStatusReady.emit(generation, video_id, status)

        # Stejný executor jako ostatní YT Music operace: requests nad jedním
        # YTMusic objektem tak zbytečně neběží paralelně.
        self._executor.submit(work)

    @Slot(int, str, str)
    def _apply_rating_status(self, generation, video_id, status):
        if generation != self._rating_generation:
            return
        if self._current_video_id() != video_id:
            return
        if self._player_rating_busy:
            return

        status = core.normalize_like_status(status)
        self._player_like_status = status
        self._propagate_like_status(video_id, status)
        self.playerChanged.emit()

    @Slot(str)
    def toggleRating(self, wanted):
        wanted = str(wanted or "").upper()
        if wanted not in ("LIKE", "DISLIKE"):
            return
        if not self.playerCanRate or self._ytmusic is None:
            return

        song = self._queue.current()
        video_id = str(song.get("videoId") or "")
        if not video_id:
            return

        old_status = self._player_like_status
        if old_status not in ("LIKE", "DISLIKE", "INDIFFERENT"):
            old_status = core.normalize_like_status(song.get("likeStatus"))

        new_status = "INDIFFERENT" if old_status == wanted else wanted

        # Optimistická změna: tlačítko reaguje okamžitě. Pokud API selže,
        # _apply_rating_action stav vrátí zpět a zobrazí chybu.
        self._rating_generation += 1
        generation = self._rating_generation
        self._player_rating_busy = True
        self._player_like_status = new_status
        self._propagate_like_status(video_id, new_status)
        self.playerChanged.emit()

        rating = {
            "LIKE": core.LikeStatus.LIKE,
            "DISLIKE": core.LikeStatus.DISLIKE,
            "INDIFFERENT": core.LikeStatus.INDIFFERENT,
        }[new_status]
        ytmusic = self._ytmusic

        def work():
            error = ""
            try:
                ytmusic.rate_song(video_id, rating)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            self._ratingActionReady.emit(
                generation, video_id, new_status, old_status, error
            )

        self._executor.submit(work)

    @Slot(int, str, str, str, str)
    def _apply_rating_action(
        self, generation, video_id, new_status, old_status, error
    ):
        current_matches = self._current_video_id() == video_id

        if error:
            self._propagate_like_status(video_id, old_status)
            if current_matches and generation == self._rating_generation:
                self._player_like_status = old_status
                self._player_rating_busy = False
                self.playerChanged.emit()
            self._set_status("Hodnocení se nepodařilo uložit")
            self.errorOccurred.emit(
                "Nepodařilo se změnit hodnocení skladby:\n" + error
            )
            return

        self._propagate_like_status(video_id, new_status)
        if current_matches and generation == self._rating_generation:
            self._player_like_status = new_status
            self._player_rating_busy = False
            self.playerChanged.emit()
            label = {
                "LIKE": "Oblíbená",
                "DISLIKE": "Neoblíbená",
                "INDIFFERENT": "Bez hodnocení",
            }.get(new_status, "Bez hodnocení")
            self._set_status(f"Hodnocení · {label}")

        # Změna likeStatus sama nestačí: nově oblíbená skladba ještě
        # v modelu Oblíbené hudby není a odoblibená z něj musí zmizet.
        if self._liked_default_items:
            self.loadLiked()

    def _set_player_state(self, state):
        state = str(state or "idle")
        if self._player_state == state:
            return
        self._player_state = state
        self.playerChanged.emit()

    def _start_current_async(self, direction=1, stop_current=False):
        self._radio_waiting_for_tracks = None
        stream = self._active_queue_stream()
        if stream:
            stream["waiting"] = False
        if self._closing.is_set() or self._queue is None or self._queue.empty():
            return

        if self._local_output is None:
            self.errorOccurred.emit(
                "Lokální GStreamer není v tomto Python prostředí dostupný.\n\n"
                "GUI virtualenv musí být vytvořen s --system-site-packages, "
                "aby viděl systémový PyGObject/GStreamer."
            )
            return

        mc = self._local_output.media_controller
        with self._transport_lock:
            self._playback_generation += 1
            if stop_current:
                try:
                    mc.stop(keep_output=True)
                except Exception as exc:
                    self._playback_transitioning = False
                    self._set_player_state("idle")
                    self.errorOccurred.emit(f"Zastavení původní skladby selhalo: {exc}")
                    return
        if self._prefetch_future is not None:
            self._prefetch_future.cancel()
        generation = self._playback_generation
        self._playback_transitioning = True
        self._set_player_state("loading")
        self._set_status(f"Připravuji audio · {self._player_title}…")
        self.playerChanged.emit()
        queue = self._queue

        def cancelled():
            return self._closing.is_set() or generation != self._playback_generation

        def work():
            last_error = None
            while generation == self._playback_generation:
                with self._transport_lock:
                    song = queue.current()
                if song is None:
                    break
                try:
                    url, content_type = core.get_local_audio_source(
                        song["videoId"], cancelled=cancelled, diagnostics=current_trace()
                    )
                    artists = core.artist_names(song)
                    trace = current_trace()
                    output_started = monotonic()
                    if trace:
                        trace.event("audio.output_begin")
                    with self._transport_lock:
                        if cancelled():
                            return
                        mc.play_media(
                            url,
                            content_type,
                            title=f"{artists} - {song.get('title', '?')}",
                            stream_type="BUFFERED",
                        )
                    mc.block_until_active(timeout=15, cancelled=cancelled)
                    if trace:
                        trace.event("audio.output_ready", seconds=round(monotonic() - output_started, 3))
                    if not cancelled():
                        self._playbackReady.emit(generation)
                    return
                except Exception as exc:
                    if self._closing.is_set() or generation != self._playback_generation:
                        return
                    last_error = exc
                    with self._transport_lock:
                        moved = queue.next() if direction >= 0 else queue.previous()
                    if not moved:
                        break

            if generation == self._playback_generation:
                text = (
                    f"{type(last_error).__name__}: {last_error}"
                    if last_error is not None
                    else "Ve frontě není přehratelná skladba."
                )
                self._playbackFailed.emit(generation, text)

        self._playback_executor.submit(work, _diagnostic_label="audio.play", _diagnostic_video=self._current_video_id())

    def _next_prefetch_id(self):
        if self._queue is None or self._queue.empty():
            return ""
        removing_current = self._queue.current().get("_guiRemoveAfterPlayback")
        if self._repeat_mode == "one" and not removing_current:
            return ""
        next_index = self._queue.index + 1
        if next_index >= self._queue.count():
            if self._repeat_mode != "all":
                return ""
            next_index = 0
        if removing_current and next_index == self._queue.index:
            return ""
        return str(self._queue.tracks[next_index].get("videoId") or "")

    def _prefetch_next_track(self):
        """Prepare just the next track, using the same serial audio worker.

        Playback and prefetch never write cookies/cache concurrently. If EOS
        arrives while prefetch is running, playback follows it and reuses the
        finished file through get_local_audio_source's normal cache lookup.
        """
        if self._closing.is_set() or self._queue is None or self._queue.empty():
            return
        video_id = self._next_prefetch_id()
        if not video_id:
            return
        generation = self._playback_generation
        revision = self._prefetch_revision

        def cancelled():
            # An automatic transition to this track can still use its download.
            return self._closing.is_set() or self._player_state == "idle" or (
                (generation != self._playback_generation or revision != self._prefetch_revision)
                and self._current_video_id() != video_id
            )

        def work():
            if cancelled():
                return
            try:
                print(f"FelisMusic přednačítání: {video_id}")
                core.get_local_audio_source(video_id, cancelled=cancelled, diagnostics=current_trace())
                if not cancelled():
                    print(f"FelisMusic přednačteno: {video_id}")
            except core.AudioPreparationCancelled:
                pass
            except Exception as exc:
                # Speculative failure must not affect playback or skip a row.
                # Normal playback will try this track again when it is needed.
                if not cancelled():
                    print(f"FelisMusic přednačítání selhalo ({video_id}): {type(exc).__name__}")

        self._prefetch_future = self._playback_executor.submit(work, _diagnostic_label="audio.prefetch", _diagnostic_video=video_id)

    @Slot(int)
    def _apply_playback_ready(self, generation):
        if self._closing.is_set() or generation != self._playback_generation:
            return
        self._playback_transitioning = False
        self._set_player_from_queue()
        self._set_player_state("playing")
        self._set_status(
            f"Přehrávám · {self._player_title}"
        )
        self.playerChanged.emit()
        self._prefetch_next_track()

    @Slot(int, str)
    def _apply_playback_failed(self, generation, message):
        if generation != self._playback_generation:
            return
        self._playback_transitioning = False
        self._set_player_state("idle")
        if self._queue and any(x.get("_guiRemoveAfterPlayback") for x in self._queue.tracks):
            self._prune_removed_queue_tracks(drop_current=True)
            self._set_player_from_queue()
        self.playerChanged.emit()
        self.errorOccurred.emit(
            "Skladbu se nepodařilo přehrát:\n" + message
        )

    @Slot()
    def _poll_player(self):
        if (
            self._local_output is None
            or self._queue is None
            or self._queue.empty()
            or self._playback_transitioning
        ):
            return

        self._maybe_refill_radio()

        try:
            status = self._local_output.media_controller.status
        except Exception:
            return

        changed = False
        try:
            position = max(0.0, float(status.adjusted_current_time or 0.0))
        except Exception:
            position = 0.0
        try:
            duration = max(0.0, float(status.duration or 0.0))
        except Exception:
            duration = 0.0

        if abs(position - self._player_position) >= 0.25:
            self._player_position = position
            changed = True
        if duration > 0 and abs(duration - self._player_duration) >= 0.25:
            self._player_duration = duration
            changed = True

        # Keep volume/mute in sync with the actual local output as well.
        try:
            output_status = self._local_output.status
            volume = int(round(
                max(0.0, min(1.0, float(output_status.volume_level))) * 100
            ))
            muted = bool(output_status.volume_muted)
            if volume != self._player_volume:
                self._player_volume = volume
                changed = True
            if muted != self._player_muted:
                self._player_muted = muted
                changed = True
        except Exception:
            pass

        state = str(getattr(status, "player_state", "IDLE") or "IDLE")
        idle_reason = str(getattr(status, "idle_reason", "") or "")

        if state == "PLAYING" and self._player_state != "playing":
            self._player_state = "playing"
            changed = True
        elif state == "PAUSED" and self._player_state != "paused":
            self._player_state = "paused"
            changed = True
        elif state == "IDLE" and idle_reason == "FINISHED" and self._player_state != "idle":
            if self._queue.current().get("_guiRemoveAfterPlayback"):
                self._leave_removed_current(1)
                return
            advance = self._repeat_mode == "one"
            if not advance:
                advance = self._queue.next()
                if not advance and self._repeat_mode == "all" and not self.playerQueueLoading:
                    self._queue.index = 0
                    advance = True
            if advance:
                self._set_player_from_queue()
                self._start_current_async(direction=1)
                return
            self._player_state = "idle"
            self._player_position = self._player_duration
            if self.playerQueueLoading:
                self._active_queue_stream()["waiting"] = True
                self._set_status("Čekám na další skladby…")
            if self._queue.radio_active:
                self._radio_waiting_for_tracks = self._queue
                self._set_status("Mix · čekám na další doporučení…")
            changed = True

        if changed:
            self.playerChanged.emit()

    @Slot(str, int)
    def playFrom(self, source, index):
        if source == "liked" and not self.likedComplete and (not self.likedLoading or self._busy):
            return
        if source == "playing":
            # Select within the existing queue; do not rebuild it from a
            # browsing model which may already display something else.
            if self._queue is None:
                return
            if not 0 <= index < self._queue.count():
                return
            self._queue.index = index
            self._set_player_from_queue()
            self._start_current_async(direction=1, stop_current=True)
            return

        items = self._source_items((source or "").strip())
        if index < 0 or index >= len(items):
            return
        if not items[index].get("videoId"):
            return

        playable = []
        source_indices = []
        start_index = None
        for original_index, item in enumerate(items):
            if not item.get("videoId"):
                continue
            if original_index == index:
                start_index = len(playable)
            track = self._playback_track(item)
            if source == "detail" and self._detail_meta.get("kind") == "playlist" and item.get("setVideoId"):
                track["_guiPlaylistBinding"] = (self._detail_meta["playlistId"], item["setVideoId"])
            playable.append(track)
            source_indices.append(original_index)

        if start_index is None or not playable:
            return

        self._queue_source = (source or "").strip()
        self._queue_source_indices = source_indices
        self._queue = core.PlaybackQueue(
            playable,
            name=self._queue_name_for_source(source),
            start_index=start_index,
            source_playlist_id=self._detail_shuffle_id() if source == "detail" else None,
        )
        # Repeat belongs to this playback queue, not to future collections.
        self._repeat_mode = "off"
        self._sync_queue_model()
        self._playing_browse_snapshots = {self._queue_source: items}
        if self._queue_source == "detail":
            for parent_source in ("library", "search"):
                self._playing_browse_snapshots[parent_source] = self._source_items(parent_source)
        self._playing_detail_title = self._detail_title
        self._playing_liked_order = self._liked_order
        origin = {
            "source": self._queue_source, "snapshots": self._playing_browse_snapshots,
            "detail_title": self._playing_detail_title,
            "detail_state": self._detail_state() if source == "detail" else {},
            "liked_order": self._playing_liked_order, "context": {},
        }
        for song, original_index in zip(self._queue.tracks, source_indices):
            song["_guiOrigin"] = dict(origin, index=original_index)
        self.playbackSourceCaptured.emit()
        if source == "liked" and self.likedLoading:
            self._liked_stream = {
                "queue": self._queue, "revision": self._liked_load_revision,
                "origin": self._queue.current()["_guiOrigin"],
                "items": list(items), "bound": list(zip(self._queue.tracks, source_indices)),
                "state": "loading", "waiting": False,
            }
        self._set_player_from_queue()
        self._start_current_async(direction=1, stop_current=True)

    @Property("QVariantMap", notify=emptyPlaylistChanged)
    def emptyPlaylistState(self):
        return self._empty_playlist_state

    @Slot(result=bool)
    def beginEmptyPlaylist(self):
        if self._busy or self._closing.is_set() or self._ytmusic is None:
            return False
        self._empty_playlist_state = {"pending": False, "completed": False,
                                      "locked": False, "error": False, "message": ""}
        self.emptyPlaylistChanged.emit()
        self.emptyPlaylistRequested.emit()
        return True

    @Slot(str, result=bool)
    @Slot(str, str, result=bool)
    def createEmptyPlaylist(self, title, privacy="PRIVATE"):
        state = self._empty_playlist_state
        if (self._busy or self._closing.is_set() or self._ytmusic is None or not state
                or state.get("pending") or state.get("completed") or state.get("locked")):
            return False
        if privacy not in ("PRIVATE", "UNLISTED", "PUBLIC"):
            self._empty_playlist_state = dict(state, error=True, message="Vyber platnou viditelnost playlistu.")
            self.emptyPlaylistChanged.emit()
            return False
        title = str(title or "").strip()
        if not title or "<" in title or ">" in title:
            self._empty_playlist_state = dict(state, error=True, message="Vyplň název playlistu bez znaků < a >.")
            self.emptyPlaylistChanged.emit()
            return False
        self._empty_playlist_state = dict(state, pending=True, error=False, message="Vytvářím prázdný playlist…")
        self.emptyPlaylistChanged.emit()
        api = self._ytmusic
        def task():
            try:
                # No video_ids/source_playlist: creation is independent of the
                # selected song, browsing page and playback queue.
                playlist_id = api.create_playlist(title, "", privacy_status=privacy)
                if not isinstance(playlist_id, str) or not playlist_id.strip():
                    raise RuntimeError("Creation not confirmed")
                return {"pending": False, "completed": True, "locked": True,
                        "error": False, "playlistId": playlist_id, "title": title,
                        "message": f"Vytvořen prázdný playlist: {title}"}
            except Exception as exc:
                print(f"FelisMusic vytvoření prázdného playlistu: {type(exc).__name__}")
                return {"pending": False, "completed": False, "locked": True, "error": True,
                        "message": "Vytvoření playlistu se nepodařilo potvrdit. Před dalším pokusem zkontroluj playlisty ve webovém YTM."}
        self._submit("playlist_create_empty", "Vytvářím prázdný playlist…", task)
        return True

    @staticmethod
    def _project_playlist_moves(tracks, moves):
        tracks = list(tracks)
        moves = list(moves)
        raw_order = [x.get("setVideoId") for x in tracks]
        # A read may already include a prefix (or all) of our confirmed writes.
        # Replaying that prefix can change the order again: moves do not commute.
        observed = max((i for i, move in enumerate(moves)
                        if isinstance(move, dict) and move["order"] == raw_order), default=-1)
        for move in moves[observed + 1:]:
            selected, before = move["move"] if isinstance(move, dict) else move
            matches = [i for i, x in enumerate(tracks) if x.get("setVideoId") == selected]
            if (len(matches) != 1 or selected == before
                    or (before and sum(x.get("setVideoId") == before for x in tracks) != 1)):
                continue
            item = tracks.pop(matches[0])
            target = next((i for i, x in enumerate(tracks) if x.get("setVideoId") == before), len(tracks))
            tracks.insert(target, item)
        return tracks

    @Slot(str, str, int, result=bool)
    def moveDetailPlaylistItem(self, video_id, set_video_id, direction):
        if (self._busy or self._closing.is_set() or self._ytmusic is None
                or not self.detailCanEditPlaylist or direction not in (-1, 1) or not set_video_id):
            return False
        visible = self._detail_tracks_model.snapshot()
        index = next((i for i, x in enumerate(visible)
                      if x.get("setVideoId") == set_video_id and x.get("videoId") == video_id), -1)
        target = index + direction
        if index < 0 or not 0 <= target < len(visible):
            return False
        neighbor = dict(visible[target])
        if not neighbor.get("setVideoId"):
            return False
        playlist_id = self._detail_meta["playlistId"]
        pending = list(self._pending_playlist_moves.get(playlist_id, []))
        removed = set(self._pending_removed_playlist_items.get(playlist_id, set()))
        api = self._ytmusic
        def task():
            attempted = False
            try:
                data = api.get_playlist(playlist_id, limit=None)
                if data.get("owned") is not True:
                    raise ValueError("Not owned")
                tracks = self._project_playlist_moves(data.get("tracks") or [], pending)
                for sid, vid in ((set_video_id, video_id), (neighbor["setVideoId"], neighbor["videoId"])):
                    matches = [x for x in tracks if x.get("setVideoId") == sid]
                    if len(matches) != 1 or matches[0].get("videoId") != vid:
                        raise ValueError("Occurrence mismatch")
                rows = [x for x in core.usable_tracks(tracks) if x.get("setVideoId") not in removed]
                current = next(i for i, x in enumerate(rows) if x.get("setVideoId") == set_video_id)
                if not 0 <= current + direction < len(rows) or rows[current + direction].get("setVideoId") != neighbor["setVideoId"]:
                    raise ValueError("Order changed")
                if direction < 0:
                    before = neighbor["setVideoId"]
                else:
                    raw_target = next(i for i, x in enumerate(tracks) if x.get("setVideoId") == neighbor["setVideoId"])
                    before = next((x["setVideoId"] for x in tracks[raw_target + 1:] if x.get("setVideoId")), "")
                if before and sum(x.get("setVideoId") == before for x in tracks) != 1:
                    raise ValueError("Ambiguous successor")
                attempted = True
                response = api.edit_playlist(playlist_id, moveItem=(set_video_id, before) if before else set_video_id)
                status = response.get("status") if isinstance(response, dict) else response
                if status != "STATUS_SUCCEEDED":
                    raise RuntimeError("Move not confirmed")
                tracks = self._project_playlist_moves(tracks, [(set_video_id, before)])
                return {"ok": True, "playlistId": playlist_id, "move": (set_video_id, before),
                        "moveOrder": [x.get("setVideoId") for x in tracks],
                        "detail": {"title": data.get("title") or "Playlist",
                                   "meta": {"kind": "playlist", "playlistId": playlist_id, "owned": True},
                                   "tracks": [self._track(x) for x in core.usable_tracks(tracks)
                                              if x.get("setVideoId") not in removed]},
                        "message": "Pořadí skladby uloženo."}
            except Exception as exc:
                print(f"FelisMusic přesun v playlistu: {type(exc).__name__}")
                return {"ok": False, "message": (
                    "Přesun se nepodařilo potvrdit. Obnov playlist a zkontroluj pořadí."
                    if attempted else "Nelze ověřit pořadí, výskyt nebo vlastnictví playlistu. Obnov seznam; nic nebylo změněno.")}
        self._submit("playlist_move_item", "Ukládám pořadí skladby…", task)
        return True

    def _sync_playlist_queue_order(self, detail):
        if self._queue is None or self._queue.shuffle_active:
            return
        playlist_id = detail["meta"]["playlistId"]
        order = {x.get("setVideoId"): i for i, x in enumerate(detail["tracks"]) if x.get("setVideoId")}
        slots = [i for i in range(self._queue.count())
                 if self._queue.tracks[i].get("_guiPlaylistBinding", (None, None))[0] == playlist_id
                 and self._queue.tracks[i]["_guiPlaylistBinding"][1] in order]
        originals = [self._queue.tracks[i] for i in slots]
        sorted_tracks = sorted(originals, key=lambda song: order[song["_guiPlaylistBinding"][1]])
        if all(a is b for a, b in zip(originals, sorted_tracks)):
            return
        with self._transport_lock:
            current = self._queue.current()
            for slot, song in zip(slots, sorted_tracks):
                self._queue.tracks[slot] = song
                self._queue_source_indices[slot] = song.get("_guiOrigin", {}).get("index", -1)
            self._queue.index = next(i for i, song in enumerate(self._queue.tracks) if song is current)
            # Relocate the same occurrence, without resetting playback/rating or
            # pretending that its changed row number is a new audio track.
            self._player_track_marker = (id(self._queue), self._queue.index, self._current_video_id())
        self._prefetch_revision += 1
        if self._prefetch_future is not None:
            self._prefetch_future.cancel()
        self._sync_queue_model()
        self.playerChanged.emit()
        if not self._playback_transitioning and self._player_state in ("playing", "paused"):
            self._prefetch_next_track()

    @Slot(str, str, result=bool)
    def removeDetailPlaylistItem(self, video_id, set_video_id):
        if (self._busy or self._closing.is_set() or self._ytmusic is None
                or not self.detailCanEditPlaylist or not video_id or not set_video_id):
            return False
        if not any(x.get("videoId") == video_id and x.get("setVideoId") == set_video_id
                   for x in self._detail_tracks_model.snapshot()):
            return False
        playlist_id = self._detail_meta["playlistId"]
        api = self._ytmusic
        pending_moves = list(self._pending_playlist_moves.get(playlist_id, []))
        def task():
            attempted = False
            try:
                data = api.get_playlist(playlist_id, limit=None)
                if data.get("owned") is not True:
                    raise ValueError("Not owned")
                tracks = self._project_playlist_moves(data.get("tracks") or [], pending_moves)
                matches = [x for x in tracks if x.get("setVideoId") == set_video_id]
                if matches:
                    if len(matches) != 1 or matches[0].get("videoId") != video_id:
                        raise ValueError("Occurrence mismatch")
                    attempted = True
                    response = api.remove_playlist_items(playlist_id, [
                        {"videoId": video_id, "setVideoId": set_video_id}])
                    status = response.get("status") if isinstance(response, dict) else response
                    if status != "STATUS_SUCCEEDED":
                        raise RuntimeError("Removal not confirmed")
                remaining = [x for x in tracks if x.get("setVideoId") != set_video_id]
                return {"ok": True, "playlistId": playlist_id, "setVideoId": set_video_id,
                        "card": self._playlist(dict(data, playlistId=playlist_id, count=len(remaining))),
                        "detail": {"title": data.get("title") or "Playlist",
                                   "meta": {"kind": "playlist", "playlistId": playlist_id, "owned": True},
                                   "tracks": [self._track(x) for x in core.usable_tracks(remaining)]},
                        "message": "Skladba odebrána z playlistu." if matches else "Položka už v playlistu není. Seznam obnoven."}
            except Exception as exc:
                print(f"FelisMusic odebrání z playlistu: {type(exc).__name__}")
                return {"ok": False, "message": (
                    "Odebrání se nepodařilo potvrdit. Obnov playlist a zkontroluj jeho obsah."
                    if attempted else "Nelze ověřit položku nebo vlastnictví playlistu. Nic nebylo změněno.")}
        self._submit("playlist_remove_item", "Odebírám skladbu z playlistu…", task)
        return True

    def _update_playlist_browse_snapshots(self, detail):
        """Refresh saved browsing views, leaving the actual playback queue intact."""
        playlist_id = detail["meta"]["playlistId"]
        tracks = detail["tracks"]
        positions = {x.get("setVideoId"): i for i, x in enumerate(tracks) if x.get("setVideoId")}
        for song in self._queue.tracks if self._queue else []:
            origin = song.get("_guiOrigin", {})
            state = origin.get("detail_state", {})
            if origin.get("source") != "detail" or state.get("meta", {}).get("playlistId") != playlist_id:
                continue
            # Origins may share snapshots/state; the queue song retains its own
            # occurrence ID even when its row has just been removed from YTM.
            origin["index"] = positions.get(song.get("setVideoId"), -1)
            origin.setdefault("snapshots", {})["detail"] = deepcopy(tracks)
            state.update(title=detail["title"], tracks=deepcopy(tracks), meta=dict(detail["meta"]))
            origin["detail_title"] = detail["title"]
        self.playerChanged.emit()

    @Property(bool, notify=detailTitleChanged)
    def detailCanEditPlaylist(self):
        return (self._detail_meta.get("kind") == "playlist"
                and bool(self._detail_meta.get("playlistId"))
                and self._detail_meta.get("owned") is True)

    @Property(bool, notify=detailTitleChanged)
    def detailCanDeletePlaylist(self):
        playlist_id = self._detail_meta.get("playlistId", "")
        normalized = playlist_id.removeprefix("VL")
        return (self.detailCanEditPlaylist and normalized not in ("LM", "SE")
                and not normalized.startswith("RD") and playlist_id not in self._deleted_playlists)

    @Property("QVariantMap", notify=playlistDeleteChanged)
    def playlistDeleteState(self):
        return self._playlist_delete_state

    @Slot(result=bool)
    def openPlaylistDelete(self):
        if self._busy or self._closing.is_set() or self._ytmusic is None or not self.detailCanDeletePlaylist:
            return False
        playlist_id = self._detail_meta["playlistId"]
        api = self._ytmusic
        def task():
            try:
                data = api.get_playlist(playlist_id, limit=1)
                if data.get("owned") is not True or not data.get("title"):
                    raise ValueError("Not owned")
                return {"ok": True, "playlistId": playlist_id, "title": data["title"],
                        "pending": False, "completed": False, "locked": False, "message": ""}
            except Exception as exc:
                print(f"FelisMusic potvrzení smazání playlistu: {type(exc).__name__}")
                raise RuntimeError("Nelze ověřit vlastní playlist pro smazání.") from None
        self._submit("playlist_delete_read", "Načítám playlist pro potvrzení smazání…", task)
        return True

    @Slot()
    def cancelPlaylistDelete(self):
        if not self._playlist_delete_state.get("pending") and not self._playlist_delete_state.get("completed"):
            self._playlist_delete_state = {}
            self.playlistDeleteChanged.emit()

    _playlist_delete_verify_delays = (0.0, 0.5, 1.5)

    @staticmethod
    def _read_playlist_library_ids(api):
        # The public method returns [] even when its expected renderer is
        # absent. Validate the library layout before interpreting an empty list.
        raw = api._send_request("browse", {"browseId": "FEmusic_liked_playlists"})
        if not isinstance(raw, dict) or raw.get("error"):
            raise ValueError("Invalid library response")
        grid = get_library_contents(raw, ["gridRenderer"])
        if not isinstance(grid, dict) or not isinstance(grid.get("items"), list):
            raise ValueError("Missing library renderer")
        first_page = parse_content_list(grid["items"][1:], parse_playlist)
        playlists = api.get_library_playlists(limit=None)
        if not isinstance(playlists, list):
            raise ValueError("Invalid playlist list")
        ids = set()
        for item in playlists:
            playlist_id = core.playlist_id_from_item(item) if isinstance(item, dict) else None
            if not playlist_id:
                raise ValueError("Missing playlist ID")
            ids.add(str(playlist_id).removeprefix("VL"))
        # A separately parsed full list must include the validated first page.
        # A missing renderer in that second response must not look like deletion.
        if any(str(x["playlistId"]).removeprefix("VL") not in ids for x in first_page):
            raise ValueError("Incomplete playlist list")
        return ids

    def _verify_playlist_deletion(self, api, target):
        playlist_id = target["playlistId"].removeprefix("VL")
        before = target.get("beforeIds")
        for delay in self._playlist_delete_verify_delays:
            if self._closing.wait(delay):
                return False
            try:
                after = self._read_playlist_library_ids(api)
                if playlist_id in after:
                    continue
                if before is not None and playlist_id in before:
                    return True
                # Without a before/after library transition, only an explicit
                # not-found response confirms absence; parser/network errors do not.
                try:
                    api.get_playlist(target["playlistId"], limit=1)
                except YTMusicServerError as exc:
                    if str(exc).startswith("Server returned HTTP 404:"):
                        return True
            except Exception as exc:
                print(f"FelisMusic ověření smazání playlistu: {type(exc).__name__}")
        return False

    def _playlist_delete_result(self, api, target):
        if self._verify_playlist_deletion(api, target):
            return {"completed": True, "locked": True, "error": False, "canRecheck": False,
                    "message": f"Smazán playlist: {target['title']}", "verification": target}
        return {"completed": False, "locked": True, "error": False, "canRecheck": True,
                "message": "Výsledek smazání zatím není ověřen. Zkus Ověřit znovu nebo zkontroluj playlist ve webovém YTM. Mazání se znovu neodesílá.",
                "verification": target}

    @Slot()
    def recheckPlaylistDelete(self):
        target = self._playlist_delete_verification
        if (self._busy or self._closing.is_set() or not target
                or not self._playlist_delete_state.get("canRecheck")):
            return
        api = self._ytmusic
        self._playlist_delete_state = dict(self._playlist_delete_state, pending=True, message="Ověřuji smazání…")
        self.playlistDeleteChanged.emit()
        self._submit("playlist_delete_recheck", "Ověřuji smazání playlistu…",
                     lambda: self._playlist_delete_result(api, target))

    @Slot(result=bool)
    def confirmPlaylistDelete(self):
        state = self._playlist_delete_state
        if (self._busy or self._closing.is_set() or self._ytmusic is None or not state
                or state.get("pending") or state.get("locked") or state.get("completed")
                or state["playlistId"] in self._deleted_playlists):
            return False
        playlist_id, title = state["playlistId"], state["title"]
        api = self._ytmusic
        self._playlist_delete_state = dict(state, pending=True, error=False, message="Mažu playlist…")
        self.playlistDeleteChanged.emit()
        def task():
            attempted = False
            target = {"playlistId": playlist_id, "title": title, "beforeIds": None}
            try:
                data = api.get_playlist(playlist_id, limit=1)
                if data.get("owned") is not True:
                    return {"completed": False, "locked": True, "error": True,
                            "message": "Playlist už není vlastní. Nic nebylo smazáno."}
                if data.get("title") != title:
                    return {"completed": False, "locked": True, "error": True,
                            "message": "Název playlistu se změnil. Zavři potvrzení a otevři ho znovu. Nic nebylo smazáno."}
                try:
                    target["beforeIds"] = sorted(self._read_playlist_library_ids(api))
                except Exception as exc:
                    print(f"FelisMusic knihovna před smazáním: {type(exc).__name__}")
                attempted = True
                response = api.delete_playlist(playlist_id)
                status = response.get("status") if isinstance(response, dict) else response
                if status == "STATUS_SUCCEEDED":
                    return {"completed": True, "locked": True, "error": False, "canRecheck": False,
                            "message": f"Smazán playlist: {title}"}
                # Metadata only: never log response bodies, titles or auth data.
                keys = [key for key in ("status", "responseContext", "actions", "error")
                        if isinstance(response, dict) and key in response]
                known_status = status if status in ("STATUS_FAILED", "STATUS_SUCCEEDED") else "jiný/chybí"
                print(f"FelisMusic odpověď smazání: typ={type(response).__name__}; stav={known_status}; pole={','.join(keys)}")
                if status == "STATUS_FAILED" or (isinstance(response, dict) and response.get("error")):
                    return {"completed": False, "locked": True, "error": True, "canRecheck": True,
                            "message": "YT Music nepotvrdilo smazání. Zkontroluj stav přes Ověřit znovu nebo ve webovém YTM.",
                            "verification": target}
                return self._playlist_delete_result(api, target)
            except Exception as exc:
                print(f"FelisMusic smazání playlistu: {type(exc).__name__}")
                if attempted:
                    return self._playlist_delete_result(api, target)
                return {"completed": False, "locked": False, "error": True,
                        "message": "Nelze ověřit vlastnictví playlistu. Nic nebylo smazáno."}
        self._submit("playlist_delete_write", "Mažu playlist…", task)
        return True

    def _forget_deleted_playlist(self, playlist_id):
        self._deleted_playlists.add(playlist_id)
        self._pending_created_playlists.pop(playlist_id, None)
        self._pending_playlist_moves.pop(playlist_id, None)
        self._pending_removed_playlist_items.pop(playlist_id, None)
        def keep(item):
            return item.get("kind") != "playlist" or item.get("playlistId") != playlist_id
        for model in (self._library_items_model, self._playlists_model, self._search_results_model):
            items = model.snapshot()
            filtered = [x for x in items if keep(x)]
            if len(filtered) != len(items):
                model.set_items(filtered)
        def clean_snapshot(snapshot):
            for source, items in snapshot.items():
                snapshot[source] = [x for x in items if keep(x)]
        def clean_history(state):
            state["history"] = [x for x in state.get("history", [])
                                if x.get("meta", {}).get("playlistId") != playlist_id]
            for parent in state["history"]:
                clean_history(parent)
        clean_snapshot(self._playing_browse_snapshots)
        for index, song in enumerate(self._queue.tracks if self._queue else []):
            origin = song.get("_guiOrigin", {})
            state = origin.get("detail_state", {})
            clean_snapshot(origin.get("snapshots", {}))
            clean_history(state)
            if (state.get("meta", {}).get("playlistId") == playlist_id
                    or song.get("_guiPlaylistBinding", (None, None))[0] == playlist_id):
                song["_guiOrigin"] = {"source": "playing", "index": index, "context": {"page": 5}}
                song.pop("_guiPlaylistBinding", None)
        self._detail_history = [x for x in self._detail_history if x.get("meta", {}).get("playlistId") != playlist_id]
        for state in self._detail_history:
            clean_history(state)
        return_to_overview = self._detail_meta.get("playlistId") == playlist_id
        if return_to_overview:
            self.clearDetail()
        self.playerChanged.emit()
        return return_to_overview

    @Property("QVariantMap", notify=playlistEditChanged)
    def playlistEditState(self):
        return self._playlist_edit_state

    @Slot(result=bool)
    def openPlaylistEdit(self):
        if self._busy or self._closing.is_set() or self._ytmusic is None or not self.detailCanEditPlaylist:
            return False
        playlist_id = self._detail_meta["playlistId"]
        api = self._ytmusic
        def task():
            try:
                data = api.get_playlist(playlist_id, limit=1)
                if data.get("owned") is not True:
                    raise ValueError("Not owned")
                privacy = data.get("privacy")
                if privacy not in ("PRIVATE", "UNLISTED", "PUBLIC"):
                    raise ValueError("Missing privacy")
                return {"playlistId": playlist_id, "title": data["title"],
                        "description": data.get("description") or "", "privacy": privacy,
                        "pending": False, "completed": False, "locked": False, "message": ""}
            except Exception as exc:
                print(f"FelisMusic údaje playlistu: {type(exc).__name__}")
                raise RuntimeError("Nelze načíst údaje vlastního playlistu.") from None
        self._submit("playlist_edit_read", "Načítám údaje playlistu…", task)
        return True

    @Slot(str, str, str, result=bool)
    def savePlaylistEdit(self, title, description, privacy):
        state = self._playlist_edit_state
        if (self._busy or self._closing.is_set() or self._ytmusic is None or not state
                or state.get("pending") or state.get("locked") or state.get("completed")):
            return False
        title = str(title or "").strip()
        if not title or any(c in title + description for c in "<>") or privacy not in ("PRIVATE", "UNLISTED", "PUBLIC"):
            self._playlist_edit_state = dict(state, error=True, message="Vyplň název a nepoužívej znaky < a >.")
            self.playlistEditChanged.emit()
            return False
        playlist_id = state["playlistId"]
        api = self._ytmusic
        self._playlist_edit_state = dict(state, pending=True, error=False, message="Ukládám údaje…")
        self.playlistEditChanged.emit()
        def task():
            writing = False
            try:
                data = api.get_playlist(playlist_id, limit=1)
                if data.get("owned") is not True:
                    raise ValueError("Not owned")
                writing = True
                if description == "":
                    # ytmusicapi.edit_playlist ignores an empty description.
                    # Send its same actions explicitly so clearing it also works.
                    response = api._send_request("browse/edit_playlist", {
                        "playlistId": playlist_id,
                        "actions": [
                            {"action": "ACTION_SET_PLAYLIST_NAME", "playlistName": title},
                            {"action": "ACTION_SET_PLAYLIST_DESCRIPTION", "playlistDescription": ""},
                            {"action": "ACTION_SET_PLAYLIST_PRIVACY", "playlistPrivacy": privacy},
                        ],
                    })
                else:
                    response = api.edit_playlist(playlist_id, title=title, description=description, privacyStatus=privacy)
                status = response.get("status") if isinstance(response, dict) else response
                if status != "STATUS_SUCCEEDED":
                    raise RuntimeError("Edit not confirmed")
                return {"completed": True, "locked": True, "error": False,
                        "title": title, "description": description, "privacy": privacy,
                        "message": "Údaje playlistu uloženy."}
            except Exception as exc:
                print(f"FelisMusic úprava playlistu: {type(exc).__name__}")
                return {"completed": False, "locked": writing, "error": True,
                        "message": ("Uložení se nepodařilo potvrdit. Zavři formulář a zkontroluj údaje před dalším pokusem."
                                    if writing else "Nelze ověřit vlastnictví playlistu. Nic nebylo změněno.")}
        self._submit("playlist_edit_write", "Ukládám údaje playlistu…", task)
        return True

    @Property("QVariantMap", notify=playlistSaveChanged)
    def playlistSaveState(self):
        return self._playlist_save_state

    @Slot(str, int, result=bool)
    def openPlaylistSave(self, source, index):
        if source == "liked" and not self.likedComplete:
            return False
        if self._busy or self._closing.is_set() or self._ytmusic is None:
            return False
        items = self._source_items(source)
        if not 0 <= index < len(items):
            return False
        item = items[index]
        if not item.get("videoId") or item.get("kind", "song") not in ("song", "video", "upload_song", ""):
            return False
        return self._open_playlist_selection([dict(item)], item.get("title", "Skladba"), False)

    @Property(bool, notify=detailTitleChanged)
    def detailCanSavePlaylist(self):
        return bool(self._detail_title and any(self._playlist_song_supported(x) for x in self._detail_tracks_model.snapshot()))

    @staticmethod
    def _playlist_song_supported(item):
        return bool(item.get("videoId") and item.get("kind", "song") in ("song", "video", "upload_song", ""))

    @Slot(result=bool)
    def openCollectionPlaylistSave(self):
        if self._busy or self._closing.is_set() or self._ytmusic is None or not self.detailCanSavePlaylist:
            return False
        items = [dict(x) for x in self._detail_tracks_model.snapshot() if self._playlist_song_supported(x)]
        return self._open_playlist_selection(items, self._detail_title, True)

    def _open_playlist_selection(self, items, title, collection):
        self._playlist_save_selection = None
        self._playlist_save_verification = None
        self._playlist_save_items = items
        self._playlist_save_item = items[0]
        self._playlist_save_state = {"title": title, "selectionCount": len(items), "collection": collection,
                                     "targets": [], "pending": True, "completed": False,
                                     "locked": False, "message": ""}
        api = self._ytmusic
        deleted_ids = set(self._deleted_playlists)
        def task():
            targets = []
            for playlist in api.get_library_playlists(limit=None) or []:
                pid = str(core.playlist_id_from_item(playlist) or "")
                if playlist.get("owned") is True and pid and pid not in deleted_ids and pid not in ("LM", "SE") and not pid.startswith("RD"):
                    targets.append({"playlistId": pid, "title": str(playlist.get("title") or "Bez názvu")})
            return sorted(targets, key=lambda x: x["title"].casefold())
        self._submit("playlist_save_choices", "Načítám vlastní playlisty…", task)
        return True

    _playlist_verify_delays = (0.0, 0.5, 1.5)

    def _verify_playlist_song(self, api, target):
        for delay in self._playlist_verify_delays:
            if self._closing.wait(delay):
                return None
            try:
                data = api.get_playlist(target["playlistId"], limit=None)
                counts = Counter(x.get("videoId") for x in data.get("tracks", []))
                if all(counts[video_id] >= minimum for video_id, minimum in target["minimumCounts"].items()):
                    return data
            except Exception as exc:
                # Parser exceptions can include entire server responses. Keep
                # them out of user messages and retry only the read operation.
                print(f"FelisMusic ověření playlistu: {type(exc).__name__}")
        return None

    def _playlist_verification_result(self, api, target):
        after = self._verify_playlist_song(api, target)
        verified = after is not None
        if verified:
            message = (f"Vytvořen playlist: {target['title']}" if target["created"]
                       else f"Skladba přidána do playlistu: {target['title']}")
        else:
            message = (f"Playlist {target['title']} byl vytvořen." if target["created"]
                       else f"YT Music potvrdilo přidání skladby do playlistu {target['title']}.")
            message += " Obsah zatím nelze ověřit. Můžeš jej zkusit načíst znovu nebo zkontrolovat ve webovém YTM."
        if verified and target.get("batch"):
            message = (f"Vytvořen playlist: {target['title']}." if target["created"]
                       else f"Uloženo do playlistu: {target['title']}.")
            message += f" Přidáno skladeb: {target['addedCount']}. Vynecháno duplicit: {target['skipped']}."
        return {"message": message, "completed": True, "locked": True,
                "changed": True, "verified": verified, "canRecheck": not verified,
                "error": False, "playlistId": target["playlistId"], "detail": after,
                "verification": target}

    def _save_playlist_song(self, api, items, playlist_id, new_title, duplicates, privacy="PRIVATE"):
        attempted = False
        requested = [item["videoId"] for item in items]
        try:
            if new_title:
                video_ids = list(dict.fromkeys(requested))
                before_counts = Counter()
                attempted = True
                result = api.create_playlist(new_title, "", privacy_status=privacy, video_ids=video_ids)
                if not isinstance(result, str) or not result.strip():
                    raise RuntimeError("Creation not confirmed")
                playlist_id = result
                title = new_title
            else:
                before = api.get_playlist(playlist_id, limit=None)
                if before.get("owned") is not True:
                    return {"message": "Playlist už není vlastní nebo ho nelze upravovat.",
                            "completed": False, "locked": False, "changed": False, "error": True}
                title = before.get("title") or "Playlist"
                before_counts = Counter(x.get("videoId") for x in before.get("tracks", []))
                seen = set(before_counts)
                video_ids = []
                for video_id in requested:
                    if duplicates or video_id not in seen:
                        video_ids.append(video_id)
                        seen.add(video_id)
                if not video_ids:
                    message = (f"Skladba už v playlistu {title} je. Nic se nepřidalo." if len(items) == 1
                               else f"Všechny vybrané skladby už v playlistu {title} jsou. Nic se nepřidalo.")
                    return {"message": message, "completed": True, "duplicate": True,
                            "locked": False, "changed": False, "playlistId": playlist_id}
                attempted = True
                result = api.add_playlist_items(playlist_id, videoIds=video_ids, duplicates=duplicates)
                status = result.get("status") if isinstance(result, dict) else result
                if status != "STATUS_SUCCEEDED":
                    raise RuntimeError("Addition not confirmed")
            added_counts = Counter(video_ids)
            target = {"playlistId": playlist_id,
                      "minimumCounts": {video_id: before_counts[video_id] + count for video_id, count in added_counts.items()},
                      "title": title, "created": bool(new_title), "batch": len(items) > 1,
                      "addedCount": len(video_ids), "skipped": len(requested) - len(video_ids)}
            return self._playlist_verification_result(api, target)
        except Exception as exc:
            print(f"FelisMusic uložení playlistu: {type(exc).__name__}")
            if attempted:
                message = "Výsledek zápisu se nepodařilo potvrdit. Před dalším pokusem zkontroluj playlist ve webovém YTM."
            else:
                message = "Playlist se nepodařilo načíst. Zkus to prosím znovu."
            return {"message": message, "completed": False, "locked": attempted,
                    "changed": False, "error": True, "playlistId": playlist_id}

    @Slot()
    def recheckPlaylistSave(self):
        state = self._playlist_save_state
        target = getattr(self, "_playlist_save_verification", None)
        if (self._busy or self._closing.is_set() or not state.get("canRecheck") or not target):
            return
        target = dict(target)
        api = self._ytmusic
        self._playlist_save_state = dict(state, pending=True, message="Ověřuji obsah playlistu…")
        self.playlistSaveChanged.emit()
        self._submit("playlist_save_recheck", "Ověřuji obsah playlistu…",
                     lambda: self._playlist_verification_result(api, target))

    @Slot(str, bool)
    def saveSongToPlaylist(self, playlist_id, duplicates):
        state = self._playlist_save_state
        if (self._busy or self._closing.is_set() or not self._playlist_save_item
                or state.get("pending") or state.get("completed") or state.get("locked")):
            return
        if playlist_id not in {x["playlistId"] for x in state.get("targets", [])}:
            return
        self._begin_playlist_save(playlist_id, "", bool(duplicates))

    @Slot(str)
    @Slot(str, str)
    def createPlaylistWithSong(self, title, privacy="PRIVATE"):
        state = self._playlist_save_state
        if (self._busy or self._closing.is_set() or not self._playlist_save_item
                or state.get("pending") or state.get("completed") or state.get("locked")):
            return
        if privacy not in ("PRIVATE", "UNLISTED", "PUBLIC"):
            self._playlist_save_state = dict(state, error=True, message="Vyber platnou viditelnost playlistu.")
            self.playlistSaveChanged.emit()
            return
        title = str(title or "").strip()
        if not title or "<" in title or ">" in title:
            self._playlist_save_state = dict(state, error=True, message="Vyplň název playlistu bez znaků < a >.")
            self.playlistSaveChanged.emit()
            return
        self._begin_playlist_save("", title, False, privacy)

    def _begin_playlist_save(self, playlist_id, title, duplicates, privacy="PRIVATE"):
        items = [dict(x) for x in self._playlist_save_items]
        api = self._ytmusic
        self._playlist_save_state = dict(self._playlist_save_state, pending=True, message="Ukládám…", error=False)
        self.playlistSaveChanged.emit()
        self._submit("playlist_save_write", "Ukládám skladbu do playlistu…",
                     lambda: self._save_playlist_song(api, items, playlist_id, title, duplicates, privacy))

    @Property("QVariantMap", notify=songLibraryMenuChanged)
    def songLibraryMenuState(self):
        return self._song_library_menu

    @staticmethod
    def _library_song_controls(song):
        state = song.get("inLibrary")
        tokens = song.get("feedbackTokens") or {}
        if not isinstance(state, bool) or not isinstance(tokens, dict):
            return None
        token = tokens.get("remove" if state else "add")
        if not isinstance(token, str) or not token:
            return None
        return {"inLibrary": state, "token": token}

    def _fetch_song_library_controls(self, api, video_id, album_id):
        data = api.get_watch_playlist(videoId=video_id, limit=1)
        song = next((x for x in data.get("tracks", []) if x.get("videoId") == video_id), {})
        controls = self._library_song_controls(song)
        if controls:
            return controls
        album = song.get("album") or {}
        album_id = (album.get("id") if isinstance(album, dict) else "") or album_id
        if album_id and "privately_owned" not in album_id:
            data = api.get_album(album_id)
            song = next((x for x in data.get("tracks", []) if x.get("videoId") == video_id), {})
            controls = self._library_song_controls(song)
            if controls:
                return controls
        raise RuntimeError("YT Music pro tuto skladbu neposkytlo ovládání knihovny.")

    @Slot(str, int, result=int)
    def prepareSongLibrary(self, source, index):
        if self._closing.is_set() or self._ytmusic is None or self._song_library_action_pending:
            return 0
        items = self._source_items(source)
        if not 0 <= index < len(items):
            return 0
        item = items[index]
        if (not item.get("videoId") or self._is_upload(item)
                or item.get("kind", "song") not in ("song", "video", "")):
            return 0
        self._library_probe_generation += 1
        request = self._library_probe_generation
        if self._library_probe_future is not None:
            self._library_probe_future.cancel()
        self._song_library_item = dict(item)
        self._song_library_token = ""
        self._song_library_menu = {"requestId": request, "videoId": item["videoId"],
                                  "pending": True, "available": False,
                                  "message": "Zjišťuji stav knihovny…"}
        self.songLibraryMenuChanged.emit()
        def work():
            if self._closing.is_set() or request != self._library_probe_generation:
                return
            result, error = {}, ""
            try:
                # An independent authenticated client keeps the main API worker
                # free for Mix/browsing while this read is waiting on the network.
                if self._library_probe_api is None:
                    self._library_probe_api = instrument_ytmusic(YTMusic(dict(self._library_probe_headers)))
                result = self._fetch_song_library_controls(self._library_probe_api, item["videoId"], item.get("albumId", ""))
            except Exception as exc:
                error = str(exc)
            self._songLibraryProbeReady.emit(request, result, error)
        self._library_probe_future = self._library_probe_executor.submit(work)
        return request

    @Slot(int)
    def cancelSongLibraryProbe(self, request):
        if request != self._library_probe_generation:
            return
        self._library_probe_generation += 1
        if self._library_probe_future is not None:
            self._library_probe_future.cancel()
        self._song_library_menu = {}
        self._song_library_token = ""
        self.songLibraryMenuChanged.emit()

    @Slot(int, object, str)
    def _apply_song_library_probe(self, request, result, error):
        if self._closing.is_set() or request != self._library_probe_generation:
            return
        self._song_library_token = result.get("token", "")
        self._song_library_menu = dict(self._song_library_menu, pending=False,
            available=not bool(error), inLibrary=result.get("inLibrary", False), message=error)
        self.songLibraryMenuChanged.emit()

    @Slot(int)
    def changeSongLibrary(self, request):
        state = self._song_library_menu
        if (self._busy or self._closing.is_set() or request != state.get("requestId")
                or self._song_library_action_pending or not state.get("available")
                or state.get("pending") or not self._song_library_token):
            return
        wanted = not state["inLibrary"]
        token = self._song_library_token
        item = dict(self._song_library_item)
        api = self._ytmusic
        self._song_library_action_pending = True
        self._song_library_menu = dict(state, pending=True, message="Ukládám změnu…")
        self.songLibraryMenuChanged.emit()
        def task():
            api.edit_song_library_status(feedbackTokens=[token])
            try:
                controls = self._fetch_song_library_controls(api, item["videoId"], item.get("albumId", ""))
                if controls["inLibrary"] != wanted:
                    raise RuntimeError("YT Music zatím nevrátilo požadovaný stav.")
            except Exception as exc:
                raise RuntimeError("Požadavek byl odeslán, ale změnu se nepodařilo ověřit. "
                                   "Znovu otevři nabídku skladby pro načtení stavu. " + str(exc)) from exc
            return dict(controls, item=item, requestId=request)
        self._submit("song_library_action", "Ukládám změnu knihovny…", task)

    def _update_song_library_snapshots(self, item, in_library):
        # Keep original browsing snapshots consistent, without editing the queue.
        if self._library_section == "songs":
            items = [x for x in self._library_items_model.snapshot() if x.get("videoId") != item["videoId"]]
            if in_library:
                items.insert(0, dict(item))
            self._library_items_model.set_items(self._sort_normalized(items, self._library_order))
        if self._queue is None:
            return
        updated = {}
        for song in self._queue.tracks:
            origin = song.get("_guiOrigin", {})
            context = origin.get("context", {})
            if context.get("librarySection") != "songs":
                continue
            items = origin.get("snapshots", {}).get("library")
            if items is None:
                continue
            if id(items) not in updated:
                remaining = [x for x in items if x.get("videoId") != item["videoId"]]
                if in_library:
                    remaining.insert(0, dict(item))
                items[:] = self._sort_normalized(remaining, context.get("libraryOrder"))
                updated[id(items)] = {x.get("videoId"): i for i, x in enumerate(items)}
            if origin.get("source") == "library":
                origin["index"] = updated[id(items)].get(song.get("videoId"), -1)
        self.playerChanged.emit()

    def _radio_queue_marker(self):
        # An explicit queue edit while the API is working supersedes its result.
        return (id(self._queue), tuple(id(song) for song in self._queue.tracks)) if self._queue else None

    def _maybe_refill_radio(self):
        queue = self._queue
        if (self._closing.is_set() or self._busy or self._radio_refill_pending
                or self._ytmusic is None or queue is None or queue.empty() or not queue.radio_active
                or self._playback_transitioning
                or (self._player_state not in ("playing", "paused")
                    and self._radio_waiting_for_tracks is not queue)
                or queue.count() - queue.index - 1 > core.current_mix_refill_threshold()
                or monotonic() < queue.radio_refill_retry_after):
            return False
        # CLI mutates its queue synchronously. Give it a detached list and apply
        # only the new suffix on the Qt thread; playback may advance meanwhile.
        snapshot = core.PlaybackQueue(list(queue.tracks), start_index=queue.index, radio_active=True)
        snapshot.radio_refill_retry_after = queue.radio_refill_retry_after
        count = snapshot.count()
        marker, revision, api = self._radio_queue_marker(), self._radio_refill_revision, self._ytmusic
        self._radio_refill_pending = True

        def work():
            result = {"queue": queue, "marker": marker, "revision": revision}
            try:
                core.refill_radio_queue(api, snapshot)
                result.update(tracks=snapshot.tracks[count:], retry=snapshot.radio_refill_retry_after)
            except Exception as exc:
                print(f"FelisMusic doplnění mixu: {type(exc).__name__}")
                result.update(tracks=[], retry=monotonic() + 30)
            self._radioRefillReady.emit(result)

        # Share the API executor to serialize account requests, but do not set
        # global busy: browsing, transport and menus remain usable during refill.
        self._executor.submit(work)
        return True

    @Slot(object)
    def _apply_radio_refill(self, result):
        self._radio_refill_pending = False
        queue = result["queue"]
        if (self._closing.is_set() or queue is not self._queue or not queue.radio_active
                or result["revision"] != self._radio_refill_revision
                or result["marker"] != self._radio_queue_marker()):
            return
        queue.radio_refill_retry_after = result["retry"]
        if not result["tracks"]:
            if not self._busy:
                self._set_status("Další část mixu zatím není dostupná · zkusím znovu za 30 s")
            return
        previous_next = self._next_prefetch_id()
        start = queue.count()
        for offset, raw in enumerate(result["tracks"]):
            item = self._track(raw)
            track = self._playback_track(item)
            track["_guiOrigin"] = {"source": "playing", "index": start + offset, "context": {"page": 5}}
            queue.tracks.append(track)
            self._queue_source_indices.append(start + offset)
            self._playing_tracks_model.insert_item(start + offset, item)
        self.playerChanged.emit()
        if self._radio_waiting_for_tracks is queue and self._player_state == "idle":
            self._radio_waiting_for_tracks = None
            if queue.next():
                self._set_player_from_queue()
                self._start_current_async(direction=1)
            return
        if previous_next != self._next_prefetch_id():
            self._prefetch_revision += 1
            if self._prefetch_future is not None:
                self._prefetch_future.cancel()
            if self._player_state in ("playing", "paused") and not self._playback_transitioning:
                self._prefetch_next_track()
        if not self._busy:
            self._set_status(f"Mix doplněn · +{len(result['tracks'])} skladeb · celkem {queue.count()}")

    @Property(bool, notify=playerChanged)
    def playerCanShuffle(self):
        return (self.playerHasTrack and self.playerCanEditQueue and not self._queue.radio_active
                and not self.playerQueueLoading and not self.playerQueueIncomplete
                and not self._queue.current().get("_guiRemoveAfterPlayback")
                and self._queue.source_playlist_id not in self._deleted_playlists
                and core.youtube_shuffle_supported(self._queue.source_playlist_id))

    @Slot(result=bool)
    def shuffleQueue(self):
        if self._busy or self._ytmusic is None or not self.playerCanShuffle:
            return False
        generation = self._playback_generation
        marker = self._radio_queue_marker()
        current = self._queue.current()
        api = self._ytmusic
        playlist_id, count = self._queue.source_playlist_id, self._queue.count()

        def task():
            result = {"generation": generation, "marker": marker, "current": current}
            try:
                result["tracks"] = core.get_youtube_shuffle_tracks(api, playlist_id, count)
            except Exception as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"
            return result

        self._submit("shuffle_queue", "YouTube Music míchá frontu…", task)
        return True

    def _apply_queue_shuffle(self, result):
        if (self._closing.is_set() or result["generation"] != self._playback_generation
                or result["marker"] != self._radio_queue_marker()
                or not self.playerCanShuffle or self._queue.current() is not result["current"]):
            return
        if result.get("error"):
            self._set_status("Frontu se nepodařilo zamíchat")
            self.errorOccurred.emit(result["error"])
            return
        # Adapt the CLI's current-first YTM shuffle without replacing exact
        # occurrences with ambiguous watch-playlist rows. Never lose GUI extras
        # or invent duplicates when the server repeats an ID or omits a song.
        current = result["current"]
        remaining = [song for song in self._queue.tracks if song is not current]
        manual = [song for song in remaining if song.get("_guiManualEnqueue")]
        collection = [song for song in remaining if not song.get("_guiManualEnqueue")]
        buckets = {}
        for song in collection:
            buckets.setdefault(song.get("videoId"), []).append(song)
        ordered = []
        used = set()
        for item in result["tracks"]:
            bucket = buckets.get(item.get("videoId"), [])
            if bucket:
                song = bucket.pop(0)
                ordered.append(song)
                used.add(id(song))
        ordered.extend(song for song in collection if id(song) not in used)
        if manual:
            # YTM cannot order songs added only to our local queue. Mix their
            # exact occurrences into random slots, preserving YTM's relative
            # collection order while also randomizing the manual items.
            random.shuffle(manual)
            manual_slots = set(random.sample(range(len(ordered) + len(manual)), len(manual)))
            manual_items, collection_items = iter(manual), iter(ordered)
            ordered = [next(manual_items) if index in manual_slots else next(collection_items)
                       for index in range(len(ordered) + len(manual))]
        with self._transport_lock:
            self._queue.tracks = [current, *ordered]
            self._queue.index = 0
            self._queue.shuffle_active = True
            self._queue_source_indices = [song.get("_guiOrigin", {}).get("index", -1)
                                          for song in self._queue.tracks]
            self._player_track_marker = (id(self._queue), 0, current.get("videoId"))
        self._prefetch_revision += 1
        if self._prefetch_future is not None:
            self._prefetch_future.cancel()
        self._sync_queue_model()
        self.playerChanged.emit()
        if self._player_state in ("playing", "paused"):
            self._prefetch_next_track()
        self._set_status("Fronta zamíchána · aktuální skladba pokračuje")
        self.queueShuffled.emit()

    @Property(bool, notify=detailTitleChanged)
    def detailCanShuffle(self):
        meta = self._detail_meta
        return (meta.get("kind") in ("playlist", "album")
                and core.youtube_shuffle_supported(self._detail_shuffle_id())
                and self._detail_tracks_model.count > 0)

    def _detail_shuffle_id(self):
        meta = self._detail_meta
        return meta.get("playlistId", "") if meta.get("kind") == "playlist" else meta.get("shufflePlaylistId", "")

    def _collection_radio_source_id(self):
        value = self._detail_shuffle_id()
        return value.strip().removeprefix("VL") if isinstance(value, str) else ""

    @Property(bool, notify=detailTitleChanged)
    def detailCanCollectionRadio(self):
        return (self._detail_meta.get("kind") in ("playlist", "album")
                and bool(self._collection_radio_source_id())
                and self._collection_radio_source_id() not in self._deleted_playlists
                and self._detail_tracks_model.count > 0)

    @Slot(result=bool)
    def startCollectionRadio(self):
        if (self._busy or self._ytmusic is None or not self.playerCanEditQueue
                or not self.detailCanCollectionRadio):
            return False
        self._radio_refill_revision += 1
        kind, source_id = self._detail_meta["kind"], self._collection_radio_source_id()
        title = self._detail_title
        radio_id = source_id if source_id.startswith("RDAMPL") else "RDAMPL" + source_id
        generation, marker, api = self._playback_generation, self._radio_queue_marker(), self._ytmusic

        def task():
            result = {"kind": kind, "sourceId": source_id, "name": f"Mix: {title}",
                      "generation": generation, "marker": marker}
            try:
                # The collection is the seed, never its first video. Albums
                # supply audioPlaylistId; the MPRE browse ID is not playable.
                data = api.get_watch_playlist(playlistId=radio_id, limit=core.MIX_LIMIT, radio=True)
                tracks = core.unique_new_radio_tracks(core.PlaybackQueue([]),
                    core.usable_tracks(data.get("tracks") or []))
                tracks = core.limit_radio_tracks_for_test(tracks)
                if not tracks:
                    raise RuntimeError("YouTube Music nevrátilo přehratelný mix této kolekce.")
                result["tracks"] = [self._playback_track(self._track(x)) for x in tracks]
            except Exception as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"
            return result

        self._submit("collection_radio", f"Načítám mix · {title}…", task)
        return True

    def _apply_collection_radio(self, result):
        if (self._closing.is_set() or result["generation"] != self._playback_generation
                or result["marker"] != self._radio_queue_marker()
                or self._detail_meta.get("kind") != result["kind"]
                or self._collection_radio_source_id() != result["sourceId"]):
            return
        if result.get("error"):
            self._set_status("Mix kolekce se nepodařilo načíst")
            self.errorOccurred.emit(result["error"])
            return
        self._start_generated_queue(result["tracks"], result["name"], radio=True)
        self.radioStarted.emit()

    @Property(bool, notify=detailTitleChanged)
    def detailCanArtistRadio(self):
        return self._detail_meta.get("kind") == "artist" and bool(self._detail_meta.get("radioId"))

    @Property(bool, notify=detailTitleChanged)
    def detailCanArtistShuffle(self):
        return self._detail_meta.get("kind") == "artist" and bool(self._detail_meta.get("shuffleId"))

    @Slot(str, result=bool)
    def startArtistPlayback(self, mode):
        if (self._busy or self._ytmusic is None or not self.playerCanEditQueue
                or mode not in ("radio", "shuffle")
                or not (self.detailCanArtistRadio if mode == "radio" else self.detailCanArtistShuffle)):
            return False
        self._radio_refill_revision += 1
        artist_id = self._detail_meta["browseId"]
        artist_name = self._detail_title
        origin = self._make_origin("detail", -1, self._source_items("detail"))
        playlist_id = self._detail_meta["radioId" if mode == "radio" else "shuffleId"]
        generation, marker, api = self._playback_generation, self._radio_queue_marker(), self._ytmusic

        def task():
            result = {"artistId": artist_id, "mode": mode, "generation": generation, "marker": marker,
                      "origin": origin}
            try:
                if mode == "shuffle":
                    tracks = self._first_watch_page(result, api, playlist_id, shuffle=False, limit=core.MIX_LIMIT)
                    name = f"{artist_name} - Náhodně"
                else:
                    queue = core.artist_action_queue(api, artist_name, playlist_id, mode=mode)
                    if queue is None or queue.empty():
                        raise RuntimeError("YouTube Music nevrátilo přehratelnou frontu interpreta.")
                    tracks = core.unique_new_radio_tracks(core.PlaybackQueue([]), queue.tracks)
                    tracks = core.limit_radio_tracks_for_test(tracks)
                    name = queue.name
                result.update(name=name, tracks=[self._playback_track(self._track(x)) for x in tracks])
            except Exception as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"
            return result

        self._submit("artist_playback", f"Načítám {'mix' if mode == 'radio' else 'náhodné pořadí'} · {artist_name}…", task)
        return True

    def _apply_artist_playback(self, result):
        if (self._closing.is_set() or result["generation"] != self._playback_generation
                or result["marker"] != self._radio_queue_marker()
                or self._detail_meta.get("kind") != "artist"
                or self._detail_meta.get("browseId") != result["artistId"]):
            return
        if result.get("error"):
            self._set_status("Frontu interpreta se nepodařilo načíst")
            self.errorOccurred.emit(result["error"])
            return
        self._start_generated_queue(result["tracks"], result["name"],
            radio=result["mode"] == "radio", shuffle=result["mode"] == "shuffle",
            origin=result["origin"] if result["mode"] == "shuffle" else None)
        if result["mode"] == "shuffle":
            self._attach_watch_stream(result)
        self.artistPlaybackStarted.emit()

    def _start_generated_queue(self, tracks, name, radio=False, shuffle=False, origin=None):
        self._radio_waiting_for_tracks = None
        self._prefetch_revision += 1
        if self._prefetch_future is not None:
            self._prefetch_future.cancel()
        self._queue = core.PlaybackQueue(tracks, name=name, radio_active=radio, shuffle_active=shuffle)
        self._repeat_mode = "off"
        self._queue_source = "playing"
        self._queue_source_indices = list(range(self._queue.count()))
        self._playing_browse_snapshots = {}
        self._playing_detail_title = ""
        # Copy the origin graph once for the whole queue. Each occurrence
        # retains its own index/context record, while shared source snapshots
        # stay shared and isolated from the input. Without a shared memo a
        # list of N songs was copied N times on the GUI thread.
        origin_memo = {}
        for index, song in enumerate(self._queue.tracks):
            song["_guiOrigin"] = (deepcopy(song.get("_guiOrigin", origin), origin_memo) if origin is not None else
                                  {"source": "playing", "index": index, "context": {"page": 5}})
        self._sync_queue_model()
        if origin is not None:
            self.playbackSourceCaptured.emit()
        self._set_player_from_queue()
        self._start_current_async(direction=1, stop_current=True)

    @Slot(str, result=bool)
    def startLikedPlayback(self, mode):
        if (self._busy or self._ytmusic is None or not self.playerCanEditQueue
                or mode not in ("radio", "shuffle") or not self._liked_model.count
                or not self.likedComplete):
            return False
        self._radio_refill_revision += 1
        items = self._source_items("liked")
        origin = self._make_origin("liked", -1, items)
        generation, marker, api = self._playback_generation, self._radio_queue_marker(), self._ytmusic

        def task():
            result = {"mode": mode, "origin": origin, "generation": generation, "marker": marker}
            try:
                if mode == "shuffle":
                    indices = [i for i, item in enumerate(items) if item.get("videoId")]
                    random.shuffle(indices)
                    result["indices"] = indices
                    tracks = [items[i] for i in indices]
                else:
                    data = api.get_watch_playlist(playlistId="RDAMPLLL", limit=core.MIX_LIMIT, radio=True)
                    tracks = core.unique_new_radio_tracks(core.PlaybackQueue([]),
                        core.usable_tracks(data.get("tracks") or []))
                    tracks = core.limit_radio_tracks_for_test(tracks)
                if not tracks:
                    raise RuntimeError("YouTube Music nevrátilo přehratelnou frontu oblíbené hudby.")
                result["tracks"] = [self._playback_track(x if mode == "shuffle" else self._track(x))
                                    for x in tracks]
            except Exception as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"
            return result

        self._submit("liked_playback", "Načítám oblíbenou hudbu · " +
                     ("mix…" if mode == "radio" else "náhodně…"), task)
        return True

    def _apply_liked_playback(self, result):
        if (self._closing.is_set() or result["generation"] != self._playback_generation
                or result["marker"] != self._radio_queue_marker()
                or result["origin"]["snapshots"]["liked"] != self._source_items("liked")):
            return
        if result.get("error"):
            self._set_status("Frontu oblíbené hudby se nepodařilo načíst")
            self.errorOccurred.emit(result["error"])
            return
        shuffle = result["mode"] == "shuffle"
        origin = result["origin"] if shuffle else None
        if shuffle:
            for song, index in zip(result["tracks"], result["indices"]):
                song["_guiOrigin"] = dict(origin, index=index)
        self._start_generated_queue(result["tracks"],
            "Oblíbená hudba – " + ("Náhodně" if shuffle else "Mix"),
            radio=not shuffle, shuffle=shuffle, origin=origin)
        if shuffle:
            self._queue.source_playlist_id = "LL"
            self._queue_source_indices = result["indices"]
            self.collectionShuffleStarted.emit()
        else:
            self.radioStarted.emit()

    def _first_watch_page(self, result, api, playlist_id, shuffle=True, limit=None):
        pager = WatchPages(api, playlist_id, shuffle=shuffle, limit=limit)
        while not self._closing.is_set():
            raw, more = pager.next_page()
            tracks = core.usable_tracks(raw)
            if tracks or not more:
                if not tracks:
                    raise RuntimeError("YouTube Music nevrátilo žádnou přehratelnou náhodnou frontu.")
                result.update(pager=pager, more=more)
                return tracks
        raise core.AudioPreparationCancelled()

    def _attach_watch_stream(self, result):
        if not result.get("more"):
            return
        origin = self._current_origin()
        source = origin.get("source")
        matches = {}
        for index, item in enumerate(origin.get("snapshots", {}).get(source, [])):
            if item.get("videoId"):
                matches.setdefault(item["videoId"], []).append(index)
        for song in self._queue.tracks:
            positions = matches.get(song["videoId"], [])
            index = song.get("_guiOrigin", {}).get("index", -1)
            if index in positions:
                positions.remove(index)
        self._watch_stream = {"queue": self._queue, "pager": result["pager"],
            "origin": origin, "matches": matches, "state": "loading", "waiting": False}
        self.playerChanged.emit()
        self._schedule_watch_page(self._watch_stream)

    def _schedule_watch_page(self, stream):
        def submit():
            if (self._closing.is_set() or stream is not self._watch_stream
                    or stream["queue"] is not self._queue or stream["state"] != "loading"):
                return
            def work():
                if self._closing.is_set() or stream is not self._watch_stream:
                    return
                result = {"stream": stream}
                try:
                    tracks, more = stream["pager"].next_page()
                    result.update(items=[self._track(x) for x in core.usable_tracks(tracks)], more=more)
                except Exception as exc:
                    result["error"] = type(exc).__name__
                    trace = current_trace()
                    if trace:
                        trace.event("api.error", error=type(exc).__name__)
                self._watchPageReady.emit(result)
            self._executor.submit(work, _diagnostic_label="api.shuffle_page")
        QTimer.singleShot(0, submit)

    @Slot(object)
    def _apply_watch_page(self, result):
        stream = result["stream"]
        if (self._closing.is_set() or stream is not self._watch_stream
                or stream["queue"] is not self._queue or stream["state"] != "loading"):
            return
        if self._busy:
            # A user-requested queue replacement validates its old marker
            # before background appends can alter it. Keep this exact page.
            QTimer.singleShot(50, lambda: self._apply_watch_page(result))
            return
        if result.get("error"):
            stream.update(state="error", waiting=False)
            self.playerChanged.emit()
            self._set_status("Další část náhodné fronty se nepodařilo načíst")
            return
        previous_next = self._next_prefetch_id()
        for item in result["items"]:
            positions = stream["matches"].get(item["videoId"], [])
            index = positions.pop(0) if positions else -1
            track = self._playback_track(item)
            track["_guiOrigin"] = dict(stream["origin"], index=index)
            self._queue.tracks.append(track)
            self._queue_source_indices.append(index)
        self._playing_tracks_model.append_items(result["items"])
        self._after_stream_append(stream, previous_next, result["more"])
        if result["more"]:
            self._schedule_watch_page(stream)

    @Slot(result=bool)
    def shuffleDetail(self):
        if (self._busy or not self.playerCanEditQueue or self._ytmusic is None
                or not self.detailCanShuffle):
            return False
        # A user-requested replacement takes priority over an older refill,
        # whose append would otherwise invalidate this request's queue marker.
        self._radio_refill_revision += 1
        state = self._detail_state()
        generation = self._playback_generation
        marker = self._radio_queue_marker()
        origin = self._make_origin("detail", -1, state["tracks"])
        playlist_id = self._detail_shuffle_id()

        def task():
            result = {"state": state, "generation": generation, "marker": marker,
                      "origin": origin, "playlistId": playlist_id}
            try:
                # Shuffle exact occurrences from the complete browsing snapshot.
                indices = [i for i, item in enumerate(state["tracks"]) if item.get("videoId")]
                random.shuffle(indices)
                if not indices:
                    raise RuntimeError("Kolekce neobsahuje přehratelné skladby.")
                result["local_indices"] = indices
                result["items"] = [state["tracks"][i] for i in indices]
            except Exception as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"
            return result

        self._submit("shuffle_detail", f"Připravuji náhodné pořadí · {state['title']}…", task)
        return True

    def _apply_detail_shuffle(self, result):
        if (self._closing.is_set() or result["generation"] != self._playback_generation
                or result["marker"] != self._radio_queue_marker()
                or result["state"] != self._detail_state()):
            return
        if result.get("error"):
            self._set_status("Náhodné pořadí se nepodařilo načíst")
            self.errorOccurred.emit(result["error"])
            return
        # Both playlist and album shuffle preserve exact source occurrences.
        tracks, indices = [], []
        for item, index in zip(result["items"], result["local_indices"]):
            track = self._playback_track(item)
            if (result["state"]["meta"].get("kind") == "playlist"
                    and item.get("setVideoId")):
                track["_guiPlaylistBinding"] = (result["playlistId"], item["setVideoId"])
            track["_guiOrigin"] = dict(result["origin"], index=index)
            tracks.append(track)
            indices.append(index)
        self._prefetch_revision += 1
        if self._prefetch_future is not None:
            self._prefetch_future.cancel()
        self._queue = core.PlaybackQueue(
            tracks, name=result["state"]["title"],
            source_playlist_id=result["playlistId"], shuffle_active=True)
        self._repeat_mode = "off"
        self._queue_source = "detail"
        self._queue_source_indices = indices
        self._playing_browse_snapshots = result["origin"]["snapshots"]
        self._playing_detail_title = result["state"]["title"]
        self._playing_liked_order = result["origin"]["liked_order"]
        self._sync_queue_model()
        self.playbackSourceCaptured.emit()
        self._set_player_from_queue()
        self._start_current_async(direction=1, stop_current=True)
        self._set_status(f"Náhodně · {self._queue.name} · {len(tracks)} skladeb")
        self.collectionShuffleStarted.emit()

    @Slot(str, int, result=bool)
    def startRadioFrom(self, source, index):
        if source == "liked" and not self.likedComplete:
            return False
        if self._busy or not self.playerCanEditQueue or self._ytmusic is None:
            return False
        items = self._source_items(source)
        if not 0 <= index < len(items):
            return False
        item = items[index]
        if (not item.get("videoId") or self._is_upload(item)
                or item.get("kind", "song") not in ("song", "video", "")):
            return False
        self._radio_refill_revision += 1
        seed = self._playback_track(item)
        generation = self._playback_generation
        marker = self._radio_queue_marker()
        api = self._ytmusic
        def task():
            result = {"generation": generation, "marker": marker}
            try:
                # Reuse the CLI's YTM request, filtering and test block limit.
                block = core.get_radio_block(api, seed["videoId"])
                queue = core.PlaybackQueue([seed])
                rest = core.unique_new_radio_tracks(queue, block, seed["videoId"])
                if not rest:
                    raise RuntimeError("YouTube Music nevrátilo žádné další skladby pro mix.")
                tracks = [seed] + [self._playback_track(self._track(song)) for song in rest]
                result["tracks"] = core.limit_radio_tracks_for_test(tracks)
            except Exception as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"
            return result
        self._submit("radio", f"Vytvářím Mix · {seed['title']}…", task)
        return True

    def _apply_radio(self, result):
        if (self._closing.is_set() or result["generation"] != self._playback_generation
                or result["marker"] != self._radio_queue_marker()):
            return
        if result.get("error"):
            self._set_status("Mix se nepodařilo vytvořit")
            self.errorOccurred.emit(result["error"])
            return
        tracks = result["tracks"]
        self._radio_waiting_for_tracks = None
        current = self._queue.current() if self.playerHasTrack else None
        keep_audio = (current is not None and current.get("videoId") == tracks[0]["videoId"]
                      and self._player_state in ("playing", "paused"))
        if keep_audio:
            tracks[0] = dict(current)
        self._prefetch_revision += 1
        if self._prefetch_future is not None:
            self._prefetch_future.cancel()
        self._queue = core.PlaybackQueue(tracks, name=f"Mix: {tracks[0]['title']}", radio_active=True)
        self._repeat_mode = "off"
        self._queue_source = "playing"
        self._queue_source_indices = list(range(len(tracks)))
        self._playing_browse_snapshots = {}
        for index, song in enumerate(self._queue.tracks):
            song["_guiOrigin"] = {"source": "playing", "index": index, "context": {"page": 5}}
        self._sync_queue_model()
        if keep_audio:
            # Do not reset time, rating or transport state for the current seed.
            self._player_track_marker = (id(self._queue), 0, tracks[0]["videoId"])
            self.playerChanged.emit()
            self.playerTrackChanged.emit()
            self._prefetch_next_track()
        else:
            self._set_player_from_queue()
            self._start_current_async(direction=1, stop_current=True)
        self._set_status(f"{self._queue.name} · {self._queue.count()} skladeb")
        self.radioStarted.emit()

    @Slot(str, int, bool, "QVariantMap", result=bool)
    def enqueueFrom(self, source, index, play_next, context):
        return self._enqueue_items(source, [index], play_next, context)

    def _enqueue_items(self, source, indices, play_next, context):
        if source == "liked" and not self.likedComplete:
            return False
        if not self.playerCanEditQueue or not indices:
            return False
        items = self._source_items(source)
        if any(not 0 <= i < len(items) or not items[i].get("videoId") for i in indices):
            return False
        # Capture the whole selection before modifying the queue or its model.
        tracks = []
        for index in indices:
            track = self._playback_track(items[index])
            track["_guiManualEnqueue"] = True
            if source == "playing":
                track["_guiOrigin"] = deepcopy(self._queue.tracks[index].get("_guiOrigin", {}))
            else:
                track["_guiOrigin"] = self._make_origin(source, index, items, context)
            tracks.append(track)
        had_queue = self.playerHasTrack
        previous_next = self._next_prefetch_id()
        if not had_queue:
            self._queue_source = source
            self._queue_source_indices = list(indices)
            self._queue = core.PlaybackQueue(tracks, name=self._queue_name_for_source(source))
            self._repeat_mode = "off"
            origin = tracks[0]["_guiOrigin"]
            self._playing_browse_snapshots = origin.get("snapshots", {})
            self._playing_detail_title = origin.get("detail_title", "")
            self._playing_liked_order = origin.get("liked_order", "")
            self._sync_queue_model()
            self._set_player_from_queue()
        else:
            position = self._queue.index + 1 if play_next else self._queue.count()
            self._queue.tracks[position:position] = tracks
            self._queue_source_indices[position:position] = [-1] * len(tracks)
            for offset, index in enumerate(indices):
                self._playing_tracks_model.insert_item(position + offset, items[index])
            self.playerChanged.emit()
        if had_queue and previous_next != self._next_prefetch_id():
            self._prefetch_revision += 1
            if self._prefetch_future is not None:
                self._prefetch_future.cancel()
            if self._player_state in ("playing", "paused"):
                self._prefetch_next_track()
        self._set_status(f"{'Přidáno jako další' if play_next else 'Přidáno do fronty'} · {len(tracks)} skladeb")
        return True

    @Slot()
    def stopPlayback(self):
        """Keep queue/selection and repeat, but Play starts this track at zero."""
        self._radio_refill_revision += 1
        self._radio_waiting_for_tracks = None
        stream = self._active_queue_stream()
        if stream:
            stream["waiting"] = False
        if self._closing.is_set() or self._local_output is None or not self.playerHasTrack:
            return
        with self._transport_lock:
            self._playback_generation += 1
            self._prefetch_revision += 1
            self._playback_transitioning = False
            self._player_state = "idle"
            self._player_position = 0.0
            if self._prefetch_future is not None:
                self._prefetch_future.cancel()
            try:
                self._local_output.media_controller.stop(keep_output=True)
            except Exception as exc:
                self.playerChanged.emit()
                self.errorOccurred.emit(f"Zastavení přehrávání selhalo: {exc}")
                return
        if self._queue.current().get("_guiRemoveAfterPlayback"):
            self._prune_removed_queue_tracks(drop_current=True)
            self._set_player_from_queue()
        self._set_status("Přehrávání zastaveno")
        self.playerChanged.emit()

    @Slot()
    def togglePlayPause(self):
        if self._local_output is None or self._queue is None or self._queue.empty():
            return
        if self._playback_transitioning:
            return
        mc = self._local_output.media_controller
        try:
            if self._player_state == "playing":
                mc.pause()
                self._set_player_state("paused")
            elif self._player_state == "paused":
                mc.play()
                self._set_player_state("playing")
            else:
                self._start_current_async(direction=1)
        except Exception as exc:
            self.errorOccurred.emit(f"Ovládání přehrávače selhalo: {exc}")

    @Slot()
    def nextTrack(self):
        if self._queue is None or self._playback_transitioning:
            return
        if self._queue.current() and self._queue.current().get("_guiRemoveAfterPlayback"):
            self._leave_removed_current(1, stop_current=True)
            return
        moved = self._queue.next()
        if not moved and self._repeat_mode == "all" and not self._queue.empty() and not self.playerQueueLoading:
            self._queue.index = 0
            moved = True
        if moved:
            self._set_player_from_queue()
            self._start_current_async(direction=1, stop_current=True)

    @Slot()
    def previousTrack(self):
        if self._queue is None or self._playback_transitioning:
            return
        if self._queue.current() and self._queue.current().get("_guiRemoveAfterPlayback"):
            self._leave_removed_current(-1, stop_current=True)
            return
        moved = self._queue.previous()
        if not moved and self._repeat_mode == "all" and not self._queue.empty() and not self.playerQueueLoading:
            self._queue.index = self._queue.count() - 1
            moved = True
        if moved:
            self._set_player_from_queue()
            self._start_current_async(direction=-1, stop_current=True)

    def _seek_to(self, seconds):
        if not self.playerCanSeek or self._local_output is None:
            return

        target = max(0.0, float(seconds))
        if self._player_duration > 0.0:
            # Avoid seeking beyond EOS; GStreamer handles the exact end
            # inconsistently across demuxers.
            target = min(target, max(0.0, self._player_duration - 0.05))

        try:
            self._local_output.media_controller.seek(target, timeout=3)
            self._player_position = target
            self.playerChanged.emit()
        except Exception as exc:
            self.errorOccurred.emit(f"Posun ve skladbě selhal: {exc}")

    @Slot(float)
    def seekTo(self, seconds):
        self._seek_to(seconds)

    @Slot(float)
    def seekRelative(self, delta):
        if not self.playerCanSeek or self._local_output is None:
            return

        current = self._player_position
        try:
            status = self._local_output.media_controller.status
            current = max(0.0, float(status.adjusted_current_time or current))
        except Exception:
            pass

        self._seek_to(current + float(delta))

    @Slot(int)
    def setVolume(self, percent):
        if self._local_output is None:
            return

        percent = max(0, min(100, int(percent)))
        try:
            level = self._local_output.set_volume(percent / 100.0)
            self._player_volume = int(round(float(level) * 100))
            self.playerChanged.emit()
        except Exception as exc:
            self.errorOccurred.emit(f"Nastavení hlasitosti selhalo: {exc}")

    @Slot(int)
    def changeVolume(self, delta):
        self.setVolume(self._player_volume + int(delta))

    @Slot()
    def toggleMute(self):
        if self._local_output is None:
            return

        try:
            self._player_muted = bool(
                self._local_output.set_volume_muted(not self._player_muted)
            )
            self.playerChanged.emit()
        except Exception as exc:
            self.errorOccurred.emit(f"Mute selhalo: {exc}")

    # ------------------------------------------------------------------
    # Worker plumbing
    # ------------------------------------------------------------------

    def _set_busy(self, value: bool):
        value = bool(value)
        if self._busy == value:
            return
        self._busy = value
        self.busyChanged.emit()

    def _set_status(self, value: str):
        if self._status == value:
            return
        self._status = value
        self.statusChanged.emit()

    def _set_connected(self, value: bool):
        value = bool(value)
        if self._connected == value:
            return
        self._connected = value
        self.connectedChanged.emit()

    def _submit(self, name: str, status: str, fn):
        if self._busy:
            return

        self._set_busy(True)
        self._set_status(status)

        def work():
            try:
                result = fn()
            except Exception as exc:  # keep API failures out of QML
                trace = current_trace()
                if trace:
                    trace.event("api.error", error=type(exc).__name__)
                self._errorReady.emit(
                    name,
                    f"{type(exc).__name__}: {exc}",
                )
                return
            self._resultReady.emit(name, result)

        self._executor.submit(work, _diagnostic_label=f"api.{name}")

    @Slot(str, object)
    def _apply_result(self, name: str, result: Any):
        emit_initialized = False
        emit_song_library_changed = False
        emit_playlist_save_requested = False
        emit_playlist_edit_requested = False
        emit_playlist_delete_requested = False
        deleted_playlist = None
        changed_playlist_id = ""
        try:
            if name == "liked_first_page":
                self._apply_liked_page(result)

            elif name == "liked_playback":
                self._apply_liked_playback(result)

            elif name == "collection_radio":
                self._apply_collection_radio(result)

            elif name == "artist_playback":
                self._apply_artist_playback(result)

            elif name == "shuffle_queue":
                self._apply_queue_shuffle(result)

            elif name == "shuffle_detail":
                self._apply_detail_shuffle(result)

            elif name == "initialize":
                self._ytmusic = result["ytmusic"]
                self._library_probe_headers = dict(result.get("auth_headers") or {})
                account = result.get("account") or {}
                new_name = account.get("accountName") or "YouTube Music"
                if new_name != self._account_name:
                    self._account_name = new_name
                    self.accountNameChanged.emit()
                self._set_connected(True)
                self._set_status(f"Připojeno · {self._account_name}")
                emit_initialized = True

            elif name == "playlist_delete_read":
                self._playlist_delete_verification = None
                self._playlist_delete_state = result
                self.playlistDeleteChanged.emit()
                emit_playlist_delete_requested = True
                self._set_status("Potvrď smazání playlistu")

            elif name in ("playlist_delete_write", "playlist_delete_recheck"):
                self._playlist_delete_verification = result.get("verification")
                self._playlist_delete_state = dict(self._playlist_delete_state,
                    **{key: value for key, value in result.items() if key != "verification"}, pending=False)
                state = self._playlist_delete_state
                if state.get("completed"):
                    playlist_id = state["playlistId"]
                    deleted_playlist = (playlist_id, self._forget_deleted_playlist(playlist_id))
                self.playlistDeleteChanged.emit()
                self._set_status(state["message"])

            elif name == "playlist_move_item":
                if result["ok"]:
                    playlist_id = result["playlistId"]
                    self._pending_playlist_moves.setdefault(playlist_id, []).append({
                        "move": result["move"], "order": result["moveOrder"]})
                    detail = result["detail"]
                    if self._detail_meta.get("playlistId") == playlist_id:
                        old = self._detail_tracks_model.snapshot()
                        source = next((i for i, x in enumerate(old) if x.get("setVideoId") == result["move"][0]), -1)
                        target = next((i for i, x in enumerate(detail["tracks"]) if x.get("setVideoId") == result["move"][0]), -1)
                        expected = list(old)
                        if source >= 0 and target >= 0:
                            expected.insert(target, expected.pop(source))
                        if source >= 0 and target >= 0 and expected == detail["tracks"]:
                            self._detail_tracks_model.move_item(source, target)
                        else:
                            self._detail_tracks_model.set_items(detail["tracks"])
                        self._detail_title = detail["title"]
                        self._detail_meta = detail["meta"]
                        self.detailTitleChanged.emit()
                    self._update_playlist_browse_snapshots(detail)
                    self._sync_playlist_queue_order(detail)
                else:
                    self.errorOccurred.emit(result["message"])
                self._set_status(result["message"])

            elif name == "playlist_remove_item":
                if result["ok"]:
                    playlist_id = result["playlistId"]
                    self._pending_removed_playlist_items.setdefault(playlist_id, set()).add(result["setVideoId"])
                    detail = result["detail"]
                    removed = self._pending_removed_playlist_items[playlist_id]
                    detail["tracks"] = [x for x in detail["tracks"] if x.get("setVideoId") not in removed]
                    if self._detail_meta.get("playlistId") == playlist_id:
                        self._detail_title = detail["title"]
                        self._detail_meta = detail["meta"]
                        old = self._detail_tracks_model.snapshot()
                        remaining = [x for x in old if x.get("setVideoId") not in removed]
                        if remaining == detail["tracks"]:
                            for i in range(len(old) - 1, -1, -1):
                                if old[i].get("setVideoId") in removed:
                                    self._detail_tracks_model.remove_item(i)
                        else:
                            self._detail_tracks_model.set_items(detail["tracks"])
                        self.detailTitleChanged.emit()
                    card = result["card"]
                    for model in (self._library_items_model, self._playlists_model):
                        cards = model.snapshot()
                        if any(x.get("playlistId") == playlist_id for x in cards):
                            model.set_items([dict(card) if x.get("playlistId") == playlist_id else x for x in cards])
                    if playlist_id in self._pending_created_playlists:
                        self._pending_created_playlists[playlist_id] = card
                    self._update_playlist_browse_snapshots(detail)
                    self._sync_removed_playlist_queue_item(playlist_id, result["setVideoId"])
                else:
                    self.errorOccurred.emit(result["message"])
                self._set_status(result["message"])

            elif name == "playlist_edit_read":
                self._playlist_edit_state = result
                self.playlistEditChanged.emit()
                emit_playlist_edit_requested = True
                self._set_status("Údaje playlistu načteny")

            elif name == "playlist_edit_write":
                self._playlist_edit_state = dict(self._playlist_edit_state, **result, pending=False)
                state = self._playlist_edit_state
                if state.get("completed"):
                    playlist_id = state["playlistId"]
                    if self._detail_meta.get("playlistId") == playlist_id:
                        self._detail_title = state["title"]
                        self._detail_meta = dict(self._detail_meta, description=state["description"], privacy=state["privacy"])
                        self.detailTitleChanged.emit()
                    for model in (self._library_items_model, self._playlists_model):
                        cards = model.snapshot()
                        for card in cards:
                            if card.get("playlistId") == playlist_id:
                                card["title"] = state["title"]
                                card["subtitle"] = state["description"]
                        model.set_items(self._sort_normalized(cards, self._library_order) if model is self._library_items_model else cards)
                    if playlist_id in self._pending_created_playlists:
                        self._pending_created_playlists[playlist_id].update(title=state["title"], subtitle=state["description"])
                self.playlistEditChanged.emit()
                self._set_status(state["message"])

            elif name == "playlist_create_empty":
                self._empty_playlist_state = result
                self.emptyPlaylistChanged.emit()
                self._set_status(result["message"])
                if result.get("completed"):
                    changed_playlist_id = result["playlistId"]
                    self._pending_created_playlists[changed_playlist_id] = self._playlist({
                        "playlistId": changed_playlist_id, "title": result["title"],
                        "count": 0, "owned": True,
                    })

            elif name == "playlist_save_choices":
                self._playlist_save_state = dict(self._playlist_save_state, targets=result, pending=False)
                self.playlistSaveChanged.emit()
                emit_playlist_save_requested = True
                self._set_status("Vlastní playlisty načteny")

            elif name in ("playlist_save_write", "playlist_save_recheck"):
                self._playlist_save_verification = result.get("verification")
                self._playlist_save_state = dict(self._playlist_save_state,
                    **{key: value for key, value in result.items() if key not in ("detail", "verification")}, pending=False)
                if (result.get("completed") and result.get("verified")
                        and self._playlist_save_selection == self._selection_revision):
                    self.clearTrackSelection()
                self.playlistSaveChanged.emit()
                self._set_status(result["message"])
                if result.get("changed"):
                    changed_playlist_id = result["playlistId"]
                    if result.get("detail") is not None and self._detail_meta.get("playlistId") == changed_playlist_id:
                        self._detail_tracks_model.set_items([self._track(x) for x in core.usable_tracks(result["detail"].get("tracks", []))])
                        self.detailTitleChanged.emit()

            elif name == "song_library_action":
                self._song_library_action_pending = False
                state = result["inLibrary"]
                if result["requestId"] == self._library_probe_generation:
                    self._song_library_token = result["token"]
                    self._song_library_menu = dict(self._song_library_menu, pending=False,
                        available=True, inLibrary=state, message="")
                    self.songLibraryMenuChanged.emit()
                self._update_song_library_snapshots(result["item"], state)
                emit_song_library_changed = True
                self._set_status("Přidáno do knihovny" if state else "Odebráno z knihovny")

            elif name == "radio":
                self._apply_radio(result)

            elif name == "mixes":
                self._mixes_model.set_items(result)
                self._set_status(f"Mixy pro vás · {len(result)}")

            elif name == "liked":
                self._liked_default_items = list(result or [])
                visible_items = self._sort_normalized(
                    self._liked_default_items,
                    self._liked_order,
                )
                self._liked_model.set_items(visible_items)
                label = {
                    "a_to_z": "A–Z",
                    "z_to_a": "Z–A",
                }.get(self._liked_order, "Výchozí YTM")
                self._set_status(
                    f"Oblíbená hudba · {len(visible_items)} skladeb · {label}"
                )

            elif name == "history":
                self._history_model.set_items(result)
                self._set_status(f"Historie · {len(result)} položek")

            elif name == "playlists":
                result = [x for x in result if x.get("playlistId") not in self._deleted_playlists]
                self._playlists_model.set_items(result)
                self._set_status(f"Playlisty · {len(result)}")

            elif name.startswith("library:"):
                if name == "library:playlists":
                    result = [x for x in result if x.get("playlistId") not in self._deleted_playlists]
                    received_ids = {item.get("playlistId") for item in result}
                    for playlist_id in received_ids:
                        self._pending_created_playlists.pop(playlist_id, None)
                    result = self._sort_normalized(
                        list(reversed(list(self._pending_created_playlists.values()))) + list(result),
                        self._library_order,
                    )
                self._library_items_model.set_items(result)
                label = {
                    "library:playlists": "Playlisty",
                    "library:songs": "Skladby",
                    "library:albums": "Alba",
                    "library:artists": "Interpreti",
                    "library:channels": "Profily",
                    "library:podcasts": "Podcasty",
                    "library:upload_songs": "Nahrané skladby",
                    "library:upload_albums": "Nahraná alba",
                    "library:upload_artists": "Nahraní interpreti",
                }.get(name, "Knihovna")
                self._set_status(f"{label} · {len(result)}")

            elif name == "search":
                result = [x for x in result if x.get("kind") != "playlist" or x.get("playlistId") not in self._deleted_playlists]
                self._search_results_model.set_items(result)
                self._set_status(f"Výsledků hledání · {len(result)}")

            elif name == "detail":
                playlist_id = result.get("meta", {}).get("playlistId")
                if playlist_id and "playlistOccurrenceIds" in result:
                    if result.get("playlistMovesCaughtUp"):
                        self._pending_playlist_moves.pop(playlist_id, None)
                    pending = self._pending_removed_playlist_items.get(playlist_id, set())
                    pending.intersection_update(result["playlistOccurrenceIds"])
                    if pending:
                        result["tracks"] = [x for x in result["tracks"] if x.get("setVideoId") not in pending]
                    else:
                        self._pending_removed_playlist_items.pop(playlist_id, None)
                    self._update_playlist_browse_snapshots(result)
                if self._pending_detail_parent is not None:
                    self._detail_history.append(self._pending_detail_parent)
                    self._pending_detail_parent = None
                title = result.get("title") or "Fronta"
                tracks = result.get("tracks") or []
                self._detail_title = title
                self._detail_meta = result.get("meta") or {}
                self._detail_tracks_model.set_items(tracks)
                self.detailTitleChanged.emit()
                label = "položek" if self._detail_meta.get("section") in ("albums", "singles") else "skladeb"
                self._set_status(f"{title} · {len(tracks)} {label}")

        finally:
            # initialized is deliberately emitted only after busy=False so the
            # QML side can immediately request its initial page.
            self._set_busy(False)

        if emit_initialized:
            self.initialized.emit()
        if emit_song_library_changed:
            self.songLibraryChanged.emit()
        if emit_playlist_save_requested:
            self.playlistSaveRequested.emit()
        if emit_playlist_edit_requested:
            self.playlistEditRequested.emit()
        if emit_playlist_delete_requested:
            self.playlistDeleteRequested.emit()
        if deleted_playlist:
            self.playlistDeleted.emit(*deleted_playlist)
        if changed_playlist_id:
            self.playlistsChanged.emit(changed_playlist_id)

    @Slot(str, str)
    def _apply_error(self, name: str, message: str):
        if name.startswith("playlist_save_"):
            message = ("Playlisty se nepodařilo načíst. Zkus to prosím znovu."
                       if name == "playlist_save_choices" else
                       "Operaci se nepodařilo dokončit. Zkontroluj stav playlistu ve webovém YTM.")
            self._playlist_save_state = dict(self._playlist_save_state, pending=False, error=True, message=message)
            self.playlistSaveChanged.emit()
        if name == "song_library_action":
            self._song_library_action_pending = False
            self._song_library_token = ""
            self._song_library_menu = dict(self._song_library_menu, pending=False,
                                           available=False, message=message)
            self.songLibraryMenuChanged.emit()
            self._set_busy(False)
            self._set_status("Změnu knihovny se nepodařilo uložit nebo ověřit")
            self.errorOccurred.emit(message)
            return
        if name == "detail":
            self._pending_detail_parent = None
        self._set_busy(False)
        if name == "initialize":
            self._ytmusic = None
            self._set_connected(False)
            self._set_status("Backend nepřipojen")
            message = (
                message
                + "\n\nGUI používá existující ~/.config/felismusic session. "
                  "Pokud session chybí nebo expirovala, obnov přihlášení v samostatném FelisMusic CLI 1.0.0."
            )
        else:
            self._set_status("Chyba při načítání")
        self.errorOccurred.emit(message)

    def _require_ytmusic(self):
        if self._ytmusic is None:
            raise RuntimeError("YouTube Music backend ještě není připojený.")
        return self._ytmusic

    # ------------------------------------------------------------------
    # Data normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _is_upload(item):
        kind = str(item.get("kind") or item.get("resultType") or "")
        if item.get("entityId") or kind.startswith("upload_"):
            return True
        album = item.get("album")
        album_id = album.get("id") if isinstance(album, dict) else ""
        artists = item.get("artists") or []
        artist_ids = [x.get("id") for x in artists if isinstance(x, dict)]
        return any(
            "privately_owned" in str(value or "")
            for value in [item.get("browseId"), album_id, *artist_ids]
        )

    @classmethod
    def _thumbnail(cls, item, allow_video_fallback=True):
        thumbs = item.get("thumbnails") or item.get("thumbnail") or []

        # Některé endpointy vrátí thumbnail rovnou jako URL.
        if isinstance(thumbs, str):
            if thumbs.strip():
                return thumbs.strip()
            thumbs = []

        if isinstance(thumbs, dict):
            thumbs = [thumbs]
        if isinstance(thumbs, list):
            for thumb in reversed(thumbs):
                if isinstance(thumb, dict) and thumb.get("url"):
                    return str(thumb["url"])
                if isinstance(thumb, str) and thumb.strip():
                    return thumb.strip()

        # YT Music občas v knihovním endpointu obrázek skladby vynechá,
        # přestože web ho zná. Pro běžné YouTube videoId lze bezpečně
        # použít standardní ytimg náhled jako fallback.
        video_id = str(item.get("videoId") or "").strip()
        if video_id and allow_video_fallback and not cls._is_upload(item):
            return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

        return ""

    @staticmethod
    def _artists(item):
        artists = item.get("artists") or item.get("artist") or []
        if isinstance(artists, dict):
            artists = [artists]
        if isinstance(artists, str):
            return artists
        values = []
        for artist in artists:
            if isinstance(artist, dict):
                name = artist.get("name")
            else:
                name = str(artist)
            if name:
                values.append(str(name))
        return ", ".join(values)

    @staticmethod
    def _album(item):
        album = item.get("album")
        if isinstance(album, dict):
            return str(album.get("name") or "")
        return str(album or "")

    @classmethod
    def _track(cls, item, upload=False, album_thumbnail="", album_id=""):
        upload = upload or cls._is_upload(item)
        artists = cls._artists(item)
        album = cls._album(item)
        raw_album = item.get("album")
        album_id = ((raw_album.get("id") if isinstance(raw_album, dict) else "")
                    or item.get("albumId") or album_id)
        duration = item.get("duration") or ""
        # Search/library payloads are not fully uniform.  Some rows contain
        # only duration_seconds even though the web UI can show a duration.
        if not duration:
            seconds = core.song_duration_seconds(item)
            if seconds:
                duration = core.format_seconds(seconds)
        subtitle_parts = [x for x in (artists, album) if x]
        return {
            "kind": "upload_song" if upload else (item.get("resultType") or "song"),
            "title": str(item.get("title") or "Bez názvu"),
            "subtitle": " · ".join(subtitle_parts),
            "artists": artists,
            "album": album,
            "albumId": str(album_id or ""),
            "duration": str(duration),
            "videoId": str(item.get("videoId") or ""),
            "setVideoId": str(item.get("setVideoId") or ""),
            "playlistId": str(item.get("playlistId") or ""),
            "browseId": str(item.get("browseId") or ""),
            "thumbnail": (
                cls._thumbnail(item, allow_video_fallback=not upload) or album_thumbnail
            ),
            "likeStatus": (
                core.normalize_like_status(item.get("likeStatus"))
                if item.get("likeStatus") is not None
                else ""
            ),
        }

    @classmethod
    def _playlist(cls, item, kind="playlist"):
        count = item.get("count")
        description = item.get("description") or ""
        if isinstance(description, list):
            description = " · ".join(str(x) for x in description if x)
        subtitle = str(description).strip()
        if not subtitle and count not in (None, ""):
            subtitle = f"{count} skladeb"
        return {
            "kind": kind,
            "title": str(item.get("title") or "Bez názvu"),
            "subtitle": subtitle,
            "artists": "",
            "album": "",
            "duration": "",
            "videoId": "",
            "playlistId": str(core.playlist_id_from_item(item) or ""),
            "browseId": str(item.get("browseId") or ""),
            "thumbnail": cls._thumbnail(item),
        }

    @classmethod
    def _album_item(cls, item, kind="album"):
        artists = cls._artists(item)
        if not artists:
            artists = str(item.get("artist") or "")
        year = item.get("year")
        subtitle = " · ".join(x for x in (artists, str(year or "")) if x)
        return {
            "kind": kind,
            "title": str(item.get("title") or "Bez názvu"),
            "subtitle": subtitle,
            "year": str(year or ""),
            "artists": artists,
            "album": "",
            "duration": "",
            "videoId": "",
            "playlistId": str(item.get("audioPlaylistId") or ""),
            "browseId": str(item.get("browseId") or ""),
            "thumbnail": cls._thumbnail(item),
        }

    @classmethod
    def _artist_item(cls, item, kind="artist"):
        title = (
            item.get("artist")
            or item.get("name")
            or item.get("title")
            or "Bez názvu"
        )
        subtitle = str(item.get("subscribers") or "")
        return {
            "kind": kind,
            "title": str(title),
            "subtitle": subtitle,
            "artists": "",
            "album": "",
            "duration": "",
            "videoId": "",
            "playlistId": "",
            "browseId": str(item.get("browseId") or ""),
            "thumbnail": cls._thumbnail(item),
        }

    @classmethod
    def _podcast_item(cls, item):
        channel = item.get("channel") or {}
        if isinstance(channel, dict):
            subtitle = str(channel.get("name") or "")
        else:
            subtitle = str(channel or "")
        return {
            "kind": "podcast",
            "title": str(item.get("title") or "Bez názvu"),
            "subtitle": subtitle,
            "artists": "",
            "album": "",
            "duration": "",
            "videoId": "",
            "playlistId": str(core.podcast_id_from_item(item) or ""),
            "browseId": str(item.get("browseId") or ""),
            "thumbnail": cls._thumbnail(item),
        }

    @classmethod
    def _search_item(cls, item, forced_type=""):
        forced_type = str(forced_type or "").strip().lower()
        result_type = str(item.get("resultType") or "").strip().lower()
        browse_id = str(item.get("browseId") or "")

        # Upload search často nevrací resultType, ale privátní browseId je
        # jednoznačné. Normalizujeme ho ještě před obecnou kategorií, aby
        # šel výsledek opravdu otevřít.
        if "privately_owned_release_detail" in browse_id:
            return cls._album_item(item, "upload_album")
        if "privately_owned_artist_detail" in browse_id:
            return cls._artist_item(item, "upload_artist")

        # Přímý videoId je nejspolehlivější signál, že jde o přehratelnou
        # skladbu/video. U filtrového hledání navíc YTM někdy resultType
        # nevrátí, proto můžeme typ doplnit z filtru.
        if item.get("videoId"):
            result = cls._track(item)
            result["kind"] = forced_type or result_type or "song"
            return result

        if forced_type:
            result_type = forced_type
        elif not result_type:
            # `category` je u hledání Vše jen poslední záchrana; může být
            # lokalizovaná, takže ji nepoužíváme pro přímé skladby.
            result_type = str(item.get("category") or "").strip().lower()

        # Normalize known entity types with their dedicated mapper.  Search
        # artist rows commonly use the key `artist` rather than `title`; the
        # old generic mapper therefore displayed the misleading "Bez názvu".
        if result_type in ("album", "single", "ep"):
            result = cls._album_item(item, "album")
            result["kind"] = result_type
            return result
        if result_type == "artist":
            return cls._artist_item(item, "artist")
        if result_type == "playlist":
            return cls._playlist(item, "playlist")
        if result_type == "podcast":
            return cls._podcast_item(item)
        if result_type in ("channel", "profile"):
            result = cls._artist_item(item, "channel")
            result["kind"] = result_type
            return result

        title = str(
            item.get("title")
            or item.get("name")
            or item.get("artist")
            or "Bez názvu"
        )
        subtitle = cls._artists(item)
        if not subtitle:
            subtitle = str(item.get("category") or result_type or "")

        return {
            "kind": result_type or "item",
            "title": title,
            "subtitle": subtitle,
            "artists": "",
            "album": "",
            "duration": "",
            "playlistId": str(core.playlist_id_from_item(item) or ""),
            "browseId": str(item.get("browseId") or ""),
            "videoId": str(item.get("videoId") or ""),
            "setVideoId": str(item.get("setVideoId") or ""),
            "thumbnail": cls._thumbnail(item),
            "likeStatus": "",
        }

    @staticmethod
    def _search_item_actionable(item):
        """True only for search rows the GUI can actually use.

        YT Music's default search can contain a visually useful "Top result"
        without the navigation ID needed to open it. Such rows are omitted
        rather than displayed as dead/non-clickable information.
        """
        if str(item.get("videoId") or ""):
            return True

        kind = str(item.get("kind") or "").strip().lower()
        browse_id = str(item.get("browseId") or "")
        playlist_id = str(item.get("playlistId") or "")

        if kind in (
            "album", "single", "ep", "artist", "channel", "profile",
            "upload_album", "upload_artist",
        ):
            return bool(browse_id)
        if kind in ("playlist", "podcast"):
            return bool(playlist_id or browse_id)

        # openSearchResult umí jako poslední záchranu otevřít playlistId i
        # tehdy, když parser nedodal resultType.
        return bool(playlist_id)

    @staticmethod
    def _sort_normalized(items, order):
        """Sort already-normalized GUI items without changing YTM data.

        ``a_to_z`` and ``z_to_a`` are intentionally local sorts.  Every other
        value preserves the order returned by YouTube Music.
        """

        result = list(items or [])

        if order not in ("a_to_z", "z_to_a"):
            return result

        result.sort(
            key=lambda item: (
                str(item.get("title") or "").casefold(),
                str(item.get("subtitle") or "").casefold(),
            ),
            reverse=(order == "z_to_a"),
        )
        return result

    # ------------------------------------------------------------------
    # Public slots called by QML
    # ------------------------------------------------------------------

    @Slot()
    def initialize(self):
        def task():
            # Deliberately non-interactive. Existing CLI auth is reused.
            headers = core.AUTH.ytmusic_headers()
            ytmusic = instrument_ytmusic(YTMusic(headers))
            ytmusic.get_library_playlists(limit=1)
            account = {"accountName": "YouTube Music"}
            try:
                info = ytmusic.get_account_info()
                if info:
                    account.update(info)
            except Exception:
                pass
            return {"ytmusic": ytmusic, "account": account, "auth_headers": headers}

        self._submit("initialize", "Připojuji k YouTube Music…", task)

    @Slot()
    def loadMixes(self):
        def task():
            ytmusic = self._require_ytmusic()
            home = ytmusic.get_home(limit=core.HOME_MIX_ROWS)
            mixes = []
            seen = set()
            for section in home or []:
                for item in section.get("contents") or []:
                    if not core.is_personalized_mix_item(item):
                        continue
                    playlist_id = core.playlist_id_from_item(item)
                    if not playlist_id or playlist_id in seen:
                        continue
                    seen.add(playlist_id)
                    normalized = self._playlist(item, "mix")
                    normalized["playlistId"] = playlist_id
                    mixes.append(normalized)
            return mixes

        self._submit("mixes", "Načítám mixy pro vás…", task)

    @Property(bool, notify=likedLoadChanged)
    def likedLoading(self):
        return self._liked_load_state == "loading"

    @Property(bool, notify=likedLoadChanged)
    def likedComplete(self):
        return self._liked_load_state == "complete"

    @Slot()
    def loadLiked(self):
        if self._busy or self._closing.is_set() or self._ytmusic is None:
            return
        if self._liked_stream and self._liked_stream["state"] == "loading":
            self._liked_stream.update(state="error", waiting=False)
            self.playerChanged.emit()
        self._liked_load_revision += 1
        revision = self._liked_load_revision
        pager = PlaylistPages(self._require_ytmusic(), "LM", liked=True)
        self._liked_load_state = "loading"
        self.clearTrackSelection()
        self.likedLoadChanged.emit()
        self._submit("liked_first_page", "Načítám oblíbenou hudbu…",
                     lambda: self._read_liked_page(pager, revision, first=True))

    def _read_liked_page(self, pager, revision, first=False):
        result = {"pager": pager, "revision": revision, "first": first}
        if self._closing.is_set() or revision != self._liked_load_revision:
            return dict(result, stale=True)
        try:
            tracks, more = pager.next_page()
            items = []
            for item in core.usable_tracks(tracks):
                normalized = self._track(item)
                if not normalized.get("likeStatus"):
                    normalized["likeStatus"] = "LIKE"
                items.append(normalized)
            result.update(items=items, more=more)
        except Exception as exc:
            result["error"] = type(exc).__name__
            trace = current_trace()
            if trace:
                trace.event("api.error", error=type(exc).__name__)
        return result

    @Slot(object)
    def _apply_liked_page(self, result):
        if (self._closing.is_set() or result["revision"] != self._liked_load_revision
                or result.get("stale")):
            return
        if result.get("error"):
            if result["first"]:
                self._set_status("Oblíbenou hudbu se nepodařilo načíst")
            self._liked_load_state = "error"
            self._fail_liked_queue(result["revision"])
            self.likedLoadChanged.emit()
            # Local page state, not a modal/global busy change. The loaded
            # prefix remains visible but cannot masquerade as the full list.
            return
        if result["first"]:
            self._set_status("Oblíbená hudba · první blok načten")
            self._liked_default_items = list(result["items"])
            self._liked_model.set_items(self._liked_default_items)
        else:
            self._liked_default_items.extend(result["items"])
            self._liked_model.append_items(result["items"])
        if result["more"]:
            revision, pager = result["revision"], result["pager"]
            def submit_page():
                if self._closing.is_set() or revision != self._liked_load_revision:
                    return
                def work():
                    self._likedPageReady.emit(self._read_liked_page(pager, revision))
                self._executor.submit(work, _diagnostic_label="api.liked_page")
            # Yield to the UI and pending user API work between each page.
            QTimer.singleShot(0, submit_page)
        else:
            if self._liked_order:
                self._liked_model.set_items(self._sort_normalized(
                    self._liked_default_items, self._liked_order))
            self._liked_load_state = "complete"
            self._invalidate_selection("liked")
        if not result["first"]:
            self._extend_liked_queue(result["items"], result["revision"], result["more"])
        self.likedLoadChanged.emit()

    def _fail_liked_queue(self, revision):
        stream = self._liked_stream
        if stream and stream["queue"] is self._queue and stream["revision"] == revision:
            stream.update(state="error", waiting=False)
            self.playerChanged.emit()

    def _extend_liked_queue(self, items, revision, more):
        stream = self._liked_stream
        if (not stream or stream["queue"] is not self._queue
                or stream["revision"] != revision or stream["state"] != "loading"):
            return
        queue = self._queue
        previous_next = self._next_prefetch_id()
        start = len(stream["items"])
        stream["items"].extend(items)
        for index, item in enumerate(items, start):
            song = self._playback_track(item)
            song["_guiOrigin"] = dict(stream["origin"], index=index)
            queue.tracks.append(song)
            stream["bound"].append((song, index))
            self._queue_source_indices.append(index)
        self._playing_tracks_model.append_items(items)
        # The queue keeps the original YTM order. Its browsing snapshot can
        # acquire the requested global sort only once the full list is known.
        rows = list(range(len(stream["items"])))
        order = stream["origin"]["liked_order"] if not more else ""
        if order in ("a_to_z", "z_to_a"):
            rows.sort(key=lambda i: (str(stream["items"][i].get("title") or "").casefold(),
                                     str(stream["items"][i].get("subtitle") or "").casefold()),
                      reverse=order == "z_to_a")
        mapping = {old: new for new, old in enumerate(rows)}
        stream["origin"]["snapshots"]["liked"] = [stream["items"][i] for i in rows]
        for song, index in stream["bound"]:
            song["_guiOrigin"]["index"] = mapping[index]
        self._after_stream_append(stream, previous_next, more)

    def _after_stream_append(self, stream, previous_next, more):
        queue = stream["queue"]
        was_waiting = stream["waiting"] and self._player_state == "idle"
        if not more:
            stream.update(state="complete", waiting=False)
        self.playerChanged.emit()
        if was_waiting:
            if queue.next():
                self._set_player_from_queue()
                self._start_current_async(direction=1)
            elif not more and self._repeat_mode == "all":
                queue.index = 0
                self._set_player_from_queue()
                self._start_current_async(direction=1)
            return
        if previous_next != self._next_prefetch_id():
            self._prefetch_revision += 1
            if self._prefetch_future is not None:
                self._prefetch_future.cancel()
            if self._player_state in ("playing", "paused") and not self._playback_transitioning:
                self._prefetch_next_track()

    @Slot(str)
    def sortLiked(self, order):
        if not self.likedComplete:
            return
        order = (order or "").strip()
        self._liked_order = order
        if not self._liked_default_items:
            return

        items = self._sort_normalized(
            self._liked_default_items,
            order,
        )
        self._liked_model.set_items(items)
        label = {
            "a_to_z": "A–Z",
            "z_to_a": "Z–A",
        }.get(order, "Výchozí YTM")
        self._set_status(
            f"Oblíbená hudba · {len(items)} skladeb · {label}"
        )

    @Slot()
    def loadHistory(self):
        def task():
            tracks = core.usable_tracks(self._require_ytmusic().get_history() or [])
            return [self._track(x) for x in tracks]

        self._submit("history", "Načítám historii…", task)

    @Slot(str, str)
    def loadLibrarySection(self, section, order):
        section = (section or "playlists").strip()
        order = (order or "").strip() or None

        labels = {
            "playlists": "playlisty",
            "songs": "skladby",
            "albums": "alba",
            "artists": "interprety",
            "channels": "profily",
            "podcasts": "podcasty",
            "upload_songs": "nahrané skladby",
            "upload_albums": "nahraná alba",
            "upload_artists": "nahrané interprety",
        }
        if section not in labels:
            return

        def task():
            ytmusic = self._require_ytmusic()

            if section == "playlists":
                items = ytmusic.get_library_playlists(limit=500) or []
                normalized = [self._playlist(x) for x in items]
                return self._sort_normalized(normalized, order)

            if section == "songs":
                items = ytmusic.get_library_songs(
                    limit=core.LIBRARY_LIMIT,
                    order=order,
                ) or []
                items = core.usable_tracks(items)
                return [self._track(x) for x in items]

            if section == "albums":
                items = ytmusic.get_library_albums(
                    limit=core.LIBRARY_LIMIT,
                    order=order,
                ) or []
                return [self._album_item(x) for x in items]

            if section == "artists":
                items = ytmusic.get_library_artists(
                    limit=core.LIBRARY_LIMIT,
                    order=order,
                ) or []
                return [self._artist_item(x) for x in items]

            if section == "channels":
                items = ytmusic.get_library_channels(
                    limit=core.LIBRARY_LIMIT,
                    order=order,
                ) or []
                return [self._artist_item(x, "channel") for x in items]

            if section == "podcasts":
                items = ytmusic.get_library_podcasts(
                    limit=core.LIBRARY_LIMIT,
                    order=order,
                ) or []
                return [self._podcast_item(x) for x in items]

            if section == "upload_songs":
                items = ytmusic.get_library_upload_songs(
                    limit=None,
                    order=order,
                ) or []
                items = core.usable_tracks(items)
                return [self._track(x, upload=True) for x in items]

            if section == "upload_albums":
                items = ytmusic.get_library_upload_albums(
                    limit=None,
                    order=order,
                ) or []
                return [self._album_item(x, "upload_album") for x in items]

            items = ytmusic.get_library_upload_artists(
                limit=None,
                order=order,
            ) or []
            return [self._artist_item(x, "upload_artist") for x in items]

        if self._busy:
            return
        self._library_section = section
        self._library_order = order
        self._library_items_model.clear()
        self.clearDetail()
        self._submit(
            f"library:{section}",
            f"Načítám {labels[section]}…",
            task,
        )

    @Slot(str, str, str, str)
    def openLibraryItem(self, kind, browse_id, playlist_id, title):
        kind = (kind or "").strip()
        browse_id = (browse_id or "").strip()
        playlist_id = (playlist_id or "").strip()
        title = (title or "Knihovna").strip()

        if kind == "playlist":
            self.loadPlaylistTracks(playlist_id, title)
            return

        def task():
            ytmusic = self._require_ytmusic()
            tracks = []
            detail_title = title
            album_thumbnail = ""
            meta = {}

            if kind == "album":
                if not browse_id:
                    raise RuntimeError("Album nemá browseId.")
                data = ytmusic.get_album(browse_id)
                detail_title = data.get("title") or title
                tracks = core.usable_tracks(data.get("tracks") or [])
                meta = {"kind": "album", "browseId": browse_id,
                        "shufflePlaylistId": data.get("audioPlaylistId") or ""}

            elif kind == "artist":
                if not browse_id:
                    raise RuntimeError("Interpret nemá browseId.")
                data = ytmusic.get_artist(browse_id)
                detail_title = data.get("name") or title
                tracks = core.usable_tracks(
                    (data.get("songs") or {}).get("results") or []
                )
                sections = {"songs": [self._track(x) for x in tracks]}
                pointers = {}
                for section in ("songs", "albums", "singles"):
                    block = data.get(section) or {}
                    if section != "songs":
                        sections[section] = [self._album_item(x) for x in block.get("results", []) if x.get("browseId")]
                    if block.get("browseId") and (section == "songs" or block.get("params")):
                        pointers[section] = {key: block[key] for key in ("browseId", "params") if key in block}
                meta = {"kind": "artist", "section": "songs", "sections": sections,
                        "pointers": pointers, "orders": {}, "thumbnail": self._thumbnail(data),
                        "browseId": browse_id,
                        "radioId": data["radioId"].strip() if isinstance(data.get("radioId"), str) else "",
                        "shuffleId": data["shuffleId"].strip() if isinstance(data.get("shuffleId"), str) else ""}
                self._load_artist_section(ytmusic, meta, "songs")


            elif kind == "channel":
                if not browse_id:
                    raise RuntimeError("Profil nemá browseId.")
                data = ytmusic.get_channel(browse_id)
                detail_title = data.get("title") or title
                tracks = core.usable_tracks(
                    (data.get("episodes") or {}).get("results") or []
                )

            elif kind == "podcast":
                podcast_id = playlist_id or browse_id
                if not podcast_id:
                    raise RuntimeError("Podcast nemá podcastId.")
                data = ytmusic.get_podcast(podcast_id, limit=None)
                detail_title = data.get("title") or title
                tracks = core.usable_tracks(data.get("episodes") or [])

            elif kind == "upload_album":
                if not browse_id:
                    raise RuntimeError("Nahrané album nemá browseId.")
                data = ytmusic.get_library_upload_album(browse_id)
                detail_title = data.get("title") or title
                album_thumbnail = self._thumbnail(data, allow_video_fallback=False)
                tracks = core.usable_tracks(data.get("tracks") or [])

            elif kind == "upload_artist":
                if not browse_id:
                    raise RuntimeError("Nahraný interpret nemá browseId.")
                tracks = core.usable_tracks(
                    ytmusic.get_library_upload_artist(
                        browse_id,
                        limit=core.LIBRARY_LIMIT,
                    ) or []
                )

            else:
                raise RuntimeError(
                    f"Detail typu {kind or '?'} zatím není podporovaný."
                )

            return {
                "title": detail_title,
                "meta": meta,
                "tracks": self._artist_sorted_items(meta) if kind == "artist" else [
                    self._track(
                        x,
                        upload=kind.startswith("upload_"),
                        album_thumbnail=album_thumbnail,
                        album_id=browse_id if kind == "album" else "",
                    )
                    for x in tracks
                ],
            }

        self._submit("detail", f"Načítám: {title}", task)

    @Slot()
    def loadPlaylists(self):
        def task():
            playlists = self._require_ytmusic().get_library_playlists(limit=500) or []
            return [self._playlist(x) for x in playlists]

        self._submit("playlists", "Načítám playlisty…", task)

    @Slot(int)
    def openSearchResult(self, index):
        items = self._search_results_model.snapshot()
        if index < 0 or index >= len(items):
            return

        item = items[index]
        if item.get("videoId"):
            self.playFrom("search", index)
            return

        kind = str(item.get("kind") or "").strip().lower()
        browse_id = str(item.get("browseId") or "")
        playlist_id = str(item.get("playlistId") or "")
        title = str(item.get("title") or "Výsledek hledání")

        # Nahrané soubory někdy nepřijdou s resultType, ale jejich browseId
        # je jednoznačný.
        if "privately_owned_release_detail" in browse_id:
            kind = "upload_album"
        elif "privately_owned_artist_detail" in browse_id:
            kind = "upload_artist"

        mapped_kind = {
            "album": "album",
            "single": "album",
            "ep": "album",
            "artist": "artist",
            "playlist": "playlist",
            "podcast": "podcast",
            "channel": "channel",
            "profile": "channel",
            "upload_album": "upload_album",
            "upload_artist": "upload_artist",
        }.get(kind, kind)

        if mapped_kind in (
            "album", "artist", "playlist", "podcast", "channel",
            "upload_album", "upload_artist",
        ):
            self.openLibraryItem(
                mapped_kind,
                browse_id,
                playlist_id,
                title,
            )
            return

        # Některé search položky mají playlistId, ale resultType chybí.
        if playlist_id:
            self.loadPlaylistTracks(playlist_id, title)
            return

        self.errorOccurred.emit(
            f"Výsledek typu {kind or '?'} zatím neumím otevřít."
        )

    @Slot(str)
    @Slot(str, str)
    @Slot(str, str, str)
    def search(self, query, mode="all", scope="catalog"):
        query = (query or "").strip()
        mode = (mode or "all").strip().lower()
        scope = (scope or "catalog").strip().lower()
        if not query:
            return

        self.clearDetail()

        modes = {
            "all": (None, ""),
            "songs": ("songs", "song"),
            "videos": ("videos", "video"),
            "albums": ("albums", "album"),
            "artists": ("artists", "artist"),
            "playlists": ("playlists", "playlist"),
            "profiles": ("profiles", "profile"),
            "podcasts": ("podcasts", "podcast"),
            "episodes": ("episodes", "episode"),
        }
        search_filter, forced_type = modes.get(mode, modes["all"])

        scope_values = {
            "catalog": None,
            "library": "library",
            "uploads": "uploads",
        }
        search_scope = scope_values.get(scope, None)

        # ytmusicapi/YT Music uploads search nepovoluje současně filter.
        # UI tam typový výběr schovává, backend to ale vynutí také.
        if search_scope == "uploads":
            search_filter = None
            forced_type = ""

        scope_label = {
            "catalog": "YT Music",
            "library": "Knihovna",
            "uploads": "Nahrané soubory",
        }.get(scope, "YT Music")

        def task():
            kwargs = {"limit": core.SEARCH_LIMIT}
            if search_filter is not None:
                kwargs["filter"] = search_filter
            if search_scope is not None:
                kwargs["scope"] = search_scope
            results = self._require_ytmusic().search(query, **kwargs) or []
            normalized = [
                self._search_item(
                    dict(x, resultType="upload_song")
                    if search_scope == "uploads" and x.get("videoId") else x,
                    forced_type,
                )
                for x in results
            ]
            return [x for x in normalized if self._search_item_actionable(x)]

        self._submit(
            "search",
            f"Hledám · {scope_label}: {query}",
            task,
        )

    @Slot(str, str)
    def loadMixTracks(self, playlist_id, title):
        playlist_id = (playlist_id or "").strip()
        title = (title or "Mix pro vás").strip()
        if not playlist_id:
            return

        def task():
            data = self._require_ytmusic().get_watch_playlist(
                playlistId=playlist_id,
                limit=core.MIX_LIMIT,
            )
            tracks = core.usable_tracks(data.get("tracks") or [])
            return {
                "title": title,
                "tracks": [self._track(x) for x in tracks],
            }

        self._submit("detail", f"Načítám: {title}", task)

    @Slot(str, str)
    def loadPlaylistTracks(self, playlist_id, title):
        playlist_id = (playlist_id or "").strip()
        title = (title or "Playlist").strip()
        if not playlist_id or playlist_id in self._deleted_playlists:
            return

        pending_moves = list(self._pending_playlist_moves.get(playlist_id, []))
        def task():
            data = self._require_ytmusic().get_playlist(
                playlist_id,
                limit=None,
            )
            raw = data.get("tracks") or []
            projected = self._project_playlist_moves(raw, pending_moves)
            tracks = core.usable_tracks(projected)
            return {
                "playlistMovesCaughtUp": ([x.get("setVideoId") for x in raw] == [x.get("setVideoId") for x in projected]),
                "title": data.get("title") or title,
                "meta": {"kind": "playlist", "playlistId": playlist_id, "owned": data.get("owned") is True},
                "playlistOccurrenceIds": [x.get("setVideoId") for x in data.get("tracks") or []],
                "tracks": [self._track(x) for x in tracks],
            }

        self._submit("detail", f"Načítám: {title}", task)

    @Slot()
    def clearDetail(self):
        self._restore_detail_state({})

    @Slot()
    def shutdown(self):
        if self._closing.is_set():
            return
        self._closing.set()
        self._player_timer.stop()
        try:
            with self._transport_lock:
                self._playback_generation += 1
                if self._local_output is not None:
                    self._local_output.media_controller.stop()
        except Exception:
            pass
        self._library_probe_executor.shutdown(wait=False, cancel_futures=True)
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._playback_executor.shutdown(wait=False, cancel_futures=True)

        # Do not delete cache files while yt-dlp is still writing to them.
        # This waiter uses no Qt objects and never blocks the GUI thread.
        executor = self._playback_executor

        def cleanup_after_audio():
            executor.shutdown(wait=True, cancel_futures=True)
            try:
                core.cleanup_local_cache()
            except Exception:
                pass

        Thread(target=cleanup_after_audio, name="felismusic-cache-cleanup").start()
