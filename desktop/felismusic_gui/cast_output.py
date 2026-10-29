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
            ready.set()
        self.pending = (ready, response, url, paused)
        self.controller.play_media(url, content_type, current_time=position, autoplay=not paused,
                                   callback_function=accepted, **kwargs)

    def block_until_active(self, timeout=15, cancelled=None):
        ready, response, url, paused = self.pending
        deadline = monotonic() + timeout
        while monotonic() < deadline:
            if cancelled and cancelled():
                raise core.AudioPreparationCancelled("Přepnutí zrušeno")
            if ready.is_set():
                if not response.get("ok"):
                    raise RuntimeError("Cast odmítl načtení skladby.")
                status = self.status
                if (status.content_id == url and status.media_session_id
                        and status.player_state in (("PAUSED",) if paused else ("PLAYING", "BUFFERING"))):
                    return
                if status.content_id == url and status.player_state == "IDLE" and status.idle_reason == "ERROR":
                    raise RuntimeError("Cast nedokázal přehrát stream.")
            Event().wait(0.1)
        raise RuntimeError("Cast nepotvrdil spuštění skladby včas.")

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


def handoff(scanner, device_id, local, song, active, cancelled):
    target = None
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
        if active:
            event("stream_begin")
            url, content_type = core.get_playback_source(song["videoId"], target.media_controller)
            event("stream_ready")
            check()
            position = core.get_media_position(local.media_controller)
            status = local.media_controller.status
            if status.player_state not in ("PLAYING", "PAUSED", "BUFFERING"):
                raise RuntimeError("Skladba mezitím dohrála. Zkus přepnutí znovu.")
            paused = status.player_state == "PAUSED"
            check()
            local.media_controller.stop(keep_output=True)
            event("local_stopped")
            source_stopped = True
            check()
            touched = True
            target.media_controller.play_media_at(url, content_type, position=position, paused=paused,
                title=f"{core.artist_names(song)} - {song.get('title', '?')}", stream_type="BUFFERED")
            target.media_controller.block_until_active(timeout=15, cancelled=cancelled)
            event("cast_ready")
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
        if source_stopped and stopped_target and not cancelled():
            try:
                url, content_type = core.get_local_audio_source(song["videoId"], cancelled=cancelled)
                check()
                local.media_controller.play_media_at(url, content_type, position=position, paused=paused,
                    title=song.get("title", ""), stream_type="BUFFERED")
                if not paused:
                    local.media_controller.block_until_active(timeout=15, cancelled=cancelled)
                check()
                recovered = True
                event("local_recovered")
            except Exception:
                try:
                    local.media_controller.stop(keep_output=True)
                except Exception:
                    pass
        print(f"FelisMusic přepnutí Cast: {type(exc).__name__}")
        message = ("Přepnutí na Cast se nepodařilo. Místní poslech byl obnoven." if recovered else
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
