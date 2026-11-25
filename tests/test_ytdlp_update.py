"""Updater guards and real asynchronous process lifecycle, without pip/network."""
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from PySide6.QtCore import QCoreApplication, QProcess
from felismusic_gui.ytdlp_update import YtdlpUpdater


class YtdlpUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.prefix = patch.object(sys, 'prefix', '/test/venv')
        self.prefix.start()
        self.addCleanup(self.prefix.stop)
        self.updater = YtdlpUpdater()
        self.addCleanup(self.updater.shutdown)

    def wait_phase(self, phase):
        deadline = time.monotonic() + 5
        while self.updater.phase != phase and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.01)
        self.assertEqual(self.updater.phase, phase)

    def test_frozen_and_system_python_cannot_update(self):
        for frozen, prefix in ((True, '/test/venv'), (False, sys.base_prefix)):
            with patch.object(sys, 'frozen', frozen, create=True), patch.object(sys, 'prefix', prefix), patch.object(QProcess, 'start') as process:
                self.assertFalse(self.updater.available)
                self.updater.update()
                process.assert_not_called()

    def test_command_targets_current_venv_and_only_ytdlp(self):
        with patch.object(QProcess, 'start') as start:
            self.updater.update()
            executable, args = start.call_args.args
            self.assertEqual(executable, sys.executable)
            self.assertEqual(args, ['-m', 'pip', '--isolated', '--require-virtualenv', '--disable-pip-version-check', '--no-input', 'install', '--upgrade', '--index-url', 'https://pypi.org/simple', 'yt-dlp[default]'])
            self.updater.update()
            self.assertEqual(start.call_count, 1)

    def run_child(self, script):
        original = QProcess.start
        def start(process, executable, args):
            original(process, sys.executable, ['-c', script])
        with patch.object(QProcess, 'start', start):
            self.updater.update()

    def test_success_requires_restart_and_blocks_second_update(self):
        self.run_child('print("done")')
        self.wait_phase('restart')
        with patch.object(QProcess, 'start') as process:
            self.updater.update()
            process.assert_not_called()
        self.assertFalse(self.updater._timer.isActive())

    def test_failure_is_retryable(self):
        self.run_child('raise SystemExit(1)')
        self.wait_phase('failed')
        self.run_child('pass')
        self.wait_phase('restart')

    def test_failed_start_is_reported(self):
        original = QProcess.start
        with patch.object(QProcess, 'start', lambda process, *_: original(process, '/nonexistent/felismusic-python', [])):
            self.updater.update()
        self.wait_phase('failed')

    def test_timeout_kills_process_and_reports_failure(self):
        self.run_child('import time; time.sleep(30)')
        self.updater._timeout()
        self.wait_phase('failed')

    def test_shutdown_kills_child_and_ignores_late_completion(self):
        self.run_child('import time; time.sleep(30)')
        process = self.updater._process
        self.updater.shutdown()
        self.assertEqual(process.state(), QProcess.ProcessState.NotRunning)
        self.app.processEvents()
        self.assertEqual(self.updater.phase, 'closed')
        with patch.object(QProcess, 'start') as factory:
            self.updater.update()
            factory.assert_not_called()
