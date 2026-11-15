#!/usr/bin/env python3
"""Experimental Debian 13 x86_64 builder. Never installs system packages."""
import ast
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "packaging/appimage"
WORK = ROOT / "build/appimage"
OUT = ROOT / "dist"
TOOLS = WORK / "tools"


def run(args, **kwargs):
    print("+", " ".join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def download(name, url, digest):
    dest = TOOLS / name
    if not dest.exists():
        temp = dest.with_suffix(dest.suffix + ".download")
        run(["curl", "--fail", "--location", "--retry", "3", "--output", temp, url])
        temp.replace(dest)
    if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
        raise RuntimeError("Checksum mismatch: " + str(dest) + "; remove this cached file and check upstream")
    return dest


def main():
    if os.geteuid() == 0:
        raise SystemExit("Run as your regular user, without sudo")
    if platform.machine() != "x86_64":
        raise SystemExit("This prototype supports only x86_64")
    system = platform.freedesktop_os_release()
    if system.get("ID") != "debian" or system.get("VERSION_ID") != "13":
        raise SystemExit("Build on Debian 13; test the result on other distributions")
    from importlib.metadata import version
    for name, wanted in (("PyInstaller", "6.22.3"), ("PySide6", "6.12.0"),
                         ("ytmusicapi", "1.12.3"), ("yt-dlp", "2026.10.26"),
                         ("PyChromecast", "14.0.10")):
        if version(name) != wanted:
            raise SystemExit(name + " must be " + wanted)
    import gi, dbus
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
    Gst.init(None)
    for name in ("playbin", "pulsesink", "qtdemux", "avdec_aac", "opusdec"):
        if Gst.ElementFactory.find(name) is None:
            raise SystemExit("Missing build-time GStreamer element: " + name)
    for name in ("curl", "patchelf", "desktop-file-validate"):
        if not shutil.which(name):
            raise SystemExit("Missing build tool: " + name)
    for directory in (WORK, OUT, TOOLS):
        directory.mkdir(parents=True, exist_ok=True)

    denozip = download("deno-2.9.0-linux-x86_64.zip",
        "https://github.com/denoland/deno/releases/download/v2.9.0/deno-x86_64-unknown-linux-gnu.zip",
        "96c9c73fc05ea57603bc28d8071d41e861bd40bcf2a9f849dd5969ed1a2c8498")
    appimagetool = download("appimagetool-x86_64.AppImage",
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage",
        "e8c1169c4af66c3184d7ee110713d4be04befe671fa358e2c1591ee840553b03")
    appimagetool.chmod(0o755)

    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         "--distpath", WORK / "frozen", "--workpath", WORK / "pyinstaller",
         PACK / "felismusic.spec"], cwd=ROOT)
    appdir = WORK / "FelisMusic.AppDir"
    if appdir.exists():
        shutil.rmtree(appdir)
    (appdir / "usr/lib").mkdir(parents=True)
    (appdir / "usr/bin").mkdir()
    shutil.copytree(WORK / "frozen/felismusic", appdir / "usr/lib/felismusic", symlinks=True)
    with zipfile.ZipFile(denozip) as z:
        (appdir / "usr/bin/deno").write_bytes(z.read("deno"))
    (appdir / "usr/bin/deno").chmod(0o755)
    for src, dst in ((PACK / "AppRun", appdir / "AppRun"),
                     (PACK / "felismusic.desktop", appdir / "felismusic.desktop"),
                     (ROOT / "desktop/felismusic.svg", appdir / "felismusic.svg")):
        shutil.copy2(src, dst)
    (appdir / "AppRun").chmod(0o755)
    (appdir / ".DirIcon").symlink_to("felismusic.svg")
    docs = appdir / "usr/share/doc/felismusic"
    docs.mkdir(parents=True)
    for name in ("LICENSE", "README.md", "README.cs.md"):
        shutil.copy2(ROOT / name, docs / name)
    (docs / "python-packages.txt").write_bytes(run(
        [sys.executable, "-m", "pip", "freeze", "--all"], capture_output=True).stdout)
    (docs / "debian-packages.txt").write_bytes(run(
        ["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\n"], capture_output=True).stdout)
    # Retain installed Debian copyright/license notices for bundled libraries.
    shutil.copytree("/usr/share/doc", docs / "debian-copyright", symlinks=False,
        ignore=lambda directory, names: [n for n in names if n != "copyright"
            and not (Path(directory) / n).is_dir()], ignore_dangling_symlinks=True)
    run(["desktop-file-validate", appdir / "felismusic.desktop"])
    # No existing user login or cache may be used during the offline smoke test.
    smoke_home = WORK / "smoke-home"
    smoke_home.mkdir(exist_ok=True)
    env = dict(os.environ, HOME=str(smoke_home), XDG_CONFIG_HOME=str(smoke_home / "config"),
        XDG_CACHE_HOME=str(smoke_home / "cache"), QT_QPA_PLATFORM="offscreen")
    run([appdir / "AppRun", "--appimage-self-test"], env=env)
    module = ast.parse((ROOT / "desktop/main.py").read_text())
    appversion = next(ast.literal_eval(n.value) for n in module.body
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in n.targets))
    target = OUT / ("FelisMusic-" + appversion + "-experimental-x86_64.AppImage")
    # Extract-and-run supports builders where FUSE mounts are unavailable.
    run([appimagetool, "--appimage-extract-and-run", appdir, target],
        env=dict(os.environ, ARCH="x86_64", VERSION=appversion))
    target.chmod(0o755)
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(target.suffix + ".sha256").write_text(checksum + "  " + target.name + "\n")
    print("EXPERIMENTAL APPIMAGE:", target)
    print("Not yet verified on the clean VM or openSUSE. ZIP distribution is unchanged.")


if __name__ == "__main__":
    main()
