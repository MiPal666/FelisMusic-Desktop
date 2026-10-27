#!/usr/bin/env python3

import os
import select
import sys
import shutil
import tempfile
import time
import hashlib
import http.cookiejar
import json
import re
import subprocess
from types import SimpleNamespace
from pathlib import Path

import pychromecast
import yt_dlp
import ytmusicapi.continuations as ytmusic_continuations
from ytmusicapi import LikeStatus, YTMusic

try:
    import gi

    gi.require_version(
        "Gst",
        "1.0",
    )

    from gi.repository import Gst

    Gst.init(None)

    GST_AVAILABLE = True
    GST_IMPORT_ERROR = None

except Exception as exc:
    Gst = None
    GST_AVAILABLE = False
    GST_IMPORT_ERROR = exc


VERSION = "1.0.0"

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

# FCM 0.0.17:
# veřejně použitelný AuthManager.
#
# Browser se používá jen při prvním přihlášení nebo obnově.
# Běžný profil uživatele FCM nečte ani nemění.
#
# Podporované login backendy:
# Firefox, Chromium, Google Chrome, Brave, Vivaldi, Edge.
#
# Provozní session:
#   ~/.config/felismusic/cookies.txt
#   ~/.config/felismusic/auth-state.json
#   ~/.config/felismusic/auth-profiles/
#
# browser.json z 0.0.16 už není pro běh FCM potřeba.

XDG_CONFIG_HOME = os.environ.get(
    "XDG_CONFIG_HOME",
    os.path.expanduser("~/.config"),
)

AUTH_DIR = os.path.join(
    XDG_CONFIG_HOME,
    "felismusic",
)

COOKIE_FILE = os.path.join(
    AUTH_DIR,
    "cookies.txt",
)

AUTH_STATE_FILE = os.path.join(
    AUTH_DIR,
    "auth-state.json",
)

AUTH_PROFILES_DIR = os.path.join(
    AUTH_DIR,
    "auth-profiles",
)

LEGACY_AUTH_FILE = os.path.join(
    AUTH_DIR,
    "browser.json",
)

YTM_ORIGIN = "https://music.youtube.com"
YTM_LOGIN_URL = (
    "https://music.youtube.com/library"
)

RESUME_SESSION_FILE = os.path.join(
    AUTH_DIR,
    "session.json",
)


SEARCH_LIMIT = 20
PLAYBACK_QUEUE_PAGE_SIZE = 50
DISCOVERY_TIMEOUT = 10
OUTPUT_REFRESH_SETTLE = 1.0
OUTPUT_INITIAL_SETTLE = 3.0
LIBRARY_LIMIT = 2000
MIX_LIMIT = 100
HOME_MIX_ROWS = 20

# Kolik skladeb před koncem radio fronty začneme
# automaticky načítat další doporučení.
MIX_REFILL_THRESHOLD = 5

# TEST prakticky nekonečného Mix/Radio.
#
# 5 = každý radio blok ve FCM uměle ořízneme na 5 skladeb,
#     takže doplnění fronty otestujeme během pár stisků "n".
#
# Po úspěšném testu změnit na:
#
# MIX_TEST_MAX_TRACKS = None
MIX_TEST_MAX_TRACKS = None

# Testovací háček z v0.0.6.2.
# None = vypnuto.
SIMULATE_BROKEN_TRACK = None

# Lokální GStreamer dostává u FCM 0.0.13.4 seekovatelný
# dočasný soubor místo přímé googlevideo URL.
LOCAL_CACHE_DIR = tempfile.mkdtemp(
    prefix="felismusic-"
)

LOCAL_AUDIO_CACHE = {}
LOCAL_CACHE_ORDER = []
LOCAL_CACHE_MAX_FILES = 8


# ============================================================
# Kompatibilita ytmusicapi / aktuální YouTube Music
# ============================================================
#
# ytmusicapi 1.12.x u get_watch_playlist() u některých front
# očekává pokračovací klíč "nextRadioContinuationData".
# YouTube Music ale aktuálně může vracet obyčejné
# "nextContinuationData" i pro radio/shuffle frontu.
#
# Výsledek bez této opravy:
#   KeyError: Unable to find 'nextRadioContinuationData'
#
# Nezasahujeme do nainstalovaného balíčku. Jen ve FCM uděláme
# malý kompatibilní wrapper, který umí obě varianty.

_ORIGINAL_GET_CONTINUATION_PARAMS = (
    ytmusic_continuations.get_continuation_params
)


def _fcm_get_continuation_params(
    results,
    ctoken_path="",
):
    try:
        continuations = results.get(
            "continuations"
        ) or []

        if continuations:
            continuation = continuations[0]

            candidate_keys = []

            if ctoken_path:
                candidate_keys.append(
                    f"next{ctoken_path}ContinuationData"
                )

            # Aktuální YTM často vrací právě tuto obecnou variantu.
            candidate_keys.append(
                "nextContinuationData"
            )

            # A zachováme i starší radio variantu jako fallback.
            candidate_keys.append(
                "nextRadioContinuationData"
            )

            for key in candidate_keys:
                data = continuation.get(key)

                if not isinstance(data, dict):
                    continue

                token = data.get(
                    "continuation"
                )

                if token:
                    return (
                        "&ctoken="
                        + token
                        + "&continuation="
                        + token
                    )

    except Exception:
        # Když se struktura změní ještě jinak,
        # necháme původní ytmusicapi vyhodit přesnější chybu.
        pass

    return _ORIGINAL_GET_CONTINUATION_PARAMS(
        results,
        ctoken_path,
    )


ytmusic_continuations.get_continuation_params = (
    _fcm_get_continuation_params
)


# ============================================================
# Globální klávesové zkratky v textových menu
# ============================================================

class GoMainMenu(Exception):
    pass


class QuitFCM(Exception):
    pass


def menu_input(prompt=""):
    """
    Globálně v textových menu:

      m = hlavní menu
      q = konec FCM

    Zkratku z = zpět řeší konkrétní menu.
    Během přehrávání z zůstává příkaz pro shuffle.
    """

    value = input(
        prompt
    ).strip()

    command = value.lower()

    if command == "m":
        raise GoMainMenu

    if command == "q":
        raise QuitFCM

    return value


# ============================================================
# Obecné pomocné funkce
# ============================================================

def artist_names(song):
    artists = song.get("artists") or []

    names = []

    for artist in artists:
        if isinstance(artist, dict):
            names.append(
                artist.get("name", "?")
            )
        else:
            names.append(str(artist))

    # Podcasty / epizody někdy nemají "artists".
    if not names:
        channel = song.get("channel")
        if isinstance(channel, dict):
            name = channel.get("name")
            if name:
                names.append(name)

    if not names:
        author = song.get("author")
        if isinstance(author, dict):
            name = author.get("name")
            if name:
                names.append(name)

    if not names:
        return "?"

    return ", ".join(names)


def song_duration(song):
    return (
        song.get("duration")
        or song.get("length")
        or "?"
    )


def album_name(song):
    album = song.get("album")

    if isinstance(album, dict):
        return album.get("name")

    if isinstance(album, str):
        return album

    return None


def song_description(song):
    title = song.get(
        "title",
        "?",
    )

    artists = artist_names(song)
    duration = song_duration(song)
    album = album_name(song)

    first_line = (
        f"{artists} - {title}"
    )

    second_line = duration

    if album:
        second_line += (
            f" | {album}"
        )

    return (
        first_line,
        second_line,
    )


def usable_tracks(tracks):
    if not tracks:
        return []

    result = []

    for song in tracks:
        if not isinstance(song, dict):
            continue

        if not song.get("videoId"):
            continue

        if not song.get(
            "isAvailable",
            True,
        ):
            continue

        result.append(song)

    return result


def choose_library_order():
    print()
    print("Řazení")
    print("======")
    print()
    print("1. Nedávno přidané")
    print("2. A–Z")
    print("3. Z–A")
    print("4. Výchozí pořadí YouTube Music")
    print("z. Zpět")
    print()

    while True:
        value = menu_input("Vyber: ")

        if value == "1":
            return "recently_added"

        if value == "2":
            return "a_to_z"

        if value == "3":
            return "z_to_a"

        if value == "4":
            return None

        if value.lower() == "z":
            return "back"

        if value == "5":
            return "back"

        print("Neplatná volba.")


# ============================================================
# Autentizace
# ============================================================

class AuthManager:
    """
    Jediné místo, které řeší autentizaci FCM.

    FCM core neví, zda login proběhl přes Firefox,
    Chromium, Chrome, Brave, Vivaldi nebo Edge.
    """

    AUTH_FORMAT_VERSION = 1

    BROWSER_BACKENDS = (
        {
            "id": "firefox",
            "name": "Firefox",
            "cookie_browser": "firefox",
            "engine": "firefox",
            "commands": ("firefox",),
            "flatpak_ids": (
                "org.mozilla.firefox",
            ),
        },
        {
            "id": "chrome",
            "name": "Google Chrome",
            "cookie_browser": "chrome",
            "engine": "chromium",
            "commands": (
                "google-chrome",
                "google-chrome-stable",
            ),
            "flatpak_ids": (
                "com.google.Chrome",
            ),
        },
        {
            "id": "chromium",
            "name": "Chromium",
            "cookie_browser": "chromium",
            "engine": "chromium",
            "commands": (
                "chromium",
                "chromium-browser",
            ),
            "flatpak_ids": (
                "org.chromium.Chromium",
            ),
        },
        {
            "id": "brave",
            "name": "Brave",
            "cookie_browser": "brave",
            "engine": "chromium",
            "commands": (
                "brave-browser",
                "brave",
            ),
            "flatpak_ids": (
                "com.brave.Browser",
            ),
        },
        {
            "id": "vivaldi",
            "name": "Vivaldi",
            "cookie_browser": "vivaldi",
            "engine": "chromium",
            "commands": (
                "vivaldi",
                "vivaldi-stable",
            ),
            "flatpak_ids": (
                "com.vivaldi.Vivaldi",
            ),
        },
        {
            "id": "edge",
            "name": "Microsoft Edge",
            "cookie_browser": "edge",
            "engine": "chromium",
            "commands": (
                "microsoft-edge",
                "microsoft-edge-stable",
            ),
            "flatpak_ids": (
                "com.microsoft.Edge",
            ),
        },
    )

    def __init__(self):
        self.cookie_file = COOKIE_FILE
        self.state_file = AUTH_STATE_FILE
        self.profiles_dir = AUTH_PROFILES_DIR
        self._ensure_storage()

    def _ensure_storage(self):
        os.makedirs(
            AUTH_DIR,
            exist_ok=True,
        )

        os.makedirs(
            self.profiles_dir,
            exist_ok=True,
        )

        for directory in (
            AUTH_DIR,
            self.profiles_dir,
        ):
            try:
                os.chmod(
                    directory,
                    0o700,
                )
            except OSError:
                pass

        for path in (
            self.cookie_file,
            self.state_file,
            LEGACY_AUTH_FILE,
        ):
            if not os.path.exists(
                path
            ):
                continue

            try:
                os.chmod(
                    path,
                    0o600,
                )
            except OSError:
                pass

    def _read_json(
        self,
        path,
        default=None,
    ):
        try:
            with open(
                path,
                "r",
                encoding="utf-8",
            ) as handle:
                return json.load(
                    handle
                )
        except Exception:
            return default

    def _write_json_private(
        self,
        path,
        value,
    ):
        tmp_path = path + ".tmp"

        with open(
            tmp_path,
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                value,
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")

        try:
            os.chmod(
                tmp_path,
                0o600,
            )
        except OSError:
            pass

        os.replace(
            tmp_path,
            path,
        )

        try:
            os.chmod(
                path,
                0o600,
            )
        except OSError:
            pass

    def _state(self):
        state = self._read_json(
            self.state_file,
            default={},
        )

        if not isinstance(
            state,
            dict,
        ):
            return {}

        return state

    # --------------------------------------------------------
    # Browser detection
    # --------------------------------------------------------

    def _installed_flatpaks(self):
        flatpak = shutil.which(
            "flatpak"
        )

        if not flatpak:
            return set()

        try:
            result = subprocess.run(
                [
                    flatpak,
                    "list",
                    "--app",
                    "--columns=application",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except Exception:
            return set()

        if result.returncode != 0:
            return set()

        return {
            line.strip()
            for line in (
                result.stdout
                or ""
            ).splitlines()
            if line.strip()
        }

    def detect_browsers(self):
        found = []
        flatpaks = (
            self._installed_flatpaks()
        )

        for definition in (
            self.BROWSER_BACKENDS
        ):
            backend = None

            for command in (
                definition["commands"]
            ):
                executable = (
                    shutil.which(
                        command
                    )
                )

                if executable:
                    backend = dict(
                        definition
                    )
                    backend.update(
                        {
                            "launcher": "native",
                            "executable": (
                                executable
                            ),
                            "flatpak_id": None,
                        }
                    )
                    break

            if backend is None:
                for app_id in (
                    definition[
                        "flatpak_ids"
                    ]
                ):
                    if app_id not in flatpaks:
                        continue

                    backend = dict(
                        definition
                    )
                    backend.update(
                        {
                            "launcher": "flatpak",
                            "executable": (
                                shutil.which(
                                    "flatpak"
                                )
                            ),
                            "flatpak_id": (
                                app_id
                            ),
                        }
                    )
                    break

            if backend is not None:
                found.append(
                    backend
                )

        return found

    def _default_desktop_browser_id(
        self,
    ):
        xdg_settings = shutil.which(
            "xdg-settings"
        )

        if not xdg_settings:
            return None

        try:
            result = subprocess.run(
                [
                    xdg_settings,
                    "get",
                    "default-web-browser",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except Exception:
            return None

        if result.returncode != 0:
            return None

        desktop_file = (
            result.stdout
            or ""
        ).strip().lower()

        mappings = (
            (
                "firefox",
                ("firefox", "mozilla"),
            ),
            (
                "chrome",
                (
                    "google-chrome",
                    "chrome",
                ),
            ),
            (
                "chromium",
                ("chromium",),
            ),
            (
                "brave",
                ("brave",),
            ),
            (
                "vivaldi",
                ("vivaldi",),
            ),
            (
                "edge",
                (
                    "microsoft-edge",
                    "edge",
                ),
            ),
        )

        for backend_id, needles in mappings:
            if any(
                needle in desktop_file
                for needle in needles
            ):
                return backend_id

        return None

    def _choose_backend(self):
        browsers = (
            self.detect_browsers()
        )

        if not browsers:
            return None

        state = self._state()

        remembered = state.get(
            "browser_id"
        )

        if remembered:
            for backend in browsers:
                if (
                    backend["id"]
                    == remembered
                ):
                    return backend

        default_id = (
            self._default_desktop_browser_id()
        )

        if default_id:
            for backend in browsers:
                if (
                    backend["id"]
                    == default_id
                ):
                    return backend

        return browsers[0]

    # --------------------------------------------------------
    # Isolated login profile
    # --------------------------------------------------------

    def _profile_root(
        self,
        backend,
    ):
        return os.path.join(
            self.profiles_dir,
            backend["id"],
        )

    def _cookie_profile_path(
        self,
        backend,
    ):
        root = self._profile_root(
            backend
        )

        if (
            backend["engine"]
            == "firefox"
        ):
            return root

        return os.path.join(
            root,
            "Default",
        )

    def _ensure_profile_permissions(
        self,
        backend,
    ):
        root = self._profile_root(
            backend
        )

        os.makedirs(
            root,
            exist_ok=True,
        )

        try:
            os.chmod(
                root,
                0o700,
            )
        except OSError:
            pass

    def _launcher_prefix(
        self,
        backend,
    ):
        if (
            backend["launcher"]
            == "native"
        ):
            return [
                backend["executable"]
            ]

        return [
            backend["executable"],
            "run",
            (
                "--filesystem="
                + AUTH_DIR
            ),
            backend["flatpak_id"],
        ]

    def _launch_command(
        self,
        backend,
    ):
        root = self._profile_root(
            backend
        )

        command = (
            self._launcher_prefix(
                backend
            )
        )

        if (
            backend["engine"]
            == "firefox"
        ):
            command.extend(
                [
                    "--no-remote",
                    "--profile",
                    root,
                    YTM_LOGIN_URL,
                ]
            )
        else:
            command.extend(
                [
                    (
                        "--user-data-dir="
                        + root
                    ),
                    (
                        "--profile-directory="
                        "Default"
                    ),
                    # Izolovaný profil je privátní a FCM
                    # z něj stejně exportuje cookies.txt 0600.
                    # Basic store odstraní rozdíly GNOME/KWallet.
                    "--password-store=basic",
                    "--no-first-run",
                    "--no-default-browser-check",
                    YTM_LOGIN_URL,
                ]
            )

        return command

    # --------------------------------------------------------
    # Cookies
    # --------------------------------------------------------

    def _youtube_cookie(
        self,
        cookie,
    ):
        domain = (
            cookie.domain
            or ""
        ).lstrip(
            "."
        ).lower()

        return (
            domain == "youtube.com"
            or domain.endswith(
                ".youtube.com"
            )
        )

    def _extract_cookies(
        self,
        backend,
    ):
        """
        Cookie DB browseru neparsujeme sami.
        Použijeme cookie loader z yt-dlp a uložíme
        pouze youtube.com cookies do vlastního jaru FCM.
        """

        profile_path = (
            self._cookie_profile_path(
                backend
            )
        )

        if (
            backend["engine"]
            == "chromium"
        ):
            browser_spec = (
                backend[
                    "cookie_browser"
                ],
                profile_path,
                "basictext",
                None,
            )
        else:
            browser_spec = (
                backend[
                    "cookie_browser"
                ],
                profile_path,
                None,
                None,
            )

        options = {
            "quiet": True,
            "no_warnings": True,
            "cookiesfrombrowser": (
                browser_spec
            ),
        }

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:
            source_jar = ydl.cookiejar

            output_jar = (
                http.cookiejar.MozillaCookieJar(
                    self.cookie_file
                )
            )

            cookie_count = 0

            for cookie in source_jar:
                if not self._youtube_cookie(
                    cookie
                ):
                    continue

                output_jar.set_cookie(
                    cookie
                )
                cookie_count += 1

        if cookie_count <= 0:
            raise RuntimeError(
                "V přihlašovacím profilu "
                "nejsou YouTube cookies."
            )

        output_jar.save(
            ignore_discard=True,
            ignore_expires=True,
        )

        try:
            os.chmod(
                self.cookie_file,
                0o600,
            )
        except OSError:
            pass

        if not self._cookie_value(
            "__Secure-3PAPISID"
        ):
            raise RuntimeError(
                "YouTube Music není přihlášený "
                "(__Secure-3PAPISID chybí)."
            )

    def _load_cookiejar(self):
        if not os.path.isfile(
            self.cookie_file
        ):
            return None

        jar = (
            http.cookiejar.MozillaCookieJar(
                self.cookie_file
            )
        )

        try:
            jar.load(
                ignore_discard=True,
                ignore_expires=True,
            )
        except Exception:
            return None

        return jar

    def _cookie_value(
        self,
        wanted_name,
    ):
        jar = self._load_cookiejar()

        if jar is None:
            return None

        best = None
        best_score = -1

        for cookie in jar:
            if (
                cookie.name
                != wanted_name
            ):
                continue

            if not self._youtube_cookie(
                cookie
            ):
                continue

            score = (
                len(
                    cookie.domain
                    or ""
                )
                + len(
                    cookie.path
                    or "/"
                )
            )

            if score > best_score:
                best = cookie.value
                best_score = score

        return best

    def _cookie_header(self):
        jar = self._load_cookiejar()

        if jar is None:
            raise RuntimeError(
                "FCM cookie session neexistuje."
            )

        candidates = []
        now = int(
            time.time()
        )

        for cookie in jar:
            if not self._youtube_cookie(
                cookie
            ):
                continue

            if (
                cookie.expires
                and cookie.expires < now
            ):
                continue

            candidates.append(
                cookie
            )

        candidates.sort(
            key=lambda cookie: (
                len(
                    cookie.domain
                    or ""
                ),
                len(
                    cookie.path
                    or "/"
                ),
            ),
            reverse=True,
        )

        chosen = {}

        for cookie in candidates:
            if (
                cookie.name
                not in chosen
            ):
                chosen[
                    cookie.name
                ] = cookie.value

        if (
            "__Secure-3PAPISID"
            not in chosen
        ):
            raise RuntimeError(
                "FCM session nemá "
                "__Secure-3PAPISID."
            )

        return "; ".join(
            (
                f"{name}={value}"
            )
            for name, value
            in chosen.items()
        )

    # --------------------------------------------------------
    # Browser API headers
    # --------------------------------------------------------

    def _browser_version(
        self,
        backend,
    ):
        if (
            backend["launcher"]
            != "native"
        ):
            return None

        try:
            result = subprocess.run(
                [
                    backend["executable"],
                    "--version",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except Exception:
            return None

        output = (
            result.stdout
            or result.stderr
            or ""
        )

        match = re.search(
            r"(\d+)(?:\.\d+)?",
            output,
        )

        if not match:
            return None

        return match.group(1)

    def _user_agent(
        self,
        backend=None,
    ):
        state = self._state()

        stored = state.get(
            "user_agent"
        )

        if stored:
            return stored

        if backend is None:
            browser_id = state.get(
                "browser_id"
            )

            if browser_id:
                for candidate in (
                    self.detect_browsers()
                ):
                    if (
                        candidate["id"]
                        == browser_id
                    ):
                        backend = candidate
                        break

        if backend is None:
            return (
                "Mozilla/5.0 "
                "(X11; Linux x86_64; "
                "rv:128.0) "
                "Gecko/20100101 "
                "Firefox/128.0"
            )

        major = (
            self._browser_version(
                backend
            )
        )

        if (
            backend["engine"]
            == "firefox"
        ):
            major = major or "128"

            return (
                "Mozilla/5.0 "
                "(X11; Linux x86_64; "
                f"rv:{major}.0) "
                "Gecko/20100101 "
                f"Firefox/{major}.0"
            )

        major = major or "130"

        return (
            "Mozilla/5.0 "
            "(X11; Linux x86_64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            f"Chrome/{major}.0.0.0 "
            "Safari/537.36"
        )

    def _authorization(
        self,
        cookie_header,
    ):
        sapisid = (
            self._cookie_value(
                "__Secure-3PAPISID"
            )
        )

        if not sapisid:
            raise RuntimeError(
                "Session neobsahuje "
                "__Secure-3PAPISID."
            )

        timestamp = str(
            int(
                time.time()
            )
        )

        raw = (
            timestamp
            + " "
            + sapisid
            + " "
            + YTM_ORIGIN
        )

        digest = hashlib.sha1(
            raw.encode(
                "utf-8"
            )
        ).hexdigest()

        return (
            "SAPISIDHASH "
            + timestamp
            + "_"
            + digest
        )

    def ytmusic_headers(self):
        cookie_header = (
            self._cookie_header()
        )

        return {
            "User-Agent": (
                self._user_agent()
            ),
            "Accept": "*/*",
            "Authorization": (
                self._authorization(
                    cookie_header
                )
            ),
            "Content-Type": (
                "application/json"
            ),
            "X-Goog-AuthUser": "0",
            "Origin": YTM_ORIGIN,
            "x-origin": YTM_ORIGIN,
            "Cookie": cookie_header,
        }

    def yt_dlp_http_headers(self):
        return {
            "User-Agent": (
                self._user_agent()
            ),
        }

    # --------------------------------------------------------
    # Session lifecycle
    # --------------------------------------------------------

    def session_exists(self):
        try:
            return bool(
                self._cookie_value(
                    "__Secure-3PAPISID"
                )
            )
        except Exception:
            return False

    def ensure_session(self):
        if self.session_exists():
            return True

        print()
        print(
            "FCM ještě nemá vlastní "
            "YouTube Music session."
        )

        if os.path.isfile(
            LEGACY_AUTH_FILE
        ):
            print(
                "Starý browser.json z 0.0.16 "
                "už nepotřebuji; nechávám ho "
                "jen jako zálohu."
            )

        answer = input(
            "Otevřít přihlášení FCM? [A/n]: "
        ).strip().lower()

        if answer in (
            "n",
            "ne",
            "no",
        ):
            return False

        return self.login()

    def login(self):
        backend = (
            self._choose_backend()
        )

        if backend is None:
            print()
            print(
                "CHYBA: Nenašel jsem žádný "
                "podporovaný webový prohlížeč."
            )
            print()
            print(
                "Podporuji Firefox, Chromium, "
                "Google Chrome, Brave, Vivaldi "
                "a Microsoft Edge."
            )
            print(
                "Po instalaci některého z nich "
                "stačí FCM spustit znovu."
            )
            return False

        self._ensure_profile_permissions(
            backend
        )

        print()
        print(
            "Pro přihlášení použiji: "
            f"{backend['name']}"
        )

        if (
            backend["launcher"]
            == "flatpak"
        ):
            print(
                "(nalezen jako Flatpak)"
            )

        print()
        print(
            "Otevírám samostatný "
            "přihlašovací profil FCM..."
        )
        print()
        print(
            "1. Přihlas se do YouTube Music."
        )
        print(
            "2. Ověř, že vidíš svou knihovnu."
        )
        print(
            "3. Celé přihlašovací okno zavři."
        )
        print()
        print(
            "Tvůj normální profil prohlížeče "
            "se nepoužívá ani nemění."
        )
        print()

        command = (
            self._launch_command(
                backend
            )
        )

        try:
            result = subprocess.run(
                command,
                check=False,
            )
        except Exception as exc:
            print()
            print(
                "Přihlašovací prohlížeč "
                "se nepodařilo spustit:"
            )
            print(
                f"{type(exc).__name__}: "
                f"{exc}"
            )
            return False

        if (
            result.returncode
            not in (
                0,
                None,
            )
        ):
            print()
            print(
                "Prohlížeč skončil s kódem "
                f"{result.returncode}."
            )

        print(
            "Načítám přihlášení FCM..."
        )

        try:
            self._extract_cookies(
                backend
            )
        except Exception as exc:
            print()
            print(
                "Přihlášení se nepodařilo "
                "převzít z browseru:"
            )
            print(
                f"{type(exc).__name__}: "
                f"{exc}"
            )
            return False

        state = {
            "format": (
                self.AUTH_FORMAT_VERSION
            ),
            "browser_id": (
                backend["id"]
            ),
            "browser_name": (
                backend["name"]
            ),
            "launcher": (
                backend["launcher"]
            ),
            "flatpak_id": (
                backend.get(
                    "flatpak_id"
                )
            ),
            "user_agent": (
                self._user_agent(
                    backend
                )
            ),
            "updated_at": int(
                time.time()
            ),
        }

        self._write_json_private(
            self.state_file,
            state,
        )

        self._ensure_storage()

        print(
            "✓ Vlastní FCM session uložena."
        )
        print(
            "Prohlížeč už při běžném "
            "používání FCM není potřeba."
        )

        return True

    def refresh(self):
        return self.login()


AUTH = AuthManager()


def _try_connect_youtube_music():
    ytmusic = YTMusic(
        AUTH.ytmusic_headers()
    )

    test_playlists = (
        ytmusic.get_library_playlists(
            limit=1
        )
    )

    return (
        ytmusic,
        test_playlists,
    )


def connect_youtube_music():
    if not AUTH.ensure_session():
        return None, None

    print(
        "Přihlašuji k YouTube Music..."
    )

    try:
        (
            ytmusic,
            test_playlists,
        ) = _try_connect_youtube_music()

    except Exception as exc:
        print()
        print(
            "FCM session k YouTube Music "
            "nefunguje:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        print()
        print(
            "Můžeme ji obnovit přes "
            "vlastní přihlašovací profil."
        )

        answer = input(
            "Obnovit přihlášení? [A/n]: "
        ).strip().lower()

        if answer in (
            "n",
            "ne",
            "no",
        ):
            return None, None

        if not AUTH.refresh():
            return None, None

        print()
        print(
            "Zkouším novou session..."
        )

        try:
            (
                ytmusic,
                test_playlists,
            ) = _try_connect_youtube_music()

        except Exception as retry_exc:
            print()
            print(
                "Ani obnovená FCM session "
                "nefunguje:"
            )
            print(
                f"{type(retry_exc).__name__}: "
                f"{retry_exc}"
            )
            return None, None

    if not test_playlists:
        print()
        print(
            "VAROVÁNÍ: YouTube Music vrátil "
            "prázdnou knihovnu playlistů."
        )
        print(
            "Session může být neplatná nebo "
            "může být vybraný jiný Google účet."
        )
        print(
            "FelisMusic bude pokračovat."
        )

    account = {
        "accountName": "YouTube Music",
        "channelHandle": "",
    }

    try:
        info = (
            ytmusic.get_account_info()
        )

        if info:
            account.update(
                info
            )
    except Exception:
        print()
        print(
            "Informace o účtu se nepodařilo "
            "načíst, ale přihlášení funguje."
        )

    name = account.get(
        "accountName",
        "YouTube Music",
    )

    handle = account.get(
        "channelHandle",
        "",
    )

    if handle:
        print(
            f"Přihlášen: {name} {handle}"
        )
    else:
        print(
            f"Přihlášen k: {name}"
        )

    state = AUTH._state()

    browser_name = state.get(
        "browser_name",
        "vlastní browser profil",
    )

    print(
        "Session: vlastní FCM "
        f"({browser_name})"
    )

    return (
        ytmusic,
        account,
    )

# ============================================================
# Fronta
# ============================================================

class PlaybackQueue:

    def __init__(
        self,
        tracks,
        name="Fronta",
        start_index=0,
        source_playlist_id=None,
        shuffle_active=False,
        radio_active=False,
    ):
        self.tracks = usable_tracks(
            tracks
        )

        self.name = name
        self.source_playlist_id = source_playlist_id
        self.shuffle_active = shuffle_active
        self.radio_active = radio_active

        # Když se doplnění Mix/Radio dočasně nepovede,
        # nebudeme server bombardovat každých 0,5 s.
        self.radio_refill_retry_after = 0.0

        if not self.tracks:
            self.index = 0

        elif start_index < 0:
            self.index = 0

        elif start_index >= len(
            self.tracks
        ):
            self.index = (
                len(self.tracks) - 1
            )

        else:
            self.index = start_index

    def empty(self):
        return not self.tracks

    def current(self):
        if self.empty():
            return None

        return self.tracks[self.index]

    def next(self):
        if (
            self.index + 1
            >= len(self.tracks)
        ):
            return False

        self.index += 1
        return True

    def previous(self):
        if self.index <= 0:
            return False

        self.index -= 1
        return True

    def position(self):
        if self.empty():
            return "0/0"

        return (
            f"{self.index + 1}"
            f"/{len(self.tracks)}"
        )

    def count(self):
        return len(self.tracks)


# ============================================================
# Lokální výstup - GStreamer
# ============================================================

class LocalMediaController:
    """
    Malý adaptér nad GStreamer playbin.

    Záměrně napodobuje část rozhraní PyChromecast
    media_controller, kterou už FCM používá. Díky tomu
    nemusíme mít dva zcela oddělené přehrávače.
    """

    is_local = True

    def __init__(self):
        if not GST_AVAILABLE:
            raise RuntimeError(
                "Python GStreamer není k dispozici."
            )

        self.player = Gst.ElementFactory.make(
            "playbin",
            "felismusic-player",
        )

        if self.player is None:
            raise RuntimeError(
                "GStreamer nevytvořil element playbin."
            )

        # Na Linuxu preferujeme explicitní PulseAudio sink. Na dnešním
        # Plasma/PipeWire desktopu jde přes pipewire-pulse, takže se stream
        # objeví v systémovém směšovači a uživatelské přesměrování výstupu
        # (např. HDMI) má stabilní identitu FelisMusic. Pokud pulsesink není
        # nainstalovaný, playbin zůstane u svého automatického výběru.
        self.audio_sink = Gst.ElementFactory.make(
            "pulsesink",
            "felismusic-audio",
        )
        self.audio_sink_name = "pulsesink"

        # Pokud GStreamer Pulse plugin není nainstalovaný, zkusíme nativní
        # PipeWire sink. Teprve potom necháme playbin použít autoaudiosink.
        if self.audio_sink is None:
            self.audio_sink = Gst.ElementFactory.make(
                "pipewiresink",
                "felismusic-audio",
            )
            self.audio_sink_name = "pipewiresink"

        if self.audio_sink is not None:
            try:
                if self.audio_sink.find_property("client-name") is not None:
                    self.audio_sink.set_property(
                        "client-name",
                        "FelisMusic",
                    )
            except Exception:
                pass
            try:
                if self.audio_sink.find_property("stream-properties") is not None:
                    props = Gst.Structure.new_empty("props")
                    props.set_value("media.role", "music")
                    props.set_value("application.name", "FelisMusic")
                    props.set_value(
                        "application.id",
                        "cz.feliscatus.felismusic",
                    )
                    self.audio_sink.set_property(
                        "stream-properties",
                        props,
                    )
            except Exception:
                pass
            try:
                self.player.set_property(
                    "audio-sink",
                    self.audio_sink,
                )
            except Exception:
                self.audio_sink = None

        if self.audio_sink is not None:
            print(
                "FelisMusic lokální audio: "
                f"{self.audio_sink_name} (PipeWire/Pulse)"
            )
        else:
            self.audio_sink_name = "autoaudiosink"
            print("FelisMusic lokální audio: autoaudiosink")

        self.bus = self.player.get_bus()

        self._finished = False
        self._runtime_error = None
        self._last_error_printed = None

        self._status = SimpleNamespace(
            player_state="IDLE",
            idle_reason=None,
            duration=None,
            current_time=0.0,
            adjusted_current_time=0.0,
        )

    def _seconds_from_ns(
        self,
        value,
    ):
        if (
            value is None
            or value < 0
        ):
            return None

        return (
            float(value)
            / float(Gst.SECOND)
        )

    def _poll_bus(self):
        message_mask = (
            Gst.MessageType.ERROR
            | Gst.MessageType.EOS
            | Gst.MessageType.DURATION_CHANGED
            | Gst.MessageType.STATE_CHANGED
        )

        while True:
            message = self.bus.timed_pop_filtered(
                0,
                message_mask,
            )

            if message is None:
                break

            if message.type == Gst.MessageType.EOS:
                self._finished = True
                self._runtime_error = None

                # Audio sink necháme v READY. Pokud uživatel ve Plasma/
                # PipeWire směšovači přesměroval FelisMusic třeba na HDMI,
                # přechod do NULL by stream zrušil a další skladba by vznikla
                # jako nový stream na výchozím zařízení. READY drží route
                # při životě i mezi skladbami.
                self.player.set_state(
                    Gst.State.READY
                )

            elif message.type == Gst.MessageType.ERROR:
                error, debug = message.parse_error()

                self._runtime_error = (
                    str(error)
                )

                self._finished = False

                self.player.set_state(
                    Gst.State.NULL
                )

                error_text = str(error)

                if (
                    error_text
                    != self._last_error_printed
                ):
                    print()
                    print(
                        "⚠ GStreamer chyba přehrávání:"
                    )
                    print(
                        f"  {error_text}"
                    )

                    if debug:
                        print(
                            f"  {debug}"
                        )

                    self._last_error_printed = (
                        error_text
                    )

    def _refresh_status(self):
        self._poll_bus()

        try:
            _, state, _ = self.player.get_state(
                0
            )
        except Exception:
            state = Gst.State.NULL

        if self._runtime_error:
            player_state = "IDLE"
            idle_reason = "ERROR"

        elif self._finished:
            player_state = "IDLE"
            idle_reason = "FINISHED"

        elif state == Gst.State.PLAYING:
            player_state = "PLAYING"
            idle_reason = None

        elif state == Gst.State.PAUSED:
            player_state = "PAUSED"
            idle_reason = None

        elif state == Gst.State.READY:
            player_state = "BUFFERING"
            idle_reason = None

        else:
            player_state = "IDLE"
            idle_reason = None

        position = 0.0
        duration = None

        if state in (
            Gst.State.PLAYING,
            Gst.State.PAUSED,
            Gst.State.READY,
        ):
            try:
                ok, position_ns = (
                    self.player.query_position(
                        Gst.Format.TIME
                    )
                )

                if ok:
                    value = self._seconds_from_ns(
                        position_ns
                    )

                    if value is not None:
                        position = value

            except Exception:
                pass

            try:
                ok, duration_ns = (
                    self.player.query_duration(
                        Gst.Format.TIME
                    )
                )

                if ok:
                    duration = (
                        self._seconds_from_ns(
                            duration_ns
                        )
                    )

            except Exception:
                pass

        self._status.player_state = (
            player_state
        )
        self._status.idle_reason = (
            idle_reason
        )
        self._status.duration = (
            duration
        )
        self._status.current_time = (
            position
        )
        self._status.adjusted_current_time = (
            position
        )

        return self._status

    @property
    def status(self):
        return self._refresh_status()

    def update_status(self):
        return self._refresh_status()

    def play_media(
        self,
        url,
        content_type=None,
        title=None,
        stream_type=None,
    ):
        del content_type
        del title
        del stream_type

        self.player.set_state(
            Gst.State.READY
        )
        try:
            self.player.get_state(
                2 * Gst.SECOND
            )
        except Exception:
            pass

        self._finished = False
        self._runtime_error = None
        self._last_error_printed = None

        self.player.set_property(
            "uri",
            url,
        )

        result = self.player.set_state(
            Gst.State.PLAYING
        )

        if (
            result
            == Gst.StateChangeReturn.FAILURE
        ):
            self.player.set_state(
                Gst.State.NULL
            )

            raise RuntimeError(
                "GStreamer odmítl spustit stream."
            )

    def play_media_at(
        self,
        url,
        content_type=None,
        title=None,
        stream_type=None,
        position=0.0,
        paused=False,
    ):
        """
        Spustí lokální stream rovnou na požadované pozici.

        Důležitý rozdíl proti play_media()+seek():
        pipeline nejprve prerollujeme do PAUSED, provedeme seek
        ještě bez zvuku a teprve potom přejdeme do PLAYING.
        Tím se při Cast -> Local neozve začátek skladby a seek
        má mnohem větší šanci uspět.
        """

        del content_type
        del title
        del stream_type

        self.player.set_state(
            Gst.State.READY
        )

        try:
            self.player.get_state(
                2 * Gst.SECOND
            )
        except Exception:
            pass

        self._finished = False
        self._runtime_error = None
        self._last_error_printed = None

        self.player.set_property(
            "uri",
            url,
        )

        result = self.player.set_state(
            Gst.State.PAUSED
        )

        if result == Gst.StateChangeReturn.FAILURE:
            self.player.set_state(
                Gst.State.NULL
            )
            raise RuntimeError(
                "GStreamer odmítl připravit stream."
            )

        # Počkáme na preroll. get_state() zde čeká i na dokončení
        # asynchronní změny stavu.
        result, state, pending = self.player.get_state(
            15 * Gst.SECOND
        )

        self._poll_bus()

        if self._runtime_error:
            self.player.set_state(
                Gst.State.NULL
            )
            raise RuntimeError(
                self._runtime_error
            )

        if state not in (
            Gst.State.PAUSED,
            Gst.State.PLAYING,
        ):
            self.player.set_state(
                Gst.State.NULL
            )
            raise RuntimeError(
                "GStreamer stream nepřipravil "
                "do stavu PAUSED."
            )

        position = max(
            0.0,
            float(position),
        )

        if position >= 1.0:
            self.seek(
                position,
                timeout=10,
            )

        if paused:
            return

        result = self.player.set_state(
            Gst.State.PLAYING
        )

        if result == Gst.StateChangeReturn.FAILURE:
            self.player.set_state(
                Gst.State.NULL
            )
            raise RuntimeError(
                "GStreamer odmítl spustit stream."
            )


    def block_until_active(
        self,
        timeout=15,
        cancelled=None,
    ):
        deadline = (
            time.monotonic()
            + float(timeout)
        )

        while (
            time.monotonic()
            < deadline
        ):
            if cancelled is not None and cancelled():
                return
            status = self.status

            if status.player_state in (
                "PLAYING",
                "PAUSED",
            ):
                return

            if status.idle_reason == "ERROR":
                raise RuntimeError(
                    self._runtime_error
                    or "GStreamer chyba přehrávání."
                )

            time.sleep(
                0.05
            )

        raise RuntimeError("GStreamer nespustil audio včas.")

    def pause(self):
        self._finished = False

        self.player.set_state(
            Gst.State.PAUSED
        )

    def play(self):
        self._finished = False
        self._runtime_error = None

        self.player.set_state(
            Gst.State.PLAYING
        )

    def stop(self, *, keep_output=False):
        self.player.set_state(
            Gst.State.READY if keep_output else Gst.State.NULL
        )

        # GStreamer změnu stavu provádí asynchronně.
        # READY při přepnutí zastaví audio a zachová směrování výstupu.
        # Při ukončení procesu nechceme zahodit playbin,
        # dokud jeho interní elementy ještě zůstávají PLAYING.
        try:
            self.player.get_state(
                2 * Gst.SECOND
            )
        except Exception:
            pass

        self._finished = False
        self._runtime_error = None

        self._status.player_state = "IDLE"
        self._status.idle_reason = None
        self._status.current_time = 0.0
        self._status.adjusted_current_time = 0.0

    def seek(
        self,
        seconds,
        timeout=10,
    ):
        """
        Seek u HTTP streamu nemusí být možný přesně v okamžiku,
        kdy playbin přejde do PLAYING. Při přepnutí Cast -> Local
        proto několik sekund počkáme, než zdroj začne seek přijímat.
        """

        seconds = max(
            0.0,
            float(seconds),
        )

        target = int(
            seconds
            * Gst.SECOND
        )

        deadline = (
            time.monotonic()
            + float(timeout)
        )

        last_error = None

        while (
            time.monotonic()
            < deadline
        ):
            self._poll_bus()

            if self._runtime_error:
                raise RuntimeError(
                    self._runtime_error
                )

            # Pokud pipeline už umí odpovědět na seeking query,
            # víme, zda TIME seek podporuje.
            try:
                query = Gst.Query.new_seeking(
                    Gst.Format.TIME
                )

                if self.player.query(query):
                    (
                        fmt,
                        seekable,
                        start,
                        end,
                    ) = query.parse_seeking()

                    if not seekable:
                        time.sleep(
                            0.25
                        )
                        continue

            except Exception as exc:
                last_error = exc

            # Nejprve přesný seek.
            try:
                ok = self.player.seek_simple(
                    Gst.Format.TIME,
                    (
                        Gst.SeekFlags.FLUSH
                        | Gst.SeekFlags.ACCURATE
                    ),
                    target,
                )
            except Exception as exc:
                ok = False
                last_error = exc

            if ok:
                return

            # Některé HTTP zdroje přijmou KEY_UNIT lépe než ACCURATE.
            try:
                ok = self.player.seek_simple(
                    Gst.Format.TIME,
                    (
                        Gst.SeekFlags.FLUSH
                        | Gst.SeekFlags.KEY_UNIT
                    ),
                    target,
                )
            except Exception as exc:
                ok = False
                last_error = exc

            if ok:
                return

            # Poslední varianta: explicitní seek event.
            try:
                ok = self.player.seek(
                    1.0,
                    Gst.Format.TIME,
                    Gst.SeekFlags.FLUSH,
                    Gst.SeekType.SET,
                    target,
                    Gst.SeekType.NONE,
                    -1,
                )
            except Exception as exc:
                ok = False
                last_error = exc

            if ok:
                return

            time.sleep(
                0.25
            )

        if last_error is not None:
            raise RuntimeError(
                f"GStreamer seek selhal po všech "
                f"variantách: {last_error}"
            )

        raise RuntimeError(
            "GStreamer seek selhal po všech variantách "
            "(zdroj stále není seekovatelný)."
        )


class LocalOutput:
    """
    Objekt kompatibilní s částí PyChromecast API,
    kterou používá FCM.
    """

    is_local = True

    def __init__(self):
        self.cast_info = SimpleNamespace(
            friendly_name="Toto zařízení",
            model_name="GStreamer",
            cast_type="local",
        )

        self.media_controller = (
            LocalMediaController()
        )

    def wait(
        self,
        timeout=15,
    ):
        del timeout
        return True

    @property
    def status(self):
        player = (
            self.media_controller.player
        )

        try:
            volume = float(
                player.get_property(
                    "volume"
                )
            )
        except Exception:
            volume = 1.0

        volume = max(
            0.0,
            min(
                1.0,
                volume,
            ),
        )

        try:
            muted = bool(
                player.get_property(
                    "mute"
                )
            )
        except Exception:
            muted = False

        return SimpleNamespace(
            volume_level=volume,
            volume_muted=muted,
        )

    def set_volume(
        self,
        level,
    ):
        level = max(
            0.0,
            min(
                1.0,
                float(level),
            ),
        )

        self.media_controller.player.set_property(
            "volume",
            level,
        )

        return level

    def volume_up(
        self,
        delta,
    ):
        return self.set_volume(
            self.status.volume_level
            + float(delta)
        )

    def volume_down(
        self,
        delta,
    ):
        return self.set_volume(
            self.status.volume_level
            - float(delta)
        )

    def set_volume_muted(
        self,
        muted,
    ):
        self.media_controller.player.set_property(
            "mute",
            bool(muted),
        )

        return bool(muted)


def create_local_output():
    if not GST_AVAILABLE:
        return None

    try:
        return LocalOutput()

    except Exception as exc:
        print()
        print(
            "Lokální GStreamer výstup "
            "se nepodařilo připravit:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return None


# ============================================================
# Chromecast discovery
# ============================================================

def find_casts():
    """
    Najde všechna Cast zařízení na aktuální síti.

    Žádný seznam názvů ani IP adres. PyChromecast provede běžné
    mDNS/zeroconf discovery a FCM si potom nechá jen audio/group.

    Browser zůstává po celou dobu FCM spuštěný, takže jeho
    browser.devices průběžně reaguje na zapnutí/vypnutí Castů.
    """

    print(
        "Hledám Cast zařízení..."
    )

    try:
        (
            chromecasts,
            browser,
        ) = pychromecast.get_chromecasts()

    except Exception as exc:
        print()
        print(
            "Chyba při hledání "
            "Cast zařízení:"
        )
        print(
            f"{type(exc).__name__}: {exc}"
        )

        return [], None

    usable = [
        cast
        for cast in chromecasts
        if cast.cast_info.cast_type
        in (
            "audio",
            "group",
        )
    ]

    usable.sort(
        key=lambda cast:
        (
            cast.cast_info.friendly_name
            or ""
        ).casefold()
    )

    return (
        usable,
        browser,
    )


def cast_uuid(output):
    if output is None:
        return None

    if getattr(
        output,
        "is_local",
        False,
    ):
        return None

    try:
        return output.cast_info.uuid
    except Exception:
        return None


def same_output(
    first,
    second,
):
    if first is second:
        return True

    if (
        first is None
        or second is None
    ):
        return False

    first_local = getattr(
        first,
        "is_local",
        False,
    )

    second_local = getattr(
        second,
        "is_local",
        False,
    )

    if first_local or second_local:
        return (
            first_local
            and second_local
        )

    first_uuid = cast_uuid(
        first
    )

    second_uuid = cast_uuid(
        second
    )

    return (
        first_uuid is not None
        and first_uuid == second_uuid
    )


class OutputState:
    """
    Živý stav audio výstupů.

    PyChromecast browser běží po celou dobu aplikace. Při každém
    stisku "o" FCM sestaví nový snapshot browser.devices:

      - nově zapnutý Cast se objeví,
      - vypnutý Cast po zmizení z discovery nabídky zmizí,
      - názvy ani IP nejsou nikde natvrdo.

    Lokální GStreamer objekt je persistentní.
    """

    def __init__(
        self,
        browser,
        initial_chromecasts,
    ):
        self.browser = browser
        self.local_output = (
            create_local_output()
        )

        self.cast_cache = {
            cast_uuid(cast): cast
            for cast in initial_chromecasts
            if cast_uuid(cast) is not None
        }

        self.outputs = []
        self.current = None

        # pychromecast.get_chromecasts() používá pro první
        # blocking discovery krátké okno. Browser ale po návratu
        # dál živě poslouchá mDNS. Některé entity (typicky Cast
        # Group) dorazí o něco později než jednotlivé Audio Casty.
        #
        # Před úplně prvním snapshotem proto necháme discovery
        # ještě krátce doběhnout. Ruční refresh "r" zůstává rychlý
        # a používá OUTPUT_REFRESH_SETTLE.
        if self.browser is not None:
            time.sleep(
                OUTPUT_INITIAL_SETTLE
            )

        refresh_outputs(
            self,
            wait=False,
        )


def _browser_devices_snapshot(browser):
    """
    browser.devices mění discovery thread. Uděláme bezpečný snapshot
    s krátkým retry, kdyby se dict právě ve stejný okamžik změnil.
    """

    if browser is None:
        return []

    for _ in range(5):
        try:
            return list(
                browser.devices.values()
            )
        except RuntimeError:
            time.sleep(
                0.05
            )

    return []


def _disconnect_cast_safely(cast):
    if cast is None:
        return

    if getattr(
        cast,
        "is_local",
        False,
    ):
        return

    try:
        cast.disconnect(
            timeout=1
        )
    except Exception:
        pass


def refresh_outputs(
    output_state,
    wait=True,
):
    """
    Obnoví nabídku výstupů z živého PyChromecast browseru.

    wait=True nechá discovery krátkou chvíli doběhnout. Samotný browser
    ale běží průběžně už od startu FCM, takže nejde o nový statický scan.
    """

    if wait:
        print()
        print(
            "Obnovuji Cast zařízení..."
        )

        time.sleep(
            OUTPUT_REFRESH_SETTLE
        )

    browser = (
        output_state.browser
    )

    infos = (
        _browser_devices_snapshot(
            browser
        )
    )

    available_infos = [
        info
        for info in infos
        if info.cast_type
        in (
            "audio",
            "group",
        )
    ]

    available_uuids = {
        info.uuid
        for info in available_infos
    }

    current_uuid = cast_uuid(
        output_state.current
    )

    casts = []

    for info in available_infos:
        uuid = info.uuid

        # Pokud právě na tomto Castu hrajeme, zachováme přesně
        # existující objekt a jeho živou socket/media session.
        if (
            current_uuid is not None
            and uuid == current_uuid
        ):
            cast = (
                output_state.current
            )

        else:
            cast = (
                output_state.cast_cache.get(
                    uuid
                )
            )

        if cast is None:
            try:
                cast = (
                    pychromecast.get_chromecast_from_cast_info(
                        info,
                        browser.zc,
                        tries=1,
                        retry_wait=1,
                        timeout=10,
                    )
                )
            except Exception:
                # Discovery zařízení zná, ale zrovna z něj nedokážeme
                # vytvořit použitelný Chromecast objekt.
                continue

        output_state.cast_cache[
            uuid
        ] = cast

        casts.append(
            cast
        )

    # Zahoď staré, už nedostupné objekty. Aktuální výstup je výjimka:
    # pokud právě zmizel ze sítě, potřebujeme jeho objekt ještě do
    # okamžiku, kdy uživatel přepne jinam.
    stale_uuids = [
        uuid
        for uuid in list(
            output_state.cast_cache
        )
        if (
            uuid not in available_uuids
            and uuid != current_uuid
        )
    ]

    for uuid in stale_uuids:
        stale = (
            output_state.cast_cache.pop(
                uuid,
                None,
            )
        )

        _disconnect_cast_safely(
            stale
        )

    casts.sort(
        key=lambda cast:
        (
            cast.cast_info.friendly_name
            or ""
        ).casefold()
    )

    outputs = []

    if (
        output_state.local_output
        is not None
    ):
        outputs.append(
            output_state.local_output
        )

    outputs.extend(
        casts
    )

    output_state.outputs = (
        outputs
    )

    return outputs


def output_name(output):
    if output is None:
        return "?"

    try:
        return (
            output.cast_info.friendly_name
        )
    except Exception:
        return "?"


def current_output_is_available(
    output_state,
):
    current = (
        output_state.current
    )

    if current is None:
        return False

    if getattr(
        current,
        "is_local",
        False,
    ):
        return True

    current_uuid = cast_uuid(
        current
    )

    return any(
        cast_uuid(output)
        == current_uuid
        for output in output_state.outputs
        if not getattr(
            output,
            "is_local",
            False,
        )
    )


def print_outputs(
    output_state,
    allow_back=False,
):
    outputs = (
        output_state.outputs
    )

    current = (
        output_state.current
    )

    print()
    print(
        "Dostupné audio výstupy:"
    )
    print()

    if not outputs:
        print(
            "  Žádný audio výstup."
        )

    for i, output in enumerate(
        outputs,
        1,
    ):
        info = output.cast_info

        marker = (
            "*"
            if same_output(
                output,
                current,
            )
            else " "
        )

        if (
            getattr(
                info,
                "cast_type",
                None,
            )
            == "local"
        ):
            print(
                f"{marker} {i}: "
                f"{info.friendly_name} "
                f"[{info.model_name}, local]"
            )

        else:
            print(
                f"{marker} {i}: "
                f"{info.friendly_name} "
                f"[{info.model_name}, "
                f"{info.cast_type}]"
            )

    if current is not None:
        print()

        if current_output_is_available(
            output_state
        ):
            print(
                f"* aktuální výstup: "
                f"{output_name(current)}"
            )
        else:
            print(
                f"* poslední výstup: "
                f"{output_name(current)} "
                f"[už není dostupný]"
            )

    print()

    if allow_back:
        print(
            "z: zpět bez změny"
        )

    print(
        "r: znovu obnovit seznam"
    )
    print()


def choose_output(
    output_state,
    allow_back=False,
):
    """
    Dynamický výběr výstupu.

    Při vstupu už output_state obsahuje čerstvý snapshot.
    Příkaz r ho z browser.devices vytvoří znovu.
    """

    while True:
        print_outputs(
            output_state,
            allow_back=allow_back,
        )

        value = input(
            "Vyber výstup: "
        ).strip()

        if (
            allow_back
            and value.lower() == "z"
        ):
            return (
                output_state.current
            )

        if value.lower() == "r":
            refresh_outputs(
                output_state,
                wait=True,
            )
            continue

        try:
            choice = int(
                value
            )

            if (
                1
                <= choice
                <= len(
                    output_state.outputs
                )
            ):
                return (
                    output_state.outputs[
                        choice - 1
                    ]
                )

        except ValueError:
            pass

        print(
            "Neplatná volba."
        )


def prepare_output(output):
    """
    U Castu naváže spojení. Lokální GStreamer nic nepotřebuje.
    """

    if getattr(
        output,
        "is_local",
        False,
    ):
        return True

    print(
        f"Připojuji se k "
        f"{output_name(output)}..."
    )

    output.wait(
        timeout=15
    )

    return True



def stop_output_safely(output):
    if output is None:
        return

    try:
        output.media_controller.stop()
    except Exception:
        pass


def cleanup_local_outputs(outputs):
    """
    Lokální GStreamer playbin patří výhradně FCM.
    Při konci procesu ho vždy explicitně shodíme do NULL,
    i kdyby zůstal po nepovedeném přepnutí jako neaktivní výstup.
    """

    for output in outputs or []:
        if getattr(
            output,
            "is_local",
            False,
        ):
            stop_output_safely(
                output
            )


# ============================================================
# yt-dlp
# ============================================================

def content_type_from_ext(ext):
    if ext == "m4a":
        return "audio/mp4"

    if ext == "webm":
        return "audio/webm"

    if ext == "mp3":
        return "audio/mpeg"

    return "audio/mp4"


def get_audio_stream(video_id):
    """
    Přímá URL pro Chromecast.

    Cast větev zůstává čistě streamovací, bez lokálního proxy
    a bez stahování skladby do FCM.
    """

    youtube_url = (
        "https://music.youtube.com/"
        f"watch?v={video_id}"
    )

    print(
        "Zjišťuji audio stream..."
    )

    options = {
        "format": (
            "140/"
            "bestaudio[ext=m4a]"
            "/bestaudio"
        ),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,

        # Vlastní izolovaná FCM session.
        "cookiefile": COOKIE_FILE,
        "http_headers": (
            AUTH.yt_dlp_http_headers()
        ),
    }

    with yt_dlp.YoutubeDL(
        options
    ) as ydl:

        info = ydl.extract_info(
            youtube_url,
            download=False,
        )

    audio_url = info.get(
        "url"
    )

    if not audio_url:
        raise RuntimeError(
            "yt-dlp nevrátilo "
            "URL audio streamu."
        )

    ext = info.get(
        "ext"
    )

    return (
        audio_url,
        content_type_from_ext(
            ext
        ),
    )


def _touch_local_cache(video_id):
    try:
        LOCAL_CACHE_ORDER.remove(
            video_id
        )
    except ValueError:
        pass

    LOCAL_CACHE_ORDER.append(
        video_id
    )


def _trim_local_cache():
    while (
        len(LOCAL_CACHE_ORDER)
        > LOCAL_CACHE_MAX_FILES
    ):
        old_video_id = (
            LOCAL_CACHE_ORDER.pop(0)
        )

        old_path = (
            LOCAL_AUDIO_CACHE.pop(
                old_video_id,
                None,
            )
        )

        if not old_path:
            continue

        try:
            os.unlink(
                old_path
            )
        except FileNotFoundError:
            pass
        except Exception:
            # Cache je jen optimalizace.
            pass


class AudioPreparationCancelled(Exception):
    """A background audio preparation is no longer needed."""


def get_local_audio_source(video_id, *, cancelled=None, diagnostics=None):
    """
    Seekovatelný zdroj pro GStreamer.

    Přímé googlevideo URL se na Kočičce přehrává, ale GStreamer
    ji reportuje jako neseekovatelnou. Proto lokální větev uloží
    aktuální audio do dočasné cache a GStreamer přehrává file://.

    Cast nadále používá přímou URL.
    """

    if diagnostics is not None:
        diagnostics.audio_begin(video_id)

    def check_cancelled(_progress=None):
        if cancelled is not None and cancelled():
            raise AudioPreparationCancelled()

    check_cancelled()
    cached = LOCAL_AUDIO_CACHE.get(
        video_id
    )

    if (
        cached
        and os.path.isfile(
            cached
        )
    ):
        if diagnostics is not None:
            diagnostics.event("audio.cache_hit")
        _touch_local_cache(
            video_id
        )

        uri = Path(
            cached
        ).resolve().as_uri()

        ext = (
            os.path.splitext(
                cached
            )[1]
            .lstrip(".")
            .lower()
        )

        return (
            uri,
            content_type_from_ext(
                ext
            ),
        )

    youtube_url = (
        "https://music.youtube.com/"
        f"watch?v={video_id}"
    )

    print(
        "Připravuji lokální audio..."
    )

    output_template = os.path.join(
        LOCAL_CACHE_DIR,
        f"{video_id}.%(ext)s",
    )

    options = {
        "format": (
            "140/"
            "bestaudio[ext=m4a]"
            "/bestaudio"
        ),
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,

        "cookiefile": COOKIE_FILE,
        "http_headers": (
            AUTH.yt_dlp_http_headers()
        ),
    }

    if cancelled is not None:
        options["progress_hooks"] = [check_cancelled]

    if diagnostics is not None:
        diagnostic_options = diagnostics.audio_options()
        diagnostic_options["progress_hooks"] = options.get("progress_hooks", []) + diagnostic_options["progress_hooks"]
        options.update(diagnostic_options)

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            if diagnostics is not None:
                diagnostics.instrument_downloader(ydl)
            info = ydl.extract_info(youtube_url, download=True)
            check_cancelled()
            path = ydl.prepare_filename(info)
    except Exception as exc:
        if diagnostics is not None:
            diagnostics.event("audio.failed", error=type(exc).__name__, host=diagnostics.download_host,
                              seconds=round(time.monotonic() - diagnostics.audio_started, 3))
        raise

    # Některé extractory mohou vrátit skutečný filepath
    # přímo v requested_downloads.
    if not os.path.isfile(
        path
    ):
        requested = (
            info.get(
                "requested_downloads"
            )
            or []
        )

        for item in requested:
            candidate = item.get(
                "filepath"
            )

            if (
                candidate
                and os.path.isfile(
                    candidate
                )
            ):
                path = candidate
                break

    if not os.path.isfile(
        path
    ):
        raise RuntimeError(
            "yt-dlp lokální audio stáhlo, "
            "ale FCM nenašlo výsledný soubor."
        )

    LOCAL_AUDIO_CACHE[
        video_id
    ] = path

    _touch_local_cache(
        video_id
    )

    _trim_local_cache()

    ext = (
        os.path.splitext(
            path
        )[1]
        .lstrip(".")
        .lower()
    )

    if diagnostics is not None:
        diagnostics.event("audio.ready", seconds=round(time.monotonic() - diagnostics.audio_started, 3))

    return (
        Path(
            path
        ).resolve().as_uri(),
        content_type_from_ext(
            ext
        ),
    )


def get_playback_source(
    video_id,
    mc,
):
    if getattr(
        mc,
        "is_local",
        False,
    ):
        return get_local_audio_source(
            video_id
        )

    return get_audio_stream(
        video_id
    )


def cleanup_local_cache():
    LOCAL_AUDIO_CACHE.clear()
    LOCAL_CACHE_ORDER.clear()

    try:
        shutil.rmtree(
            LOCAL_CACHE_DIR,
            ignore_errors=True,
        )
    except Exception:
        pass


# ============================================================
# Výpis / výběr skladeb
# ============================================================

def choose_song_index(
    tracks,
    title="Skladby",
    page_size=20,
):
    tracks = usable_tracks(
        tracks
    )

    if not tracks:
        print()
        print(
            "Žádné přehratelné "
            "skladby."
        )

        return None

    page = 0

    total_pages = (
        len(tracks)
        + page_size
        - 1
    ) // page_size

    while True:

        start = (
            page * page_size
        )

        end = min(
            start + page_size,
            len(tracks),
        )

        print()
        print(title)

        print(
            "=" * min(
                len(title),
                60,
            )
        )

        print(
            f"Strana "
            f"{page + 1}"
            f"/{total_pages}"
        )

        print()

        for index in range(
            start,
            end,
        ):
            song = tracks[index]

            (
                first_line,
                second_line,
            ) = song_description(
                song
            )

            print(
                f"{index + 1:4}. "
                f"{first_line}"
            )

            print(
                f"      "
                f"{second_line}"
            )

        print()

        commands = []

        if page > 0:
            commands.append(
                "p=předchozí"
            )

        if page + 1 < total_pages:
            commands.append(
                "d=další"
            )

        commands.append(
            "z=zpět"
        )

        print(
            " | ".join(commands)
        )

        value = menu_input(
            "Vyber číslo: "
        ).lower()

        if value == "z":
            return None

        if (
            value == "d"
            and page + 1
            < total_pages
        ):
            page += 1
            continue

        if (
            value == "p"
            and page > 0
        ):
            page -= 1
            continue

        try:
            choice = int(value)

            if (
                1
                <= choice
                <= len(tracks)
            ):
                return (
                    choice - 1
                )

        except ValueError:
            pass

        print(
            "Neplatná volba."
        )


def choose_generic_index(
    items,
    title,
    line_builder,
    page_size=20,
):
    if not items:
        print()
        print("Nic tu není.")
        return None

    page = 0

    total_pages = (
        len(items)
        + page_size
        - 1
    ) // page_size

    while True:
        start = page * page_size
        end = min(
            start + page_size,
            len(items),
        )

        print()
        print(title)
        print(
            "=" * min(
                len(title),
                60,
            )
        )
        print(
            f"Strana "
            f"{page + 1}/{total_pages}"
        )
        print()

        for index in range(
            start,
            end,
        ):
            print(
                f"{index + 1:4}. "
                f"{line_builder(items[index])}"
            )

        print()

        commands = []

        if page > 0:
            commands.append(
                "p=předchozí"
            )

        if page + 1 < total_pages:
            commands.append(
                "d=další"
            )

        commands.append(
            "z=zpět"
        )

        print(
            " | ".join(commands)
        )

        value = menu_input(
            "Vyber číslo: "
        ).lower()

        if value == "z":
            return None

        if (
            value == "d"
            and page + 1
            < total_pages
        ):
            page += 1
            continue

        if (
            value == "p"
            and page > 0
        ):
            page -= 1
            continue

        try:
            choice = int(value)

            if (
                1
                <= choice
                <= len(items)
            ):
                return choice - 1

        except ValueError:
            pass

        print(
            "Neplatná volba."
        )


# ============================================================
# Search
# ============================================================

SEARCH_TYPE_LABELS = {
    "song": "Skladba",
    "video": "Video",
    "album": "Album",
    "artist": "Interpret",
    "playlist": "Playlist",
    "profile": "Profil",
    "podcast": "Podcast",
    "episode": "Epizoda",
}


def search_result_type(
    item,
    forced_type=None,
):
    if forced_type:
        return forced_type

    result_type = item.get(
        "resultType"
    )

    if result_type:
        return result_type

    video_type = (
        item.get("videoType")
        or ""
    )

    if (
        "PODCAST_EPISODE"
        in video_type
    ):
        return "episode"

    if item.get("videoId"):
        return "song"

    return "unknown"


def search_author_text(item):
    author = item.get(
        "author"
    )

    if isinstance(
        author,
        dict,
    ):
        return (
            author.get("name")
            or ""
        )

    if author:
        return str(author)

    channel = item.get(
        "channel"
    )

    if isinstance(
        channel,
        dict,
    ):
        return (
            channel.get("name")
            or ""
        )

    return ""


def search_result_line(
    item,
    forced_type=None,
):
    result_type = search_result_type(
        item,
        forced_type=forced_type,
    )

    label = SEARCH_TYPE_LABELS.get(
        result_type,
        result_type or "?",
    )

    title = (
        item.get("title")
        or item.get("artist")
        or item.get("name")
        or "Bez názvu"
    )

    # --------------------------------------------------------
    # Skladba / video / podcastová epizoda
    # --------------------------------------------------------

    if result_type in (
        "song",
        "video",
        "episode",
    ):
        artists = artist_names(
            item
        )

        duration = song_duration(
            item
        )

        details = []

        if artists != "?":
            details.append(
                artists
            )

        if duration != "?":
            details.append(
                duration
            )

        album = album_name(
            item
        )

        if album:
            details.append(
                album
            )

        if details:
            return (
                f"[{label}] "
                f"{title} - "
                f"{' | '.join(details)}"
            )

        return (
            f"[{label}] {title}"
        )

    # --------------------------------------------------------
    # Album
    # --------------------------------------------------------

    if result_type == "album":
        details = []

        artist = (
            item.get("artist")
            or ""
        )

        if not artist:
            artists = (
                item.get("artists")
                or []
            )

            artist = ", ".join(
                a.get("name", "?")
                for a in artists
                if isinstance(a, dict)
            )

        if artist:
            details.append(
                str(artist)
            )

        year = item.get(
            "year"
        )

        if year:
            details.append(
                str(year)
            )

        if details:
            return (
                f"[{label}] "
                f"{title} - "
                f"{' | '.join(details)}"
            )

        return (
            f"[{label}] {title}"
        )

    # --------------------------------------------------------
    # Interpret
    # --------------------------------------------------------

    if result_type == "artist":
        subscribers = item.get(
            "subscribers"
        )

        if subscribers:
            return (
                f"[{label}] "
                f"{title} "
                f"[{subscribers}]"
            )

        return (
            f"[{label}] {title}"
        )

    # --------------------------------------------------------
    # Playlist
    # --------------------------------------------------------

    if result_type == "playlist":
        details = []

        author = search_author_text(
            item
        )

        if author:
            details.append(
                author
            )

        count = (
            item.get("itemCount")
            or item.get("count")
        )

        if count:
            details.append(
                f"{count} položek"
            )

        if details:
            return (
                f"[{label}] "
                f"{title} - "
                f"{' | '.join(details)}"
            )

        return (
            f"[{label}] {title}"
        )

    # --------------------------------------------------------
    # Profil
    # --------------------------------------------------------

    if result_type == "profile":
        handle = item.get(
            "name"
        )

        if (
            handle
            and handle != title
        ):
            return (
                f"[{label}] "
                f"{title} - {handle}"
            )

        return (
            f"[{label}] {title}"
        )

    # --------------------------------------------------------
    # Podcast
    # --------------------------------------------------------

    if result_type == "podcast":
        author = search_author_text(
            item
        )

        if author:
            return (
                f"[{label}] "
                f"{title} - {author}"
            )

        return (
            f"[{label}] {title}"
        )

    return (
        f"[{label}] {title}"
    )


def playlist_id_from_item(
    item,
):
    playlist_id = item.get(
        "playlistId"
    )

    if playlist_id:
        return playlist_id

    browse_id = item.get(
        "browseId"
    )

    if not browse_id:
        return None

    # Search výsledky playlistů používají browseId "VL" + playlistId.
    if browse_id.startswith(
        "VL"
    ):
        return browse_id[2:]

    return browse_id


def podcast_id_from_item(
    item,
):
    podcast_id = (
        item.get("podcastId")
        or item.get("playlistId")
    )

    if podcast_id:
        return podcast_id

    browse_id = item.get(
        "browseId"
    )

    if not browse_id:
        return None

    # Podcast browseId má běžně tvar MPSP + playlistId.
    if browse_id.startswith(
        "MPSP"
    ):
        return browse_id[4:]

    if browse_id.startswith(
        "VL"
    ):
        return browse_id[2:]

    return browse_id


def playlist_queue_from_item(
    ytmusic,
    playlist,
):
    playlist_id = playlist_id_from_item(
        playlist
    )

    title = playlist.get(
        "title",
        "Playlist",
    )

    if not playlist_id:
        print()
        print(
            "Playlist nemá playlistId."
        )
        return None

    print()
    print(
        f"Načítám playlist: "
        f"{title}"
    )

    try:
        data = ytmusic.get_playlist(
            playlist_id,
            limit=None,
        )

    except Exception as exc:
        print()
        print(
            "Chyba při načítání "
            "playlistu:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return None

    tracks = usable_tracks(
        data.get("tracks") or []
    )

    if not tracks:
        print()
        print(
            "Playlist je prázdný "
            "nebo nemá přehratelné skladby."
        )
        return None

    return collection_queue_menu(
        data.get("title", title),
        tracks,
        ytmusic=ytmusic,
        source_playlist_id=playlist_id,
    )


def profile_queue_from_item(
    ytmusic,
    profile,
):
    channel_id = profile.get(
        "browseId"
    )

    title = (
        profile.get("title")
        or profile.get("artist")
        or profile.get("name")
        or "Profil"
    )

    if not channel_id:
        print()
        print(
            "Profil nemá browseId."
        )
        return None

    print()
    print(
        f"Načítám profil: {title}"
    )

    try:
        data = ytmusic.get_channel(
            channel_id
        )

    except Exception as exc:
        print()
        print(
            "Tento profil nemá detail, "
            "který FCM zatím umí otevřít."
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return None

    episodes = (
        data.get("episodes")
        or {}
    ).get("results") or []

    episodes = usable_tracks(
        episodes
    )

    if not episodes:
        print()
        print(
            "Profil nemá přehratelné "
            "epizody."
        )
        return None

    return collection_queue_menu(
        data.get("title", title),
        episodes,
    )


def open_search_result(
    ytmusic,
    item,
    forced_type=None,
):
    result_type = search_result_type(
        item,
        forced_type=forced_type,
    )

    # --------------------------------------------------------
    # Přímo přehratelný výsledek
    # --------------------------------------------------------

    if result_type in (
        "song",
        "video",
        "episode",
    ):
        tracks = usable_tracks(
            [item]
        )

        if not tracks:
            print()
            print(
                "Tento výsledek nelze "
                "přehrát."
            )
            return None

        title = SEARCH_TYPE_LABELS.get(
            result_type,
            "Hledání",
        )

        return PlaybackQueue(
            tracks,
            name=f"Hledání - {title}",
        )

    # --------------------------------------------------------
    # Album
    # --------------------------------------------------------

    if result_type == "album":
        return album_queue_from_item(
            ytmusic,
            item,
        )

    # --------------------------------------------------------
    # Interpret
    # --------------------------------------------------------

    if result_type == "artist":
        return artist_detail_queue(
            ytmusic,
            item,
        )

    # --------------------------------------------------------
    # Playlist
    # --------------------------------------------------------

    if result_type == "playlist":
        return playlist_queue_from_item(
            ytmusic,
            item,
        )

    # --------------------------------------------------------
    # Podcast
    # --------------------------------------------------------

    if result_type == "podcast":
        podcast = dict(
            item
        )

        podcast_id = podcast_id_from_item(
            podcast
        )

        if podcast_id:
            podcast["podcastId"] = (
                podcast_id
            )

        return podcast_queue_from_item(
            ytmusic,
            podcast,
        )

    # --------------------------------------------------------
    # Profil - může se objevit ve "Vše".
    # --------------------------------------------------------

    if result_type == "profile":
        return profile_queue_from_item(
            ytmusic,
            item,
        )

    print()
    print(
        "Tento typ výsledku FCM "
        "zatím neumí otevřít:"
    )
    print(
        result_type
    )

    return None


def open_upload_search_result(
    ytmusic,
    item,
):
    """
    Otevře výsledek hledání v nahraných souborech.
    """

    result_type = item.get(
        "resultType"
    )

    browse_id = item.get(
        "browseId"
    )

    if item.get("videoId"):
        tracks = usable_tracks(
            [item]
        )

        if not tracks:
            print()
            print(
                "Tento nahraný soubor "
                "nelze přehrát."
            )
            return None

        return PlaybackQueue(
            tracks,
            name="Hledání - nahrané soubory",
        )

    if (
        result_type == "album"
        or (
            browse_id
            and "privately_owned_release_detail"
            in browse_id
        )
    ):
        return upload_album_queue_from_item(
            ytmusic,
            item,
        )

    if (
        result_type == "artist"
        or (
            browse_id
            and "privately_owned_artist_detail"
            in browse_id
        )
    ):
        return upload_artist_queue_from_item(
            ytmusic,
            item,
        )

    print()
    print(
        "Tento typ výsledku v "
        "nahraných souborech FCM "
        "zatím neumí otevřít."
    )

    return None



def search_results_menu(
    ytmusic,
    query,
    search_filter,
    forced_type,
    heading,
    search_scope=None,
):
    print()
    print(
        f"Hledám: {query}"
    )

    try:
        results = ytmusic.search(
            query,
            filter=search_filter,
            scope=search_scope,
            limit=SEARCH_LIMIT,
        )

    except Exception as exc:
        print()
        print(
            "Chyba při hledání:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return None

    if not results:
        print()
        print(
            "Nic jsem nenašel."
        )
        return None

    while True:
        index = choose_generic_index(
            results,
            f"{heading}: {query}",
            lambda item: search_result_line(
                item,
                forced_type=forced_type,
            ),
        )

        if index is None:
            return None

        if search_scope == "uploads":
            queue = open_upload_search_result(
                ytmusic,
                results[index],
            )
        else:
            queue = open_search_result(
                ytmusic,
                results[index],
                forced_type=forced_type,
            )

        # Pokud uživatel z detailu alba/interpreta/playlistu
        # dal Zpět, vrátíme se na stejné výsledky hledání.
        if queue is None:
            continue

        return queue


def search_queue(ytmusic):
    """
    Rozšířené hledání ve stylu YouTube Music.

    "Vše" používá defaultní YT Music search a podle resultType
    umí otevřít skladbu/video, album, interpreta, playlist,
    podcast i profil.
    """

    search_modes = {
        "1": (
            "Vše",
            None,
            None,
            None,
        ),
        "2": (
            "Skladby",
            "songs",
            "song",
            None,
        ),
        "3": (
            "Alba",
            "albums",
            "album",
            None,
        ),
        "4": (
            "Interpreti",
            "artists",
            "artist",
            None,
        ),
        "5": (
            "Playlisty",
            "playlists",
            "playlist",
            None,
        ),
        "6": (
            "Podcasty",
            "podcasts",
            "podcast",
            None,
        ),
        "7": (
            "Nahrané soubory",
            None,
            None,
            "uploads",
        ),
    }

    while True:
        print()
        print(
            "Hledat"
        )
        print(
            "======"
        )
        print()
        print(
            "1. Vše"
        )
        print(
            "2. Skladby"
        )
        print(
            "3. Alba"
        )
        print(
            "4. Interpreti"
        )
        print(
            "5. Playlisty"
        )
        print(
            "6. Podcasty"
        )
        print(
            "7. Nahrané soubory"
        )
        print(
            "z. Zpět"
        )
        print()

        choice = menu_input(
            "Vyber: "
        )

        if choice.lower() == "z":
            return None

        if choice not in search_modes:
            print(
                "Neplatná volba."
            )
            continue

        (
            heading,
            search_filter,
            forced_type,
            search_scope,
        ) = search_modes[
            choice
        ]

        print()

        query = menu_input(
            "Co hledat "
            "('z' = zpět): "
        )

        if query.lower() == "z":
            continue

        if not query:
            continue

        queue = search_results_menu(
            ytmusic,
            query,
            search_filter,
            forced_type,
            heading,
            search_scope=search_scope,
        )

        if queue is not None:
            return queue



# ============================================================
# Playlisty
# ============================================================

def choose_playlist(ytmusic):
    print()
    print(
        "Načítám playlisty..."
    )

    try:
        playlists = (
            ytmusic.get_library_playlists(
                limit=None
            )
        )

    except Exception as exc:
        print()
        print(
            "Chyba při načítání "
            "playlistů:"
        )

        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return None

    if not playlists:
        print()
        print(
            "YouTube Music nevrátil "
            "žádné playlisty."
        )

        return None

    index = choose_generic_index(
        playlists,
        "Playlisty",
        lambda playlist: (
            f"{'* ' if playlist.get('owned') else ''}"
            f"{playlist.get('title', 'Bez názvu')} "
            f"[{playlist.get('count', '?')}]"
        ),
    )

    if index is None:
        return None

    return playlists[index]


def playlist_queue(ytmusic):
    playlist = choose_playlist(
        ytmusic
    )

    if playlist is None:
        return None

    return playlist_queue_from_item(
        ytmusic,
        playlist,
    )


# ============================================================
# Mixy pro vás
# ============================================================

def is_personalized_mix_item(
    item,
):
    """
    Rozpozná personalizované My Mix / Supermix playlisty bez
    závislosti na textu sekce nebo lokalizovaném názvu v UI.

    YouTube Music pro tuto rodinu používá playlistId začínající
    na RDTMAK. Název samotného mixu se může měnit a lokalizovat,
    playlistId je pro tento účel podstatně stabilnější.
    """

    if not isinstance(
        item,
        dict,
    ):
        return False

    playlist_id = (
        playlist_id_from_item(
            item
        )
    )

    return bool(
        isinstance(
            playlist_id,
            str,
        )
        and playlist_id.startswith(
            "RDTMAK"
        )
    )


def get_personalized_mixes(
    ytmusic,
):
    """
    Vytáhne personalizované mixy z Home feedu YT Music.

    Nehledáme sekci podle názvu "Mixy pro vás" / "Mixed for
    you". Projdeme Home a vezmeme položky s RDTMAK playlistId.
    """

    print()
    print(
        "Načítám mixy pro vás..."
    )

    try:
        home = ytmusic.get_home(
            limit=HOME_MIX_ROWS
        )

    except Exception as exc:
        print()
        print(
            "Chyba při načítání "
            "mixů pro vás:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return []

    mixes = []
    seen_ids = set()

    for section in home or []:
        if not isinstance(
            section,
            dict,
        ):
            continue

        contents = section.get(
            "contents"
        )

        if not isinstance(
            contents,
            list,
        ):
            continue

        for item in contents:
            if not is_personalized_mix_item(
                item
            ):
                continue

            playlist_id = (
                playlist_id_from_item(
                    item
                )
            )

            if playlist_id in seen_ids:
                continue

            seen_ids.add(
                playlist_id
            )

            # Kopie: parser ytmusicapi nechceme měnit in-place.
            mix = dict(
                item
            )
            mix[
                "playlistId"
            ] = playlist_id

            mixes.append(
                mix
            )

    return mixes


def personalized_mix_line(
    mix,
):
    title = (
        mix.get(
            "title"
        )
        or "Mix"
    )

    description = (
        mix.get(
            "description"
        )
        or ""
    )

    if isinstance(
        description,
        list,
    ):
        description = " • ".join(
            str(part)
            for part in description
            if part
        )

    description = str(
        description
    ).strip()

    if (
        description
        and description != title
    ):
        return (
            f"{title} - {description}"
        )

    return title


def personalized_mix_queue_from_item(
    ytmusic,
    mix,
):
    playlist_id = (
        playlist_id_from_item(
            mix
        )
    )

    title = (
        mix.get(
            "title"
        )
        or "Mix pro vás"
    )

    if not playlist_id:
        print()
        print(
            "Mix nemá playlistId."
        )
        return None

    print()
    print(
        f"Načítám mix: {title}"
    )

    try:
        # RDTMAK je dynamický/generated playlist. get_playlist()
        # u těchto ID nemusí fungovat spolehlivě, watch playlist
        # je stejná cesta, kterou YTM používá při stisku Play.
        data = ytmusic.get_watch_playlist(
            playlistId=playlist_id,
            limit=MIX_LIMIT,
        )

    except Exception as exc:
        print()
        print(
            "Chyba při načítání mixu:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return None

    tracks = usable_tracks(
        data.get(
            "tracks"
        ) or []
    )

    if not tracks:
        print()
        print(
            "YouTube Music nevrátilo "
            "žádné skladby z mixu."
        )
        return None

    return collection_queue_menu(
        title,
        tracks,
        ytmusic=ytmusic,
        source_playlist_id=playlist_id,
    )


def personalized_mixes_queue(
    ytmusic,
):
    mixes = get_personalized_mixes(
        ytmusic
    )

    if not mixes:
        print()
        print(
            "YouTube Music teď nevrátilo "
            "žádné personalizované mixy."
        )
        return None

    index = choose_generic_index(
        mixes,
        "Mixy pro vás",
        personalized_mix_line,
    )

    if index is None:
        return None

    return personalized_mix_queue_from_item(
        ytmusic,
        mixes[index],
    )


# ============================================================
# Knihovna - skladby
# ============================================================

def library_songs_queue(
    ytmusic
):
    order = choose_library_order()

    if order == "back":
        return None

    print()
    print(
        "Načítám knihovnu "
        "skladeb..."
    )

    try:
        tracks = (
            ytmusic.get_library_songs(
                limit=LIBRARY_LIMIT,
                order=order,
            )
        )

    except Exception as exc:
        print()
        print(
            "Chyba při načítání "
            "knihovny skladeb:"
        )

        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return None

    tracks = usable_tracks(
        tracks
    )

    return collection_queue_menu(
        "Knihovna - skladby",
        tracks,
    )


# ============================================================
# Knihovna - alba
# ============================================================

def album_line(album):
    title = album.get(
        "title",
        "Bez názvu",
    )

    artists = album.get(
        "artists"
    ) or []

    artist_text = ", ".join(
        artist.get("name", "?")
        for artist in artists
        if isinstance(artist, dict)
    )

    # Search výsledky alb často používají prostý string "artist".
    if not artist_text:
        artist_text = (
            album.get("artist")
            or ""
        )

    year = album.get(
        "year"
    )

    extra = []

    if artist_text:
        extra.append(
            str(artist_text)
        )

    if year:
        extra.append(
            str(year)
        )

    if extra:
        return (
            f"{title} - "
            f"{' | '.join(extra)}"
        )

    return title


def album_queue_from_item(
    ytmusic,
    album,
):
    browse_id = album.get(
        "browseId"
    )

    title = album.get(
        "title",
        "Album",
    )

    if not browse_id:
        print()
        print(
            "Album nemá browseId."
        )
        return None

    print()
    print(
        f"Načítám album: {title}"
    )

    try:
        data = ytmusic.get_album(
            browse_id
        )

    except Exception as exc:
        print()
        print(
            "Chyba při načítání alba:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return None

    tracks = usable_tracks(
        data.get("tracks") or []
    )

    if not tracks:
        print()
        print(
            "Album neobsahuje "
            "přehratelné skladby."
        )
        return None

    return collection_queue_menu(
        data.get("title", title),
        tracks,
        ytmusic=ytmusic,
        source_playlist_id=data.get(
            "audioPlaylistId"
        ),
    )


def library_albums_queue(
    ytmusic
):
    order = choose_library_order()

    if order == "back":
        return None

    print()
    print(
        "Načítám alba..."
    )

    try:
        albums = (
            ytmusic.get_library_albums(
                limit=LIBRARY_LIMIT,
                order=order,
            )
        )

    except Exception as exc:
        print()
        print(
            "Chyba při načítání alb:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return None

    index = choose_generic_index(
        albums,
        "Knihovna - alba",
        album_line,
    )

    if index is None:
        return None

    return album_queue_from_item(
        ytmusic,
        albums[index],
    )


# ============================================================
# Knihovna - interpreti
# ============================================================

def artist_line(artist):
    name = (
        artist.get("artist")
        or artist.get("name")
        or "Bez názvu"
    )

    subscribers = artist.get(
        "subscribers"
    )

    if subscribers:
        return (
            f"{name} "
            f"[{subscribers}]"
        )

    return name


def artist_album_list(
    ytmusic,
    section,
):
    results = section.get(
        "results"
    ) or []

    browse_id = section.get(
        "browseId"
    )

    params = section.get(
        "params"
    )

    if (
        browse_id
        and params
    ):
        try:
            full_results = (
                ytmusic.get_artist_albums(
                    browse_id,
                    params,
                    limit=None,
                )
            )

            if full_results:
                results = full_results

        except Exception:
            # Když plný seznam selže,
            # použijeme top výsledky z get_artist().
            pass

    return results


def artist_action_queue(
    ytmusic,
    artist_name,
    playlist_id,
    mode,
):
    """
    Vytvoří frontu z YT Music akce na stránce interpreta.

    mode:
      "shuffle" -> stejné tlačítko Náhodně jako v YT Music
      "radio"   -> stejné tlačítko Mix / rádio jako v YT Music

    get_artist() vrací pro tato tlačítka přímo shuffleId
    a radioId. Ty pošleme jako playlistId do watch endpointu.
    """

    if not playlist_id:
        print()
        print(
            "YouTube Music pro tohoto interpreta "
            "nevrátilo potřebné playlistId."
        )
        return None

    if mode == "shuffle":
        print()
        print(
            f"🔀 YouTube Music vytváří "
            f"náhodnou frontu interpreta "
            f"{artist_name}..."
        )
    else:
        print()
        print(
            f"📻 YouTube Music vytváří "
            f"Mix / rádio interpreta "
            f"{artist_name}..."
        )

    try:
        data = ytmusic.get_watch_playlist(
            playlistId=playlist_id,
            limit=MIX_LIMIT,
        )

    except Exception as exc:
        print()
        print(
            (
                "Náhodnou frontu interpreta "
                "se nepodařilo vytvořit:"
            )
            if mode == "shuffle"
            else (
                "Mix / rádio interpreta "
                "se nepodařilo vytvořit:"
            )
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return None

    tracks = usable_tracks(
        data.get("tracks") or []
    )

    if not tracks:
        print()
        print(
            "YouTube Music nevrátilo "
            "žádné přehratelné skladby."
        )
        return None

    if mode == "shuffle":
        print(
            f"🔀 Náhodná fronta interpreta: "
            f"{len(tracks)} skladeb"
        )

        return PlaybackQueue(
            tracks,
            name=(
                f"{artist_name} - Náhodně"
            ),
            start_index=0,
            shuffle_active=True,
            radio_active=False,
        )

    print(
        f"📻 Mix / rádio interpreta: "
        f"{len(tracks)} skladeb"
    )

    return PlaybackQueue(
        tracks,
        name=(
            f"{artist_name} - Mix / rádio"
        ),
        start_index=0,
        shuffle_active=False,
        radio_active=True,
    )



def artist_detail_queue(
    ytmusic,
    artist,
):
    browse_id = artist.get(
        "browseId"
    )

    if not browse_id:
        print()
        print(
            "Interpret nemá browseId."
        )
        return None

    print()
    print(
        f"Načítám interpreta: "
        f"{artist_line(artist)}"
    )

    try:
        data = ytmusic.get_artist(
            browse_id
        )

    except Exception as exc:
        print()
        print(
            "Chyba při načítání "
            "interpreta:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return None

    name = (
        data.get("name")
        or artist.get("artist")
        or "Interpret"
    )

    # Aktuální ytmusicapi vrací tyto dvě hodnoty přímo
    # z tlačítek stránky interpreta. Bereme je přednostně
    # z get_artist(), ale necháváme fallback na položku
    # ze search/library výsledku.
    shuffle_id = (
        data.get("shuffleId")
        or artist.get("shuffleId")
    )

    radio_id = (
        data.get("radioId")
        or artist.get("radioId")
    )

    while True:
        print()
        print(name)
        print(
            "=" * min(
                len(name),
                60,
            )
        )
        print()
        print(
            "1. Hrát náhodně "
            "(YouTube Music)"
        )
        print(
            "2. Mix / rádio "
            "(YouTube Music)"
        )
        print("3. Top skladby")
        print("4. Alba")
        print("5. Singly")
        print("z. Zpět")
        print()

        choice = menu_input(
            "Vyber: "
        )

        if choice == "1":
            queue = artist_action_queue(
                ytmusic,
                name,
                shuffle_id,
                mode="shuffle",
            )

            if queue is not None:
                return queue

        elif choice == "2":
            queue = artist_action_queue(
                ytmusic,
                name,
                radio_id,
                mode="radio",
            )

            if queue is not None:
                return queue

        elif choice == "3":
            songs = (
                data.get("songs")
                or {}
            ).get("results") or []

            songs = usable_tracks(
                songs
            )

            if not songs:
                print()
                print(
                    "YouTube Music nevrátil "
                    "žádné top skladby."
                )
                continue

            queue = collection_queue_menu(
                f"{name} - top skladby",
                songs,
            )

            if queue is not None:
                return queue

        elif choice in (
            "4",
            "5",
        ):
            section_name = (
                "albums"
                if choice == "4"
                else "singles"
            )

            section = (
                data.get(section_name)
                or {}
            )

            albums = artist_album_list(
                ytmusic,
                section,
            )

            if not albums:
                print()
                print(
                    "V této části nic není."
                )
                continue

            title = (
                f"{name} - "
                f"{'alba' if choice == '4' else 'singly'}"
            )

            index = choose_generic_index(
                albums,
                title,
                album_line,
            )

            if index is None:
                continue

            queue = album_queue_from_item(
                ytmusic,
                albums[index],
            )

            if queue is not None:
                return queue

        elif choice.lower() == "z":
            return None

        else:
            print(
                "Neplatná volba."
            )



def library_artists_queue(
    ytmusic
):
    order = choose_library_order()

    if order == "back":
        return None

    print()
    print(
        "Načítám interprety..."
    )

    try:
        artists = (
            ytmusic.get_library_artists(
                limit=LIBRARY_LIMIT,
                order=order,
            )
        )

    except Exception as exc:
        print()
        print(
            "Chyba při načítání "
            "interpretů:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return None

    index = choose_generic_index(
        artists,
        "Knihovna - interpreti",
        artist_line,
    )

    if index is None:
        return None

    return artist_detail_queue(
        ytmusic,
        artists[index],
    )


# ============================================================
# Knihovna - nahrané soubory
# ============================================================

def upload_album_queue_from_item(
    ytmusic,
    album,
):
    browse_id = album.get(
        "browseId"
    )

    title = album.get(
        "title",
        "Nahrané album",
    )

    if not browse_id:
        print()
        print(
            "Nahrané album nemá browseId."
        )
        return None

    print()
    print(
        f"Načítám nahrané album: "
        f"{title}"
    )

    try:
        data = (
            ytmusic.get_library_upload_album(
                browse_id
            )
        )

    except Exception as exc:
        print()
        print(
            "Chyba při načítání "
            "nahraného alba:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return None

    tracks = usable_tracks(
        data.get("tracks") or []
    )

    if not tracks:
        print()
        print(
            "Album nemá přehratelné "
            "nahrané skladby."
        )
        return None

    return collection_queue_menu(
        data.get("title", title),
        tracks,
        ytmusic=ytmusic,
        source_playlist_id=data.get(
            "audioPlaylistId"
        ),
    )


def upload_artist_line(artist):
    return (
        artist.get("artist")
        or artist.get("name")
        or "Bez názvu"
    )


def upload_artist_queue_from_item(
    ytmusic,
    artist,
):
    browse_id = artist.get(
        "browseId"
    )

    name = upload_artist_line(
        artist
    )

    if not browse_id:
        print()
        print(
            "Nahraný interpret nemá "
            "browseId."
        )
        return None

    print()
    print(
        f"Načítám nahraného "
        f"interpreta: {name}"
    )

    try:
        tracks = (
            ytmusic.get_library_upload_artist(
                browse_id,
                limit=LIBRARY_LIMIT,
            )
        )

    except Exception as exc:
        print()
        print(
            "Chyba při načítání "
            "nahraného interpreta:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return None

    tracks = usable_tracks(
        tracks
    )

    return collection_queue_menu(
        f"Nahrané - {name}",
        tracks,
        ytmusic=ytmusic,
    )


def library_upload_songs_queue(
    ytmusic,
):
    order = choose_library_order()

    if order == "back":
        return None

    print()
    print(
        "Načítám nahrané skladby..."
    )

    try:
        tracks = (
            ytmusic.get_library_upload_songs(
                limit=None,
                order=order,
            )
        )

    except Exception as exc:
        print()
        print(
            "Chyba při načítání "
            "nahraných skladeb:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return None

    tracks = usable_tracks(
        tracks
    )

    return collection_queue_menu(
        "Nahrané soubory - skladby",
        tracks,
        ytmusic=ytmusic,
    )


def library_upload_albums_queue(
    ytmusic,
):
    order = choose_library_order()

    if order == "back":
        return None

    print()
    print(
        "Načítám nahraná alba..."
    )

    try:
        albums = (
            ytmusic.get_library_upload_albums(
                limit=None,
                order=order,
            )
        )

    except Exception as exc:
        print()
        print(
            "Chyba při načítání "
            "nahraných alb:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return None

    index = choose_generic_index(
        albums,
        "Nahrané soubory - alba",
        album_line,
    )

    if index is None:
        return None

    return upload_album_queue_from_item(
        ytmusic,
        albums[index],
    )


def library_upload_artists_queue(
    ytmusic,
):
    order = choose_library_order()

    if order == "back":
        return None

    print()
    print(
        "Načítám nahrané interprety..."
    )

    try:
        artists = (
            ytmusic.get_library_upload_artists(
                limit=None,
                order=order,
            )
        )

    except Exception as exc:
        print()
        print(
            "Chyba při načítání "
            "nahraných interpretů:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return None

    index = choose_generic_index(
        artists,
        "Nahrané soubory - interpreti",
        upload_artist_line,
    )

    if index is None:
        return None

    return upload_artist_queue_from_item(
        ytmusic,
        artists[index],
    )


def library_uploads_menu(
    ytmusic,
):
    while True:
        print()
        print(
            "Nahrané soubory"
        )
        print(
            "==============="
        )
        print()
        print(
            "1. Skladby"
        )
        print(
            "2. Alba"
        )
        print(
            "3. Interpreti"
        )
        print(
            "z. Zpět"
        )
        print()

        choice = menu_input(
            "Vyber: "
        ).lower()

        queue = None

        if choice == "1":
            queue = (
                library_upload_songs_queue(
                    ytmusic
                )
            )

        elif choice == "2":
            queue = (
                library_upload_albums_queue(
                    ytmusic
                )
            )

        elif choice == "3":
            queue = (
                library_upload_artists_queue(
                    ytmusic
                )
            )

        elif choice == "z":
            return None

        else:
            print(
                "Neplatná volba."
            )
            continue

        if queue is not None:
            return queue


# ============================================================
# Knihovna - profily / kanály
# ============================================================

def channel_line(channel):
    name = (
        channel.get("artist")
        or channel.get("title")
        or "Bez názvu"
    )

    subscribers = channel.get(
        "subscribers"
    )

    if subscribers:
        return (
            f"{name} "
            f"[{subscribers}]"
        )

    return name


def library_channels_menu(
    ytmusic
):
    order = choose_library_order()

    if order == "back":
        return None

    print()
    print(
        "Načítám profily..."
    )

    try:
        channels = (
            ytmusic.get_library_channels(
                limit=LIBRARY_LIMIT,
                order=order,
            )
        )

    except Exception as exc:
        print()
        print(
            "Chyba při načítání profilů:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return None

    index = choose_generic_index(
        channels,
        "Knihovna - profily",
        channel_line,
    )

    if index is None:
        return None

    channel = channels[index]
    channel_id = channel.get(
        "browseId"
    )

    if not channel_id:
        return None

    # U části profilů může jít o podcastový kanál.
    # Když YouTube vrátí jeho epizody, nabídneme je.
    try:
        data = ytmusic.get_channel(
            channel_id
        )
    except Exception:
        print()
        print(
            "Profil byl načten, ale "
            "pro tento typ kanálu zatím "
            "nemáme další detail."
        )
        menu_input(
            "Enter = zpět..."
        )
        return None

    episodes = (
        data.get("episodes")
        or {}
    ).get("results") or []

    if episodes:
        queue = collection_queue_menu(
            data.get(
                "title",
                channel_line(channel),
            ),
            episodes,
        )

        if queue is not None:
            return queue

    else:
        print()
        print(
            "Profil nemá přehratelné "
            "epizody."
        )
        menu_input(
            "Enter = zpět..."
        )

    return None


# ============================================================
# Knihovna - podcasty
# ============================================================

def podcast_line(podcast):
    title = podcast.get(
        "title",
        "Bez názvu",
    )

    channel = podcast.get(
        "channel"
    ) or {}

    channel_name = (
        channel.get("name")
        if isinstance(
            channel,
            dict,
        )
        else None
    )

    if channel_name:
        return (
            f"{title} - "
            f"{channel_name}"
        )

    return title


def podcast_queue_from_item(
    ytmusic,
    podcast,
):
    playlist_id = podcast_id_from_item(
        podcast
    )

    title = podcast.get(
        "title",
        "Podcast",
    )

    if not playlist_id:
        print()
        print(
            "Podcast nemá podcastId."
        )
        return None

    print()
    print(
        f"Načítám podcast: "
        f"{title}"
    )

    try:
        data = ytmusic.get_podcast(
            playlist_id,
            limit=None,
        )

    except Exception as exc:
        print()
        print(
            "Chyba při načítání "
            "podcastu:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return None

    episodes = (
        data.get("episodes")
        or []
    )

    author = (
        data.get("author")
        or {}
    )

    author_name = (
        author.get("name")
        if isinstance(
            author,
            dict,
        )
        else None
    )

    normalized = []

    for episode in episodes:
        if not isinstance(
            episode,
            dict,
        ):
            continue

        item = dict(
            episode
        )

        if (
            author_name
            and not item.get("artists")
            and not item.get("author")
            and not item.get("channel")
        ):
            item["artists"] = [
                {
                    "name": author_name
                }
            ]

        normalized.append(
            item
        )

    return collection_queue_menu(
        data.get("title", title),
        normalized,
    )


def library_podcasts_queue(
    ytmusic
):
    order = choose_library_order()

    if order == "back":
        return None

    print()
    print(
        "Načítám podcasty..."
    )

    try:
        podcasts = (
            ytmusic.get_library_podcasts(
                limit=LIBRARY_LIMIT,
                order=order,
            )
        )

    except Exception as exc:
        print()
        print(
            "Chyba při načítání "
            "podcastů:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return None

    index = choose_generic_index(
        podcasts,
        "Knihovna - podcasty",
        podcast_line,
    )

    if index is None:
        return None

    return podcast_queue_from_item(
        ytmusic,
        podcasts[index],
    )


# ============================================================
# Oblíbená hudba
# ============================================================

def liked_queue(ytmusic):
    print()
    print(
        "Načítám oblíbenou hudbu..."
    )

    try:
        data = (
            ytmusic.get_liked_songs(
                limit=2000
            )
        )

    except Exception as exc:
        print()
        print(
            "Chyba při načítání "
            "Oblíbená hudba:"
        )

        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return None

    tracks = usable_tracks(
        data.get("tracks") or []
    )

    return collection_queue_menu(
        "Oblíbená hudba",
        tracks,
        ytmusic=ytmusic,
        source_playlist_id="LM",
    )


# ============================================================
# Historie
# ============================================================

def history_queue(ytmusic):
    print()
    print(
        "Načítám historii..."
    )

    try:
        tracks = (
            ytmusic.get_history()
        )

    except Exception as exc:
        print()
        print(
            "Chyba při načítání "
            "historie:"
        )

        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return None

    tracks = usable_tracks(
        tracks
    )

    return collection_queue_menu(
        "Historie",
        tracks,
    )


# ============================================================
# Menu kolekce skladeb
# ============================================================

def youtube_shuffle_supported(
    playlist_id,
):
    """
    Vrátí False pro typy playlistů, u kterých YouTube Music
    nenabízí běžný shuffle endpoint.

    RDCLAK... jsou YouTube Music kurátorované / automatické
    playlisty. Samotný playlist lze normálně přehrát, ale
    get_watch_playlist(..., shuffle=True) pro ně vrací prázdný
    obsah. Ve webovém YTM tomu odpovídá i neaktivní trvalý
    shuffle přepínač ve spodním přehrávači.
    """

    if not playlist_id:
        return False

    return not str(playlist_id).startswith(
        "RDCLAK"
    )


def get_youtube_shuffle_tracks(
    ytmusic,
    playlist_id,
    limit,
):
    """
    Necháme frontu zamíchat přímo YouTube Music.

    Shuffle v ytmusicapi funguje s playlistId.
    U alba používáme jeho audioPlaylistId.
    """

    if not playlist_id:
        raise RuntimeError(
            "Tato fronta nemá YouTube Music playlistId."
        )

    data = ytmusic.get_watch_playlist(
        playlistId=playlist_id,
        limit=max(
            25,
            int(limit or 25),
        ),
        shuffle=True,
    )

    tracks = usable_tracks(
        data.get("tracks") or []
    )

    if not tracks:
        raise RuntimeError(
            "YouTube Music nevrátilo žádnou "
            "náhodnou frontu."
        )

    return tracks


def collection_queue_menu(
    name,
    tracks,
    ytmusic=None,
    source_playlist_id=None,
):
    tracks = usable_tracks(
        tracks
    )

    if not tracks:
        print()
        print(
            "Žádné přehratelné "
            "skladby."
        )

        return None

    has_youtube_shuffle = (
        ytmusic is not None
        and youtube_shuffle_supported(
            source_playlist_id
        )
    )

    while True:

        print()
        print(name)

        print(
            "=" * min(
                len(name),
                60,
            )
        )

        print(
            f"Skladeb: "
            f"{len(tracks)}"
        )

        print()
        print(
            "1. Hrát od začátku"
        )

        print(
            "2. Vybrat skladbu "
            "a pokračovat od ní"
        )

        if has_youtube_shuffle:
            print(
                "3. Hrát náhodně "
                "(YouTube Music)"
            )
            print(
                "z. Zpět"
            )
        else:
            print(
                "z. Zpět"
            )

        print()

        choice = menu_input(
            "Vyber: "
        )

        if choice == "1":

            return PlaybackQueue(
                tracks,
                name=name,
                start_index=0,
                source_playlist_id=source_playlist_id,
            )

        elif choice == "2":

            index = choose_song_index(
                tracks,
                title=name,
            )

            if index is not None:

                return PlaybackQueue(
                    tracks,
                    name=name,
                    start_index=index,
                    source_playlist_id=source_playlist_id,
                )

        elif (
            choice == "3"
            and has_youtube_shuffle
        ):
            print()
            print(
                "YouTube Music míchá frontu..."
            )

            try:
                shuffled_tracks = (
                    get_youtube_shuffle_tracks(
                        ytmusic,
                        source_playlist_id,
                        len(tracks),
                    )
                )

            except Exception as exc:
                print()
                print(
                    "Náhodnou frontu se "
                    "nepodařilo vytvořit:"
                )
                print(
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )
                continue

            print(
                f"🔀 Náhodná fronta: "
                f"{len(shuffled_tracks)} skladeb"
            )

            return PlaybackQueue(
                shuffled_tracks,
                name=name,
                start_index=0,
                source_playlist_id=source_playlist_id,
                shuffle_active=True,
            )

        elif (
            choice.lower() == "z"
            and has_youtube_shuffle
        ):
            return None

        elif (
            choice.lower() == "z"
            and not has_youtube_shuffle
        ):
            return None

        else:
            print(
                "Neplatná volba."
            )


# ============================================================
# Knihovna - hlavní menu
# ============================================================

def library_menu(
    ytmusic
):
    while True:
        print()
        print("Knihovna")
        print("========")
        print()
        print("1. Playlisty")
        print("2. Skladby")
        print("3. Alba")
        print("4. Interpreti")
        print("5. Profily")
        print("6. Podcasty")
        print("7. Nahrané soubory")
        print("z. Zpět")
        print()

        choice = menu_input(
            "Vyber: "
        )

        queue = None

        if choice == "1":
            queue = playlist_queue(
                ytmusic
            )

        elif choice == "2":
            queue = library_songs_queue(
                ytmusic
            )

        elif choice == "3":
            queue = library_albums_queue(
                ytmusic
            )

        elif choice == "4":
            queue = library_artists_queue(
                ytmusic
            )

        elif choice == "5":
            queue = library_channels_menu(
                ytmusic
            )

        elif choice == "6":
            queue = library_podcasts_queue(
                ytmusic
            )

        elif choice == "7":
            queue = library_uploads_menu(
                ytmusic
            )

        elif choice.lower() == "z":
            return None

        else:
            print(
                "Neplatná volba."
            )
            continue

        if queue is not None:
            return queue


# ============================================================
# Playback
# ============================================================

def normalize_like_status(value):
    if hasattr(value, "value"):
        value = value.value

    value = str(
        value or "INDIFFERENT"
    ).upper()

    if value not in (
        "LIKE",
        "DISLIKE",
        "INDIFFERENT",
    ):
        return "INDIFFERENT"

    return value


def ensure_song_like_status(
    ytmusic,
    song,
):
    """
    Většina položek z playlistů, alb a knihovny už obsahuje
    likeStatus. Pokud chybí, zkusíme ho doplnit z watch queue.
    """

    if song.get("likeStatus") is not None:
        song["likeStatus"] = normalize_like_status(
            song.get("likeStatus")
        )
        return song["likeStatus"]

    video_id = song.get("videoId")

    if not video_id:
        song["likeStatus"] = "INDIFFERENT"
        return "INDIFFERENT"

    try:
        data = ytmusic.get_watch_playlist(
            videoId=video_id,
            limit=1,
        )

        for item in data.get("tracks") or []:
            if item.get("videoId") == video_id:
                song["likeStatus"] = normalize_like_status(
                    item.get("likeStatus")
                )
                return song["likeStatus"]

    except Exception:
        pass

    song["likeStatus"] = "INDIFFERENT"
    return "INDIFFERENT"


def like_status_text(song):
    status = normalize_like_status(
        song.get("likeStatus")
    )

    if status == "LIKE":
        return "👍 Oblíbená"

    if status == "DISLIKE":
        return "👎 Neoblíbená"

    return "○ Bez hodnocení"


def format_seconds(value):
    try:
        seconds = max(
            0,
            int(float(value)),
        )
    except (
        TypeError,
        ValueError,
    ):
        return "--:--"

    hours, remainder = divmod(
        seconds,
        3600,
    )

    minutes, seconds = divmod(
        remainder,
        60,
    )

    if hours:
        return (
            f"{hours:d}:"
            f"{minutes:02d}:"
            f"{seconds:02d}"
        )

    return (
        f"{minutes:02d}:"
        f"{seconds:02d}"
    )


def song_duration_seconds(song):
    value = song.get(
        "duration_seconds"
    )

    if value is not None:
        try:
            return float(value)
        except (
            TypeError,
            ValueError,
        ):
            pass

    duration = song.get(
        "duration"
    ) or song.get(
        "length"
    )

    if not isinstance(
        duration,
        str,
    ):
        return None

    try:
        parts = [
            int(part)
            for part in duration.split(":")
        ]
    except ValueError:
        return None

    if len(parts) == 2:
        return (
            parts[0] * 60
            + parts[1]
        )

    if len(parts) == 3:
        return (
            parts[0] * 3600
            + parts[1] * 60
            + parts[2]
        )

    return None


def get_media_position(mc):
    try:
        mc.update_status()
        time.sleep(0.15)
    except Exception:
        pass

    status = mc.status

    try:
        position = (
            status.adjusted_current_time
        )
    except Exception:
        position = status.current_time

    try:
        return max(
            0.0,
            float(position or 0),
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0.0


def print_current_track(
    ytmusic,
    queue,
):
    song = queue.current()

    if song is None:
        return

    ensure_song_like_status(
        ytmusic,
        song,
    )

    (
        first_line,
        second_line,
    ) = song_description(
        song
    )

    print()
    print(
        "=" * 65
    )

    print(
        f"▶ [{queue.position()}] "
        f"{first_line}"
    )

    print(
        f"  {second_line}"
    )

    print(
        f"  Hodnocení: "
        f"{like_status_text(song)}"
    )

    print(
        f"  Fronta: "
        f"{queue.name}"
    )

    print(
        "=" * 65
    )

    print()


def start_current_track(
    ytmusic,
    mc,
    queue,
):
    song = queue.current()

    if song is None:
        raise RuntimeError(
            "Fronta je prázdná."
        )

    video_id = song[
        "videoId"
    ]

    title = song.get(
        "title",
        "?",
    )

    artists = artist_names(
        song
    )

    print_current_track(
        ytmusic,
        queue,
    )

    if (
        SIMULATE_BROKEN_TRACK is not None
        and queue.index + 1
        == SIMULATE_BROKEN_TRACK
    ):
        raise RuntimeError(
            "SIMULACE: skladbu nelze přehrát"
        )

    (
        audio_url,
        content_type,
    ) = get_playback_source(
        video_id,
        mc,
    )

    if getattr(
        mc,
        "is_local",
        False,
    ):
        print(
            "Přehrávám na tomto zařízení..."
        )
    else:
        print(
            "Posílám do Chromecastu..."
        )

    mc.play_media(
        audio_url,
        content_type,
        title=(
            f"{artists} - {title}"
        ),
        stream_type="BUFFERED",
    )

    try:
        mc.block_until_active(
            timeout=15
        )

    except Exception:
        pass

    time.sleep(
        0.5
    )


def start_current_track_with_skip(
    ytmusic,
    mc,
    queue,
    direction=1,
):
    while True:

        song = queue.current()

        if song is None:
            return False

        try:

            start_current_track(
                ytmusic,
                mc,
                queue,
            )

            return True

        except Exception as exc:

            title = song.get(
                "title",
                "?",
            )

            artists = artist_names(
                song
            )

            print()
            print(
                "⚠ Skladbu nelze přehrát:"
            )

            print(
                f"  [{queue.position()}] "
                f"{artists} - {title}"
            )

            print(
                f"  {type(exc).__name__}: "
                f"{exc}"
            )

            print()

            if direction >= 0:

                moved = queue.next()

                if moved:

                    print(
                        "⏭ Přeskakuji na další "
                        "skladbu..."
                    )

            else:

                moved = queue.previous()

                if moved:

                    print(
                        "⏮ Přeskakuji na předchozí "
                        "skladbu..."
                    )

            if not moved:

                print(
                    "⚠ Ve frontě už není "
                    "další přehratelná skladba."
                )

                return False


def switch_playback_output(
    ytmusic,
    output_state,
    queue,
    stopped=False,
):
    """
    Přepne právě hrající skladbu na jiný výstup.

    Postup:
      1. zjistí aktuální pozici a stav
      2. připojí cílový výstup
      3. ještě za běhu starého výstupu získá čerstvou audio URL
      4. zastaví starý výstup
      5. spustí cílový výstup
      6. seekne na původní pozici
      7. zachová PAUSE, pokud byla skladba pozastavená

    Vrací True, pokud se výstup opravdu změnil.
    """

    current_output = (
        output_state.current
    )

    current_mc = (
        current_output.media_controller
    )

    refresh_outputs(
        output_state,
        wait=True,
    )

    target_output = choose_output(
        output_state,
        allow_back=True,
    )

    if same_output(
        target_output,
        current_output,
    ):
        print(
            f"Výstup zůstává: "
            f"{output_name(current_output)}"
        )
        return False

    # Když je přehrávač ručně STOPnutý, stačí změnit výstup.
    # Skladbu znovu spustí až příkaz r.
    if stopped:
        try:
            prepare_output(
                target_output
            )
        except Exception as exc:
            print()
            print(
                "Výstup se nepodařilo "
                "připravit:"
            )
            print(
                f"{type(exc).__name__}: "
                f"{exc}"
            )
            return False

        output_state.current = (
            target_output
        )

        print()
        print(
            f"🔊 Výstup změněn: "
            f"{output_name(target_output)}"
        )
        print(
            "Přehrávání je zastavené; "
            "r ho spustí na novém výstupu."
        )

        return True

    status = current_mc.status

    was_paused = (
        status.player_state
        == "PAUSED"
    )

    was_active = (
        status.player_state
        in (
            "PLAYING",
            "PAUSED",
            "BUFFERING",
        )
    )

    position = get_media_position(
        current_mc
    )

    # Pokud už nic skutečně nehraje, jen změníme aktivní výstup.
    if not was_active:
        try:
            prepare_output(
                target_output
            )
        except Exception as exc:
            print()
            print(
                "Výstup se nepodařilo "
                "připravit:"
            )
            print(
                f"{type(exc).__name__}: "
                f"{exc}"
            )
            return False

        output_state.current = (
            target_output
        )

        print()
        print(
            f"🔊 Výstup změněn: "
            f"{output_name(target_output)}"
        )

        return True

    song = queue.current()

    if song is None:
        return False

    video_id = song.get(
        "videoId"
    )

    if not video_id:
        print(
            "Aktuální skladba nemá videoId."
        )
        return False

    title = song.get(
        "title",
        "?",
    )

    artists = artist_names(
        song
    )

    print()
    print(
        f"🔄 Přepínám "
        f"{output_name(current_output)} "
        f"→ {output_name(target_output)}"
    )
    print(
        f"   Pozice: "
        f"{format_seconds(position)}"
    )

    # Cílový Cast připojíme ještě v době, kdy zdroj dál hraje.
    try:
        prepare_output(
            target_output
        )
    except Exception as exc:
        print()
        print(
            "Přepnutí výstupu selhalo "
            "při připojování:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return False

    # Čerstvou URL získáme ještě před zastavením zdroje.
    try:
        (
            audio_url,
            content_type,
        ) = get_playback_source(
            video_id,
            target_output.media_controller,
        )
    except Exception as exc:
        print()
        print(
            "Přepnutí výstupu selhalo "
            "při získávání streamu:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return False

    target_mc = (
        target_output.media_controller
    )

    # Teprve teď umlčíme původní výstup.
    try:
        current_mc.stop()
    except Exception:
        pass

    try:
        if getattr(
            target_mc,
            "is_local",
            False,
        ):
            # Local připravíme v PAUSED, seekneme beze zvuku
            # a až pak pustíme. Při Cast -> Local tedy nemá
            # krátce zaznít začátek skladby.
            target_mc.play_media_at(
                audio_url,
                content_type,
                title=(
                    f"{artists} - {title}"
                ),
                stream_type="BUFFERED",
                position=position,
                paused=was_paused,
            )

            if not was_paused:
                target_mc.block_until_active(
                    timeout=15
                )

        else:
            target_mc.play_media(
                audio_url,
                content_type,
                title=(
                    f"{artists} - {title}"
                ),
                stream_type="BUFFERED",
            )

            try:
                target_mc.block_until_active(
                    timeout=15
                )
            except Exception:
                pass

            time.sleep(
                0.4
            )

            if position >= 1.0:
                target_mc.seek(
                    position
                )

                time.sleep(
                    0.15
                )

            if was_paused:
                target_mc.pause()

    except Exception as exc:
        print()
        print(
            "⚠ Nový výstup skladbu "
            "nespustil:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        # DŮLEŽITÉ: play_media() už mohlo cílový výstup rozjet.
        # Pokud pak selhal až seek, v 0.0.13 zůstal Local hrát
        # souběžně s obnoveným Chromecastem.
        stop_output_safely(
            target_output
        )

        print(
            "Cílový výstup zastaven."
        )
        print(
            "Pokouším se obnovit "
            "původní výstup..."
        )

        # Best-effort návrat na původní výstup.
        try:
            (
                recovery_url,
                recovery_type,
            ) = get_playback_source(
                video_id,
                current_mc,
            )

            current_mc.play_media(
                recovery_url,
                recovery_type,
                title=(
                    f"{artists} - {title}"
                ),
                stream_type="BUFFERED",
            )

            try:
                current_mc.block_until_active(
                    timeout=15
                )
            except Exception:
                pass

            time.sleep(
                0.4
            )

            if position >= 1.0:
                current_mc.seek(
                    position
                )

            if was_paused:
                current_mc.pause()

            print(
                f"✓ Obnoven původní výstup: "
                f"{output_name(current_output)}"
            )

        except Exception as recovery_exc:
            stop_output_safely(
                target_output
            )

            print(
                "⚠ Nepodařilo se obnovit "
                "ani původní výstup:"
            )
            print(
                f"{type(recovery_exc).__name__}: "
                f"{recovery_exc}"
            )

        return False

    output_state.current = (
        target_output
    )

    print()
    print(
        f"✓ Výstup změněn: "
        f"{output_name(target_output)}"
    )

    if was_paused:
        print(
            f"  Pozice zachována: "
            f"{format_seconds(position)} "
            f"(pozastaveno)"
        )
    else:
        print(
            f"  Pokračuji od: "
            f"{format_seconds(position)}"
        )

    return True



def player_info(
    ytmusic,
    cast,
    queue,
    repeat_mode,
):
    song = queue.current()

    if song is None:
        return

    ensure_song_like_status(
        ytmusic,
        song,
    )

    mc = cast.media_controller
    position = get_media_position(
        mc
    )

    status = mc.status

    duration = status.duration

    if not duration:
        duration = song_duration_seconds(
            song
        )

    state_text = {
        "PLAYING": "Hraje",
        "PAUSED": "Pozastaveno",
        "BUFFERING": "Načítá se",
        "IDLE": "Stojí",
        "UNKNOWN": "Neznámý stav",
    }.get(
        status.player_state,
        status.player_state or "?",
    )

    repeat_text = {
        "off": "Vypnuto",
        "all": "Celá fronta",
        "one": "Jedna skladba",
    }.get(
        repeat_mode,
        repeat_mode,
    )

    title = song.get(
        "title",
        "?",
    )

    artists = artist_names(
        song
    )

    album = album_name(
        song
    ) or "-"

    remaining = None

    if duration:
        remaining = max(
            0,
            float(duration) - position,
        )

    cast_status = cast.status

    if cast_status is not None:
        volume = int(
            round(
                cast_status.volume_level
                * 100
            )
        )

        muted = bool(
            cast_status.volume_muted
        )

    else:
        volume = 0
        muted = False

    print()
    print(
        "Informace o přehrávání"
    )
    print(
        "======================="
    )
    print()
    print(
        f"Skladba:     {title}"
    )
    print(
        f"Interpret:   {artists}"
    )
    print(
        f"Album:       {album}"
    )
    print(
        f"Hodnocení:   "
        f"{like_status_text(song)}"
    )
    print()
    print(
        f"Fronta:      {queue.name}"
    )
    print(
        f"Pozice:      "
        f"{queue.index + 1} / "
        f"{queue.count()}"
    )
    print(
        f"Repeat:      {repeat_text}"
    )

    if getattr(
        queue,
        "radio_active",
        False,
    ):
        queue_mode = "Mix / rádio"

    elif getattr(
        queue,
        "shuffle_active",
        False,
    ):
        queue_mode = "Náhodně (YouTube Music)"

    else:
        queue_mode = "Normální"

    print(
        f"Režim fronty: {queue_mode}"
    )
    print()
    print(
        f"Přehrávání:  {state_text}"
    )

    if duration:
        print(
            f"Čas:         "
            f"{format_seconds(position)} / "
            f"{format_seconds(duration)}"
        )
        print(
            f"Zbývá:       "
            f"{format_seconds(remaining)}"
        )
    else:
        print(
            f"Čas:         "
            f"{format_seconds(position)}"
        )

    print()
    print(
        f"Výstup:      "
        f"{cast.cast_info.friendly_name}"
    )

    if muted:
        print(
            f"Hlasitost:   "
            f"{volume} % (MUTE)"
        )
    else:
        print(
            f"Hlasitost:   "
            f"{volume} %"
        )

    print()


def toggle_song_rating(
    ytmusic,
    queue,
    wanted,
):
    song = queue.current()

    if song is None:
        return

    video_id = song.get(
        "videoId"
    )

    if not video_id:
        print(
            "Skladba nemá videoId."
        )
        return

    current = ensure_song_like_status(
        ytmusic,
        song,
    )

    if current == wanted:
        new_status = "INDIFFERENT"
    else:
        new_status = wanted

    rating = {
        "LIKE": LikeStatus.LIKE,
        "DISLIKE": LikeStatus.DISLIKE,
        "INDIFFERENT": LikeStatus.INDIFFERENT,
    }[new_status]

    try:
        ytmusic.rate_song(
            video_id,
            rating,
        )

    except Exception as exc:
        print()
        print(
            "Nepodařilo se změnit "
            "hodnocení skladby:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        print()
        return

    song["likeStatus"] = new_status

    print(
        f"Hodnocení: "
        f"{like_status_text(song)}"
    )


def seek_relative(
    mc,
    delta,
):
    state = mc.status.player_state

    if state not in (
        "PLAYING",
        "PAUSED",
        "BUFFERING",
    ):
        print(
            "Není co posouvat."
        )
        return

    current = get_media_position(
        mc
    )

    duration = mc.status.duration

    target = current + delta
    target = max(
        0.0,
        target,
    )

    if duration:
        target = min(
            target,
            max(
                0.0,
                float(duration) - 0.5,
            ),
        )

    try:
        mc.seek(
            target
        )

    except Exception as exc:
        print(
            f"Seek selhal: "
            f"{type(exc).__name__}: {exc}"
        )
        return

    sign = "+" if delta >= 0 else ""

    print(
        f"⏩ Seek {sign}{int(delta)} s "
        f"→ {format_seconds(target)}"
    )


def change_volume(
    cast,
    delta,
):
    try:
        if delta > 0:
            level = cast.volume_up(
                delta
            )
        else:
            level = cast.volume_down(
                abs(delta)
            )

    except Exception as exc:
        print(
            f"Změna hlasitosti selhala: "
            f"{type(exc).__name__}: {exc}"
        )
        return

    print(
        f"🔊 Hlasitost: "
        f"{int(round(level * 100))} %"
    )


def set_volume_percent(
    cast,
    percent,
):
    percent = max(
        0,
        min(
            100,
            int(percent),
        ),
    )

    try:
        level = cast.set_volume(
            percent / 100.0
        )

    except Exception as exc:
        print(
            f"Nastavení hlasitosti selhalo: "
            f"{type(exc).__name__}: {exc}"
        )
        return

    print(
        f"🔊 Hlasitost: "
        f"{int(round(level * 100))} %"
    )


def toggle_mute(cast):
    if cast.status is None:
        print(
            "Chromecast neposlal stav."
        )
        return

    new_state = not bool(
        cast.status.volume_muted
    )

    try:
        cast.set_volume_muted(
            new_state
        )

    except Exception as exc:
        print(
            f"Mute selhalo: "
            f"{type(exc).__name__}: {exc}"
        )
        return

    if new_state:
        print(
            "🔇 MUTE"
        )
    else:
        print(
            "🔊 Zvuk zapnut"
        )



def apply_youtube_shuffle(
    ytmusic,
    queue,
):
    """
    Zamíchá aktuální playlist/alba přes YouTube Music.

    Právě hranou skladbu nepřerušíme. Pouze přestavíme frontu.
    """

    playlist_id = getattr(
        queue,
        "source_playlist_id",
        None,
    )

    if not youtube_shuffle_supported(
        playlist_id
    ):
        print()
        print(
            "🔀 YouTube Music shuffle není "
            "pro tuto frontu k dispozici."
        )
        return False

    current_song = queue.current()

    if current_song is None:
        return False

    current_video_id = current_song.get(
        "videoId"
    )

    print()
    print(
        "🔀 YouTube Music míchá frontu..."
    )

    try:
        tracks = get_youtube_shuffle_tracks(
            ytmusic,
            playlist_id,
            queue.count(),
        )

    except Exception as exc:
        print(
            "Náhodnou frontu se "
            "nepodařilo vytvořit:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return False

    # Aktuální skladbu necháme na prvním místě a zbytek
    # převezmeme v pořadí, které nám vrátil YouTube Music.
    # Tím při zamíchání za běhu neztratíme skladby, které by
    # jinak skončily před aktuální pozicí.
    shuffled_rest = []

    for item in tracks:
        if (
            current_video_id
            and item.get("videoId")
            == current_video_id
        ):
            continue

        shuffled_rest.append(
            item
        )

    tracks = [
        current_song,
        *shuffled_rest,
    ]

    queue.tracks = tracks
    queue.index = 0
    queue.shuffle_active = True
    queue.radio_active = False

    print(
        f"🔀 Fronta zamíchána: "
        f"{queue.count()} skladeb"
    )
    print(
        "Aktuální skladba pokračuje."
    )

    return True


def get_radio_block(
    ytmusic,
    seed_video_id,
):
    """
    Nechá YouTube Music vytvořit jeden blok Mix/Radio
    podle zadané skladby.
    """

    data = ytmusic.get_watch_playlist(
        videoId=seed_video_id,
        limit=MIX_LIMIT,
        radio=True,
    )

    tracks = usable_tracks(
        data.get("tracks") or []
    )

    if not tracks:
        raise RuntimeError(
            "YouTube Music nevrátilo "
            "žádnou radio frontu."
        )

    return tracks


def current_mix_refill_threshold():
    """
    V testovacím režimu chceme doplnění spustit až po pár
    ručních skocích, ne hned po vytvoření pětiskladbové fronty.
    """

    if MIX_TEST_MAX_TRACKS is not None:
        return 2

    return MIX_REFILL_THRESHOLD


def limit_radio_tracks_for_test(
    tracks,
):
    """
    Testovací ořez radio bloku.

    V normálním provozu (None) nic nemění.
    """

    if MIX_TEST_MAX_TRACKS is None:
        return tracks

    return tracks[
        :MIX_TEST_MAX_TRACKS
    ]


def unique_new_radio_tracks(
    queue,
    tracks,
    seed_video_id=None,
):
    """
    Vrátí jen skladby, které ještě v aktuální radio frontě
    nejsou. Duplicitu poznáváme podle videoId.
    """

    existing_ids = {
        song.get("videoId")
        for song in queue.tracks
        if song.get("videoId")
    }

    result = []

    for song in tracks:
        video_id = song.get(
            "videoId"
        )

        if not video_id:
            continue

        # Seed bývá první položkou nového radio bloku.
        if (
            seed_video_id
            and video_id == seed_video_id
        ):
            continue

        if video_id in existing_ids:
            continue

        existing_ids.add(
            video_id
        )

        result.append(
            song
        )

    return result


def refill_radio_queue(
    ytmusic,
    queue,
    force=False,
):
    """
    Přidá další YT Music radio blok na konec fronty.

    Nový blok seedujeme poslední skladbou dosavadní fronty.
    Duplicity se nepřidávají.

    force=True ignoruje hranici počtu zbývajících skladeb.
    """

    if (
        not queue.radio_active
        or queue.empty()
    ):
        return False

    remaining = (
        queue.count()
        - queue.index
        - 1
    )

    threshold = (
        current_mix_refill_threshold()
    )

    if (
        not force
        and remaining > threshold
    ):
        return False

    now = time.monotonic()

    if (
        not force
        and now
        < queue.radio_refill_retry_after
    ):
        return False

    seed_song = (
        queue.tracks[-1]
    )

    seed_video_id = (
        seed_song.get("videoId")
    )

    if not seed_video_id:
        queue.radio_refill_retry_after = (
            now + 30
        )
        return False

    print()
    print(
        f"📻 Mix se blíží ke konci "
        f"(zbývá {remaining} skladeb)."
    )
    print(
        "📻 Načítám další doporučení..."
    )

    try:
        tracks = get_radio_block(
            ytmusic,
            seed_video_id,
        )

    except Exception as exc:
        print(
            "⚠ Další část Mix/Radio se "
            "nepodařilo načíst:"
        )
        print(
            f"  {type(exc).__name__}: "
            f"{exc}"
        )

        # Další automatický pokus nejdříve za 30 sekund.
        queue.radio_refill_retry_after = (
            time.monotonic() + 30
        )

        return False

    received_count = len(
        tracks
    )

    new_tracks = (
        unique_new_radio_tracks(
            queue,
            tracks,
            seed_video_id=seed_video_id,
        )
    )

    unique_count = len(
        new_tracks
    )

    if MIX_TEST_MAX_TRACKS is not None:
        new_tracks = (
            limit_radio_tracks_for_test(
                new_tracks
            )
        )

    if not new_tracks:
        print(
            "⚠ YouTube Music tentokrát "
            "nevrátilo žádné nové skladby."
        )

        queue.radio_refill_retry_after = (
            time.monotonic() + 30
        )

        return False

    queue.tracks.extend(
        new_tracks
    )

    queue.radio_refill_retry_after = 0.0

    print(
        f"📻 YTM vrátilo "
        f"{received_count} skladeb, "
        f"nových bylo {unique_count}."
    )

    if MIX_TEST_MAX_TRACKS is not None:
        print(
            f"🧪 TEST: přidávám jen "
            f"{len(new_tracks)} skladeb."
        )

    print(
        f"📻 Přidáno "
        f"{len(new_tracks)} skladeb. "
        f"Fronta má nyní "
        f"{queue.count()} skladeb."
    )

    return True


def maybe_refill_radio_queue(
    ytmusic,
    queue,
):
    """
    Tichý hlídač radio fronty.

    Dokud je skladeb dost, nedělá nic.
    Jakmile se přiblížíme ke konci, doplní další blok.
    """

    return refill_radio_queue(
        ytmusic,
        queue,
        force=False,
    )


def activate_radio_from_current(
    ytmusic,
    queue,
):
    """
    Vytvoří YouTube Music Mix/Radio podle právě hrané skladby.

    Aktuální skladbu necháme hrát; další skladby už budou
    pocházet z YT Music radio fronty.

    V normálním provozu FCM frontu automaticky doplňuje,
    takže je Mix/Radio z pohledu uživatele prakticky nekonečný.
    """

    current_song = queue.current()

    if current_song is None:
        return False

    video_id = current_song.get(
        "videoId"
    )

    if not video_id:
        print()
        print(
            "📻 Aktuální skladba nemá videoId."
        )
        return False

    title = current_song.get(
        "title",
        "Skladba",
    )

    print()
    print(
        "📻 YouTube Music vytváří "
        "Mix / rádio..."
    )

    try:
        tracks = get_radio_block(
            ytmusic,
            video_id,
        )

    except Exception as exc:
        print(
            "Mix / rádio se nepodařilo "
            "vytvořit:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        return False

    received_count = len(
        tracks
    )

    # Radio z aktuální skladby má pokračovat právě hranou
    # skladbou a pak navázat doporučeními od YouTube Music.
    radio_rest = []
    seen_ids = {
        video_id
    }

    for item in tracks:
        item_video_id = item.get(
            "videoId"
        )

        if not item_video_id:
            continue

        if item_video_id in seen_ids:
            continue

        seen_ids.add(
            item_video_id
        )

        radio_rest.append(
            item
        )

    tracks = [
        current_song,
        *radio_rest,
    ]

    if MIX_TEST_MAX_TRACKS is not None:
        tracks = (
            limit_radio_tracks_for_test(
                tracks
            )
        )

    queue.tracks = tracks
    queue.index = 0
    queue.name = (
        f"Mix: {title}"
    )
    queue.source_playlist_id = None
    queue.shuffle_active = False
    queue.radio_active = True
    queue.radio_refill_retry_after = 0.0

    print(
        f"📻 YTM vytvořilo první blok: "
        f"{received_count} skladeb"
    )

    if MIX_TEST_MAX_TRACKS is not None:
        print(
            f"🧪 TEST: FCM používá zatím "
            f"jen prvních {queue.count()} skladeb."
        )

    print(
        f"📻 Mix / rádio připraveno: "
        f"{queue.count()} skladeb"
    )
    print(
        "Aktuální skladba pokračuje; "
        "další už budou z mixu."
    )

    return True


def cycle_repeat_mode(mode):
    if mode == "off":
        return "all"

    if mode == "all":
        return "one"

    return "off"


def print_repeat_mode(mode):
    text = {
        "off": "Vypnuto",
        "all": "Celá fronta",
        "one": "Jedna skladba",
    }[mode]

    print(
        f"🔁 Repeat: {text}"
    )


def browse_playback_queue(
    queue,
    page_size=PLAYBACK_QUEUE_PAGE_SIZE,
):
    """
    Textový prohlížeč právě aktivní fronty.

    Vrací dvojici:
      ("back", None)     - zpět bez změny
      ("jump", index)    - skočit na vybranou skladbu
      ("menu", None)     - hlavní menu
      ("quit", None)     - ukončit FCM

    Začíná na stránce, kde je právě hrající skladba.
    Číslo skladby lze zadat přímo i tehdy, když není
    na právě zobrazené stránce.
    """

    if (
        queue is None
        or queue.empty()
    ):
        print()
        print(
            "Fronta je prázdná."
        )

        return (
            "back",
            None,
        )

    page_size = max(
        1,
        int(page_size),
    )

    page = (
        queue.index
        // page_size
    )

    while True:
        total = queue.count()

        if total <= 0:
            return (
                "back",
                None,
            )

        total_pages = (
            total
            + page_size
            - 1
        ) // page_size

        page = max(
            0,
            min(
                page,
                total_pages - 1,
            ),
        )

        start = (
            page
            * page_size
        )

        end = min(
            start + page_size,
            total,
        )

        print()
        print(
            f"Fronta: {queue.name}"
        )

        print(
            "=" * min(
                len(
                    f"Fronta: {queue.name}"
                ),
                65,
            )
        )

        print(
            f"Strana "
            f"{page + 1}/{total_pages} "
            f"| skladeb {total} "
            f"| aktuální "
            f"{queue.index + 1}"
        )

        print()

        for index in range(
            start,
            end,
        ):
            song = (
                queue.tracks[
                    index
                ]
            )

            (
                first_line,
                second_line,
            ) = song_description(
                song
            )

            marker = (
                "▶"
                if index == queue.index
                else " "
            )

            print(
                f"{marker} "
                f"{index + 1:4}. "
                f"{first_line}"
            )

            print(
                f"       "
                f"{second_line}"
            )

        print()

        commands = []

        if page > 0:
            commands.append(
                "p=předchozí strana"
            )

        if (
            page + 1
            < total_pages
        ):
            commands.append(
                "d=další strana"
            )

        commands.append(
            "z=zpět"
        )
        commands.append(
            "m=hlavní menu"
        )
        commands.append(
            "q=konec"
        )

        print(
            " | ".join(
                commands
            )
        )

        value = input(
            "Vyber skladbu: "
        ).strip().lower()

        if value == "z":
            return (
                "back",
                None,
            )

        if value == "m":
            return (
                "menu",
                None,
            )

        if value == "q":
            return (
                "quit",
                None,
            )

        if (
            value == "d"
            and page + 1
            < total_pages
        ):
            page += 1
            continue

        if (
            value == "p"
            and page > 0
        ):
            page -= 1
            continue

        try:
            choice = int(
                value
            )

            if (
                1
                <= choice
                <= total
            ):
                return (
                    "jump",
                    choice - 1,
                )

        except ValueError:
            pass

        print(
            "Neplatná volba."
        )



def save_resume_session(
    output_state,
    queue,
    position,
    repeat_mode="off",
):
    """
    Uloží poslední rozposlouchanou frontu.

    Nic se při příštím startu nespustí automaticky.
    session.json pouze umožní nabídnout "Pokračovat?".

    Ukládáme celou frontu, protože u Shuffle/Mix musí být
    zachováno přesné pořadí, ne jen videoId aktuální skladby.
    """

    if (
        queue is None
        or queue.empty()
    ):
        return False

    try:
        position = max(
            0.0,
            float(position or 0.0),
        )
    except (
        TypeError,
        ValueError,
    ):
        position = 0.0

    current_output = None

    try:
        current_output = (
            output_state.current
        )
    except Exception:
        pass

    output_info = {
        "name": (
            output_name(
                current_output
            )
            if current_output is not None
            else ""
        ),
        "local": bool(
            getattr(
                current_output,
                "is_local",
                False,
            )
        ),
        "uuid": None,
    }

    if (
        current_output is not None
        and not output_info["local"]
    ):
        uuid = cast_uuid(
            current_output
        )

        if uuid is not None:
            output_info[
                "uuid"
            ] = str(uuid)

    data = {
        "format": 1,
        "saved_at": int(
            time.time()
        ),
        "position": position,
        "repeat_mode": (
            repeat_mode
            if repeat_mode
            in (
                "off",
                "all",
                "one",
            )
            else "off"
        ),
        "output": output_info,
        "queue": {
            "name": queue.name,
            "index": queue.index,
            "tracks": queue.tracks,
            "source_playlist_id": (
                queue.source_playlist_id
            ),
            "shuffle_active": bool(
                queue.shuffle_active
            ),
            "radio_active": bool(
                queue.radio_active
            ),
        },
    }

    tmp_path = (
        RESUME_SESSION_FILE
        + ".tmp"
    )

    try:
        os.makedirs(
            AUTH_DIR,
            exist_ok=True,
        )

        with open(
            tmp_path,
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                data,
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write(
                "\n"
            )

        try:
            os.chmod(
                tmp_path,
                0o600,
            )
        except OSError:
            pass

        os.replace(
            tmp_path,
            RESUME_SESSION_FILE,
        )

        try:
            os.chmod(
                RESUME_SESSION_FILE,
                0o600,
            )
        except OSError:
            pass

        return True

    except Exception as exc:
        try:
            if os.path.exists(
                tmp_path
            ):
                os.unlink(
                    tmp_path
                )
        except Exception:
            pass

        print()
        print(
            "⚠ Poslední přehrávání "
            "se nepodařilo uložit:"
        )
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return False


def clear_resume_session():
    try:
        os.unlink(
            RESUME_SESSION_FILE
        )
    except FileNotFoundError:
        pass
    except Exception:
        pass


def load_resume_session():
    if not os.path.isfile(
        RESUME_SESSION_FILE
    ):
        return None

    try:
        with open(
            RESUME_SESSION_FILE,
            "r",
            encoding="utf-8",
        ) as handle:
            data = json.load(
                handle
            )

    except Exception:
        return None

    if not isinstance(
        data,
        dict,
    ):
        return None

    queue_data = data.get(
        "queue"
    )

    if not isinstance(
        queue_data,
        dict,
    ):
        return None

    tracks = queue_data.get(
        "tracks"
    )

    if not isinstance(
        tracks,
        list,
    ):
        return None

    if not tracks:
        return None

    try:
        index = int(
            queue_data.get(
                "index",
                0,
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        index = 0

    queue = PlaybackQueue(
        tracks,
        name=(
            queue_data.get(
                "name"
            )
            or "Poslední přehrávání"
        ),
        start_index=index,
        source_playlist_id=(
            queue_data.get(
                "source_playlist_id"
            )
        ),
        shuffle_active=bool(
            queue_data.get(
                "shuffle_active",
                False,
            )
        ),
        radio_active=bool(
            queue_data.get(
                "radio_active",
                False,
            )
        ),
    )

    if queue.empty():
        return None

    try:
        position = max(
            0.0,
            float(
                data.get(
                    "position",
                    0.0,
                )
                or 0.0
            ),
        )
    except (
        TypeError,
        ValueError,
    ):
        position = 0.0

    repeat_mode = data.get(
        "repeat_mode",
        "off",
    )

    if repeat_mode not in (
        "off",
        "all",
        "one",
    ):
        repeat_mode = "off"

    output_info = data.get(
        "output"
    )

    if not isinstance(
        output_info,
        dict,
    ):
        output_info = {}

    return {
        "queue": queue,
        "position": position,
        "repeat_mode": repeat_mode,
        "output": output_info,
        "saved_at": data.get(
            "saved_at"
        ),
    }


def offer_resume_session():
    """
    Pouze NABÍDNE pokračování.
    Samo nikdy nic nepustí.
    """

    session = load_resume_session()

    if session is None:
        return None

    queue = session[
        "queue"
    ]

    song = queue.current()

    if song is None:
        return None

    first_line, _ = (
        song_description(
            song
        )
    )

    output_name_saved = (
        session[
            "output"
        ].get(
            "name"
        )
        or "?"
    )

    print()
    print(
        "Nalezeno poslední "
        "přehrávání:"
    )
    print(
        "=" * 32
    )
    print(
        f"Fronta: {queue.name}"
    )
    print(
        f"Skladba: "
        f"[{queue.position()}] "
        f"{first_line}"
    )
    print(
        f"Pozice: "
        f"{format_seconds(session['position'])}"
    )
    print(
        f"Poslední výstup: "
        f"{output_name_saved}"
    )
    print()

    answer = input(
        "Pokračovat? [A/n]: "
    ).strip().lower()

    if answer in (
        "n",
        "ne",
        "no",
    ):
        return None

    return session


def _current_resume_position(
    mc,
    stopped,
    position_hint,
):
    """
    Před STOPem vezmeme živou pozici.
    Po STOPu už některé backendy hlásí 0, proto držíme hint.
    """

    if stopped:
        return max(
            0.0,
            float(
                position_hint
                or 0.0
            ),
        )

    try:
        position = (
            get_media_position(
                mc
            )
        )

        if position >= 0.0:
            return position

    except Exception:
        pass

    return max(
        0.0,
        float(
            position_hint
            or 0.0
        ),
    )



def print_player_commands():
    print()
    print(
        "Ovládání:"
    )
    print(
        "  p  = pause"
    )
    print(
        "  r  = play / resume"
    )
    print(
        "  n  = další skladba"
    )
    print(
        "  b  = předchozí skladba"
    )
    print(
        "  <  = zpět 10 s"
    )
    print(
        "  >  = vpřed 10 s"
    )
    print(
        "  << = zpět 30 s"
    )
    print(
        "  >> = vpřed 30 s"
    )
    print(
        "  +  = hlasitost +5 %"
    )
    print(
        "  -  = hlasitost -5 %"
    )
    print(
        "  v 35 = hlasitost 35 %"
    )
    print(
        "  u  = mute / unmute"
    )
    print(
        "  o  = změnit výstup"
    )
    print(
        "  t  = repeat off/all/one"
    )
    print(
        "  z  = zamíchat přes YouTube Music"
    )
    print(
        "  x  = Mix / rádio z aktuální skladby"
    )
    print(
        "  l  = oblíbená / zrušit"
    )
    print(
        "  d  = neoblíbená / zrušit"
    )
    print(
        "  i  = informace"
    )
    print(
        "  f  = zobrazit frontu / skočit na skladbu"
    )
    print(
        "  h  = zobrazit ovládání"
    )
    print(
        "  s  = stop"
    )
    print(
        "  m  = hlavní menu"
    )
    print(
        "  q  = konec FelisMusic"
    )
    print()


def queue_player(
    ytmusic,
    output_state,
    queue,
    resume_position=0.0,
    initial_repeat_mode="off",
):
    if (
        queue is None
        or queue.empty()
    ):
        return "menu"

    cast = output_state.current
    mc = cast.media_controller

    stopped = False

    repeat_mode = (
        initial_repeat_mode
        if initial_repeat_mode
        in (
            "off",
            "all",
            "one",
        )
        else "off"
    )

    try:
        resume_position = max(
            0.0,
            float(
                resume_position
                or 0.0
            ),
        )
    except (
        TypeError,
        ValueError,
    ):
        resume_position = 0.0

    resume_index = queue.index
    resume_position_hint = (
        resume_position
    )

    started = (
        start_current_track_with_skip(
            ytmusic,
            mc,
            queue,
            direction=1,
        )
    )

    if not started:

        print()
        print(
            "Ve frontě není nic, "
            "co lze přehrát."
        )

        return "menu"

    # Pokračování z minulé session:
    # pozici aplikujeme jen tehdy, pokud se start_current_track_with_skip()
    # nemusel kvůli rozbité skladbě posunout jinam.
    if (
        resume_position >= 1.0
        and queue.index == resume_index
    ):
        try:
            mc.seek(
                resume_position
            )
            time.sleep(
                0.15
            )

            print(
                f"▶ Pokračuji od "
                f"{format_seconds(resume_position)}"
            )

        except Exception as exc:
            print()
            print(
                "⚠ Uloženou pozici se "
                "nepodařilo obnovit, "
                "hraji od začátku."
            )
            print(
                f"{type(exc).__name__}: "
                f"{exc}"
            )
            resume_position_hint = 0.0

    else:
        resume_position_hint = 0.0

    # Po startu čekáme na skutečný PLAYING/PAUSED/BUFFERING.
    # Tím nezpracujeme omylem FINISHED stav předchozí skladby.
    seen_active = False

    print_player_commands()

    while True:

        # Prakticky nekonečný Mix/Radio:
        # při přiblížení ke konci doplníme další doporučení.
        #
        # Chromecast mezitím přehrává sám, takže krátké čekání
        # na YT Music API nepřeruší aktuální audio.
        maybe_refill_radio_queue(
            ytmusic,
            queue,
        )

        ready, _, _ = select.select(
            [sys.stdin],
            [],
            [],
            0.5,
        )

        if ready:

            command = (
                sys.stdin
                .readline()
                .strip()
                .lower()
            )

            if command == "p":

                if (
                    mc.status.player_state
                    == "PLAYING"
                ):

                    mc.pause()

                    print(
                        "⏸ Pause"
                    )

                else:

                    print(
                        "Není co pozastavit."
                    )

            elif command == "r":

                state = (
                    mc.status.player_state
                )

                if state == "PAUSED":

                    mc.play()

                    stopped = False
                    seen_active = True

                    print(
                        "▶ Pokračuji"
                    )

                elif (
                    stopped
                    or state == "IDLE"
                ):

                    print(
                        "▶ Spouštím aktuální "
                        "skladbu znovu"
                    )

                    stopped = False
                    resume_position_hint = 0.0

                    started = (
                        start_current_track_with_skip(
                            ytmusic,
                            mc,
                            queue,
                            direction=1,
                        )
                    )

                    if not started:
                        return "menu"

                    seen_active = False

                else:

                    print(
                        "▶ Už hraje."
                    )

            elif command == "n":

                mc.stop()

                if queue.next():

                    print(
                        "⏭ Další skladba"
                    )

                elif repeat_mode == "all":
                    queue.index = 0

                    print(
                        "⏭ Konec fronty → začátek"
                    )

                else:

                    print()
                    print(
                        "Jsme na konci fronty."
                    )

                    stopped = True
                    continue

                stopped = False

                started = (
                    start_current_track_with_skip(
                        ytmusic,
                        mc,
                        queue,
                        direction=1,
                    )
                )

                if not started:

                    print()
                    print(
                        "✓ Konec fronty."
                    )

                    return "menu"

                seen_active = False

            elif command == "b":

                mc.stop()

                if queue.previous():

                    print(
                        "⏮ Předchozí skladba"
                    )

                elif repeat_mode == "all":
                    queue.index = (
                        queue.count() - 1
                    )

                    print(
                        "⏮ Začátek fronty → konec"
                    )

                else:

                    print()
                    print(
                        "Jsme na začátku fronty."
                    )

                    stopped = True
                    continue

                stopped = False

                started = (
                    start_current_track_with_skip(
                        ytmusic,
                        mc,
                        queue,
                        direction=-1,
                    )
                )

                if not started:

                    print()
                    print(
                        "Jsme na začátku fronty."
                    )

                    stopped = True

                else:
                    seen_active = False

            elif command == "<":
                seek_relative(
                    mc,
                    -10,
                )

            elif command == ">":
                seek_relative(
                    mc,
                    10,
                )

            elif command == "<<":
                seek_relative(
                    mc,
                    -30,
                )

            elif command == ">>":
                seek_relative(
                    mc,
                    30,
                )

            elif command == "+":
                change_volume(
                    cast,
                    0.05,
                )

            elif command == "-":
                change_volume(
                    cast,
                    -0.05,
                )

            elif command.startswith("v "):
                value = command[2:].strip()

                try:
                    percent = int(value)
                except ValueError:
                    print(
                        "Použij například: v 35"
                    )
                else:
                    set_volume_percent(
                        cast,
                        percent,
                    )

            elif command == "u":
                toggle_mute(
                    cast
                )

            elif command == "o":
                changed = switch_playback_output(
                    ytmusic,
                    output_state,
                    queue,
                    stopped=stopped,
                )

                if changed:
                    cast = output_state.current
                    mc = cast.media_controller

                    if not stopped:
                        seen_active = False

            elif command == "t":
                repeat_mode = cycle_repeat_mode(
                    repeat_mode
                )
                print_repeat_mode(
                    repeat_mode
                )

            elif command == "z":
                apply_youtube_shuffle(
                    ytmusic,
                    queue,
                )

            elif command == "x":
                activate_radio_from_current(
                    ytmusic,
                    queue,
                )

            elif command == "l":
                toggle_song_rating(
                    ytmusic,
                    queue,
                    "LIKE",
                )

            elif command == "d":
                toggle_song_rating(
                    ytmusic,
                    queue,
                    "DISLIKE",
                )

            elif command == "f":

                action, jump_index = (
                    browse_playback_queue(
                        queue
                    )
                )

                if action == "menu":
                    resume_position_hint = (
                        _current_resume_position(
                            mc,
                            stopped,
                            resume_position_hint,
                        )
                    )

                    save_resume_session(
                        output_state,
                        queue,
                        resume_position_hint,
                        repeat_mode,
                    )

                    mc.stop()
                    return "menu"

                if action == "quit":
                    resume_position_hint = (
                        _current_resume_position(
                            mc,
                            stopped,
                            resume_position_hint,
                        )
                    )

                    save_resume_session(
                        output_state,
                        queue,
                        resume_position_hint,
                        repeat_mode,
                    )

                    mc.stop()
                    return "quit"

                if (
                    action == "jump"
                    and jump_index is not None
                ):
                    if (
                        jump_index
                        == queue.index
                    ):
                        print()
                        print(
                            "▶ Tato skladba už "
                            "je aktuální."
                        )

                    else:
                        old_index = (
                            queue.index
                        )

                        mc.stop()

                        queue.index = (
                            jump_index
                        )

                        print()
                        print(
                            f"⏭ Přeskakuji "
                            f"{old_index + 1} "
                            f"→ {jump_index + 1}"
                        )

                        stopped = False

                        started = (
                            start_current_track_with_skip(
                                ytmusic,
                                mc,
                                queue,
                                direction=1,
                            )
                        )

                        if not started:
                            return "menu"

                        seen_active = False

            elif command == "i":

                player_info(
                    ytmusic,
                    cast,
                    queue,
                    repeat_mode,
                )

            elif command == "h":
                print_player_commands()

            elif command == "s":

                resume_position_hint = (
                    _current_resume_position(
                        mc,
                        stopped,
                        resume_position_hint,
                    )
                )

                save_resume_session(
                    output_state,
                    queue,
                    resume_position_hint,
                    repeat_mode,
                )

                mc.stop()

                stopped = True
                seen_active = False

                print(
                    "■ Stop"
                )

            elif command == "m":

                resume_position_hint = (
                    _current_resume_position(
                        mc,
                        stopped,
                        resume_position_hint,
                    )
                )

                save_resume_session(
                    output_state,
                    queue,
                    resume_position_hint,
                    repeat_mode,
                )

                mc.stop()

                return "menu"

            elif command == "q":

                resume_position_hint = (
                    _current_resume_position(
                        mc,
                        stopped,
                        resume_position_hint,
                    )
                )

                save_resume_session(
                    output_state,
                    queue,
                    resume_position_hint,
                    repeat_mode,
                )

                mc.stop()

                return "quit"

            elif command:

                print(
                    "Neznámý příkaz. "
                    "Použij h pro nápovědu."
                )

        state = (
            mc.status.player_state
        )

        idle_reason = (
            mc.status.idle_reason
        )

        if state in (
            "PLAYING",
            "PAUSED",
            "BUFFERING",
        ):

            seen_active = True

        if (
            not stopped
            and state == "IDLE"
            and idle_reason == "ERROR"
        ):

            print()
            print(
                "⚠ Přehrávání skladby selhalo."
            )

            if queue.next():

                print(
                    "⏭ Automaticky přeskakuji "
                    "na další..."
                )

                started = (
                    start_current_track_with_skip(
                        ytmusic,
                        mc,
                        queue,
                        direction=1,
                    )
                )

                if not started:
                    return "menu"

                seen_active = False
                continue

            print()
            print(
                "✓ Konec fronty."
            )

            return "menu"

        if (
            not stopped
            and seen_active
            and state == "IDLE"
            and idle_reason == "FINISHED"
        ):

            print()
            print(
                "✓ Skladba skončila."
            )

            if repeat_mode == "one":

                print(
                    "🔂 Opakuji skladbu..."
                )

            elif queue.next():

                print(
                    "⏭ Automaticky další..."
                )

            elif repeat_mode == "all":

                queue.index = 0

                print(
                    "🔁 Opakuji frontu od začátku..."
                )

            else:

                print()
                print(
                    "✓ Konec fronty."
                )

                clear_resume_session()

                return "menu"

            started = (
                start_current_track_with_skip(
                    ytmusic,
                    mc,
                    queue,
                    direction=1,
                )
            )

            if not started:

                print()
                print(
                    "✓ Konec fronty."
                )

                return "menu"

            seen_active = False

# ============================================================
# Hlavní menu
# ============================================================

def main_menu(account):
    name = account.get(
        "accountName",
        "YouTube Music",
    )

    print()
    print(
        "=" * 50
    )

    print(
        f"FelisMusic v{VERSION}"
        f" - {name}"
    )

    print(
        "=" * 50
    )

    print()
    print(
        "1. Hledat"
    )

    print(
        "2. Knihovna"
    )

    print(
        "3. Oblíbená hudba"
    )

    print(
        "4. Historie"
    )

    print(
        "5. Mixy pro vás"
    )

    print(
        "6. Konec"
    )

    print()

    while True:

        value = menu_input(
            "Vyber: "
        )

        if value in (
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
        ):

            return value

        if value.lower() == "z":
            continue

        print(
            "Neplatná volba."
        )


# ============================================================
# MAIN
# ============================================================

def main():
    print()
    print(
        f"FelisMusic v{VERSION}"
    )

    print(
        "=" * 24
    )

    print()

    browser = None
    cast = None
    outputs = []

    try:

        (
            ytmusic,
            account,
        ) = connect_youtube_music()

        if ytmusic is None:
            return

        print()

        (
            chromecasts,
            browser,
        ) = find_casts()

        if not chromecasts:
            print()
            print(
                "Žádný audio/group Cast "
                "zatím nenalezen; lokální "
                "přehrávání může fungovat "
                "i bez něj."
            )

        output_state = OutputState(
            browser,
            chromecasts,
        )

        # Browser už po úvodním discovery běží dál.
        # Před prvním výběrem vezmeme jeho aktuální snapshot.
        refresh_outputs(
            output_state,
            wait=False,
        )

        cast = choose_output(
            output_state
        )

        if cast is None:
            return

        output_state.current = cast
        outputs = output_state.outputs

        print()
        print(
            f"Vybráno: "
            f"{output_name(cast)}"
        )

        try:
            prepare_output(
                cast
            )

        except Exception as exc:

            print()
            print(
                "Nepodařilo se "
                "připravit výstup:"
            )

            print(
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            return

        if getattr(
            cast,
            "is_local",
            False,
        ):
            print(
                "Lokální přehrávání "
                "připraveno."
            )
        else:
            print(
                "Připojeno."
            )

        # Nic nespouštíme automaticky.
        # Pouze jednou při startu nabídneme poslední rozposlouchanou
        # frontu, pokud session.json existuje.
        resume_session = (
            offer_resume_session()
        )

        if resume_session is not None:
            try:
                result = queue_player(
                    ytmusic,
                    output_state,
                    resume_session["queue"],
                    resume_position=(
                        resume_session[
                            "position"
                        ]
                    ),
                    initial_repeat_mode=(
                        resume_session[
                            "repeat_mode"
                        ]
                    ),
                )

                cast = output_state.current
                outputs = output_state.outputs

            except Exception as exc:
                cast = output_state.current
                outputs = output_state.outputs

                print()
                print(
                    "Neočekávaná chyba při "
                    "obnově posledního přehrávání:"
                )
                print(
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )

                result = "menu"

            if result == "quit":
                return

        while True:

            try:
                choice = main_menu(
                    account
                )

                queue = None

                if choice == "1":

                    queue = search_queue(
                        ytmusic
                    )

                elif choice == "2":

                    queue = library_menu(
                        ytmusic
                    )

                elif choice == "3":

                    queue = liked_queue(
                        ytmusic
                    )

                elif choice == "4":

                    queue = history_queue(
                        ytmusic
                    )

                elif choice == "5":

                    queue = personalized_mixes_queue(
                        ytmusic
                    )

                elif choice == "6":

                    break

                if queue is None:
                    continue

                try:

                    result = queue_player(
                        ytmusic,
                        output_state,
                        queue,
                    )

                    cast = output_state.current
                    outputs = output_state.outputs

                except Exception as exc:

                    cast = output_state.current
                    outputs = output_state.outputs

                    print()
                    print(
                        "Neočekávaná chyba "
                        "přehrávání:"
                    )

                    print(
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    )

                    print()
                    print(
                        "Vracíme se do "
                        "hlavního menu."
                    )

                    continue

                if result == "quit":
                    break

            except GoMainMenu:
                continue

            except QuitFCM:
                break

    except KeyboardInterrupt:

        print()
        print(
            "Ukončeno přes Ctrl+C."
        )

        if cast is not None:

            try:
                cast.media_controller.stop()

            except Exception:
                pass

    finally:

        # I neaktivní lokální výstup mohl být krátce spuštěn
        # během nepovedeného přepnutí. Před ukončením procesu
        # musí být každý FCM GStreamer playbin ve stavu NULL.
        cleanup_local_outputs(
            outputs
        )

        cleanup_local_cache()

        # Ukončíme případná Cast socket spojení, která FCM během
        # dynamického discovery vytvořilo.
        try:
            if "output_state" in locals():
                seen = set()

                for cast_object in (
                    output_state.cast_cache.values()
                ):
                    uuid = cast_uuid(
                        cast_object
                    )

                    if uuid in seen:
                        continue

                    seen.add(
                        uuid
                    )

                    _disconnect_cast_safely(
                        cast_object
                    )
        except Exception:
            pass

        if browser is not None:
            browser.stop_discovery()

    print()
    print(
        "FelisMusic ukončen."
    )


if __name__ == "__main__":
    main()
