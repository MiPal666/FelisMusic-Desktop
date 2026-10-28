"""Preserve upload navigation links omitted by the album parser."""
from copy import copy


ARTIST_PREFIX = 'FEmusic_library_privately_owned_artist'


def _row_artist_links(response):
    found = {}

    def visit(value):
        if isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, dict):
            row = value.get('musicResponsiveListItemRenderer')
            if isinstance(row, dict):
                items = row.get('menu', {}).get('menuRenderer', {}).get('items', [])
                video_id, links = '', []
                for item in items:
                    service = item.get('menuServiceItemRenderer', {}).get('serviceEndpoint', {})
                    target = service.get('queueAddEndpoint', {}).get('queueTarget', {})
                    video_id = video_id or target.get('videoId', '')
                    endpoint = item.get('menuNavigationItemRenderer', {}).get('navigationEndpoint', {})
                    artist_id = endpoint.get('browseEndpoint', {}).get('browseId', '')
                    if isinstance(artist_id, str) and artist_id.startswith(ARTIST_PREFIX):
                        if not any(link['id'] == artist_id for link in links):
                            links.append({'id': artist_id, 'name': 'Interpret'})
                if video_id and links:
                    found[video_id] = links
            for child in value.values():
                visit(child)

    visit(response)
    return found


def load_upload_album(api, browse_id):
    # Observe the same request used by the public parser, on a shallow client
    # copy. Do not replace the shared client's method or make a second request.
    client = copy(api)
    send = api._send_request
    links = {}

    def capture(*args, **kwargs):
        response = send(*args, **kwargs)
        links.update(_row_artist_links(response))
        return response

    client._send_request = capture
    data = client.get_library_upload_album(browse_id)
    for row in data.get('tracks') or []:
        artists = row.get('artistLinks') or row.get('artists') or []
        has_private_id = any(isinstance(x, dict) and str(x.get('id') or '').startswith(ARTIST_PREFIX)
                             for x in artists)
        if not has_private_id and row.get('videoId') in links:
            row['artistLinks'] = links[row['videoId']]
    return data
