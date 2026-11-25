"""Explicit updates of the running virtualenv; frozen bundles stay immutable."""
import sys

from PySide6.QtCore import QObject, Property, QProcess, QTimer, Signal, Slot
from yt_dlp.version import __version__


class YtdlpUpdater(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(self._drain_output)
        self._process.readyReadStandardError.connect(self._drain_output)
        self._process.finished.connect(self._finished)
        self._process.errorOccurred.connect(self._error)
        self._phase = "idle"
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._timeout)

    @Property(str, constant=True)
    def version(self):
        # This is the version actually imported by this process, until restart.
        return __version__

    @Property(bool, constant=True)
    def available(self):
        return not getattr(sys, "frozen", False) and sys.prefix != sys.base_prefix

    @Property(str, notify=changed)
    def phase(self):
        return self._phase

    def _set_phase(self, phase):
        self._phase = phase
        self.changed.emit()

    @Slot()
    def update(self):
        if not self.available or self._phase in ("updating", "restart", "closed"):
            return
        process = self._process
        self._set_phase("updating")
        process.start(sys.executable, ["-m", "pip", "--isolated", "--require-virtualenv",
            "--disable-pip-version-check", "--no-input", "install", "--upgrade",
            "--index-url", "https://pypi.org/simple", "yt-dlp[default]"])
        self._timer.start(180000)

    def _drain_output(self):
        self._process.readAllStandardOutput()
        self._process.readAllStandardError()

    def _finished(self, code, status):
        if self._phase != "updating":
            return
        self._timer.stop()
        self._set_phase("restart" if code == 0 and status == QProcess.ExitStatus.NormalExit else "failed")

    def _error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self._finished(-1, QProcess.ExitStatus.CrashExit)

    def _timeout(self):
        if self._phase == "updating":
            self._process.kill()

    def shutdown(self):
        self._timer.stop()
        process = self._process
        self._set_phase("closed")
        if process.state() != QProcess.ProcessState.NotRunning:
            process.kill()
            process.waitForFinished(1000)
