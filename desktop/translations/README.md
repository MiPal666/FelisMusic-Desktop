# Překlady FelisMusic Desktop

První přípravný krok (0.3.95-dev) ponechává češtinu jako zdrojový jazyk.
Označeno je prvních 46 různých textů: hlavní navigace, vybrané nabídky a
přehrávací ovladače, výchozí stav backendu a název místního výstupu.
Zbytek dialogů, hlášek a skládaných textů čeká na další kroky. Zatím se
nedistribuuje anglický katalog a žádný kompletní druhý jazyk není hotový.

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
- Počty a množné číslo řešit samostatně podle Qt numerus, s testy češtiny.
- Před převodem zkontrolovat vazby na obsah textu. Například barva stavové
  hlášky zatím používá české slovo `Chyba`; takové vazby nelze jen přeložit.
- Angličtinu nabídnout až po převedení a kontrole zbývajících textů, aby
  uživatel nedostal pouze částečně přeložené rozhraní.
