# FelisMusic Desktop

## Stav

V menu ⋮ otevřeného online alba jsou také **Přehrát jako další** a **Přidat na konec fronty**. Vloží celé album v původním pořadí bez přerušení současné skladby. Prázdnou frontu připraví bez automatického spuštění.

U interpreta otevřeného z Knihovna → Interpreti nabídne rozbalovací volba **Skladby** (výchozí knihovní obsah podle YTM) a **Všechny skladby** (celý dostupný katalog). Oba seznamy lze řadit; přepnutí nemění rozehranou frontu. Alba a Singly/EP i dosavadní akce interpreta zůstávají stejné.

Online skladby nyní v menu ⋮ nabízejí Otevřít album / interpreta podle skutečných ID; u více interpretů lze vybrat konkrétního. V detailu alba je pouze přechod na interpreta, u interpreta na album. Přechod přepne i sekci Knihovna → Alba/Interpreti a Zpět obnoví původní seznam, hledání, Oblíbené, historii nebo Frontu. Přehrávání zůstává beze změny.

Online Knihovna → Skladby se nyní také načítá po blocích s použitelným prvním seznamem, lokálním stavem a postupným doplňováním rozehrané fronty. Po úplném načtení nabídne ⋮ pouze „Přehrát náhodně“, které míchá všechny načtené výskyty lokálně; pro celý tento seznam se nepřidává Mix ani enqueue/save kolekce. Jednotlivé a vybrané skladby si své akce zachovávají.

Ve vlastním playlistu lze označit více skladeb a přes Akce ⋮ → Odebrat z playlistu potvrdit odebrání přesných výskytů. Duplicitní skladby se rozlišují pomocí setVideoId. Navázaná přehrávací fronta se synchronizuje; aktuální odebraný výskyt může dohrát, ručně vložené kopie se zachovají. Po úspěchu se výběr zruší.

Nahrané mají pořadí Alba → Interpreti → Skladby. První vstup po spuštění aplikace otevírá Alba; při dalších návratech během stejného běhu se obnoví naposledy navštívená sekce Nahraných. Nahrané skladby se načítají po blocích: první část lze přehrát dvojklikem, další se doplní na pozadí i do stejné rozehrané fronty. Navigace a přehrávací ovládání zůstávají dostupné; Shuffle, multivýběr a ostatní akce nad seznamem čekají na dokončení. Lokální panel ukazuje načítání, dokončení nebo neúplný seznam po chybě.

Nahraný interpret má v ⋮ pod „Přehrát náhodně“ také „Spustit mix“, pokud pro něj YTM poskytne radioId. Používá pouze vlastní nahrávky daného interpreta (při jediném nahraném albu jen toto album), nikoli doporučení další podobné hudby. Zachová skutečné serverové pořadí, přejde do Fronty a cover vrátí původní detail/řazení. Respektuje pokračování či konec této fronty; běžné katalogové rádio se k ní nepřidává.

U nahrané skladby nabízí menu ⋮ otevření nahraného alba a interpreta, pokud jsou k dispozici jejich ID. V detailu interpreta se nabízí jen album, v detailu alba jen interpret, v hlavním seznamu a Frontě obojí. Přechod přepne i sekci Nahrané → Alba/Interpreti; Zpět obnoví původní sekci. U více interpretů lze vybrat konkrétního. Funguje také z Fronty a hledání v Nahraných; Zpět obnoví předchozí seznam a řazení bez zásahu do přehrávání.

Zvýraznění přehrávaného výskytu nyní v seznamech skladeb knihovny a Nahraných i u katalogového/nahraného interpreta sleduje jeho novou pozici po změně řazení. Fronta a audio pokračují beze změny; řazení nevyvolává automatické posunutí k přehrávané skladbě.

U nahraného interpreta lze skladby řadit A–Z (výchozí), Z–A nebo obnovit původní pořadí. Přepnutí je lokální a nemění již přehrávanou frontu. Nahraná alba si zachovávají pořadí skladeb.

Nahrané skladby a detaily nahraných alb/interpreta nyní v nabídce ⋮ mají „Přehrát náhodně“. Míchá se celý již načtený seznam lokálně se zachováním všech výskytů. Fronta ukáže nové pořadí; cover vrátí původní seznam. Celé nahrané seznamy lze také přidat jako další nebo na konec fronty; hlavní Nahrané skladby nově nabízejí uložení celého seznamu do playlistu. Jednotlivé skladby, multivýběr a uložení celých alb/interpreta využívají existující akce. Mix nahraných zdrojů není součástí tohoto kroku.

Seznamy s ID `RD…` nyní oběma cestami (Playlisty i Mixy pro vás) zobrazí jen úvodní náhled. Další blok stejného mixu se načte až při přiblížení ke konci přehrávané fronty, místo neomezeného stahování dopředu. Detail i Fronta označují dynamický mix. Pevné playlisty se dál načítají celé po blocích; dostupné ukončení pokračování se respektuje i u mixu.

Příprava náhodné fronty už nekopíruje celý původní seznam pro každou skladbu zvlášť. Cover a přesné výskyty zůstávají zachované; playlistové detaily se nyní také načítají po blocích. První část lze přehrát dvojklikem, další skladby přibývají i do téže fronty; akce nad celkem čekají na dokončení. Při obnově s dosud nepotvrzeným přesunem položek se nejprve načte úplný seznam kvůli porovnání pořadí.

„Přehrát náhodně“ v detailu playlistu i alba zamíchá všechny již načtené přehratelné výskyty lokálně, bez dalšího stahování seznamu a bez serverové náhodné fronty. Duplicity a původní pořadí prohlíženého playlistu zachovává. Stejné lokální zamíchání nyní používají také Oblíbené z hlavního menu po dokončení načítání celého seznamu, se zachováním coveru a řazení prohlížení. Interpret nyní také lokálně míchá svůj načtený seznam skladeb (i při spuštění z Alb/Singlů), bez dalšího stahování a limitu velikosti Mixu. „Zamíchat“ v aktuální frontě nyní také míchá lokálně všechny ostatní výskyty včetně ručně přidaných; aktuální skladba zůstává první, čas/pauza/Repeat pokračují. Funguje i u front bez playlistového ID; Mix/Rádio se nemění.

- Desktop GUI: **0.3.68-dev** (přidání/odebrání alba v knihovně; Michalem otestováno a přijato)
- Aktuální stav a předání projektu: [STATUS.md](STATUS.md). Základ včetně oprav z 2026-10-24 byl uživatelem přijat jako otestovaný.
- Aktuální stav bodů 1–11 a pořadí dalších prací do desktopové 1.0: [PLAN.md](PLAN.md).
- Porovnání funkcí původní CLI a dnešního GUI: [CLI-GUI.md](CLI-GUI.md) (audit 2026-10-26).
- GUI toolkit: PySide6 + QML
- FelisMusic CLI 1.0.0 je samostatný, zmrazený projekt / referenční implementace.

GUI používá existující FCM session z `~/.config/felismusic/`.

## Hotová datová vrstva

- start na Knihovně,
- Hledat,
- Knihovna: Playlisty, Skladby, Alba, Interpreti, Profily, Podcasty, Nahrané,
- Nahrané: Skladby / Alba / Interpreti,
- rozkliknutí kolekcí na skladby/epizody,
- Oblíbená hudba; menu ⋮ → Přehrát náhodně / Spustit mix (0.3.29 uživatelsky ověřeno),
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

## 0.3.3.4-dev – přednačítání další skladby

- Po spuštění skladby se na pozadí připraví jedna následující skladba z fronty. Při automatickém přechodu se použije hotový soubor z cache; pokud ještě příprava běží, přechod využije stejné stažení.
- Přednačítání nemění přehrávanou skladbu, neblokuje procházení knihovny a nezobrazuje načítací spinner místo aktivního přehrávače.
- Chyba přednačítání nepřeruší aktuální skladbu ani neposune frontu. Při přechodu se příprava zkusí znovu běžnou cestou.
- Při výběru jiné skladby se zruší nepotřebné přednačítání. Dosavadní chování přehrávané skladby během ručního přepínání zůstává zachované.
- Při zavření aplikace se příprava zruší; cache se odstraní až po skončení audio workeru. Přerušení během získávání metadat může počkat na dokončení právě probíhajícího síťového požadavku.
- Nejde o garantované gapless přehrávání. Krátká prodleva přepnutí výstupu může zůstat; první nepřipravená skladba stále vyžaduje stažení.

Offline ověření bez účtu a zvukového zařízení: `env/bin/python -m unittest discover -s tests -v`.

## 0.3.3.5-dev – ruční přepnutí skladby

- Kliknutí na skladbu a ruční Previous/Next nejdřív zastaví původní audio. Lokální výstup přejde do READY, aby se zachovalo směrování například na HDMI.
- Nově vybraný řádek během přípravy ukazuje `Připravuji…`; `Hraje` až po spuštění. Pauza a zastavený stav mají odpovídající označení.
- Nový výběr zneplatní předchozí přípravu, včetně rozpracovaného stahování. Neaktuální požadavek nesmí znovu spustit starou skladbu. Přerušení síťového požadavku na metadata může stále chvíli trvat.
- Automatický přechod po dohrání dál využívá přednačítání, bez dodatečného zastavování výstupu.

## 0.3.4-dev – Repeat

- Tlačítko vedle přehrávacích ovladačů cykluje `Opakovat: vyp.` → `Opakovat: vše` → `Opakovat: 1`. Aktivní režimy jsou barevně zvýrazněné; popisek po najetí vysvětlí jejich význam.
- Vypnuto: po dohrání poslední skladby se přehrávání zastaví.
- Vše: po poslední skladbě se pokračuje první; ruční Next/Previous na krajích seznamu také přejdou na opačný konec.
- Jedna: po dohrání se tatáž skladba spustí od začátku z cache. Ruční Next/Previous dál vybírají sousední skladbu, na hranicích nepřeskakují na opačný konec.
- Změna režimu nerestartuje skladbu, neruší pauzu a sama nespouští zastavené přehrávání. Režim platí i pro nově vybranou kolekci; po spuštění aplikace je vypnutý.
- Přednačítání respektuje režim: při opakování celého seznamu připraví i návrat na první skladbu, při opakování jedné nepřipravuje zbytečně další.
- Shuffle bude samostatný následující podkrok po ověření a commitu Repeat.

## 0.3.5-dev – Fronta + Info + Stop

- Položka **Fronta** v levé navigaci ukazuje skutečné pořadí přehrávání a pozici aktuální skladby, například `17 / 133`. Obsah je nezávislý na právě prohlížené kolekci a rozlišuje i duplicitní výskyty skladeb.
- Kliknutí na řádek fronty přepne skladbu ve stávající frontě, bez jejího nahrazení prohlíženým seznamem. Lze volně rolovat; při změně skladby se nová položka ukáže. Tlačítko **Na aktuální** ji přivede do záběru na požádání.
- **Info** vpravo nahoře otevře informace o aktuálně vybrané skladbě: název, interpret, album, délka, hodnocení, pozice ve frontě a název seznamu. Údaje sledují změnu aktuální skladby; chybějící metadata se zobrazí jako neuvedená či nezjištěná.
- Čtvercové tlačítko **Stop** zastaví přehrávání i rozpracovanou přípravu skladby. Zachová frontu, výběr a repeat; následné **Play spustí vybranou skladbu od začátku**, nikoli z poslední pozice. Pro pokračování z pozice slouží Pause/Play.
- Stop ponechává lokální výstup v READY kvůli zachování směrování zvuku.
- Kliknutí na cover dál vrací původní kolekci s její navigací. Samostatná Fronta je jiný pohled.
- Shuffle je podle zadání uživatele zatím odložený; tato verze implementuje krok 2 plánu.

## 0.3.6-dev – nabídka skladby a přidávání do fronty

- U přehratelných řádků je tlačítko „⋮“; stejnou nabídku otevře pravé tlačítko myši. Dostupné akce: **Přehrát jako další**, **Přidat na konec fronty**. Levé kliknutí na samotný řádek funguje dál jako dříve.
- „Jako další“ vloží kopii skladby hned za aktuální, „do fronty“ přidá kopii na konec. Opakované použití zachová i duplicity; při několika požadavcích „jako další“ bude bezprostředně další poslední zvolená položka.
- Vložení nezastaví přehrávání, neposune aktuální skladbu ani její čas a nezruší pauzu či Stop. Do prázdné fronty přidá první vybranou skladbu, ale automaticky ji nespustí.
- Během přípravy nové skladby jsou obě vkládací akce dočasně neaktivní. Samotné přehrátí jiné skladby zůstává dostupné.
- Počet položek se zobrazuje u Fronty v levé navigaci. Vložení používá změnu jednoho řádku modelu, nikoli reset celé fronty; přednačítání se přeplánuje, pokud se skutečně změnila následující skladba.
- Každý výskyt ve frontě si uchovává vlastní zdroj i navigaci. Ve smíšené frontě tak cover vrací album/playlist právě vybrané skladby, včetně původního řazení a výsledků hledání.
- Tato etapa zahrnuje skladby v seznamech a ve Frontě. Akce pro celé kolekce, odebrání a přesouvání budou samostatné podkroky.

## 0.3.7-dev – detail interpreta (podkrok 4a)

- Veřejný interpret z knihovny nebo hledání má části **Skladby**, **Alba**, **Singly a EP**. Při otevření se načte celý dostupný seznam skladeb; alba a singly/EP při prvním přepnutí na danou část. Pokud YTM poskytuje odkaz na úplný seznam, načte se automaticky. Jinak používáme všechny položky dodané serverem. Načtené části zůstávají uložené při přepínání; tlačítko Zobrazit vše již není potřeba.
- Výchozí řazení je **A–Z**, dále lze vybrat **Z–A** a **Původní pořadí YTM**. Alba a singly/EP lze řadit také **od nejnovějších / nejstarších**, položky bez roku zůstávají na konci. Každá část si během procházení pamatuje vlastní řazení; změna řazení nepřestavuje již přehrávanou frontu.
- Kliknutí na album nebo single/EP otevře skladby alba. **Zpět** vrací interpreta se zvolenou částí, řazením a již načtenými položkami; další návrat vede do knihovny nebo výsledků hledání.
- Prázdná část zůstane otevřená s vysvětlením. Procházení nemění přehrávanou frontu; kliknutí na skladbu ji spouští jako dosud. Cover přehrávače obnoví i části interpreta a návrat z jeho alba.
- Nahraný interpret používá nadále soukromý seznam skladeb; veřejnou diskografii mu nedohledáváme podle názvu.
- Podkrok uživatel otestoval a přijal. Hlavičky kolekcí a přechody skladba → album → interpret budou pokračováním 4b/4c; Shuffle a Mix zůstávají samostatně plánované.

## 0.3.8-dev – Mix ze skladby (podkrok 5a)

- Nabídka „⋮“ / pravé tlačítko u veřejné skladby nebo videa obsahuje **Spustit mix**. Používá stejné vytváření rádia jako CLI; nahraným soukromým skladbám a epizodám tuto akci nenabízíme.
- Po úspěšném načtení nahradí dosavadní frontu mixem začínajícím vybranou skladbou a otevře **Frontu** s názvem **Mix: název skladby**. Pokud vybraná skladba již hraje nebo je pozastavená, pokračuje ze stejného místa a zachová pauzu. Jiná nebo zastavená skladba se spustí od začátku.
- Během vytváření se dosavadní fronta ani označení aktuální skladby nemění. Chyba ponechá původní přehrávání. Stop, jiný výběr nebo vložení položky do fronty během čekání zneplatní opožděný výsledek mixu.
- Doporučení jsou z YTM, nepřehratelné položky a duplicitní videoId se filtrují. Od 0.3.21 se při vytvoření nového mixu repeat vypíná; přednačítání následující skladby funguje dál. Cover u skladeb mixu otevře jeho aktuální frontu.
- První samostatně testovatelný podkrok obsahuje **jeden blok doporučení**. Průběžné doplňování je následující podkrok 5b, mixy interpreta/kolekce pak 5c.

- Podkrok 5a uživatel otestoval na skutečném přehrávání a přijal 2026-10-25.

## 0.3.9-dev – knihovna skladeb (první část 6a)

- Při otevření nabídky veřejné skladby/videa se na pozadí načte skutečné členství v knihovně. Knihovní položka je zpočátku skrytá; pouze při dostupné akci se na konci menu objeví **Přidat do knihovny** nebo **Odebrat z knihovny**. Ostatní řádky menu se tím neposunou. Kliknutí provede změnu bez dalšího okna.
- Během zjišťování stavu zůstávají **Přehrát jako další**, **Přidat na konec fronty** a **Spustit mix** aktivní a funkční. Čtení knihovny běží odděleně od hlavních požadavků na YTM, nevyvolává celkové načítání ani nepřerušuje audio.
- Zavření menu nebo otevření nabídky jiné skladby zneplatní opožděnou odpověď. Každé otevření zjišťuje stav znovu. Pokud YTM ovládání neposkytne nebo se stav nepodaří načíst, položka zůstane skrytá. Soukromé uploady a epizody tuto nabídku nemají.
- Skladby v otevřeném veřejném albu přebírají jeho známé ID, pokud nemají vlastní konkrétní ID alba. Údaj zůstává zachovaný i ve frontě a umožňuje náhradní zjištění knihovního stavu přes album.
- Po změně znovu načítáme stav z YTM. Teprve ověřená změna aktualizuje knihovnu. Případná chyba nebo neověřený výsledek se zobrazí; pro nový stav stačí znovu otevřít menu skladby.
- Změna knihovny nepřerušuje přehrávání, nemění hodnocení a neodebírá skladby z přehrávací fronty. Návrat přes cover respektuje změněný obsah knihovny.
- Zatím skladby; přidávání/odebírání alb a playlistů, odběry interpretů a kopírování odkazů jsou další samostatné podkroky.

- Finální podobu menu a chování skladeb z alb uživatel ověřil proti webovému YTM a přijal 2026-10-25.

## 0.3.10-dev – uložení skladby do playlistu (první část 7a)

- Nabídka skladby obsahuje **Přidat do playlistu…**. Dialog nabídne vlastní playlisty účtu; před zápisem se znovu ověří, že je vybraný playlist vlastní a upravitelný. Používá se přesné videoId vybrané skladby, také u uploadů; změna přehrávané skladby výběr v dialogu nepřesměruje.
- Duplicity jsou ve výchozím stavu vypnuté: pokud už playlist obsahuje stejné videoId, nic nepřidáme a oznámíme to. **Povolit další výskyt stejné skladby** dovolí další kopii.
- **Nový soukromý playlist** vytvoří playlist se zadaným názvem rovnou s vybranou skladbou. Popis a další viditelnosti patří do navazujících úprav údajů playlistu.
- Po potvrzeném zápisu ověřujeme obsah až třemi kontrolními načteními s krátkým odstupem. Pokud obsah stále není dostupný, zpráva rozliší potvrzené vytvoření/přidání od neověřeného obsahu. **Ověřit znovu** opakuje pouze čtení; nevytvoří další playlist ani znovu nepřidá skladbu. Chybová zpráva nezobrazuje dlouhé technické odpovědi YTM. Při nepotvrzeném zápisu zůstává další odeslání blokované do nového otevření.
- Po ověřeném úspěchu se ukládací okno samo zavře; zpráva zůstane ve stavové liště. Nepovolená duplicita zobrazí výrazné oznámení Duplicitní skladba a jediné tlačítko OK. Chyby a neověřený obsah ponechají okno otevřené, případně s Ověřit znovu; úspěšné dodatečné ověření ho zavře také.
- Uložení nepřeruší audio, nemění přehrávací frontu, pozici ani hodnocení. Právě otevřený cílový playlist zobrazí ověřený obsah; přehrávací fronta zůstává samostatná.
- Tato část zatím ukládá jednotlivou skladbu. Celé kolekce, přejmenování, popis/viditelnost, odebrání/přesun položek a smazání vlastního playlistu budou samostatné podkroky.

- Uživatel 2026-10-25 potvrdil celý tento podkrok včetně ověřování a finálního chování dialogu. Playlisty mohou mít stejný název; operace používají jejich jedinečná ID.

## 0.3.11-dev – uložení otevřeného seznamu do playlistu (druhá část 7a)

- V detailu alba/playlistu a v části Skladby u interpreta je **Přidat seznam do playlistu…**. Uloží přehratelné skladby právě zobrazeného seznamu v jeho pořadí; dialog ukazuje počet vybraných skladeb. Na části Alba/Singly interpreta se akce nezobrazuje.
- Playlisty načítáme celé s `limit=None`. U ostatních zdrojů se ukládá dostupný zobrazený obsah; výběr se zachytí při otevření ukládání a další procházení ho nezmění.
- Bez povolených duplicit se vynechají videoId již přítomná v cíli i opakování uvnitř výběru, pořadí zbývajících skladeb se zachová. S volbou **Povolit opakované výskyty skladeb** se přidá každý výskyt. Pokud není co přidat, zobrazí se potvrzení duplicit přes OK.
- Nový soukromý playlist obsahuje vybraný seznam bez duplicit a v zobrazeném pořadí. Po uložení se ověřuje počet výskytů každého přidávaného videoId; neúplný výsledek nenahlásíme jako plně ověřený a Ověřit znovu stále pouze čte.
- Audio a přehrávací fronta se nemění. Ověřený úspěch okno zavře; stavová zpráva u kolekcí uvádí počet přidaných skladeb a vynechaných duplicit.
- Další podkroky: prázdný playlist, úpravy názvu/popisu/viditelnosti, odebírání/přesuny a smazání vlastních playlistů.

- Druhou část 7a uživatel otestoval a přijal 2026-10-25, včetně dostupnosti u nahraných seznamů.

## 0.3.12-dev – kompaktní hlavičky kolekcí

- Detail alba, playlistu, interpreta a mixu sdílí jednu kompaktní hlavičku: **Zpět**, název a počet položek, vpravo **⋮** pro akce celé kolekce. Dlouhý název se zkrátí, ovladače zůstávají viditelné.
- **Přidat seznam do playlistu…** je nyní uvnitř této nabídky; samostatné velké tlačítko pod hlavičkou je odstraněné. Nabídka se zobrazí jen tam, kde je dostupná zapojená akce. Nabídky u jednotlivých skladeb zůstávají samostatné.
- U interpreta jsou **Skladby / Alba / Singly a EP** a řazení vedle sebe; při nedostatku šířky se řazení zalomí pod záložky. Seznam tak dostává více svislého místa.
- Jde o úpravu rozložení; ukládání, pořadí/duplicity, přehrávání, fronta i návraty fungují stejně. Další metadata hlaviček a akce kolekcí zůstávají navazujícími podkroky.

- Kompaktní hlavičky a přesun akcí do menu uživatel otestoval a přijal 2026-10-25.

## 0.3.13-dev – nový prázdný playlist (první část 7b)

- V přehledu **Knihovna → Playlisty** je nabídka **⋮ → Nový playlist…**. Samostatný dialog vytvoří soukromý playlist se zadaným názvem a bez skladeb, nezávisle na přehrávání i dříve vybraných skladbách.
- Prázdný název a znaky < > se odmítnou; stejné názvy více playlistů jsou povolené. Enter v názvu provede stejnou akci jako Vytvořit.
- Po potvrzeném vytvoření se dialog zavře a přehled playlistů se znovu načte. Potvrzený nový playlist zůstane viditelný i při opožděné odpovědi knihovny YTM; po jeho načtení ze serveru se karta nahradí skutečnými údaji podle ID, bez duplicity. Nový playlist lze otevřít i s nulovým počtem skladeb a vrátit se přes Zpět.
- Při nepotvrzeném výsledku zůstane stručná zpráva a opakované odeslání je blokované do nového otevření, aby nevznikla další kopie. Zavření formuláře bez odeslání nic nevytvoří.
- Název/popisy/viditelnost existujících playlistů, další viditelnosti nového playlistu, odebrání/přesouvání položek a smazání jsou následující podkroky.

## 0.3.14-dev – úprava údajů vlastního playlistu (další část 7b)

- V otevřeném vlastním playlistu je **⋮ → Upravit playlist…**, také pokud nemá žádné skladby. Cizí playlist tuto akci nenabízí.
- Formulář načte aktuální název, popis a viditelnost; lze zvolit Soukromý, Neveřejný (přes odkaz) a Veřejný. Popis lze i úplně vymazat. Název musí být neprázdný; znaky < > nejsou povolené.
- Před uložením se znovu ověřuje vlastnictví přesné identity playlistu. Po potvrzení zápisu YTM se formulář zavře a aktualizuje název detailu i již načtené karty. Obsah, fronta ani audio se tím nepřestavují.
- Nepotvrzený zápis ponechá stručné oznámení a zablokuje další odeslání z téhož formuláře; další pokus až po jeho zavření a novém načtení údajů. Zrušení formuláře nic nezapisuje.
- Vytvoření prázdného playlistu zůstává soukromé; další viditelnost lze nastavit následnou úpravou. Odebrání/přesouvání skladeb a smazání playlistu následují samostatně.

## 0.3.15-dev – viditelnost při vytvoření playlistu (dokončení 7b)

- Všechny způsoby vytvoření nového playlistu nabízejí **Soukromý / Neveřejný (přístup přes odkaz) / Veřejný**: prázdný playlist, playlist ze skladby i z celé kolekce.
- Každé nové otevření formuláře začíná volbou Soukromý. Vybraná viditelnost se odešle přímo při vytvoření v jednom požadavku se skladbami, pokud jsou vybrané.
- V režimu přidávání do existujícího playlistu je volba skrytá a jeho viditelnost se nemění. Následná úprava viditelnosti zůstává dostupná přes Upravit playlist….

## 0.3.16-dev – odebrání výskytu skladby z playlistu (první část 7c)

- V detailu vlastního playlistu nabízí menu skladby **Odebrat z tohoto playlistu**. Akce vyžaduje skutečné videoId i setVideoId konkrétního výskytu; dvě stejné skladby se nerozlišují podle názvu ani samotného videoId.
- Před odebráním se znovu načte playlist, ověří vlastnictví a shoda výskytu. Pokud už položka chybí, pouze se obnoví seznam. Chyba ověření nic nezapisuje; nepotvrzený zápis zobrazí stručnou zprávu s pokynem ke kontrole obsahu.
- Potvrzené odebrání aktualizuje detail. Při běžném odstranění jediného řádku zachovává rolování; opožděná odpověď YTM odebraný výskyt nevrátí do seznamu. Poslední skladbu lze odebrat a ponechat prázdný playlist.
- Fronta se po potvrzeném odebrání synchronizuje pro původní výskyty převzaté z tohoto playlistu: čekající položka zmizí hned, právě hrající či pozastavená může dohrát a pak se vyřadí. Ručně přidané skladby (i kopie stejného výskytu) a fronta jiného playlistu zůstávají zachované. Aktuální čas a audio se při synchronizaci neresetují.
- Odebraný aktuální výskyt se znovu neopakuje ani v Repeat One; po dohrání pokračuje další skladba, Repeat All dovoluje návrat na začátek zbývající fronty. Next/Previous, výběr jiné položky a Stop ho také vyřadí při opuštění. Odebraná zastavená položka zmizí ihned. Přednačítání se přesměruje na skutečného nástupce.
- Návrat přes cover ukáže upravený playlist a zbývající výskyty mají správné pozice. Odebrání z knihovny je samostatná akce; v samotné Frontě se odebrání z uloženého playlistu nenabízí.
- Změna pořadí skladeb je další samostatná část 7c; smazání celého playlistu následuje v 7d.

## 0.3.17-dev – výběr skladeb a společné akce

- V seznamech skladeb jeden klik pouze vybere řádek; **dvojklik nebo Enter** spustí přehrávání. Enter přehraje naposledy vybraný řádek, pokud je stále součástí výběru. Přehrávání nadále vychází z celého zdrojového seznamu, ve Frontě se vybírá v existující frontě. Alba, interpreti a ostatní kolekce se dál otevírají jedním klikem.
- **Ctrl+klik** přidává/odebírá jednotlivé řádky, **Shift+klik** vybírá rozsah, **Ctrl+Shift+klik** rozsah přidává. **Ctrl+A** vybere všechny skladby v aktivním seznamu, **Escape** nebo Zrušit výběr výběr zruší. Dvě stejné skladby jsou dva samostatné řádky.
- Vybrané řádky mají vlastní zvýraznění, nezávislé na značce právě přehrávané skladby. Při výběru alespoň dvou skladeb je nad přehrávačem počet Vybráno a nabídka Akce ⋮: **Přehrát jako další / Přidat na konec fronty / Přidat do playlistu…**.
- Pravé tlačítko nebo ⋮ na již vybraném řádku zachová celý výběr; na jiném řádku vybere jen tento řádek. Pro skupinu jsou dostupné společné akce, jednotlivé Mix/knihovna/odebrání se nenabízejí. Hromadné odebrání je další samostatný podkrok.
- Dávka do fronty zachovává zobrazené pořadí a všechny vybrané výskyty; nepřeruší současné audio. Do prázdné fronty se vloží bez automatického spuštění. Uložení do playlistu používá dosavadní formulář a volby viditelnosti/duplicit.
- Při změně stránky, otevření detailu a strukturální změně zdrojového modelu (obnovení, řazení, vložení/odebrání řádků) se výběr zruší; změna hodnocení ani pravidelné aktualizace přehrávače ho neruší. Otevřený ukládací formulář už drží vlastní zachycené položky.

- Po úspěšné hromadné akci se původní výběr zruší a lišta zmizí. U uložení do playlistu až po ověřeném úspěchu (také při Ověřit znovu); chyba, neověřený obsah nebo zavření formuláře bez uložení výběr zachová. Dokončení staršího formuláře nezruší později vytvořený výběr.

## 0.3.18-dev – změna pořadí skladeb ve vlastním playlistu (druhá část 7c)

- Menu jedné skladby ve vlastním playlistu nabízí **Posunout nahoru / Posunout dolů**. U první/poslední zobrazené skladby je příslušný směr neaktivní. Cizí playlisty a hromadný výběr tyto akce nenabízejí.
- Přesun pracuje s videoId/setVideoId vybraného výskytu i souseda. Před zápisem znovu načte playlist a ověří vlastnictví, identity a jejich sousedství. Pořadí se zapíše přes edit_playlist(moveItem=…), včetně přesunu na konec; nedostupné skryté řádky se nezaměňují za viditelné pozice.
- Po potvrzení YTM se přesune řádek i v aplikaci; při běžném přesunu se model neresetuje. Potvrzené operace a jejich výsledná pořadí překlenou opožděné odpovědi serveru. Už obsažené operace se neaplikují podruhé; po dorovnání se pomocná informace zahodí.
- Všechny původní výskyty tohoto playlistu ve frontě se seřadí podle nového pořadí, také před aktuální skladbou a při zastaveném přehrávání. Právě hrající/pozastavená/zastavená skladba se sleduje podle identity výskytu a dostane nový index; audio, čas ani hodnocení se neresetují. Pozice ručně vložených skladeb zůstávají zachované. Přednačítání se přesměruje na skutečného nástupce a návrat přes cover obnoví nové pořadí playlistu.
- Pokud nelze před zápisem potvrdit výskyty/souseda/vlastnictví, nic se nezapíše. Nepotvrzený zápis zobrazí stručnou zprávu s pokynem k obnovení a kontrole pořadí.

## 0.3.28-dev – volitelný debug a Fronta po náhodném spuštění

- Normálně spusť `./run-gui.sh`: podrobná diagnostika je standardně vypnutá. Základní dosavadní chybová hlášení zůstávají dostupná.
- Pro diagnostiku spusť `./run-gui.sh --debug`. Přepínač se zpracuje před argumenty Qt a zapne `[FelisMusic diag]` pro celý běh. Nadále funguje `FELISMUSIC_DIAGNOSTICS=1`; explicitní `--debug` má přednost před hodnotou 0.
- **⋮ alba/playlistu → Přehrát náhodně** po úspěšném načtení otevře Frontu stejně jako akce interpreta a Mix. Navigační kontext původní kolekce se zachytí ještě před přechodem; cover ji dál obnoví v původním řazení. Neúspěšný či zneplatněný požadavek do Fronty nepřepne.
- Prošlo 265 offline testů. Skutečný uživatelský test čeká; příčina dřívějšího přechodného zpomalení není prokázaná.

## 0.3.27-dev – diagnostika pomalého načítání

Po hlášených timeoutech a HTTP 503 audia a dlouhém busy při načítání playlistu je před přijetím B3 doplněné měření. Tato etapa nemění timeouty, počty opakování, výběr formátu, směrování serverů ani práci s přihlášením. Dlouhé načítání nyní není nově rušitelné; nejdřív potřebujeme zachytit příčinu.

Spuštění s uložením výstupu:

```bash
cd ~/src/FelisMusic && ./run-gui.sh --debug 2>&1 | tee /tmp/felismusic-diagnostic.log
```

Řádky `[FelisMusic diag]` obsahují JSON s relativním časem `t`, ID úlohy `job`, názvem `task` a událostí `event`:

- `job.queued` / `job.start`: `queue_s` ukáže čekání na pracovní vlákno. `audio.play` a `audio.prefetch` se odlišují; API akce mají např. `api.detail`.
- `http.begin` / `http.end` / `http.error`: skutečné požadavky stávající session ytmusicapi, bezpečný endpoint/hostname, původní timeout, HTTP stav či typ chyby a doba požadavku. Nezapisují se těla, query, cookies nebo přihlašovací hlavičky.
- `audio.metadata_*`, `audio.js_challenge`, `audio.site_wait`: fáze yt-dlp; doba od začátku přípravy a případná oznámená čekací doba YouTube. Známé události se rozpoznávají z loggeru, jejich nepřítomnost sama nedokazuje vynechání daného kroku.
- `audio.cdn_http_begin` / `_headers` / `_error`: hostname audio serveru i před prvními daty. Čas `_headers` měří získání odpovědi, nikoli dokončení přenosu celého souboru.
- `audio.first_data` / `audio.download_progress` / `audio.download_finished`: přijaté bajty/rychlost, hostname a čas. `transfer_s` běží od prvního progress callbacku, nezahrnuje čekání před prvním chunkem; sledovat také předchozí HTTP události a `prepare_s`. Progress nejvýše jednou za pět sekund, navíc první a poslední zpráva.
- `audio.postprocess_*`, `audio.ready`, `audio.cache_hit`, `audio.output_begin` / `audio.output_ready`: dokončení souboru, cache a spuštění GStreameru. `yt.warning` / `yt.error` zobrazují bezpečné kategorie, HTTP kód a dostupný hostname; původní texty s možnými citlivými URL se nepřebírají.

V původní 0.3.27 byla diagnostika zapnutá automaticky; od 0.3.28 se zapíná přepínačem `--debug` a standardně je vypnutá. CLI volání převzatého jádra bez diagnostického objektu dál funguje původním způsobem. Prošlo 262 offline testů včetně zachování parametrů a kontroly, že do nových diagnostických řádků neunikají citlivé údaje; GUI ověřeno při 1280×800/900×600. Skutečná příčina pomalosti zatím nepotvrzená.

## 0.3.26-dev – Mix celého alba a playlistu (B3, čeká na uživatelský test)

- Otevři album nebo playlist a v **⋮ v hlavičce → Spustit mix** vytvoř doporučení podle celé kolekce. Playlist používá `RDAMPL` + playlistId, album `RDAMPL` + audioPlaylistId. Nejde o mix podle první skladby. Stávající **Přehrát náhodně** zůstává samostatnou akcí.
- Mix se otevře ve Frontě a průběžně pokračuje pomocí B1. Cover vrací skutečnou Frontu; původní obsah/pořadí alba či playlistu se nemění. Nové přehrávání vypne Repeat. Do úspěšné odpovědi zůstávají původní audio a fronta; při chybě se zachovají.
- U prázdné kolekce nebo alba bez audioPlaylistId je akce neaktivní; uploady ji nenabízejí. Normalizuje se případný prefix VL a již přítomný RDAMPL se nezdvojuje. Opožděné výsledky po Stop/novém přehrávání/editaci fronty/opuštění detailu se ignorují.
- Prošlo 253 offline testů a skutečné QML klikání při 1280×800/900×600: album i playlist, ID, Fronta/cover/Repeat, pokračování do nového bloku a neaktivní nedostupné zdroje. Skutečný účet/YTM čeká na uživatelský test. Přehled existujících „Mixů pro vás“ se tímto nemění.

## 0.3.25-dev – Mix a Náhodně interpreta (B2, uživatelsky přijato)

- Otevři interpreta a v **⋮ v jeho hlavičce** zvol **Spustit mix** nebo **Přehrát náhodně**. Nabídka funguje na kartách Skladby / Alba / Singly a EP; obě akce vždy cílí na interpreta jako celek, nikoli na právě zobrazenou část katalogu.
- Používá se převzaté `artist_action_queue`: přímo `radioId` či `shuffleId` z YTM, nikoli rádio první skladby ani místní náhodné řazení. Chybí-li některé ID, odpovídající akce je neaktivní. Menu zůstává dostupné i při prázdné katalogové části.
- Výsledek se otevře jako skutečná Fronta. Mix je průběžně doplňovaný přes B1; Náhodně je konečná fronta. Cover u obou vrací Frontu, která obsahuje skutečně vrácený výběr YTM. Nové přehrávání vypne Repeat; původní audio/fronta zůstávají až do úspěšné odpovědi.
- Při chybě se původní přehrávání zachová. Stop, nový výběr, zásah do fronty či opuštění detailu zneplatní starou odpověď. Nová akce interpreta má přednost před starým automatickým doplňováním.
- Prošlo 241 offline testů a QML kontroly při 1280×800 a 900×600. Uživatel přijal Mix i Náhodně interpreta a ověřil shodu výsledků s webovým YTM. Opakované spuštění může vrátit stejnou frontu; interval změny není doložený. Mix celého alba/playlistu přes ⋮ navazuje v 0.3.26-dev / B3.

## 0.3.24-dev – průběžné pokračování Mixu ze skladby (B1, uživatelsky přijato)

- Spusť **menu skladby → Spustit mix**. Při pěti nebo méně skladbách zbývajících za aktuální položkou se na pozadí připojí další doporučení z YTM. Průběžně přibývají do stejné Fronty; nepřerušují audio, nemění Repeat/pauzu a nepřitahují seznam zpět na aktuální řádek.
- Používá převzatou logiku CLI: zdrojem dalšího bloku je poslední skladba fronty. Nepřehratelné skladby, chybějící ID, již přítomné skladby i duplicity uvnitř odpovědi se vyřadí. Přednačítání naváže na nového nástupce.
- Po chybě nebo odpovědi bez nových skladeb následuje další pokus nejdříve za 30 sekund, bez chybového dialogu. Pokud mezitím fronta dohraje, po úspěšném doplnění naváže. **Stop** zruší toto automatické pokračování a funguje i během čekání po dohrání.
- Nové přehrávání/Mix/Shuffle a změny obsahu fronty zneplatní starou odpověď. Procházení, pauza a běžný přechod na další skladbu ve stejném mixu doplňování neruší. Účetní API požadavky jsou řazené za sebou, transport zůstává dostupný.
- Prošlo 228 offline testů a QML kontroly při 1280×800/900×600. Uživatel ověřil dva navazující bloky i nárůst počtu v GUI/logu (186 → 276 skladeb). Mix playlistu/alba přes ⋮ je další samostatná etapa; akce interpreta navazují v 0.3.25-dev.

## 0.3.23-dev – zamíchání aktuální fronty (A2, uživatelsky přijato)

- Ve **Frontě → Zamíchat** se vyžádá YTM Shuffle původního playlistu/alba. Funguje pro normálně i náhodně spuštěnou kolekci s podporovaným zdrojovým ID. Fronta bez takového ID, uploady, rádio a nepodporované kolekce mají tlačítko neaktivní.
- Aktuální skladba se přesune na první místo a pokračuje beze změny času, hlasitosti, hodnocení a Repeat; pauza i Stop zůstávají zachované. Stejně jako v CLI mohou za aktuální skladbou znovu být dříve přehrané skladby kolekce.
- Existující výskyty se neztrácejí a nepřibývají další: kolekční část přebírá dostupné pořadí YTM, nevrácené položky zůstávají za ní a ručně vložené položky se lokálně promíchají a vloží do náhodných míst mezi ně. Přesné duplicity a původ každé položky se zachovají.
- Další skladba se přednačte podle nového pořadí. Cover dál vrací příslušnou kolekci. Změna pořadí uloženého playlistu nepřepíše náhodné pořadí fronty; odebrání známého konkrétního výskytu se dál promítá.
- Samotné přidání respektuje „jako další“/„na konec“; ruční položky se náhodně přemístí až stisknutím **Zamíchat**. Náhoda může někdy ponechat stejnou pozici.
- Nový stisk znovu zamíchá; nejde o přepínač pro obnovení původního pořadí. Chyba či zneplatněný požadavek ponechá původní frontu a audio.

## 0.3.21-dev – Repeat patří k aktuální frontě (uživatelsky přijato)

- Spuštění nové fronty dvojklikem/Enter ze seznamu skladeb, přes **Přehrát náhodně** či vytvořením nového rádia přepne Repeat na **Vypnuto**. Platí i pro nové spuštění téže kolekce.
- Výběr skladby přímo ve Frontě, Next/Previous, Pause/Play, Stop/Play, procházení a návrat přes cover nastavení zachovají. Stejně tak vložení skladeb do existující fronty.
- Neúspěšný nebo zneplatněný požadavek na Shuffle/Rádio ponechá původní Repeat i frontu. Při pouhém otevření jiného alba se Repeat ještě nemění.

## 0.3.20-dev – náhodné spuštění playlistu/alba (A1, uživatelsky přijato)

- Otevři playlist nebo album a v menu hlavičky **⋮ → Přehrát náhodně** vyžádej náhodné pořadí od YTM. U alba se používá jeho audioPlaylistId. Skutečné vrácené pořadí najdeš ve Frontě; uložený playlist se nemění.
- Next/Previous, Repeat a načítání další skladby předem respektují tuto frontu. Cover vrátí původní kolekci a její navigaci.
- Nepodporované kolekce a alba bez potřebného ID mají akci neaktivní. Uploady ji nenabízejí. Chyba YTM ponechá původní přehrávání/frontu.
- Automaticky ověřeno 192 offline testy a QML klikáním při 1280×800/900×600. Uživatel potvrdil skutečné přehrávání playlistu/alba, Repeat, přechody a návrat přes cover; commit `2c51536`. Zamíchání běžící fronty bez přerušení aktuální skladby přijde samostatně v A2.

## 0.3.19-dev – smazání vlastního playlistu (7d)

- V menu otevřeného vlastního playlistu je **⋮ → Smazat playlist…**, také u prázdného playlistu. Cizí a známé automatické playlisty tuto akci nenabízejí.
- Před potvrzením se načte aktuální název a vlastnictví. Dialog upozorní na smazání celého playlistu z YTM; **Zrušit** nebo Escape nic nezapisuje. Teprve **Smazat playlist** provede akci podle zachyceného jedinečného ID, takže stejně pojmenované playlisty neovlivní.
- Bezprostředně před zápisem se znovu ověří vlastnictví i potvrzený název. Pokud se název mezitím změnil, je nutné otevřít nové potvrzení. Během mazání se další odeslání i zavření zablokuje.
- Po přímém potvrzení YTM nebo následném ověření smazání dialog zmizí, karta se odebere a otevřený smazaný detail se vrátí do Knihovna → Playlisty. Opožděný přehled nebo hledání smazanou kartu během této session nevrátí. Pokud odpověď neobsahuje očekávané potvrzení, následuje omezené čtecí ověření zmizení konkrétního ID z úplné knihovny, kde před zápisem bylo. Neověřený stav zůstane jako neutrální zpráva s tlačítkem **Ověřit znovu**, které už mazání neodesílá. Chyba sítě nebo nečitelný přehled nejsou důkazem smazání.
- Přehrávání, čas, fronta a její pořadí zůstávají zachované. Skladby z již smazaného zdroje odkazují na samotnou Frontu, takže kliknutí na cover neotevře neexistující playlist a přehrávání může pokračovat.

### Postupné načítání velkých seznamů – P1 (0.3.30-dev)

Oblíbená hudba zobrazí první stránku a zbytek doplní na pozadí bez blokování celé aplikace a bez původního limitu 2000. Do dokončení jsou akce a řazení vypnuté; stav je vidět u počtu položek. Po chybě lze načítání zopakovat novým otevřením Oblíbené hudby. Původní řazení A–Z/Z–A se použije až po dokončení. V této etapě se nemění rychlost přípravy Shuffle ani načítání ostatních kolekcí; ty následují samostatně.

Stav nad Oblíbenými: malé kolečko a „Načítám další skladby…“, po dokončení čtyři sekundy „Vše načteno · X skladeb“. Panel neblokuje navigaci ani ovládání hrající hudby.

### Přehrávání před dokončením načítání – P2a (0.3.32-dev)

Během kolečka nad Oblíbenými už lze přehrát viditelnou skladbu dvojklikem nebo výběrem a Enterem. Další stránky rozšíří i tuto frontu; hrající skladba pokračuje. Na dočasném konci fronta počká na další blok, Stop čekání zruší. Stav načítání či neúplnosti je vidět ve Frontě. Případné A–Z se po dokončení projeví v prohlíženém seznamu; spuštěná fronta si ponechá pořadí YTM. Ostatní akce a řazení jsou do dokončení vypnuté. Rychlejší příprava náhodné fronty následuje samostatně.

### Rychlý start Přehrát náhodně – P2b (0.3.33-dev)

Náhodné přehrávání playlistu, alba, Oblíbených a interpreta připravuje audio už z první stránky serverové fronty; další stránky doplní na pozadí se zachováním stejného pořadí YTM. Ve Frontě je vidět doplňování, případné čekání nebo neúplnost po chybě. Stop zruší automatické pokračování, pozdější bloky nepřerušují audio. Cover vrací původní kolekci. Opětovné zamíchání existující fronty je během doplňování vypnuté. Dostupnost akcí nad dosud nenačtenou zdrojovou kolekcí se zatím nemění; zejména u Oblíbených se menu stále aktivuje po načtení seznamu. Příprava audio souboru zůstává samostatnou prodlevou.

Při hlášce „Seznam není úplný“ v náhodné frontě spusť aplikaci s `--debug`. Verze 0.3.34 rozlišuje chybu požadavku, parsování a opakované pokračování pomocí bezpečných počtů a důvodu; samotné načítání zatím nemění.

### Porovnání původního a postupného Shuffle

`env/bin/python tools/compare_shuffle.py --limit 1635` nabídne výběr playlistu z knihovny. Zvol stejný playlist jako při chybě a počet uprav podle zdroje v GUI. Nástroj provede původní načtení a potom jeho odpovědi porovná s novým adaptérem pouze v paměti; druhé náhodné serverové pořadí se nevytváří. Vypíše souhrn položek/různých skladeb a shodu společného začátku. Nepřehrává audio ani nemění playlisty; odpovědi a pokračovací tokeny neukládá na disk. Pro nynější diagnostiku neposuzovat úplnost jen podle celkového počtu položek.
