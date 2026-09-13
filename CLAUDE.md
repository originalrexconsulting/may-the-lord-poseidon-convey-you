# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

A terminal player for the archive.org Grateful Dead collection and the audio plumbing
around it. `README.md` is the tour, `SYSTEM.md` the reference (every script, every key,
the archive.org facts), `docs/setup-*.md` the per-OS guides.

## Current work: build + release system

`docs/build-release-plan.md` is a complete, settled plan for a build + release system
(one `poseidon` dispatcher over the existing scripts, a universal `.pex` plus `pex --scie`
binaries for Linux and macOS, a Makefile, tag-driven GitHub Actions releases). If you are
asked to implement the build or release system, read that file first and follow it in the
order given. Its Decisions section is settled with the owner; do not re-open it. Work on a
branch, run its Phase E checklist, open a PR. Replace the plan with `docs/release.md`
when the work lands.

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
python3 -m py_compile scripts/*.py                     # syntax check
test -L scripts/deadtui.py                             # the symlink guard
```
