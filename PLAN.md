# FelisMusic Desktop – plán do verze 1.0

Výchozí stav: uživatelem otestovaná **0.3.3.5-dev**, commit **7f3f704**.
Plán schváleného rozsahu z 2026-10-24. Jednotlivé kroky níže dosud nejsou implementované, pokud STATUS.md neříká jinak.

## Cíl a hranice

- Desktopová 1.0 pro Linux: běžné přehrávání, shuffle/repeat, fronta, rádio, práce s knihovnou a playlisty, obnova session, MPRIS a Cast.
- Převzít ověřenou logiku CLI, zejména shuffle, rádio, obnovu session a přepínání výstupů. Vyvíjíme jejich propojení s GUI; nepíšeme fungující mechanismy znovu.
- Start vždy na lokálním výstupu. Cast hledat až po otevření výběru výstupu / ručním obnovení.
- Trvalé offline stahování až po 1.0. Přednačítání a dočasná cache zůstávají součástí běžného přehrávání.
- Vyřazeno: připínání do „Poslouchejte znovu“ a poděkování u skladby. Počty přehrání a podobné doplňky nejsou podmínkou 1.0.
- Sailfish port následuje po stabilním desktopovém základu jako samostatná etapa.

## Jak budeme pracovat

1. Vybereme jeden níže uvedený podkrok. Před změnami aplikace uživatel potvrdí její zavření.
2. Klára implementuje daný podkrok, ověří ho přiměřenými kontrolami a napíše konkrétní postup uživatelského testu.
3. Michal otestuje skutečný účet, zvuk a zařízení; chyby stejného podkroku opravíme před pokračováním.
4. Po přijetí aktualizujeme STATUS a dokumentaci, připravíme příkaz pro commit. Git zápis zatím provádí Michal a pošle výsledek; Klára ověří stav.
5. Každý samostatně přijatý podkrok může mít vlastní commit. Čísla vývojových verzí přidělujeme podle skutečně dokončeného obsahu.

## 1. Repeat, potom Shuffle

**1a – Repeat:** vypnuto / celý seznam / jedna skladba. Jednoznačně ukázat režim v přehrávači. Repeat-one opakuje při dohrání, ruční Next/Previous přejdou na sousední skladbu bez obalení seznamu. Repeat-all obaluje seznam při dohrání i ručním přechodu. Hotovo v 0.3.4-dev, uživatel ověřil a přijal 2026-10-25, uloženo v commitu `0a9b50c`.

**1b – Shuffle:** zapojit náhodné přehrávání přes YTM z CLI. Nabídnout ho u podporovaných zdrojů a zachovat výjimku pro nepodporované playlisty `RDCLAK…`. Vyjasnit přepnutí režimu za běhu a návrat k původnímu pořadí; upravit přednačítání podle skutečné následující skladby.

Na výslovný pokyn uživatele z 2026-10-25 odložené; po Repeat jsme přešli ke kroku 2. Shuffle tím není zrušené ani dokončené.

**Přijetí:** dohrání poslední skladby, opakování jedné, ruční Next/Previous a nové pořadí fungují konzistentně. U nepodporovaných zdrojů nevzniká nefunkční ovladač ani tichá náhrada jiným typem shuffle.

## 2. Samostatná Fronta a Info

Hotovo v 0.3.5-dev, uživatel ověřil a přijal 2026-10-25, uloženo v commitu `f04c01b`. Aktuální podrobnosti v STATUS.md.

**2a – Fronta:** samostatný pohled na skutečné pořadí přehrávání, označení aktuální skladby, pozice například `17 / 133`, vlastní scroll a výběr skladby.

**2b – Info:** název, interpret, album, délka, hodnocení a pozice ve frontě. Přidat uživatelské Stop s jasným zastaveným stavem.

Cover nadále vrací původní kolekci s původní navigací. Fronta ukazuje aktuální pořadí, které se po shuffle nebo vložení položek může od kolekce lišit. Zvýrazňování nesmí spoléhat jen na původní index řádku.

**Přijetí:** procházení jiné kolekce nemění frontu; skok, Next a shuffle označují správné položky. Stop zastaví audio, Play má předem určené chování po zastavení.

## 3. Kontextová menu a úpravy fronty

**3a – Skladba:** nabídka „⋮“ a pravé tlačítko, Přehrát jako další, Přidat na konec fronty, Info a dostupné hodnocení.

První dílčí etapa je uživatelsky ověřená v 0.3.6-dev: nabídka Přehrát jako další / Přidat na konec fronty, včetně zachování navigace ve smíšené frontě. Uživatel potvrdil vkládání do fronty; na jeho návrh byla odstraněna duplicitní akce Přehrát odtud. Upravené menu je také uživatelsky potvrzené; uloženo v commitu `a284740`. Další akce nabídky a následující podkroky dosud nejsou hotové.

**3b – Kolekce:** Přehrát, Náhodně, celou kolekci přehrát jako další nebo přidat na konec. Akce přidá skladby ve správném pořadí a nepřeruší aktuální audio.

**3c – Fronta:** odebrání čekající položky a změna pořadí. Předem určit chování při zásahu do aktuální položky; bezpečně aktualizovat indexy i přednačítání.

**Přijetí:** „jako další“ znamená hned za aktuální skladbu, „do fronty“ znamená na konec. Duplicitní výskyty stejné skladby se dají rozlišit. Menu obsahuje jen skutečně zapojené a dostupné akce.

## 4. Detail interpreta a dokončení detailů kolekcí

Na výslovný pokyn uživatele jsme po skladbovém menu přešli ke kroku 4. Zbývající části kroku 3 zůstávají plánované.

V 0.3.7-dev je první podkrok 4a uživatelsky otestovaný a přijatý (commit `635fb27`): části interpreta s automatickým načtením celých dostupných seznamů, výchozím řazením A–Z a volbou dalších pořadí, otevření alba a návrat k interpretovi. Přehrávání skladeb z řádků funguje stávajícím způsobem; samostatné akce pro celou kolekci, Shuffle a Mix zůstávají navazující práce.

**4a – Interpret:** nejposlouchanější skladby, dostupné rozšíření seznamu, alba a singly/EP. Nabídky Přehrát/Náhodně podle dostupného zdroje; Mix dopojit v následujícím kroku.

**4b – Album/playlist:** přehledná hlavička s coverem, názvem, interpretem či autorem, rokem a počtem/délkou skladeb, pokud jsou data dostupná. Ověřit úplnost obsahu a případné stránkování.

**4c – Navigace:** ze skladby otevřít její album nebo interpreta, z alba interpreta. Podporovat více interpretů a korektní návrat zpět. Chybějící ID případně doplnit datovým dotazem; nevytvářet odkazy odhadem podle názvu.

**Přijetí:** procházení detailů nemění přehrávání; cover stále vrací skutečný původ aktuální kolekce. Nahraná hudba používá své soukromé identifikátory a dostupné akce.

## 5. Rádio / Mix

Uživatel výslovně zvolil krok 5 po přijetí podkroku interpreta; 4b/4c zůstávají otevřené. V 0.3.8-dev je uživatelsky otestovaný a přijatý podkrok 5a (commit `635fb27`): Mix ze skladby přes CLI rádio, zachování audia aktuálního seedu, přesměrování přednačítání a pojistky proti opožděným výsledkům. Zatím jeden blok doporučení; 5b/5c následují samostatně.

**5a – Aktuální nebo vybraná skladba:** zapojit vytvoření rádia z CLI a ukázat, že se přehrává rádio.

**5b – Doplňování:** průběžně načítat další bloky, filtrovat duplicity a spolupracovat s přednačítáním. Dočasná chyba doplnění nesmí přerušit aktuální skladbu nebo neustále opakovat požadavky.

**5c – Interpret a kolekce:** dopojit Mix tam, kde je podporovaný a máme potřebné identifikátory. Mixy pro vás již fungují; nemíchat jejich otevření s vytvářením nového rádia.

**Přijetí:** rádio přehraje více doplněných bloků bez konce na původní dávce. Fronta, aktuální skladba a přepnutí zpět na běžný playlist zůstávají konzistentní.

## 6. Knihovna, odběry a odkazy

Na výslovný pokyn uživatele jsme po commitu `635fb27` přešli ke kroku 6. Podkroky 5b/5c a dříve nedokončené části plánu zůstávají otevřené. V 0.3.9-dev je uživatelsky otestovaná a přijatá první část 6a (commit `c3de56b`): přímá akce Přidat/Odebrat v menu skladby podle skutečného členství, nezávislé načítání stavu bez blokování ostatních akcí, změna přes feedback tokeny a ověření výsledku bez změny hodnocení nebo fronty. Původní dialog uživatel otestoval. Finální varianta skrývá knihovní položku do potvrzení dostupné akce, při nedostupnosti ji vůbec nezobrazuje a doplňuje předání ID alba skladbám; uživatel potvrdil shodu s webovým YTM křížovým testem. Alba a playlisty jsou následující část 6a; odběry a odkazy 6b/6c zatím nehotové.

**6a – Knihovna:** přidání/odebrání podporovaných skladeb, alb a playlistů. Rozlišovat hodnocení Like/Dislike, členství v knihovně a členství v playlistu.

**6b – Interpret:** odebírat / zrušit odběr a správně ukázat aktuální stav.

**6c – Sdílení:** kopírovat odkaz a otevřít v YT Music u položek s vhodným odkazem.

**Přijetí:** změny se ověří proti skutečnému YTM a promítnou do příslušné části GUI. Při chybě se stav vrátí nebo se zobrazí jasné selhání. Soukromým uploadům se nevyrábí neplatný veřejný odkaz.

## 7. Správa playlistů – součást 1.0

Na výslovný pokyn uživatele po commitu `c3de56b` přecházíme ke kroku 7. V 0.3.10-dev je uživatelsky otestovaná a přijatá první část 7a (commit `cb4ce81`): uložení jedné skladby do vlastního playlistu, výslovná volba duplicit a vytvoření nového soukromého playlistu se skladbou. Po skutečném testu vytvoření playlistu opravené následné ověřování (omezené opakování čtení, rozlišení potvrzeného zápisu a neověřeného obsahu, ruční Ověřit znovu bez opakování zápisu); uživatel ověřil vytvoření i přidávání včetně duplicit. Následně upravené automatické zavírání po ověřeném úspěchu a výrazné potvrzení duplicity přes OK uživatel také ověřil a přijal. V 0.3.11-dev je uživatelsky otestovaná a přijatá druhá část 7a (čeká na commit): uložení právě otevřeného seznamu skladeb do vlastního či nového soukromého playlistu, s počtem výběru, pořadím a dávkovou politikou duplicit. Obecná tvorba/prázdný playlist, úpravy údajů, pořadí/odebírání a smazání zatím neimplementované. Zbývající části kroku 6 a dřívějšího plánu zůstávají otevřené.

**7a – Přidávání:** dialog pro výběr vlastního editovatelného playlistu, přidání skladby i celé kolekce; možnost vytvořit nový playlist přímo při ukládání. Výslovně vyřešit duplicity.

**7b – Vytvoření a úprava údajů:** název, popis a viditelnost u podporovaných vlastních playlistů.

**7c – Obsah:** odebrání konkrétního výskytu skladby a přesun pořadí. Uchovávat potřebné identifikátory položek playlistu, nikoli jen videoId, aby šlo bezpečně pracovat i s duplicitami.

**7d – Smazání:** pouze u vlastního editovatelného playlistu a s potvrzením. U cizích a automatických playlistů nabídnout jen dostupné akce; odebrání z knihovny nesmí být prezentované jako smazání playlistu.

Úprava uloženého playlistu se nesmí nečekaně promítnout jako přestavění právě hrající fronty. Fronta a uložený playlist jsou dvě různé věci.

**Přijetí:** na testovacím vlastním playlistu projít vytvoření, přidání, duplicity, přesun, odebrání, přejmenování i smazání a změny ověřit v YTM. Prověřit nedostatečná oprávnění a chybu sítě.

## 8. Obnova session a přihlášení

**8a – Session:** uložit frontu, aktuální skladbu, pozici, repeat/shuffle a potřebné informace o zdroji. Po restartu nabídnout pokračování, nic automaticky nespouštět.

**8b – Přihlášení:** zapojit osvědčený způsob autentizace z CLI do ovladatelného GUI postupu, včetně srozumitelného stavu neplatné session. Desktopová 1.0 nemá vyžadovat ovládání samostatné CLI aplikace pro běžné přihlášení.

**Přijetí:** po restartu lze pokračovat i odmítnout; změněný nebo nedostupný zdroj nezpůsobí pád. Start zůstává lokální a neobnovuje automaticky spojení s Castem. Přihlašovací údaje zůstávají mimo Git.

## 9. MPRIS / systémové ovládání

Play, Pause, PlayPause, Next, Previous, metadata, cover, délka a správné stavy. Doplnit podporované další ovládání podle možností backendu. Ověřit KDE a Bluetooth sluchátka / multimediální klávesy.

**Přijetí:** systém i GUI ovládají tentýž přehrávač a zobrazují shodný stav. Připravit rozhraní tak, aby stejné příkazy po zapojení Castu mířily na zvolený výstup.

## 10. Cast – převzetí fungující logiky CLI

**10a – Výběr výstupu:** ručně vyvolané discovery, lokální zařízení, Chromecast Audio a Cast Groups. Stav dostupnosti a aktuálně zvolený výstup.

**10b – Přehrávání a přepínání:** propojit ověřené funkce CLI pro Local ↔ Cast a Cast1 ↔ Cast2, včetně pozice, hlasitosti a pauzy. Jednotlivé přechody testovat postupně.

**10c – Stav a odpojení:** ztráta zařízení, dlouhá pauza a usnutí session, kontrola živosti a opětovné připojení. GUI nesmí ukazovat připojení, které už nefunguje.

**10d – Celková integrace:** ověřit frontu, repeat/shuffle, rádio, systémová tlačítka a MPRIS pro aktuální výstup. Lokální cache/přednačítání používat jen tam, kde má význam pro daný výstup.

**Přijetí:** reálné přechody mezi Kočičkou a Casty zachovají skladbu, přibližnou pozici a stav přehrávání. Při startu aplikace se žádný Cast sám nevyhledává ani nepřipojuje.

## 11. Příprava a vydání desktopové 1.0

**11a – Kontrola celku:** projít scénáře z předchozích etap, velké kolekce, opakovaná kliknutí, výpadek sítě, nedostupné skladby, chyby účtu a ukončení během načítání.

**11b – Použitelnost a instalace:** zkontrolovat rozložení oken, klávesové ovládání, popisky a chybové zprávy; doplnit ikonu, desktopový spouštěč a ověřený postup instalace se závislostmi. Konkrétní distribuční balíček zvolit před touto etapou.

**11c – Vydání:** aktuální README, seznam známých omezení, uživatelsky přijatý kandidát, čistý Git, release commit/tag a připravený instalační výstup. Publikaci provést až na samostatný pokyn.

**Přijetí:** běžné používání nevyžaduje zásahy do kódu ani CLI přehrávač a nedochází k regresi ověřeného přehrávání nebo Castu.

## Po 1.0

- Podle skutečného zájmu trvalé offline stahování: správa místa, souborů, metadat a přehrávání bez sítě. Není podmínkou první verze.
- Další vylepšení podle zkušeností z používání.
- Sailfish OS / Silica port s využitím již ověřené funkční logiky; vlastní rozložení, audio a systémová integrace pro Jollu.
