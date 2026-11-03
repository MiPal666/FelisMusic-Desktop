#!/usr/bin/env bash
set -euo pipefail

source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
install_dir="$HOME/.local/opt/felismusic"
applications_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
desktop_file="$applications_dir/felismusic.desktop"

if [[ -e "$install_dir" || -L "$install_dir" || -e "$desktop_file" || -L "$desktop_file" ]]; then
    echo "FelisMusic already has an installation or launcher. This installer supports fresh installations only." >&2
    exit 1
fi

if ! python3 -c 'import venv, ensurepip, gi; gi.require_version("Gst", "1.0"); from gi.repository import Gst; Gst.init(None)'; then
    echo "Install Python 3 with venv/ensurepip, PyGObject and the GStreamer 1.0 introspection bindings for that Python." >&2
    exit 1
fi

deno_bin="$(command -v deno || printf '%s' "${DENO_INSTALL:-$HOME/.deno}/bin/deno")"
if ! deno_version="$("$deno_bin" --version 2>/dev/null)" ||
    [[ ! "$deno_version" =~ ^deno[[:space:]]+([0-9]+)\.([0-9]+)\. ]] ||
    (( BASH_REMATCH[1] < 2 || (BASH_REMATCH[1] == 2 && BASH_REMATCH[2] < 3) )); then
    echo "FelisMusic requires Deno 2.3 or newer for YouTube playback." >&2
    echo "Install or update Deno, then run this installer again:" >&2
    echo "https://docs.deno.com/runtime/getting_started/installation/" >&2
    exit 1
fi

mkdir -p -- "$(dirname -- "$install_dir")" "$applications_dir"
mkdir -- "$install_dir"
launcher_tmp=""
cleanup() {
    rm -rf -- "$install_dir"
    if [[ -n "$launcher_tmp" ]]; then
        rm -f -- "$launcher_tmp"
    fi
    echo "FelisMusic installation failed." >&2
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

cp -R -- "$source_dir/desktop" "$source_dir/run-gui.sh" "$source_dir/requirements-gui.txt" "$source_dir/uninstall.sh" "$install_dir/"
chmod +x -- "$install_dir/run-gui.sh"
python3 -m venv --system-site-packages "$install_dir/env"
"$install_dir/env/bin/python" -m pip --disable-pip-version-check install -r "$install_dir/requirements-gui.txt"
"$install_dir/env/bin/python" -c 'import PySide6.QtQuick, ytmusicapi, yt_dlp, pychromecast, dbus'

launcher_tmp="$(mktemp "$applications_dir/.felismusic.XXXXXX")"
python3 - "$install_dir" > "$launcher_tmp" <<'PY'
import sys

path = sys.argv[1]
exec_path = path.replace("%", "%%")
for character in ('\\', '"', '`', '$'):
    exec_path = exec_path.replace(character, '\\' + character)

print("[Desktop Entry]")
print("Type=Application")
print("Name=FelisMusic")
print("GenericName=YouTube Music player")
print("GenericName[cs]=Přehrávač YouTube Music")
print("Comment=Play music from YouTube Music on your desktop")
print("Comment[cs]=Poslouchejte hudbu z YouTube Music na počítači")
print(f'Exec="{exec_path.replace(chr(92), chr(92) * 2)}/run-gui.sh"')
print(f"Icon={path.replace(chr(92), chr(92) * 2)}/desktop/felismusic.svg")
print("Categories=AudioVideo;Audio;Player;")
print("Terminal=false")
PY
chmod 644 -- "$launcher_tmp"
ln -- "$launcher_tmp" "$desktop_file"
trap - EXIT INT TERM
rm -f -- "$launcher_tmp"

echo "FelisMusic is installed. Start it from the application menu. You can delete the extracted ZIP folder."
