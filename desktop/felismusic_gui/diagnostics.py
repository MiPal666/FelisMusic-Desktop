"""Bounded diagnostic events: no bodies, credentials or signed URLs."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from itertools import count
import json
import os
import re
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit

_active = ContextVar('felismusic_trace', default=None)
_ids = count(1)
_started = monotonic()
_print_lock = Lock()


def enabled():
    return os.environ.get('FELISMUSIC_DIAGNOSTICS', '0') == '1'


def configure_debug(argv):
    """Consume our switch before Qt parses its own command-line options."""
    if '--debug' in argv:
        os.environ['FELISMUSIC_DIAGNOSTICS'] = '1'
    return [argument for argument in argv if argument != '--debug']


def current_trace():
    return _active.get()


def _host(url):
    try:
        host = urlsplit(str(url)).hostname or ''
        return host if re.fullmatch(r'[a-zA-Z0-9.:-]{1,253}', host) else ''
    except ValueError:
        return ''


class Trace:
    def __init__(self, label, video=''):
        self.id = next(_ids)
        self.label = re.sub(r'[^a-zA-Z0-9_.:-]', '_', label)[:100]
        self.video = video if re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', str(video)) else ''
        self.queued = monotonic()
        self.audio_started = self.queued
        self.download_started = None
        self.last_progress = 0
        self.download_host = ''

    def event(self, event, **fields):
        record = dict(t=round(monotonic() - _started, 3), job=self.id, task=self.label,
                      event=event, **fields)
        if self.video:
            record['video'] = self.video
        with _print_lock:
            try:
                print('[FelisMusic diag] ' + json.dumps(record, ensure_ascii=False), flush=True)
            except OSError:
                pass  # Closing a log pipe must not break playback.

    def audio_begin(self, video):
        self.video = video if re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', str(video)) else ''
        self.audio_started = monotonic()
        self.download_started = None
        self.download_host = ''
        self.event('audio.prepare_begin')

    def progress(self, data):
        now = monotonic()
        info = data.get('info_dict') or {}
        host = _host(info.get('url', ''))
        if host:
            self.download_host = host
        status = data.get('status')
        if status not in ('downloading', 'finished'):
            return
        first = self.download_started is None
        if first:
            self.download_started = now
        if first or status == 'finished' or now - self.last_progress >= 5:
            self.last_progress = now
            fields = dict(host=self.download_host, prepare_s=round(now - self.audio_started, 3),
                          transfer_s=round(now - self.download_started, 3))
            for key in ('downloaded_bytes', 'total_bytes', 'speed'):
                value = data.get(key)
                if isinstance(value, (int, float)):
                    fields[key] = round(value, 2)
            self.event('audio.download_finished' if status == 'finished' else
                       ('audio.first_data' if first else 'audio.download_progress'), **fields)

    def postprocess(self, data):
        if data.get('status') in ('started', 'finished'):
            self.event('audio.postprocess_' + data['status'])

    def audio_options(self):
        return dict(logger=DownloadLogger(self), no_warnings=False,
                    progress_hooks=[self.progress], postprocessor_hooks=[self.postprocess])

    def instrument_downloader(self, downloader):
        original = getattr(downloader, 'urlopen', None)
        if not callable(original):
            return

        def urlopen(request):
            url = request if isinstance(request, str) else getattr(request, 'url', getattr(request, 'full_url', ''))
            host = _host(url)
            cdn = host == 'googlevideo.com' or host.endswith('.googlevideo.com')
            if cdn:
                self.download_host = host
            prefix = 'audio.cdn_http' if cdn else 'audio.http'
            start = monotonic()
            self.event(prefix + '_begin', host=host)
            try:
                response = original(request)
                status = getattr(response, 'status', None)
                fields = {'http_status': status} if isinstance(status, int) else {}
                self.event(prefix + '_headers', host=host, seconds=round(monotonic() - start, 3), **fields)
                return response
            except Exception as exc:
                status = getattr(getattr(exc, 'response', None), 'status', None)
                fields = {'http_status': status} if isinstance(status, int) else {}
                self.event(prefix + '_error', host=host, seconds=round(monotonic() - start, 3),
                           error=type(exc).__name__, **fields)
                raise

        downloader.urlopen = urlopen


class DiagnosticExecutor(ThreadPoolExecutor):
    def submit(self, fn, /, *args, _diagnostic_label=None, _diagnostic_video='', **kwargs):
        if not enabled():
            return super().submit(fn, *args, **kwargs)
        label = _diagnostic_label or getattr(fn, '__qualname__', type(fn).__name__).split('.<locals>')[0].split('.')[-1]
        trace = Trace(label, _diagnostic_video)
        trace.event('job.queued')

        def run():
            token = _active.set(trace)
            start = monotonic()
            trace.event('job.start', queue_s=round(start - trace.queued, 3))
            try:
                return fn(*args, **kwargs)
            except BaseException as exc:
                trace.event('job.error', error=type(exc).__name__)
                raise
            finally:
                trace.event('job.end', run_s=round(monotonic() - start, 3))
                _active.reset(token)

        future = super().submit(run)
        future.add_done_callback(lambda f: trace.event('job.cancelled_before_start') if f.cancelled() else None)
        return future


class DownloadLogger:
    def __init__(self, trace):
        self.trace = trace

    def debug(self, message):
        # Forward only known event categories, never arbitrary downloader text.
        if message.startswith('[debug]'):
            return
        event = None
        if 'Downloading webpage' in message:
            event = 'audio.metadata_webpage'
        elif 'player API JSON' in message:
            event = 'audio.metadata_player'
        elif 'Solving JS challenges' in message:
            event = 'audio.js_challenge'
        elif 'Downloading m3u8' in message:
            event = 'audio.metadata_manifest'
        elif re.search(r'Downloading \d+ format\(s\)', message):
            event = 'audio.metadata_ready'
        if event:
            self.trace.event(event, prepare_s=round(monotonic() - self.trace.audio_started, 3))
        delay = re.search(r'Sleeping ([\d.]+) seconds', message)
        if delay:
            self.trace.event('audio.site_wait', seconds=float(delay[1]))
        if 'Got error:' in message:
            self.warning(message)

    def _report(self, message, level):
        reason = 'other'
        for text, category in (('timed out', 'timeout'), ('HTTP Error', 'http'),
                               ('challenge', 'js_challenge'), ('PO Token', 'po_token'),
                               ('cookie', 'cookies'), ('format', 'format'), ('retry', 'retry')):
            if text.lower() in message.lower():
                reason = category
                break
        fields = dict(reason=reason, host=self.trace.download_host)
        status = re.search(r'HTTP(?: Error)?[ :]+(\d{3})', message)
        if status:
            fields['http_status'] = int(status[1])
        host = re.search(r"host=['\"]([a-zA-Z0-9.-]+)['\"]", message)
        if host:
            fields['host'] = host[1]
        timeout = re.search(r'(?:read )?timeout[=: ]+([\d.]+)', message)
        if timeout:
            fields['timeout_s'] = float(timeout[1])
        self.trace.event('yt.' + level, **fields)

    def warning(self, message):
        self._report(message, 'warning')

    def error(self, message):
        self._report(message, 'error')


def instrument_ytmusic(api):
    """Wrap the existing session, retaining its original timeout and retries."""
    import requests
    session = getattr(api, '_session', None)
    if not isinstance(session, requests.Session) or getattr(session, '_felis_diagnostic', False):
        return api
    original = session.request
    defaults = getattr(original, 'keywords', {}) or {}

    def request(method, url, **kwargs):
        trace = current_trace()
        if trace is None:
            return original(method, url, **kwargs)
        start = monotonic()
        endpoint = urlsplit(url).path.rsplit('/', 1)[-1]
        endpoint = endpoint if endpoint in ('browse', 'next', 'search', 'player', 'feedback',
                    'account_menu', 'get_account_info', 'edit_playlist', 'rate', 'subscribe', 'unsubscribe') else 'other'
        timeout = kwargs.get('timeout', defaults.get('timeout'))
        fields = dict(host=_host(url), endpoint=endpoint,
                      method=method.upper() if method.upper() in ('GET', 'POST') else 'OTHER')
        if isinstance(timeout, (int, float)):
            fields['timeout_s'] = timeout
        trace.event('http.begin', **fields)
        try:
            response = original(method, url, **kwargs)
            trace.event('http.end', **fields, seconds=round(monotonic() - start, 3),
                        http_status=response.status_code)
            return response
        except Exception as exc:
            trace.event('http.error', **fields, seconds=round(monotonic() - start, 3), error=type(exc).__name__)
            raise

    session.request = request
    session._felis_diagnostic = True
    return api
