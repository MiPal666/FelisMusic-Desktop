"""Retain the album header's explicit library control from the same browse read."""
from copy import copy
from ytmusicapi.navigation import nav
from ytmusicapi.parsers.albums import TWO_COLUMN_RENDERER, TAB_CONTENT, SECTION_LIST_ITEM, RESPONSIVE_HEADER


def album_library_controls(response, playlist_id):
    header = nav(response, [*TWO_COLUMN_RENDERER, *TAB_CONTENT, *SECTION_LIST_ITEM, *RESPONSIVE_HEADER], True)
    if not isinstance(header, dict) or not isinstance(playlist_id, str) or not playlist_id:
        return None
    controls = []
    for button in header.get('buttons') or []:
        toggle = button.get('toggleButtonRenderer') or {}
        toggled = toggle.get('isToggled')
        if not isinstance(toggled, bool):
            continue
        endpoints = [(toggle.get(key) or {}).get('likeEndpoint') or {}
                     for key in ('defaultServiceEndpoint', 'toggledServiceEndpoint')]
        if (any((endpoint.get('target') or {}).get('playlistId') != playlist_id for endpoint in endpoints)
                or {endpoint.get('status') for endpoint in endpoints} != {'LIKE', 'INDIFFERENT'}):
            continue
        # Both endpoints remain fixed after a write. isToggled chooses which
        # action is currently offered; removing LIKE means the album is saved.
        status = endpoints[int(toggled)]['status']
        controls.append(dict(playlistId=playlist_id, inLibrary=status == 'INDIFFERENT'))
    return controls[0] if len(controls) == 1 else None


def load_catalog_album(api, browse_id):
    client = copy(api)
    send = api._send_request
    responses = []

    def capture(*args, **kwargs):
        response = send(*args, **kwargs)
        responses.append(response)
        return response

    client._send_request = capture
    data = dict(client.get_album(browse_id))
    data['_albumLibraryControls'] = (album_library_controls(responses[0], data.get('audioPlaylistId'))
                                     if len(responses) == 1 else None)
    return data
