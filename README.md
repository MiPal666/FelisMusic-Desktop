# FelisMusic Desktop

## Stav

- Desktop GUI: **0.3.3.3-dev**
- Aktuální stav a předání projektu: [STATUS.md](STATUS.md). Základ včetně oprav z 2026-10-24 byl uživatelem přijat jako otestovaný.
- GUI toolkit: PySide6 + QML
- FelisMusic CLI 1.0.0 je samostatný, zmrazený projekt / referenční implementace.

GUI používá existující FCM session z `~/.config/felismusic/`.

## Hotová datová vrstva

- start na Knihovně,
- Hledat,
- Knihovna: Playlisty, Skladby, Alba, Interpreti, Profily, Podcasty, Nahrané,
- Nahrané: Skladby / Alba / Interpreti,
- rozkliknutí kolekcí na skladby/epizody,
- Oblíbená hudba,
- Historie,
- Mixy pro vás a otevření mixu,
- obrázky, názvy, interpreti/alba, délky a počty,
- řazení knihovny tam, kde dává smysl,
- Playlisty: Výchozí YTM / A–Z / Z–A,
- Oblíbená hudba: Výchozí YTM / A–Z / Z–A,
- Historie zůstává chronologická, Mixy zachovávají pořadí YTM.

## 0.3-dev – první skutečný přehrávač

- výchozí a zatím jediný aktivní výstup je **Toto zařízení / GStreamer**,
- kliknutí na skladbu vytvoří frontu z právě zobrazeného seznamu a spustí ji,
- funguje pro Knihovnu – Skladby, Oblíbenou hudbu, Historii a rozkliknuté playlisty/alba/mixy,
- v Hledání se přehraje položka, která má `videoId`; ostatní typy výsledků se zatím jen zobrazují,
- spodní player ukazuje cover, skladbu, popis, pozici a délku,
- Play/Pause,
- Previous / Next,
- automatický přechod na další skladbu po dohrání,
- nepřehratelná skladba se při startu přeskočí podobně jako v CLI,
- lokální audio dál používá osvědčenou seekovatelnou dočasnou cache z CLI core.

Zatím není v 0.3.3.3-dev:

- repeat/shuffle,
- fronta v samostatném panelu,
- Cast discovery a přepínání výstupů.

## Důležité: GStreamer a virtualenv

Na openSUSE je PyGObject/GStreamer systémový Python modul. GUI virtualenv proto musí vidět systémové balíčky:

```bash
cd /home/michal/src/FelisMusic
rm -rf env
python3 -m venv --system-site-packages env
source env/bin/activate
python -m pip install -U pip
python -m pip install -r requirements-gui.txt
```

`run-gui.sh` při chybějícím `gi/Gst` vypíše varování. Datová vrstva bude fungovat dál, ale lokální přehrávání ne.

## Aktualizace

```bash
cd /home/michal/src/FelisMusic
tar -xzf ~/Stažené/FelisMusic-desktop-0.3.3.3-dev.tar.gz --strip-components=1
source env/bin/activate
./run-gui.sh
```

Pokud session není platná, obnov ji v samostatném FelisMusic CLI 1.0.0 a GUI spusť znovu.

## 0.3.1-dev

- Knihovna: `Výchozí YTM` zůstává pouze u Playlistů. Ostatní kategorie používají `Nedávno přidané / A–Z / Z–A`, protože prázdný `order` po předchozím řazení není spolehlivý reset pořadí.
- Obrázky skladeb: robustnější čtení thumbnailu a fallback na standardní YouTube `ytimg` podle `videoId`, pokud knihovní endpoint obrázek nevrátí.
- Přehrávač: během přípravy lokálního audia je viditelný spinner, text `Připravuji skladbu…` a indeterminate progress bar; stav je zároveň vidět v horním statusu.
- Ukončení: backend je vlastněný QML enginem a držen po celý život aplikace, aby při zavírání nevznikala série `Cannot read property ... of null`.


## 0.3.2-dev

- progress je skutečný `Slider`: lze kliknout / táhnout na požadovanou pozici ve skladbě,
- seek tlačítka `−30 / −10 / +10 / +30 s`,
- hlasitost 0–100 % přes slider,
- tlačítka hlasitosti po 5 %,
- mute / unmute,
- hlasitost a mute se čtou ze skutečného GStreamer výstupu, ne jen z GUI stavu,
- seek funguje při přehrávání i pauze a používá seekovatelnou lokální cache.


## 0.3.2.1-dev

- transportní tlačítka mají vlastní QML kreslené ikony, takže nezávisí na systémovém icon theme ani na dostupnosti Unicode symbolů,
- seek tlačítka a hlasitost mají explicitně stylovaný text s kontrastní barvou,
- drag/click na seek slideru je obsloužen explicitní MouseArea a seek se provede při puštění myši, takže backendový polling už nepřepisuje polohu během tažení,
- při tažení seeku se vlevo zobrazuje cílový čas,
- oblast hlasitosti je širší a volume slider má větší preferovanou šířku,
- hláška `kf.iconthemes: Icon theme "AdwaitaLegacy" not found` je systémové Qt/KDE varování; ovládací prvky FelisMusic na něm už nejsou závislé.


## 0.3.3-dev

- aktuální skladba má v playeru tlačítka `Oblíbená` a `Neoblíbená`,
- stav se načte z `likeStatus`; pokud ho daný YT Music endpoint neposlal, GUI ho zjistí na pozadí přes watch queue,
- kliknutí na aktivní hodnocení ho zruší (`INDIFFERENT`), stejně jako v CLI 1.0,
- změna se v GUI projeví okamžitě a teprve potom se uloží přes `ytmusic.rate_song()`,
- během ukládání jsou tlačítka dočasně zamčená a zobrazí se malý spinner,
- pokud YouTube Music změnu odmítne, GUI vrátí předchozí stav a zobrazí chybu,
- známý stav hodnocení se propisuje i do už načtených modelů/fronty, takže při návratu ke stejné skladbě není potřeba stav znovu zjišťovat,
- skladby načtené přes `Oblíbená hudba` jsou považovány za `LIKE` i tehdy, když endpoint explicitní `likeStatus` vynechá.


## 0.3.3.2-dev

- hledání: výsledky bez `videoId` už nejsou mrtvé položky; album, interpret, playlist, podcast nebo profil lze rozkliknout na detail a skladby, zatímco skladba/video se dál rovnou přehrává,
- Oblíbená hudba se po změně like/dislike obnoví a při každém vstupu na stránku se znovu načte z YT Music; zvolené A–Z/Z–A řazení se přitom zachová,
- Like/Dislike mají vlastní QML kreslené palce nahoru/dolů místo textových tlačítek a nejsou závislé na Unicode ani icon theme,
- lokální GStreamer preferuje `pulsesink` (přes PipeWire/Pulse) a při jeho absenci `pipewiresink`, aby byl stream normálně vidět v Plasma/PipeWire směšovači,
- mezi skladbami už audio pipeline nepadá do `NULL`, ale zůstává v `READY`; tím se zachová uživatelské přesměrování výstupu (např. HDMI) místo vytvoření nového streamu na výchozím zařízení.

- Hledání má filtr `Vše / Skladby / Alba / Interpreti / Playlisty / Podcasty / Nahrané soubory`, stejně jako CLI 1.0.


## 0.3.3.2-dev

- aktuálně přehrávaná skladba je v seznamu zvýrazněná a označená `Hraje`,
- seznam sleduje změnu aktuální skladby a posune ji do viditelné oblasti,
- Hledání/Vše zobrazuje typ výsledku (Skladba, Album, Interpret, ...),
- search entity bez použitelného ID je zřetelně označená `bez odkazu` a kliknutí už nevyhodí chybu,
- interpret ve výsledcích používá správně i pole `artist`, takže nevzniká falešné `Bez názvu`,
- délka skladby má fallback přes `duration_seconds`, pokud YTM nevrátí textové `duration`.


## 0.3.3.3-dev

- Hledání je rozdělené stejně jako YT Music/ytmusicapi na samostatné scope `YT Music / Knihovna / Nahrané soubory`; už se nesnaží míchat veřejný katalog, knihovnu a uploady do jednoho filtru.
- `YT Music` a `Knihovna` mají typový filtr `Vše / Skladby / Videa / Alba / Interpreti / Playlisty / Profily / Podcasty / Epizody`.
- `Nahrané soubory` používají pouze vlastní search scope bez typového filtru, protože uploads scope kombinaci s `filter=` nepodporuje.
- výsledky bez použitelného `videoId` / `browseId` / `playlistId` se už do GUI vůbec nezařadí; mrtvá karta typu `Interpret · bez odkazu` tedy zmizí,
- upload album/interpret se rozpozná i podle privátního `browseId`, i když search payload nevrátí `resultType`,
- automatické sledování seznamu se spouští jen při skutečné změně skladby. Během přehrávání lze seznam normálně rolovat; při Next/Previous nebo automatickém přechodu se nová skladba znovu přivede do záběru.


## Rozložení při zúžení okna

- Kategorie Knihovny a nabídka řazení se při nedostatku místa zalomí do dalšího řádku.
- Seznam skladeb se přizpůsobuje dostupné šířce, takže délky skladeb zůstávají viditelné i v úzkém okně.

## Návrat k přehrávanému seznamu

- Kliknutí na cover ve spodním přehrávači zobrazí aktuálně přehrávaný seznam a přivede aktuální skladbu do záběru.
- Cover obnoví původní stránku a navigaci: playlist v Knihovně, nahrané album v Nahraných, mix v Mixech pro vás nebo původní hledání. Zachová název kolekce, příslušnou kategorii a řazení; tlačítko zpět vede do původního nadřazeného seznamu.
- Seznam zůstává dostupný i po procházení jiných playlistů, Knihovny nebo hledání; návrat nevyžaduje nové načítání z YT Music.
- Návrat zachová pozici přehrávání i pauzu. Kliknutím na jiný řádek lze přejít na danou skladbu ve stávající frontě.
- Bez vybrané skladby není cover klikací.

## Obrázky nahrané hudby

- Skladby v detailu nahraného alba přebírají cover alba, pokud nemají vlastní obrázek. Cover se přenese také do přehrávače a přehrávaného seznamu.
- U nahrané hudby se nepoužívá veřejný YouTube thumbnail podle videoId, protože soukromá ID tímto způsobem obrázek nezpřístupňují.
- Pokud YouTube Music nevrátí obrázek skladby ani otevřeného alba, zůstane neutrální plocha.
