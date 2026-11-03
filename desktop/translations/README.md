# Překlady FelisMusic Desktop

Čeština je zdrojový jazyk. FelisMusic od 0.3.100-dev dodává anglický
katalog pro 490 aplikačních textů. Český katalog obsahuje tvary počtů
a umožňuje vybrat češtinu i v prostředí, které uvádí angličtinu jako
další preferovaný jazyk. Bez katalogu zůstávají české zdrojové texty
včetně správných českých tvarů pro 1, 2–4 a ostatní počty.

## Volba jazyka

`desktop/main.py` zavolá `install_translation()` před vznikem backendu a QML.
Qt použije `QLocale.system()` a jeho pořadí jazyků rozhraní podle prostředí
Linuxu (`LANG`, `LC_MESSAGES`, případně `LANGUAGE` a jejich systémové priority).
Nezavádíme vlastní přepínač jazyka ani neměníme locale čísel nebo datumů.
Změna prostředí vyžaduje nový start aplikace.

Načítají se pouze lokální katalogy `felismusic_<jazyk>.qm` v tomto adresáři.
Qt zohlední regionální varianty a základní jazyk (např. en_GB → en).
Pokud se nepodaří načíst katalog žádného preferovaného jazyka, použije se angličtina.
Pokud chybí i anglický katalog nebo překlad jednotlivé položky, použije se český zdrojový text.
Překlad neřídí jazyk API YouTube Music, názvy skladeb/playlistů od serveru,
přihlášení ani stav audia. Standardní texty Qt dialogů tento krok nemění.

## Aktualizace katalogů

Z kořene projektu:

```bash
env/bin/python tools/update_translations.py --release
```

Skript aktualizuje zdrojové katalogy `.ts` a sestaví `.qm`.
Používá dostupné nástroje Qt Linguist `pyside6-lupdate`, `lupdate6` nebo
`lupdate` a odpovídající `lrelease`. Při běžném spuštění aplikace
už Qt Linguist není potřeba. Změny katalogů commituj společně se
sestavenými soubory `.qm`. Rozpracované položky se do nich nezahrnují.
Pro zkušební sestavení mimo aplikační adresář lze přidat
`--output-dir /tmp/felismusic-translations`.

Jazyk lze jednorázově ověřit bez změny systémových nastavení:

```bash
env -u LC_ALL -u LC_MESSAGES LANG=en_GB.UTF-8 LANGUAGE=en ./run-gui.sh
```

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
- Po přidání nebo změně textu aktualizuj anglickou položku a znovu sestav katalogy.
