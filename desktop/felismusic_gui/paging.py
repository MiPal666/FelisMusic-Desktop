"""One-page playlist reads using ytmusicapi's installed parsers.

The public API consumes continuations internally and does not return a cursor.
Capture the initial response on a shallow client copy (never patch the shared
client/session), then consume the exact continuation tokens one at a time.
PlaylistPages covers playlist shelves; WatchPages covers watch continuations.
"""
from copy import copy
from .diagnostics import current_trace
from .playlist_library import playlist_library_controls
from ytmusicapi.continuations import get_continuation_token
from ytmusicapi.navigation import nav
from ytmusicapi.mixins.playlists import (
    TWO_COLUMN_RENDERER, SECTION, CONTENT, CONTINUATION_ITEMS,
)
from ytmusicapi.parsers.playlists import parse_playlist_items


class PlaylistPages:
    def __init__(self, api, playlist_id, *, liked=False):
        self.api = api
        self.playlist_id = playlist_id
        self.liked = liked
        self.token = None
        self.started = False
        self.collaborative = False
        self._seen = set()
        self.metadata = {}

    def next_page(self):
        if not self.started:
            if self.liked:
                self.api._check_auth()
            client = copy(self.api)
            request = self.api._send_request
            responses = []

            def capture(*args, **kwargs):
                response = request(*args, **kwargs)
                responses.append(response)
                return response

            client._send_request = capture
            # In ytmusicapi 1.12.3 limit=0 suppresses continuation requests;
            # the initial shelf is still parsed by the library itself.
            data = client.get_playlist(self.playlist_id, limit=0)
            self.metadata = {key: value for key, value in data.items() if key != 'tracks'}
            if len(responses) != 1:
                raise RuntimeError('Neočekávaný průběh stránkování playlistu.')
            self.metadata['_playlistLibraryControls'] = playlist_library_controls(responses[0], self.playlist_id, data)
            contents = nav(responses[0], [*TWO_COLUMN_RENDERER, 'secondaryContents',
                *SECTION, *CONTENT, 'musicPlaylistShelfRenderer', 'contents'])
            self.collaborative = 'collaborators' in data
            tracks = data.get('tracks') or []
            token = get_continuation_token(contents) if contents else None
        else:
            if not self.token:
                return [], False
            response = self.api._send_request('browse', {'continuation': self.token})
            contents = nav(response, CONTINUATION_ITEMS)
            tracks = parse_playlist_items(contents, is_collaborative=self.collaborative)
            token = get_continuation_token(contents) if contents else None
        if token and (not isinstance(token, str) or token in self._seen):
            raise RuntimeError('YouTube Music opakuje pokračování playlistu.')
        if token:
            self._seen.add(token)
        self.token = token
        self.started = True
        return tracks, bool(token)


class WatchPages:
    """Continue one server-generated watch order, never reshuffle each page."""
    def __init__(self, api, playlist_id, *, shuffle=True, limit=None):
        self.limit, self.count = limit, 0
        self.api, self.playlist_id, self.shuffle = api, playlist_id, shuffle
        self.started = False
        self.body = None
        self.continuation = None
        self._seen = {}
        self._videos = set()
        self._last_videos = None
        self.pages = 0

    def next_page(self):
        self._page_stats = dict(page=self.pages + 1, total_before=self.count,
                               target_count=self.limit or 0)
        self._phase, self._reason = "initial_request" if not self.started else "continuation_request", "request_or_parse"
        try:
            result = self._next_page()
        except Exception as exc:
            trace = current_trace()
            if trace:
                trace.event("shuffle.page_error", error=type(exc).__name__,
                            reason=self._reason, phase=self._phase, **self._page_stats)
            raise
        trace = current_trace()
        if trace:
            trace.event("shuffle.page", **self._page_stats)
        return result

    def _next_page(self):
        from ytmusicapi.continuations import get_continuation_params
        from ytmusicapi.parsers.watch import parse_watch_playlist
        if not self.started:
            client = copy(self.api)
            requests = []
            def capture(endpoint, body, *args, **kwargs):
                response = self.api._send_request(endpoint, body, *args, **kwargs)
                requests.append((dict(body), response))
                self._phase = "initial_parse"
                return response
            client._send_request = capture
            kwargs = {"playlistId": self.playlist_id, "limit": 0}
            if self.shuffle:
                kwargs["shuffle"] = True
            data = client.get_watch_playlist(**kwargs)
            if len(requests) != 1:
                self._reason = "unexpected_initial_requests"
                raise RuntimeError('Neočekávaný průběh stránkování přehrávací fronty.')
            body, response = requests[0]
            panel = nav(response, ['contents', 'singleColumnMusicWatchNextResultsRenderer',
                'tabbedRenderer', 'watchNextTabbedResultsRenderer', 'tabs', 0, 'tabRenderer',
                'content', 'musicQueueRenderer', 'content', 'playlistPanelRenderer'])
            tracks = data.get('tracks') or []
        else:
            if not self.continuation:
                return [], False
            body = self.body
            response = self.api._send_request('next', dict(body), self.continuation)
            self._phase = "continuation_parse"
            panel = nav(response, ['continuationContents', 'playlistPanelContinuation'])
            tracks = parse_watch_playlist(panel['contents'])
        # Same continuation variant as the installed get_watch_playlist.
        path = '' if self.playlist_id.removeprefix('VL').startswith(('PL', 'OLA')) else 'Radio'
        continuation = get_continuation_params(panel, path) if 'continuations' in panel else None
        count = self.count + len(tracks)
        videos = tuple(x.get('videoId') for x in tracks)
        valid_videos = [video for video in videos if isinstance(video, str) and video]
        self._page_stats.update(page_tracks=len(tracks), returned_total=count,
            unique_new=len(set(valid_videos) - self._videos),
            previously_seen_rows=sum(video in self._videos for video in valid_videos),
            duplicate_rows=len(valid_videos) - len(set(valid_videos)),
            same_as_previous=self._last_videos is not None and videos == self._last_videos,
            continuation_present=bool(continuation),
            repeated_continuation=bool(continuation and continuation in self._seen),
            repeated_from_page=self._seen.get(continuation, 0),
            target_reached=self.limit is not None and count >= self.limit)
        self._phase = "continuation_check"
        if self.limit is not None and count >= self.limit:
            continuation = None
        if continuation and continuation in self._seen:
            self._reason = "repeated_continuation"
            raise RuntimeError('YouTube Music opakuje pokračování přehrávací fronty.')
        if continuation:
            self._seen[continuation] = self.pages + 1
        self._videos.update(valid_videos)
        self._last_videos = videos
        self.pages += 1
        self.count = count
        self.body, self.continuation, self.started = body, continuation, True
        return tracks, bool(continuation)


class UploadSongPages:
    """One uploaded-song shelf at a time, in the requested server order."""
    upload = True
    def __init__(self, api, order=None):
        self.api, self.order = api, order
        self.started, self.continuation, self.body = False, None, None
        self._seen = set()

    def next_page(self):
        from ytmusicapi.mixins.uploads import get_library_contents, MUSIC_SHELF
        from ytmusicapi.parsers.uploads import parse_uploaded_items
        from ytmusicapi.continuations import get_continuation_params, get_continuation_contents
        parse_items = parse_uploaded_items if self.upload else parse_playlist_items
        if not self.started:
            client = copy(self.api)
            requests = []
            def capture(endpoint, body, *args, **kwargs):
                response = self.api._send_request(endpoint, body, *args, **kwargs)
                requests.append((dict(body), response))
                return response
            client._send_request = capture
            method = client.get_library_upload_songs if self.upload else client.get_library_songs
            tracks = method(limit=0, order=self.order)
            if len(requests) != 1:
                raise RuntimeError('unexpected_upload_requests')
            body, response = requests[0]
            shelf = get_library_contents(response, MUSIC_SHELF)
        else:
            if not self.continuation:
                return [], False
            body = self.body
            response = self.api._send_request('browse', dict(body), self.continuation)
            shelf = nav(response, ['continuationContents', 'musicShelfContinuation'])
            tracks = get_continuation_contents(shelf, parse_items)
        continuation = get_continuation_params(shelf) if shelf and 'continuations' in shelf else None
        if continuation and continuation in self._seen:
            raise RuntimeError('repeated_upload_continuation')
        if continuation:
            self._seen.add(continuation)
        self.started, self.body, self.continuation = True, body, continuation
        return tracks or [], bool(continuation)


class LibrarySongPages(UploadSongPages):
    """The separate online library source, using its playlist-item parser."""
    upload = False


class LibraryArtistSongPages:
    """Read the exact library artist shelf; never strip its MPLA prefix."""
    def __init__(self, api, browse_id):
        if not browse_id.startswith("MPLAUC"):
            raise ValueError("invalid_library_artist")
        self.api, self.browse_id = api, browse_id
        self.started, self.continuation = False, None
        self._seen = set()

    def next_page(self):
        from ytmusicapi.parsers.library import get_library_contents
        from ytmusicapi.navigation import nav
        from ytmusicapi.continuations import get_continuation_params
        body = {"browseId": self.browse_id}
        if self.started:
            if not self.continuation:
                return [], False
            response = self.api._send_request("browse", body, self.continuation)
            shelf = nav(response, ["continuationContents", "musicShelfContinuation"])
        else:
            response = self.api._send_request("browse", body)
            shelf = get_library_contents(response, ["musicShelfRenderer"])
        if not isinstance(shelf, dict) or not isinstance(shelf.get("contents"), list):
            raise RuntimeError("missing_library_artist_shelf")
        tracks = parse_playlist_items(shelf["contents"])
        continuation = get_continuation_params(shelf) if "continuations" in shelf else None
        if continuation and continuation in self._seen:
            raise RuntimeError("repeated_library_artist_continuation")
        if continuation:
            self._seen.add(continuation)
        self.started, self.continuation = True, continuation
        return tracks, bool(continuation)
