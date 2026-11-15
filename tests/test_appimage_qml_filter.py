"""Keep the QML interface dependencies without unrelated speech/3D plugins."""
from pathlib import Path
import runpy
import tempfile
from unittest import TestCase

keep = runpy.run_path(str(Path(__file__).resolve().parents[1] /
    'packaging/appimage/qml_filter.py'))['keep_qml_file']
unexpected = runpy.run_path(str(Path(__file__).resolve().parents[1] /
    'packaging/appimage/qml_filter.py'))['unexpected_qt_resource']


class AppImageQmlFilterTests(TestCase):
    def test_interface_modules_and_transitive_controls_resources_are_kept(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ('QtQuick/qmldir', 'QtQuick/libqtquick2plugin.so',
                'QtQml/Models/qmldir', 'QtQml/WorkerScript/qmldir',
                'QtQuick/Controls/Basic/Button.qml', 'QtQuick/Controls/Fusion/impl/qmldir',
                'QtQuick/Templates/qmldir', 'QtQuick/Layouts/qmldir',
                'QtQuick/Window/qmldir', 'QtQuick/Effects/qmldir', 'QtQuick/Shapes/qmldir'):
                with self.subTest(relative=relative):
                    resource = root / relative
                    resource.parent.mkdir(parents=True, exist_ok=True)
                    resource.touch()
                    self.assertTrue(keep(resource, root))

    def test_speech_3d_and_other_unused_modules_are_excluded(self):
        root = Path('/example/qml')
        for relative in ('QtTextToSpeech/qmldir', 'QtQuick3D/Xr/qmldir',
            'Qt3D/Core/qmldir', 'QtQuick/Scene3D/qmldir', 'QtWebEngine/qmldir',
            'QtMultimedia/qmldir'):
            with self.subTest(relative=relative):
                self.assertFalse(keep(root / relative, root))
        self.assertFalse(keep(root, root))
        self.assertFalse(keep(root / 'QtQuick', root))

    def test_resources_outside_selected_qt_are_rejected(self):
        with self.assertRaises(ValueError):
            keep('/system/QtQuick/qmldir', '/bundled/qml')

    def test_auxiliary_library_dependency_is_allowed_without_allowing_qml_module(self):
        for path in ('PySide6/Qt/lib/libQt6Quick3DUtils.so.6', 'libQt6Quick3DUtils.so.6.12.0'):
            self.assertFalse(unexpected(path))
        self.assertTrue(unexpected('PySide6/Qt/qml/QtQuick3D/Utils/qmldir'))

    def test_speech_and_actual_quick3d_libraries_remain_forbidden(self):
        for path in ('libQt6TextToSpeech.so.6', 'PySide6/Qt/lib/libQt6Quick3D.so.6',
                'libQt6Quick3DRuntimeRender.so.6', 'libQt6Quick3DXr.so.6',
                'libQt6Quick3DUtilsUnexpected.so.6', 'PySide6/Qt/qml/QtTextToSpeech/qmldir'):
            with self.subTest(path=path):
                self.assertTrue(unexpected(path))
