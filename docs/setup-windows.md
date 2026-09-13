# Setup on Windows

Run it under WSL 2 as Linux. A native Windows port is not done: Python on Windows has
no curses without the `windows-curses` package, and mpv's control socket would have to
become a named pipe. Everything below happens inside the WSL distro; the Windows side
only supplies the terminal and the speakers.

## 1. WSL 2 with Ubuntu

In an administrator PowerShell:

```
wsl --install -d Ubuntu-24.04
```

Reboot if asked, open "Ubuntu 24.04" from the Start menu, pick a username. `wsl -l -v`
must show version 2: WSL 1 has no WSLg and no sound. Windows 11, or Windows 10 21H2 and
later, ships WSLg; it is what carries audio out.

## 2. Packages

Inside Ubuntu:

```
sudo apt update
sudo apt install mpv pulseaudio-utils ffmpeg
```

mpv is required. `pulseaudio-utils` provides `parec`, the light show's audio tap, and
`pactl` for checking sound. ffmpeg converts SHN tapes and probes radio stations. No
Python packages: the download below carries its own.

## 3. Download

Windows on x86_64 uses the Linux x86_64 build. Keep it in the Linux home directory, not
under `/mnt/c`: the Windows filesystem is slow from WSL and does not keep the execute
bit reliably.

```
cd ~
curl -fLo poseidon https://github.com/originalrexconsulting/may-the-lord-poseidon-convey-you/releases/download/v<ver>/poseidon-<ver>-linux-x86_64
chmod +x poseidon
./poseidon doctor
./poseidon
```

`<ver>` is the release date, e.g. `2026.09.13.2`; copy the link from the
[releases page](https://github.com/originalrexconsulting/may-the-lord-poseidon-convey-you/releases).
The first run unpacks its Python into `~/.cache/nce` (a few seconds, once). `doctor`
should show mpv found and `terminfo: ok`. A clone works too (`sudo apt install python3
python3-numpy python3-mutagen` and follow the [Linux guide](setup-linux.md)).

## 4. Audio

WSLg runs a PulseAudio server for the distro and presets `PULSE_SERVER` in every shell,
so mpv plays to whatever Windows uses as its default output device with no configuration.
Check:

```
pactl info | head -3        # Server Name: pulseaudio ... means WSLg's server is up
```

Pick the DAC in Windows' Sound settings; WSL follows the Windows default. The light show
taps WSLg's sink monitor with `parec` (`pactl list short sources` shows it as
`RDPSink.monitor` or similar), so `v` works without extra setup. Windows resamples in its
mixer; there is no bit-perfect path through WSLg, and the status line's `DAC nn k` readout
(a Linux `/proc/asound` feature) stays blank.

If `pactl info` cannot connect, WSLg is not running: `wsl --shutdown` from PowerShell and
reopen Ubuntu, and make sure the distro is WSL 2.

## 5. Terminal

Use Windows Terminal (the default on Windows 11; on the Store for Windows 10) with the
Cascadia Mono font it ships: it does 256 colours and has the block and braille glyphs the
light show draws with. The old console host window does neither. `TERM` is
`xterm-256color` there already.

## 6. The library

Shows fetched with `d` land in `~/Music/dead` inside the distro (the distro's disk lives
in a virtual disk file on `C:`; `\\wsl$\Ubuntu-24.04\home\<you>\Music\dead` reaches it
from Explorer). To keep the music on a Windows drive instead:

```
POSEIDON_LIBRARY=/mnt/d/dead ./poseidon
```

Slower (every file goes through the 9P bridge), and playback of a fetched show from
`/mnt/d` may stutter on a busy disk; streaming is unaffected. Put the export in
`~/.bashrc` to make it stick.

## 7. Things that live outside the repo

- `~/.cache/deadtui/`: state, history, the 7-day metadata cache.
- `~/.cache/nce/`: the build's unpacked Python, about 120 MB per release, and
  `~/.cache/pex/`: its venv. Safe to delete; rebuilt on the next run.
- `$XDG_RUNTIME_DIR/deadtui-mpv.sock` (WSL sets `XDG_RUNTIME_DIR`): mpv's control
  socket. If the TUI dies mpv keeps playing and the next start adopts it.

## 8. Not on Windows

`radio.py`'s own commands (`play`, `now`) drive the Strawberry music player over D-Bus
and do not apply here. The station list is what the TUI's `c` uses, and that works.
