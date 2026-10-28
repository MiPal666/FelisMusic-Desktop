# FelisMusic Desktop – aktuální plán do 1.0

**0.3.44-dev:** opraven návrat coverem z Mixu playlistu/alba/interpreta (také hlavních Oblíbených) do původního zdroje, včetně doporučení z dalších bloků. Obnoví detail/záložku bez restartu audia. 372 offline testů a šest QML scénářů prošlo. Michal potvrdil celek 0.3.42–0.3.44 jako otestovaný a funkční; připraveno ke společnému commitu.

**0.3.43-dev:** domluvené pravidlo RD… pro dynamické zdroje. Playlisty i Mixy pro vás načtou stejnou cestou první watch blok; pokračování stejného ID až podle postupu poslechu, s EOS/Stop/pauzou/Repeat a odstupem při výpadku. Pevné seznamy dál celé po blocích. 371 offline testů a 4 QML scénáře prošly; navíc dva skutečné read-only bloky Supermixu 24+24 s pokračováním. Čeká na reálný poslech/test, necommitováno spolu s 0.3.42. Poslední commit 0bc66cb.

**0.3.42-dev:** playlistové detaily včetně „Liked Music“ mají první blok a background doplnění stejně jako hlavní Oblíbené. Běžné přehrávání z prefixu rozšiřuje tutéž konečnou frontu; akce nad celkem až po dokončení. Ochrany EOS/Repeat/Stop, chyby, cover a zneplatnění. Výjimka obnovy s čekajícím přesunem: úplné načtení pro porovnání. 355 offline testů + QML dvojklik při načítání v obou velikostech prošly; čeká na Michalův reálný test. Předchozí commit 0bc66cb. Potom samostatně Nahrané a podle dostupných endpointů další velké kolekce.

**Doplněný samostatný krok – Nahrané:** lokální náhodné přehrávání nahraných skladeb, alb a skladeb interpreta. Možnosti Mixu nahraných zdrojů nejprve ověřit podle skutečných možností API; podporu zatím neslibovat a nenahrazovat ji potichu katalogovou skladbou. Implementace dosud nezačala.

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
| **4. Detaily a navigace** | **4a hotovo:** interpret – dostupné úplné skladby/alba/singly/EP, řazení, otevření alba a návrat. Kompaktní hlavičky hotové. | **4b:** dostupná metadata hlaviček. **4c:** přímé přechody skladba → album/interpret a album → interpret. |
| **5. Rádio / Mix** | **5a hotovo:** mix z jedné skladby, první blok doporučení. Mixy pro vás lze načíst a otevřít. | **5b / B1 hotovo:** uživatelsky přijato v 0.3.24-dev. **5c / B2:** Mix/Náhodně interpreta přijaté v 0.3.25. **B3:** Mix alba/playlistu přes ⋮ skutečně ověřený 2026-10-27; doplnění Oblíbené hudby v 0.3.29 čeká na test. |
| **6. Knihovna a odběry** | Přímé přidání/odebrání podporované skladby v knihovně hotové. | **6a zbytek:** alba/playlisty. **6b:** odběry interpretů. **6c:** kopírování/otevírání odkazů. |
| **7. Správa playlistů** | **7a–7d hotové, uživatelsky přijaté a commitnuté.** | Další náměty: hromadné odebrání a přetahování; nezpochybňují dokončení domluveného rozsahu 7a–7d. |
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

### E. MPRIS (9)

1. Lokální Play/Pause/PlayPause/Stop/Next/Previous, metadata, cover, délka, pozice a dostupné seek/volume/repeat/shuffle podle podporovaného rozhraní.
2. Ověřit KDE, fyzické multimediální klávesy a skutečná Bluetooth sluchátka. Systém i GUI ovládají jeden stav přehrávání.
3. Po zapojení Castu zopakovat integraci pro aktuální výstup.

MPRIS není hotová funkce referenční CLI; jde o novou systémovou integraci.

### F. Cast (10)

1. **10a – Ruční discovery a výběr.** Místní výstup, Chromecast Audio a Cast Groups, aktuální dostupnost. Startup zůstává lokální.
2. **10b.1 – Local → Cast.** Převzít `switch_playback_output`, ověřit stejnou skladbu, pozici, pause/play, hlasitost a že starý výstup současně nehraje.
3. **10b.2 – Cast → Local.** Samostatný skutečný test včetně přípravy lokálního audia.
4. **10b.3 – Cast1 → Cast2 / skupina.** Samostatný skutečný test se zařízeními uživatele.
5. **10c – Odpojení a výpadky.** Stav zařízení, dlouhá pauza, obnova spojení, aktualizace discovery, nefunkční/zmizelý výstup a ukončení aplikace.
6. **10d – Celek.** Fronta, repeat/shuffle, průběžné rádio, MPRIS a systémové ovládání míří na zvolený výstup. Cast používá svůj streamovací postup CLI; lokální cache/prefetch nezapojovat mechanicky stejným způsobem.

Cast už v CLI funguje. Chybí propojení s GUI a ověření jeho nových funkcí, nikoli vymyšlení přepínání výstupů od začátku.

### G. Desktop 1.0 (11)

1. **11a – Kontrola celku.** Velké kolekce, nedostupné skladby, duplicity, chyby sítě/účtu, opakované akce, opožděné výsledky, ukončení během práce, kombinace všech přijatých funkcí a reálný Cast.
2. **11b – Vzhled a instalace.** Celková revize menu/rozložení a klávesnice, texty a chyby, ikona, desktopový spouštěč a ověřený instalační postup se závislostmi. Formu distribučního balíčku zvolit před touto etapou.
3. **11c – Příprava vydání.** README, známá omezení, přijatý kandidát, čistý Git, release commit/tag a instalační výstup. Publikace až na samostatný pokyn.

## Dokončený bod 7 a další náměty

**7a–7d jsou hotové:** skladba/kolekce do existujícího či nového playlistu, politika duplicit, prázdný playlist, název/popisy/viditelnost, jednotlivé odebrání podle setVideoId se synchronizací fronty, přesun nahoru/dolů včetně celé původní fronty a potvrzené smazání vlastního playlistu při zachování audia. Poslední commit `99dcad6`.

Multivýběr, dvojklik/Enter, dávkové vkládání/ukládání, lišta od dvou vybraných a odznačení po úspěchu jsou rovněž hotové (`142bb2d`).

Hromadné odebrání z playlistu a přetahování myší jsou **další rozšíření**, nikoli nedodělky původního přijatého rozsahu bodu 7. Jejich prioritu domluvit samostatně; samy teď neblokují návrat ke Shuffle a Mix/Rádiu.

## Mimo desktopovou 1.0

- Trvalé offline stahování, správa stažené knihovny a přehrávání bez sítě. Ani referenční CLI nemá hotovou takovou offline knihovnu; dočasné stažení/cache pro přehrání je jiná funkce.
- Sailfish OS / Silica port s vlastní ergonomií, audio a systémovou integrací; použít stabilní datovou logiku desktopu.
- Vyřazené nápady zůstávají vyřazené: připínání do „Poslouchejte znovu“, poděkování u skladby a podobné nepoužívané doplňky. Počty přehrání nejsou podmínkou 1.0.
