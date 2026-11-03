#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$ROOT/env/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$ROOT/env/bin/activate"
elif [[ -f "$ROOT/../env/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$ROOT/../env/bin/activate"
fi

# Desktop launchers may lack the shell PATH configured by the Deno installer.
if ! command -v deno >/dev/null 2>&1 && [[ -x "${DENO_INSTALL:-$HOME/.deno}/bin/deno" ]]; then
    export PATH="${DENO_INSTALL:-$HOME/.deno}/bin:$PATH"
fi

if ! python -c 'import gi; gi.require_version("Gst", "1.0"); from gi.repository import Gst' >/dev/null 2>&1; then
    echo "VAROVÁNÍ: tento Python nevidí PyGObject/GStreamer." >&2
    echo "Datová část GUI poběží, ale lokální přehrávání nebude dostupné." >&2
    echo "Na openSUSE vytvoř env přes: python3 -m venv --system-site-packages env" >&2
    echo >&2
fi

exec python "$ROOT/desktop/main.py" "$@"
