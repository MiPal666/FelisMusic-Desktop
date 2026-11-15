# Experimental FelisMusic AppImage (Debian 13, x86_64)

The maintained ZIP installer is unchanged. This is an additional experimental
distribution, not a replacement and not a published AppImage release.

Build as a regular user on Debian 13 with Python 3.13. The `.appimage-env`
virtualenv must use `--system-site-packages` for Debian's PyGObject/dbus-python.
Python build dependencies are pinned in requirements.txt. The system needs git,
curl, ca-certificates, unzip, build-essential, pkg-config, python3-dev,
python3-venv, python3-gi, python3-dbus, gir1.2-gstreamer-1.0,
gir1.2-gst-plugins-base-1.0, gstreamer1.0-tools, gstreamer1.0-plugins-base,
gstreamer1.0-plugins-good, gstreamer1.0-libav, gstreamer1.0-pulseaudio,
patchelf, squashfs-tools, desktop-file-utils, libegl1, libopengl0, libxcb-cursor0.

The custom PySide6.QtQml hook limits collection to QtQml and the QtQuick
Controls/Templates/Layouts/Window/Effects/Shapes/Timeline modules. It avoids
collecting every installed QML module, including unused TextToSpeech and 3D.
The spec rejects reintroduced speech/Quick3D libraries, with an explicit exception
for the auxiliary libQt6Quick3DUtils.so library if binary dependency analysis
collects it. The Quick3D QML modules remain excluded. Self-test startup prints
flushed stages and enables faulthandler to help diagnose native crashes.
The first Debian build crashed in QtTextToSpeech during QGuiApplication creation;
its Qt libraries all came from the same PySide6 wheel. The restricted bundle is
a targeted diagnostic build. After allowing its auxiliary Quick3DUtils library,
the build and offline self-test succeeded on Debian1. The user confirmed startup,
Firefox sign-in, audio playback, and MPRIS PlaybackStatus/PlayPause/Next on a clean
Debian VM, then also confirmed the simplified sign-in workflow. Cast and
openSUSE tests remain pending; no public AppImage release has been made.

From the project root:

```sh
.appimage-env/bin/python -m pip install -r packaging/appimage/requirements.txt
.appimage-env/bin/python packaging/appimage/build.py
```

The builder downloads official Deno 2.9.0 and appimagetool assets and verifies
their pinned SHA-256 digests before executing them. The appimagetool continuous
URL is mutable: if the checksum changes, the builder stops. Reassess the tool
and update the pinned checksum explicitly; never skip verification.

Build output is isolated under build/appimage. The final experimental AppImage
and checksum go to dist/. No installation into the home directory or application
menu is performed. Source login/configuration is not packaged. Run-time user
settings remain in the normal XDG config directory. AppImage is not a sandbox.

The offline self-test checks bundled Qt/QML, translations, Python imports,
GStreamer codec/output factories (including their actual bundle locations), and
bundled Deno. It uses a separate config/cache under build/appimage/smoke-home and
does not sign in, contact YTM, or play sound. This is not a complete runtime test.

Test on the clean Debian VM and openSUSE:

```sh
chmod +x FelisMusic-1.0.2-experimental-x86_64.AppImage
QT_QPA_PLATFORM=offscreen ./FelisMusic-1.0.2-experimental-x86_64.AppImage --appimage-self-test
./FelisMusic-1.0.2-experimental-x86_64.AppImage --debug
```

If FUSE mounts are unavailable, add `--appimage-extract-and-run` before app
arguments. A successful extracted run does not verify normal FUSE mounting.

Verify fresh browser login, persisted login, search/library/artists, local AAC
and Opus audio, seek, pause/next, Cast including speaker groups, MPRIS and the
yt-dlp fallback (uploaded tracks). Test both GUI launch and terminal launch.
Do not install Python packages, Deno or codecs into the clean test VM to make the
AppImage work: report missing dependencies so the bundle can be corrected.

Before public release: finish the clean-system tests, verify notices and source
availability for bundled dependencies, record their versions, and check that no
system-only paths were used. Package inventories and Debian copyright notices
are included under usr/share/doc/felismusic. Current minimum target is Debian 13;
compatibility with older glibc systems has not been established.
