# The listening rig

Reference for the scripts in this repo and the Linux audio setup they run on: a Debian ThinkPad feeding a Rotel A14 MKII's USB DAC through PipeWire, B&W 706 S3 speakers, a REL sub. Read before touching audio config or the streaming scripts. House-specific detail (room, cabling, vendors, to-do) lives in PRIVATE.md, which is not committed.

Last updated: 2026-09-13

## Settings that took work to get right

Do not change these without a reason.

- Sony Bravia Sync: "Auto devices off" = disabled. Lets UB820 play CDs with the TV off.
- UB820: HDMI CEC = off. Stops disc insertion waking the TV. Cost: manual TV input selection for movies.
- ThinkPad: PipeWire, A14 MKII in USB Audio Class 2 mode. Managed by ansible-homelab `nslcd-laptop.yml --tags audio` (spec: AUDIO-ANSIBLE.md); `--tags verify` checks it. Rate-following confirmed 2026-09-11 (S24_3LE at the source rate in `/proc/asound/R20/pcm0p/sub0/hw_params`).
- Rotel as default sink on plug-in: the internal card's Pro Audio profile outranks the Rotel (priority.session 1500 vs 1009), so WirePlumber never picked it by itself. `~/.config/wireplumber/wireplumber.conf.d/51-rotel-default.conf` ranks the Rotel at 3000 (written 2026-09-12, in the playbook, takes effect at the next WirePlumber restart or login). Until then `wpctl set-default <id>` moves everything live, and WirePlumber remembers that choice in `~/.local/state/wireplumber/default-nodes`. Fallback to the speakers when the Rotel is unplugged needs `52-internal-pro-audio.conf` (same playbook): PipeWire only offers "off" and "pro-audio" for the sof-hda-dsp card (no HiFi profile, cause unknown) and WirePlumber never picks pro-audio by itself, so without the pin the card came up "off" and streams landed on a silent Dummy Output (2026-09-12). Why HiFi is missing: PipeWire drops a UCM profile if any mapping fails to open, and the internal DMIC (`hw:0,6`) fails hw_params because the 6.12 kernel asks the BIOS NHLT for a 16-bit DMIC blob it does not have (topology ABI 3:29 vs kernel 3:23; PulseAudio had silently fallen back to its classic analog profile, so the internal mics never worked). Headphone-vs-speaker switching is done by the codec's `Auto-Mute Mode` (enabled by the same playbook task, stored with alsactl), not by PipeWire. Untried: `sof_use_tplg_nhlt=1` on snd_sof_intel_hda_common (needs reboot) might revive the DMICs; a trixie-backports kernel is the real fix.
- REL starting point: crossover ~40 Hz, gain low, phase 0 then by ear. Final placement by subwoofer crawl.
- OLED: no extended ambient/screensaver use. Cover only after panel is fully cooled. Dry microfiber only.

## Sources and how they are used

- archive.org: Grateful Dead live shows, working chronologically through ~1990. Streamed from ThinkPad over USB via `scripts/deadtui.py`.
- Lossless classical radio: `scripts/radio.py play naim` (also ddur, klasu, klasupro, sector; all FLAC, verified 2026-09-11). Plays in a Strawberry tab named "Radio" so the Dead playlist is untouched; `radio.py now` shows the DAC's actual rate. Mother Earth Klassik (24/192) is gone, the station closed.
- Criterion and other discs: UB820.
- OTA TV: Mohu Leaf.

## Work a Claude Code agent may be asked to do

Scope is the ThinkPad side. Hardware and cabling decisions are the owner's.

1. PipeWire / ALSA config for the A14 MKII USB endpoint: sample rate handling, avoiding resampling, sink priority, making the amp the default sink when connected.
2. Streaming helpers: archive.org show fetch/queue scripts, KDFC stream launcher, playback control from CLI.
3. DAT archive pipeline: capture from an audio interface at the source rate (48 / 44.1 / 32 kHz, never resample on capture), verify against archive.org lineages before duplicating Dead shows, tag and checksum output. Radiators tapes are the priority; likely more archivally significant.
4. Diagnostics: scripts to list USB audio devices, confirm Class 2 negotiation, log xruns.

Conventions:

- Debian stable, PipeWire. Do not introduce PulseAudio or JACK.
- Prefer stock packages over pip/npm installs where an equivalent exists.
- Check cables and connections before blaming components. The "dead" left channel was a cable.
- Keep responses short. Verdict first, one reason, details only on request.

## Scripts

`scripts/poseidon.py` (2026-09-13) is the one door to every tool and the entry point of the built artifacts: bare `poseidon` is the TUI, `poseidon gdarchive|deadviz|radio|restore-playlist|tui ...` runs that script as `__main__` with `poseidon <tool>` as its argparse prog, `poseidon doctor` prints one `key: value` line per fact (version, running as checkout/pex/scie, python, numpy, mutagen, mpv/ffmpeg/ffprobe/parec, library, cache, socket, TERM, terminfo, re-exec argv) and `poseidon --version` the version. It also dispatches on the invoked basename, so a symlink named `gdarchive` or `deadtui` runs that tool (in a scie the name arrives in `SCIE_ARGV0`). It is stdlib only and imports no sibling; the siblings import it for `user_agent()` (`may-the-lord-poseidon-convey-you/<ver> (+repo URL)`, used by gdarchive and the mpv it starts), `library_dir()` (`$POSEIDON_LIBRARY`, else `dead/` beside `scripts/` in a checkout, else `~/Music/dead`; `gdarchive.DEFAULT_DEST` is this) and `self_command(args)` (argv that runs this program again: the scie binary from `SCIE`, the `.pex` from `PEX`, else `python3 poseidon.py`; the TUI's `d` uses it for the background fetch). `version()` reads `_version.py` (staged into a build only), else `git describe` in a checkout, else `dev`. Before any curses import it sets `TERMINFO_DIRS` to whichever of the usual terminfo directories exist, because the self-contained builds carry a static ncurses that may not know the host's layout.

`scripts/May-The_Lord_Poseidon-Convey-You.py` (renamed from deadtui.py on 2026-09-13; starts with a two-second splash screen of Poseidon, crowned, red-eyed, trident raised, any key skips; `SPLASH_STYLE` picks "crowned" (the keeper), "storm" (rising from the sea under lightning) or "random", `SPLASH_SECS` 0 disables; `scripts/deadtui.py` is a symlink to it, and the cache stays at `~/.cache/deadtui/`) is the terminal browser/player (stock python3 curses + mpv, Debian package) for the archive.org Grateful Dead collection and the classical radio stations. Levels: home > years > dates > sources > tracks. The home screen is sectioned (headers are skipped by the cursor): Now (`▶ Now playing`, `🎲 Random show`: a random year, a random night in it rated 4+ when possible, best source, straight into play), The Dead (`Grateful Dead` years, `★ Dark Star`: fifteen famous nights from `DARK_STARS` with a line on why, ↵ plays that night from Dark Star on using the best source that really has it, on disk first, plus a row that streams random Dark Stars one after another, `☔ Rain and Snow`: weather and water songs from `RAIN_SONGS`, a random night's version of a random song, four to start and three more each time the last queued one begins, `Tears`, `JGB`), Memories (one ✦ row each), Not Dead (`♪ Classical radio`, `Firesign Theatre`, `Jokes`), Everything (`History`). `JGB`: Melvin Seals & JGB, the band Jerry left behind, 1996 to today (archive.org collection `JGB`). Jerry's own Garcia Band tapes were removed from archive.org at the estate's request, so there is no pre-1996 JGB there. JGB shows fetched with `d` land in `dead/jgb/<year>/`; `g 2001-06-24` jumps straight into JGB; `f` inside JGB searches that collection. `gdarchive.py --collection JGB` does the same on the command line. `Firesign Theatre` (home, Not Dead): the four LPs archive.org holds as library vinyl transfers (Waiting for the Electrician, How Can You Be in Two Places, Don't Crush That Dwarf, Dear Friends), one 24-bit/96k FLAC per side, titled from the mp3 cut list; Dear Friends is stream-only and plays cut by cut as mp3. `d` fetches an LP into `dead/lp/<year>/`. Melvin Seals & JGB is the only place on archive.org with Tears of Rage (2006-01-13 GAMH soundboard is the good one); the Dead never played it. `Jokes` (sixteen comedy LPs, same vinyl transfers: Lord Buckley, Lenny Bruce, Mort Sahl, Shelley Berman, Jonathan Winters, Newhart, Beyond the Fringe, the Goons, Freberg, Redd Foxx, Flip Wilson, Moms Mabley, Python, Pryor; list in `ALBUMS[JOKES]`), `Tears` (the weepers, `TEARS_LIST`; ↵ on a song runs the `f` song search, Tears of Rage searches the JGB collection), one `✦` row per entry in `MEMORIES` (an evening as a set list of (show, first song, last song) parts; ↵ plays a part, `a` plays the evening through; the first one is 2026-09-12/13: China>Rider 2/13/70, Mission in the Rain and the rest of 6/12/76, Tears of Rage JGB 2006-01-13, then Dark Star onward), and `History`: every track that starts playing is appended to `~/.cache/deadtui/history.jsonl` (time, show, title, source, enough of the doc to replay); the menu lists the last 500 newest first, ↵ plays one again, `/` filters. On quit a built playlist (Rain and Snow, a Dark Star stream, a memory evening, every version of a song, an adopted list) is saved whole in state.json and `r` rebuilds it at the saved track and second, refilling included. If the TUI dies without `q` (closed terminal, hangup, crash) mpv keeps playing its whole playlist on its own; it is a separate process with the playlist loaded, and the TUI is only a remote over the socket. Since 2026-09-13 a new start adopts such an mpv instead of starting a second one over it: it reads the playlist back, recognises shows on disk and archive.org URLs, rebuilds the status line, and `q` then quits the adopted player too. `q` quits the TUI and leaves the music playing (the next start adopts it); `Q` quits and stops the music. If something else loads a playlist into the TUI's mpv (`scripts/restore-playlist.py <snapshot.json> [--from N]`, which reloads a saved playlist, or `--snapshot <file>` to save the current one) the TUI notices within a second and describes it like an adopted playlist; `▶ Now playing` (home screen) or `w` anywhere shows the whole current playlist with ▶ on the track; ↵ jumps to a track. Works for adopted, song-version and memory playlists, not just single shows. Rows show source kinds present (M/S/A), best rating, source count, and `*` when a show is on disk. Plays through mpv (JSON IPC over `$XDG_RUNTIME_DIR/deadtui-mpv.sock`), so audio goes out PipeWire like Strawberry. Shows already in `dead/shows/` play from the local files; otherwise it streams (lossless for open items, the mp3 derivative for stream-only SBD/matrix). Gapless between tracks. On quit it saves show, track and position (or the radio station) to `~/.cache/deadtui/state.json`; the next start re-opens that view with the cursor on the track and `r` resumes from the saved position. Search and metadata responses are cached there for 7 days.

The status line shows what mpv measures, not what the tag claims: codec, bit depth (lossless only), sample rate, live bitrate, and `DAC nn k`, the rate the Rotel is actually clocked at from `/proc/asound/R20`. Radio stations come from `radio.py`'s STATIONS (six FLAC, then a lossy tier: France Musique and its Baroque, Concerts and Opéra webradios at AAC 192, Linn Classical MP3 320, NPO Radio 4, WQXR, WFMT, Venice Classic; the nominal format shows in the right column and the status line shows what mpv measures); `i` probes one with ffprobe. KDFC is deliberately absent: every StreamTheWorld mount answered "430 Invalid Mount" on 2026-09-12 and kdfc.com no longer exposes a stream URL. Add it to `EXTRA_STATIONS` in deadtui.py once a working URL is found (browser dev tools, Network tab, while the web player runs).

Portability (2026-09-13): every script has an `env python3` shebang; the TUI and gdarchive run on macOS with Homebrew mpv (README has the recipe). `dac_rate()` returns None where `/proc/asound` is absent and the readout is omitted. deadviz picks its audio tap in `Capture.backend()`: parec when present, else on macOS ffmpeg's avfoundation input reading a BlackHole loopback device (`DEADVIZ_DEVICE`, `DEADVIZ_CAPTURE` to force one); with neither it says what to install in the footer. The macOS path is written blind, untested on a Mac. The self-contained builds (below) embed python-build-standalone's CPython, whose ncurses is static and terminfo-blind; `poseidon.py` points it at the host's terminfo directories and `poseidon doctor` reports `terminfo: ok (N colors)` or the `setupterm` error, and the release workflow greps for the former on all four platforms.

`scripts/ansi2svg.py` turns a `tmux capture-pane -e -p` dump into an SVG (`--crop` trims a centred splash); `docs/screenshots/` holds the README shots, taken from a sandboxed TUI (`HOME`/`XDG_RUNTIME_DIR` elsewhere, mpv `ao=null`) and, for the light show, from `deadviz.py` against the live sink. deadviz keeps all its colour pairs below 256 (13 ramps of 16 from pair 8): curses attributes hold the pair number in 8 bits, so the earlier 31-step ramps past pair 255 silently wrapped and the wave/radial/meters/spiral/plasma/poseidon colours were wrong until 2026-09-13.

`scripts/deadviz.py` is the light show: `v` in deadtui, or standalone. It captures the default sink's monitor with parec (so it hears exactly what the Rotel gets, from any player), runs an FFT with python3-numpy, and draws one of 16 modes: bars, plasma, scope (stereo Lissajous), rings, waterfall (spectrogram), fire, rain (falling glyphs), stars (warp field), wave (stereo waveform), radial (spectrum on a circle), particles (beat fountain), meters (VU: L/R/bass/mid/treble), spiral, life (Conway, seeded by the beat), poseidon (the Earth Shaker swims a night sea: bass raises the swell, treble lights stars and foam, a beat shakes the screen and the trident throws lightning; when he gets bored or the music goes quiet he dives, lurks on the bottom with burning eyes, and a big beat brings him back up; sharks, a spouting whale, beat-jumping dolphins, jellyfish and a crab drop by now and then, three at most), enik (2026-09-13: Enik the Altrusian head to foot, drawn as a vector figure on the braille canvas and scaled to the terminal; the pose changes only four times a second, in angular jolts, the way the costume moved, and a beat lands a step early; the bass opens the time doorway behind him, the crystal matrix in the corner shows one crystal per band, a beat flashes his eyes and he hisses; quiet music stops him with his arms down and he says the doorway will not open). `v` steps to the next mode, `V` back (from bars, `V` lands on enik), 1-9/0 pick the first ten, space/n/b/arrows still control playback, Esc (or any other key) returns. It also starts by itself after `SCREENSAVER_SECS` (180) idle while playing; set 0 to disable. Mode choice is remembered.

```bash
scripts/May-The_Lord_Poseidon-Convey-You.py   # (or scripts/deadtui.py) ↵ open, p play (best source on a date: matrix > sbd > aud, on-disk first), ␣ pause,
                       # n/b next/prev, ←→ seek 10 s, </> seek 60 s, / filter, g goto YYYY[-MM-DD],
                       # d fetch show in background (poseidon gdarchive fetch), r resume, s stop, q quit (music stays), Q stop & quit
                       # f song search across all years: one row per date, best source that really has
                       # the track; ↵ opens the show at it, p plays from it, a plays every listed version
                       # in date order (/ filter first, e.g. "1977", to narrow what a queues)
                       # c classical radio, i probe station, v light show (v again cycles its 16 modes, Esc returns)
scripts/deadviz.py     # light show on its own, against whatever PipeWire is playing
```

Song search verifies each date against item metadata, so the first run of a common song takes minutes (Jack Straw: 494 dates, ~10 min) while rows fill in live. Results and metadata are cached, so later runs and the tracks view are instant.

`scripts/gdarchive.py` (stock python3, no pip) searches and downloads from the archive.org Grateful Dead collection into the library: `$POSEIDON_LIBRARY`, else `dead/` beside `scripts/` in a checkout, else `~/Music/dead` (`--dest` overrides per call). Layout: `dead/shows/<year>/<date>.<identifier>/` for whole shows, `dead/songs/<song>/` for single tracks. Resumable, md5-verified, keeps the taper's txt files and an `archive-metadata.json` per show.

```bash
scripts/gdarchive.py search --song "Jack Straw" --year 1977 --min-reviews 5 --sort "avg_rating desc"
scripts/gdarchive.py show <identifier>                          # tracks, formats, rating, downloadable?
scripts/gdarchive.py fetch <identifier> [...]                   # whole show(s), lossless when allowed, tagged, shn->flac
scripts/poseidon.py gdarchive fetch <identifier>                # the same through the dispatcher; a downloaded build: ./poseidon gdarchive fetch <identifier>
scripts/gdarchive.py convert <identifier> [...]                 # shn->flac for a show already on disk
scripts/gdarchive.py songs --song "Jack Straw" --year 1981 --source sbd   # every matching track
scripts/gdarchive.py urls <identifier> --song "Jack Straw"      # direct URLs, e.g. | xargs mpv
```

Facts that shape what you get:

- GD soundboards and matrixes on archive.org are stream-only. FLAC/SHN downloads return 401. The VBR MP3 derivatives are downloadable, so `--format best` falls back to mp3 for those and says so. Pre-FM broadcast soundboards (identifiers with `prefm`/`orefm`/`fm`) are usually not restricted and download lossless.
- Audience tapes download lossless (FLAC or SHN). `--source aud` or `--downloadable` restricts to those.
- SHN (Shorten, 1993) and FLAC are both lossless; SHN just compresses worse, can't seek, and can't hold tags. `fetch` converts SHN downloads to FLAC with ffmpeg, compares the decoded audio, tags the FLAC, then removes the .shn (`--keep-shn` to keep it). `convert <identifier>` does the same for a show already on disk. The taper's `.md5` files name the old .shn files; the archive md5 lives in the `GDARCHIVE_MD5` tag instead.
- `songs` keeps one item per show date. Preference order is `--prefer matrix,sbd,aud` (default), then lossless-downloadable, then rating. `--lossless-first` flips the first two. `--all-sources` keeps every item.
- Matrix (SBD+AUD mix) is the preferred source. Most matrixes are stream-only like SBDs, but a few dozen (Dusborne, Seamons, Chappell, Eichorn mixes) download lossless: `search --source matrix --downloadable --song ...`.
- Most taper FLACs arrive untagged, so Strawberry indexes them with blank titles. `fetch` and `songs` tag FLAC/MP3/OGG after download (title, artist, album `<date> <venue>`, date, track, archive URL) via python3-mutagen. `--no-tag` skips it. Tagging changes the file md5, so the archive md5 is kept in a `GDARCHIVE_MD5` tag and later runs treat those files (and FLACs converted from SHN) as verified; the taper's `.ffp` audio fingerprints still verify. Re-running `fetch <identifier>` on an existing show tags it in place.
- Strawberry: after a fetch, Tools > Rescan songs (or full rescan) so new tags and finished `.part` files replace the mid-download index entries.

## Build and release

Since 2026-09-13 the scripts also ship as single-file downloads, built by pex (`docs/release.md` is the procedure). Two kinds: `poseidon-<ver>.pex`, universal, pure Python with mutagen bundled, boots with `/bin/sh` on any python3 ≥ 3.11 found on PATH and borrows the system's numpy (`--inherit-path=fallback`) for the light show; and `poseidon-<ver>-{linux-x86_64,linux-aarch64,macos-aarch64,macos-x86_64}`, `pex --scie eager` binaries with CPython 3.13 (python-build-standalone, stripped) plus numpy and mutagen inside, needing only mpv on the machine. Windows is WSL 2 and uses the linux-x86_64 file. Versions are calendar tags, `v2026.09.13` (`.1`, `.2` for a second release the same day), stamped into `poseidon --version` and the User-Agent by a `_version.py` that `make stage` writes into `build/src/` (the six shipped scripts copied there; `-D scripts` would dereference the `deadtui.py` symlink into a second copy of the TUI and sweep in `ansi2svg.py`). `make dist` builds both kinds for the current machine into `dist/`, `make check` smoke-tests them against a throwaway `HOME` (never the real `~/.cache/deadtui`), `make clean` removes `build/` and `dist/` (both gitignored; `build/venv` is the only place pip runs). Pushing a `v*` tag runs `.github/workflows/release.yml`: four native runners (ubuntu-24.04, ubuntu-24.04-arm, macos-15, macos-15-intel) each build and smoke-test their scie, the first also the `.pex`, and a final job publishes the GitHub Release with the five files and a `SHA256SUMS`. `ci.yml` runs the syntax check, the symlink guard and the `.pex` build on every push and PR. On the user's machine a scie unpacks its Python into `~/.cache/nce` (macOS `~/Library/Caches/nce`; `SCIE_BASE` relocates) and builds its venv under `~/.cache/pex` (`PEX_ROOT`); both are caches, safe to delete, about 120 MB per release. In a scie the environment carries `SCIE` (the binary's path) and `SCIE_ARGV0`; in a `.pex`, `PEX`; `poseidon.self_command` uses them so the TUI's background fetch re-runs the same artifact.

## FreeBSD notes

Assessed 2026-09-12 for FreeBSD 15 on the X1 Carbon Gen 12. Verdict: not worth moving the listening machine. Stay on Debian/PipeWire. Revisit only if the laptop is replaced with better-supported hardware.

What would carry over:

- `deadtui.py` and `gdarchive.py` are stock Python (curses, socket, urllib, subprocess) plus mpv over a unix socket. mpv is in ports. Only the shebang and the `XDG_RUNTIME_DIR` fallback are Linux-flavored, and the fallback already handles its absence.
- `radio.py` does not carry over: it depends on Strawberry, systemd `busctl`, and `/proc/asound`. Would need `dbus-send` and `/dev/sndstat` instead.

USB audio to the A14 MKII:

- `snd_uaudio` handles USB Audio Class 2 async devices, so the Rotel should enumerate with no driver work.
- Default sound mode resamples everything to one fixed vchan rate, the same behavior PulseAudio had before the 2026-09-11 switch.
- Bit-perfect is exclusive: `sysctl dev.pcm.N.play.vchans=0` and `dev.pcm.N.bitperfect=1` on the Rotel's pcm device, then mpv with `--ao=oss` opens it directly and the DAC follows the file rate. `sysctl hw.snd.verbose=2` then `cat /dev/sndstat` is the equivalent of the hw_params check.
- Cost: one app owns the DAC. Dead playback and a KDFC browser tab cannot both be open. `virtual_oss` mixes but at one fixed rate, which brings resampling back. PipeWire's rate-following shared sink has no clean FreeBSD equivalent.

Platform problems on the Gen 12 (Meteor Lake):

- WiFi: CNVi radio (8086:7e40) is supported by `iwlwifi`, but at 802.11n/ac rates only; ax is still planned as of the 15.1 man page. Enough for FLAC streams. No Ethernet on this laptop.
- Suspend: Meteor Lake is s2idle only, FreeBSD's ACPI S3 path does not apply. Expect lid-close to be unreliable.
- Internal audio: the HDA controller runs in SOF DSP mode and FreeBSD has no SOF. Speakers and mic likely dead. Irrelevant to the Rotel but a sign of how new the platform is there.
- Graphics: needs a recent drm-kmod; GPU hangs reported on similar hardware. Fine for a console TUI, risky for a desktop with Strawberry and a browser.
- The ansible-homelab audio role, systemd user services, and PipeWire rate config are all Linux. The closest hardware thread (T14 Gen 5, Meteor Lake) had no confirmed successful install as of April 2026.

If the exclusive bit-perfect path is ever wanted, mpv against the Rotel's ALSA `hw:` device on Debian gives the same thing without changing OS. Rejected for the same sharing reason; see AUDIO-ANSIBLE.md.

If testing anyway: boot a 15.x memstick image with the Rotel connected, check `dmesg | grep uaudio` and `/dev/sndstat`, play a 48 kHz file with `mpv --ao=oss`, and confirm the rate in sndstat. Do not install over Debian.

References: FreeBSD forum threads on T14 Gen 5 Meteor Lake support and iwlwifi n/ac/ax status; iwlwifi(4) for 15.1; FreeBSD status report 2025 Q2 (LinuxKPI 802.11); cneira.github.io "Bit-perfect sound on FreeBSD".
