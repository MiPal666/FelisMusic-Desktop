# FelisMusic Desktop – aktuální plán do 1.0

**0.3.66-dev / Plán 4 – údaje v hlavičkách alb a playlistů:** kompaktní hlavička má dostupný obal, interpreta/autora, skutečný rok, počet a délku. Platí také pro nahraná alba podle dostupných údajů. Při načítání rozlišuje načteno/celkem, při nedostupných skladbách dostupné/celkem. Přesný součet délek až po kompletním načtení a při známé délce všech zobrazených řádků; jinak pouze původní textová délka od YTM, pokud existuje. Číselný duration_seconds z prvního bloku se nepoužívá jako délka celku. Metadata zachována při coveru/navigaci i při přesunu/odebrání v playlistu. 533 offline testů a čtyři QML kontroly prošly. Michal skutečným testem přijal 2026-10-29; plán 4 hotový a připravený ke commitu. Hodnocení uložené v 06577cf.

**0.3.65-dev / Plán 3b – hodnocení vybrané skladby:** přes ⋮ → Hodnocení… lze výslovně nastavit Oblíbená / Neoblíbená / Zrušit hodnocení bez spuštění skladby. Známý stav označen ✓; změna z menu až po úspěšné odpovědi YTM, při chybě původní data zůstávají. Sdílený zápis s horními tlačítky serializuje akce a chrání proti starým rating probes i změně aktuální skladby. Propagace do duplicit/fronty/modelů/navigačních i aktivních stránkovaných snapshotů, aktualizace známého seznamu Oblíbených stávající cestou. 525 offline testů a dvě QML kontroly prošly. Michal skutečným testem přijal 2026-10-29; uložené v 06577cf. Plán 3 uzavřený, následuje plán 4 – údaje v hlavičkách. Informace 0.3.64-dev přijaté a uložené v f169537.

**0.3.64-dev / Plán 3a – Informace o libovolné skladbě:** přes ⋮ → Informace lze otevřít dostupná metadata konkrétního výskytu bez spuštění skladby, API dotazu nebo změny fronty. Sdílený dialog zobrazí název, interpreta, album, délku, známé hodnocení a obal; pouze u položky z Fronty také její pozici/název fronty při otevření. Menu drží snapshot vybrané skladby, horní Info nadále živě sleduje aktuální přehrávání. Chybějící data se neodhadují. 516 offline testů a dvě QML kontroly prošly; Michal skutečným testem přijal 2026-10-29. Hodnocení přes menu zatím není součástí tohoto podkroku. Přesuny Fronty přijaté a uložené v cb77085 + 64e4e1a.

**0.3.63-dev / Plán 2b – přesouvání přímo ve Frontě:** menu konkrétního výskytu má Posunout nahoru / Posunout dolů. Přesun nemění zdrojový playlist ani audio, čas, pauzu/Stop, hodnocení, Repeat či Shuffle/Mix; aktuální skladba a její zdrojový index zůstávají zachované. Přednačítání reaguje na nového nástupce, pozdější editace pořadí zdrojového playlistu nepřepíše ruční frontu. Přesun dostupných řádků funguje během doplňování; během přechodu přehrávání nebo čekání na nové skladby je neaktivní. 512 offline testů a dvě QML kontroly prošly. Michal skutečným testem přijal 2026-10-29. Implementace přesunů již v cb77085; test přesunů a zápis přijetí uložené v 64e4e1a. Plán 2 hotový, následuje plán 3 – Info/hodnocení jiné skladby.

**0.3.62-dev – po spuštění playlistu zobrazit Frontu:** běžné spuštění skladby z detailu playlistu (dvojklik i Enter) nyní přepne na Frontu. Nejdřív se zachytí původní navigační kontext; cover obnoví playlist i konkrétní výskyt. Pouhé enqueue nepřepíná zobrazení. Čtyři QML scénáře 900×600/1280×800 × dvojklik/Enter prošly bez varování, včetně coveru, duplicit a regrese běžné knihovní skladby. Michal skutečným testem přijal 2026-10-29. Odebrání z Fronty 0.3.61-dev rovněž přijato; oba podkroky uložené jako 76444a3.

**0.3.61-dev / Plán 2a – odebrání přímo z Fronty:** menu jednotlivého výskytu má Odebrat z fronty. Odstraní pouze tento výskyt z aktuálního poslechu, bez zápisu do YTM a změny zdrojového seznamu. Hrající/pozastavený výskyt má výslovnou volbu Odebrat z fronty po dohrání, po označení neaktivní Odebere se po dohrání; mizí při EOS, Next/Previous nebo Stopu. Ostatní výskyty mizí ihned, zachovává se aktuální audio, čas, Repeat, Mix, zdrojové indexy a cover. Přesouvání a hromadné odebírání tímto krokem nepřidáváme. 504 offline testů a dvě QML kontroly prošly. Michal skutečným testem přijal. Album/playlist do fronty přijaté a uložené jako 44833e6.

**0.3.60-dev / Plán 1b – celý online playlist do fronty:** v ⋮ dokončeného běžného playlistu Přehrát jako další / Přidat na konec fronty. Vkládá všechny načtené přehratelné výskyty v původním pořadí včetně duplicit, bez nového API požadavku, zápisu do playlistu či přerušení audia. Akce čekají na dokončení všech bloků; při chybě zůstanou neaktivní. Průběžné Mixy tyto akce nenabízejí. Prázdná fronta se připraví bez spuštění; cover vrací zdroj a přesný výskyt. Album 0.3.59-dev Michalem přijato. 493 offline testů a dva QML scénáře prošly. Playlist Michalem skutečně otestován a přijat 2026-10-29; album i playlist uložené jako 44833e6.

**0.3.59-dev / Plán 1a – online album do fronty:** v ⋮ otevřeného alba „Přehrát jako další“ vloží celé album hned za aktuální skladbu, „Přidat na konec fronty“ za dosavadní konec. Pořadí a duplicitní výskyty alba zachované; bez dalšího požadavku YTM, nového startu audia či změny pozice/Repeat/Mix. Prázdná fronta se připraví bez automatického spuštění. Vložené skladby mají zdrojový kontext pro cover/navigaci. 488 offline testů a tři QML scénáře prošly; Michal skutečným testem přijal. Playlist navazuje v 0.3.60-dev. Poslední commit 443cfa1.


## Aktuální pořadí dalších prací – domluva 2026-10-28

Tento přehled nahrazuje starší pořadí níže. Dokončené čtyři Michalovy poznámky už nejsou otevřené úkoly; body 3–4 uložené v **443cfa1**. Cast má přednost před MPRIS. MPRIS bude poslední funkční krok před závěrečnou kontrolou a vydáním, včetně ovládání již zapojeného Castu.

| Pořadí | Co přibude v aplikaci | Samostatně testovatelné podkroky |
|---|---|---|
| 1. Celé album/playlist do fronty | Při poslechu přidat celé další album nebo playlist, aniž se přeruší současná skladba. | 1a album: jako další / na konec; 1b playlist se stejnými akcemi a zachováním duplicit. Menu ⋮, bez nových tlačítek. Online Knihovna → Skladby zůstává bez těchto celoseznamových akcí. |
| 2. Upravit samotnou Frontu | Vyřadit skladbu z dnešního poslechu nebo ji posunout dřív, aniž se změní uložený playlist. | 2a odebrat konkrétní výskyt, zvlášť dohodnout právě hrající; 2b přesunout výskyt a ověřit nové pořadí, Shuffle/Mix a přednačítání. Přetahování není podmínkou. |
| 3. Info a hodnocení jiné skladby | Přes ⋮ zjistit údaje nebo dát líbí/nelíbí i skladbě, která právě nehraje. | 3a Info vybrané skladby; 3b dostupné hodnocení s ověřením výsledku. |
| 4. Údaje u alba/playlistu/interpreta | Doplnit do kompaktní hlavičky to, co YTM skutečně vrací, například autora, rok nebo délku. | 4a prověřit současné údaje a navrhnout jen chybějící; 4b doplnit a zkontrolovat malé okno. Žádné odhadované údaje. |
| 5. Knihovna, odběry a odkazy | Uložit/odebrat album či playlist, sledovat interpreta, zkopírovat nebo otevřít veřejný odkaz. | 5a alba v knihovně; 5b playlisty v knihovně (jiná věc než smazat vlastní playlist); 5c odběr interpreta; 5d odkazy. Každá část zvlášť. |
| 6. Pokračovat po restartu | Po novém spuštění nabídnout návrat ke skladbě, její pozici a frontě. | 6a uložení/obnova běžné fronty a odmítnutí nabídky; 6b Shuffle, Repeat, Mix a zdrojový kontext. Bez automatického přehrání či připojení Castu. |
| 7. Přihlášení z aplikace | Přihlásit účet nebo obnovit neplatné přihlášení bez práce v terminálu. | 7a první přihlášení existujícím mechanismem CLI; 7b obnovení, zrušení a chyby. |
| 8. Cast – přednost před MPRIS | Vybrat Kočičku/jiné zařízení/skupinu a přenášet na ně poslech. | 8a najít a zobrazit zařízení na pokyn; 8b notebook → Cast; 8c Cast → notebook; 8d Cast1 → Cast2/skupina; 8e výpadky, odpojení a celý přehrávací provoz. Každý přechod zvlášť, využít funkční CLI. |
| 9. MPRIS – poslední nová funkce | Ovládat FelisMusic z přehrávacího panelu KDE, multimediálních kláves a sluchátek. | 9a lokální přehrávání; 9b stejná integrace pro vybraný Cast výstup; 9c skutečný test kláves a sluchátek. |
| 10. Dokončení desktopové 1.0 | Doladit celek a připravit instalovatelnou aplikaci se spouštěčem. | 10a společná kontrola funkcí; 10b vzhled/menu/texty; 10c ikona, instalace a spouštěč; 10d dokumentace a kandidát vydání. Publikace pouze na samostatný pokyn. |

Před každým podkrokem Klára stručně popíše konkrétní chování. Potom: zavřená aplikace a Michalovo „můžeš“ → úprava → kontroly Kláry → skutečný test Michala → případné opravy → přijetí a commit → další podkrok. Tento zápis autorizuje plánování, nikoli automatické zahájení programování.


**0.3.58-dev / Poznámky 4:** Knihovna → Interpreti → interpret s přesným knihovním ID MPLAUC nabízí rozbalovací **Skladby / Všechny skladby**. Výchozí Skladby čtou jeho vlastní knihovní shelf včetně pokračování; Všechny skladby zachovávají dosavadní celý katalog. Bez hledání podle jména, odvozování členství nebo odstraňování duplicit. Přepínání a řazení jsou lokální, Zpět/cover zachovávají zdrojový stav a audio/frontu nemění. Alba, Singly/EP i rozsah dosavadních akcí Náhodně/Mix zůstávají stejné; běžný katalogový interpret bez knihovního ID má původní zobrazení. 482 offline testů a tři QML scénáře prošly (obě velikosti a regrese online navigace). Michal skutečným testem potvrdil i bod 4 jako plně funkční. Všechny čtyři nadiktované poznámky jsou hotové a přijaté; body 1–2 uložené v c0c5ccf, body 3–4 uložené v 443cfa1.


**0.3.57-dev / Poznámky 3:** online navigace přes skutečná album/artist ID, stejná pravidla nabídek jako Nahrané, volba více interpretů. Společná historie vrací seznam/řazení, hledání/Oblíbené/historii nebo Frontu, přepíná cílové sekce a zachovává audio. Také karta alba v diskografii přepíná menu a vrací se na původní záložku. 475 offline testů, 12 online QML scénářů a dvě upload regrese prošly; Michal skutečným testem potvrdil funkčnost a povolil bod 4. Poslední commit c0c5ccf (přijaté body 1–2).

**0.3.56-dev / Poznámky 2:** online Knihovna → Skladby přes LibrarySongPages a public get_library_songs(limit=0), společné ověřené řízení bloků s Nahranými při rozlišení obou zdrojů/parserů. První blok použitelný, fronta roste, cover/Stop/Repeat/řazení/staré odpovědi chráněny. Po dokončení v menu celku pouze lokální Přehrát náhodně, bez Mixu/enqueue/save celého seznamu. 463 offline testů, čtyři online QML scénáře a dvě regrese Nahraných prošly; dva skutečné read-only bloky 23+42 přehratelných řádků s pokračováním. Michal potvrdil také bod 2 jako funkční. Body 1–2 přijaty a připraveny ke společnému commitu; poslední commit 134f3b7. Dále bod 3 online navigace, potom bod 4 knihovní/všechny skladby interpreta.

**0.3.55-dev / Poznámky 1:** multivýběr ve vlastním playlistu → Odebrat z playlistu, potvrzení počtu, čerstvé ověření vlastnictví a všech přesných setVideoId před jediným batch požadavkem. Synchronizace fronty jedním průchodem, zachování aktuálního audia/ručních kopií, odznačení po úspěchu. 450 offline testů a čtyři QML scénáře prošly; Michal potvrdil bod 1 jako otestovaný a funkční. Dále postupně poznámky 2 (online Skladby po blocích + Shuffle), 3 (online navigace), 4 (Skladby / Všechny skladby interpreta). Poslední commit 134f3b7; předchozí read-only ověření bodu 4 je pouze dokumentované, neimplementované.

**Bod 4 upřesněn a proveditelnost ověřena (2026-10-28).** Jen volbu Skladby katalogového interpreta rozdělit rozbalovací nabídkou na **Skladby** (knihovní obsah interpreta podle YTM) a **Všechny skladby** (dosavadní celý dostupný katalogový seznam). Při vstupu z Knihovna → Interpreti výchozí Skladby; Alba, Singly/EP a ostatní funkce neměnit. Skutečný read-only test Olympicu: karta „2 songs“, browseId začíná MPLA a nemá params; přímý browse tohoto přesného ID vrací 2 přehratelné skladby (parser navíc vrací jeden nepřehratelný pomocný řádek), bez pokračování. `get_artist` instalované ytmusicapi z browseId odstraňuje prefix MPLA, a tím současný kód otevře katalogový detail místo knihovního. Katalogový detail Olympicu má 5 úvodních skladeb a pointer pro celý dostupný seznam; ten už GUI umí načíst. Řešení: uchovat skutečný knihovní endpoint MPLA z karty, načíst/parsovat jeho skladby odděleně od katalogového songs pointeru a respektovat případná pokračování jiných interpretů. Neskenovat ručně playlisty a neodvozovat členství podle názvu ani Like. Původ členství těchto dvou skladeb (playlist/Oblíbené/jiná knihovní akce) test neprokazuje. Tehdy pouze ověřeno a naplánováno; implementace navazuje v 0.3.58-dev výše.

**Rozhodnutí – cache seznamů (2026-10-28).** Michal po otestování načítání po blocích rozhodl další cache seznamů nyní neřešit. Není to další plánovaný úkol; stávající audio cache/prefetch se nemění.

**0.3.54-dev / Nahrané – skladby po blocích:** první upload shelf přes limit=0, pokračování po jednotlivých stránkách na pozadí bez globálního busy. Běžné přehrávání z prefixu doplňuje tutéž frontu; EOS/Stop/Repeat/cover a ochrany po navigaci/novém řazení. Whole-list akce/multivýběr až po dokončení, lokální banner. 439 offline testů a čtyři QML scénáře prošly; dva skutečné read-only bloky 25+50 řádků s pokračováním. Michal skutečným testem potvrdil funkčnost. Pořadí/výchozí Alba a načítání po blocích (0.3.53–0.3.54) přijaty; domluvený rozsah Nahraných uzavřený a připravený ke společnému commitu. Poslední commit 188bba8.

**0.3.53-dev / Nahrané – první podkrok ergonomie:** pořadí Alba → Interpreti → Skladby; první vstup po spuštění otevírá Alba, další návraty pamatují poslední upload sekci během téhož běhu. QML 900×600/1280×800 prošlo včetně klikání na všechny sekce a odchodů/návratů, první vstup neposílá požadavek na skladby. Michal skutečným testem přijal. Předchozí Mix uložen jako 188bba8. Navazující stránkování skladeb připravené v 0.3.54-dev.

**Poznámka k Mixu nahraného interpreta:** Michalovo hodnocení: „mix na píču“. Funguje stejně jako webové YTM: používá pouze vlastní nahrávky daného interpreta; při jediném nahraném albu tedy míchá jen toto album. Nejde o doporučování další podobné hudby. Volbu ponecháváme, funkce je otestovaná a uzavřená.

**0.3.52-dev / Mix nahraného interpreta:** ⋮ → Spustit mix pod lokálním Shuffle, podle skutečného radioId z upload karty. ID uchováno v detailu/cache, při vstupu přes skladbu se případně dohledá přes přesný browseId v seznamu upload interpretů. Serverové pořadí a duplicity, Fronta/cover, konec či pokračování stejného watch zdroje; žádný katalogový reseed. 421 offline testů a šest QML scénářů prošlo; Michal skutečným testem potvrdil funkčnost i shodu s webovým YTM. Mix Nahraných přijat. Navigace 3b uložená jako 170ac2f. Potom zbývá rychlé načítání Nahraných po blocích.

**Další navigace – online sekce (2026-10-28).** Michal požaduje doplnit „Otevřít album / interpreta“ také u online katalogových skladeb, obdobně jako přijatou navigaci Nahraných. V seznamu skladeb obě možnosti podle dostupných skutečných ID, v detailu interpreta přechod na album a v albu na interpreta; odpovídající přepnutí sekce menu a návrat Zpět se zachováním původu/řazení i běžícího audia. Implementováno v 0.3.57-dev a Michalem potvrzeno jako funkční. Navigace Nahraných 3b uložena Michalem jako **170ac2f**.

**0.3.51-dev:** oprava chybějícího přechodu z nahraného alba na interpreta. Skutečný album endpoint u vzorku vrací artists=None u všech 10 skladeb a žádné artists v hlavičce, ale privátní artist browseId je v menu každého surového řádku. Nový malý adaptér uchová ID ze stejného požadavku; fallback na ID v hlavičce, pokud je dostupné, a přednost přímých údajů skladby. 412 offline testů a šest QML scénářů prošlo, navíc read-only ověření 10/10 skutečných odkazů. Michal skutečným testem potvrdil navigaci jako funkční. Celek 0.3.49–0.3.51 přijat a připraven ke společnému commitu.

**0.3.50-dev / oprava 3b:** podle skutečného testu v upload interpretovi jen Otevřít album, v upload albu jen Otevřít interpreta, v seznamu skladeb/Frontě obojí podle ID. Přechod vždy do příslušné sekce knihovny (Alba/Interpreti), Zpět obnoví i sekci menu. 405 offline testů a šest QML scénářů prošlo; čeká na skutečný test. 0.3.49–0.3.50 zatím společně necommitované.

**0.3.49-dev / Nahrané 3b:** v menu nahrané skladby přechod na nahrané album/interpreta podle skutečných ID, více interpretů s výběrem. ID zachována i ve Frontě; Zpět obnoví seznam/řazení nebo Frontu/hledání. Bez nového startu audia a změny fronty; bez hádání chybějících ID. 403 offline testů a šest QML scénářů prošlo, čeká na skutečný test. Předchozí řazení/marker uložené jako c5bc90c. Mix Nahraných ani načítání po blocích nejsou v tomto kroku implementovány.

**Ověřeno – Mix nahraného interpreta (2026-10-28, pouze čtení).** Instalovaná ytmusicapi vrací v `get_library_upload_artists` radioId i shuffleId; první blok 25 interpretů měl obě ID u všech. Dva skutečné radioId byly předány přímo watch endpointu/WatchPages: prefix MLPAa_po, vráceno 20 a 39 přehratelných skladeb, u obou bez pokračování. Všechny zkontrolované řádky mají videoType MUSIC_VIDEO_TYPE_PRIVATELY_OWNED_TRACK. Srovnání s úplnými upload skladbami příslušného interpreta: 20/20 a 39/39, shodné množiny videoId. Jde tedy v těchto dvou vzorcích o konečný výběr vlastních nahrávek, nikoli důkaz nekonečného katalogového rádia. Zachovat serverové radioId, nic neskládat z browseId/jména; přehrát serverový výsledek a respektovat skutečné pokračování/konec. Nezapojovat automaticky CLI reseed rádio z posledního videoId. GUI `_artist_item` nyní radioId/shuffleId zahazuje a upload detail vrací jen skladby; implementace musí zachovat ID z karty do detailu i cover kontextu. Uživatelsky požadovaná volba pouze u nahraného interpreta, nikoli upload alba/skladby; playlisty společné a jejich Mix zůstává. Funkce zatím neimplementovaná. Kontrola bez audio přehrávání, změn knihovny a dumpování auth/odpovědí.

**Poznámka od Michala – Knihovna → Interpreti → interpret (2026-10-28).** „Vrátit do Knihovna → Interpreti → interpret zobrazení ‚moje‘ skladby a všechny skladby interpreta.“ Přesné zamýšlené chování Michal vysvětlí, až se na tento bod dostaneme. Zatím pouze poznámka; neodvozovat implementaci ani nezačínat úpravu.

**0.3.48-dev:** oprava zvýraznění po změně řazení ve čtyřech domluvených místech: skladby knihovny, nahrané skladby, katalogový a nahraný interpret. Samostatný viditelný index sleduje původní výskyt, bez zásahu do fronty/audia a bez automatického posunu při řazení; jiný zdroj se stejným videoId se neoznačuje. 395 offline testů a osm QML scénářů prošlo; Michal skutečným testem potvrdil funkčnost opravy. 0.3.47–0.3.48 společně necommitované, poslední commit e0b75ba.

**Další úprava – Knihovna → Skladby (2026-10-28).** Upravit načítání po blocích, aby první část byla rychle použitelná a ovládání/navigace dostupné i během doplňování. Přidat lokální „Přehrát náhodně“ pro celý seznam; dostupnost akce musí respektovat úplnost načtení. Michal výslovně nechce další kolekční akce nad celým tímto seznamem (Mix, přidání celku jako další/na konec fronty apod.). Jednotlivé skladby a multivýběr tím neměníme. Zatím zapsáno, neimplementováno.

**Schválená oprava – zvýraznění přehrávaného výskytu při řazení (2026-10-28).** Michal našel problém v Knihovna → Interpreti → interpret, Nahrané → Interpreti → interpret, Knihovna → Skladby a Nahrané → Skladby. Po přerovnání musí zvýraznění sledovat tentýž konkrétní výskyt na jeho nové pozici, včetně rozlišení duplicit. Fronta, audio a jeho pozice se nemění; seznam se automaticky neposouvá a v jiné kolekci se stejná skladba neoznačuje jen podle videoId. Ostatní zobrazení v tomto kroku neupravovat. Hotovo: řazení i navazující opravu 0.3.48 Michal skutečně přijal a uložil jako c5bc90c. Tento požadavek už není otevřený.

**0.3.47-dev / Nahrané 3a:** řazení skladeb nahraného interpreta A–Z (výchozí), Z–A a původní pořadí, bez nového API požadavku. Přepnutí nemění přehrávanou frontu; cover obnovuje zdrojové řazení zachycené při spuštění. Alba zachovávají pořadí. 389 offline testů a QML 900×600/1280×800 prošlo; čeká na skutečný test. Předchozí body 1–2 commitnuté jako e0b75ba. Navigace skladba → album/interpret a rychlé otevření Nahraných nejsou součástí tohoto podkroku.

**Další úprava Nahraných – rychlé první otevření (2026-10-28).** Po kliknutí na Nahrané se nyní jako první otevírají skladby a úplné načítání dlouho blokuje další akce. Michal požaduje vyřešit samostatně po aktuálním kroku: načítat nahrané skladby po blocích s použitelným prvním seznamem a dostupnou navigací/ovládáním, případně přesunout Skladby na poslední místo a jako výchozí otevřít jinou sekci. Hotovo a přijato v 0.3.53–0.3.54: Alba → Interpreti → Skladby, první vstup Alba a paměť poslední sekce během běhu; nahrané skladby načítané po blocích s přehráváním z prefixu. Tento požadavek už není otevřený.

**Domluvený podkrok – multivýběr: Odebrat z playlistu (2026-10-28).** Doplnit do hromadných akcí odebrání označených výskytů z vlastního upravitelného playlistu podle jejich setVideoId, včetně synchronizace související přehrávací fronty. Jde o odebrání z uloženého playlistu, nikoli pouze z Fronty. Implementováno v 0.3.55-dev jako samostatný testovatelný krok; čeká na Michalův skutečný test.

**0.3.46-dev:** bod 1 (Shuffle Nahraných) Michal přijal a povolil bod 2. Celé Nahrané skladby/album/interpret mají přidání jako další a na konec fronty; hlavní seznam také uložení celku do playlistu. Jednotlivé a vybrané skladby i uložení celých upload detailů už fungovaly a jsou regresně ověřené. 384 offline testů a šest QML scénářů prošlo. Michal potvrdil také bod 2 jako funkční; body 1 a 2 (0.3.45–0.3.46) přijaty a připraveny ke společnému commitu. Poslední commit 3689b13.

**0.3.45-dev:** lokální Shuffle Nahraných: seznam skladeb, album a skladby interpreta; nabídky ⋮, Fronta a návrat coverem, přesné výskyty a metadata. Interpret se načítá bez limitu 2000. 378 offline testů a šest QML scénářů prošlo; Michal skutečným testem přijal bod 1. Předchozí celek přijat a uložen jako 3689b13. Mix Nahraných a další akce zůstávají samostatné kroky.

**0.3.44-dev:** opraven návrat coverem z Mixu playlistu/alba/interpreta (také hlavních Oblíbených) do původního zdroje, včetně doporučení z dalších bloků. Obnoví detail/záložku bez restartu audia. 372 offline testů a šest QML scénářů prošlo. Michal potvrdil celek 0.3.42–0.3.44 jako otestovaný a funkční; připraveno ke společnému commitu.

**0.3.43-dev:** domluvené pravidlo RD… pro dynamické zdroje. Playlisty i Mixy pro vás načtou stejnou cestou první watch blok; pokračování stejného ID až podle postupu poslechu, s EOS/Stop/pauzou/Repeat a odstupem při výpadku. Pevné seznamy dál celé po blocích. 371 offline testů a 4 QML scénáře prošly; navíc dva skutečné read-only bloky Supermixu 24+24 s pokračováním. Čeká na reálný poslech/test, necommitováno spolu s 0.3.42. Poslední commit 0bc66cb.

**0.3.42-dev:** playlistové detaily včetně „Liked Music“ mají první blok a background doplnění stejně jako hlavní Oblíbené. Běžné přehrávání z prefixu rozšiřuje tutéž konečnou frontu; akce nad celkem až po dokončení. Ochrany EOS/Repeat/Stop, chyby, cover a zneplatnění. Výjimka obnovy s čekajícím přesunem: úplné načtení pro porovnání. 355 offline testů + QML dvojklik při načítání v obou velikostech prošly; čeká na Michalův reálný test. Předchozí commit 0bc66cb. Potom samostatně Nahrané a podle dostupných endpointů další velké kolekce.

**Doplněný samostatný krok – Nahrané:** lokální náhodné přehrávání nahraných skladeb, alb a skladeb interpreta. Možnosti Mixu nahraných zdrojů nejprve ověřit podle skutečných možností API; podporu zatím neslibovat a nenahrazovat ji potichu katalogovou skladbou. Lokální Shuffle 0.3.45-dev přijaté Michalem; hromadné akce fronty/playlistů připravené v 0.3.46-dev, čekají na test. Navigace/řazení a možnosti Mixu zůstávají samostatné kroky.

**0.3.41-dev:** lokální Zamíchat aktuální frontu bez serverového pořadí, se zachováním aktuálního výskytu/audia/času/pauzy/Repeat, všech ručních i duplicitních výskytů. 337 offline testů a obě QML velikosti prošly; Michal skutečným testem potvrdil funkčnost. Po přijetí/commitu sjednocení stránkování detailů playlistů. Předchozí commit 6135d69.

**0.3.40-dev:** Michal ověřil lokální Shuffle interpreta; menu sjednoceno na Přehrát náhodně → Spustit mix, stejně jako u alb/playlistů. Přehrávací logika se v této drobné úpravě nemění.

**0.3.39-dev:** lokální Shuffle interpreta nad již načtenou sekcí Skladby, všechny dostupné výskyty, bez watch požadavku/limitu Mixu. Cover zachovává původní záložku. Mix/refill nezměněny. Čeká na skutečný test; potom lokální přemíchání aktuální fronty a stránkování playlistových detailů. Album uložené v e408639.

**0.3.38-dev:** připravené lokální Shuffle alb nad celým již načteným seznamem, shodnou cestou jako playlisty. Mix/refill beze změny. Michal skutečným testem přijal; po commitu zvlášť interpret, přemíchání fronty a stránkování detailů playlistů. Předchozí celek uložen v 1bdf196.

**0.3.37-dev:** opraveno kvadratické kopírování zdrojového seznamu při přípravě hlavních Oblíbených (společný deepcopy memo, zachované indexy/izolace/cover). 346 offline testů a obě QML velikosti prošly, Michal skutečným testem potvrdil funkčnost i opravu pomalé přípravy. Načítání detailů playlistů po blocích zatím neměněno.

**0.3.36-dev:** lokální Shuffle nyní také v hlavních Oblíbených, až po dokončení jejich seznamu; zachovává přesné výskyty a návrat přes cover. 344 offline testů a QML v obou velikostech prošlo, čeká na skutečný test. Další samostatné kroky: alba, interpreti, přemíchání fronty. Mix/refill beze změny.

**Aktuální podkrok 2026-10-27 / 0.3.35-dev:** po prokázaném cyklu serverového Shuffle je připravené lokální „Přehrát náhodně“ pouze v detailu playlistu, nad celým již načteným seznamem se zachováním přesných výskytů. 339 offline testů a QML 900×600/1280×800 prošlo; čeká na Michalův test. Potom samostatně alba, Oblíbené, interpreti a přemíchání fronty. Mix/Rádio beze změny. P3 zatím nezahajovat.

Aktualizováno: **2026-10-26 (Europe/Prague)** po porovnání kódu GUI, původní CLI reference `tmp/felismusic.py` a převzatého `desktop/felismusic_gui/legacy_core.py`.

Aktuální uživatelsky přijatá verze: **0.3.25-dev**, commit **`eb531ef`** (B2 přijato 2026-10-26). B1 je uložený v commitu **`eac3b3d`**. A2 je uložené v commitu **`869838b`**. Předchozí úprava Repeat je uložená v commitu **`6272381`**. Shuffle A1 je uložený v commitu **`2c51536`**. Poslední ověřování: **241 offline testů**, QML 1280×800/900×600 a skutečné uživatelské testy YTM. Historie změn a přijetí je v [STATUS.md](STATUS.md); věcné porovnání funkcí v [CLI-GUI.md](CLI-GUI.md). Tento plán popisuje současný stav, nikoli postupně zastarávající historické mezistavy.

**A1 přijato uživatelem a commitnuto:** náhodné spuštění playlistu/alba, Repeat, přechody a návrat přes cover ověřené ve skutečném YTM. Kolekce zachovává své řazení, Fronta ukazuje skutečné pořadí přehrávání; toto chování uživatel výslovně chce zachovat.

Přijato uživatelem **0.3.21-dev**: Repeat patří k aktuální frontě. Nové přehrávání z kolekce/vyhledávání, nový Shuffle či rádio jej vypne až při úspěšném vytvoření fronty. Pohyb uvnitř fronty, procházení, cover, Pause/Play, Stop/Play a vkládání skladeb jej zachovají. Skutečný uživatelský test potvrdil funkčnost. Následují A2 a Rádio jako samostatné podkroky.

Přijato uživatelem **0.3.23-dev / A2**: tlačítko **Fronta → Zamíchat**, zachování aktuálního audia/času/pauzy/Repeat a přesných výskytů. Pořadí kolekční části určuje YTM; ruční položky se lokálně promíchají a náhodně rozptýlí mezi kolekční část. Michal potvrdil funkčnost po několika ručních testech. B1 – průběžné doplňování Rádia/Mixu – je následující samostatný podkrok.

Přijato uživatelem **0.3.24-dev / B1**: automatické doplňování mixu ze skladby přes CLI `refill_radio_queue` na pozadí. Při nejvýše pěti zbývajících skladbách doplní nový blok; při chybě či žádných nových výsledcích odloží pokus o 30 sekund. Dosažený přirozený konec může po doplnění automaticky navázat, Stop to zruší. Prošlo 228 offline testů a QML ověření; Michal potvrdil skutečné doplňování dvou navazujících bloků a růst Fronty v GUI i logu. Následuje B2 – akce interpreta přes ⋮.

Přijato uživatelem **0.3.25-dev / B2**: **menu ⋮ v hlavičce interpreta → Spustit mix / Přehrát náhodně**, přes vrácené radioId/shuffleId a CLI `artist_action_queue`. Mix pokračuje přes B1, Shuffle je konečná fronta. Akce fungují na všech kartách interpreta a dostupnost se řídí každým ID samostatně. Prošlo 241 offline testů a QML kontroly; Michal potvrdil funkčnost a shodu opakovaných front s webovým YTM. B3 – Mix alba/playlistu – navazuje v 0.3.26-dev.

Rozpracováno **0.3.26-dev / B3**: **⋮ v hlavičce alba/playlistu → Spustit mix** používá RDAMPL + audioPlaylistId/playlistId celé kolekce. Nová generovaná Fronta využívá průběžné doplňování B1. Prošlo 253 offline testů a QML kontroly; čeká na skutečný uživatelský test. Otevření existujících „Mixů pro vás“ se touto etapou nemění.

**Aktuální priorita – 0.3.27-dev, diagnostika před přijetím B3.** Uživatel hlásí pomalou přípravu/stahování a dlouhý busy při načítání playlistu. Doloženy read timeouty 20 s na googlevideo.com a HTTP 503; GUI zůstává responzivní, ale busy znemožňuje další akce. Samostatný nepřihlášený yt-dlp test: metadata 4,382 s; stažení celkem 14,570 s, včetně oznámeného čekání 4 s a přenosu cca 3 MiB za 5 s. Není doložené omezení 429 ani příčina pomalosti. Doplněno časování front úloh, session HTTP a audio fází, bezpečné hostnames/chyby a vypínatelná diagnostika; 262 offline testů a QML kontrola. Čeká na skutečný diagnostický log; síťové parametry, retries a funkce busy se zatím nemění. Další funkce pozastavit do objasnění.

**0.3.28-dev – čeká na uživatelský test:** při dalším běhu se zpomalení podle uživatele neprojevovalo; příčina není potvrzená. Diagnostiku ponechat, ale default vypnout, zapínat přes `./run-gui.sh --debug`. Náhodné spuštění alba/playlistu nově po úspěchu otevře Frontu; původní kontext pro cover se zachová. 265 offline testů. B3 a následná úprava navigace nadále čekají na přijetí, neuzavírat jako hotové bez skutečného testu.

**Test 2026-10-27 a 0.3.29-dev:** Michal potvrdil Shuffle alba/playlistu včetně coveru a opakované doplňování všech mixů (B3 skutečně ověřeno). Opraven chybějící návrat coverem ke kartě interpreta po Shuffle. Doplněno ⋮ v Oblíbené hudbě: Náhodně přes LL, Mix přes RDAMPLLL s průběžným doplňováním B1. 271 offline testů a QML obou velikostí; tyto dvě úpravy čekají na nový skutečný test. Diagnostika zůstává volitelná přes --debug; příčina dřívější pomalosti není doložená.

**2026-10-27 – 0.3.29 skutečně potvrzeno; priorita P – postupné načítání:** Michal potvrdil návrat k interpretovi i obě akce Oblíbených. Před dalšími funkcemi zrychlit dlouhé seznamy/fronty obecně. **P1 (0.3.30-dev, implementováno, čeká na test):** adaptér po stránkách a první nasazení na prohlížení Oblíbených, bez limitu 2000, neblokující doplňování a označení neúplnosti. Akce/řazení zatím až po dokončení. 284 offline testů a QML obou velikostí. **P2:** zachovat pokračování serverové přehrávací/Shuffle fronty a začít přehrávat první blok; řešit EOS, Stop, Repeat, přesné výskyty a vazby. **P3:** postupné nasazení na velké playlisty a dostupné endpointy interpreta/kolekcí s ochranou celokolekčních akcí a řazení. Přesné rozdělení ověřovat podle možností každého endpointu, nesnižovat pouze limity a netvářit se, že zkrácený seznam je celý. Každá etapa má vlastní test a přijetí; automatické testy velkých dat jsou práce Kláry, Michal ověřuje několik běžných skutečných scénářů.

**0.3.31-dev – zpřehlednění P1:** rychlé otevření Oblíbených uživatel potvrdil; dokončení celého seznamu z původního textu nedokázal rozlišit. Doplněn výrazný neblokující panel s malým kolečkem, průběhem a čtyřsekundovým potvrzením dokončení. QML ověřuje i dostupný Stop/navigaci během načítání. Čeká na skutečný test indikace; P2 se zatím nezahajuje.

**0.3.32-dev / P2a – implementováno, čeká na test:** normální přehrávání dvojklikem/Enterem z prvního bloku Oblíbených, další stránky doplňují stejnou frontu. Při přirozeném konci prefixu čekání a navázání, Stop ruší automatické pokračování, Repeat All čeká na skutečný konec a chyby/obnova/nový zdroj nesmějí přimíchat cizí stránky. Prošlo 300 offline testů a QML obou velikostí. **P2b dál zbývá:** samostatně stránkovat a rychle spustit serverovou Shuffle frontu se zachováním přesného pokračování; v P2a se Shuffle nemění. Po přijetí pokračovat P2b, pak P3 další kolekce/interpreti podle jejich endpointů.

**0.3.33-dev / P2b – implementováno, čeká na test:** první blok serverové Shuffle fronty pro playlist/album/Oblíbené/interpreta; další bloky přes přesné pokračování stejného požadavku, konečný původní cíl a sdílené EOS/Stop/Repeat čekání. 319 offline testů, QML všech čtyř zdrojů v obou velikostech. Rychlost přípravy audio souboru ani dostupnost akcí při načítání původního seznamu zatím neměnit. P2a souběh audio/seznam skutečně potvrzen, diagnostikou doložen. Po přijetí P2b pokračovat **P3: prohlížení velkých playlistů**, potom alba/interpret podle možností endpointů; každý zvlášť testovat. Průběžný Mix a A2 opětovné zamíchání existující fronty jsou oddělené mechanismy.

**Aktuální priorita 0.3.34-dev – diagnostika před přijetím P2b:** uživatelský test narazil na neúplnou frontu. Log ukazuje HTTP 200 a RuntimeError při další stránce, podezření na opakovaný token dosud není potvrzené. Přidáno bezpečné rozlišení důvodu/fáze a počty/porovnání bloků přes --debug; 322 offline testů. Tok načítání a ochrany beze změny. **Počkat na nový skutečný log, P3 neimplementovat.** Pokud watch continuation nebude spolehlivé, je uživatelem přijatelné vrátit samotný Shuffle k původnímu pomalejšímu načtení; P1/P2a Oblíbených jsou nezávislé a lze je zachovat.

**Další diagnostický krok po logu (3):** opakovaný token potvrzen, 344 přijatých položek z cíle 1635; odmítnutý osmý blok obsahuje 49 již viděných skladeb a 0 nových. Připravený `tools/compare_shuffle.py --limit 1635` porovná starý helper a nový adaptér na přesně stejných odpovědích (jeden živý původní běh, nový pouze replay v RAM). Čtyři cílené offline testy prošly. Čeká se na skutečný výstup stejného playlistu; neprohlašovat zatím starý výsledek za chybný a nepokračovat P3.

## Rozsah a pracovní domluva

- Cíl: desktopová 1.0 pro Linux s přehráváním, YTM Shuffle, frontou, průběžným rádiem, knihovnou a playlisty, session, MPRIS a Castem.
- Hotové datové a přehrávací mechanismy CLI znovu nevymýšlet. Převzít je a adaptovat na asynchronní GUI, jeho metadata, přesné výskyty skladeb a ochranu proti opožděným výsledkům. Textová menu a blokující smyčku CLI nepouštět jako GUI přehrávač.
- Start vždy na lokálním výstupu. Cast hledat/připojit až na ruční pokyn, i po obnovení session.
- Jeden samostatně testovatelný podkrok: úprava → kontroly Kláry → skutečný test Michala → opravy → přijetí/dokumentace → commit. Potom další podkrok.
- Před programováním upozornit na zavření aplikace a počkat na potvrzení. Čtení kódu, plánování a zápis přijetí do dokumentace mohou probíhat za běhu aplikace.
- Git zápis provádí Michal připraveným jednořádkovým příkazem. Push a publikace pouze na samostatný pokyn.
- Trvalé offline stahování a Sailfish port nejsou podmínkou desktopové 1.0.

## Stav původních bodů 1–11

| Bod | Současný stav | Co zbývá |
|---|---|---|
| **1. Repeat / Shuffle** | Repeat včetně resetu pro novou frontu (0.3.21) a A1 náhodné spuštění playlistu/alba přijaté. | A2 zamíchání běžící fronty přijaté v 0.3.23. Bod 1 hotový; Shuffle interpreta patří do B2. |
| **2. Fronta + Info + Stop** | **Hotovo** v původním rozsahu. | Samostatné zásahy do fronty patří do 3c. |
| **3. Kontextová menu** | Menu skladeb, vložení jedné či vybraných skladeb jako další/na konec, multivýběr hotové. | **3a:** Info/hodnocení konkrétní vybrané skladby v menu. **3b:** přímé přehrávací a vkládací akce celých kolekcí. **3c:** odebrání/přesun přímo ve Frontě. |
| **4. Detaily a navigace** | **4a hotovo:** interpret – dostupné úplné skladby/alba/singly/EP, řazení, otevření alba a návrat. Kompaktní hlavičky hotové. | **4b:** dostupná metadata hlaviček. **4c hotovo:** online i upload přechody a návraty, přijato v 443cfa1 (online). |
| **5. Rádio / Mix** | **5a hotovo:** mix z jedné skladby, první blok doporučení. Mixy pro vás lze načíst a otevřít. | **5b / B1 hotovo:** uživatelsky přijato v 0.3.24-dev. **5c / B2:** Mix/Náhodně interpreta přijaté v 0.3.25. **B3:** Mix alba/playlistu přes ⋮ skutečně ověřený 2026-10-27; doplnění Oblíbené hudby v 0.3.29 čeká na test. |
| **6. Knihovna a odběry** | Přímé přidání/odebrání podporované skladby v knihovně hotové. | **6a zbytek:** alba/playlisty. **6b:** odběry interpretů. **6c:** kopírování/otevírání odkazů. |
| **7. Správa playlistů** | **7a–7d hotové, uživatelsky přijaté a commitnuté.** | Hromadné odebrání hotové v c0c5ccf; další námět přetahování; nezpochybňují dokončení domluveného rozsahu 7a–7d. |
| **8. Session a přihlášení** | GUI používá existující FCM přihlášení. | **8a:** uložit/obnovit přehrávání. **8b:** přihlásit/obnovit přihlášení z GUI. |
| **9. MPRIS** | Nezapojeno. | Systémové ovládání KDE, multimediální klávesy a Bluetooth sluchátka. |
| **10. Cast** | GUI má lokální výstup. Ověřený Cast existuje v CLI. | Discovery, výběr výstupu, Local ↔ Cast ↔ Cast, odpojení/ztráta zařízení a integrace ostatních funkcí. |
| **11. Desktop 1.0** | Vývojový základ průběžně ověřovaný. | Kontrola celku, vzhled/použitelnost, instalace, ikona/spouštěč, dokumentace a příprava vydání. |

Pozor na dva různé významy „úprava fronty“: synchronizace po změně uloženého playlistu je hotová v bodu 7. Samostatné odebrání/přesun položky pouze ve Frontě, bez zápisu do YTM playlistu, ještě není hotový bod 3c.

## Nejbližší pořadí práce

Uživatel zdůraznil časté používání Mix/Rádia. Proto se po bodu 7 nepostupuje rovnou k 8; nejprve se vracíme k přeskočenému Shuffle a rádiu. Následující pořadí je aktuální návrh, každý podkrok má vlastní test a commit.

### A. Shuffle (1b)

1. **A1 – Spustit kolekci náhodně přes YTM (hotovo, přijato, commit `2c51536`).** Uchovat skutečné zdrojové playlistId; u alba jeho audioPlaylistId. Použít `get_youtube_shuffle_tracks`, nikoli tiše nahradit YTM Shuffle lokálním `random.shuffle`. U nepodporovaných zdrojů, včetně CLI výjimky `RDCLAK…`, je akce neaktivní; u uploadů se nezobrazuje.
2. **A2 – Zamíchat běžící frontu (hotovo a uživatelsky přijato v 0.3.23-dev).** Adaptuje current-first chování `apply_youtube_shuffle` a společný `get_youtube_shuffle_tracks`: aktuální audio/pozice/hodnocení a Repeat pokračují, aktualizuje se skutečná fronta a prefetch. Existující objekty/výskyty zůstávají zachované: kolekční část se řadí podle odpovědi YTM, nevrácené položky zůstávají za ní, ruční vložení se lokálně zamíchá a rozptýlí do náhodných míst mezi všechny ostatní položky. Cizí výsledky ani přebytečné serverové duplicity nepřidávají nové výskyty. Stejně jako CLI je aktuální skladba první a mezi zbytkem mohou být dříve přehrané skladby. Nejde o přepínač návratu k původnímu pořadí; další stisk vyžádá nové zamíchání.

**Přijetí:** skutečné YTM pořadí, označení aktuální skladby, Next/Previous/Repeat, správný nástupce v prefetch a dostupnost jen u podporovaných zdrojů. Uploadům bez odpovídajícího YTM endpointu nevyrábět nefunkční shuffle.

### B. Rádio / Mix – vysoká priorita (5b/5c)

1. **B1 – Průběžné doplňování mixu ze skladby (hotovo, uživatelsky přijato v 0.3.24-dev).** Dopojit mechanismus `refill_radio_queue` / `maybe_refill_radio_queue`: načítat před koncem fronty, další blok seedovat vhodnou poslední skladbou, filtrovat již přítomné/nepoužitelné výsledky. Operaci provádět mimo UI vlákno, zachovat audio, aktualizovat frontu a prefetch. Zrušit nebo ignorovat starý výsledek při změně zdroje. Při chybě omezený další pokus, nikoli opakování v každém pollu.
2. **B2 – Mix a Náhodně interpreta (hotovo, uživatelsky přijato v 0.3.25-dev).** GUI uchovává YTM `radioId`/`shuffleId` v metadatech interpreta. Převzít datovou logiku `artist_action_queue`. Rádio interpreta musí spolupracovat s doplňováním B1. Mix i Náhodně nabídnout přes menu ⋮, nepřidávat samostatná tlačítka.
3. **B3 – Mix alba/playlistu přes ⋮ (implementováno v 0.3.26-dev, čeká na uživatelský test).** Mix playlistu a alba nabídnout přes menu ⋮, bez dalších samostatných tlačítek. Pro skladbu používat videoId / RDAMVM, pro playlist RDAMPL + playlistId, pro album RDAMPL + audioPlaylistId a pro interpreta vrácené radioId; mix celé kolekce nenahrazovat rádiem její první skladby. Nabídnout akci tam, kde YTM skutečně vrací vhodný zdroj. Rozlišovat otevření existujícího „Mixu pro vás“, vytvoření rádia a konečný playlist. U dynamických mixů ověřit vhodný způsob pokračování; neslibovat neomezené přehrávání každému obyčejnému playlistu.

**Přijetí:** několik skutečně doplněných bloků, duplicity, konec původního bloku, dočasná chyba sítě, přepnutí na jinou frontu během dotazu a zachování aktuální skladby při aktivaci jejího rádia. První blok rádia nebo samotné otevření Mixů pro vás není splněné automatické doplňování.

### C. Uzavřít zbývající rozsah bodů 3, 4 a 6

1. **C1 / 3b – Akce celých kolekcí.** Přehrát, Náhodně (po A), přehrát celou kolekci jako další, přidat ji na konec. Uložení celé kolekce do playlistu už existuje; vkládání výběru přes Ctrl+A také funguje, chybí přímé akce kolekce.
2. **C2 / 3c – Úpravy přímo ve Frontě.** Odebrat konkrétní výskyt a přesunout ho v pořadí bez zápisu do uloženého playlistu. Samostatně určit aktuální položku, historii, ruční vložení, prefetch a interakci se Shuffle/Rádiem.
3. **C3 / 3a – Info a dostupné hodnocení vybrané skladby.** Horní Info a Like/Dislike aktuální skladby už fungují; doplnit cílení na jinou vybranou skladbu přes její menu.
4. **C4 / 4b – Hlavičky.** Dostupný cover, autor/interpret, rok, počet a délka; neodhadovat chybějící data. Kompaktní rozložení se třemi tečkami zachovat. Dostupné celé seznamy/stránkování průběžně kontrolovat.
5. **C5 / 4c – Navigace.** Skladba → album → interpret, případně výběr z více interpretů, správný návrat. Uchovat skutečná ID, podle potřeby je načíst; názvy neslouží jako náhradní identifikátor. Seznamy interpreta zůstávají dostupné celé a výchozí A–Z; datum skladby nevymýšlet z data jiného objektu.
6. **C6 / 6a – Alba a playlisty v knihovně.** Přidání/odebrání podle reálně dostupných API údajů. Nezaměňovat smazání vlastního playlistu, členství v knihovně a Like. Stávající chování skladbového menu odpovídající YTM znovu nepřepisovat na základě domněnek.
7. **C7 / 6b – Odběry interpretů.** Načíst stav, přihlásit/zrušit odběr, ověřit a obnovit přehled.
8. **C8 / 6c – Odkazy.** Kopírovat a otevřít v YTM podporované veřejné položky. Uploadům nevyrábět neplatný veřejný odkaz.

### D. Session a přihlášení (8)

1. **8a – Obnova přehrávání.** Uchovat frontu, přesné výskyty, aktuální skladbu/pozici, repeat/shuffle/radio a potřebný zdrojový kontext. Nabídnout pokračování nebo odmítnutí; nic automaticky nepřehrávat ani nepřipojovat Cast. Využít `save_resume_session` / `load_resume_session`, ověřit kompatibilitu/oddělení CLI a GUI uloženého stavu a neukládat zbytečně rozkopírované snapshoty modelů u každé skladby.
2. **8b – Přihlášení z GUI.** Zapojit existující izolovaný login `AuthManager`; odstranit závislost uživatelského postupu na textovém `input`/CLI menu. Nabídnout obnovu přihlášení při neplatné session, průběh, chybu a zrušení. Přihlašovací data ponechat mimo Git.

Autentizační session a obnovení přehrávání jsou dvě různé věci. Přihlášené GUI dnes neznamená uloženou frontu po restartu.

### E. Cast (10)

1. **10a – Ruční discovery a výběr.** Místní výstup, Chromecast Audio a Cast Groups, aktuální dostupnost. Startup zůstává lokální.
2. **10b.1 – Local → Cast.** Převzít `switch_playback_output`, ověřit stejnou skladbu, pozici, pause/play, hlasitost a že starý výstup současně nehraje.
3. **10b.2 – Cast → Local.** Samostatný skutečný test včetně přípravy lokálního audia.
4. **10b.3 – Cast1 → Cast2 / skupina.** Samostatný skutečný test se zařízeními uživatele.
5. **10c – Odpojení a výpadky.** Stav zařízení, dlouhá pauza, obnova spojení, aktualizace discovery, nefunkční/zmizelý výstup a ukončení aplikace.
6. **10d – Celek.** Fronta, repeat/shuffle a průběžné rádio míří na zvolený výstup. MPRIS se doplní až v následujícím posledním funkčním kroku. Cast používá svůj streamovací postup CLI; lokální cache/prefetch nezapojovat mechanicky stejným způsobem.

Cast už v CLI funguje. Chybí propojení s GUI a ověření jeho nových funkcí, nikoli vymyšlení přepínání výstupů od začátku.

### F. MPRIS (9)

1. Lokální Play/Pause/PlayPause/Stop/Next/Previous, metadata, cover, délka, pozice a dostupné seek/volume/repeat/shuffle podle podporovaného rozhraní.
2. Ověřit KDE, fyzické multimediální klávesy a skutečná Bluetooth sluchátka. Systém i GUI ovládají jeden stav přehrávání.
3. Cast je již zapojený; ověřit stejné systémové ovládání pro aktuální lokální i Cast výstup.

MPRIS není hotová funkce referenční CLI; jde o novou systémovou integraci.

### G. Desktop 1.0 (11)

1. **11a – Kontrola celku.** Velké kolekce, nedostupné skladby, duplicity, chyby sítě/účtu, opakované akce, opožděné výsledky, ukončení během práce, kombinace všech přijatých funkcí a reálný Cast.
2. **11b – Vzhled a instalace.** Celková revize menu/rozložení a klávesnice, texty a chyby, ikona, desktopový spouštěč a ověřený instalační postup se závislostmi. Formu distribučního balíčku zvolit před touto etapou.
3. **11c – Příprava vydání.** README, známá omezení, přijatý kandidát, čistý Git, release commit/tag a instalační výstup. Publikace až na samostatný pokyn.

## Dokončený bod 7 a další náměty

**7a–7d jsou hotové:** skladba/kolekce do existujícího či nového playlistu, politika duplicit, prázdný playlist, název/popisy/viditelnost, jednotlivé odebrání podle setVideoId se synchronizací fronty, přesun nahoru/dolů včetně celé původní fronty a potvrzené smazání vlastního playlistu při zachování audia. Poslední commit `99dcad6`.

Multivýběr, dvojklik/Enter, dávkové vkládání/ukládání, lišta od dvou vybraných a odznačení po úspěchu jsou rovněž hotové (`142bb2d`).

Hromadné odebrání z playlistu a přetahování myší jsou **další rozšíření**, nikoli nedodělky původního přijatého rozsahu bodu 7. Hromadné odebrání bylo mezitím implementované, skutečně přijaté a uložené v c0c5ccf. Přetahování myší zůstává námětem.

## Mimo desktopovou 1.0

- Trvalé offline stahování, správa stažené knihovny a přehrávání bez sítě. Ani referenční CLI nemá hotovou takovou offline knihovnu; dočasné stažení/cache pro přehrání je jiná funkce.
- Sailfish OS / Silica port s vlastní ergonomií, audio a systémovou integrací; použít stabilní datovou logiku desktopu.
- Vyřazené nápady zůstávají vyřazené: připínání do „Poslouchejte znovu“, poděkování u skladby a podobné nepoužívané doplňky. Počty přehrání nejsou podmínkou 1.0.
