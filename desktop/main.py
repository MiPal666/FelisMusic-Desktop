#!/usr/bin/env python3

import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from felismusic_gui.backend import BackendBridge
from felismusic_gui.diagnostics import configure_debug


VERSION = "0.3.91-dev"


def main():
    app = QGuiApplication(configure_debug(sys.argv))
    app.setApplicationName("FelisMusic")
    app.setOrganizationName("FelisCatus")

    engine = QQmlApplicationEngine()
    # Backend je potomkem QML enginu, takže při ukončení zůstane živý,
    # dokud QML nedokončí destrukci bindingů. Tím nevznikají hlášky
    # "Cannot read property ... of null" při zavření aplikace.
    bridge = BackendBridge(engine)
    engine.rootContext().setContextProperty("fcmVersion", VERSION)
    engine.rootContext().setContextProperty("backend", bridge)

    qml_file = Path(__file__).with_name("Main.qml")
    engine.load(QUrl.fromLocalFile(str(qml_file)))

    if not engine.rootObjects():
        return 1

    # MPRIS is optional: missing desktop D-Bus must not prevent playback.
    try:
        from felismusic_gui.mpris import start_mpris
        app._felismusic_mpris = start_mpris(bridge, app, engine.rootObjects()[0])
    except ImportError:
        import logging
        logging.getLogger(__name__).warning("MPRIS requires dbus-python and PyGObject")
        app._felismusic_mpris = None
    if app._felismusic_mpris is not None:
        app.aboutToQuit.connect(app._felismusic_mpris.close)
    app.aboutToQuit.connect(bridge.shutdown)
    QTimer.singleShot(0, bridge.initialize)

    # Explicitní reference na engin/backend po celou dobu života aplikace.
    app._felismusic_engine = engine
    app._felismusic_backend = bridge

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
