# Překlady FelisMusic Desktop

Čeština je zdrojový jazyk. Po kroku L4 (0.3.99-dev) katalog zahrnuje
476 textů včetně přihlášení, chyb, výsledků operací s playlisty a hlášek
při načítání. Texty s proměnnými hodnotami používají šablony.
Počty skladeb a položek používají Qt numerus nebo formulaci „Počet …“.
Bez katalogu zůstávají k dispozici české tvary pro 1, 2–4 a ostatní počty.
Anglický katalog se zatím nedistribuuje.

## Volba jazyka

`desktop/main.py` zavolá `install_translation()` před vznikem backendu a QML.
Qt použije `QLocale.system()` a jeho pořadí jazyků rozhraní podle prostředí
Linuxu (`LANG`, `LC_MESSAGES`, případně `LANGUAGE` a jejich systémové priority).
Nezavádíme vlastní přepínač jazyka ani neměníme locale čísel nebo datumů.
Změna prostředí vyžaduje nový start aplikace.

Načítají se pouze lokální katalogy `felismusic_<jazyk>.qm` v tomto adresáři.
Qt zohlední regionální varianty a základní jazyk (např. en_GB → en).
Chybějící/neplatný katalog nebo nepřeložená položka ponechá český zdrojový text.
Překlad neřídí jazyk API YouTube Music, názvy skladeb/playlistů od serveru,
přihlášení ani stav audia. Standardní texty Qt dialogů tento krok nemění.

## Aktualizace katalogů

Z kořene projektu:

```bash
env/bin/python tools/update_translations.py
```

Skript používá dostupné `pyside6-lupdate`, `lupdate6` nebo `lupdate`.
Jde o vývojový nástroj Qt Linguist; běh aplikace jej nepotřebuje.
Český `.ts` obsahuje zdrojové texty a vyplněné tvary Qt numerus.
Český `.qm` aplikace ke spuštění nepotřebuje.

Volitelné sestavení dokončených překladů (nedokončené se nezahrnují):

```bash
env/bin/python tools/update_translations.py --release
```

Pro ověření bez souborů v aplikačním adresáři použij `--output-dir /tmp/felismusic-translations`.
Skript hledá také `pyside6-lrelease`, `lrelease6` nebo `lrelease`.
Anglický katalog pro testy vzniká jen dočasně v testovacím adresáři.

## Pravidla pro další kroky

- QML označuje zobrazované texty přes `qsTr()`, Python přes
  `QCoreApplication.translate()` se stálým kontextem.
- Nepřekládat ID, role modelů, klíče API, názvy signálů, stavy jako `playing`,
  `album`, `LIKE`, cesty ani data dodaná uživatelem/serverem.
- Další skládané věty převádět na celé překládané šablony s parametry;
  neobalovat až výsledný dynamický text a neupravovat uživatelské hodnoty.
  Python používá například `translate(..., "Přehrávám · {title}").format(title=title)`;
  názvy parametrů musí zůstat v překladu zachované. QML používá `%1` a `.arg()`.
  Názvy zadané uživatelem mohou samy obsahovat `{count}` nebo `%1`; berou se jako data.
- Pro počty používat Qt numerus a zachovat české tvary i bez katalogu.
- Před převodem zkontrolovat vazby na obsah textu. Barva obecné chyby načítání
  už používá příznak `statusIsError` místo hledání českého slova `Chyba`.
  `_set_status()` příznak předává explicitně; nový běžný stav jej vynuluje.
- Angličtinu nabídnout až po převedení a kontrole zbývajících textů, aby
  uživatel nedostal pouze částečně přeložené rozhraní.
