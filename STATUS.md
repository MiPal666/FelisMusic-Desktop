# FelisMusic Desktop – aktuální stav

Aktualizováno: 2026-10-25 (Europe/Prague).

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
- Uživatel po skutečném přehrání potvrdil: „výsledek je super“. Uloženo společně s 0.3.3.5-dev v commitu `7f3f704`. Git zápis je v prostředí asistenta blokovaný; commit provádí uživatel podle připraveného příkazu a posílá výsledek.

### Otestováno uživatelem: 0.3.3.5-dev

- Při kliknutí na skladbu a ručním Previous/Next se původní audio zastaví před přípravou nové položky, s ponecháním lokálního výstupu v READY kvůli zachování směrování.
- Řádek během přípravy ukazuje „Připravuji…“, po spuštění „Hraje“, při pauze „Pozastaveno“ a při zastavení „Zastaveno“.
- Neaktuální stahování a čekání na spuštění se zneplatní novým výběrem. Zastavení a spuštění výstupu se synchronizují, aby starší worker nemohl po novém kliknutí spustit původní skladbu.
- Automatické dohrání dál používá přednačítání bez dalšího stopu.
- Prošlo 10 offline testů přehrávání/přednačítání a samostatná kontrola skutečného kliknutí v QML: okamžité zastavení starého audia, příprava nové položky a správná změna označení po spuštění. Uživatel ověřil skutečné přehrávání a potvrdil: „funguje jak má“. Uloženo společně s přednačítáním v commitu `7f3f704`; po commitu byl pracovní strom čistý.

### Navazující funkce

- Závazný aktuální postup: `PLAN.md`, jeho původní znění je uložené v commitu `e8012e0`. Repeat je přijatý a commitnutý (`0a9b50c`). Uživatel následně výslovně zadal krok 2 – Fronta + Info; Shuffle zůstává odložený, neimplementovaný.
- Do desktopové 1.0 patří také správa vlastních playlistů a Cast s převzetím ověřené logiky CLI. Následují Fronta/Info, kontextové akce, detaily, rádio, knihovna/odběry, playlisty, obnova session/přihlášení, MPRIS, Cast a závěrečné ověření podle pořadí v plánu.
- Trvalé offline stahování až po 1.0. Připínání do „Poslouchejte znovu“ a poděkování u skladby jsou vyřazené. Sailfish port je samostatná etapa po stabilním desktopu.
- Návrat přes cover slouží k otevření původní kolekce. Samostatná Fronta v 0.3.5-dev je uživatelem otestovaná a uložená v commitu `f04c01b`, viz níže.
- Výchozí výstup při startu zůstává Toto zařízení. CLI 1.0.0 je samostatný zmrazený projekt.

### Otestováno uživatelem: 0.3.4-dev – Repeat (krok 1a)

- Tři režimy: vypnuto / celý seznam / jedna skladba. Tlačítko je vedle transportních ovladačů, s textem, barevným zvýrazněním a tooltipem.
- Používá přepínání režimů z CLI. Repeat-one se uplatní při dohrání; ruční Next/Previous přejdou na sousední skladbu. Repeat-all obaluje seznam při dohrání i ručním Next/Previous.
- Změna režimu zachová pozici i pauzu a sama nezačne přehrávat. Po startu aplikace je režim vypnutý, během relace zůstává i při výběru nové kolekce.
- Přednačítání respektuje skutečného následujícího kandidáta; repeat-one další skladbu nestahuje, repeat-all na konci připraví první. Změna režimu zneplatní nepotřebné přednačítání.
- Prošlo 18 offline testů (10 původních a 8 pro Repeat), plus QML kontrola načtení, viditelnosti a skutečného klikání na tlačítko při 900 a 1280 px.
- Uživatel 2026-10-25 potvrdil funkčnost Repeat po skutečném testu. Podkrok 1a je přijatý a uložený v commitu `0a9b50c`. Shuffle (1b) zatím neimplementovaný; na následný výslovný pokyn uživatele jsme přešli ke kroku 2.

### Otestováno uživatelem: 0.3.5-dev – Fronta + Info + Stop (krok 2)

- Nová položka Fronta v levé navigaci: model ze skutečné playback fronty, aktuální řádek, pozice `N / celkem`, vlastní scroll a tlačítko Na aktuální. Kliknutí na řádek zachovává existující frontu i původní zdroj/navigaci pro cover.
- Info v horní liště: živý detail aktuální skladby s interpretem, albem, délkou, hodnocením a pozicí ve frontě. Prázdná fronta má vysvětlení a Info je deaktivované.
- Stop je dostupný i během načítání; zneplatní požadavky a zastaví audio s výstupem v READY. Fronta, vybraná skladba a repeat zůstanou zachované. Play po Stop začíná vybranou skladbu od nuly; Pause zachovává pozici.
- Prošlo 26 offline testů (18 původních, 8 pro frontu/metadata/Stop). Ověřena i změna výběru během stahování, duplicitní skladby a zrušení přednačítání při Stop.
- QML ověřeno skutečným klikáním při 1280×800 a 900×600: prázdná fronta, výběr, nezávislé rolování, živé Info a zavření dialogu, Stop/Play i návrat přes cover.
- Uživatel 2026-10-25 potvrdil funkčnost celého kroku 2 na skutečném přehrávání. Etapa je uložená v commitu `f04c01b`.

### Uživatelsky ověřeno, čeká na commit: 0.3.6-dev – skladbové menu a vkládání do fronty (část kroku 3a)

- Uživatel zadal krok 3 se zavřenou aplikací. První samostatně testovaný podkrok: nabídka přes „⋮“ / pravé tlačítko s akcemi Přehrát jako další / Přidat na konec fronty.
- Nové položky jsou kopie, včetně duplicit; vložení nemění aktuální skladbu, čas, pauzu ani Stop. Vícenásobné „jako další“ klade poslední volbu bezprostředně za aktuální skladbu. Prázdná fronta dostane jednu skladbu bez automatického přehrání.
- Vkládání je během přechodu/přípravy dočasně zakázané. Ve stabilním přehrávání nebo pauze aktualizuje model vložením jednoho řádku, bez resetu a bez přerušení audia.
- Přednačítání se zneplatňuje jen při změně následujícího videoId. Zachovává se Repeat, včetně návratu na první skladbu při all.
- Původ a navigační kontext jsou uložené u každého výskytu ve frontě. Změna skladby mezi různými zdroji proto obnovuje přes cover správnou kolekci a zdrojový index. Změny hodnocení se propisují také do těchto snapshotů.
- Prošlo 38 offline testů: 26 původních + 12 pro vkládání, přehrávání, přenačítání, duplicity, smíšené zdroje, pauzu, Stop a Repeat. QML ověřeno klikáním na obě varianty menu a jejich akce při 1280×800 i 900×600; zahrnutý návrat přes cover mezi vloženým albem a původním seznamem.
- Uživatel 2026-10-25 potvrdil funkčnost přehrání jako další a přidání do fronty. Na jeho návrh byla odstraněna duplicitní akce Přehrát odtud; přidání má přesnější název Přidat na konec fronty. Uživatel potvrdil i upravené menu. Podkrok je přijatý a čeká na commit. Akce pro celé kolekce, zbývající akce skladbového menu a odebírání/přesouvání položek zatím neimplementované.

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
