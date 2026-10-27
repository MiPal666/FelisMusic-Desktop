"""Timing and credential-safe diagnostic output, with no network/account."""
from contextlib import redirect_stdout
from functools import partial
import io
import json
import os
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import requests
import test_prefetch as support
from felismusic_gui import diagnostics as diag


def records(output):
    return [json.loads(line.split('] ', 1)[1]) for line in output.getvalue().splitlines()
            if line.startswith('[FelisMusic diag] ')]


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, FELISMUSIC_DIAGNOSTICS='1')
        self.env.start(); self.addCleanup(self.env.stop)

    def test_default_is_off_and_regular_qt_arguments_are_preserved(self):
        os.environ.pop('FELISMUSIC_DIAGNOSTICS')
        self.assertFalse(diag.enabled())
        args = ['felismusic', '-platform', 'offscreen']
        self.assertEqual(diag.configure_debug(args), args)
        self.assertFalse(diag.enabled())
        output = io.StringIO()
        with redirect_stdout(output), diag.DiagnosticExecutor(max_workers=1) as pool:
            self.assertEqual(pool.submit(lambda: 42).result(2), 42)
        self.assertEqual(output.getvalue(), '')

    def test_debug_switch_enables_diagnostics_and_is_consumed_before_qt(self):
        os.environ['FELISMUSIC_DIAGNOSTICS'] = '0'
        args = ['felismusic', '--debug', '-platform', 'offscreen']
        self.assertEqual(diag.configure_debug(args), ['felismusic', '-platform', 'offscreen'])
        self.assertTrue(diag.enabled()); self.assertIn('--debug', args)

    def test_environment_opt_in_remains_supported(self):
        self.assertEqual(diag.configure_debug(['felismusic']), ['felismusic'])
        self.assertTrue(diag.enabled())

    def test_executor_distinguishes_queue_delay_run_time_and_context(self):
        output = io.StringIO(); entered, release = Event(), Event()
        with redirect_stdout(output), diag.DiagnosticExecutor(max_workers=1) as pool:
            def blocked():
                entered.set(); release.wait(3)
            first = pool.submit(blocked, _diagnostic_label='audio.prefetch')
            self.assertTrue(entered.wait(1))
            second = pool.submit(lambda: diag.current_trace().label, _diagnostic_label='audio.play')
            self.assertFalse(release.wait(.03)); release.set()
            first.result(2); self.assertEqual(second.result(2), 'audio.play')
        data = records(output)
        start = next(x for x in data if x['event'] == 'job.start' and x['task'] == 'audio.play')
        self.assertGreaterEqual(start['queue_s'], .025)
        self.assertEqual(len({x['job'] for x in data}), 2)
        self.assertIsNone(diag.current_trace())

    def test_cancelled_queued_job_is_logged_without_running_it(self):
        output = io.StringIO(); entered, release = Event(), Event(); action = Mock()
        with redirect_stdout(output), diag.DiagnosticExecutor(max_workers=1) as pool:
            first = pool.submit(lambda: (entered.set(), release.wait(3)))
            self.assertTrue(entered.wait(1))
            second = pool.submit(action, _diagnostic_label='cancelled')
            self.assertTrue(second.cancel()); release.set(); first.result(2)
        action.assert_not_called()
        self.assertTrue(any(x['event'] == 'job.cancelled_before_start' for x in records(output)))

    def test_disabled_mode_retains_executor_behavior_and_silence(self):
        output = io.StringIO()
        with patch.dict('os.environ', FELISMUSIC_DIAGNOSTICS='0'), redirect_stdout(output), \
             diag.DiagnosticExecutor(max_workers=1) as pool:
            self.assertEqual(pool.submit(lambda x: x + 1, 4, _diagnostic_label='test').result(2), 5)
        self.assertEqual(output.getvalue(), '')

    def test_http_wrapper_preserves_original_timeout_and_arguments_but_logs_no_secrets(self):
        session = requests.Session(); response = requests.Response(); response.status_code = 200
        send = Mock(return_value=response)
        session.request = partial(send, timeout=30)
        api = SimpleNamespace(_session=session)
        self.assertIs(diag.instrument_ytmusic(api), api)
        wrapped = session.request; diag.instrument_ytmusic(api); self.assertIs(session.request, wrapped)
        url = 'https://USERSECRET:PASSSECRET@music.youtube.com/youtubei/v1/browse?key=KEYSECRET'
        kwargs = dict(headers={'Cookie': 'COOKIESECRET', 'Authorization': 'AUTHSECRET'},
                      json={'query': 'QUERYSECRET'}, proxies={'https': 'PROXYSECRET'})
        output = io.StringIO()
        with redirect_stdout(output), diag.DiagnosticExecutor(max_workers=1) as pool:
            self.assertIs(pool.submit(lambda: session.post(url, **kwargs)).result(2), response)
        self.assertEqual(send.call_args.args, ('POST', url))
        self.assertEqual(send.call_args.kwargs['timeout'], 30)
        self.assertEqual(send.call_args.kwargs['headers'], kwargs['headers'])
        self.assertEqual(send.call_args.kwargs['json'], kwargs['json'])
        self.assertNotIn('SECRET', output.getvalue())
        event = next(x for x in records(output) if x['event'] == 'http.end')
        self.assertEqual((event['host'], event['endpoint'], event['timeout_s'], event['http_status']),
                         ('music.youtube.com', 'browse', 30, 200))

    def test_http_error_does_not_print_exception_content_or_url(self):
        session = requests.Session()
        session.request = Mock(side_effect=requests.exceptions.ReadTimeout('TOKEN_SECRET cookie=SECRET'))
        diag.instrument_ytmusic(SimpleNamespace(_session=session)); output = io.StringIO()
        with redirect_stdout(output), diag.DiagnosticExecutor(max_workers=1) as pool:
            with self.assertRaises(requests.exceptions.ReadTimeout):
                pool.submit(lambda: session.get('https://music.youtube.com/PRIVATE_SECRET?key=SECRET')).result(2)
        self.assertNotIn('SECRET', output.getvalue())
        error = next(x for x in records(output) if x['event'] == 'http.error')
        self.assertEqual(error['error'], 'ReadTimeout'); self.assertEqual(error['endpoint'], 'other')

    def test_downloader_phases_site_wait_host_and_warnings_are_safe(self):
        output = io.StringIO()
        with redirect_stdout(output):
            trace = diag.Trace('audio.play'); trace.audio_begin('video')
            logger = diag.DownloadLogger(trace)
            logger.debug('[debug] headers Cookie: SECRET')
            logger.debug('[youtube] Downloading webpage https://music.youtube.com/?key=SECRET')
            logger.debug('[youtube] Downloading player API JSON COOKIE_SECRET')
            logger.debug('[jsc:deno] Solving JS challenges')
            logger.debug('[info] video: Downloading 1 format(s): 140')
            logger.debug('[download] Sleeping 4.00 seconds as required by the site...')
            trace.progress(dict(status='downloading', downloaded_bytes=100, speed=50,
                                info_dict={'url': 'https://rr5.googlevideo.com/videoplayback?sig=SECRET',
                                           'title': 'TITLE_SECRET'}))
            logger.warning("HTTPSConnectionPool(host='rr5.googlevideo.com', port=443): Read timed out. (read timeout=20.0) SECRET")
            logger.error('HTTP Error 503: Service Unavailable https://rr5.googlevideo.com/?sig=SECRET')
            logger.warning('unrecognized credential SECRET')
            trace.progress(dict(status='finished', downloaded_bytes=200))
            trace.postprocess(dict(status='started', info_dict={'filepath': 'SECRET'}))
            trace.postprocess(dict(status='finished'))
        self.assertNotIn('SECRET', output.getvalue())
        data = records(output); events = [x['event'] for x in data]
        for event in ('audio.metadata_webpage', 'audio.metadata_player', 'audio.js_challenge',
                      'audio.metadata_ready', 'audio.first_data', 'audio.download_finished',
                      'audio.postprocess_started', 'audio.postprocess_finished'):
            self.assertIn(event, events)
        wait = next(x for x in data if x['event'] == 'audio.site_wait'); self.assertEqual(wait['seconds'], 4)
        timeout = next(x for x in data if x['event'] == 'yt.warning' and x['reason'] == 'timeout')
        self.assertEqual(timeout['timeout_s'], 20); self.assertEqual(timeout['host'], 'rr5.googlevideo.com')
        error = next(x for x in data if x['event'] == 'yt.error'); self.assertEqual(error['http_status'], 503)

    def test_broken_log_pipe_does_not_break_trace(self):
        with patch('builtins.print', side_effect=BrokenPipeError):
            diag.Trace('test').event('test')

    def test_downloader_cdn_host_and_error_are_logged_before_first_byte_without_signed_url(self):
        response = SimpleNamespace(status=200)
        original = Mock(return_value=response); downloader = SimpleNamespace(urlopen=original)
        request = SimpleNamespace(url='https://rr5.googlevideo.com/videoplayback?sig=SECRET',
                                  headers={'Cookie': 'SECRET'})
        output = io.StringIO()
        with redirect_stdout(output):
            trace = diag.Trace('audio.prefetch'); trace.instrument_downloader(downloader)
            self.assertIs(downloader.urlopen(request), response)
            error = RuntimeError('PRIVATE_SECRET')
            error.response = SimpleNamespace(status=503)
            original.side_effect = error
            with self.assertRaises(RuntimeError):
                downloader.urlopen(request)
        self.assertEqual(original.call_args.args, (request,))
        self.assertNotIn('SECRET', output.getvalue())
        self.assertEqual(trace.download_host, 'rr5.googlevideo.com')
        event = next(x for x in records(output) if x['event'] == 'audio.cdn_http_error')
        self.assertEqual(event['http_status'], 503)


class PlaybackDiagnosticTests(support.AudioPlaybackTestCase):
    def setUp(self):
        env = patch.dict(os.environ, FELISMUSIC_DIAGNOSTICS='1')
        env.start(); self.addCleanup(env.stop)
        super().setUp()

    def test_actual_playback_cache_and_prefetch_events_without_changing_download_options(self):
        output = io.StringIO(); fake = support.core.yt_dlp.YoutubeDL
        with redirect_stdout(output), patch.object(support.core.yt_dlp, 'YoutubeDL', wraps=fake) as factory:
            self.start('A', 'B'); self.until(lambda: 'B' in support.core.LOCAL_AUDIO_CACHE)
            self.b.stopPlayback(); self.b.togglePlayPause()
            self.until(lambda: self.b.playerState == 'playing')
            self.b._playback_executor.submit(lambda: None).result(2)
        self.assertEqual(self.played, ['A', 'A'])
        self.assertEqual(self.downloads['A'], 1)
        for call in factory.call_args_list:
            options = call.args[0]
            self.assertNotIn('socket_timeout', options); self.assertNotIn('retries', options)
            self.assertEqual(options['format'], '140/bestaudio[ext=m4a]/bestaudio')
            self.assertIsInstance(options['logger'], diag.DownloadLogger)
            self.assertFalse(options['no_warnings'])
        data = records(output)
        self.assertTrue(any(x['task'] == 'audio.prefetch' for x in data))
        for event in ('audio.cache_hit', 'audio.ready', 'audio.output_begin', 'audio.output_ready'):
            self.assertTrue(any(x['event'] == event for x in data), event)
