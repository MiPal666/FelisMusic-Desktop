"""Frozen entry point; --appimage-self-test avoids login/network/audio output."""
import os
import sys


def stage(message):
    if "--appimage-self-test" in sys.argv:
        print("[AppImage self-test] " + message, file=sys.stderr, flush=True)


stage("Entry point reached; importing application")
# Use bundled plugins exclusively; do not silently borrow codecs from the VM.
os.environ["GST_PLUGIN_SYSTEM_PATH"] = ""
os.environ["GST_PLUGIN_SYSTEM_PATH_1_0"] = ""
os.environ.pop("GST_PLUGIN_PATH_1_0", None)
# PyInstaller's GStreamer hook points the registry into _MEIPASS. AppImage's
# mounted payload is read-only, so override that location after the hook ran.
_registry_dir = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "felismusic")
os.makedirs(_registry_dir, exist_ok=True)
os.environ["GST_REGISTRY"] = os.path.join(_registry_dir, "appimage-gstreamer-registry.bin")

import main as desktop_main
stage("Application imported")


def self_test():
    import json
    import subprocess
    from pathlib import Path
    from importlib.metadata import version
    import dbus
    import yt_dlp_ejs
    from yt_dlp.extractor.youtube._base import INNERTUBE_CLIENTS
    from felismusic_gui import legacy_core as core
    from felismusic_gui.i18n import TRANSLATIONS_DIR
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from felismusic_gui.backend import BackendBridge

    assert getattr(sys, "frozen", False), "Run the bundled executable"
    assert core.GST_AVAILABLE, type(core.GST_IMPORT_ERROR).__name__
    elements = ("playbin", "pulsesink", "qtdemux", "avdec_aac", "opusdec")
    available = {name: core.Gst.ElementFactory.find(name) is not None for name in elements}
    assert all(available.values()), available
    for name in elements:
        plugin = core.Gst.ElementFactory.find(name).get_plugin()
        assert Path(plugin.get_filename()).resolve().is_relative_to(Path(sys._MEIPASS).resolve()), name
    assert "visionos" in INNERTUBE_CLIENTS
    for locale in ("cs", "en"):
        assert (TRANSLATIONS_DIR / ("felismusic_" + locale + ".qm")).is_file()
    deno = subprocess.run(["deno", "--version"], check=True, capture_output=True, text=True)
    stage("Imports, bundled codecs, translations and Deno OK; creating QGuiApplication")
    app = QGuiApplication([])
    stage("QGuiApplication created; creating QML engine")
    engine = QQmlApplicationEngine()
    errors = []
    engine.warnings.connect(lambda warnings: errors.extend(str(x) for x in warnings))
    bridge = BackendBridge(engine)
    stage("Backend created; loading Main.qml")
    engine.rootContext().setContextProperty("backend", bridge)
    engine.rootContext().setContextProperty("fcmVersion", desktop_main.VERSION)
    engine.load(QUrl.fromLocalFile(str(Path(desktop_main.__file__).with_name("Main.qml"))))
    app.processEvents()
    stage("QML loaded and events processed")
    try:
        assert engine.rootObjects(), errors
        assert not errors, errors
        print(json.dumps(dict(version=desktop_main.VERSION, gstreamer=core.Gst.version_string(),
            elements=available, deno=deno.stdout.splitlines()[0],
            ytmusicapi=version("ytmusicapi"), qt_qml="OK", translations="OK")), flush=True)
    finally:
        stage("Shutting down backend")
        bridge.shutdown()
        stage("Backend shutdown complete")


if __name__ == "__main__":
    from multiprocessing import freeze_support
    freeze_support()
    if "--appimage-self-test" in sys.argv:
        self_test()
    else:
        raise SystemExit(desktop_main.main())
