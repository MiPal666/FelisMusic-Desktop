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
from pathlib import Path
import re
import sys
import tempfile


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
from felismusic_gui.direct_audio import DirectResolver, Transport, audio_formats


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
    resolver = DirectResolver(log=log)
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
