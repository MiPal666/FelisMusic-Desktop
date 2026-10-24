# FelisMusic – STATUS 2026-10-21

## Účel dokumentu

Tento soubor je předávací / kontinuitní dokument pro projekt **FelisMusic**. Má umožnit navázat v novém chatu bez ztráty kontextu: co je hotové, co bylo reálně otestováno, co je rozpracované, známé problémy, architektura, důležité příkazy a plán dalších verzí.

---

# 1. Projekt ve zkratce

**FelisMusic** je vlastní klient pro **YouTube Music**.

Aktuálně existují dvě větve:

1. **FelisMusic CLI 1.0.0**
   - stabilní referenční verze,
   - považována za samostatný uzavřený projekt,
   - slouží jako referenční implementace funkcí a backendového chování.

2. **FelisMusic Desktop GUI**
   - aktivně vyvíjená verze,
   - Python + PySide6 + Qt/QML,
   - cílem je nejprve plnohodnotný desktopový přehrávač,
   - následně port / adaptace na **Sailfish OS / Jolla Phone 2026**.

---

# 2. Umístění projektu na Kočičce

Hlavní GUI projekt:

```bash
/home/michal/src/FelisMusic
```

Virtualenv:

```bash
/home/michal/src/FelisMusic/env
```

Spuštění:

```bash
cd ~/src/FelisMusic
source env/bin/activate
./run-gui.sh
```

Důležité: virtualenv musí být vytvořen s přístupem k systémovým Python balíkům kvůli PyGObject / GStreamer:

```bash
python3 -m venv --system-site-packages env
```

Pokud je potřeba environment vytvořit znovu:

```bash
cd ~/src/FelisMusic
rm -rf env
python3 -m venv --system-site-packages env
source env/bin/activate
python -m pip install -U pip
python -m pip install -r requirements-gui.txt
```

---

# 3. CLI 1.0.0 – stav

## Stav

**CLI 1.0.0 je považováno za stabilní a uzavřené.**

Původní stabilní CLI odpovídá prakticky verzi 0.0.23 s verzí změněnou na 1.0.0.

Samostatná záloha / projekt:

```bash
~/src/FelisMusic-backup-1.0
```

Po přesunu adresáře přestal fungovat starý `.venv`, protože virtualenv obsahoval původní absolutní cestu. Opraveno vytvořením nového:

```bash
cd ~/src/FelisMusic-backup-1.0
rm -rf .venv
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install pychromecast ytmusicapi yt-dlp
python -m pip install -r requirements-gui.txt
```

Po opravě backup CLI opět fungoval správně včetně lokálního GStreamer výstupu.

## CLI umí

### Účet / session
- přihlášení přes vlastní FCM session,
- zobrazení účtu,
- sdílená konfigurace v `~/.config/felismusic/`.

### Hledání
- Vše
- Skladby
- Alba
- Interpreti
- Playlisty
- Podcasty
- Nahrané soubory

### Knihovna
- Playlisty
- Skladby
- Alba
- Interpreti
- Profily
- Podcasty
- Nahrané soubory

Řazení:
- Nedávno přidané
- A–Z
- Z–A
- Výchozí pořadí YouTube Music tam, kde dává smysl

### Interpreti
- náhodné přehrávání,
- Mix / rádio,
- Top skladby,
- Alba,
- Singly.

### Oblíbená hudba
- kompletní seznam,
- přehrání,
- start od vybrané skladby,
- shuffle.

### Historie
- seznam,
- přehrávání.

### Mixy pro vás
- My Mixy,
- Supermix,
- otevření mixu,
- dynamické skladby přes YTM.

### Přehrávání
- Play
- Pause / Resume
- Stop
- Previous / Next
- automatický přechod na další skladbu
- přeskočení nepřehratelné skladby

### Seek
- ±10 s
- ±30 s

### Hlasitost
- ±5 %
- konkrétní %
- mute / unmute

### Repeat
- off
- all
- one

### Shuffle
- shuffle přes YouTube Music,
- známá výjimka: playlisty s ID začínajícím `RDCLAK...` nemají YTM shuffle spolehlivě podporovaný, takže se shuffle nenabízí.

### Rádio / Mix z aktuální skladby
- vytvoření rádia,
- průběžné doplňování fronty,
- filtrování duplicit,
- prakticky nekonečná fronta.

### Like / dislike
- oblíbená / zrušit,
- neoblíbená / zrušit.

### Fronta
- zobrazení,
- zvýraznění aktuální skladby,
- skok na jinou skladbu.

### Výstupy
- Toto zařízení / GStreamer
- Chromecast Audio
- Cast Group
- přepínání výstupů
- zachování pozice a stavu při přepnutí

### Resume session
- fronta
- aktuální skladba
- pozice
- repeat
- výstup
- nabídka pokračování po restartu bez automatického spuštění.

---

# 4. Známý problém CLI / Cast

Nejde pravděpodobně o chybu samotného FelisMusic, ale o chování Cast session.

Pozorování:
- pokud Chromecast delší dobu nic nepřehrává,
- typicky při delší pauze nebo stopu,
- Cast může spojení / media session ukončit,
- aplikace si ale stále myslí, že je zařízení připojené,
- další příkazy pak odcházejí „do prázdna“ bez chyby,
- nic se nepřehrává,
- pomůže přepnout výstup jinam a zpět.

Rozhodnutí:
- CLI 1.0.0 kvůli tomu nyní neupravovat,
- v GUI řešit reconnect / kontrolu živosti session konstrukčně,
- případný fix později backportovat jako CLI 1.0.1.

---

# 5. Rozdělení CLI a GUI

Rozhodnutí:
- CLI 1.0.0 zůstává samostatné,
- GUI projekt nemá obsahovat spustitelnou CLI aplikaci,
- GUI může dál používat společný / převzatý backendový kód, např. `legacy_core.py`.

Od verze **Desktop 0.2.5-dev**:
- odstraněn adresář `cli/` z GUI projektu,
- odstraněn spodní text `CLI core · 1.0.0`,
- GUI a CLI jsou konceptuálně oddělené.

---

# 6. GUI – architektura

Desktop GUI:
- **PySide6**
- **Qt/QML**
- backend v Pythonu
- lokální audio přes **GStreamer**
- YT Music přes `ytmusicapi`
- audio získávání / cache přes `yt-dlp`
- Cast později přes `PyChromecast`

Přibližná struktura projektu:

```text
FelisMusic/
├── env/
├── desktop/
│   ├── main.py
│   ├── Main.qml
│   └── felismusic_gui/
│       ├── __init__.py
│       ├── backend.py
│       └── legacy_core.py
├── requirements-gui.txt
├── run-gui.sh
└── README.md
```

Autentizace / session:

```text
~/.config/felismusic/
```

Desktop GUI používá stejnou session jako stabilní CLI.

---

# 7. GUI – vývoj po verzích

## 0.1-dev
Pouze vizuální skeleton.

## 0.2-dev
První skutečná datová vrstva:
- účet / session,
- Mixy,
- Oblíbené,
- Historie,
- Playlisty / knihovna,
- Hledání.

Problém:
- Qt/QML modely a `modelData` / `model.title`.

## 0.2.1-dev
Přechod na `QAbstractListModel` s explicitními rolemi.

Role:
- kind
- title
- subtitle
- artists
- album
- duration
- videoId
- playlistId
- browseId
- thumbnail

## 0.2.2-dev
Opraveno:
- role používané přímo jako required properties,
- data, obrázky, názvy, stopáže,
- start na Knihovně,
- `Výstup: Toto zařízení`.

Reálně otestováno jako funkční.

## 0.2.3-dev
Přidány kategorie Knihovny:
- Playlisty
- Skladby
- Alba
- Interpreti
- Profily
- Podcasty
- Nahrané

Přidáno řazení.

## 0.2.4-dev
Doladění řazení:

Playlisty:
- Výchozí YTM
- A–Z
- Z–A

Oblíbená hudba:
- Výchozí YTM
- A–Z
- Z–A

Historie:
- chronologická, bez řazení.

Mixy:
- pořadí YTM.

## 0.2.5-dev
Oddělení GUI od CLI:
- odstraněn text `CLI core · 1.0.0`,
- odstraněn `cli/` adresář z GUI projektu,
- datová vrstva považována za dokončenou.

## 0.3-dev
První skutečné přehrávání:
- GStreamer lokální výstup,
- kliknutí na skladbu spustí přehrávání,
- fronta z právě zobrazeného seznamu,
- Play / Pause,
- Previous / Next,
- automatický přechod na další skladbu,
- přeskočení nepřehratelné skladby,
- cover / název / čas / progress ve spodním panelu.

## 0.3.1-dev
Opravy:
- viditelná příprava audia,
- spinner,
- `Připravuji skladbu…`,
- fallback thumbnailů,
- opravy řazení,
- odstranění shutdown QML chyb typu `Cannot read property ... of null`.

## 0.3.2-dev
Přidáno:
- seek slider,
- ±10 s,
- ±30 s,
- hlasitost,
- mute.

Problémy:
- seek slider nešel táhnout,
- ikony nebyly vidět,
- volume slider byl příliš krátký.

## 0.3.2.1-dev
Opraveno a otestováno:
- seek tažením,
- seek tlačítky,
- hlasitost,
- mute / unmute,
- viditelné QML kreslené ovládací prvky,
- delší volume slider.

Tato verze byla potvrzena jako funkční.

## 0.3.3-dev
Přidáno:
- like / unlike,
- dislike / undislike,
- okamžitá změna stavu v GUI,
- synchronizace s YT Music.

Funkce byla potvrzena jako funkční.

## 0.3.3.1-dev
Opravy a rozšíření:
- vyhledávání,
- aktualizace Oblíbené hudby po like/unlike,
- audio sink přes Pulse/PipeWire místo náhodného ALSA výstupu,
- vlastní kreslené palce,
- typové filtry vyhledávání.

Audio výstup po opravě drží desktopem zvolený HDMI / jiný výstup.

## 0.3.3.2-dev
Přidáno:
- zvýraznění aktuálně hrající skladby,
- označení `Hraje`,
- autoscroll na aktuální skladbu,
- typy výsledků hledání,
- lepší práce s neklikacími výsledky,
- fallback `duration_seconds`.

Pozorování:
- autoscroll byl příliš agresivní,
- při přehrávání vracel uživatele stále zpět na aktuální skladbu,
- výsledek interpreta typu `The Browning` mohl být zobrazen jako nepoužitelný `Interpret · bez odkazu`.

## 0.3.3.3-dev
**Poslední vytvořená verze.**

Tato verze zatím nemá v tomto chatu potvrzený kompletní test.

Měla opravit:
1. Rozdělení vyhledávání na:
   - YT Music
   - Knihovna
   - Nahrané soubory
2. Filtry pro YT Music / Knihovnu:
   - Vše
   - Skladby
   - Videa
   - Alba
   - Interpreti
   - Playlisty
   - Profily
   - Podcasty
   - Epizody
3. Uploads:
   - samostatné hledání,
   - bez dalšího typového filtru.
4. Nepoužitelné výsledky:
   - pokud chybí potřebný `videoId`, `browseId`, `playlistId` apod.,
   - výsledek se vůbec nezobrazí.
5. Autoscroll:
   - aktuální skladba zůstane označena,
   - během běžného přehrávání může uživatel rolovat kam chce,
   - seznam se posune na aktuální skladbu až při skutečné změně tracku.

---

# 8. Co je potřeba otestovat jako první po návratu

Aktuální build:

```text
FelisMusic-desktop-0.3.3.3-dev
```

### Hledání
- ověřit oddělené scope:
  - YT Music
  - Knihovna
  - Nahrané soubory
- ověřit filtry v YT Music / Knihovně,
- ověřit hledání v Uploads,
- ověřit, že mrtvé / neklikatelné výsledky už nejsou zobrazovány.

Doporučený test:
- hledat `The Browning`,
- ve `Vše` se nemá objevit nepoužitelný interpret bez odkazu,
- použitelné výsledky musí jít otevřít / přehrát.

### Autoscroll
- spustit skladbu,
- odrolovat daleko od aktuální skladby,
- GUI nesmí během stejné skladby vracet seznam zpět,
- při Next / Previous / automatickém přechodu se má seznam posunout na nově hrající skladbu.

Pokud toto projde:
- blok **0.3.3** je možné uzavřít.

---

# 9. Známé chování hledání YT Music

Bylo ověřeno porovnáním s webem YT Music, že výsledky samotného YTM mohou působit zvláštně.

Například:
- `The Browning` jako interpret je nalezen správně,
- po otevření interpreta web ukazuje několik top skladeb,
- FelisMusic zatím u interpreta zobrazoval jen jednoduchý výřez `songs.results`.

Závěr:
- neimplementovat jedno „magické“ hledání napříč vším,
- respektovat rozdělení YTM:
  - YT Music
  - Knihovna
  - Nahrané soubory.

---

# 10. Aktuálně potvrzené GUI funkce

## Datová vrstva
- účet / session
- Knihovna
- Playlisty
- Skladby
- Alba
- Interpreti
- Profily
- Podcasty
- Nahrané
- Oblíbená hudba
- Historie
- Mixy pro vás
- obrázky / thumbnaily
- řazení tam, kde dává smysl

## Přehrávání
- lokální GStreamer
- Play
- Pause / Resume
- Previous / Next
- automatický přechod
- seek ±10 / ±30
- seek sliderem
- hlasitost
- mute
- HDMI / jiný desktopový výstup přes Pulse/PipeWire
- označení aktuální skladby

## Hodnocení
- like / unlike
- dislike / undislike
- refresh Oblíbené hudby po změně

---

# 11. Co ještě zbývá udělat

### 0.3.4 – Info + skutečná Fronta
- panel Fronta,
- pozice např. `17 / 133`,
- aktuální skladba,
- možnost skočit na jinou položku,
- scroll fronty nezávislý na hlavním seznamu,
- info o skladbě:
  - název
  - interpret
  - album
  - délka
  - hodnocení
  - pozice ve frontě

### 0.3.5 – Kontextové akce
Po kliknutí / pravém kliknutí na skladbu:
- Přehrát
- Přehrát odtud
- Přidat do fronty
- Přehrát jako další
- Otevřít album
- Otevřít interpreta
- Mix / rádio z této skladby
- Oblíbená / Neoblíbená
- případně otevřít v YT Music / kopírovat název

Podobná menu i pro album, interpreta a playlist.

### 0.3.6 – Detail interpreta / album / playlist
Interpret:
- Nejposlouchanější skladby
- Alba
- Singly / EP
- Náhodně
- Mix

Album:
- kompletní tracklist

Playlist:
- kompletní obsah

### 0.3.7 – Repeat / Shuffle
- Repeat off
- Repeat all
- Repeat one
- Shuffle přes YTM
- respektovat výjimku `RDCLAK...`

### 0.3.8 – Rádio / Mix z aktuální skladby
- radio z aktuální skladby,
- dynamické doplňování fronty,
- odstranění duplicit,
- prakticky nekonečné přehrávání.

### 0.3.9 – Resume session
- uložit frontu,
- aktuální skladbu,
- pozici,
- repeat / shuffle,
- nabídnout pokračování po restartu,
- nepouštět automaticky bez potvrzení.

### 0.3.10 – Komfort / výkon
- prefetch další skladby,
- rychlejší Next / automatický přechod,
- lepší cache,
- čištění starých cache souborů,
- doladění obrázků.

### 0.4 – Cast
Cast je záměrně odsunut až na konec desktopového přehrávače.

Plán:
- discovery až po otevření výstupů,
- Toto zařízení + Chromecast Audio + Cast Groups,
- přepínání Local ↔ Cast ↔ Cast,
- zachování pozice,
- reconnect po uspání Castu,
- ošetření známého stavu, kdy Cast session zemře, ale klient to nepozná.

---

# 12. MPRIS / Bluetooth media controls – TODO

Přidáno 2026-10-12.

## Desktop openSUSE
Přes **MPRIS2**:
- Play
- Pause
- PlayPause
- Next
- Previous

Cíl:
- fungující Bluetooth tlačítka na sluchátkách,
- multimediální klávesy,
- integrace do KDE / desktopového přehrávačového rozhraní.

Synchronizace stavu:
- `Playing`
- `Paused`
- metadata skladby
- cover
- délka
- změny stavu
- aktuální track

## Sailfish OS
Stejný princip přes MPRIS:
- Play
- Pause
- PlayPause
- Next
- Previous

Cíl:
- ovládání ze sluchátek,
- případně lockscreen / systémové media controls podle možností Sailfish OS.

## Lokální přehrávání / Cast
MPRIS příkazy musí vždy ovládat **aktuálně zvolený výstup**:
- lokální GStreamer,
- nebo Chromecast.

Stav musí zůstat konzistentní bez ohledu na výstup.

---

# 13. Lokální audio – důležité technické poznatky

Původně GStreamer používal automatický sink a nová skladba mohla skončit na interním Realtek výstupu místo uživatelem zvoleného HDMI.

Oprava:
- preferovat `pulsesink` přes PipeWire/Pulse,
- případně `pipewiresink`,
- fallback až potom.

Očekávaný log:

```text
FelisMusic lokální audio: pulsesink (PipeWire/Pulse)
```

nebo:

```text
FelisMusic lokální audio: pipewiresink (PipeWire/Pulse)
```

Nežádoucí fallback:

```text
FelisMusic lokální audio: autoaudiosink
```

Po opravě už desktopový zvukový výstup držel správně.

---

# 14. Lokální audio cache / čekání při změně skladby

Lokální přehrávání používá seekovatelný dočasný soubor / cache.

Důvod:
- přímý stream nebyl spolehlivě seekovatelný,
- proto se skladba nejprve připraví / stáhne,
- až potom se předá GStreameru.

Důsledek:
- první spuštění nové skladby může chvíli trvat.

GUI už zobrazuje:
- spinner,
- `Připravuji skladbu…`,
- stav přípravy.

Budoucí optimalizace:
- prefetch následující skladby během přehrávání aktuální,
- tím téměř odstranit čekání při Next / automatickém přechodu.

---

# 15. yt-dlp / YouTube změny

V jednom okamžiku se objevila chyba:

```text
Requested format is not available
```

Současně nový venv neměl lokální GStreamer kvůli chybějícím systémovým `gi`.

GStreamer problém byl vysvětlen špatně vytvořeným virtualenvem bez `--system-site-packages`.

Pro yt-dlp byl jako možný budoucí problém identifikován nový požadavek YouTube / yt-dlp na JavaScript runtime / EJS.

Do budoucna při podobné chybě zkontrolovat:

```bash
python -m yt_dlp --version
python -m pip show yt-dlp yt-dlp-ejs
command -v deno
deno --version
```

Doporučená instalace moderního yt-dlp:

```bash
python -m pip install -U "yt-dlp[default]"
```

Poznámka:
- neřešit preventivně, pokud aktuální přehrávání funguje,
- diagnostikovat až podle konkrétní chyby.

---

# 16. Sailfish / Jolla – budoucí port

Cíl:
- nativně působící FelisMusic pro Sailfish OS / Jolla Phone 2026.

RPM + Python není samo o sobě problém:
- RPM může obsahovat Python kód.

Hlavní technická otázka:
- desktopový PySide6/QML bridge nepůjde přenést 1:1,
- backend je potřeba držet co nejvíce nezávislý na desktop UI,
- Sailfish část bude používat QML / Silica a vhodný Python bridge / runtime.

Plán:
- nejprve dokončit stabilní desktopový backend,
- potom přenášet funkční logiku,
- UI přepsat pro Sailfish / Silica,
- vyřešit audio stack, MPRIS a systémovou integraci na Jolle.

---

# 17. Designová rozhodnutí

## Desktop start
GUI má vždy startovat na:

```text
Výstup: Toto zařízení
```

- lokální audio inicializovat automaticky,
- Cast discovery nespouštět při startu,
- Cast hledat až po otevření výběru výstupu / refresh.

## Cast
- až po dokončení lokálního přehrávače,
- nekomplikovat jím vývoj GUI předčasně.

## Historie
- chronologická,
- neřadit A–Z.

## Mixy pro vás
- zachovat pořadí YTM,
- neřadit ručně.

## Playlisty
- Výchozí YTM
- A–Z
- Z–A

## Nepoužitelné výsledky hledání
- pokud položku nelze otevřít / přehrát kvůli chybějícímu ID,
- nezobrazovat ji vůbec.

---

# 18. Nejbližší postup

1. Spustit a otestovat `0.3.3.3-dev`.
2. Pokud projde:
   - uzavřít celý blok 0.3.3.
3. Pokračovat:
   - **0.3.4 – Info + Fronta**
4. Potom:
   - kontextová menu,
   - detail interpreta / alb / playlistů,
   - repeat / shuffle,
   - rádio,
   - resume,
   - prefetch,
   - MPRIS,
   - Cast.
5. Po stabilním desktopu:
   - Sailfish / Jolla port.

---

# 19. Aktuální pracovní bod pro nový chat

Pokud se tento soubor použije v novém chatu, navázat větou přibližně:

> Pokračujeme na FelisMusic. Poslední vytvořená verze je `FelisMusic-desktop-0.3.3.3-dev`. Nejdřív potřebuji dokončit její test: search scope YT Music/Knihovna/Nahrané, filtrování neklikacích výsledků a opravený autoscroll. Potom pokračujeme verzí 0.3.4 – Info + Fronta.

---

# 20. Stav v jedné větě

**FelisMusic Desktop už je funkční lokální YT Music přehrávač s knihovnou, hledáním, přehráváním, seekem, hlasitostí, hodnocením a základní navigací; nejbližší nedokončený krok je otestovat 0.3.3.3-dev a potom doplnit skutečnou frontu, info, kontextová menu a další pokročilé funkce před Castem a Sailfish portem.**
