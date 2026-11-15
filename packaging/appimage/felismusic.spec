from pathlib import Path
import runpy
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).resolve().parents[1]
datas = [(str(root / "desktop" / name), ".") for name in ("Main.qml", "felismusic.svg")]
datas += [(str(root / "desktop/translations"), "translations")]
binaries, hiddenimports = [], ["dbus.mainloop.glib", "gi.repository.Gst",
    "gi.repository.GstAudio", "gi.repository.GstPbutils", "gi.repository.GLib",
    "PySide6.QtNetwork"]
# Plugins/extractors and package metadata are loaded dynamically by these libs.
for package in ("ytmusicapi", "yt_dlp", "yt_dlp_ejs", "pychromecast", "zeroconf", "certifi"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h
a = Analysis([str(root / "packaging/appimage/entry.py")],
    pathex=[str(root / "desktop")], binaries=binaries, datas=datas,
    hookspath=[str(root / "packaging/appimage/hooks")],
    hiddenimports=hiddenimports,
    runtime_hooks=[str(root / "packaging/appimage/runtime_hook.py")],
    hooksconfig={"gi": {"languages": ["cs", "en"]}, "gstreamer": {"include_plugins": [
        "coreelements", "playback", "typefindfunctions", "audioconvert", "audioresample",
        "volume", "pulseaudio", "autodetect", "isomp4", "audioparsers", "libav",
        "opus", "ogg", "vorbis", "matroska", "wavparse", "flac", "mpg123"]}},
    excludes=["tkinter", "pytest", "IPython"], noarchive=False)
# Fail visibly if an unrelated dependency reintroduces these QML libraries.
unexpected_qt_resource = runpy.run_path(str(root / "packaging/appimage/qml_filter.py"))["unexpected_qt_resource"]
unexpected = [dest for dest, source, kind in a.binaries
    if unexpected_qt_resource(dest)]
if unexpected:
    raise RuntimeError("Unexpected unused Qt modules in bundle: " + repr(unexpected))
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="felismusic", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="felismusic")
