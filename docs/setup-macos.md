# Setup on macOS

Written blind from Linux. The TUI, the archive.org tools and playback should work as
described; the light show's audio tap is the part that most needs a real Mac to
confirm. If something here is wrong, open an issue with what you saw.

## 0. Or just download a build

Each [release](https://github.com/originalrexconsulting/may-the-lord-poseidon-convey-you/releases)
has a self-contained `poseidon-<ver>-macos-aarch64` (Apple silicon) and
`poseidon-<ver>-macos-x86_64` (Intel) with CPython 3.13, numpy and mutagen inside, so
`brew install python numpy` and `pip3 install mutagen` below are not needed.

```
brew install mpv ffmpeg     # mpv required; ffmpeg optional (SHN to FLAC, the light show's tap)
curl -fLo poseidon https://github.com/originalrexconsulting/may-the-lord-poseidon-convey-you/releases/download/v<ver>/poseidon-<ver>-macos-aarch64
chmod +x poseidon
./poseidon doctor
./poseidon
```

Downloaded with a browser instead of curl, the file carries a quarantine attribute and
Gatekeeper refuses to run it: `xattr -d com.apple.quarantine poseidon` clears it (curl
sets no such attribute). The first run unpacks Python into `~/Library/Caches/nce` (a few
seconds, once; safe to delete). Shows fetched with `d` land in `~/Music/dead` unless
`POSEIDON_LIBRARY` says otherwise (section 2). `./poseidon doctor` has a `terminfo:`
line: the build carries its own ncurses and looks for terminfo in `/usr/share/terminfo`
and Homebrew's; `TERMINFO_DIRS=/path` overrides that if a terminal comes up blank.

`poseidon-<ver>.pex` is the same program for a Python 3.11+ already on PATH (Homebrew's;
Apple's `/usr/bin/python3` is too old). It uses that Python's numpy for the light show.

Or clone and run the scripts, which is what the rest of this page describes.

## 1. Homebrew packages

```
brew install mpv ffmpeg python numpy
pip3 install mutagen        # optional: tags fetched shows
```

| Package | Used by | Without it |
|---|---|---|
| mpv | the TUI, playback | nothing plays |
| python (3.11 or newer; Apple's own `/usr/bin/python3` also works) | everything | nothing runs |
| numpy | deadviz, the light show | no light show |
| mutagen | gdarchive, tagging fetched shows | shows fetch untagged |
| ffmpeg | gdarchive (SHN to FLAC), the light show's tap, station probe | SHN stays SHN; no light show |

## 2. Get the code

```
git clone git@github.com:originalrexconsulting/may-the-lord-poseidon-convey-you.git
cd may-the-lord-poseidon-convey-you
```

Fetched shows land in the library, under `shows/<year>/`: `$POSEIDON_LIBRARY` if set,
else `dead/` inside the clone, else `~/Music/dead` (what a downloaded build uses). A
whole show is 0.7 to 4 GB.

## 3. Audio

mpv talks to CoreAudio directly. Pick the DAC in System Settings > Sound > Output
before starting; mpv follows the system output. For bit-exact playback CoreAudio
resamples to whatever rate the device is set to in Audio MIDI Setup, so set the DAC's
format there to match what you play most (44.1 kHz for the Dead), or use mpv's
exclusive mode: put `audio-exclusive=yes` in `~/.config/mpv/mpv.conf` and the DAC
follows each file's rate, at the cost of other apps being muted while it plays.

The status line's `DAC nn k` readout is Linux-only (it reads `/proc/asound`) and stays
blank here. What mpv measures (codec, depth, rate, bitrate) still shows.

## 4. Run

```
scripts/May-The_Lord_Poseidon-Convey-You.py
```

Two seconds of Poseidon, then the home screen. Enter opens, p plays, w shows the
playlist, v the light show, q quits and leaves the music playing, Q stops it. The
control socket lives in `~/.cache/deadtui/` (macOS has no `XDG_RUNTIME_DIR`); if the
TUI dies mpv keeps playing and the next start adopts it. Terminal.app and iTerm2 both
do 256 colours; the block and braille glyphs need a font that has them (Menlo does).

Outside the repo: `~/.cache/deadtui/` (state, history, the 7-day metadata cache), and
for a downloaded build `~/Library/Caches/nce` (its Python, about 120 MB per release) and
`~/.cache/pex` (its venv). Delete any of them to reset; the next run rebuilds them.

## 5. The light show

macOS has no "monitor" of the output the way PipeWire does, so the tap goes through a
loopback device:

```
brew install blackhole-2ch
```

Then in Audio MIDI Setup make a Multi-Output Device containing the DAC and BlackHole
2ch, and choose that as the system output. mpv plays to both; the light show reads
BlackHole back with `ffmpeg -f avfoundation`. If the device is named differently:

```
DEADVIZ_DEVICE="BlackHole 16ch" scripts/May-The_Lord_Poseidon-Convey-You.py
```

`ffmpeg -f avfoundation -list_devices true -i ""` lists the names. The first run asks
for microphone permission for the terminal; grant it, that is the tap. Without
BlackHole the light show draws nothing and says what to install in its footer.

## 6. Not on macOS

`radio.py`'s own commands (`play`, `now`) drive Strawberry over D-Bus and are Linux
only. The station list they hold is what the TUI's `c` uses, and that works anywhere.
