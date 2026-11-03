# Překlady FelisMusic Desktop

Příprava překladů ponechává češtinu jako zdrojový jazyk. Po kroku L3
(0.3.98-dev) je označeno 287 různých textů: navigace, dialogy, pevné nabídky
skladeb/kolekcí, základní ovladače a přímé stavové hlášky backendu.
Proměnné stavové věty používají celé šablony s pojmenovanými parametry.
V QML jsou celé šablony také pro připojení, počet vybraných a název výstupu.

Zatím zbývají zejména hlášky připravované v API úlohách (dialogové stavy,
přihlášení, texty chyb), skládané bannery načítání a množné číslo.
Nedistribuuje se anglický katalog a žádný kompletní druhý jazyk není hotový.

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
Český `.ts` je zatím zdrojový inventář s nedokončenými překlady. Čeština je
přímo ve zdrojových textech, takže pro její použití není nutný český `.qm`.

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
- Počty a množné číslo řešit samostatně podle Qt numerus, s testy češtiny.
- Před převodem zkontrolovat vazby na obsah textu. Barva obecné chyby načítání
  už používá příznak `statusIsError` místo hledání českého slova `Chyba`.
  `_set_status()` příznak předává explicitně; nový běžný stav jej vynuluje.
- Angličtinu nabídnout až po převedení a kontrole zbývajících textů, aby
  uživatel nedostal pouze částečně přeložené rozhraní.
