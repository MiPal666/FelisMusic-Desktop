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

## Install FelisMusic Desktop 1.0.0

Installation, launch from the application menu, and local playback were tested on
openSUSE Tumbleweed with KDE and Debian 13.7 with GNOME 48.

1. Install Python 3 with virtual environment support, PyGObject, and GStreamer 1.0.
   On Debian, install `python3-venv` if virtual environment support is missing.
2. Install Deno 2.3 or newer. A system RPM was tested on Tumbleweed and a
   per-user installation on Debian. See the [Deno installation guide](https://docs.deno.com/runtime/getting_started/installation/).
3. Download `FelisMusic-1.0.0-linux-installer.zip` from [GitHub Releases](https://github.com/MiPal666/FelisMusic-Desktop/releases).
   Extract it and run `bash install.sh` from the `FelisMusic-Installer` directory without `sudo`.
4. Open FelisMusic from the application menu and sign in. You can delete the extracted folder after installation.

If you already have FelisMusic installed, close it and run `bash uninstall.sh`
from the extracted archive before installing. To remove the installed app, run
`bash "$HOME/.local/opt/felismusic/uninstall.sh"`. Your sign-in and settings
remain in your user configuration directory, usually `~/.config/felismusic/`.

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
