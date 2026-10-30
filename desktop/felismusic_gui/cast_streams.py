"""One speculative Cast URL, in memory only and scoped to queue/connection."""
from threading import Lock
from math import isfinite
from time import monotonic, time
from urllib.parse import parse_qs, urlsplit


class CastStreamCache:
    MAX_AGE = 600
    EXPIRY_MARGIN = 30

    def __init__(self):
        self._lock = Lock()
        self._entry = self._pending = None

    def clear(self):
        with self._lock:
            self._entry = self._pending = None

    def reserve(self, key):
        with self._lock:
            if self._entry and self._entry[0] == key and self._entry[2] > monotonic():
                return None
            if self._pending and self._pending[1] == key:
                return None
            self._entry = None
            self._pending = (object(), key)
            return self._pending

    def complete(self, ticket, source=None):
        with self._lock:
            if self._pending is not ticket:
                return False
            self._pending = None
            if source is None:
                return False
            ttl = self.MAX_AGE
            try:
                expiry = parse_qs(urlsplit(source[0]).query).get("expire")
                if expiry:
                    remaining = float(expiry[0]) - time() - self.EXPIRY_MARGIN
                    if not isfinite(remaining):
                        return False
                    ttl = min(ttl, remaining)
            except (ValueError, TypeError, OverflowError):
                return False
            if not 0 < ttl <= self.MAX_AGE:
                return False
            self._entry = (ticket[1], source, monotonic() + ttl)
            return True

    def take(self, key):
        with self._lock:
            entry, self._entry = self._entry, None
            if entry and entry[0] == key and entry[2] > monotonic():
                return entry[1]
            return None
