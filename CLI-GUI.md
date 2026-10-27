# FelisMusic – porovnání CLI a Desktop GUI

**0.3.40-dev:** Michal ověřil lokální Shuffle interpreta; menu sjednoceno na Přehrát náhodně → Spustit mix, stejně jako u alb/playlistů. Přehrávací logika se v této drobné úpravě nemění.

**0.3.39-dev:** lokální Shuffle interpreta nad již načtenou sekcí Skladby, všechny dostupné výskyty, bez watch požadavku/limitu Mixu. Cover zachovává původní záložku. Mix/refill nezměněny. Čeká na skutečný test; potom lokální přemíchání aktuální fronty a stránkování playlistových detailů. Album uložené v e408639.

**0.3.38-dev:** připravené lokální Shuffle alb nad celým již načteným seznamem, shodnou cestou jako playlisty. Mix/refill beze změny. Michal skutečným testem přijal; po commitu zvlášť interpret, přemíchání fronty a stránkování detailů playlistů. Předchozí celek uložen v 1bdf196.

**0.3.37-dev:** opraveno kvadratické kopírování zdrojového seznamu při přípravě hlavních Oblíbených (společný deepcopy memo, zachované indexy/izolace/cover). 346 offline testů a obě QML velikosti prošly, Michal skutečným testem potvrdil funkčnost i opravu pomalé přípravy. Načítání detailů playlistů po blocích zatím neměněno.

**0.3.36-dev:** lokální Shuffle nyní také v hlavních Oblíbených, až po dokončení jejich seznamu; zachovává přesné výskyty a návrat přes cover. 344 offline testů a QML v obou velikostech prošlo, čeká na skutečný test. Další samostatné kroky: alba, interpreti, přemíchání fronty. Mix/refill beze změny.

**Aktuální podkrok 2026-10-27 / 0.3.35-dev:** po prokázaném cyklu serverového Shuffle je připravené lokální „Přehrát náhodně“ pouze v detailu playlistu, nad celým již načteným seznamem se zachováním přesných výskytů. 339 offline testů a QML 900×600/1280×800 prošlo; čeká na Michalův test. Potom samostatně alba, Oblíbené, interpreti a přemíchání fronty. Mix/Rádio beze změny. P3 zatím nezahajovat.

Audit: **2026-10-26**, Desktop **0.3.19-dev**, přijatý commit **`99dcad6`**. Audit je porovnání zdrojového kódu; nové testy zařízení ani zápisy do YTM se při něm neprováděly.

Referenční zdroje: lokálně dodaná původní CLI `tmp/felismusic.py`, převzaté jádro [legacy_core.py](desktop/felismusic_gui/legacy_core.py), GUI [backend.py](desktop/felismusic_gui/backend.py) a [Main.qml](desktop/Main.qml). `tmp/felismusic.py` je lokální reference, nikoli instalační soubor aplikace. Aktuální pořadí dalších prací určuje [PLAN.md](PLAN.md), historie a uživatelská přijetí jsou v [STATUS.md](STATUS.md).

Navazující změna **0.3.20-dev**: A1 Shuffle playlistu/alba je automaticky i uživatelsky ověřené a přijaté v commitu `2c51536`. Níže je tato položka aktualizovaná; ostatní závěry auditu zůstávají platné.

**0.3.23-dev / A2**: zamíchání existující fronty je implementované a uživatelsky přijaté. Oproti destruktivnímu nahrazení zbytku v CLI zachovává přesné GUI výskyty i ručně přidané položky a YTM používá jako zdroj pořadí kolekční části. Ruční výskyty se navíc lokálně promíchají a rozmístí mezi ni.

**0.3.24-dev / B1**: průběžné doplňování skladbového mixu je implementované přes CLI `refill_radio_queue` nad snapshotem fronty a uživatelsky přijaté.

**0.3.25-dev / B2**: Mix i Náhodně interpreta jsou implementované přes CLI `artist_action_queue`, s přímými radioId/shuffleId a menu ⋮ na všech kartách interpreta. Uživatelsky přijato; mix využívá průběžné doplňování B1.

**0.3.26-dev / B3**: Mix alba/playlistu je implementovaný přes RDAMPL + zdrojové audioPlaylistId/playlistId, s doplňováním B1 a menu ⋮. Michal 2026-10-27 potvrdil opakované doplňování mixů.

**0.3.29-dev**: návrat coverem ke kartě interpreta po Shuffle a menu Náhodně/Mix pro Oblíbenou hudbu (LL/RDAMPLLL). 271 offline testů a QML kontroly; nové úpravy čekají na skutečný test.

**0.3.30-dev / P1:** Oblíbené se načítají po skutečných pokračovacích stránkách bez limitu 2000; první blok je vidět dříve, zbytek neblokuje globální busy. Do dokončení jsou akce vypnuté. Nová etapa čeká na test; rychlý start přehrávání a další kolekce navazují samostatně. Úpravy 0.3.29 byly uživatelem potvrzené.

**0.3.32-dev / P2a:** normální přehrávání z prvního bloku Oblíbených a doplňování související fronty bez restartu, EOS čekání/Stop a označení neúplnosti. 300 offline testů a QML; čeká na skutečný test. Rychlý Shuffle/ostatní kolekce stále navazují samostatně.

**0.3.33-dev / P2b:** start náhodné fronty už po prvním serverovém bloku pro album/playlist/LL/interpreta, další stránky přes původní watch continuation. Zachován konečný počet podle původního cíle, pořadí YTM, výskyty/cover a EOS/Stop/Repeat. 319 offline testů a QML; čeká na skutečný test. A2 a dostupnost menu při načítání zdrojových dat se nemění; prohlížení dalších kolekcí je P3.

## Co skutečně chybí v GUI oproti fungující CLI

| Funkce | CLI reference | GUI nyní | Co je třeba dopojit |
|---|---|---|---|
| YTM Shuffle kolekce | Ano: `get_youtube_shuffle_tracks`, `collection_queue_menu`. U alba používá audioPlaylistId; nepodporuje `RDCLAK…` a zdroje bez playlistId. | A1 hotovo a uživatelsky přijato v 0.3.20-dev (`2c51536`). | A2 hotovo; Shuffle interpreta přijaté v B2. |
| Zamíchání běžící fronty | Ano: `apply_youtube_shuffle` zachová aktuální skladbu a zamíchá zbytek. | A2 hotovo a uživatelsky přijato v 0.3.23-dev. | Ověřené automaticky i uživatelským testem. Jednorázová akce, nikoli návrat přepínačem k původnímu pořadí. |
| Náhodně interpreta | Ano: `artist_action_queue(mode="shuffle")` používá YTM shuffleId. | B2 hotovo a uživatelsky přijato v 0.3.25-dev. | Shoda s webovým YTM ověřená uživatelem; nové pořadí při každém spuštění není zaručené. |
| Mix/Rádio ze skladby | Ano: aktivace a další bloky. | První blok i B1 doplňování přijaté v 0.3.24-dev. | Skutečně ověřené dva navazující bloky; další zdroje mixů samostatně. |
| Doplňování rádia | Ano: `refill_radio_queue` / `maybe_refill_radio_queue`, seed poslední skladbou, filtr duplicit, odklad při chybě. | B1 implementované v 0.3.24-dev: CLI refill na oddělené kopii, připojení na UI vlákně, single-flight, odklad chyb, ochrana výsledku. | Uživatelsky přijaté doplňování více bloků; prefetch a čekání na konci ověřené také automaticky/QML. |
| Mix/Rádio interpreta | Ano: `artist_action_queue(mode="radio")` používá radioId a radio_active. | B2 uživatelsky přijaté v 0.3.25-dev. | Aktivace ověřená uživatelem; návaznost na B1 automaticky/QML. |
| Obnova přehrávání po restartu | Ano: `save_resume_session`, `load_resume_session`, `offer_resume_session`. | Ne. Shutdown zastaví audio a uklidí cache, frontu k pokračování neukládá. | GUI nabídka pokračování/odmítnutí, fronta/pozice/režimy/kontext; vhodný uložený formát. |
| Přihlášení a obnova přihlášení | Ano: interaktivní `AuthManager`, izolovaný profil podporovaného browseru. | Pouze čtení existujících FCM hlaviček v `initialize`; žádný GUI login postup. | GUI ovládání existujícího loginu a chyb/obnovy session, bez textového menu v běžném použití. |
| Cast a přepínání výstupů | Ano: discovery, `OutputState`, `refresh_outputs`, `switch_playback_output`, obsluha stavu/odpojení. | Pouze Local/GStreamer. | Výběr výstupu a postupné reálné testy Local ↔ Cast ↔ Cast, skupin, pauzy/pozice/hlasitosti, výpadků a úklidu. |
| Diagnostika aktuálního výstupu | CLI Info uvádí také technické údaje výstupu/Castu. | GUI Info řeší aktuální skladbu/frontu a lokální přehrávání. | Smysluplné údaje o zvoleném výstupu doplnit společně s Castem. |

Podstatné: přítomnost CLI kódu v `legacy_core.py` neznamená, že je funkce zapojená v GUI. Naopak pro `AuthManager`, Shuffle, artist_action_queue, radio block/refill, save/load resume, discovery/refresh a switch_playback_output byly při auditu porovnané definice v původní referenci a převzatém jádru a jejich AST se shoduje. Tyto mechanismy skutečně máme k dispozici pro adaptaci; není nutné je vymýšlet od začátku. Jejich textové ovládání a synchronní průběh se ale musí přizpůsobit GUI.

## Co už GUI z CLI funkčně pokrývá

- Hledání YT Music / knihovna / uploady a dostupné typy výsledků, procházení knihovny, playlistů/alb/interpretů, uploadů, profilů s dostupnými epizodami a podcastů.
- Oblíbená hudba a historie, místní přehrávání, Play/Pause/Next/Previous/Stop, seek, hlasitost a mute.
- Repeat off/all/one, zobrazení skutečné fronty/pozice, skok na skladbu a Info aktuální skladby.
- Like/Dislike aktuální skladby a aktualizace souvisejících zobrazení.
- Přehled a otevření „Mixů pro vás“ přes get_home/get_watch_playlist. To není totéž jako automatické doplňování rádia. Ani CLI otevření personalized mixu přes collection_queue_menu samo o sobě neznamená radio_active.
- Datové procházení interpreta, alb a singlů; GUI má navíc dostupné celé části a vlastní řazení.
- Použití existujícího FCM účtu a dočasnou lokální audio cache. GUI má také uživatelsky ověřené přednačtení následující skladby.

„Pokryto“ znamená funkční oblast v rozsahu dat, která API poskytuje, nikoli neomezenou podporu každého typu profilu nebo všech veřejných YTM akcí.

## Co je navíc v GUI nebo v našem plánu, nikoli chybějící CLI funkce

| Oblast | Stav |
|---|---|
| Správa uložených playlistů | **GUI hotovo 7a–7d:** vytvoření, přidávání skladeb/kolekcí, duplicity, název/popisy/viditelnost, přesné odebrání/přesun, smazání s potvrzením a ověřením. Referenční CLI taková editační menu nemá. |
| Multivýběr a dávkové akce | **GUI hotovo:** klik/Ctrl/Shift, dvojklik/Enter, dávkové vložení do fronty a uložení do playlistu, automatické odznačení po úspěchu. CLI prohlížeč fronty nabízí především zobrazení a skok. |
| Samostatná editace přehrávací fronty | **Ještě naplánovaná 3c.** Nezaměňovat se synchronizací po změně uloženého playlistu, která už v GUI funguje. |
| Přímé akce celé kolekce | **3b zbývá:** přehrát/náhodně/jako další/na konec v menu kolekce. Uložení kolekce do playlistu a vkládání multivýběru už funguje. CLI má přehrání od začátku/od vybrané skladby/náhodně, nikoli celou naši budoucí sadu dávkových vkládacích akcí. |
| Knihovní změny a odběry | GUI umí přímé členství podporované skladby v knihovně. Zbývají alba/playlisty a odběry interpretů (6a/6b); toto není hotové editační rozhraní referenční CLI. |
| Odkazy a přímá navigace | Plánované kopírování/otevření odkazů a přechody skladba → album/interpret, album → interpret. Uložené albumId samo o sobě není hotová navigační akce. |
| Metadata hlaviček a menu Info/hodnocení jiné skladby | GUI úpravy navazující na současné hlavičky a Info/hodnocení aktuálního audia; dosud nekompletní (4b a 3a). |
| Mix kolekce dle možností YTM | B3 implementované v 0.3.26-dev, čeká na uživatelský test. CLI explicitně má rádio skladby a interpreta; GUI navíc nabízí Mix celého playlistu/alba přes RDAMPL + playlistId/audioPlaylistId v menu ⋮. Doporučení generuje YTM, pokračování používá B1. |
| MPRIS | Není implementované v referenční CLI ani v GUI; nová desktopová systémová integrace (9). |
| Instalace/spouštěč/release a celková revize vzhledu | Příprava desktopové 1.0 (11), nikoli chybějící přehrávací algoritmus CLI. |
| Hromadné odebrání a drag-and-drop | Další náměty; jednotlivé odebrání a přesun přes menu v bodu 7 jsou hotové. |
| Trvalá offline knihovna | Hotová není v CLI ani GUI. Dočasná cache přehrávaného audia není offline správa hudby. Odloženo po 1.0. |

## Doporučený návrat k přeskočeným bodům

**YTM Shuffle → průběžné Rádio/Mix → Mix/Náhodně interpreta a dostupné kolekční akce → ostatní chybějící části 3/4/6 → Session/přihlášení → MPRIS → Cast → kontrola a vydání 1.0.** Podrobný rozpad na samostatně testovatelné podkroky je v PLAN.md. Programování dalšího kroku až po domluvě a potvrzení zavřené aplikace.
