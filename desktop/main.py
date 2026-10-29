#!/usr/bin/env python3

import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from felismusic_gui.backend import BackendBridge
from felismusic_gui.diagnostics import configure_debug


VERSION = "0.3.65-dev"


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

    app.aboutToQuit.connect(bridge.shutdown)
    QTimer.singleShot(0, bridge.initialize)

    # Explicitní reference na engin/backend po celou dobu života aplikace.
    app._felismusic_engine = engine
    app._felismusic_backend = bridge

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
