#!/usr/bin/env python3
"""Compare direct InnerTube audio with an anonymous yt-dlp fallback on desktop.

Reference: sandstorm244/harbour-fintune, eeda872f8f63a3e1381329736c1482ab0e6d588c,
python/innertube.py (request shape). Client metadata comes from installed yt-dlp.
Adapted from FelisMusic-SFOS/tools/probe_direct.py. Temporary audio is removed on exit.
"""

import time

START = time.monotonic()


def log(message):
    print("[+{:6.2f} s] {}".format(time.monotonic() - START, message), flush=True)


import argparse
from copy import deepcopy
import http.client
import json
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import parse_qs, urlsplit


class Transport:
    def __init__(self):
        self.connections = {}

    def request(self, method, url, headers, body=None):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.port not in (None, 443):
            raise ValueError("Only HTTPS on port 443 is supported")
        host = parsed.hostname or ""
        if host != "www.youtube.com" and not host.endswith(".googlevideo.com"):
            raise ValueError("Unexpected host")
        connection = self.connections.get(host)
        if connection is None:
            # Use IPv4 for both PLAYER and media: signed URLs can be IP-bound.
            connection = http.client.HTTPSConnection(host, timeout=20, source_address=("0.0.0.0", 0))
            self.connections[host] = connection
        target = parsed.path + ("?" + parsed.query if parsed.query else "")
        connection.request(method, target, body=body, headers=headers)
        return connection.getresponse()

    def close(self):
        for connection in self.connections.values():
            connection.close()


def audio_formats(response):
    selected = []
    for item in (response.get("streamingData") or {}).get("adaptiveFormats", []):
        mime = item.get("mimeType", "")
        url = item.get("url", "")
        if not mime.startswith(("audio/mp4", "audio/webm")) or not url:
            continue
        if item.get("drmFamilies") or item.get("targetDurationSec") or item.get("type") == "FORMAT_STREAM_TYPE_OTF":
            continue
        if "n" in parse_qs(urlsplit(url).query):
            continue  # Needs JS; deliberately outside this diagnostic.
        selected.append(item)
    def score(item):
        track = item.get("audioTrack") or {}
        language = 2 if "original" in track.get("displayName", "").lower() else int(bool(track.get("audioIsDefault")))
        return (language, item.get("itag") == 140, item.get("bitrate", 0))
    return sorted(selected, key=score, reverse=True)


def play(path, seconds, requested):
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
    Gst.init(None)
    player = Gst.ElementFactory.make("playbin", "felismusic-direct-probe")
    sink = Gst.ElementFactory.make("pulsesink", None)
    if player is None or sink is None:
        raise RuntimeError("playbin or pulsesink unavailable")
    player.set_property("audio-sink", sink)
    player.set_property("volume", 0.3)
    player.set_property("uri", path.resolve().as_uri())
    bus = player.get_bus()
    began = None
    deadline = time.monotonic() + 45 + seconds
    try:
        if player.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Player refused playback")
        while time.monotonic() < deadline:
            message = bus.timed_pop_filtered(100 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS)
            if message:
                if message.type == Gst.MessageType.ERROR:
                    error, _ = message.parse_error()
                    raise RuntimeError(error.message)
                if began is None:
                    raise RuntimeError("End of audio before playback advanced")
                return
            valid, position = player.query_position(Gst.Format.TIME)
            if valid and position > 0 and began is None:
                began = time.monotonic()
                log("REQUEST TO PLAYBACK: {:.2f} s; please confirm audible sound".format(began - requested))
            if began is not None and time.monotonic() - began >= seconds:
                return
        raise RuntimeError("Playback timed out")
    finally:
        player.set_state(Gst.State.NULL)
        player.get_state(5 * Gst.SECOND)


class DirectResolver:
    def __init__(self):
        self.transport = Transport()
        self.client = None
        self.headers = None

    def close(self):
        self.transport.close()

    def post(self, endpoint, payload):
        body = json.dumps(dict(payload, context={"client": self.client})).encode()
        response = self.transport.request(
            "POST", "https://www.youtube.com/youtubei/v1/" + endpoint + "?prettyPrint=false",
            self.headers, body,
        )
        try:
            data = response.read(8 * 1024 * 1024 + 1)
            if response.status != 200 or len(data) > 8 * 1024 * 1024:
                raise RuntimeError("PLAYER response rejected")
            return json.loads(data)
        finally:
            response.close()

    def configure(self):
        from yt_dlp.extractor.youtube._base import INNERTUBE_CLIENTS
        config = INNERTUBE_CLIENTS["visionos"]
        if config.get("REQUIRE_JS_PLAYER", True) or config.get("REQUIRE_AUTH"):
            raise RuntimeError("Installed visionos client requires JS or authentication")
        self.client = deepcopy(config["INNERTUBE_CONTEXT"]["client"])
        self.client.update(hl="en", timeZone="UTC", utcOffsetMinutes=0)
        self.client.pop("gl", None)
        self.headers = {
            "Content-Type": "application/json", "Accept-Encoding": "identity",
            "User-Agent": self.client["userAgent"], "Origin": "https://www.youtube.com",
            "X-YouTube-Client-Name": str(config["INNERTUBE_CONTEXT_CLIENT_NAME"]),
            "X-YouTube-Client-Version": self.client["clientVersion"],
        }
        visitor = (self.post("visitor_id", {}).get("responseContext") or {}).get("visitorData")
        if not visitor:
            raise RuntimeError("No visitor ID returned")
        self.headers["X-Goog-Visitor-Id"] = visitor

    def download(self, video_id, directory):
        if self.headers is None:
            self.configure()
        started = time.monotonic()
        response = self.post("player", {
            "videoId": video_id, "contentCheckOk": True, "racyCheckOk": True,
            "playbackContext": {"contentPlaybackContext": {"html5Preference": "HTML5_PREF_WANTS"}},
        })
        details = response.get("videoDetails") or {}
        status = response.get("playabilityStatus") or {}
        if status.get("status") != "OK" or details.get("videoId") != video_id or details.get("isLive"):
            raise RuntimeError("PLAYER refused this track")
        candidates = audio_formats(response)
        log("PLAYER {:.2f} s; {} candidate formats".format(time.monotonic() - started, len(candidates)))
        # Bound this probe to one transfer per codec family, as in the SFOS test.
        families = set()
        for item in candidates:
            family = item["mimeType"].split(";", 1)[0]
            if family in families:
                continue
            size = int(item.get("contentLength") or 0)
            if not 0 < size <= 32 * 1024 * 1024:
                continue
            families.add(family)
            path = directory / ("direct.m4a" if family == "audio/mp4" else "direct.webm")
            try:
                return self.transfer(item, size, path)
            except Exception as error:
                log("Direct transfer rejected: {}; trying alternate codec".format(type(error).__name__))
                path.unlink(missing_ok=True)
                self.transport.close()
                self.transport = Transport()
        raise RuntimeError("No verified direct audio file")

    def transfer(self, item, size, path):
        response = self.transport.request("GET", item["url"], {
            "User-Agent": self.client["userAgent"], "Accept": "*/*",
            "Accept-Encoding": "identity", "Range": "bytes=0-{}".format(size - 1),
        })
        started = time.monotonic()
        try:
            log("Audio response: HTTP {}; expected {} bytes".format(response.status, size))
            if response.status not in (200, 206):
                raise RuntimeError("Audio HTTP status rejected")
            if response.status == 206:
                content_range = response.getheader("Content-Range") or ""
                parsed_range = re.fullmatch(r"bytes ([0-9]+)-([0-9]+)/([0-9]+)", content_range)
                if parsed_range:
                    log("Audio range: {}-{} / {}".format(*parsed_range.groups()))
                else:
                    log("Audio range header missing or malformed")
                if content_range != "bytes 0-{}/{}".format(size - 1, size):
                    raise RuntimeError("Unexpected partial audio range")
            count = 0
            with path.open("wb") as output:
                while True:
                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > size:
                        raise RuntimeError("Audio larger than declared")
                    output.write(chunk)
            if count != size:
                log("Incomplete audio: {} / {} bytes".format(count, size))
                raise RuntimeError("Incomplete audio")
            log("Verified {} bytes, itag {}; transfer {:.2f} s".format(count, item.get("itag"), time.monotonic() - started))
            return path
        finally:
            response.close()


class QuietLogger:
    def debug(self, message):
        pass

    def warning(self, message):
        log("yt-dlp warning (raw message omitted)")

    def error(self, message):
        log("yt-dlp error (raw message omitted)")


def download_fallback(video_id, directory):
    import yt_dlp
    options = {
        "format": "140/bestaudio[ext=m4a]/bestaudio",
        "outtmpl": str(directory / "fallback.%(ext)s"),
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "logger": QuietLogger(), "socket_timeout": 20, "retries": 1,
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info("https://music.youtube.com/watch?v=" + video_id, download=True)
        path = Path(downloader.prepare_filename(info))
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError("yt-dlp produced no audio file")
    return path


def prepare_audio(resolver, video_id, directory, *, fallback_only=False):
    if not fallback_only:
        try:
            return resolver.download(video_id, directory), "direct"
        except Exception as error:
            log("Direct failed: {}; falling back to yt-dlp".format(type(error).__name__))
            resolver.close()
            resolver.transport = Transport()
            resolver.headers = None
    return download_fallback(video_id, directory), "yt-dlp"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-id", action="append", help="Repeat to test different tracks")
    parser.add_argument("--repeat", type=int, choices=range(1, 4), default=2)
    parser.add_argument("--play", action="store_true")
    parser.add_argument("--seconds", type=int, choices=range(1, 31), default=5)
    parser.add_argument("--yt-dlp-only", action="store_true", help="Measure the existing extraction path")
    args = parser.parse_args()
    videos = args.video_id or ["ojvldIzbaMo"]
    if any(not re.fullmatch(r"[A-Za-z0-9_-]{11}", video) for video in videos):
        parser.error("Invalid video ID")

    # Match the GUI launcher's Deno lookup without modifying the user's shell.
    import os
    import shutil
    deno_directory = Path(os.environ.get("DENO_INSTALL", str(Path.home() / ".deno"))) / "bin"
    if not shutil.which("deno") and os.access(deno_directory / "deno", os.X_OK):
        os.environ["PATH"] = str(deno_directory) + os.pathsep + os.environ.get("PATH", "")

    log("Importing yt-dlp metadata; anonymous probe, temporary audio")
    import yt_dlp
    log("yt-dlp imported")
    resolver = DirectResolver()
    try:
        for attempt in range(args.repeat):
            for video in videos:
                requested = time.monotonic()
                log("ATTEMPT {}: {}".format(attempt + 1, video))
                with tempfile.TemporaryDirectory(prefix="felismusic-audio-probe-") as directory:
                    path, route = prepare_audio(resolver, video, Path(directory), fallback_only=args.yt_dlp_only)
                    log("FILE READY via {}: {:.2f} s from request".format(route, time.monotonic() - requested))
                    if args.play:
                        play(path, args.seconds, requested)
                log("Sample finished; temporary audio removed")
    finally:
        resolver.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Interrupted")
        sys.exit(130)
    except Exception as error:
        log("FAILED: {} (raw error omitted)".format(type(error).__name__))
        sys.exit(1)
