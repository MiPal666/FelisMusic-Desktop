"""Load optional Qt message catalogs once, before constructing the UI."""
from pathlib import Path

from PySide6.QtCore import QLocale, QTranslator


TRANSLATIONS_DIR = Path(__file__).resolve().parents[1] / "translations"


def install_translation(app, *, locale=None, directory=TRANSLATIONS_DIR):
    """Use Linux/Qt UI language preferences, with English as the default catalog.

    QTranslator handles language/territory fallbacks (e.g. en_GB -> en).
    If no preferred catalog loads, try English. Without a usable catalog,
    Qt displays the Czech source text.
    The caller retains the returned translator for the application lifetime.
    Language is chosen at startup; this does not change API request languages,
    account settings, playback state, or QLocale's number/date formatting.
    """
    translator = QTranslator(app)
    selected_locale = QLocale.system() if locale is None else locale
    catalog_directory = str(directory)
    if (translator.load(selected_locale, "felismusic", "_", catalog_directory)
            or translator.load("felismusic_en.qm", catalog_directory)):
        app.installTranslator(translator)
        return translator
    return None
