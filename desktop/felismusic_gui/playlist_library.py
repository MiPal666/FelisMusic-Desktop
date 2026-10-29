"""Explicit save controls for foreign, finite playlists; never delete ownership."""
from copy import copy
from .album_library import album_library_controls


def playlist_library_controls(response, playlist_id, data):
    playlist_id = str(playlist_id or '').removeprefix('VL')
    if (data.get('owned') is not False or not playlist_id or playlist_id in ('LM', 'SE', 'HL')
            or playlist_id.startswith(('RD', 'OLAK', 'ML'))):
        return None
    if data.get('id') and str(data['id']).removeprefix('VL') != playlist_id:
        return None
    return album_library_controls(response, playlist_id)


def load_library_playlist(api, playlist_id):
    client = copy(api)
    send = api._send_request
    responses = []

    def capture(*args, **kwargs):
        response = send(*args, **kwargs)
        responses.append(response)
        return response

    client._send_request = capture
    data = dict(client.get_playlist(playlist_id, limit=0))
    data['_playlistLibraryControls'] = (playlist_library_controls(responses[0], playlist_id, data)
                                        if len(responses) == 1 else None)
    return data
