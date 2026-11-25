# FelisMusic Desktop

**English** | [Čeština](README.cs.md)

**Chromecast Audio and Google Cast speaker groups.** FelisMusic is a YouTube Music
player for Linux that lets you switch between your computer and a Cast speaker
while keeping the current queue, track, playback position, and pause state.

## Features

- Search YouTube Music and browse your library, liked songs, uploads, and playlists.
- Manage the playback queue and start mixes and radio.
- Control playback with desktop media keys through MPRIS.
- Use the app in English or Czech.

## New in 1.0.4

- Updated bundled yt-dlp to 2026.11.23 to fix YouTube playback failures in AppImage.
- Added **Update yt-dlp** under **About** for virtualenv installations. Updates run only when requested; restart FelisMusic after completion. AppImage users update by downloading a new AppImage.
- About now credits Michal Kasík (MiPal) with help from Klára (AI).

## New in 1.0.3

- Sign-in opens Google directly and verifies the account automatically after the sign-in browser window closes.
- Removed the CLI reference from the sign-out confirmation.
- AppImage distribution, tested on Debian 13.7 and openSUSE Tumbleweed. The ZIP installer remains supported.

## New in 1.0.2

- Fixed artist pages such as Bruno Mars failing to open when YouTube Music returns a carousel without a header. Available releases and subscription controls remain accessible even when the songs section is absent.

## New in 1.0.1

- Faster local and Cast audio preparation through a direct InnerTube resolver, with yt-dlp fallback for uploads and other unavailable content.
- About dialog with version, license, and project links.
- Artist details use the original YouTube Music order by default.

## Install FelisMusic Desktop 1.0.4

### AppImage

Download `FelisMusic-1.0.4-x86_64.AppImage` from [GitHub Releases](https://github.com/MiPal666/FelisMusic-Desktop/releases), make it executable and run it. Python, Qt, GStreamer and Deno are bundled; a supported system browser is needed for sign-in. Tested on Debian 13.7 (GNOME) and openSUSE Tumbleweed (KDE), including Cast and MPRIS/Bluetooth controls. Compatibility with older systems has not been established.

```sh
chmod +x FelisMusic-1.0.4-x86_64.AppImage && ./FelisMusic-1.0.4-x86_64.AppImage
```

### ZIP installer

Installation, launch from the application menu, and local playback were tested on
openSUSE Tumbleweed with KDE and Debian 13.7 with GNOME 48.

1. Install Python 3 with virtual environment support, PyGObject, and GStreamer 1.0.
   On Debian, install `python3-venv` if virtual environment support is missing.
2. Install Deno 2.3 or newer. A system RPM was tested on Tumbleweed and a
   per-user installation on Debian. See the [Deno installation guide](https://docs.deno.com/runtime/getting_started/installation/).
3. Download `FelisMusic-1.0.4-linux-installer.zip` from [GitHub Releases](https://github.com/MiPal666/FelisMusic-Desktop/releases).
   Extract it and run `bash install.sh` from the `FelisMusic-Installer` directory without `sudo`.
4. Open FelisMusic from the application menu and sign in. You can delete the extracted folder after installation.

To upgrade an existing installation, close FelisMusic and run the following from
the newly extracted `FelisMusic-Installer` directory, without `sudo`:

```sh
bash uninstall.sh && bash install.sh
```

The installer creates a new environment and explicitly upgrades yt-dlp to the
latest available compatible release. The **Update yt-dlp** button is for updates
between FelisMusic releases; no extra click is needed after installation.

To remove the installed app, run
`bash "$HOME/.local/opt/felismusic/uninstall.sh"`. Your sign-in and settings
remain in your user configuration directory, usually `~/.config/felismusic/`.

## Sign-in

Choose a supported browser in the Account dialog. FelisMusic opens Google sign-in
in its own browser profile. Sign in and close the entire sign-in window; the app
then verifies and saves the account automatically. Firefox, Chrome, Chromium,
Brave, Vivaldi, and Edge are supported. Cancelling or a failed verification keeps
your previously saved credentials.

## Cast playback

Open **Outputs → Find devices** to discover Chromecast Audio devices and speaker
groups. If a group member drops out, playback on the group may stop. You can
select an available output and restart playback manually. FelisMusic starts
with local output each time you open it.

## Planned

- Download and manage music for offline listening.
- Restore the queue, current track, and playback position after restarting the app.
- Use a Chromecast connected to a TV as an additional audio output.

## License

FelisMusic Desktop is licensed under the GNU General Public License, version 3 or any later version (GPL-3.0-or-later). See [LICENSE](LICENSE).
