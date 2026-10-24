# FelisMusic Desktop – aktuální stav

Aktualizováno: 2026-10-24 (Europe/Prague).

## Uzavřený a otestovaný základ

Otestovaný základ **0.3.3.3-dev** je uložený v prvním commitu `f62ec06` na větvi `main`. Základ a následující opravy uživatel proklikal a přijal jako funkční výchozí bod pro další funkce.

- Knihovna, hledání YT Music / Knihovna / Nahrané, typové filtry a odstranění nepoužitelných výsledků.
- Lokální přehrávání přes GStreamer, předchozí/další skladba, automatický přechod, seek, hlasitost, mute a hodnocení.
- Autoscroll při změně skladby; během téže skladby lze seznam volně procházet.
- Kategorie Knihovny se při zúžení okna zalamují a délky skladeb zůstávají viditelné.
- Nahrané skladby v detailu alba přebírají jeho cover, pokud nemají vlastní. U uploadů se nepoužívá veřejný YouTube thumbnail jako náhrada.
- Kliknutí na cover přehrávače obnoví původní kolekci a její navigaci: stránku, příslušné kategorie, řazení, název a nadřazený seznam. Aktuální skladbu přivede do záběru bez restartu přehrávání nebo zrušení pauzy.

## Ověření

- Uživatel potvrdil hledání, autoscroll a opravu coverů; po poslední úpravě návratu přes cover oznámil, že vše dostupné proklikal a základ vypadá funkční.
- Automatická kontrola na testovacích datech: návrat do playlistu, nahraného alba, mixu, hledání, knihovních skladeb, Oblíbených a Historie při šířkách 900 a 1280 px. Ověřeno zachování fronty, pozice a pauzy, původních dat i funkce zpět a návratu bez nových požadavků na YTM.

## Další práce

### Otestováno uživatelem: 0.3.3.4-dev

- Přednačítání jedné následující skladby během přehrávání aktuální, s využitím stávající cache.
- Přehrávání i přednačítání používají jeden sériový audio worker; při přechodu během přípravy se využije stejné stažení.
- Selhání přednačítání nemění frontu ani aktuální přehrávání. Při zavření se příprava ruší a cache se uklízí až po skončení workeru.
- V této verzi zůstalo chování staré skladby během ručního výběru jiné zachované; následně uživatel zadal úpravu popsanou níže.
- Šest offline testů pokrývá přednačtení před dohráním, dohrání během stahování, chybu a opakování přípravy, zneplatnění nepotřebného přednačítání a zavření během přípravy aktuální i příští skladby.
- Uživatel po skutečném přehrání potvrdil: „výsledek je super“. Tato změna ještě není commitnutá. Git zápis je v prostředí asistenta blokovaný; commit provádí uživatel podle připraveného příkazu a posílá výsledek.

### Otestováno uživatelem: 0.3.3.5-dev

- Při kliknutí na skladbu a ručním Previous/Next se původní audio zastaví před přípravou nové položky, s ponecháním lokálního výstupu v READY kvůli zachování směrování.
- Řádek během přípravy ukazuje „Připravuji…“, po spuštění „Hraje“, při pauze „Pozastaveno“ a při zastavení „Zastaveno“.
- Neaktuální stahování a čekání na spuštění se zneplatní novým výběrem. Zastavení a spuštění výstupu se synchronizují, aby starší worker nemohl po novém kliknutí spustit původní skladbu.
- Automatické dohrání dál používá přednačítání bez dalšího stopu.
- Prošlo 10 offline testů přehrávání/přednačítání a samostatná kontrola skutečného kliknutí v QML: okamžité zastavení starého audia, příprava nové položky a správná změna označení po spuštění. Uživatel ověřil skutečné přehrávání a potvrdil: „funguje jak má“. Připraveno ke commitu společně s přednačítáním z 0.3.3.4-dev.

### Navazující funkce

- Pokračovat po jednotlivých funkcích: informace o skladbě a samostatná Fronta, kontextové akce, detail interpreta/kolekcí, shuffle, repeat a rádio/mix.
- Dále obnova session, další optimalizace cache, MPRIS a Cast; následně port na Sailfish OS.
- Návrat přes cover slouží k otevření původní kolekce. Samostatná Fronta ještě není hotová.
- Výchozí výstup při startu zůstává Toto zařízení. CLI 1.0.0 je samostatný zmrazený projekt.

## Pracovní domluva

- Řešit jeden problém za druhým.
- Před změnami aplikace upozornit uživatele na zavření aplikace; uživatel potvrzuje, že lze upravovat. Při pouhém čtení může aplikace běžet.
- Po změně stručně popsat výsledek, ověření a co má uživatel vyzkoušet.
- Shellové příkazy pro uživatele psát vždy na jediném řádku.
- Git má zachytit přijatý základ a potom přehledné dokončené změny; první commit je výslovně autorizovaný. Push ani publikace nebyly zadány.

## Soubory a spuštění

- Projekt: `/home/michal/src/FelisMusic`.
- Spuštění: `./run-gui.sh` (skript aktivuje `env`, pokud existuje).
- Virtualenv vyžaduje `--system-site-packages` kvůli GStreameru/PyGObject.
- Přihlášení je mimo projekt v `~/.config/felismusic/`; autentizační soubory nepatří do Gitu.
- `legacy_core.py` je převzaté CLI jádro s desktopovými úpravami audio výstupu, nikoli nezměněná kopie CLI.
- Podrobná historie a plán: `FelisMusic-STATUS-2026-10-21.md`. Pro současný stav má přednost tento soubor a README.
