#!/usr/bin/env python3
"""Read-only playlist diagnosis: ordinary contents or legacy Shuffle + replay.

Responses and continuation tokens exist only in RAM. No audio, history writes,
playlist edits, credential dumps, or second randomly generated server queue.
"""
import argparse
from copy import copy, deepcopy
from pathlib import Path
import sys
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from felismusic_gui import legacy_core as core
from felismusic_gui.paging import WatchPages
from ytmusicapi import YTMusic
from ytmusicapi.navigation import nav
from ytmusicapi.mixins.playlists import TWO_COLUMN_RENDERER, SECTION, CONTENT, CONTINUATION_ITEMS
from ytmusicapi.parsers.playlists import parse_playlist_items


class ComparisonFailure(RuntimeError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def compare(api, playlist_id, limit, *, max_requests=100, timeout=180, emit=print):
    records = []
    started = monotonic()
    original = copy(api)

    def capture(endpoint, body, *args, **kwargs):
        if len(records) >= max_requests:
            raise ComparisonFailure('request_limit')
        if monotonic() - started >= timeout:
            raise ComparisonFailure('time_limit')
        signature = deepcopy((endpoint, body, args, kwargs))
        response = api._send_request(endpoint, body, *args, **kwargs)
        records.append((signature, deepcopy(response), deepcopy(body)))
        emit(f'Původní postup: odpověď {len(records)} přijata.')
        return response

    original._send_request = capture
    # The exact helper used before progressive shuffle, including its limits.
    old = core.get_youtube_shuffle_tracks(original, playlist_id, limit)
    replay = copy(api)
    replay_index = 0

    def replay_request(endpoint, body, *args, **kwargs):
        nonlocal replay_index
        if replay_index >= len(records):
            raise ComparisonFailure('replay_exhausted')
        signature, response, sent_body = records[replay_index]
        if (endpoint, body, args, kwargs) != signature:
            raise ComparisonFailure('replay_request_mismatch')
        # ytmusicapi._send_request mutates the caller's body with its client
        # context. Reproduce that side effect, not just the returned response.
        # Keep strict pre-call matching; never ignore arbitrary body differences.
        body.clear()
        body.update(deepcopy(sent_body))
        replay_index += 1
        return deepcopy(response)

    replay._send_request = replay_request
    pager = WatchPages(replay, playlist_id, limit=max(25, int(limit or 25)))
    new = []
    error = None
    while True:
        try:
            tracks, more = pager.next_page()
        except ComparisonFailure:
            raise
        except Exception as exc:
            # Only locally defined fixed reasons; never external exception text.
            error = dict(type=type(exc).__name__, reason=pager._reason,
                         phase=pager._phase, **pager._page_stats)
            break
        new.extend(core.usable_tracks(tracks))
        emit(f'Nový postup (místní replay): stránka {pager.pages}, celkem {len(new)} položek.')
        if not more:
            break
    old_ids, new_ids = ([x['videoId'] for x in rows] for rows in (old, new))
    signatures = [entry[0] for entry in records]
    repeated_requests = sum(signature in signatures[:i] for i, signature in enumerate(signatures))
    return dict(old_count=len(old_ids), old_unique=len(set(old_ids)),
                old_duplicate_rows=len(old_ids) - len(set(old_ids)), old_requests=len(records),
                repeated_requests=repeated_requests, new_count=len(new_ids),
                new_unique=len(set(new_ids)), replay_requests=replay_index,
                same_order_prefix=new_ids == old_ids[:len(new_ids)], error=error)


def inspect_playlist(api, playlist_id, *, max_requests=100, timeout=180, emit=print):
    """Read the ordinary playlist with the installed public API, without shuffle.

    Do not impose the manually supplied shuffle target or deduplicate rows.
    Check exact requests before sending them, so a cycle cannot fill a limit.
    """
    client = copy(api)
    signatures = []
    raw_pages = []
    started = monotonic()

    def capture(endpoint, body, *args, **kwargs):
        signature = deepcopy((endpoint, body, args, kwargs))
        if signature in signatures:
            raise ComparisonFailure('ordinary_repeated_request')
        if len(signatures) >= max_requests:
            raise ComparisonFailure('ordinary_request_limit')
        if monotonic() - started >= timeout:
            raise ComparisonFailure('ordinary_time_limit')
        signatures.append(signature)
        response = api._send_request(endpoint, body, *args, **kwargs)
        if len(signatures) == 1:
            contents = nav(response, [*TWO_COLUMN_RENDERER, 'secondaryContents',
                *SECTION, *CONTENT, 'musicPlaylistShelfRenderer', 'contents'], True)
        else:
            contents = nav(response, CONTINUATION_ITEMS, True)
        if not isinstance(contents, list):
            raise ComparisonFailure('ordinary_unrecognized_raw_page')
        raw_pages.append(contents)
        emit(f'Běžný playlist: odpověď {len(signatures)} přijata.')
        return response

    client._send_request = capture
    # None is intentionally unlimited. related/suggestions stay disabled.
    data = client.get_playlist(playlist_id, limit=None)
    tracks = data.get('tracks')
    if not isinstance(tracks, list):
        raise ComparisonFailure('ordinary_missing_tracks')
    ids = [row.get('videoId') for row in tracks]
    valid_ids = [vid for vid in ids if isinstance(vid, str) and vid]
    # Only numeric metadata may leave this function, never a returned title,
    # token, request body, or free-form exception message.
    count = data.get('trackCount')
    if isinstance(count, str) and count.isascii() and count.isdecimal():
        count = int(count)
    if type(count) is not int or count < 0:
        count = None
    raw = dict(raw_items=0, raw_song_rows=0, raw_continuations=0,
               raw_other_rows=0, raw_grey_rows=0, parser_skipped_rows=0,
               raw_parsed_rows=0, raw_pages_with_continuation=0)
    for contents in raw_pages:
        song_rows = [item for item in contents if 'musicResponsiveListItemRenderer' in item]
        continuation_rows = sum('continuationItemRenderer' in item for item in contents)
        parsed = parse_playlist_items(contents, is_collaborative='collaborators' in data)
        raw['raw_items'] += len(contents)
        raw['raw_song_rows'] += len(song_rows)
        raw['raw_continuations'] += continuation_rows
        raw['raw_other_rows'] += len(contents) - len(song_rows) - continuation_rows
        raw['raw_grey_rows'] += sum(item['musicResponsiveListItemRenderer'].get(
            'musicItemRendererDisplayPolicy') == 'MUSIC_ITEM_RENDERER_DISPLAY_POLICY_GREY_OUT'
            for item in song_rows)
        raw['parser_skipped_rows'] += len(song_rows) - len(parsed)
        raw['raw_parsed_rows'] += len(parsed)
        raw['raw_pages_with_continuation'] += bool(continuation_rows)
    return dict(reported_count=count, rows=len(tracks), video_rows=len(valid_ids),
                unique_videos=len(set(valid_ids)),
                duplicate_rows=len(valid_ids) - len(set(valid_ids)),
                missing_video_rows=len(tracks) - len(valid_ids),
                usable_rows=len(core.usable_tracks(tracks)), requests=len(signatures), **raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--playlist', help='Playlist ID; bez něj nabídne výběr z knihovny.')
    parser.add_argument('--ordinary', action='store_true', help='Běžný obsah playlistu bez Shuffle, bez cílového limitu.')
    parser.add_argument('--limit', type=int, help='Počet skladeb zdrojové kolekce v GUI (jen srovnání Shuffle).')
    args = parser.parse_args(argv)
    if not args.ordinary and args.limit is None:
        parser.error('srovnání Shuffle vyžaduje --limit; běžný obsah použije --ordinary')
    if args.limit is not None and not 1 <= args.limit <= 10000:
        parser.error('--limit musí být od 1 do 10000')
    if args.ordinary and args.limit is not None:
        parser.error('--ordinary nepoužívá --limit')
    print('Pouze čtení; žádné přehrávání ani změny knihovny. Odpovědi se neukládají na disk.')
    try:
        api = YTMusic(core.AUTH.ytmusic_headers())
        pid = args.playlist
        if not pid:
            playlists = api.get_library_playlists(limit=None)
            choices = [('LL', 'Oblíbená hudba')] + [
                (x['playlistId'], x.get('title') or 'Playlist') for x in playlists if x.get('playlistId')]
            for index, (_, title) in enumerate(choices, 1):
                print(f'{index}. {title}')
            choice = int(input('Číslo STEJNÉHO playlistu jako v problémovém pokusu: '))
            if not 1 <= choice <= len(choices):
                raise ComparisonFailure('invalid_selection')
            pid = choices[choice - 1][0]
        if args.ordinary:
            # get_liked_songs uses the browse playlist LM; LL is the watch ID.
            report = inspect_playlist(api, 'LM' if pid == 'LL' else pid)
            print('\nBĚŽNÝ OBSAH PLAYLISTU BEZ SHUFFLE:')
            count = report['reported_count']
            print('Počet v metadatech YTM: ' + (str(count) if count is not None else 'API neuvedlo'))
            print(f"Načteno položek: {report['rows']}; přehratelných podle GUI: {report['usable_rows']}.")
            print(f"Různých videoId: {report['unique_videos']}; opakovaných výskytů: {report['duplicate_rows']}; "
                  f"položek bez videoId: {report['missing_video_rows']}.")
            print(f"Síťové požadavky: {report['requests']}; bez shodně opakovaných požadavků.")
            print(f"Surové odpovědi: {report['raw_song_rows']} řádků skladeb; "
                  f"z toho označeno nedostupných (GREY_OUT): {report['raw_grey_rows']}.")
            print(f"Parser vynechal řádků skladeb: {report['parser_skipped_rows']}; "
                  f"po opětovném místním parsování: {report['raw_parsed_rows']} položek.")
            print(f"Pomocné řádky: pokračování {report['raw_continuations']}, "
                  f"ostatní {report['raw_other_rows']}; nejsou započtené jako skladby.")
            if count is not None:
                print(f"Rozdíl metadata minus surové řádky skladeb: {count - report['raw_song_rows']}.")
            print(f"Rozdíl místní parsování minus výsledek knihovny: {report['raw_parsed_rows'] - report['rows']}.")
            print('Běžné načítání dokončeno knihovnou; žádný ručně zadaný cílový počet.')
            print('Duplicity nebyly odstraněny. Dokončení samo nezaručuje shodu s počtem ve webovém YTM.')
            return 0
        report = compare(api, pid, args.limit)
        print('\nSROVNÁNÍ STEJNÝCH ODPOVĚDÍ YTM (nový postup už bez sítě):')
        print(f"Původní: {report['old_count']} položek, {report['old_unique']} různých videoId, "
              f"{report['old_duplicate_rows']} opakovaných výskytů.")
        print(f"Síťové požadavky: {report['old_requests']}, z toho shodně opakovaných: {report['repeated_requests']}.")
        print(f"Nový: {report['new_count']} přijatých položek, {report['new_unique']} různých videoId.")
        print('Stejné pořadí společného začátku: ' + ('ANO' if report['same_order_prefix'] else 'NE'))
        if report['error']:
            print('Důvod zastavení nového postupu: ' + str(report['error']))
        else:
            print('Nový postup dokončen bez chyby.')
        print('Běžné duplicity v uloženém playlistu mohou být úmyslné; samotný jejich počet není důkaz chyby.')
        return 0
    except (EOFError, KeyboardInterrupt):
        print('\nTest ukončen.'); return 1
    except Exception as exc:
        reason = exc.reason if isinstance(exc, ComparisonFailure) else type(exc).__name__
        print(('Běžné načítání nedokončeno: ' if args.ordinary else 'Srovnávací test nedokončen: ') + reason)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
