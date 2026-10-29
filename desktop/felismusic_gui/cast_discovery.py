"""Opt-in discovery metadata only: never create a Chromecast/media controller."""
from threading import Event, Thread
from time import monotonic
from pychromecast.discovery import CastBrowser, SimpleCastListener
from zeroconf import Zeroconf
from . import legacy_core as core


def device_rows(infos):
    rows = {}
    for info in infos:
        if info.cast_type not in ("audio", "group") or info.uuid is None:
            continue
        key = str(info.uuid)
        rows[key] = dict(id=key, name=str(info.friendly_name or "Cast zařízení"), kind=info.cast_type)
    return sorted(rows.values(), key=lambda row: (row["name"].casefold(), row["id"]))


class CastDiscovery:
    poll_interval = 0.5
    initial_settle = core.OUTPUT_INITIAL_SETTLE
    refresh_settle = core.OUTPUT_REFRESH_SETTLE

    def __init__(self, callback):
        self.callback = callback
        self.stopped = Event()
        self.refresh_requested = Event()
        self.thread = Thread(target=self._run, name="felismusic-cast-discovery", daemon=True)

    def start(self):
        self.thread.start()

    def refresh(self):
        self.refresh_requested.set()

    def close(self):
        self.stopped.set()

    def _notify(self, rows, scanning, error=""):
        if not self.stopped.is_set():
            try:
                self.callback(rows, scanning, error)
            except RuntimeError:
                pass  # The Qt receiver can already be gone during shutdown.

    def _run(self):
        browser = zc = None
        try:
            if self.stopped.is_set():
                return
            zc = Zeroconf()
            browser = CastBrowser(SimpleCastListener(), zeroconf_instance=zc)
            browser.start_discovery()
            deadline = monotonic() + self.initial_settle
            previous = None
            while not self.stopped.is_set():
                if self.refresh_requested.is_set():
                    self.refresh_requested.clear()
                    deadline = monotonic() + self.refresh_settle
                rows = device_rows(core._browser_devices_snapshot(browser))
                state = (rows, monotonic() < deadline)
                if state != previous:
                    self._notify(*state)
                    previous = state
                self.stopped.wait(self.poll_interval)
        except Exception as exc:
            print(f"FelisMusic hledání Cast: {type(exc).__name__}")
            self._notify([], False, "Cast zařízení se nepodařilo vyhledat. Zkontroluj síť a zkus hledání znovu.")
        finally:
            if browser is not None:
                try:
                    browser.stop_discovery()
                except Exception:
                    pass
            if zc is not None:
                try:
                    zc.close()
                except Exception:
                    pass
