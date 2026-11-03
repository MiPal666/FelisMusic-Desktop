"""Qt catalogs follow the desktop locale while missing text stays Czech."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from PySide6.QtCore import QCoreApplication, QLocale
from felismusic_gui.i18n import install_translation


class TranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])
        cls.directory = tempfile.TemporaryDirectory()
        cls.catalogs = Path(cls.directory.name)
        compiler = next((shutil.which(name) for name in ('pyside6-lrelease', 'lrelease6', 'lrelease')
                         if shutil.which(name)), None)
        if compiler is None:
            cls.directory.cleanup()
            raise unittest.SkipTest('Qt Linguist lrelease is needed for catalog integration tests')
        source = cls.catalogs / 'felismusic_en.ts'
        source.write_text('''<?xml version="1.0" encoding="utf-8"?>
<TS version="2.1" language="en" sourcelanguage="cs_CZ">
<context><name>Main</name>
<message><source>Hledat</source><translation>Search</translation></message>
</context>
<context><name>BackendBridge</name>
<message><source>Toto zařízení</source><translation>This device</translation></message>
</context></TS>''')
        subprocess.run([compiler, str(source), '-qm', str(source.with_suffix('.qm'))],
                       check=True, stdout=subprocess.DEVNULL)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def install(self, locale, directory=None):
        translator = install_translation(self.app, locale=QLocale(locale),
                                         directory=directory or self.catalogs)
        if translator is not None:
            self.addCleanup(self.app.removeTranslator, translator)
        return translator

    def test_regional_catalog_fallback_translates_qml_and_python_contexts(self):
        self.assertIsNotNone(self.install('en_GB'))
        self.assertEqual(QCoreApplication.translate('Main', 'Hledat'), 'Search')
        self.assertEqual(QCoreApplication.translate('BackendBridge', 'Toto zařízení'), 'This device')
        self.assertEqual(QCoreApplication.translate('Main', 'Nepřeložená hláška'), 'Nepřeložená hláška')
        self.assertEqual(QCoreApplication.translate('Main', 'playing'), 'playing')

    def test_czech_unknown_and_c_locales_preserve_source_text(self):
        for locale in ('cs_CZ', 'fr_FR', 'C'):
            with self.subTest(locale=locale):
                self.assertIsNone(self.install(locale))
                self.assertEqual(QCoreApplication.translate('Main', 'Hledat'), 'Hledat')

    def test_missing_or_invalid_catalog_does_not_prevent_startup(self):
        self.assertIsNone(self.install('en_GB', self.catalogs / 'does-not-exist'))
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'felismusic_en.qm').write_bytes(b'invalid catalog')
            self.assertIsNone(self.install('en_GB', Path(directory)))
        self.assertEqual(QCoreApplication.translate('BackendBridge', 'Toto zařízení'), 'Toto zařízení')

    def test_loading_translation_does_not_change_number_formatting_locale(self):
        before = QLocale().name()
        self.install('en_GB')
        self.assertEqual(QLocale().name(), before)

    def test_linux_language_preferences_are_used_without_explicit_locale(self):
        code = '''import json, sys
from PySide6.QtCore import QCoreApplication, QLocale
from felismusic_gui.i18n import install_translation
app = QCoreApplication([])
translator = install_translation(app, directory=sys.argv[1])
print(json.dumps([QLocale.system().uiLanguages(), QCoreApplication.translate("Main", "Hledat")]))
'''
        for language, preference, expected in (('en_GB.UTF-8', 'en_GB:en', 'Search'),
                                               ('cs_CZ.UTF-8', 'cs', 'Hledat'),
                                               ('cs_CZ.UTF-8', 'en:cs', 'Search'),
                                               ('fr_FR.UTF-8', 'fr', 'Hledat')):
            with self.subTest(language=language, preference=preference):
                environment = dict(os.environ, LANG=language, LANGUAGE=preference,
                                   PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'desktop'))
                environment.pop('LC_ALL', None); environment.pop('LC_MESSAGES', None)
                result = subprocess.run([sys.executable, '-c', code, str(self.catalogs)],
                                        env=environment, capture_output=True, text=True, check=True)
                languages, text = json.loads(result.stdout)
                self.assertEqual(text, expected, languages)
