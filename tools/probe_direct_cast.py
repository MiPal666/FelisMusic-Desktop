#!/usr/bin/env python3
"""Play direct InnerTube audio URLs on a named Cast, with the existing fallback.

The selected Cast downloads the audio itself. Each sample checks actual PLAYING
position advancement, seeks to 30 seconds, and checks advancement again.
"""
import argparse
import contextlib
import io
import logging
from pathlib import Path
import re
import sys
import time
from threading import Event

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from felismusic_gui.direct_audio import DirectResolver, DirectAudioError
from felismusic_gui.cast_output import CastController
from felismusic_gui import legacy_core as core
import pychromecast

START = time.monotonic()


def log(message):
    print('[+{:6.2f} s] {}'.format(time.monotonic() - START, message), flush=True)


def wait_for_position(controller, url, minimum, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        controller.update_status()
        status = controller.status
        if status.content_id == url:
            if status.player_state == 'IDLE' and status.idle_reason == 'ERROR':
                raise RuntimeError('Cast reported a playback error')
            if status.player_state == 'PLAYING' and status.adjusted_current_time >= minimum:
                return
        elif status.content_id:
            raise RuntimeError('Cast content changed during the sample')
        Event().wait(0.2)
    raise RuntimeError('Cast playback position did not advance')


def play_sample(controller, url, content_type, seconds, requested):
    controller.play_media(url, content_type, stream_type='BUFFERED', title='FelisMusic Cast test')
    controller.block_until_active(timeout=15)
    log('Cast LOAD confirmed; waiting for playback position')
    wait_for_position(controller, url, 0.2)
    log('REQUEST TO PLAYING: {:.2f} s; please confirm audible sound'.format(time.monotonic() - requested))
    time.sleep(seconds)
    seek_started = time.monotonic()
    log('Seeking to 30 s')
    controller.seek(30, timeout=5)
    wait_for_position(controller, url, 30.2)
    log('Seek to 30 s confirmed in {:.2f} s'.format(time.monotonic() - seek_started))
    time.sleep(seconds)


def test_track(resolver, controller, video_id, seconds, owned_urls, *, fallback_only=False):
    requested = time.monotonic()
    if not fallback_only:
        try:
            candidates = resolver.resolve(video_id)
            # Match the application's preferred AAC/m4a format for Cast.
            item = next(item for item in candidates if item['mimeType'].startswith('audio/mp4'))
            url = item['url']
            owned_urls.add(url)
            log('Direct URL ready in {:.2f} s; itag {}'.format(time.monotonic() - requested, item.get('itag')))
            play_sample(controller, url, 'audio/mp4', seconds, requested)
            log('DIRECT PLAY AND SEEK PASSED')
            return 'direct'
        except Exception as error:
            log('Direct sample failed: {}; trying yt-dlp'.format(type(error).__name__))
            if controller.status.content_id in owned_urls:
                controller.stop()
    requested = time.monotonic()
    # Keep raw downloader errors, which may contain signed URLs, out of the log.
    with contextlib.redirect_stderr(io.StringIO()):
        url, content_type = core.get_yt_dlp_audio_stream(video_id)
    owned_urls.add(url)
    log('yt-dlp URL ready in {:.2f} s'.format(time.monotonic() - requested))
    play_sample(controller, url, content_type, seconds, requested)
    log('YT-DLP PLAY AND SEEK PASSED')
    return 'yt-dlp'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', required=True, help='Exact Cast name, e.g. Audio Pracovna or Music')
    parser.add_argument('--video-id', action='append', help='Repeat to test different tracks')
    parser.add_argument('--seconds', type=int, choices=range(1, 16), default=5)
    parser.add_argument('--yt-dlp-only', action='store_true')
    args = parser.parse_args()
    videos = args.video_id or ['ojvldIzbaMo', 'b-OLFNSSYco']
    if any(not re.fullmatch(r'[A-Za-z0-9_-]{11}', video) for video in videos):
        parser.error('Invalid video ID')

    import os
    import shutil
    deno_directory = Path(os.environ.get('DENO_INSTALL', str(Path.home() / '.deno'))) / 'bin'
    if not shutil.which('deno') and os.access(deno_directory / 'deno', os.X_OK):
        os.environ['PATH'] = str(deno_directory) + os.pathsep + os.environ.get('PATH', '')
    # Library diagnostics can include signed URLs; use only the summaries above.
    cast_logger = logging.getLogger('pychromecast')
    cast_logger.handlers = [logging.NullHandler()]
    cast_logger.propagate = False
    casts = []
    browser = None
    resolver = DirectResolver(log=log)
    controller = None
    owned_urls = set()
    try:
        log('Finding selected Cast: ' + args.device)
        casts, browser = pychromecast.get_listed_chromecasts(
            friendly_names=[args.device], discovery_timeout=10, tries=1, timeout=5,
        )
        matches = [cast for cast in casts if cast.cast_info.friendly_name == args.device
                   and cast.cast_info.cast_type in ('audio', 'group')]
        if len(matches) != 1:
            raise DirectAudioError('Expected exactly one matching audio Cast or group')
        cast = matches[0]
        cast.wait(timeout=10)
        controller = CastController(cast.media_controller)
        for video in videos:
            log('TRACK: ' + video)
            test_track(resolver, controller, video, args.seconds, owned_urls, fallback_only=args.yt_dlp_only)
        log('All samples finished; please confirm sound before and after each seek')
    finally:
        resolver.close()
        if controller is not None and controller.status.content_id in owned_urls:
            try:
                controller.stop()
            except Exception:
                log('Could not stop test playback')
        for cast in casts:
            core._disconnect_cast_safely(cast)
        if browser is not None:
            browser.stop_discovery()
            browser.zc.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log('Interrupted')
        sys.exit(130)
    except Exception as error:
        log('FAILED: {} (raw error omitted)'.format(type(error).__name__))
        sys.exit(1)
