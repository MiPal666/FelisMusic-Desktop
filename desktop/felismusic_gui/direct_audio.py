"""Anonymous InnerTube audio download with bounded transfers and atomic files.

Request shape verified by the FelisMusic-SFOS and desktop probes. Client metadata
comes from installed yt-dlp. Unsupported responses are left to the caller's
existing authenticated yt-dlp fallback.
"""
from copy import deepcopy
import http.client
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import parse_qs, urlsplit
from urllib.request import getproxies


class DirectAudioError(RuntimeError):
    """The anonymous direct path cannot provide a complete audio file."""


class DirectCastURL(str):
    """A string URL carrying the track ID needed for a rejected Cast LOAD retry."""

    def __new__(cls, url, video_id):
        instance = super().__new__(cls, url)
        instance.video_id = video_id
        return instance


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
            connection = http.client.HTTPSConnection(host, timeout=5, source_address=("0.0.0.0", 0))
            self.connections[host] = connection
        target = parsed.path + ("?" + parsed.query if parsed.query else "")
        connection.request(method, target, body=body, headers=headers)
        return connection.getresponse()

    def close(self):
        for connection in self.connections.values():
            connection.close()
        self.connections.clear()


def audio_formats(response):
    selected = []
    for item in (response.get("streamingData") or {}).get("adaptiveFormats", []):
        mime = item.get("mimeType", "")
        url = item.get("url", "")
        if not mime.startswith(("audio/mp4", "audio/webm")) or not url:
            continue
        if item.get("drmFamilies") or item.get("targetDurationSec") or item.get("type") == "FORMAT_STREAM_TYPE_OTF":
            continue
        if "n" in parse_qs(urlsplit(url).query, keep_blank_values=True):
            continue  # Needs JS; use the yt-dlp fallback.
        selected.append(item)
    def score(item):
        track = item.get("audioTrack") or {}
        language = 2 if "original" in track.get("displayName", "").lower() else int(bool(track.get("audioIsDefault")))
        return (language, item.get("itag") == 140, item.get("bitrate", 0))
    return sorted(selected, key=score, reverse=True)


class DirectResolver:
    def __init__(self, *, check_cancelled=None, log=None):
        self.transport = Transport()
        self.check_cancelled = check_cancelled or (lambda: None)
        self.log = log or (lambda message: None)
        self.deadline = None
        self.client = None
        self.headers = None

    def close(self):
        self.transport.close()

    def check(self):
        self.check_cancelled()
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise DirectAudioError("Direct audio preparation timed out")

    def post(self, endpoint, payload):
        self.check()
        body = json.dumps(dict(payload, context={"client": self.client})).encode()
        response = self.transport.request(
            "POST", "https://www.youtube.com/youtubei/v1/" + endpoint + "?prettyPrint=false",
            self.headers, body,
        )
        try:
            data = response.read(8 * 1024 * 1024 + 1)
            self.check()
            if response.status != 200 or len(data) > 8 * 1024 * 1024:
                raise DirectAudioError("PLAYER response rejected")
            return json.loads(data)
        finally:
            response.close()

    def configure(self):
        from yt_dlp.extractor.youtube._base import INNERTUBE_CLIENTS
        config = INNERTUBE_CLIENTS["visionos"]
        if config.get("REQUIRE_JS_PLAYER", True) or config.get("REQUIRE_AUTH"):
            raise DirectAudioError("Installed visionos client requires JS or authentication")
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
            raise DirectAudioError("No visitor ID returned")
        self.headers["X-Goog-Visitor-Id"] = visitor

    def resolve(self, video_id):
        self.deadline = time.monotonic() + 30
        self.check()
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            raise DirectAudioError("Unsupported video ID")
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
            raise DirectAudioError("PLAYER refused this track")
        candidates = audio_formats(response)
        self.log("PLAYER {:.2f} s; {} candidate formats".format(time.monotonic() - started, len(candidates)))
        if not candidates:
            raise DirectAudioError("No plain audio URLs")
        return candidates

    def download(self, video_id, directory):
        candidates = self.resolve(video_id)
        # Try one transfer per codec family before the authenticated fallback.
        families = set()
        for item in candidates:
            family = item["mimeType"].split(";", 1)[0]
            if family in families:
                continue
            size = int(item.get("contentLength") or 0)
            if not 0 < size <= 256 * 1024 * 1024:
                continue
            families.add(family)
            suffix = ".m4a" if family == "audio/mp4" else ".webm"
            descriptor, temporary = tempfile.mkstemp(prefix="direct-", suffix=suffix + ".part", dir=directory)
            os.close(descriptor)
            path = Path(temporary)
            complete = path.with_suffix("")
            try:
                self.transfer(item, size, path)
                self.check()
                os.replace(path, complete)
                return complete
            except (OSError, ValueError, http.client.HTTPException, DirectAudioError) as error:
                self.log("Direct transfer rejected: {}; trying alternate codec".format(type(error).__name__))
                self.transport.close()
                self.transport = Transport()
            finally:
                path.unlink(missing_ok=True)
        raise DirectAudioError("No verified direct audio file")

    def transfer(self, item, size, path):
        self.check()
        response = self.transport.request("GET", item["url"], {
            "User-Agent": self.client["userAgent"], "Accept": "*/*",
            "Accept-Encoding": "identity", "Range": "bytes=0-{}".format(size - 1),
        })
        started = time.monotonic()
        try:
            self.log("Audio response: HTTP {}; expected {} bytes".format(response.status, size))
            if response.status not in (200, 206):
                raise DirectAudioError("Audio HTTP status rejected")
            if response.status == 206:
                content_range = response.getheader("Content-Range") or ""
                parsed_range = re.fullmatch(r"bytes ([0-9]+)-([0-9]+)/([0-9]+)", content_range)
                if parsed_range:
                    self.log("Audio range: {}-{} / {}".format(*parsed_range.groups()))
                else:
                    self.log("Audio range header missing or malformed")
                if content_range != "bytes 0-{}/{}".format(size - 1, size):
                    raise DirectAudioError("Unexpected partial audio range")
            count = 0
            with path.open("wb") as output:
                while True:
                    self.check()
                    chunk = response.read(64 * 1024)
                    self.check()
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > size:
                        raise DirectAudioError("Audio larger than declared")
                    output.write(chunk)
            if count != size:
                self.log("Incomplete audio: {} / {} bytes".format(count, size))
                raise DirectAudioError("Incomplete audio")
            self.log("Verified {} bytes, itag {}; transfer {:.2f} s".format(count, item.get("itag"), time.monotonic() - started))
            return path
        finally:
            response.close()


def download_audio(video_id, directory, *, check_cancelled, log=None):
    # The direct transport binds API and media to IPv4. Respect configured proxies
    # by letting the existing yt-dlp transport handle such environments.
    proxies = getproxies()
    if any(proxies.get(scheme) for scheme in ("http", "https", "all")):
        raise DirectAudioError("Proxy configured; use yt-dlp transport")
    resolver = DirectResolver(check_cancelled=check_cancelled, log=log)
    try:
        return str(resolver.download(video_id, Path(directory)))
    finally:
        resolver.close()


def resolve_cast_url(video_id):
    proxies = getproxies()
    if any(proxies.get(scheme) for scheme in ("http", "https", "all")):
        raise DirectAudioError("Proxy configured; use yt-dlp transport")
    resolver = DirectResolver()
    try:
        for item in resolver.resolve(video_id):
            if item["mimeType"].startswith("audio/mp4"):
                parsed = urlsplit(item["url"])
                if (parsed.scheme == "https" and parsed.port in (None, 443)
                        and (parsed.hostname or "").endswith(".googlevideo.com")):
                    return DirectCastURL(item["url"], video_id)
        raise DirectAudioError("No direct AAC URL for Cast")
    finally:
        resolver.close()
