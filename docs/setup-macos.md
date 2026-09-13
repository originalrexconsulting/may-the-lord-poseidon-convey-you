# Setup on macOS

Written blind from Linux. The TUI, the archive.org tools and playback should work as
described; the light show's audio tap is the part that most needs a real Mac to
confirm. If something here is wrong, open an issue with what you saw.

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

Fetched shows land in `dead/shows/<year>/` inside the clone. A whole show is 0.7 to 4 GB.

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
