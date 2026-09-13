# Setup on Linux

Written for Debian 13 (trixie) with PipeWire, which is what it runs on at home. Any
distribution with the same packages works.

## 1. Packages

```
sudo apt install mpv python3 python3-numpy python3-mutagen pulseaudio-utils ffmpeg tmux
```

| Package | Used by | Without it |
|---|---|---|
| mpv | the TUI, playback | nothing plays |
| python3 (3.11 or newer, with curses) | everything | nothing runs |
| python3-numpy | deadviz, the light show | no light show, the rest is fine |
| python3-mutagen | gdarchive, tagging fetched shows | shows fetch untagged |
| pulseaudio-utils | deadviz (`parec` taps the sink via pipewire-pulse) | the light show says so and draws nothing |
| ffmpeg | gdarchive (SHN to FLAC), `i` in the radio list (ffprobe) | SHN tapes stay SHN; no station probe |
| tmux | optional, for screenshots and for leaving it running | nothing |

No pip. Everything is a stock package.

## 2. Get the code

```
git clone git@github.com:originalrexconsulting/may-the-lord-poseidon-convey-you.git
cd may-the-lord-poseidon-convey-you
```

Shows fetched with `d` land in `dead/shows/<year>/`, next to the scripts. That folder
is gitignored. A whole show is 0.7 to 4 GB; plan the disk.

## 3. Audio

mpv plays through PipeWire like any other app. Whatever is the default sink gets the
music; `wpctl status` shows the sinks, `wpctl set-default <id>` picks one. A USB DAC
should be set to follow the file's sample rate rather than resampling: see
`AUDIO-ANSIBLE.md` for the PipeWire settings that make a Rotel A14 MKII clock to the
source, and the `DAC nn k` readout in the status line, which reads
`/proc/asound/<card>/pcm0p/sub0/hw_params` (the card name is in `HW_PARAMS` at the
top of the TUI script; change it for another DAC).

## 4. Run

```
scripts/May-The_Lord_Poseidon-Convey-You.py
```

`scripts/deadtui.py` is the same thing, an older name kept as a symlink. Two seconds of
Poseidon, then the home screen. Enter opens, p plays, w shows the playlist, v the light
show, q quits and leaves the music playing, Q stops it. Everything else is in the
docstring at the top of the script and in `SYSTEM.md`.

## 5. Things that live outside the repo

- `~/.cache/deadtui/`: search results, item metadata (7-day cache), `state.json`
  (where you were), `history.jsonl` (everything played). Delete the folder to reset.
- `$XDG_RUNTIME_DIR/deadtui-mpv.sock`: mpv's control socket. If the TUI dies, mpv keeps
  playing and the next start adopts it.
- `dead/playlist-*.json`: snapshots from `scripts/restore-playlist.py --snapshot`.

## 6. Radio

The station list in `scripts/radio.py` is used by the TUI (`c`). `radio.py`'s own
commands (`play`, `now`, `back`) drive the Strawberry music player over D-Bus and need
`busctl` (systemd) and Strawberry running; they are a separate, Linux-only convenience.
