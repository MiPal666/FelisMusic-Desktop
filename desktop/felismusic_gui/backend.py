from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock, Thread
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

from . import legacy_core as core


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

    _resultReady = Signal(str, object)
    _errorReady = Signal(str, str)
    _playbackReady = Signal(int)
    _playbackFailed = Signal(int, str)
    _ratingStatusReady = Signal(int, str, str)
    _ratingActionReady = Signal(int, str, str, str, str)

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
        self._ytmusic = None
        self._status = "Připravuji backend…"
        self._account_name = "YouTube Music"
        self._busy = False
        self._connected = False
        self._detail_title = ""

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

        # Original YT Music order for client-side re-sorting.
        # We keep the untouched baseline so switching back to
        # "Výchozí YTM" never requires another network request.
        self._liked_default_items = []
        self._liked_order = ""

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
        return self._queue_source

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
        queue_index = int(self._queue.index)
        if 0 <= queue_index < len(self._queue_source_indices):
            return int(self._queue_source_indices[queue_index])
        return -1

    @Property(bool, notify=playerChanged)
    def playerCanPrevious(self):
        return (
            self._queue is not None
            and not self._queue.empty()
            and (self._queue.index > 0 or self._repeat_mode == "all")
            and not self._playback_transitioning
        )

    @Property(bool, notify=playerChanged)
    def playerCanNext(self):
        return (
            self._queue is not None
            and not self._queue.empty()
            and (self._queue.index + 1 < self._queue.count() or self._repeat_mode == "all")
            and not self._playback_transitioning
        )

    @Property(bool, notify=playerChanged)
    def localPlaybackAvailable(self):
        return self._local_output is not None

    @Property(str, notify=detailTitleChanged)
    def detailTitle(self):
        return self._detail_title

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
            "album": ({"name": album} if album else None),
            "duration": str(item.get("duration") or ""),
            "videoId": str(item.get("videoId") or ""),
            "playlistId": str(item.get("playlistId") or ""),
            "browseId": str(item.get("browseId") or ""),
            "isAvailable": True,
            "likeStatus": (str(item.get("likeStatus") or "").upper() or None),
            "_guiSubtitle": str(item.get("subtitle") or ""),
            "_guiThumbnail": thumbnail,
        }
        return track

    def _source_model(self, source):
        models = {
            "library": self._library_items_model,
            "liked": self._liked_model,
            "history": self._history_model,
            "search": self._search_results_model,
            "detail": self._detail_tracks_model,
        }
        return models.get(source)

    def _source_items(self, source):
        model = self._source_model(source)
        return model.snapshot() if model is not None else []

    @Slot(int, result=bool)
    def restorePlayingSource(self, page):
        """Restore browsing data without rebuilding or restarting playback."""
        if not self.playerHasTrack or self._busy:
            return False
        sources = [self._queue_source]
        if self._queue_source == "detail":
            if page == 1:
                sources.append("library")
            elif page == 0:
                sources.append("search")
        for source in sources:
            model = self._source_model(source)
            if model is not None:
                model.set_items(self._playing_browse_snapshots.get(source, []))
        title = self._playing_detail_title if self._queue_source == "detail" else ""
        if title != self._detail_title:
            self._detail_title = title
            self.detailTitleChanged.emit()
        if self._queue_source != "detail":
            self._detail_tracks_model.clear()
        if self._queue_source == "liked":
            self._liked_order = self._playing_liked_order
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

    def _set_player_from_queue(self):
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

        for items in self._playing_browse_snapshots.values():
            for item in items:
                if str(item.get("videoId") or "") == video_id:
                    item["likeStatus"] = status

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
                song = queue.current()
                if song is None:
                    break
                try:
                    url, content_type = core.get_local_audio_source(
                        song["videoId"], cancelled=cancelled
                    )
                    artists = core.artist_names(song)
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
                    if not cancelled():
                        self._playbackReady.emit(generation)
                    return
                except Exception as exc:
                    if self._closing.is_set() or generation != self._playback_generation:
                        return
                    last_error = exc
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

        self._playback_executor.submit(work)

    def _prefetch_next_track(self):
        """Prepare just the next track, using the same serial audio worker.

        Playback and prefetch never write cookies/cache concurrently. If EOS
        arrives while prefetch is running, playback follows it and reuses the
        finished file through get_local_audio_source's normal cache lookup.
        """
        if self._closing.is_set() or self._queue is None or self._queue.empty():
            return
        if self._repeat_mode == "one":
            return  # The current track is already in the local cache.
        next_index = self._queue.index + 1
        if next_index >= self._queue.count():
            if self._repeat_mode != "all":
                return
            next_index = 0
        video_id = str(self._queue.tracks[next_index].get("videoId") or "")
        if not video_id:
            return
        generation = self._playback_generation
        revision = self._prefetch_revision

        def cancelled():
            # An automatic transition to this track can still use its download.
            return self._closing.is_set() or (
                (generation != self._playback_generation or revision != self._prefetch_revision)
                and self._current_video_id() != video_id
            )

        def work():
            if cancelled():
                return
            try:
                print(f"FelisMusic přednačítání: {video_id}")
                core.get_local_audio_source(video_id, cancelled=cancelled)
                if not cancelled():
                    print(f"FelisMusic přednačteno: {video_id}")
            except core.AudioPreparationCancelled:
                pass
            except Exception as exc:
                # Speculative failure must not affect playback or skip a row.
                # Normal playback will try this track again when it is needed.
                if not cancelled():
                    print(f"FelisMusic přednačítání selhalo ({video_id}): {type(exc).__name__}")

        self._prefetch_future = self._playback_executor.submit(work)

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
            advance = self._repeat_mode == "one"
            if not advance:
                advance = self._queue.next()
                if not advance and self._repeat_mode == "all":
                    self._queue.index = 0
                    advance = True
            if advance:
                self._set_player_from_queue()
                self._start_current_async(direction=1)
                return
            self._player_state = "idle"
            self._player_position = self._player_duration
            changed = True

        if changed:
            self.playerChanged.emit()

    @Slot(str, int)
    def playFrom(self, source, index):
        if source == "playing":
            # Select within the existing queue; do not rebuild it from a
            # browsing model which may already display something else.
            if self._queue is None or self._playback_transitioning:
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
            playable.append(self._playback_track(item))
            source_indices.append(original_index)

        if start_index is None or not playable:
            return

        self._queue_source = (source or "").strip()
        self._queue_source_indices = source_indices
        self._queue = core.PlaybackQueue(
            playable,
            name=self._queue_name_for_source(source),
            start_index=start_index,
        )
        self._playing_tracks_model.set_items([items[i] for i in source_indices])
        self._playing_browse_snapshots = {self._queue_source: items}
        if self._queue_source == "detail":
            for parent_source in ("library", "search"):
                self._playing_browse_snapshots[parent_source] = self._source_items(parent_source)
        self._playing_detail_title = self._detail_title
        self._playing_liked_order = self._liked_order
        self.playbackSourceCaptured.emit()
        self._set_player_from_queue()
        self._start_current_async(direction=1, stop_current=True)

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
        moved = self._queue.next()
        if not moved and self._repeat_mode == "all" and not self._queue.empty():
            self._queue.index = 0
            moved = True
        if moved:
            self._set_player_from_queue()
            self._start_current_async(direction=1, stop_current=True)

    @Slot()
    def previousTrack(self):
        if self._queue is None or self._playback_transitioning:
            return
        moved = self._queue.previous()
        if not moved and self._repeat_mode == "all" and not self._queue.empty():
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
                self._errorReady.emit(
                    name,
                    f"{type(exc).__name__}: {exc}",
                )
                return
            self._resultReady.emit(name, result)

        self._executor.submit(work)

    @Slot(str, object)
    def _apply_result(self, name: str, result: Any):
        emit_initialized = False
        try:
            if name == "initialize":
                self._ytmusic = result["ytmusic"]
                account = result.get("account") or {}
                new_name = account.get("accountName") or "YouTube Music"
                if new_name != self._account_name:
                    self._account_name = new_name
                    self.accountNameChanged.emit()
                self._set_connected(True)
                self._set_status(f"Připojeno · {self._account_name}")
                emit_initialized = True

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
                self._playlists_model.set_items(result)
                self._set_status(f"Playlisty · {len(result)}")

            elif name.startswith("library:"):
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
                self._search_results_model.set_items(result)
                self._set_status(f"Výsledků hledání · {len(result)}")

            elif name == "detail":
                title = result.get("title") or "Fronta"
                tracks = result.get("tracks") or []
                if title != self._detail_title:
                    self._detail_title = title
                    self.detailTitleChanged.emit()
                self._detail_tracks_model.set_items(tracks)
                self._set_status(f"{title} · {len(tracks)} skladeb")

        finally:
            # initialized is deliberately emitted only after busy=False so the
            # QML side can immediately request its initial page.
            self._set_busy(False)

        if emit_initialized:
            self.initialized.emit()

    @Slot(str, str)
    def _apply_error(self, name: str, message: str):
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
        artists = item.get("artists") or []
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
    def _track(cls, item, upload=False, album_thumbnail=""):
        upload = upload or cls._is_upload(item)
        artists = cls._artists(item)
        album = cls._album(item)
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
            "duration": str(duration),
            "videoId": str(item.get("videoId") or ""),
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
            ytmusic = YTMusic(headers)
            ytmusic.get_library_playlists(limit=1)
            account = {"accountName": "YouTube Music"}
            try:
                info = ytmusic.get_account_info()
                if info:
                    account.update(info)
            except Exception:
                pass
            return {"ytmusic": ytmusic, "account": account}

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

    @Slot()
    def loadLiked(self):
        def task():
            data = self._require_ytmusic().get_liked_songs(limit=2000)
            tracks = core.usable_tracks(data.get("tracks") or [])
            result = []
            for item in tracks:
                normalized = self._track(item)
                if not normalized.get("likeStatus"):
                    normalized["likeStatus"] = "LIKE"
                result.append(normalized)
            return result

        self._submit("liked", "Načítám oblíbenou hudbu…", task)

    @Slot(str)
    def sortLiked(self, order):
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

            if kind == "album":
                if not browse_id:
                    raise RuntimeError("Album nemá browseId.")
                data = ytmusic.get_album(browse_id)
                detail_title = data.get("title") or title
                tracks = core.usable_tracks(data.get("tracks") or [])

            elif kind == "artist":
                if not browse_id:
                    raise RuntimeError("Interpret nemá browseId.")
                data = ytmusic.get_artist(browse_id)
                detail_title = data.get("name") or title
                tracks = core.usable_tracks(
                    (data.get("songs") or {}).get("results") or []
                )

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
                "tracks": [
                    self._track(
                        x,
                        upload=kind.startswith("upload_"),
                        album_thumbnail=album_thumbnail,
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
        if not playlist_id:
            return

        def task():
            data = self._require_ytmusic().get_playlist(
                playlist_id,
                limit=core.LIBRARY_LIMIT,
            )
            tracks = core.usable_tracks(data.get("tracks") or [])
            return {
                "title": title,
                "tracks": [self._track(x) for x in tracks],
            }

        self._submit("detail", f"Načítám: {title}", task)

    @Slot()
    def clearDetail(self):
        if self._detail_title:
            self._detail_title = ""
            self.detailTitleChanged.emit()
        self._detail_tracks_model.clear()

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
