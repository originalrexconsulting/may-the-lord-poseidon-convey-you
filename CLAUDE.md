# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

A terminal player for the archive.org Grateful Dead collection and the audio plumbing
around it. `README.md` is the tour, `SYSTEM.md` the reference (every script, every key,
the archive.org facts), `docs/setup-*.md` the per-OS guides.

## Build and release

`docs/release.md` is the procedure: `make dist` / `make check` locally, a `v2026.09.13`-style
tag drives `.github/workflows/release.yml` (four native runners, GitHub Release with
`SHA256SUMS`). `scripts/poseidon.py` is the dispatcher and the artifacts' entry point.
`build/` and `dist/` are gitignored build output.

## Rules

- `scripts/May-The_Lord_Poseidon-Convey-You.py` is the canonical TUI and its canonical
  name. `scripts/deadtui.py` is a nickname and must stay a symlink to it (git mode 120000).
  Never run `sed -i` or any in-place rewrite over `scripts/*.py`: that is exactly how the
  symlink once became a stale copy. Edit the canonical file only.
- The scripts are stock Python 3 (curses) plus mpv; runtime needs no pip. A build venv
  under a gitignored `build/` is the only place pip is used.
- Runtime state lives outside the repo: `~/.cache/deadtui/` (state.json, history,
  caches) and `$XDG_RUNTIME_DIR/deadtui-mpv.sock`. When testing, point `HOME` at a
  temporary directory and unset `XDG_RUNTIME_DIR`; never touch a real state.json or a
  running mpv. Use `mpv --ao=null` for a sandboxed player.
- `dead/shows/`, `dead/songs/`, `dead/jgb/`, `dead/lp/` hold the music (gitignored,
  many GB). `PRIVATE.md` and `manuals/` are gitignored house notes; do not commit them.
- Python 3.11 or newer is the supported floor; the scie build embeds 3.13 because
  numpy 2.5 needs 3.12+.

## Commands

```bash
scripts/May-The_Lord_Poseidon-Convey-You.py            # the TUI
scripts/gdarchive.py search --song "Jack Straw" --year 1977
scripts/gdarchive.py fetch <identifier>                # download a show
scripts/deadviz.py                                     # light show, standalone
scripts/radio.py list                                  # classical stations
scripts/restore-playlist.py --snapshot dead/playlist-$(date +%F).json
scripts/poseidon.py doctor                             # what this checkout/build sees
make check-src                                         # syntax check + the symlink guard
make dist && make check                                # build both artifacts, smoke-test them
```
