"""QML deployment scope for FelisMusic's QtQuick Controls interface."""
from pathlib import Path
import re


def unexpected_qt_resource(destination):
    parts = Path(destination).parts
    name = Path(destination).name
    if "QtTextToSpeech" in parts or "QtQuick3D" in parts:
        return True
    if name.startswith("libQt6TextToSpeech."):
        return True
    # Keep an actual dependency selected by binary analysis. This auxiliary
    # library is not the Quick3D renderer or a Quick3D QML module.
    if re.fullmatch(r"libQt6Quick3DUtils\.so(?:\.\d+)*", name):
        return False
    return name.startswith("libQt6Quick3D")


def keep_qml_file(source, qml_root):
    try:
        parts = Path(source).resolve().relative_to(Path(qml_root).resolve()).parts
    except ValueError:
        raise ValueError("QML resource outside the selected PySide6 QML directory") from None
    if not parts:
        return False  # Never copy the complete QML root directory.
    if parts[0] == "QtQml":
        return True
    if parts[0] != "QtQuick":
        return False
    if len(parts) == 1:
        return False  # A directory entry would copy unrelated submodules.
    if len(parts) == 2 and Path(source).is_file():
        return True  # QtQuick's own qmldir, plugin and type metadata.
    return parts[1] in {"Controls", "Templates", "Layouts", "Window", "Effects", "Shapes", "Timeline"}
