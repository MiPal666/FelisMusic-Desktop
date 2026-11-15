"""Limit PyInstaller 6.22.3's otherwise exhaustive QML plugin collection."""
from pathlib import Path
import runpy
from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
qml_binaries, qml_datas = pyside6_library_info.collect_qtqml_files()
keep = runpy.run_path(str(Path(__file__).resolve().parents[1] / "qml_filter.py"))["keep_qml_file"]
qml_root = pyside6_library_info.location.get("QmlImportsPath") or pyside6_library_info.location["Qml2ImportsPath"]
binaries += [item for item in qml_binaries if keep(item[0], qml_root)]
datas += [item for item in qml_datas if keep(item[0], qml_root)]
