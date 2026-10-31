"""Recognize typed network causes, including yt-dlp's exception wrappers."""
import errno
import socket
from urllib.error import URLError
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout
from yt_dlp.networking.exceptions import TransportError


_NETWORK_ERRNOS = {errno.ENETDOWN, errno.ENETUNREACH, errno.EHOSTUNREACH,
                        errno.ECONNREFUSED, errno.ECONNRESET, errno.ECONNABORTED,
                        errno.ETIMEDOUT}


def is_network_failure(error):
    """Do not classify localized error text or every DownloadError as offline."""
    pending, seen = [error], set()
    while pending:
        exc = pending.pop()
        if not isinstance(exc, BaseException) or id(exc) in seen:
            continue
        seen.add(id(exc))
        if isinstance(exc, (TransportError, RequestsConnectionError, Timeout,
                            TimeoutError, socket.gaierror)):
            return True
        if isinstance(exc, OSError) and exc.errno in _NETWORK_ERRNOS:
            return True
        for attr in ('cause', '__cause__'):
            pending.append(getattr(exc, attr, None))
        if not exc.__suppress_context__:
            pending.append(exc.__context__)
        info = getattr(exc, 'exc_info', None)
        if isinstance(info, tuple) and len(info) == 3:
            pending.append(info[1])
        if isinstance(exc, URLError):
            pending.append(exc.reason)
    return False
