# FelisMusic Desktop – aktuální plán do 1.0

Aktualizováno: **2026-10-26 (Europe/Prague)** po porovnání kódu GUI, původní CLI reference `tmp/felismusic.py` a převzatého `desktop/felismusic_gui/legacy_core.py`.

Aktuální uživatelsky přijatá verze: **0.3.23-dev** (A2 přijato 2026-10-26; připraveno ke commitu). Předchozí úprava Repeat je uložená v commitu **`6272381`**. Shuffle A1 je uložený v commitu **`2c51536`**. Poslední ověřování: **212 offline testů**, QML 1280×800/900×600 a skutečné uživatelské testy YTM. Historie změn a přijetí je v [STATUS.md](STATUS.md); věcné porovnání funkcí v [CLI-GUI.md](CLI-GUI.md). Tento plán popisuje současný stav, nikoli postupně zastarávající historické mezistavy.

**A1 přijato uživatelem a commitnuto:** náhodné spuštění playlistu/alba, Repeat, přechody a návrat přes cover ověřené ve skutečném YTM. Kolekce zachovává své řazení, Fronta ukazuje skutečné pořadí přehrávání; toto chování uživatel výslovně chce zachovat.

Přijato uživatelem **0.3.21-dev**: Repeat patří k aktuální frontě. Nové přehrávání z kolekce/vyhledávání, nový Shuffle či rádio jej vypne až při úspěšném vytvoření fronty. Pohyb uvnitř fronty, procházení, cover, Pause/Play, Stop/Play a vkládání skladeb jej zachovají. Skutečný uživatelský test potvrdil funkčnost. Následují A2 a Rádio jako samostatné podkroky.

Přijato uživatelem **0.3.23-dev / A2**: tlačítko **Fronta → Zamíchat**, zachování aktuálního audia/času/pauzy/Repeat a přesných výskytů. Pořadí kolekční části určuje YTM; ruční položky se lokálně promíchají a náhodně rozptýlí mezi kolekční část. Michal potvrdil funkčnost po několika ručních testech. Další podkrok: B1 – průběžné doplňování Rádia/Mixu.

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
| **5. Rádio / Mix** | **5a hotovo:** mix z jedné skladby, první blok doporučení. Mixy pro vás lze načíst a otevřít. | **5b:** automatické doplňování. **5c:** Mix/Náhodně interpreta a podporované akce kolekcí. |
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

1. **B1 – Průběžné doplňování mixu ze skladby.** Dopojit mechanismus `refill_radio_queue` / `maybe_refill_radio_queue`: načítat před koncem fronty, další blok seedovat vhodnou poslední skladbou, filtrovat již přítomné/nepoužitelné výsledky. Operaci provádět mimo UI vlákno, zachovat audio, aktualizovat frontu a prefetch. Zrušit nebo ignorovat starý výsledek při změně zdroje. Při chybě omezený další pokus, nikoli opakování v každém pollu.
2. **B2 – Mix a Náhodně interpreta.** Uchovat YTM `radioId`/`shuffleId`, které GUI dosud nevyužívá. Převzít datovou logiku `artist_action_queue`. Rádio interpreta musí spolupracovat s doplňováním B1.
3. **B3 – Dostupné mixy kolekcí a sjednocení jejich chování.** Nabídnout akci tam, kde YTM skutečně vrací vhodný zdroj. Rozlišovat otevření existujícího „Mixu pro vás“, vytvoření rádia a konečný playlist. U dynamických mixů ověřit vhodný způsob pokračování; neslibovat neomezené přehrávání každému obyčejnému playlistu.

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
