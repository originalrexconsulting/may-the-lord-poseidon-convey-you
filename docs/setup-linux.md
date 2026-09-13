# Setup on Linux

Written for Debian 13 (trixie) with PipeWire, which is what it runs on at home. Any
distribution with the same packages works.

## 0. Or just download a build

Skip the Python packages entirely: each [release](https://github.com/originalrexconsulting/may-the-lord-poseidon-convey-you/releases)
has a self-contained `poseidon-<ver>-linux-x86_64` (and `-linux-aarch64` for a Raspberry
Pi 4/5 or an ARM server) with CPython 3.13, numpy and mutagen inside. Needs glibc 2.28 or
newer (Debian 10, Ubuntu 18.10, RHEL 8 and anything later).

```
sudo apt install mpv pulseaudio-utils ffmpeg     # mpv required; the other two optional
curl -fLo poseidon https://github.com/originalrexconsulting/may-the-lord-poseidon-convey-you/releases/download/v<ver>/poseidon-<ver>-linux-x86_64
chmod +x poseidon
./poseidon doctor        # mpv found? library path? terminfo ok?
./poseidon               # the TUI; ./poseidon gdarchive ..., ./poseidon radio list
```

The first run unpacks Python into `~/.cache/nce` (a few seconds, once). Shows fetched
with `d` land in `~/Music/dead` unless `POSEIDON_LIBRARY` says otherwise (section 2).
If the screen comes up without colours or with odd glyphs, `./poseidon doctor` shows the
`terminfo:` line; the build carries its own ncurses and looks for the system's terminfo
in the usual places, and `TERMINFO_DIRS=/path/to/terminfo` overrides that.

There is also `poseidon-<ver>.pex`, the same program for a machine that already has
Python 3.11+ with curses: it bundles mutagen and uses the system `python3-numpy` for the
light show. `python3 poseidon-<ver>.pex` or `chmod +x` and run it.

Or clone and run the scripts, which is what the rest of this page describes.

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

Shows fetched with `d` land in the library, under `shows/<year>/` (JGB in `jgb/`, LPs in
`lp/`). The library is `$POSEIDON_LIBRARY` if set, else `dead/` next to `scripts/` in a
clone (gitignored), else `~/Music/dead` (what a downloaded build uses). A whole show is
0.7 to 4 GB; plan the disk.

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
- `~/.cache/nce/`: where a downloaded `poseidon-<ver>-linux-*` build unpacks its Python
  (about 120 MB per release, never pruned), and `~/.cache/pex/`: its venv, and the
  `.pex`'s. Both are rebuilt on the next run; delete them whenever you like.
  `SCIE_BASE` and `PEX_ROOT` relocate them.

## 6. Radio

The station list in `scripts/radio.py` is used by the TUI (`c`). `radio.py`'s own
commands (`play`, `now`, `back`) drive the Strawberry music player over D-Bus and need
`busctl` (systemd) and Strawberry running; they are a separate, Linux-only convenience.
