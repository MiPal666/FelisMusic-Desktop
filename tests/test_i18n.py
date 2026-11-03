"""Qt catalogs follow the desktop locale while missing text stays Czech."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from PySide6.QtCore import QCoreApplication, QLocale, QTranslator
from felismusic_gui.i18n import TRANSLATIONS_DIR, install_translation


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

    def test_no_matching_catalog_uses_english(self):
        self.assertIsNotNone(self.install('fr_FR'))
        self.assertEqual(QCoreApplication.translate('Main', 'Hledat'), 'Search')

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
                                               ('C', 'C', 'Search'),
                                               ('cs_CZ.UTF-8', 'en:cs', 'Search'),
                                               ('fr_FR.UTF-8', 'fr', 'Search')):
            with self.subTest(language=language, preference=preference):
                environment = dict(os.environ, LANG=language, LANGUAGE=preference,
                                   PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'desktop'))
                environment.pop('LC_ALL', None); environment.pop('LC_MESSAGES', None)
                result = subprocess.run([sys.executable, '-c', code, str(self.catalogs)],
                                        env=environment, capture_output=True, text=True, check=True)
                languages, text = json.loads(result.stdout)
                self.assertEqual(text, expected, languages)


class ShippedEnglishCatalogTests(unittest.TestCase):
    def test_shipped_czech_is_preferred_to_english_default(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        translator = install_translation(app, locale=QLocale('cs_CZ'))
        self.assertIsNotNone(translator)
        self.addCleanup(app.removeTranslator, translator)
        self.assertEqual(QCoreApplication.translate('Main', 'Hledat'), 'Hledat')
        self.assertEqual(QCoreApplication.translate('Main', '%n skladba', None, 2), '2 skladby')
    def test_compiled_catalog_covers_the_czech_source_inventory(self):
        catalogs = {
            language: ET.parse(TRANSLATIONS_DIR / f'felismusic_{language}.ts').getroot()
            for language in ('cs', 'en')
        }
        def messages(catalog):
            return {
                (context.findtext('name'), message.findtext('source')): message
                for context in catalog.findall('context')
                for message in context.findall('message')
                if message.find('translation').get('type') not in ('vanished', 'obsolete')
            }

        english = messages(catalogs['en'])
        self.assertEqual(english.keys(), messages(catalogs['cs']).keys())
        translator = QTranslator()
        self.assertTrue(translator.load(str(TRANSLATIONS_DIR / 'felismusic_en.qm')))
        for (context, source), message in english.items():
            with self.subTest(context=context, source=source):
                entry = message.find('translation')
                self.assertIsNone(entry.get('type'))
                if message.get('numerus') == 'yes':
                    forms = [form.text for form in entry.findall('numerusform')]
                    self.assertEqual(len(forms), 2)
                    for count, form in enumerate(forms, start=1):
                        self.assertTrue(form)
                        self.assertEqual(translator.translate(context, source, None, count), form)
                else:
                    self.assertTrue(entry.text)
                    self.assertEqual(translator.translate(context, source), entry.text)
