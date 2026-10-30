"""Read the server-issued Library Profiles filter, distinct from podcast channels."""
from ytmusicapi.continuations import get_continuation_token
from ytmusicapi.parsers.library import parse_artists
from ytmusicapi.parsers.browsing import parse_content_list, parse_playlist, parse_video

PROFILE_FILTER = 'FEmusic_library_user_profile_channels_list'


def _objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _objects(child)


def _sections(response):
    tabs = response.get('contents', {}).get('singleColumnBrowseResultsRenderer', {}).get('tabs', [])
    tabs = [t.get('tabRenderer', {}) for t in tabs]
    selected = next((t for t in tabs if t.get('selected')), tabs[0] if tabs else {})
    sections = selected.get('content', {}).get('sectionListRenderer')
    if not isinstance(sections, dict):
        raise ValueError('Missing selected section list')
    return sections


def _browse_commands(command):
    if not isinstance(command, dict):
        return
    endpoint = command.get('browseEndpoint')
    if isinstance(endpoint, dict):
        yield {k: endpoint[k] for k in ('browseId', 'params') if k in endpoint}
    for child in command.get('commandExecutorCommand', {}).get('commands', []):
        yield from _browse_commands(child)


def _block(response, renderer, continuation=False):
    if continuation:
        block = response.get('continuationContents', {}).get(renderer.replace('Renderer', 'Continuation'))
        if isinstance(block, dict):
            return block
        for action in response.get('onResponseReceivedActions', []):
            items = action.get('appendContinuationItemsAction', {}).get('continuationItems')
            if isinstance(items, list):
                return {'contents' if renderer == 'musicShelfRenderer' else 'items': items}
        raise ValueError('Missing continuation')
    sections = _sections(response)
    candidates = []
    for row in sections.get('contents', []):
        if renderer in row:
            candidates.append(row[renderer])
        for inner in row.get('itemSectionRenderer', {}).get('contents', []):
            if renderer in inner:
                candidates.append(inner[renderer])
    if len(candidates) == 1:
        return candidates[0]
    if not candidates and any('messageRenderer' in obj for obj in _objects(sections.get('contents', []))):
        return {'contents' if renderer == 'musicShelfRenderer' else 'items': []}
    raise ValueError('Missing or ambiguous content renderer')


def _token(block):
    contents = block.get('contents', block.get('items', []))
    token = get_continuation_token(contents) if contents else None
    if not token:
        entries = block.get('continuations') or []
        if entries:
            token = (entries[0].get('nextContinuationData') or {}).get('continuation')
    return token


def load_library_profiles(api):
    api._check_auth()
    landing = api._send_request('browse', {'browseId': 'FEmusic_library_landing'})
    endpoints = []
    for obj in _objects(_sections(landing).get('header', {})):
        chip = obj.get('chipCloudChipRenderer')
        if isinstance(chip, dict):
            endpoints.extend(e for e in _browse_commands(chip.get('navigationEndpoint'))
                             if e.get('browseId') == PROFILE_FILTER and e.get('params'))
    unique = {(e['browseId'], e['params']) for e in endpoints}
    if len(unique) != 1:
        raise ValueError('Missing or ambiguous Profiles filter')
    browse_id, params = unique.pop()
    response = api._send_request('browse', {'browseId': browse_id, 'params': params})
    result, seen, ids = [], set(), set()
    continuation = False
    while True:
        block = _block(response, 'musicShelfRenderer', continuation)
        rows = block.get('contents')
        if not isinstance(rows, list):
            raise ValueError('Invalid Profiles contents')
        for row in rows:
            if 'musicResponsiveListItemRenderer' not in row:
                if any(key in row for key in ('continuationItemRenderer', 'messageRenderer')):
                    continue
                raise ValueError('Unsupported Profiles row')
            parsed = parse_artists([row])[0]
            if parsed.get('type') != 'channel':
                raise ValueError('Non-profile in Profiles filter')
            if parsed['browseId'] not in ids:
                ids.add(parsed['browseId'])
                result.append(parsed)
        token = _token(block)
        if not token:
            return result
        if token in seen:
            raise ValueError('Repeated Profiles continuation')
        seen.add(token)
        response = api._send_request('browse', {'continuation': token})
        continuation = True


def load_profile(api, browse_id):
    response = api._send_request('browse', {'browseId': browse_id})
    header = response.get('header', {}).get('musicVisualHeaderRenderer')
    if not isinstance(header, dict):
        raise ValueError('Not a user profile')
    name = ''.join(r.get('text', '') for r in header.get('title', {}).get('runs', []))
    if not name:
        raise ValueError('Missing profile title')
    data = api.parser.parse_channel_contents(_sections(response).get('contents', []))
    return dict(data, name=name, thumbnails=header.get('foregroundThumbnail', {}).get('musicThumbnailRenderer', {}).get('thumbnail', {}).get('thumbnails', []))


def load_profile_page(api, browse_id, section, state):
    """One page only; never download a large channel's entire video history."""
    if section not in ('videos', 'playlists') or state.get('complete'):
        raise ValueError('Invalid profile section state')
    started = state.get('started', False)
    body = ({'continuation': state['token']} if started else
            {'browseId': browse_id, 'params': state['params']})
    response = api._send_request('browse', body)
    block = _block(response, 'gridRenderer', started)
    rows = block.get('items')
    if not isinstance(rows, list):
        raise ValueError('Missing profile grid')
    if any(not any(key in row for key in ('musicTwoRowItemRenderer', 'continuationItemRenderer', 'messageRenderer'))
           for row in rows):
        raise ValueError('Unsupported profile grid row')
    items = parse_content_list(rows, parse_video if section == 'videos' else parse_playlist)
    token = _token(block)
    seen = list(state.get('seen', []))
    if token and token in seen:
        raise ValueError('Repeated profile continuation')
    if token:
        seen.append(token)
    return items, dict(state, started=True, token=token, seen=seen, complete=not token)
