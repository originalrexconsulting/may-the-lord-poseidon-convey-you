# Build + release plan: pex artifacts for Linux, macOS and Windows/WSL

Handoff document, written 2026-09-13 in a planning session with the owner. Everything here
is to be implemented by whoever picks it up; the decisions section is settled, the rest is
the design and its verification. Delete or replace this file with `docs/release.md` once the
work lands.


## Context

The repo (GitHub `originalrexconsulting/may-the-lord-poseidon-convey-you`) is a flat
`scripts/` directory of stand-alone Python scripts: no package, no pyproject, no CI, no
tags, no version string. Users must clone it and apt/brew-install Python deps. The goal is
downloadable single-file artifacts per platform so a listener needs only mpv on the
target, plus a repeatable, tag-driven release flow.

### Decisions (made with the owner on 2026-09-13, do not re-open)

- **Artifacts, both kinds:**
  (a) one universal `poseidon-<ver>.pex`: pure Python, bundles only `mutagen`, uses the
  system's numpy for the light show via `--inherit-path fallback`, needs a python3 ≥ 3.11
  with curses on PATH, boots via `--sh-boot`;
  (b) self-contained `pex --scie eager` binaries with CPython 3.13 (python-build-standalone)
  and numpy embedded: `poseidon-<ver>-linux-x86_64`, `-linux-aarch64`, `-macos-aarch64`,
  `-macos-x86_64`. Windows = WSL 2 = the linux-x86_64 files. No native Windows.
- **CI:** GitHub Actions. Tag push `v*` runs a 4-runner matrix, smoke-tests every artifact,
  publishes a GitHub Release with `SHA256SUMS`. A `Makefile` runs the identical build locally.
- **Versioning:** calendar tags `v2026.09.13` (`.1`, `.2` for a second release the same day).
  Stamped into `poseidon --version` and the HTTP User-Agent
  `may-the-lord-poseidon-convey-you/<ver> (+https://github.com/originalrexconsulting/may-the-lord-poseidon-convey-you)`.
- **Entry points:** one artifact `poseidon`, busybox-style. Bare `poseidon` = the TUI.
  `poseidon gdarchive|deadviz|radio|restore-playlist ...` run the tools; `poseidon doctor`,
  `poseidon --version`. Also dispatch on the invoked basename so a symlink named
  `gdarchive` or `deadtui` works. The TUI's background fetch re-execs the same artifact.
- `scripts/May-The_Lord_Poseidon-Convey-You.py` **stays the canonical file and name**.
  `scripts/deadtui.py` is the nickname and **must be a symlink again**. It was a git symlink
  (mode 120000) until commit 674fad9; commit b83acef's in-place shebang edit (the `sed -i`
  pattern, which replaces a symlink with a file) turned it into a stale copy, now two
  commits behind.

### Facts that shape the design

Code (all in `scripts/`):
- `May-The_Lord_Poseidon-Convey-You.py` (2042 lines): the TUI. Imports siblings after
  `sys.path.insert(0, dirname(abspath(__file__)))` (L89-95); `deadviz` import is guarded
  (numpy optional). L1584 re-execs `gdarchive.py` by `__file__` path for background fetches.
  Uses `gd.DEFAULT_DEST` at L401, L984, L1065-1066, L1146 and `gd.UA` at L619.
- `gdarchive.py` (736 lines): `DEFAULT_DEST = os.path.expanduser("~/projects/audiophile/dead")`
  at L59 is hardcoded to the owner's checkout: the main distribution blocker. `UA` at L75.
  `--dest` defaults at L676 and L718. `fetch_item` already `makedirs` the outdir (L550).
  Optional `mutagen` import inside a function (L406-408).
- `deadviz.py` (987): `import numpy` unguarded at L50. `radio.py` (267): STATIONS + Linux-only
  Strawberry commands. `restore-playlist.py` (71): stdlib only, duplicates the UA string at
  L29, hyphenated name so not importable. `ansi2svg.py`: dev tool, not shipped.
- Runtime state is all under `~/.cache/deadtui/` and `$XDG_RUNTIME_DIR/deadtui-mpv.sock`;
  no data files are read relative to `__file__`. External binaries: mpv (required),
  ffmpeg/ffprobe, parec (Linux tap), strawberry/busctl/pgrep (radio.py Linux-only).
- Syntax needs only Python 3.7; docs promise 3.11+. numpy 2.5.3 needs Python ≥ 3.12 and
  has cp313 wheels for manylinux_2_28 x86_64/aarch64, macosx_11_0_arm64, macosx_10_13_x86_64.

Tooling (verified against pex 2.102.0 source and docs on 2026-09-13):
- pex sets `os.environ["PEX"]` to the pex path at boot, and `--strip-pex-env` (the default)
  removes only `PEX_*`/`__PEX_*` keys, so `PEX` survives. No `--no-strip-pex-env` needed.
- scie-jump sets `SCIE` (absolute path of the scie executable) and `SCIE_ARGV0` (argv[0]
  as invoked, symlink name preserved). Unpack base: `~/.cache/nce` (Linux),
  `~/Library/Caches/nce` (macOS); `SCIE_BASE` overrides.
- `-D DIR` walks the dir and `shutil.copy`s files, dereferencing symlinks: `-D scripts` would
  ship a second copy of the TUI as `deadtui.py`, plus `ansi2svg.py` and `__pycache__`.
  Hence sources are staged into `build/src/`.
- `--scie-platform` values include `linux-x86_64 linux-aarch64 macos-x86_64 macos-aarch64`
  and `current`. `--scie-name-style platform-file-suffix` appends `-<os>-<arch>`.
  `--scie-only` suppresses the .pex; `--scie-pbs-stripped` halves the Python size.
  `--scie-hash-alg sha256` can emit checksum files (we build SHA256SUMS ourselves instead).
- `--inject-env`/`--inject-args` exist but are not used (version is stamped as a file).
- python-build-standalone statically links ncurses and its docs warn that terminfo lookup
  may need `TERMINFO_DIRS`. The launcher sets a fallback before any curses import.
- GitHub runner labels confirmed: `ubuntu-24.04`, `ubuntu-24.04-arm`, `macos-15` (arm64),
  `macos-15-intel` (x86_64).

## Implementation plan

Order: Phase A → B → C → D. Verify after each phase with the checklist in Phase E.

### Phase A: code changes in `scripts/`

### A1. New `scripts/poseidon.py` (executable, `#!/usr/bin/env python3`, stdlib only)

The dispatcher and the shared helpers. Imports nothing from siblings at module level (the
siblings import it, so this avoids cycles).

```python
#!/usr/bin/env python3
"""poseidon - one door to every tool. Bare `poseidon` is the TUI; `poseidon <tool> ...` runs a tool.

Tools: gdarchive, deadviz, radio, restore-playlist, tui. Also: doctor, --version.
A symlink named after a tool (gdarchive, deadtui, ...) runs that tool directly.
"""
import functools, os, runpy, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_URL = "https://github.com/originalrexconsulting/may-the-lord-poseidon-convey-you"
TUI = "May-The_Lord_Poseidon-Convey-You.py"
TOOLS = {"tui": TUI, "deadtui": TUI, "may-the_lord_poseidon-convey-you": TUI,
         "gdarchive": "gdarchive.py", "deadviz": "deadviz.py", "radio": "radio.py",
         "restore-playlist": "restore-playlist.py"}
SUBCOMMANDS = ("gdarchive", "deadviz", "radio", "restore-playlist", "tui")
TERMINFO_DIRS = ("/usr/share/terminfo", "/lib/terminfo", "/etc/terminfo", "/usr/lib/terminfo",
                 "/usr/local/share/terminfo", "/opt/homebrew/share/terminfo")

@functools.lru_cache(maxsize=None)
def version():
    try:
        from _version import __version__          # written by `make stage` into build/src only
        return __version__
    except ImportError:
        pass
    if os.path.isdir(os.path.join(os.path.dirname(HERE), ".git")):
        try:
            r = subprocess.run(["git", "-C", HERE, "describe", "--tags", "--always", "--dirty"],
                               capture_output=True, text=True, timeout=3)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip().lstrip("v")
        except OSError:
            pass
    return "dev"

def user_agent():
    return f"may-the-lord-poseidon-convey-you/{version()} (+{REPO_URL})"

def library_dir():
    """$POSEIDON_LIBRARY, else dead/ beside scripts/ in a checkout, else ~/Music/dead."""
    env = os.environ.get("POSEIDON_LIBRARY")
    if env:
        return os.path.expanduser(env)
    checkout = os.path.join(os.path.dirname(HERE), "dead")
    if os.path.isdir(checkout):
        return checkout
    return os.path.expanduser("~/Music/dead")

def running_as():
    return "scie" if os.environ.get("SCIE") else "pex" if os.environ.get("PEX") else "checkout"

def self_command(args):
    """argv that runs this program again: the scie, the .pex, or the checkout's poseidon.py."""
    scie = os.environ.get("SCIE")
    if scie and os.path.isfile(scie):
        return [scie, *args]
    pex = os.environ.get("PEX")
    if pex and os.path.exists(pex):
        return [sys.executable, pex, *args]
    return [sys.executable, os.path.join(HERE, "poseidon.py"), *args]

def _terminfo_fallback():
    if os.environ.get("TERMINFO") or os.environ.get("TERMINFO_DIRS"):
        return
    dirs = [d for d in TERMINFO_DIRS if os.path.isdir(d)]
    if dirs:
        os.environ["TERMINFO_DIRS"] = os.pathsep.join(dirs)

def _tool_from_argv0():
    # In a scie the Python process sees the pex path as argv[0]; scie-jump keeps the
    # invoked name (symlink name included) in SCIE_ARGV0.
    name = os.path.basename(os.environ.get("SCIE_ARGV0") or sys.argv[0]).lower()
    for ext in (".py", ".pex"):
        if name.endswith(ext):
            name = name[:-len(ext)]
    return TOOLS.get(name)          # "poseidon", "poseidon-2026.09.13-linux-x86_64" -> None

def run(filename, argv):
    sys.argv = [f"poseidon {os.path.splitext(filename)[0]}", *argv]   # argparse prog
    runpy.run_path(os.path.join(HERE, filename), run_name="__main__")

def doctor():
    # One "key: value" line each, exit 0 always; CI greps the lines it needs:
    # version, running as, python (version + sys.executable), platform,
    # numpy: <ver>|missing, mutagen: <ver>|missing,
    # mpv/ffmpeg/ffprobe/parec: shutil.which or "not found",
    # library: library_dir() (+ "exists" / "created on first fetch"),
    # cache: ~/.cache/deadtui, socket: ($XDG_RUNTIME_DIR or cache)/deadtui-mpv.sock,
    # TERM, TERMINFO_DIRS,
    # terminfo: "ok (N colors)" from curses.setupterm()+tigetnum("colors") or "FAILED: <err>",
    # re-exec: self_command(["gdarchive", "fetch", "<id>"]).
    ...

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    _terminfo_fallback()
    tool = _tool_from_argv0()
    if tool:
        return run(tool, argv)
    if argv and argv[0] in ("--version", "-V"):
        print(f"poseidon {version()}"); return
    if argv and argv[0] in ("--help", "-h"):
        print(__doc__); return
    if argv and argv[0] == "doctor":
        return doctor()
    if argv and argv[0] in SUBCOMMANDS:
        return run(TOOLS[argv[0]], argv[1:])
    if argv:
        sys.exit(f"poseidon: unknown tool {argv[0]!r}; one of {', '.join(SUBCOMMANDS)}, doctor, --version")
    return run(TUI, [])

if __name__ == "__main__":
    main()
```

Why these choices:
- `runpy.run_path(..., run_name="__main__")` for every tool: two files are not importable
  by name, and every script already does its work in `main()` under the `__main__` guard,
  so each runs exactly as it does today (`__file__`, sibling `sys.path` insert included).
- Version as a staged `_version.py`, not `--inject-env`: independent of pex plumbing,
  works the same in pex, scie and a future tarball; the checkout never holds a stale file.
- `self_command` order SCIE → PEX → checkout; no `PYTHONPATH` tricks (they would leak
  bootstrap paths to mpv/ffmpeg grandchildren and bypass pex's own boot).
- `version()` is cached: `gdarchive` calls it at import for `UA`.

### A2. `scripts/gdarchive.py`
- After the stdlib imports: `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))`
  then `import poseidon`.
- L59: `DEFAULT_DEST = poseidon.library_dir()` with a comment naming the rule
  (`$POSEIDON_LIBRARY` > `dead/` beside `scripts/` in a checkout > `~/Music/dead`).
  Keep the name `DEFAULT_DEST`: the TUI's five call sites (two inside per-frame `render()`
  closures) stay textually unchanged and the two `--dest` defaults follow automatically.
- L75: `UA = poseidon.user_agent()`.
- `--dest` help at L676/L718: add `(default: %(default)s)`. Docstring: one sentence on
  the library location and `POSEIDON_LIBRARY`.

### A3. `scripts/May-The_Lord_Poseidon-Convey-You.py`
- L91, after `import gdarchive as gd`: `import poseidon  # noqa: E402`.
- L1584-1586: Popen argv becomes `poseidon.self_command(["gdarchive", "fetch", doc["identifier"]])`;
  keep stdin/stdout/stderr/`start_new_session=True`.
- User-visible strings that say `gdarchive.py fetch` (L45 docstring, L1580 message): say
  `poseidon gdarchive fetch <id>`.
- `gd.DEFAULT_DEST` uses at L401, L984, L1065-1066, L1146: unchanged; re-read each to
  confirm they are `isdir`/`listdir`/`realpath` guarded (they are).

### A4. `scripts/restore-playlist.py`
- Add the same `sys.path.insert(...)`; in the "no player running" branch replace the inline
  UA literal (L29) with `import poseidon; ua = poseidon.user_agent()`.

### A5. `scripts/deadtui.py` back to a symlink
```
git rm --quiet scripts/deadtui.py
ln -s May-The_Lord_Poseidon-Convey-You.py scripts/deadtui.py
git add scripts/deadtui.py        # git ls-files -s shows mode 120000
```
Never edit `scripts/*.py` in place with `sed -i` again; that is what broke it.

### A6. `.gitignore`: add `build/` and `dist/`.

### Phase B: `Makefile` at the repo root

```make
PEX_VERSION ?= 2.102.0
PYTHON      ?= python3.13        # the scie embeds 3.13; resolve numpy with the same minor
VENV        := build/venv
PEX         := $(VENV)/bin/pex
STAGE       := build/src
DIST        := dist
VERSION     ?= $(shell git describe --tags --always --dirty 2>/dev/null | sed 's/^v//')
SOURCES     := scripts/poseidon.py scripts/May-The_Lord_Poseidon-Convey-You.py scripts/gdarchive.py \
               scripts/deadviz.py scripts/radio.py scripts/restore-playlist.py
UPEX        := $(DIST)/poseidon-$(VERSION).pex
SCIE_NAME   := $(DIST)/poseidon-$(VERSION)          # pex appends -<os>-<arch>

.PHONY: venv stage pex scie dist check check-src smoke-pex smoke-scie clean

$(PEX):
	$(PYTHON) -m venv $(VENV) && $(VENV)/bin/pip install --quiet pex==$(PEX_VERSION)
venv: $(PEX)

stage:
	rm -rf $(STAGE) && mkdir -p $(STAGE) $(DIST)
	install -m 644 $(SOURCES) $(STAGE)/
	printf '__version__ = "%s"\n' "$(VERSION)" > $(STAGE)/_version.py

pex: $(PEX) stage
	$(PEX) mutagen -D $(STAGE) -e poseidon:main \
	  --interpreter-constraint '>=3.11' --inherit-path fallback --sh-boot -o $(UPEX)

scie: $(PEX) stage
	$(PEX) numpy mutagen -D $(STAGE) -e poseidon:main --python $(PYTHON) --venv \
	  --scie eager --scie-only --scie-python-version 3.13 --scie-pbs-stripped \
	  --scie-platform current --scie-name-style platform-file-suffix -o $(SCIE_NAME)

dist: pex scie

check-src:
	$(PYTHON) -m py_compile scripts/*.py
	test -L scripts/deadtui.py && test "$$(readlink scripts/deadtui.py)" = May-The_Lord_Poseidon-Convey-You.py

check: check-src smoke-pex smoke-scie

# Smoke tests run against a throwaway HOME and no XDG_RUNTIME_DIR: they must never touch
# a real ~/.cache/deadtui/state.json or a running mpv.
SANDBOX = env -u XDG_RUNTIME_DIR HOME=$$SB PEX_ROOT=$$SB/.cache/pex SCIE_BASE=$$SB/.cache/nce TERM=xterm-256color
PTY     = $(PYTHON) -c 'import pty,sys; sys.exit(pty.spawn(sys.argv[1:]) >> 8)'

smoke-pex:
	SB=$$(mktemp -d) && $(SANDBOX) sh -c '$(UPEX) --version | grep -x "poseidon $(VERSION)" \
	  && $(UPEX) gdarchive --help >/dev/null && $(UPEX) radio list >/dev/null && $(UPEX) doctor'
smoke-scie:
	SB=$$(mktemp -d) && B=$$(ls $(SCIE_NAME)-*) && $(SANDBOX) sh -c "$$B --version | grep -x 'poseidon $(VERSION)' \
	  && $$B gdarchive --help >/dev/null && $(PTY) $$B doctor | tee /dev/stderr | grep -q 'terminfo: ok' \
	  && $(PTY) $$B doctor | grep -q 'numpy: [0-9]'"

clean:
	rm -rf build dist
```

Notes:
- `mutagen` ships a `py3-none-any` wheel, so one resolve serves every Python ≥ 3.11.
  `--sh-boot` searches PATH for a satisfying interpreter. `--inherit-path fallback` lets
  `import numpy` find the distro's `python3-numpy`.
- `-o dist/poseidon-<ver>` has no `.pex` extension and `--scie-only` is set, so the only
  output is `poseidon-<ver>-linux-x86_64` etc. `--python python3.13` pins the resolve to
  cp313 so the wheels match the embedded interpreter.
- After the first green build, pin `numpy==2.5.3` and `--scie-pbs-release YYYYMMDD` for
  reproducible re-releases.
- Cross-build recipe, only if a native runner is unavailable: replace
  `--python $(PYTHON) --scie-platform current` with
  `--platform macosx_10_13_x86_64-cp-313-cp313 --scie-platform macos-x86_64` (or
  `manylinux_2_28_aarch64-cp-313-cp313` / `linux-aarch64`). Wheel-only resolve; cannot be
  smoke-tested on that host.
- The build venv is the only place pip is used; runtime stays "no pip".
- Override the version: `make dist VERSION=2026.09.13`.

### Phase C: GitHub Actions

### C1. `.github/workflows/ci.yml` (push to main + PRs)
```yaml
name: ci
on: { push: { branches: [main] }, pull_request: {} }
jobs:
  check:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: make check-src
      - run: make pex smoke-pex
      - uses: actions/upload-artifact@v4
        with: { name: poseidon-pex, path: dist/*.pex, retention-days: 7 }
```

### C2. `.github/workflows/release.yml` (tags `v*` + manual)
```yaml
name: release
on:
  push: { tags: ["v*"] }
  workflow_dispatch: {}
permissions: { contents: write }
jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        include:
          - { os: ubuntu-24.04,     universal: true }
          - { os: ubuntu-24.04-arm, universal: false }
          - { os: macos-15,         universal: false }   # arm64
          - { os: macos-15-intel,   universal: false }   # x86_64; if the label goes away, cross-build on macos-15
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }                          # git describe needs the tags
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - id: ver
        shell: bash
        run: |
          if [[ "$GITHUB_REF_TYPE" == tag ]]; then
            [[ "$GITHUB_REF_NAME" =~ ^v[0-9]{4}\.[0-9]{2}\.[0-9]{2}(\.[0-9]+)?$ ]] || { echo "bad tag $GITHUB_REF_NAME"; exit 1; }
            echo "version=${GITHUB_REF_NAME#v}" >> "$GITHUB_OUTPUT"
          else
            echo "version=$(git describe --tags --always --dirty | sed 's/^v//')" >> "$GITHUB_OUTPUT"
          fi
      - run: make check-src
      - run: make scie smoke-scie VERSION=${{ steps.ver.outputs.version }}
      - if: matrix.universal
        run: make pex smoke-pex VERSION=${{ steps.ver.outputs.version }}
      - uses: actions/upload-artifact@v4
        with: { name: dist-${{ matrix.os }}, path: dist/*, if-no-files-found: error }
  release:
    needs: build
    if: github.ref_type == 'tag'
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/download-artifact@v4
        with: { path: dist, merge-multiple: true }
      - run: cd dist && sha256sum * > SHA256SUMS && cat SHA256SUMS
      - env: { GH_TOKEN: "${{ github.token }}" }
        run: |
          v=${GITHUB_REF_NAME#v}
          cat > notes.md <<EOF
          ## Install
          One file, no Python needed. Linux x86_64 / aarch64, macOS arm64 / x86_64; WSL uses linux-x86_64.
          \`\`\`
          curl -fLo poseidon https://github.com/${GITHUB_REPOSITORY}/releases/download/${GITHUB_REF_NAME}/poseidon-${v}-linux-x86_64
          chmod +x poseidon && ./poseidon doctor && ./poseidon
          \`\`\`
          Or \`poseidon-${v}.pex\` for any Python 3.11+ (uses your system numpy for the light show).
          Needs mpv; ffmpeg optional. Verify: \`sha256sum -c SHA256SUMS --ignore-missing\`.
          EOF
          gh release create "$GITHUB_REF_NAME" --title "$GITHUB_REF_NAME" --generate-notes --notes-file notes.md dist/*
```
mpv is deliberately absent on runners; `doctor` reports it missing and the smoke tests do
not grep for it. Run the workflow once via `workflow_dispatch` (no tag, artifacts only)
before cutting the first tag.

### Phase D: docs

- `README.md`: header line becomes "Stock Python 3 (curses), mpv, PipeWire. No pip: run
  the scripts from a clone, or download one self-contained build from Releases." Add
  `scripts/poseidon.py` to the script list. "Running it" opens with a **Download**
  paragraph: the curl/chmod snippet, which file for which machine, `.pex` for the
  Python-present case, `poseidon doctor`, `POSEIDON_LIBRARY` and the `~/Music/dead`
  default (clone: `dead/` next to `scripts/`). Fix "(WSL; guide to come)".
- `docs/setup-linux.md`, `docs/setup-macos.md`: new "0. Or just download a build" before
  "1. Packages" (scie needs only mpv; ffmpeg/pulseaudio-utils optional; nothing Python).
  Section 2 states the library-path rule. Section 5 lists `~/.cache/nce` (scie unpack,
  safe to delete) and `~/.cache/pex`. macOS: `~/Library/Caches/nce`, Gatekeeper
  (`xattr -d com.apple.quarantine poseidon` after a browser download; curl sets no
  attribute), and that the scie drops the `brew install python numpy` requirement.
- `docs/setup-windows.md`, written properly: WSL 2 + Ubuntu 24.04; `sudo apt install mpv
  pulseaudio-utils ffmpeg`; WSLg provides a PulseAudio server (`PULSE_SERVER` preset,
  `pactl info` to check) so mpv plays to Windows' default device and `parec` taps WSLg's
  sink monitor for the light show; download `poseidon-<ver>-linux-x86_64` into the Linux
  home (not `/mnt/c`), `chmod +x`, `./poseidon doctor`; Windows Terminal with Cascadia
  Mono for 256 colours and braille glyphs; library defaults to `~/Music/dead` in the
  distro, `POSEIDON_LIBRARY=/mnt/d/dead` to keep music on a Windows drive (slower);
  `~/.cache/nce`; radio.py's Strawberry commands do not apply.
- `SYSTEM.md`: a `scripts/poseidon.py` paragraph in Scripts (dispatcher, `self_command`,
  `library_dir`, `version`, terminfo fallback); a new "Build and release" section
  (artifacts, `make dist`, tag flow, unpack locations); the Portability paragraph gains a
  sentence on the scie/PBS terminfo handling; `gdarchive.py fetch` examples also show the
  `poseidon gdarchive fetch` form.
- New `docs/release.md`: version scheme; `git tag -a v2026.09.13 -m ... && git push origin
  v2026.09.13`; what the workflow does; local `make dist` / `make check`; manual fallback
  (`gh auth login`, `gh release create`); cache locations and how to wipe them; the
  cross-build recipe. Replace `docs/build-release-plan.md` with a pointer to it (or delete
  the plan) once implementation lands.

### Phase E: verification checklist

Checkout, no artifacts:
1. `scripts/poseidon.py --version` prints `poseidon <git-describe>`; after tagging, `poseidon 2026.09.13`.
2. `scripts/poseidon.py doctor`: `running as: checkout`, library = the checkout's `dead/`,
   numpy and mutagen versions (or `missing`), `terminfo: ok (256 colors)`, re-exec shows
   `[python, .../scripts/poseidon.py, gdarchive, ...]`.
3. `scripts/poseidon.py gdarchive --help` shows prog `poseidon gdarchive`;
   `scripts/gdarchive.py --help` still works standalone; `--dest` default is the checkout `dead/`.
4. `test -L scripts/deadtui.py`; `git ls-tree HEAD scripts/deadtui.py` shows `120000`;
   `scripts/deadtui.py` still starts the TUI.
5. `POSEIDON_LIBRARY=/tmp/x scripts/poseidon.py doctor` shows the override; a copy of
   `scripts/` with no `dead/` sibling and `HOME=$(mktemp -d)` resolves `~/Music/dead`.
6. `python3 -c 'import sys; sys.path.insert(0,"scripts"); import gdarchive; print(gdarchive.UA)'`
   prints the new UA with the version.
7. Sandboxed TUI (`HOME`/`XDG_RUNTIME_DIR` elsewhere, mpv `ao=null`): `d` on a small show;
   the fetch log shows the child ran via `poseidon`; files land under the sandbox library.
   Never run this against the owner's live player or state.

Artifacts (`make check`, sandboxed HOME):
8. `dist/poseidon-<ver>.pex`: `--version`, `doctor` (`running as: pex`, numpy from the
   system via inherit-path, `PEX` path in re-exec), `gdarchive --help`, `radio list`.
9. `dist/poseidon-<ver>-linux-x86_64`: `--version`; `doctor` under a pty shows `running as:
   scie`, python 3.13.x from the sandboxed nce dir, `numpy: 2.5.x`, `terminfo: ok`, re-exec
   `[<SCIE path>, gdarchive, ...]`.
10. `ln -s dist/poseidon-<ver>-linux-x86_64 /tmp/gdarchive && /tmp/gdarchive --help` shows
    gdarchive's help (argv0 dispatch via `SCIE_ARGV0`); same trick with the `.pex` under a
    symlink named `gdarchive` (plain `sys.argv[0]`).
11. Second run of the scie starts in well under a second (nce warm).
12. Push a branch: `ci` green. Push `v2026.09.13`: four build jobs green, the release has
    six assets, `sha256sum -c SHA256SUMS --ignore-missing` passes on a downloaded pair.
13. macOS job logs show `terminfo: ok` inside the PBS build: the single most important
    thing the mac runners prove, since the macOS guide was written blind.

First-build checks (could not be verified from source ahead of time):
- Does `sys.argv[0]` inside a `--sh-boot` pex invoked through a symlink keep the symlink
  path? If not, argv0 dispatch for the `.pex` needs `PEX` plus `os.path.basename(sys.argv[0])`
  reconsidered; the scie path is covered by `SCIE_ARGV0`.
- Does pex accept `--python python3.13` together with `--scie-python-version 3.13` without
  complaint on all four runners (it should; both name the same minor).
- Whether `curses.setupterm()` in `doctor` needs the pty on macOS runners (the Makefile
  already provides one).

### Risks and mitigations

| Risk | Mitigation |
|---|---|
| PBS's static ncurses cannot find terminfo (macOS hashed db, distros with only `/lib/terminfo`) | `_terminfo_fallback()` sets `TERMINFO_DIRS` from existing dirs before any curses import; `doctor` reports `setupterm`; CI greps `terminfo: ok` on all four platforms. Escape hatches documented: `TERMINFO_DIRS=...`, or use the `.pex` with the system Python. |
| `-D` dereferences `deadtui.py` and sweeps in `ansi2svg.py`/`__pycache__` | Stage the six shipped files into `build/src/`. |
| numpy cp313 manylinux_2_28 needs glibc ≥ 2.28 (Debian 10+, Ubuntu 18.10+, RHEL 8+) | Fine for every target; document the floor. Pin `numpy==2.5.3` after the first green build. |
| Intel mac runner retired | `macos-15-intel` exists today; cross-build recipe documented, smoke test skipped for that job. |
| First run of the eager scie unpacks ~60 MB and builds a venv | Several seconds once; `doctor` is the recommended first command. Documented. |
| `~/.cache/nce` grows by ~150 MB per release, never pruned | Docs: deleting it is always safe; `SCIE_BASE` relocates it. Same for `~/.cache/pex`. |
| Universal pex on a Mac with only Apple's python3 (3.9) | `--sh-boot` fails with a clear "no interpreter satisfying >=3.11"; README positions the scie as the default download. |
| `SCIE` inherited from an unrelated parent scie | Accepted; noted in the `self_command` docstring. |
| `gh` not logged in on the developer machine | Releases are cut by CI from the tag; local `gh release create` is a documented fallback. |
| `version()` runs `git describe` at gdarchive import in a checkout | 3 s timeout, cached, errors swallowed, skipped without `.git`. |

Out of scope, noted for later: `HW_PARAMS` is hardcoded to the owner's DAC card (`R20`)
in the TUI and radio.py; other Linux users get a blank DAC readout. Auto-discovering the
running `/proc/asound/*/pcm0p/sub0/hw_params` would fix it.

### Environment the implementing session needs

- Linux or macOS with `git`, `make`, a CPython 3.13 (`python3.13` on PATH, or pass
  `PYTHON=python3.12`; numpy needs ≥ 3.12), network access to PyPI and GitHub (pex
  downloads python-build-standalone and the `science` binary on first scie build).
- Push rights on the GitHub repo (or a fork and a PR), and Actions enabled.
- mpv is not needed to build or smoke-test; it is needed only to try the TUI for real.
- Do not `sed -i` anything under `scripts/`; edit with a tool that follows symlinks or
  edit the canonical file only.
