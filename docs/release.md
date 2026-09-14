# Building and releasing

How the downloadable builds are made. What they are and where they unpack is in
`SYSTEM.md` ("Build and release"); the user-side instructions are in `README.md` and the
`docs/setup-*.md` guides.

## Versions

Calendar tags: `v2026.09.13`. A second release the same day is `v2026.09.13.1`, a third
`.2`. The release workflow rejects any other shape. The version is the tag without the
`v`, stamped into `poseidon --version` and into gdarchive's User-Agent
(`may-the-lord-poseidon-convey-you/2026.09.13 (+https://github.com/originalrexconsulting/may-the-lord-poseidon-convey-you)`).
Between tags a checkout reports `git describe` (`v2026.09.13-3-gabc1234`, `-dirty` when
modified) and a copy without `.git` reports `dev`.

## Cutting a release

```
git checkout main && git pull
make check-src && make dist && make check     # the same build CI will do, on this machine
git tag -a v2026.09.13 -m "v2026.09.13"
git push origin v2026.09.13
```

The tag push runs `.github/workflows/release.yml`:

1. `build`, a four-runner matrix: `ubuntu-24.04` (x86_64), `ubuntu-24.04-arm`,
   `macos-15` (Apple silicon), `macos-15-intel`. Each checks out with full history,
   installs Python 3.13, runs `make check-src`, then `make scie smoke-scie` for its own
   platform. The x86_64 Linux runner also runs `make pex smoke-pex` for the universal
   `.pex`. Every smoke test runs the artifact against a throwaway `HOME`: `--version`
   must print the tag's version, `gdarchive --help` must work, and `doctor` under a pty
   must show `terminfo: ok` and a numpy version. mpv is absent on runners by design;
   `doctor` says `mpv: not found` and nothing greps for it.
2. `release`: downloads the five artifacts, writes `SHA256SUMS`, and runs
   `gh release create` with the tag, install notes and auto-generated notes.

About ten minutes end to end. Each build job has `timeout-minutes: 15`: twice on
2026-09-14 (the Linux x86_64 job of `v2026.09.14`, the Intel Mac job of `v2026.09.14.2`)
a runner hung in `make scie smoke-scie` while the same step took minutes elsewhere, and
without the timeout it would have sat for GitHub's six hours. When one job times out,
`gh run rerun --job <job-id>` reruns just that job; the other jobs' artifacts are kept and
the publish job follows. The release page then has six assets:
`poseidon-<ver>.pex`, the four `poseidon-<ver>-<os>-<arch>` binaries, and `SHA256SUMS`.
`sha256sum -c SHA256SUMS --ignore-missing` verifies a downloaded pair.

`workflow_dispatch` (Actions tab, "Run workflow", or `gh workflow run release.yml`) runs
the `build` matrix without publishing: the artifacts appear on the run page for a week.
Do that once before the first tag after a change to the build.

`.github/workflows/ci.yml` runs on every push to `main` and every pull request: syntax
check, the `scripts/deadtui.py` symlink guard, and the `.pex` build with its smoke test.

## Building locally

```
make dist                # dist/poseidon-<ver>.pex and dist/poseidon-<ver>-<os>-<arch> for this machine
make check               # check-src + smoke-pex + smoke-scie
make dist VERSION=2026.09.13
make clean               # removes build/ and dist/
```

Needs `git`, `make`, a CPython 3.13 on PATH as `python3.13` (`make PYTHON=python3.12`
also works; numpy 2.5 needs 3.12 or newer), and network access to PyPI and GitHub: the
first `make scie` downloads python-build-standalone and the `science` tool into
`~/.cache/pex`. `build/venv` holds pex itself and is the only place pip is used; the
runtime never needs pip. `make stage` copies the six shipped scripts into `build/src/`
and writes `_version.py` there; the checkout never holds a version file.

The scie build is pinned at the top of the Makefile: `PBS_RELEASE` (the
python-build-standalone release), `PY_VERSION` (its CPython patch) and `NUMPY`. A
rebuild months later produces the same binary. To move to a newer Python, bump the
three together, `make scie smoke-scie`, and run the release workflow's dry run before
tagging.

`science`, pex's scie builder, asks `api.github.com` for the release's asset list even
when the release is pinned. Unauthenticated, GitHub's shared runner addresses hit the
API rate limit (the v2026.09.13.4 run failed that way on the Apple silicon job). The
workflow exports `SCIENCE_AUTH_API_GITHUB_COM_BEARER` with the job's token; locally,
`SCIENCE_AUTH_API_GITHUB_COM_BEARER=$(gh auth token) make scie` does the same if you
ever see a 403 from the build.

Releases so far: `v2026.09.13` (the publish job failed for want of `-R`, so it was
published by hand from the run's artifacts), `v2026.09.13.1` (the fix, published by the
workflow), `v2026.09.13.2` (enik), `v2026.09.13.3` (cyclops), `v2026.09.13.4` (convey
and athena; the tag's run failed on the API rate limit above, so there is no release
for it), `v2026.09.13.5` (the same code with the pin and the token), `v2026.09.13.6`
and `.7`, `v2026.09.14` (the owl's dance; the Linux x86_64 job hung in `make scie
smoke-scie` for a quarter of an hour while the other three runners finished, the run was
cancelled, and there is no release for it) and `v2026.09.14.1` (the same code plus
althea, published by the workflow).

## If CI cannot publish

Build on the machines you have and publish by hand:

```
gh auth login
make dist VERSION=2026.09.13
cd dist && sha256sum * > SHA256SUMS
gh release create v2026.09.13 --title v2026.09.13 --generate-notes *
```

`gh release upload v2026.09.13 <file>` adds an artifact built elsewhere to an existing
release; regenerate and re-upload `SHA256SUMS` (`--clobber`) afterwards.

## Cross-building

Only if a native runner is unavailable (the Intel Mac label is the likely casualty). On
a machine of the same OS, replace `--python $(PYTHON) --scie-platform current` in the
`scie` recipe with a wheel-only target:

```
--platform macosx_10_13_x86_64-cp-313-cp313 --scie-platform macos-x86_64
--platform manylinux_2_28_aarch64-cp-313-cp313 --scie-platform linux-aarch64
```

The result cannot be smoke-tested on the build host; skip `smoke-scie` for that job and
test the file on a real machine before tagging.

## Caches on a user's machine

- `~/.cache/nce` (macOS `~/Library/Caches/nce`): the scie's unpacked CPython, about
  120 MB per release, never pruned. `SCIE_BASE=/elsewhere` relocates it.
- `~/.cache/pex`: the venv the scie builds on first run, and the `.pex`'s own unpacked
  state. `PEX_ROOT` relocates it.
- Deleting either is always safe; the next run rebuilds it in a few seconds.
- `~/.cache/deadtui` is the program's own state and is unaffected by any of this.

Escape hatches if a built binary misbehaves on some terminal: `TERMINFO_DIRS=/path`
(the build's ncurses is static; `poseidon doctor` shows what it found), or use the `.pex`
with the system Python.
