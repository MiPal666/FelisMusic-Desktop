"""Cast transport adapter and explicit Local / Cast handoffs."""
from threading import Event
from time import monotonic
from . import legacy_core as core
from .diagnostics import current_trace


def dispose(result):
    target = result.get("output")
    if target:
        if result.get("active"):
            core.stop_output_safely(target)
        if not result.get("local"):
            core._disconnect_cast_safely(target)


class CastController:
    is_local = False

    def __init__(self, controller):
        self.controller = controller
        self.pending = None

    @property
    def status(self):
        return self.controller.status

    def update_status(self):
        self.controller.update_status()

    def play_media(self, url, content_type, **kwargs):
        self.play_media_at(url, content_type, **kwargs)

    def play_media_at(self, url, content_type, position=0.0, paused=False, **kwargs):
        ready, response = Event(), {}
        def accepted(success, data):
            response["ok"] = bool(success)
            response["type"] = data.get("type") if isinstance(data, dict) else None
            ready.set()
        self.pending = (ready, response, url, paused)
        self.controller.play_media(url, content_type, current_time=position, autoplay=not paused,
                                   callback_function=accepted, **kwargs)

    def block_until_active(self, timeout=15, cancelled=None):
        ready, response, url, paused = self.pending
        deadline = monotonic() + timeout
        previous = None
        while monotonic() < deadline:
            if cancelled and cancelled():
                raise core.AudioPreparationCancelled("Přepnutí zrušeno")
            status = self.status
            response_type = response.get("type")
            if response_type not in (None, "MEDIA_STATUS", "LOAD_FAILED", "LOAD_CANCELLED", "INVALID_REQUEST"):
                response_type = "other"
            state = {"acknowledged": ready.is_set(), "accepted": bool(response.get("ok")),
                     "response_type": response_type, "content_matches": status.content_id == url,
                     "has_session": bool(status.media_session_id),
                     "player_state": status.player_state if status.player_state in
                         ("UNKNOWN", "IDLE", "BUFFERING", "PLAYING", "PAUSED") else "other",
                     "idle_reason": status.idle_reason if status.idle_reason in
                         (None, "", "FINISHED", "CANCELLED", "INTERRUPTED", "ERROR") else "other"}
            if state != previous:
                trace = current_trace()
                if trace:
                    trace.event("cast.load.state", **state)
                previous = state
            if ready.is_set():
                if not response.get("ok") or response_type in ("LOAD_FAILED", "LOAD_CANCELLED", "INVALID_REQUEST"):
                    raise RuntimeError("Cast odmítl načtení skladby.")
                if (status.content_id == url and status.media_session_id
                        and status.player_state in (("PAUSED",) if paused else ("PLAYING", "BUFFERING"))):
                    return
                if status.content_id == url and status.player_state == "IDLE" and status.idle_reason == "ERROR":
                    raise RuntimeError("Cast nedokázal přehrát stream.")
            Event().wait(0.1)
        raise RuntimeError("Cast nepotvrdil spuštění skladby včas.")

    def start_receiver(self, timeout=15, cancelled=None):
        """Start an individual receiver independently of its former group app."""
        if cancelled and cancelled():
            raise core.AudioPreparationCancelled("Přepnutí zrušeno")
        ready, response = Event(), {}
        def accepted(success, data):
            response["ok"] = bool(success)
            ready.set()
        self.controller.launch(force_launch=True, callback_function=accepted)
        deadline = monotonic() + timeout
        while monotonic() < deadline:
            if cancelled and cancelled():
                raise core.AudioPreparationCancelled("Přepnutí zrušeno")
            if ready.is_set():
                if not response.get("ok"):
                    raise RuntimeError("Cast nepotvrdil samostatný přijímač.")
                return
            ready.wait(0.1)
        raise RuntimeError("Cast nepotvrdil samostatný přijímač včas.")

    def stop(self, keep_output=False):
        # A receiver application can remain open after its media session ends.
        # PyChromecast rejects STOP without a session, preventing the next LOAD.
        if self.status is None or self.status.media_session_id is None:
            return
        self.controller.stop(timeout=3)

    def pause(self):
        self.controller.pause()

    def play(self):
        self.controller.play()

    def seek(self, position, timeout=3):
        self.controller.seek(position, timeout=timeout)


class CastOutput:
    is_local = False

    def __init__(self, cast):
        self.cast = cast
        self.cast_info = cast.cast_info
        self.media_controller = CastController(cast.media_controller)

    @property
    def status(self):
        return self.cast.status

    def set_volume(self, level):
        return self.cast.set_volume(level)

    def set_volume_muted(self, muted):
        self.cast.set_volume_muted(muted)
        return bool(muted)

    def disconnect(self, timeout=1):
        self.cast.disconnect(timeout=timeout)


def handoff(scanner, device_id, source, song, active, cancelled):
    target = None
    source_local = getattr(source, "is_local", True)
    source_stopped = touched = recovered = False
    position, paused = 0.0, False
    def event(stage):
        trace = current_trace()
        if trace:
            trace.event("cast.switch." + stage)
    def check():
        if cancelled():
            raise core.AudioPreparationCancelled("Přepnutí zrušeno")
    try:
        check()
        event("connect_begin")
        raw = scanner.resolve(device_id)
        target = CastOutput(raw)
        core.prepare_output(raw)
        event("connected")
        check()
        group_to_audio = (not source_local and source.cast_info.cast_type == "group"
                          and target.cast_info.cast_type == "audio")
        if active:
            event("stream_begin")
            url, content_type = core.get_playback_source(song["videoId"], target.media_controller)
            event("stream_ready")
            check()
            position = core.get_media_position(source.media_controller)
            status = source.media_controller.status
            if status.player_state not in ("PLAYING", "PAUSED", "BUFFERING"):
                raise RuntimeError("Skladba mezitím dohrála. Zkus přepnutí znovu.")
            paused = status.player_state == "PAUSED"
            check()
            source.media_controller.stop(keep_output=True)
            event("local_stopped" if source_local else "cast_stopped")
            source_stopped = True
            check()
            touched = True
            if group_to_audio:
                event("receiver_begin")
                target.media_controller.start_receiver(cancelled=cancelled)
                event("receiver_ready")
                check()
            target.media_controller.play_media_at(url, content_type, position=position, paused=paused,
                title=f"{core.artist_names(song)} - {song.get('title', '?')}", stream_type="BUFFERED")
            target.media_controller.block_until_active(timeout=15, cancelled=cancelled)
            event("cast_ready")
            check()
        elif not source_local:
            # Explicitly leave the selected Cast even with an idle GUI queue.
            source.media_controller.stop()
            source_stopped = True
            check()
            if group_to_audio:
                touched = True
                event("receiver_begin")
                target.media_controller.start_receiver(cancelled=cancelled)
                event("receiver_ready")
                check()
        return {"output": target, "active": active, "paused": paused, "position": position, "error": ""}
    except Exception as exc:
        event("failed")
        stopped_target = True
        if touched:
            try:
                target.media_controller.stop()
            except Exception:
                stopped_target = False
        if target:
            core._disconnect_cast_safely(target)
        if active and source_stopped and stopped_target and not cancelled():
            try:
                url, content_type = (core.get_local_audio_source(song["videoId"], cancelled=cancelled) if source_local else
                                     core.get_playback_source(song["videoId"], source.media_controller))
                check()
                source.media_controller.play_media_at(url, content_type, position=position, paused=paused,
                    title=song.get("title", ""), stream_type="BUFFERED")
                if not paused or not source_local:
                    source.media_controller.block_until_active(timeout=15, cancelled=cancelled)
                check()
                recovered = True
                event("local_recovered" if source_local else "cast_recovered")
            except Exception:
                try:
                    source.media_controller.stop(keep_output=True)
                except Exception:
                    pass
        print(f"FelisMusic přepnutí Cast: {type(exc).__name__}")
        message = (("Přepnutí na Cast se nepodařilo. Místní poslech byl obnoven." if source_local else
                    "Přepnutí na Cast se nepodařilo. Poslech na původním Castu byl obnoven.") if recovered else
                   "Přepnutí na Cast se nepodařilo. Původní výstup zůstává vybraný." if not source_stopped else
                   "Přepnutí na Cast selhalo a přehrávání se nepodařilo obnovit. Zkontroluj výstupy.")
        return {"output": None, "error": message, "sourceStopped": source_stopped,
                "recovered": recovered, "paused": paused, "position": position}


def handoff_to_local(source, local, song, active, cancelled):
    """Prepare local audio before stopping Cast; never play both at once."""
    source_stopped = touched = recovered = False
    position, paused = 0.0, False

    def event(stage):
        trace = current_trace()
        if trace:
            trace.event("cast.return." + stage)

    def check():
        if cancelled():
            raise core.AudioPreparationCancelled("Přepnutí zrušeno")

    try:
        check()
        if active:
            event("prepare_begin")
            url, content_type = core.get_local_audio_source(song["videoId"], cancelled=cancelled,
                                                           diagnostics=current_trace())
            event("prepare_ready")
            check()
            position = core.get_media_position(source.media_controller)
            status = source.media_controller.status
            if status.player_state not in ("PLAYING", "PAUSED", "BUFFERING"):
                raise RuntimeError("Skladba mezitím dohrála. Zkus přepnutí znovu.")
            paused = status.player_state == "PAUSED"
        check()
        source.media_controller.stop()
        source_stopped = True
        event("cast_stopped")
        check()
        if active:
            touched = True
            local.media_controller.play_media_at(url, content_type, position=position, paused=paused,
                title=f"{core.artist_names(song)} - {song.get('title', '?')}", stream_type="BUFFERED")
            local.media_controller.block_until_active(timeout=15, cancelled=cancelled)
            check()
        event("local_ready")
        return {"output": local, "local": True, "active": active, "paused": paused,
                "position": position, "error": ""}
    except Exception as exc:
        event("failed")
        stopped_target = True
        if touched:
            try:
                local.media_controller.stop(keep_output=True)
            except Exception:
                stopped_target = False
        if active and source_stopped and stopped_target and not cancelled():
            try:
                url, content_type = core.get_playback_source(song["videoId"], source.media_controller)
                check()
                source.media_controller.play_media_at(url, content_type, position=position, paused=paused,
                    title=song.get("title", ""), stream_type="BUFFERED")
                source.media_controller.block_until_active(timeout=15, cancelled=cancelled)
                check()
                recovered = True
                event("cast_recovered")
            except Exception:
                try:
                    source.media_controller.stop()
                except Exception:
                    pass
        print(f"FelisMusic návrat z Castu: {type(exc).__name__}")
        message = ("Návrat na toto zařízení se nepodařil. Poslech na Castu byl obnoven." if recovered else
                   "Návrat na toto zařízení se nepodařil. Cast zůstává vybraný." if not source_stopped else
                   "Návrat na toto zařízení selhal a přehrávání se nepodařilo obnovit. Zkontroluj výstupy.")
        return {"output": None, "error": message, "sourceStopped": source_stopped,
                "recovered": recovered, "paused": paused, "position": position}
