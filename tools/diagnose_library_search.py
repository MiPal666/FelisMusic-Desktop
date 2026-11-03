#!/usr/bin/env python3
"""Read-only library search probe: structure/error types, never response text or tokens."""
import argparse
import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
import requests
from ytmusicapi import YTMusic
from felismusic_gui import legacy_core as core
from felismusic_gui.search import search_music


STRUCTURE_KEYS = {'contents', 'content', 'tabs', 'selected', 'continuations',
                  'continuationContents', 'onResponseReceivedActions'}
SAFE_ERROR_KEYS = {'contents', 'content', 'tabs', 'tabRenderer', 'sectionListRenderer',
                   'musicShelfRenderer', 'itemSectionRenderer'}


def shape(value, depth=0):
    if depth > 14:
        return 'depth limit'
    if isinstance(value, dict):
        return {key: shape(child, depth + 1) for key, child in value.items()
                if key in STRUCTURE_KEYS or key.endswith('Renderer')}
    if isinstance(value, list):
        return {'length': len(value), 'first': [shape(child, depth + 1) for child in value[:3]]}
    if isinstance(value, bool):
        return value
    return type(value).__name__


def error_summary(error):
    result = {'error_type': type(error).__name__}
    if (isinstance(error, KeyError) and len(error.args) == 1
            and isinstance(error.args[0], str) and error.args[0] in SAFE_ERROR_KEYS):
        result['missing_key'] = error.args[0]
    frames = traceback.extract_tb(error.__traceback__)
    if frames:
        # Only file basename/line. Source lines and exception messages may contain data.
        result['last_frame'] = f'{Path(frames[-1].filename).name}:{frames[-1].lineno}'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query', help='The expression that fails in Library search')
    parser.add_argument('--adapted', action='store_true', help='Use the FelisMusic tab-selection adapter')
    args = parser.parse_args()
    session = requests.Session()
    request = session.request

    def bounded(method, url, **kwargs):
        kwargs['timeout'] = (5, 20)
        return request(method, url, **kwargs)

    session.request = bounded
    try:
        api = YTMusic(core.AUTH.ytmusic_headers(), requests_session=session)
        send = api._send_request

        def capture(endpoint, body, *extra, **kwargs):
            response = send(endpoint, body, *extra, **kwargs)
            if endpoint == 'search':
                print(json.dumps({'response_type': type(response).__name__,
                                  'has_error': isinstance(response, dict) and 'error' in response,
                                  'contents_shape': shape(response.get('contents'))
                                      if isinstance(response, dict) else None}, ensure_ascii=False), flush=True)
            return response

        api._send_request = capture
        for category in ('songs', 'albums', 'artists'):
            print(json.dumps({'scope': 'library', 'filter': category,
                              'parser': 'adapted' if args.adapted else 'upstream'}), flush=True)
            try:
                rows = (search_music(api, args.query, filter=category, scope='library', limit=5)
                        if args.adapted else api.search(args.query, filter=category, scope='library', limit=5))
                print(json.dumps({'result_count': len(rows)}), flush=True)
            except Exception as error:
                print(json.dumps(error_summary(error)), flush=True)
    except Exception as error:
        print(json.dumps({'initialization': error_summary(error)}), flush=True)
        return 1
    finally:
        session.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
