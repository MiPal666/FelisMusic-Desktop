# FelisMusic Desktop – aktuální stav

Aktualizováno: 2026-10-26 (Europe/Prague).

## Přijato uživatelem: 0.3.21-dev – Repeat pro aktuální frontu

- Nová fronta z prohlíženého seznamu (včetně opětovného spuštění stejné kolekce), náhodné spuštění kolekce, nové Rádio/Mix a první vložení do prázdné fronty nastaví Repeat na Vypnuto. Reset probíhá až při úspěšném vytvoření fronty; chyba nebo zneplatněná odpověď zachová starý stav.
- Pohyb a výběr přímo ve Frontě, Pause/Play, Stop/Play, Next/Previous, procházení, cover a přidávání do existující fronty Repeat zachovávají. Budoucí A2 zamíchání téže fronty ho rovněž zachová.
- Automatické kontroly: 197 offline testů; aktualizované původní scénáře zapínají Repeat po spuštění kolekce. Nové kontroly pokrývají všechny prohlížecí zdroje, opětovné spuštění stejné kolekce, výběr ve Frontě, pauzu/Stop a návrat, procházení/cover, neplatný výběr a první vložení. Stávající testy Shuffle/Rádia navíc ověřují reset až po úspěchu a zachování při chybě.
- QML ověřené skutečným klikáním při 1280×800 a 900×600 pro oba režimy: viditelný reset tlačítka po novém albu/Shuffle, zachování při návratu přes cover, výběru ve Frontě, pauze, Stop/Play a Next/Previous. Bez QML chyb; API i audio jsou testovací.
- Michal potvrdil skutečný test a přijetí 2026-10-26: Repeat funguje podle domluvy. A2 a další Rádio zatím nejsou rozpracované.

## Přijato uživatelem: 0.3.20-dev – A1 Shuffle kolekce

- Menu ⋮ otevřeného playlistu/alba obsahuje **Přehrát náhodně**. Používá převzaté `get_youtube_shuffle_tracks`: `get_watch_playlist(playlistId=…, shuffle=True)`, limit nejméně 25 nebo počet načtených skladeb. U alba se uchovává skutečné `audioPlaylistId`, nikoli jeho browseId.
- Fronta přebírá přesné pořadí použitelné odpovědi YTM, včetně opakovaných videoId; nejde o místní náhodné řazení. Přepnutí, Repeat a prefetch používají tutéž frontu. Uložené pořadí playlistu se nezapisuje ani nemění.
- Návrat přes cover zachová původní kolekci a navigační kontext. Vazba na řádek je podle dostupných výskytů; položka odpovědi mimo původně načtený seznam má index −1. Bez potvrzených occurrence ID se nevyrábějí `_guiPlaylistBinding`: náhodná fronta se neprohlašuje za přesné původní výskyty uloženého playlistu.
- U prázdné kolekce, nepodporovaného `RDCLAK…` či alba bez audioPlaylistId je akce neaktivní; u uploadů a interpreta se nezobrazuje. Stávající akce přidání kolekce do playlistu zůstává dostupná.
- Požadavek běží mimo UI vlákno. Původní audio/fronta zůstávají do úspěšné odpovědi; poté se staré audio zastaví před přípravou nového. Chyba nezničí starou frontu. Stop, změna přehrávání/fronty či opuštění detailu během dotazu zneplatní opožděný výsledek i chybu.
- Kontroly: **192 offline testů**, z toho 10 nových v `tests/test_shuffle.py`; skutečné QML kliknutí na menu, neaktivní nepodporovaná akce, návrat přes cover a pokračování podle fronty v 1280×800 a 900×600. Testy používají falešné API/audio, bez skutečného YTM účtu.
- **Michal potvrdil skutečný test a přijetí; commit `2c51536`.** Ověřeno album/playlist, Repeat, přechody tam/zpět a návrat přes cover. Uživatel chce zachovat rozdíl mezi původním řazením kolekce a skutečnou náhodně uspořádanou Frontou. Zamíchání už běžící fronty při zachování aktuální skladby (A2), interpret a doplňování rádia nejsou součástí tohoto podkroku.

## Aktuální souhrn po auditu 2026-10-26

- Přijatá verze **0.3.19-dev**, commit **`99dcad6`**. Správa playlistů **7a–7d hotová**; multivýběr a synchronizace změn playlistu do fronty rovněž přijaté. Poslední funkční etapa prošla 182 offline testy, QML kontrolami a skutečnými uživatelskými testy.
- [PLAN.md](PLAN.md) je přepsaný na aktuální stav, zbavený rozporů mezi historickými mezistavy. Níže zůstává podrobná historie přijatých etap. Porovnání původní reference `tmp/felismusic.py`, převzatého jádra a GUI je v [CLI-GUI.md](CLI-GUI.md).
- Přeskočené části: Shuffle 1b; kontextové/kolekční akce a samostatná editace fronty 3a–3c; metadata a přímé navigační vazby 4b/4c; doplňování rádia a artist/collection mixy 5b/5c; zbývající knihovní změny/odběry/odkazy 6a–6c. Samotný bod 7 je hotový; hromadné odebrání a přetahování jsou rozšíření.
- Oproti CLI GUI nezapojuje YTM Shuffle (včetně interpreta), průběžné rádio, rádio interpreta, resume session, interaktivní login a Cast. Relevantní převzaté definice byly při auditu ověřené proti původní CLI a shodují se v AST. Playlist management a multivýběr naopak jdou nad rámec CLI. MPRIS je nová integrace, nikoli hotový mechanismus CLI.
- Nejbližší návrh: Shuffle, potom s vysokou prioritou průběžné Rádio/Mix a akce interpreta/kolekcí. Následně uzavřít zbytek 3/4/6 a pokračovat 8 Session/login, 9 MPRIS, 10 Cast a 11 vydání. Zachovat lokální startup a ruční Cast discovery.
- Při tomto auditu se upravovala pouze dokumentace; nové programování, API zápisy ani nové skutečné testy zařízení se neprováděly.

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

### Otestováno uživatelem: 0.3.6-dev – skladbové menu a vkládání do fronty (část kroku 3a)

- Uživatel zadal krok 3 se zavřenou aplikací. První samostatně testovaný podkrok: nabídka přes „⋮“ / pravé tlačítko s akcemi Přehrát jako další / Přidat na konec fronty.
- Nové položky jsou kopie, včetně duplicit; vložení nemění aktuální skladbu, čas, pauzu ani Stop. Vícenásobné „jako další“ klade poslední volbu bezprostředně za aktuální skladbu. Prázdná fronta dostane jednu skladbu bez automatického přehrání.
- Vkládání je během přechodu/přípravy dočasně zakázané. Ve stabilním přehrávání nebo pauze aktualizuje model vložením jednoho řádku, bez resetu a bez přerušení audia.
- Přednačítání se zneplatňuje jen při změně následujícího videoId. Zachovává se Repeat, včetně návratu na první skladbu při all.
- Původ a navigační kontext jsou uložené u každého výskytu ve frontě. Změna skladby mezi různými zdroji proto obnovuje přes cover správnou kolekci a zdrojový index. Změny hodnocení se propisují také do těchto snapshotů.
- Prošlo 38 offline testů: 26 původních + 12 pro vkládání, přehrávání, přenačítání, duplicity, smíšené zdroje, pauzu, Stop a Repeat. QML ověřeno klikáním na obě varianty menu a jejich akce při 1280×800 i 900×600; zahrnutý návrat přes cover mezi vloženým albem a původním seznamem.
- Uživatel 2026-10-25 potvrdil funkčnost přehrání jako další a přidání do fronty. Na jeho návrh byla odstraněna duplicitní akce Přehrát odtud; přidání má přesnější název Přidat na konec fronty. Uživatel potvrdil i upravené menu. Podkrok je přijatý a uložený v commitu `a284740`. Akce pro celé kolekce, zbývající akce skladbového menu a odebírání/přesouvání položek zatím neimplementované.

### Otestováno uživatelem: 0.3.7-dev – interpret (podkrok 4a)

- Uživatel po commitu `a284740` výslovně zvolil krok 4 a potvrdil zavřenou aplikaci. Zbývající podkroky 3 zůstávají otevřené.
- Veřejný interpret z knihovny i hledání: části Skladby / Alba / Singly a EP. Uživatel původní variantu otestoval, následně schválil automatické načítání celých dostupných seznamů a řazení místo tlačítka Zobrazit vše. Skladby se načítají při otevření interpreta, ostatní části při prvním přepnutí. Používáme skutečné browseId/params z odpovědi YTM a `limit=None`; bez odkazu na rozšíření zobrazíme všechny dodané položky. Další přepnutí používá uložená data.
- Řazení každé části: výchozí A–Z, Z–A, Původní pořadí YTM; alba a singly/EP navíc podle roku oběma směry, chybějící rok vždy na konci. Zachováváme původní pořadí serveru pro možnost návratu. Změna řazení nepřestavuje přehrávanou frontu. Chyba načtení části ponechá dosavadní část; opakované kliknutí dotaz zopakuje.
- Album/single otevře detail skladeb. Zpět obnoví interpreta i vybranou část bez nového dotazu. Prázdné části nezavírají detail; chyba načtení zachová dosavadní obsah a možnost opakování.
- Snapshot původu přehrávání zahrnuje detail interpreta a návratovou historii alba. Cover je obnovuje; hodnocení se propisuje i do částí a historie. Procházení nepřerušuje zvuk ani nemění frontu.
- Nahraní interpreti zachovávají soukromý endpoint a seznam skladeb. Veřejné části jim nevyrábíme podle názvu.
- Prošlo 49 offline testů (38 původních + 11 pro interpreta a řazení). QML ověřeno klikáním při 1280×800 a 900×600: automatické načítání částí, řazení, otevření alba, Zpět, prázdná část a spuštění skladby; opět prošly i kontroly menu/fronty a smíšeného původu přes cover.
- Uživatel potvrdil funkčnost včetně automatického načítání a řazení. Řazení skladeb podle roku jsme po ověření dostupných údajů výslovně vynechali; roky zůstávají pouze u alb a singlů/EP. Uloženo společně s Mixem ze skladby v commitu `635fb27`. Hlavičky kolekcí a odkazy skladba → album → interpret (4b/4c), Shuffle a Mix nejsou tímto podkrokem dokončené.

### Otestováno uživatelem: 0.3.8-dev – Mix ze skladby (podkrok 5a)

- Uživatel po přijetí detailu interpreta výslovně zadal krok 5 a oznámil zavírání aplikace. Hlavičky kolekcí a odkazy z kroku 4b/4c zůstávají otevřené; změny 0.3.7-dev dosud nejsou commitnuté.
- Spustit mix v nabídce veřejné skladby/videa. Využívá CLI `get_radio_block`, `unique_new_radio_tracks` a testovací omezení bloků. Seed je první, doporučení bez neplatných/duplicitních videoId; prázdná doporučení skončí srozumitelnou chybou.
- Úspěšný mix nahradí playback frontu a otevře Frontu s názvem Mix: skladba. Právě hrající/pozastavený seed zachová audio, čas, hodnocení a stav; jiný či zastavený seed spustí od začátku. Repeat zůstává zachovaný, přednačítání se přesměruje na nového nástupce.
- Po dobu API požadavku je původní fronta/stav platný. Výsledek ověřuje generaci přehrávání a identitu/obsah fronty. Stop, jiný výběr a vložení položky během požadavku potlačí opožděný výsledek i jeho chybu. Běžná chyba mixu nemění přehrávání.
- Původ skladeb mixu odkazuje na živou Frontu; cover ji otevře bez obnovování zastaralého snapshotu. Nahrané skladby a epizody nemají akci mixu.
- Prošlo 59 offline testů (49 dosavadních + 10 pro rádio). QML ověřeno skutečným klikáním při 1280×800 a 900×600: nabídka, mix aktuální/jiné skladby, zobrazení fronty, cover a nepřítomnost akce u uploadů.
- Uživatel 2026-10-25 potvrdil funkčnost na skutečném YTM a audiu. Podkrok 5a je přijatý a uložený společně s detailem interpreta 0.3.7-dev v commitu `635fb27`. Zatím jeden blok doporučení; automatické doplňování 5b a mixy interpreta/kolekce 5c dosud neimplementované.

### Otestováno uživatelem: 0.3.9-dev – knihovna skladeb (první část 6a)

- Uživatel výslovně zvolil krok 6 a potvrdil vypnutou aplikaci. Zbývající nabídky kolekcí 3b, fronta 3c, hlavičky/navigace 4b/4c a rádio 5b/5c zůstávají otevřené.
- Původní variantu s dialogem uživatel otestoval jako funkční, následně schválil přímou akci v menu a výslovně požadoval provozuschopnost ostatních akcí během zjišťování stavu. Před touto úpravou potvrdil zavřenou aplikaci.
- Po porovnání s webovým YTM uživatel přijal dostupnost akcí podle vrácených údajů. Následně schválil skrytí knihovní položky během zjišťování i při nedostupném ovládání a opravu předání ID alba; před úpravou potvrdil zavřenou aplikaci.
- Menu nyní knihovní položku zpočátku skrývá. Pouze při potvrzené dostupné akci se na konci objeví Přidat/Odebrat podle skutečného stavu; bez dialogu a bez posunu stávajících akcí. Samostatný jednovláknový executor a vlastní autentizovaný YTMusic klient pro čtení uvolňují hlavní API worker pro Mix a další požadavky. Čtení nezvedá globální busy ani nemění stavový text přehrávání.
- Každé menu má identifikátor požadavku. Zavření, zánik delegátu nebo jiné menu zneplatní starou odpověď; čekající zbytečné úlohy se ruší. Nepodporovaný stav nebo chyba čtení ponechá knihovní položku skrytou. Uploady a epizody vynechané.
- Skladby otevřeného veřejného alba přebírají známé browseId alba jako albumId, pokud nemají vlastní konkrétní ID. Normalizace a fronta ID zachovávají; regresní test ověřuje skutečnou cestu otevření alba → fronta → náhradní dotaz na album.
- Nejprve `get_watch_playlist(videoId, limit=1)`; pokud chybí ovládání, dotaz na skutečné albumId a přesná shoda videoId v `get_album`. Bez stavu a správného feedback tokenu nedovolíme zápis. Používá `edit_song_library_status`, nikoli `rate_song`. Po zápisu nezávisle ověří stav; neověřený výsledek nehlásí jako úspěch. Chyba zápisu/ověření se zobrazí, členství není odhadované podle Like.
- Přehrávání, pozice, pauza/Stop, hodnocení a obsah fronty se změnou členství nemění. Ověřená změna aktualizuje knihovní seznam a původní snapshoty pro cover včetně indexů. Viditelná sekce Knihovna/Skladby se znovu načte ze serveru.
- Prošlo 75 offline testů (59 před knihovnou + 16 pro knihovnu včetně souběhu, rušení a předání ID alba). QML ověřeno klikáním při 1280×800 a 900×600: během zablokovaného čtení skutečně použity obě vkládací akce a Mix, pak přímé přidání/odebrání bez dialogu a ignorování staré odpovědi při změně menu. Ověřené skrytí položky během čekání i po odpovědi bez dostupné akce. Předchozí kontroly ověřily také obnovení seznamu/cover a uploady.
- Uživatel 2026-10-25 potvrdil finální menu i chování skladeb z alba křížovým porovnáním s webovým YTM. První část 6a je přijatá a uložená v commitu `c3de56b`. Alba/playlisty v knihovně, odběry interpretů a kopírování odkazů dosud nejsou implementované.

### Otestováno uživatelem: 0.3.10-dev – uložení skladby do playlistu (první část 7a)

- Uživatel potvrdil commit `c3de56b`, zavřenou aplikaci a výslovně zvolil krok 7. Zbývající části kroku 6 a dřívějšího plánu zůstávají otevřené.
- Přidat do playlistu… v menu skladby/videa/uploadu. Dialog načte všechny vlastní playlisty (`get_library_playlists(limit=None)`, owned=True); cizí, neznámé a automatické cíle se nenabízejí. Před zápisem nový `get_playlist(limit=None)` ověří vlastnictví i duplicity.
- Výchozí přesné duplicity podle videoId se nepřidají, dialog to oznámí. Výslovné Povolit další výskyt zapne `duplicates=True`. Přidání přes `add_playlist_items`, následný úplný dotaz ověřuje nárůst počtu výskytů vybraného videoId. Obsah se neodvozuje z názvu.
- Vytvoření nového soukromého playlistu se skladbou jedním `create_playlist(..., privacy_status=PRIVATE, video_ids=[id])`, následná kontrola obsahu. Prázdný název a < > odmítnuté. Při nejasném výsledku po zahájeném zápisu se opakované odeslání zablokuje do nového otevření; pokud už playlist vznikl, zpráva to výslovně uvede.
- Volba skladby zůstává navázaná na původní výběr. Audio, pozice, hodnocení a playback queue se nemění. Aktuálně prohlížený cílový playlist dostane ověřený obsah bez přestavění playback queue; přehled playlistů se při zobrazení obnoví.
- Uživatel při skutečném testu nahlásil chybu kontrolního načtení po vytvoření playlistu (odpověď bez contents). Ve webovém YTM ověřil, že playlist i vybraná skladba existují. Vlastní zápis tedy uspěl; příčina chybějícího obsahu v kontrolním dotazu není potvrzená. Po potvrzení zavřené aplikace upravené oddělení zápisu od ověření: tři pokusy pouze o čtení s odstupy 0 / 0,5 / 1,5 s, stručná zpráva a tlačítko Ověřit znovu, které už nikdy neopakuje vytvoření/přidání. Obsah se neoznačí za ověřený, dokud skutečně nepřijde. Technická těla odpovědí se nevypisují do dialogu.
- V průběhu práce je v Gitu commit `08a6493` obsahující první implementaci; aktuální oprava a tests/test_playlist_save.py čekají na uložení.
- Prošlo 89 offline testů (75 původních + 14 pro ukládání a ověřování playlistů). QML ověřeno klikáním při 1280×800 a 900×600: nabídka, výběr vlastního cíle, duplicity a opt-in dalšího výskytu, vytvoření soukromého playlistu a zachování audia/fronty. Navíc ověřeno stručné zobrazení neověřeného obsahu a úspěšné ruční Ověřit znovu po simulované chybě parseru bez opakování zápisu.
- Uživatel potvrdil, že po opravě vzniká playlist bez chyby a se skladbou, funguje přidání do existujícího playlistu i obě varianty duplicit. Následně schválil automatické zavření po ověřeném úspěchu a výrazné potvrzení duplicity přes OK; před úpravou potvrdil zavřenou aplikaci.
- Ověřený úspěch nyní zavře ukládací dialog, zpráva zůstane ve stavové liště. U nepovolené duplicity jsou vstupy skryté, zobrazené výrazné oznámení a pouze OK. Při chybě či neověřeném obsahu dialog zůstává otevřený; úspěšné Ověřit znovu ho také zavře. Kontrola QML při 1280×800 a 900×600 zahrnuje všechny tyto větve i povolenou duplicitu a zachování audia/fronty; 89 offline testů prochází.
- Uživatel 2026-10-25 potvrdil i finální dokončení dialogu jako funkční. První část 7a je přijatá; opravy a testy jsou uložené v commitu `cb4ce81`. YTM dovoluje shodné názvy playlistů, aplikace pracuje s jejich jedinečnými ID a názvovou jedinečnost nevynucuje. Přidání kolekcí (zbytek 7a), obecná tvorba/prázdný playlist a přejmenování/popisy/viditelnost (7b), odebrání/přesun (7c) a smazání (7d) dosud nehotové.

### Otestováno uživatelem: 0.3.11-dev – uložení seznamu do playlistu (druhá část 7a)

- Uživatel potvrdil commit `cb4ce81` a zavřenou aplikaci, pokračujeme druhou částí 7a.
- Přidat seznam do playlistu… v otevřených detailech se skladbami (album, playlist, část Skladby interpreta; také dostupné nahrané seznamy/mixy). Počet a pořadí vycházejí ze zachyceného modelu, bez odkazů odhadovaných podle názvu. Akce je skrytá na seznamech alb/singlů bez skladeb. Playlisty načítány celé přes limit=None.
- Výchozí režim vynechá existující videoId a opakování uvnitř výběru; výslovné povolení duplicit zachová všechny výskyty. Zbývající skladby se odešlou v původním pořadí. Nový soukromý playlist vytvořen jedním požadavkem bez opakujících se videoId. Celý duplicitní výběr zobrazí výrazné potvrzení přes OK.
- Kontrolní načtení ověřuje minimální výsledný počet všech přidávaných videoId, včetně více stejných výskytů. Neúplné potvrzení zachová možnost čtecího Ověřit znovu, bez opakování zápisu. Úspěšná stavová zpráva uvádí přidáno/vynecháno.
- Zůstává zachovaná kontrola vlastnictví, vazba dialogu na původní výběr, automatické zavření po ověřeném úspěchu a nezávislost playback queue/audia.
- Prošlo 95 offline testů (89 dosavadních + 6 pro dávky/kolekce). QML ověřeno klikáním při 1280×800 a 900×600: tlačítko kolekce, počet/pořadí, výchozí a povolené duplicity, vytvoření playlistu z výběru, skrytí na albové části interpreta, zachování audia/fronty.
- Uživatel potvrdil funkčnost celé této části, následně ověřil dostupnost i u nahraných seznamů. Druhá část 7a je přijatá a uložená v commitu `b114cea`. Následuje samostatná úprava rozložení popsaná níže. Prázdný playlist/úpravy údajů 7b, úpravy položek 7c a smazání 7d následují samostatně; dříve odložené kroky zůstávají otevřené.

### Otestováno uživatelem: 0.3.12-dev – kompaktní hlavičky a menu kolekcí

- Uživatel potvrdil commit `b114cea`, zavřenou aplikaci a povolil domluvenou úpravu vzhledu.
- Sdílená QML CollectionHeader pro detail hledání, knihovny a mixů: Zpět, název s elipsou a počet aktuálně zobrazených položek, vpravo ⋮. Menu obsahuje stávající Přidat seznam do playlistu…; není-li zapojená akce dostupná, ⋮ je skryté. Odstraněné samostatné akční tlačítko na dalším řádku.
- ArtistNavigation používá Flow: záložky a řazení na jednom řádku, při užší ploše se řazení zalomí. Pořadí a logika akcí, backend, playback queue a audio se neměnily.
- Prošlo všech 95 dosavadních offline testů. QML ověřeno při 1280×800 a 900×600: menu kolekce a celé uložení včetně duplicit/nového playlistu, přepínání interpreta, dlouhý název, návraty z knihovny/hledání/mixů, zachování audia/fronty. Zalomení řazení ověřeno také v uměle zúžené testovací ploše.
- Uživatel 2026-10-25 potvrdil funkčnost úpravy. Mezikrok vzhledu je přijatý a uložený v commitu `543732c`. Metadata typu rok/autor/cover a další akce kolekcí zůstávají plánované, stejně jako zbytek kroku 7 a starší otevřené podkroky.

### Otestováno uživatelem: 0.3.13-dev – nový prázdný playlist (první část 7b)

- Uživatel po commitu `543732c` potvrdil zavřenou aplikaci a povolil pokračování vytvořením prázdného playlistu.
- Nabídka ⋮ → Nový playlist… v přehledu Knihovna/Playlisty otevře samostatný formulář. `create_playlist(title, "", privacy_status=PRIVATE)` bez video_ids/source_playlist; nikdy nepoužije skladby z výběru ani playback queue.
- Ověřuje neprázdný název bez < >, názvovou jedinečnost nevynucuje. Úspěch podle vráceného playlistId zavře formulář a obnoví knihovní přehled. Samotné potvrzení vytvoření se neváže na kontrolní parser obsahu prázdného playlistu.
- Chyba/nepotvrzený výsledek má stručnou zprávu a zablokuje opakované odeslání; dvojklik a nové otevření během zápisu odmítnuté. Další pokus až po novém otevření a kontrole skutečného stavu. Audio, fronta, pozice a hodnocení nezměněné.
- Prošlo 101 offline testů (95 dosavadních + 6 pro prázdný playlist). QML ověřeno při 1280×800 a 900×600: umístění tlačítka, validace, vytvoření/obnova přehledu, otevření prázdné karty a Zpět, zrušení, chyba a blokování opakování, zachování audia/fronty.
- Uživatel ověřil vytvoření, ale nahlásil opožděné zobrazení karty až po ruční obnově. Po potvrzení zavřené aplikace upraveno: potvrzené nově vytvořené karty se uchovají v paměti do prvního skutečného výskytu ID v knihovní odpovědi; respektují řazení a shodné názvy, po převzetí serverových údajů nevzniká duplicita ani obnovení později smazané karty. Tlačítko nahrazeno nabídkou ⋮. Prošlo 103 offline testů a QML kontrola při 1280×800/900×600 včetně trvale opožděného knihovního přehledu, vytvoření přes menu, otevření prázdné karty, chyb a zachování audia/fronty.
- Uživatel 2026-10-25 potvrdil funkčnost finální opravy. První část 7b je přijatá a uložená v commitu `d811929`. Úpravy názvu/popisu/viditelnosti a další viditelnosti při tvorbě jsou další část 7b; úpravy obsahu/pořadí 7c, smazání 7d a starší otevřené části plánu zůstávají nedokončené.

### Otestováno uživatelem: 0.3.14-dev – údaje vlastního playlistu (další část 7b)

- Uživatel potvrdil commit `d811929`, schválil další podkrok úpravy názvu/popisu/viditelnosti a povolil programování po zavření aplikace.
- Detail playlistu zachovává příznak owned z get_playlist; akce ⋮ → Upravit playlist… dostupná jen pro owned=True, také u prázdného playlistu. Před formulářem se znovu načtou aktuální údaje, chybějící vlastnictví/viditelnost vyvolá stručnou chybu bez otevření formuláře.
- Formulář upravuje název, víceřádkový popis a PRIVATE/UNLISTED/PUBLIC; dovoluje vymazání popisu. Instalovaná ytmusicapi při prázdném description přeskakuje akci, proto tato větev používá stejný browse/edit_playlist endpoint s explicitní prázdnou ACTION_SET_PLAYLIST_DESCRIPTION a dalšími dvěma akcemi v jednom požadavku. Neprázdný popis používá veřejné edit_playlist.
- Zápis je vázaný na ID načtené formulářem a před ním se znovu ověřuje owned=True. Úspěch potvrzuje STATUS_SUCCEEDED; pak se zavře formulář a upraví název detailu, údaje již načtených karet a případná čekající karta nového playlistu. Fronta, audio a pozice se nemění. Neověřený zápis má stručnou zprávu a blokuje opakované odeslání; chyba před zápisem ponechá možnost dalšího pokusu. Syrové odpovědi se nevypisují.
- Prošlo 111 offline testů (103 předchozích + 8 pro metadata) a QML kontrola při 1280×800 a 900×600: vlastní prázdný playlist, aktuální údaje, skutečné ovládání volby viditelnosti, změna/zavření, zrušení, vymazání popisu, chyba a blokování dalšího odeslání, nepřítomnost menu u prázdného cizího playlistu a zachování audia/fronty.
- Uživatel 2026-10-25 potvrdil funkčnost úpravy údajů playlistu. Tato část 7b je přijatá a uložená v commitu `39ab6cc`. Následně domluveno doplnění výběru Soukromý/Neveřejný/Veřejný při všech způsobech vytvoření nového playlistu (prázdný, ze skladby, z kolekce), s výchozím Soukromý. Další viditelnosti přímo při tvorbě dosud nezapojené; obsah/pořadí 7c, smazání 7d a starší otevřené části plánu následují samostatně.

### Otestováno uživatelem: 0.3.15-dev – viditelnost při vytvoření playlistu (dokončení 7b)

- Uživatel potvrdil commit `39ab6cc` a povolil doplnění výběru viditelnosti ve všech způsobech vytvoření playlistu.
- Sdílený QML výběr Soukromý/Neveřejný (přístup přes odkaz)/Veřejný v dialogu prázdného playlistu i v režimu Nový playlist při ukládání skladby/kolekce. Při každém otevření reset na Soukromý. V existujícím playlistu se volba nezobrazuje a viditelnost se nemění.
- Backend přijímá jen PRIVATE/UNLISTED/PUBLIC, neplatné hodnoty odmítne před zápisem a umožní opravu. Volba se zachytí při odeslání a předá create_playlist přímo, bez následného editování. Dosavadní volání bez druhého argumentu zůstávají soukromá. Obsah, pořadí, duplicity a předchozí ověřování výsledku zachované.
- Prošlo 114 offline testů (111 dosavadních + 3 pro volby ve všech cestách a neplatné hodnoty). Kontrola QML při 1280×800 a 900×600 pokrývá všechny tři viditelnosti ve všech třech cestách, výchozí reset na soukromý, skrytí v existujícím playlistu a zachování audia/fronty.
- Uživatel 2026-10-25 potvrdil funkčnost výběru viditelnosti. Podkrok 7b je přijatý a uložený v commitu `413ba83`. Odebrání/přesun položek 7c, smazání 7d a starší otevřené podkroky zůstávají nedokončené.

### Otestováno uživatelem: 0.3.16-dev – odebrání výskytu skladby (první část 7c)

- Uživatel potvrdil commit `413ba83` a povolil první část 7c. Menu skladby v detailu vlastního playlistu obsahuje Odebrat z tohoto playlistu; není dostupné v jiném zdroji nebo bez přesné identity výskytu.
- Model, normalizace i playback track zachovávají setVideoId. Před zápisem se get_playlist(limit=None) znovu ověří owned=True a přesná shoda videoId/setVideoId. remove_playlist_items dostane jediný tento pár, nikoli index filtrovaného modelu nebo samotné videoId. Chybějící výskyt pouze obnoví detail, rozporná identita nebo chybějící vlastnictví nic nezapisují.
- Úspěch dle STATUS_SUCCEEDED lokálně odebere výskyt z čerstvého seznamu; běžné odebrání řádku používá beginRemoveRows místo resetu. Potvrzená odebrání se v paměti filtrují i z opožděných odpovědí, do prvního potvrzeného zmizení ID ze serveru. Nový výskyt stejného videoId s jiným setVideoId se neztrácí. Prázdný playlist zůstává otevřený s možností úpravy údajů.
- Uložené browsing snapshots a jejich indexy se upraví pro návrat přes cover. Uživatel potvrdil samotné odebrání, ale požádal také o synchronizaci fronty; po zavření aplikace schválil navržené chování.
- Původní výskyty při spuštění playlistu nesou vlastní vazbu playlistId/setVideoId. Potvrzené odebrání vyřadí odpovídající čekající původní výskyt z fronty ihned, bez resetu času/ratingu/audia; aktuální playing/paused/loading ponechá označený do opuštění. Po EOS se vyřadí i při Repeat One, následuje skutečný nástupce; Repeat All se vrací jen do zbývající fronty. Manual Next/Previous/výběr jiné skladby, Stop nebo selhání přípravy vyřadí označené opuštěné položky. Zastavený aktuální výskyt se odstraní ihned. Ruční vložení nekopíruje původní vazbu, takže ručně přidané kopie i jiné playlisty zůstávají zachované. Index, model fronty, marker a přednačítání se přizpůsobí, pořadí ostatních skladeb se nepřestavuje.
- Prošlo 135 offline testů (114 dosavadních + 10 pro odebrání a 11 pro synchronizaci fronty): duplicity, filtrování nedostupných skladeb, aktuální vlastnictví/ID, chybějící výskyt, neplatné zdroje, chyby čtení/zápisu, dvojklik a vazba na původní ID, opožděné odpovědi, nově přidaný výskyt, prázdný playlist, upload a zachování playbacku/obnovení přes cover. QML při 1280×800 a 900×600 ověřeno skutečným menu druhé duplicitní skladby, její odebrání během přehrávání, zachování druhé kopie/fronty/audia, návrat přes cover a nepřítomnost akce v cizím playlistu.
- Dodatečné offline kontroly: čekající a předchozí výskyty, zachování ruční kopie, posun indexu bez změny audia/času a bez falešného trackChanged, EOS/Repeat One/All, konec/vyprázdnění fronty, ruční přechody/výběr, paused/Stop, idle, jiný playlist, přerušení přednačítání a odebrání během přípravy audia. Aktualizovaná QML kontrola v obou velikostech ověřila vyřazení právě hrajícího výskytu po EOS, správného nástupce, okamžité vyřazení čekajícího původního výskytu a zachování ruční kopie.
- Uživatel 2026-10-25 potvrdil samotné odebrání i doplněnou synchronizaci fronty. První část 7c je přijatá a uložená v commitu `ca8c39e`. Přesouvání položek (zbytek 7c), smazání playlistu 7d a dříve otevřené podkroky dosud nehotové.

### Otestováno uživatelem: 0.3.17-dev – multivýběr a dvojklik

- Uživatel po commitu `ca8c39e` dodal screenshot multivýběru YTM a navrhl přesun přehrávání z jednoho kliku na dvojklik. Schválil předřazení multivýběru změně pořadí a povolil programování.
- Backend drží jediný výběr se zdrojem, seřazenými indexy řádků, kotvou a fokusem. Klik vybere jeden řádek; Ctrl přepíná, Shift vybírá rozsah, Ctrl+Shift sjednotí rozsah s výběrem, Ctrl+A všechny přehratelné řádky, Escape/Zrušit výběr ruší. Duplicity zůstávají samostatnými výskyty. Strukturální změny zdrojového modelu výběr invalidují; změna hodnocení ho zachová.
- QML ve všech track seznamech včetně Hledání a Fronty používá jeden klik pro výběr, dvojklik/Enter pro dosavadní playFrom. Kolekce bez videoId mají nadále jednoklikové otevření. Výběr má vlastní barvu, aktuální audio dosavadní značku. Společná lišta nad přehrávačem zobrazuje počet, Akce ⋮ a Zrušit výběr.
- Pravé tlačítko/⋮ zachová skupinu na vybraném řádku, jinak vybere nový samostatný řádek. Skupina používá tři společné akce (jako další, na konec, do playlistu); individuální mix/knihovna/odebrání jsou pro ni skryté. Uložení zachytí celou skupinu ve viditelném pořadí a používá stávající pravidla duplicit a viditelnosti. Nepodporované typy nemají společné uložení do playlistu.
- Enqueue byl sjednocen pro jednu i více skladeb: před úpravou zachytí všechny řádky a původní kontexty, potom vloží dávku v původním pořadí včetně opakovaných videoId. Ze samotné fronty se zachytí před vkládáním, aby se indexy neposunuly pod rukama. Ručně přidané kopie nezískávají automatickou vazbu pro synchronizaci s uloženým playlistem. Prázdná fronta se připraví bez startu audia, aktivní přehrávání/čas/pořadí zbývajících položek zůstávají zachované, prefetch se přesměruje podle nástupce.
- Prošlo 145 offline testů (135 dosavadních + 10 pro výběr a dávkové akce). QML při 1280×800 a 900×600 ověřeno skutečným klikáním/klávesnicí: klik bez přehrání, Ctrl/Shift/Ctrl+A/Escape, Enter a dvojklik, skupinové pravé menu, pořadí jako další, výběr do playlistového formuláře, zrušení, výběr/Enter v existující frontě a jednoklikové otevření alba. V užším okně test před kliknutím roluje na cílový řádek, aby neklikal do oříznuté části seznamu. Vizuálně ověřena lišta a odlišení vybraných řádků.
- Uživatel potvrdil funkčnost multivýběru a požádal o zobrazení lišty hromadných akcí pouze při alespoň dvou vybraných skladbách. Po potvrzení zavřené aplikace upravena viditelnost lišty a podmínky jejích akcí; menu ⋮ u jednotlivých řádků zůstává dostupné. QML znovu ověřeno při 1280×800 a 900×600 včetně přechodů 0→1→2 a 2→1→0, zachování ⋮, přehrávání a společných akcí. Uživatel ověřil i viditelnost lišty a následně požádal o odznačení po úspěšné akci. Po potvrzení zavřené aplikace doplněno zrušení původního výběru po úspěšném enqueue a po ověřeném uložení do playlistu. Chyba, neověřený obsah a pouhé zavření formuláře výběr zachovávají; úspěšné Ověřit znovu ho zruší jen tehdy, pokud jde stále o původní výběr. Revize výběru chrání pozdější výběr i se stejnými indexy před dokončením staršího formuláře. Prošlo 149 offline testů (145 předchozích + 4 pro dokončení a chyby). QML při 1280×800/900×600 navíc ověřilo zmizení výběru/lišt po enqueue a uložení do existujícího playlistu, zachování při zavření bez uložení a dosavadní výběr/přehrávání. Uživatel 2026-10-25 potvrdil finální chování podle představ. Multivýběr včetně dvojkliku, viditelnosti lišty a odznačení po úspěchu je přijatý a uložený v commitu `142bb2d`. Hromadné odebrání, změna pořadí playlistu, smazání playlistu a dřívější otevřené podkroky zůstávají nedokončené.

### Otestováno uživatelem: 0.3.18-dev – přesun položek playlistu (druhá část 7c)

- Uživatel potvrdil commit `142bb2d` a povolil pokračování přesouváním jednotlivých položek nahoru/dolů přes jejich menu.
- Akce pouze pro jednu položku vlastního detailu s videoId/setVideoId. Před uložením get_playlist(limit=None), owned=True, jedinečné identity obou výskytů i skutečné sousedství ve viditelném seznamu. Nahoru přes moveItem=(selected, previous); dolů přes moveItem=(selected, raw successor after next visible) nebo samotné selected pro konec. Žádné odhadování podle názvu/videoId ani záměna s indexem filtrovaným o nedostupné řádky.
- Úspěch potvrzuje STATUS_SUCCEEDED; běžný přesun používá beginMoveRows a zruší výběr jako jiná změna pořadí. Při změně obsahu na serveru lze model nahradit čerstvými daty. Čtecí a neověřené zápisové chyby mají stručné zprávy bez syrových odpovědí, původní zobrazení zůstává při chybě zachované.
- Potvrzené přesuny jsou dočasně vedené s výsledným raw pořadím výskytů. Při opožděném čtení se promítá jen suffix operací za posledním pozorovaným stavem; prosté opakování všech přesunů není idempotentní a bylo během testování opravené. Loader po dorovnání serveru pomocná data odstraní. Také odebrání položky používá promítnuté pořadí, aby nevrátilo předchozí přesun.
- Aktualizované browsing snapshots a indexy pro návrat přes cover. Původní řešení přerovnávalo jen část za aktuální pozicí; uživatel při testu nahlásil nesoulad fronty při přesunech aktuální/předchozí části a při zastavení. Po potvrzení zavřené aplikace opraveno: seřadí se všechny původní výskyty stejného playlistu na jejich místech, zachová se identita aktuální skladby a přepočítá její index i marker. Ručně vložené sloty zůstávají. Audio/čas/rating se nezmění a nedojde k falešnému trackChanged. Čtení aktuální položky a přechod po chybě přípravy jsou koordinované s přerovnáním přes transport lock. Prefetch se zneplatní a podle potřeby přednačte nový nástupce.
- Prošlo 160 offline testů (149 dosavadních + 11 pro přesuny): duplicity, hranice, nedostupné řádky, konec, aktuální vlastnictví/identity/sousedství, chyby čtení/zápisu, dvojklik a vazba na ID, opožděné čtení, opakované přesuny včetně 15 navazujících změn, zachování ručních slotů/current audio/času, cover a přesměrování prefetch. QML při 1280×800/900×600 ověřeno skutečným menu nahoru/dolů/na konec, neaktivní hranice, přesné duplicitní výskyty, nové pořadí čekající fronty a nástupce po EOS, cover, skrytí pro skupinu/cizí playlist. Menu vizuálně zkontrolované.
- Nově prochází 164 offline testů (160 předchozích + 4 regresní): přesun aktuálního duplicitního výskytu bez změny audia/času/ratingu, přesun předchozí položky za aktuální a správný nástupce po EOS, okamžitá synchronizace zastavené/pozastavené fronty a přesun během přípravy audia. Původní test s ručními sloty upraven pro nové umístění aktuální skladby. Aktualizovaná QML kontrola při 1280×800/900×600 ověřila také skutečné zobrazení Fronty po přesunu aktuální skladby na nový index a přesun při zastavení přes tlačítko Stop bez spuštění audia. Uživatel 2026-10-25 potvrdil funkčnost finální opravy včetně celé fronty. Přesouvání přes menu a synchronizace jsou přijaté a uložené v commitu `a3e106e`. Přetahování myší a hromadné odebrání jsou další možné podkroky; smazání vlastního playlistu 7d a dřívější otevřené části zůstávají nedokončené.

### Otestováno uživatelem: 0.3.19-dev – smazání vlastního playlistu (7d)

- Uživatel potvrdil commit `a3e106e` a povolil smazání vlastního playlistu s potvrzením, včetně zachování běžícího přehrávání.
- Detail nabízí ⋮ → Smazat playlist… pouze pro owned=True s platným ID, kromě známých automatických LM/SE/RD (také VL variant). Před otevřením se načte aktuální title/owned; potvrzení drží přesné playlistId. Zrušení/Escape před odesláním zneplatní potvrzení a nic nezapisuje.
- Před delete_playlist se znovu načte owned a potvrzený title. Změněné vlastnictví/název nic nesmaže a zablokuje staré potvrzení; výpadek čtení umožní opakování bez předchozího zápisu. Po odeslání je dvojklik, nové otevření a zavření blokované. STATUS_SUCCEEDED potvrzuje úspěch přímo. Při jiné/neúplné odpovědi nebo výjimce po odeslání následuje omezené čtecí ověření: před zápisem zachycené členství ID v úplné knihovně a po zápisu jeho zmizení. Neověřený zápis má neutrální zprávu a čtecí Ověřit znovu, blokuje opakované odeslání a nemění místní přehled jako by šlo o úspěch. Výslovný STATUS_FAILED/error zůstává chybou, dostupné je pouze čtecí ověření.
- Úspěch odstraní přesnou kartu z načtených modelů a snapshotů, uklidí pomocné informace pro vytvoření/přesuny/odebrání, zapamatuje smazané ID proti opožděným výsledkům knihovny/hledání a vyřadí ho z nových cílů ukládání. Stejný název jiného ID zůstává. Návrat do knihovního přehledu proběhne po busy=False jen pokud uživatel stále měl otevřený tento detail.
- Fronta se nepřestavuje a audio/čas/pořadí se nemění. Origins skladeb z vymazaného zdroje se odpojí na source=playing/context page 5; cover otevře skutečnou Frontu a další skladby pokračují. Vyčistí se také rodičovské přehledy a historie, aby návrat neobnovil smazanou kartu/detail.
- Prošlo 174 offline testů (164 předchozích + 10 pro smazání): potvrzení/zrušení, přesné stejnojmenné ID, prázdný playlist, čerstvé vlastnictví/název, automatické/cizí/nesprávné typy, výpadky a nepovolené opakování, neověřený stav, běžící fronta/čas/cover/EOS, opožděné karty a cíle uložení, dvojklik a změna pohledu za běhu požadavku. QML při 1280×800/900×600 ověřeno skutečným menu a dialogem: zrušení bez zápisu, potvrzení, přeživší stejnojmenná karta, filtrování trvale opožděného přehledu, zachování audia/fronty, cover na Frontu, stručná blokovaná chyba, skrytí u cizího a smazání prázdného playlistu. Dialog vizuálně zkontrolován.
- Uživatel při skutečném testu nahlásil, že playlist byl smazán, ale dialog hlásil nepotvrzený výsledek (log pouze RuntimeError). Následný uživatelský log potvrdil typ dict bez položky status, s přítomným responseContext; úplné tělo odpovědi se nezaznamenává. Po zavření aplikace opravené vyhodnocení: zachování jednoho zápisu, doověření přes úplnou knihovnu s validací skutečného grid rendereru a zahrnutí první stránky do úplného výsledku. Chybějící renderer/parsování/síť se nesmí zaměnit za prázdnou knihovnu. Bez zachyceného členství před zápisem lze potvrdit jen explicitní 404 daného playlistu spolu s čitelným knihovním přehledem; obecný parser error není důkaz. Pro nejasný stav doplněné Ověřit znovu bez dalšího delete_playlist. Diagnostika vypíše jen typ odpovědi, známý stav a přítomnost vybraných klíčů, nikdy tělo odpovědi/auth data.
- Prochází 182 offline testů (174 předchozích + 8 pro ověření): odpověď bez statusu, výjimka po skutečném smazání, opakované čtení až k potvrzení bez dalšího zápisu, neplatný knihovní renderer, síťová chyba, předem chybějící členství, explicitní not-found a nesoulad validované první stránky s neúplným seznamem. QML při 1280×800/900×600 znovu ověřilo odpověď bez statusu s automatickým doověřením, neutrální neověřený stav a úspěšné Ověřit znovu bez dalšího zápisu, včetně zachovaného audia/fronty. Uživatel 2026-10-26 potvrdil, že mazání funguje a aplikace už výsledek správně potvrdí. Podkrok 7d včetně opravy ověřování je přijatý a uložený v commitu `99dcad6`. Hromadné odebrání, přetahování myší a dřívější otevřené části plánu zůstávají nedokončené; zatím neoznačovat celý plán 1.0 za hotový.

## Pracovní domluva

- Řešit jeden problém za druhým.
- Před změnami aplikace upozornit uživatele na zavření aplikace; uživatel potvrzuje, že lze upravovat. Při pouhém čtení může aplikace běžet. Příprava příkazu pro commit a zápis přijetí do dokumentace nevyžadují další pokyn; na potvrzení čekat až před programováním aplikace.
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
