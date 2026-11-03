#!/usr/bin/env bash
set -euo pipefail

install_dir="$HOME/.local/opt/felismusic"
desktop_file="${XDG_DATA_HOME:-$HOME/.local/share}/applications/felismusic.desktop"
icon_path="$install_dir/desktop/felismusic.svg"
icon_path="${icon_path//\\/\\\\}"

if [[ -L "$install_dir" || ( -e "$install_dir" && ! -f "$install_dir/desktop/felismusic_gui/legacy_core.py" ) ]]; then
    echo "The installation directory does not look like a FelisMusic installation: $install_dir" >&2
    exit 1
fi

if [[ -e "$desktop_file" || -L "$desktop_file" ]]; then
    if [[ -L "$desktop_file" || ! -f "$desktop_file" ]] || ! grep -Fxq -- "Icon=$icon_path" "$desktop_file"; then
        echo "The launcher does not belong to this FelisMusic installation: $desktop_file" >&2
        exit 1
    fi
    rm -- "$desktop_file"
fi

rm -rf -- "$install_dir"
echo "FelisMusic was removed. Your settings and sign-in data were kept."
