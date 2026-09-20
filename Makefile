# Build the release artifacts locally; .github/workflows/release.yml runs the same targets.
# See docs/release.md.
#
#   make dist                   # dist/poseidon-<ver>.pex + dist/poseidon-<ver>-<os>-<arch>
#   make check                  # syntax + symlink guard + smoke tests of both artifacts
#   make dist VERSION=2026.09.13
#
# The build venv under build/ is the only place pip is used; runtime needs no pip.

PEX_VERSION ?= 2.102.0
# Pinned for reproducible builds: the python-build-standalone release and CPython patch
# the scie embeds, and the numpy inside it. Bump all three together after a test build.
PBS_RELEASE ?= 20260901
PY_VERSION  ?= 3.13.15
NUMPY       ?= numpy==2.5.3
# the scie embeds 3.13; resolve numpy with the same minor
PYTHON      ?= python3.13
VENV        := build/venv
PEX         := $(VENV)/bin/pex
STAGE       := build/src
DIST        := dist
VERSION     ?= $(shell git describe --tags --always --dirty 2>/dev/null | sed 's/^v//')
SOURCES     := scripts/poseidon.py scripts/May-The_Lord_Poseidon-Convey-You.py scripts/gdarchive.py \
               scripts/deadviz.py scripts/radio.py scripts/restore-playlist.py
UPEX        := $(DIST)/poseidon-$(VERSION).pex
SCIE_NAME   := $(DIST)/poseidon-$(VERSION)
# pex appends -<os>-<arch> to SCIE_NAME (--scie-name-style platform-file-suffix)

.PHONY: venv stage pex scie dist check check-src smoke-pex smoke-scie clean

$(PEX):
	$(PYTHON) -m venv $(VENV) && $(VENV)/bin/pip install --quiet pex==$(PEX_VERSION)
venv: $(PEX)

# -D scripts would dereference the deadtui.py symlink into a second copy of the TUI and
# sweep in ansi2svg.py and __pycache__; stage exactly the shipped files instead.
stage:
	rm -rf $(STAGE) && mkdir -p $(STAGE) $(DIST)
	install -m 644 $(SOURCES) $(STAGE)/
	printf '__version__ = "%s"\n' "$(VERSION)" > $(STAGE)/_version.py

# Universal: pure Python, bundles only mutagen, uses the system numpy (--inherit-path
# fallback), needs a python3 >= 3.11 with curses on PATH (--sh-boot searches for one).
pex: $(PEX) stage
	$(PEX) mutagen -D $(STAGE) -e poseidon:main \
	  --interpreter-constraint '>=3.11' --inherit-path=fallback --sh-boot -o $(UPEX)

# Self-contained: CPython 3.13 (python-build-standalone) + numpy + mutagen, one file.
# science (pex's scie builder) asks api.github.com for the release's asset list even when
# the release is pinned; unauthenticated, GitHub's shared runner IPs hit the rate limit.
# Export SCIENCE_AUTH_API_GITHUB_COM_BEARER=<token> to authenticate (the workflow does).
scie: $(PEX) stage
	$(PEX) $(NUMPY) mutagen -D $(STAGE) -e poseidon:main --python $(PYTHON) --venv \
	  --scie eager --scie-only --scie-python-version $(PY_VERSION) --scie-pbs-release $(PBS_RELEASE) \
	  --scie-pbs-stripped --scie-platform current --scie-name-style platform-file-suffix -o $(SCIE_NAME)

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
# `doctor` runs under a pty so the static ncurses is really exercised. Its output goes to a
# file, never straight into `grep -q`: grep exits on the first match, the next write to the
# pipe fails, and pty.spawn then stops reading the child for good (it marks stdout dead and
# only selects on stdin), so the child is never drained or reaped and the recipe hangs
# forever. That is what hung the release build in `make scie smoke-scie` six times between
# 2026-09-14 and 2026-09-20, five on Linux x86_64 and once on the Intel Mac; locally the
# output lands in one chunk and gets through. Two greps over the file, one pty run.
smoke-scie:
	SB=$$(mktemp -d) && B=$$(ls $(SCIE_NAME)-*) && $(SANDBOX) sh -c "$$B --version | grep -x 'poseidon $(VERSION)' \
	  && $$B gdarchive --help >/dev/null && $(PTY) $$B doctor > $$SB/doctor.txt; rc=\$$?; cat $$SB/doctor.txt; [ \$$rc = 0 ] \
	  && grep -q 'terminfo: ok' $$SB/doctor.txt && grep -q 'numpy: [0-9]' $$SB/doctor.txt"

clean:
	rm -rf build dist
