"""Canonical YTM links from known public entity IDs, without API lookups."""
import re


_ID = r"[A-Za-z0-9_-]+"
_PATHS = (
    rf"watch\?v={_ID}",
    rf"playlist\?list=(?:PL|OLAK5uy){_ID}",
    rf"browse/MPRE{_ID}",
    rf"channel/UC{_ID}",
)
_URL = re.compile(r"https://music\.youtube\.com/(?:" + "|".join(_PATHS) + r")")


def valid_public_link(url):
    return isinstance(url, str) and len(url) <= 512 and _URL.fullmatch(url) is not None


def public_link(item):
    kind = item.get("kind")
    if item.get("dynamicMix") or item.get("entityId"):
        return ""
    if kind in ("song", "video"):
        path = "watch?v=" + str(item.get("videoId") or "")
    elif kind in ("album", "single", "ep"):
        path = "browse/" + str(item.get("browseId") or "")
    elif kind == "artist":
        path = "channel/" + str(item.get("browseId") or "").removeprefix("MPLA")
    elif kind == "playlist":
        path = "playlist?list=" + str(item.get("playlistId") or "").removeprefix("VL")
    else:
        return ""
    url = "https://music.youtube.com/" + path
    return url if valid_public_link(url) else ""
