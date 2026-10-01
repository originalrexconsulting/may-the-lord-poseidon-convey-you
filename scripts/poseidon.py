#!/usr/bin/env python3
"""poseidon - one door to every tool. Bare `poseidon` is the TUI; `poseidon <tool> ...` runs a tool.

Tools: gdarchive, deadviz, radio, restore-playlist, tui. Also: play, remote, doctor, --version.
A symlink named after a tool (gdarchive, deadtui, ...) runs that tool directly.

  poseidon                                  # the TUI
  poseidon gdarchive search --song "Jack Straw" --year 1977
  poseidon gdarchive fetch <identifier>
  poseidon radio list
  poseidon play 1977-05-08 --song "Morning Dew"   # play without the TUI (also random, an identifier,
  poseidon play random | stop | pause | status    # radio <station|random>); the next TUI adopts the player
  poseidon remote                           # the phone remote on the LAN, for a player started without the TUI
  poseidon doctor                           # what this build is, what it found
  POSEIDON_LIBRARY=/path/to/dead poseidon   # where shows are kept (default: dead/ beside
                                            # scripts/ in a checkout, else ~/Music/dead)
  poseidon --host tiro                      # the player is on another box: mpv (and the light show's
                                            # parec) run there over ssh, the TUI and the show here.
                                            # Works with every verb; remembered, --no-host forgets.
                                            # --host-library and --host-fetch say where its shows
                                            # are and how to run poseidon there (fetches).

This file is stdlib only and imports nothing from its siblings at module level: they
import it (for user_agent, library_dir), so that would be a cycle.
"""
import functools
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import types

HERE = os.path.dirname(os.path.realpath(__file__))   # realpath: a symlink elsewhere still finds the siblings
REPO_URL = "https://github.com/originalrexconsulting/may-the-lord-poseidon-convey-you"
TUI = "May-The_Lord_Poseidon-Convey-You.py"
TOOLS = {"tui": TUI, "deadtui": TUI, "may-the_lord_poseidon-convey-you": TUI,
         "gdarchive": "gdarchive.py", "deadviz": "deadviz.py", "radio": "radio.py",
         "restore-playlist": "restore-playlist.py"}
SUBCOMMANDS = ("gdarchive", "deadviz", "radio", "restore-playlist", "tui")
TUI_VERBS = ("play", "remote")   # poseidon play ..., poseidon remote: the TUI's own command line
# python-build-standalone links ncurses statically and may not know the host's terminfo
# location; these are the usual ones (Debian's /lib/terminfo, Homebrew's, ...).
TERMINFO_DIRS = ("/usr/share/terminfo", "/lib/terminfo", "/etc/terminfo", "/usr/lib/terminfo",
                 "/usr/local/share/terminfo", "/opt/homebrew/share/terminfo")
CACHE = os.path.expanduser("~/.cache/deadtui")


@functools.lru_cache(maxsize=None)
def version():
    """The release version: build/src/_version.py in a built artifact, git describe in a
    checkout, else "dev". Cached: gdarchive calls it at import time for its User-Agent."""
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
        except (OSError, subprocess.SubprocessError):
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


# --------------------------------------------------------------------------- the player on another box

MPV_FLAGS = ["--no-video", "--no-terminal", "--idle=yes", "--force-window=no", "--audio-display=no",
             "--gapless-audio=yes", "--prefetch-playlist=yes", "--cache=yes", "--demuxer-max-bytes=64MiB"]
HOST_KEYS = (("host", "POSEIDON_HOST"), ("host_library", "POSEIDON_HOST_LIBRARY"), ("host_fetch", "POSEIDON_HOST_FETCH"))
HOST_FLAGS = {"--host": "POSEIDON_HOST", "--host-library": "POSEIDON_HOST_LIBRARY", "--host-fetch": "POSEIDON_HOST_FETCH"}


def mpv_argv(sock):
    """The player every tool starts: idle, no window, answering JSON IPC on `sock`."""
    return ["mpv", *MPV_FLAGS, "--user-agent=" + user_agent(), "--input-ipc-server=" + sock]


def pop_host_flags(argv):
    """Take --host NAME, --host-library PATH, --host-fetch CMD and --no-host out of argv and into
    the environment (POSEIDON_HOST, ...), so every tool reads the one place. Returns the rest."""
    out, it = [], iter(argv)
    for a in it:
        flag, eq, val = a.partition("=")
        if flag in HOST_FLAGS:
            os.environ[HOST_FLAGS[flag]] = val if eq else next(it, "")
        elif a == "--no-host":
            os.environ["POSEIDON_HOST"] = ""
        else:
            out.append(a)
    return out


def host_settings():
    """{host, host_library, host_fetch}: the environment (the command line, via pop_host_flags) over
    state.json, so a bare `poseidon` keeps driving the box named last time. POSEIDON_HOST set but
    empty (--no-host) means this machine."""
    try:
        with open(os.path.join(CACHE, "state.json")) as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}
    return {key: os.environ[env] if env in os.environ else state.get(key) for key, env in HOST_KEYS}


@functools.lru_cache(maxsize=None)
def host():
    """The Host named by --host / POSEIDON_HOST / state.json, or None: the player is on this machine."""
    s = host_settings()
    return Host(s["host"], s["host_library"], s["host_fetch"]) if s["host"] else None


class Host:
    """Another box's player, reached over one ssh master (key auth; nothing to install there).

    mpv keeps its socket on the box (<its XDG_RUNTIME_DIR>/deadtui-mpv.sock, the same name the
    box's own TUI uses, so either side adopts the same player) and ssh forwards it to local_sock:
    the JSON IPC is byte-identical through the forward. parec runs there too, its raw stream read
    here by the light show (deadviz), so the FFT and the drawing cost this machine, not the box.
    The master is a -N child of this process and dies with it; mpv on the box plays on.
    """
    MASTER = ["-o", "ConnectTimeout=5", "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=3",
              "-o", "ControlMaster=yes", "-o", "ControlPersist=no", "-o", "StreamLocalBindUnlink=yes",
              "-o", "ExitOnForwardFailure=yes", "-N"]

    def __init__(self, name, library=None, fetch_cmd=None):
        self.name = name
        self.library = library or "~/Music/dead"     # where the box keeps its shows (a built artifact's default)
        self.fetch_cmd = fetch_cmd or "poseidon"      # how to run poseidon there, on a login shell's PATH
        run = os.environ.get("XDG_RUNTIME_DIR") or CACHE
        self.ctl = os.path.join(run, f"deadtui-ssh-{name}")
        self.local_sock = os.path.join(run, f"deadtui-mpv@{name}.sock")
        self.remote_run = None        # the box's XDG_RUNTIME_DIR, asked once per master
        self.remote_sock = None
        self.proc = None
        self.reads = {}               # path -> (when, text), for read()

    def ssh(self, *args):
        return ["ssh", "-o", "BatchMode=yes", "-o", "ControlPath=" + self.ctl, *args]

    def exec_prefix(self):
        """argv that runs a command on the box through the master (straight to it if the master is gone)."""
        return self.ssh("-o", "ControlMaster=no", "-o", "ConnectTimeout=5", self.name, "--")

    def quote(self, path):
        """path, quoted for the box's shell; a leading ~/ is the box's home, not this one's."""
        return '"$HOME"/' + shlex.quote(path[2:]) if path.startswith("~/") else shlex.quote(path)

    def alive(self):
        if self.proc and self.proc.poll() is not None:
            return False              # our master exited (the link went); reaped here
        if not os.path.exists(self.ctl):
            return False
        try:
            return subprocess.run(self.ssh("-O", "check", self.name), capture_output=True, timeout=5).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def ensure(self):
        """The master up, the box's runtime dir known, its socket forwarded. Idempotent; raises OSError."""
        if not self.alive():
            os.makedirs(os.path.dirname(self.ctl), exist_ok=True)
            if os.path.exists(self.ctl):
                os.unlink(self.ctl)          # left by a master that died
            self.proc = subprocess.Popen(self.ssh(*self.MASTER, self.name), stdin=subprocess.DEVNULL,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            for _ in range(200):
                if os.path.exists(self.ctl):
                    break
                if self.proc.poll() is not None:
                    raise OSError(f"ssh {self.name}: {self.proc.stderr.read().strip() or 'exited'}")
                time.sleep(0.05)
            else:
                self.proc.kill()
                raise OSError(f"ssh {self.name}: no control socket after 10 s")
            self.remote_run = None
        if self.remote_run is None:
            r = self.run('printf %s "${XDG_RUNTIME_DIR:-$HOME/.cache/deadtui}"')
            if r.returncode != 0 or not r.stdout.strip():
                raise OSError(f"ssh {self.name}: {r.stderr.strip() or 'no runtime dir'}")
            self.remote_run = r.stdout.strip()
            self.remote_sock = self.remote_run + "/deadtui-mpv.sock"
            r = subprocess.run(self.ssh("-O", "forward", "-L", f"{self.local_sock}:{self.remote_sock}", self.name),
                               capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                raise OSError(f"ssh {self.name}: forward: {r.stderr.strip()}")
        return self

    def run(self, cmd, timeout=10):
        """A shell command on the box; a CompletedProcess with text output (rc 255: ssh itself failed)."""
        try:
            return subprocess.run(self.exec_prefix() + [cmd], capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(cmd, 255, "", "timed out")

    def popen(self, argv, **kw):
        """A command on the box as a Popen: its stdout is the raw stream (the audio tap, a fetch's log)."""
        return subprocess.Popen(self.exec_prefix() + list(argv), **kw)

    def start_mpv(self):
        """The player, in its own session on the box so it outlives this ssh channel (and this TUI)."""
        r = self.run("setsid -f " + shlex.join(mpv_argv(self.remote_sock)) + " </dev/null >/dev/null 2>&1")
        if r.returncode != 0:
            raise OSError(f"mpv on {self.name}: {r.stderr.strip() or 'did not start'}")

    def sock_present(self):
        return self.run("test -S " + shlex.quote(self.remote_sock)).returncode == 0

    def sock_unlink(self):
        self.run("rm -f " + shlex.quote(self.remote_sock))

    def read(self, path, ttl=10):
        """The text of a file on the box, re-read at most every ttl seconds; None when it is not there."""
        when, text = self.reads.get(path, (0, None))
        if time.time() - when > ttl:
            r = self.run("cat " + shlex.quote(path))
            text = r.stdout if r.returncode == 0 else None
            self.reads[path] = (time.time(), text)
        return text

    def close(self):
        """Take down the master this process started, the forward with it; one another process
        started (the TUI's, while `poseidon play status` runs beside it) is left alone. mpv on the
        box plays on either way."""
        if self.proc:
            try:
                subprocess.run(self.ssh("-O", "exit", self.name), capture_output=True, timeout=5)
                self.proc.wait(2)
            except (OSError, subprocess.SubprocessError):
                self.proc.kill()
            self.proc = None
        self.remote_run = None


def running_as():
    """"scie" (self-contained binary), "pex" (universal .pex) or "checkout"."""
    return "scie" if os.environ.get("SCIE") else "pex" if os.environ.get("PEX") else "checkout"


def self_command(args):
    """argv that runs this program again: the scie, the .pex, or the checkout's poseidon.py.

    scie-jump sets SCIE to the binary's absolute path and pex sets PEX to the .pex path;
    both survive into the Python process. If a parent process that is itself a scie
    exported SCIE, a checkout run would re-exec that scie instead; accepted.
    """
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
    """Run a sibling script as __main__, exactly as `python3 scripts/<filename>` would.

    Not runpy.run_path: that resets sys.argv[0] to the path, and argparse's usage line
    should read `poseidon gdarchive`, not `gdarchive.py`.
    """
    path = os.path.join(HERE, filename)
    sys.argv = [f"poseidon {os.path.splitext(filename)[0]}", *argv]   # argparse prog
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    with open(path, "rb") as f:
        code = compile(f.read(), path, "exec")
    mod = types.ModuleType("__main__")
    mod.__file__ = path
    sys.modules["__main__"] = mod
    exec(code, mod.__dict__)


def _module_version(name):
    try:
        mod = __import__(name)
    except ImportError:
        return "missing"
    return getattr(mod, "__version__", None) or getattr(mod, "version_string", None) or "present"


def _terminfo_status():
    try:
        import curses
        curses.setupterm()
        return f"ok ({curses.tigetnum('colors')} colors)"
    except Exception as e:  # curses.error, or no terminal at all
        return f"FAILED: {e}"


def _best_output_profile(profiles):
    """The highest-priority available profile that would give a card a sink, or None."""
    best, best_priority = None, -1
    for key, rest in profiles:
        if key == "off":
            continue
        m = re.search(r"sinks: (\d+).*priority: (\d+).*available: (\w+)", rest)
        if not m:
            continue
        sinks, priority, available = int(m.group(1)), int(m.group(2)), m.group(3)
        if sinks and available == "yes" and priority > best_priority:
            best, best_priority = key, priority
    return best


def _parse_cards(text):
    """`pactl list cards` -> [{name, description, profiles, active}]. One tab is a key on
    the card, two is a line inside the block the last one-tab key opened."""
    cards, card, block = [], None, None
    for line in text.splitlines():
        key = line.strip()
        if line.startswith("Card #"):
            card = {"name": "", "description": "", "profiles": [], "active": ""}
            cards.append(card)
            block = None
        elif card is None:
            continue
        elif not line.startswith("\t\t"):          # any one-tab key closes the block before it
            block = key if key in ("Profiles:", "Properties:") else None
            if key.startswith("Name:"):
                card["name"] = key.partition(":")[2].strip()
            elif key.startswith("Active Profile:"):
                card["active"] = key.partition(":")[2].strip()
        elif block == "Properties:" and key.startswith("device.description = "):
            card["description"] = key.partition("=")[2].strip().strip('"')
        elif block == "Profiles:" and ":" in key:
            name, _, rest = key.partition(":")
            card["profiles"].append((name.strip(), rest))
    return cards


def _audio_status():
    """A card parked at profile `off` is plugged in and enumerated but has no sink, so
    mpv silently lands on the fallback device instead: connected, and no sound."""
    if not shutil.which("pactl"):
        return "pactl not found (no check)"
    try:
        r = subprocess.run(["pactl", "list", "cards"], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return "pactl failed (no check)"
    if r.returncode != 0:
        return "no pipewire/pulse server (no check)"
    cards = _parse_cards(r.stdout)
    off = [(c, _best_output_profile(c["profiles"])) for c in cards if c["active"] == "off"]
    off = [(c, p) for c, p in off if p]            # off with no way out is not actionable
    if not off:
        return f"{len(cards)} card(s), none parked at off"
    return "; ".join(f"{c['description'] or c['name']} is OFF, no sink -- "
                     f"pactl set-card-profile {c['name']} {p}" for c, p in off)


def _host_status(h):
    """What the TUI will find on the box, in one ssh round trip."""
    lib, fetch = h.quote(h.library), shlex.quote(h.fetch_cmd.split()[0])
    script = ('run="${XDG_RUNTIME_DIR:-$HOME/.cache/deadtui}"; echo "name=$(uname -n)"; echo "run=$run"; '
              'echo "mpv=$(command -v mpv)"; echo "parec=$(command -v parec)"; '
              'test -S "$run/deadtui-mpv.sock" && echo sock=present || echo sock=absent; '
              f'test -d {lib} && echo lib=exists || echo lib=missing; '
              f'echo "fetch=$(bash -lc {shlex.quote("command -v " + fetch)} 2>/dev/null)"; '
              'echo "dac=$(grep -m1 ^rate: /proc/asound/R20/pcm0p/sub0/hw_params 2>/dev/null)"')
    r = h.run(script, timeout=20)
    if r.returncode != 0:
        return [("host ssh", f"FAILED: {r.stderr.strip() or r.returncode}")]
    got = dict(line.split("=", 1) for line in r.stdout.splitlines() if "=" in line)
    found = lambda k: got.get(k) or "not found"   # noqa: E731
    return [
        ("host ssh", f"ok ({got.get('name', '?')})"),
        ("host runtime dir", got.get("run", "?")),
        ("host mpv", found("mpv")),
        ("host parec", found("parec")),
        ("host socket", f"{got.get('run', '?')}/deadtui-mpv.sock ({'present' if got.get('sock') == 'present' else 'absent'})"),
        ("host library", f"{h.library} ({'exists' if got.get('lib') == 'exists' else 'missing: --host-library PATH'})"),
        ("host fetch", f"{h.fetch_cmd} ({got['fetch'] if got.get('fetch') else 'not on its login PATH: --host-fetch CMD'})"),
        ("host DAC", got["dac"].split()[-1] if got.get("dac") else "closed"),
    ]


def doctor():
    """One "key: value" line each; always exits 0. CI greps the lines it needs."""
    lib = library_dir()
    sock_dir = os.environ.get("XDG_RUNTIME_DIR") or CACHE
    h = host()
    lines = [
        ("version", version()),
        ("running as", running_as()),
        ("python", f"{sys.version.split()[0]} ({sys.executable})"),
        ("platform", f"{sys.platform} {os.uname().machine}"),
        ("numpy", _module_version("numpy")),
        ("mutagen", _module_version("mutagen")),
    ]
    for exe in ("mpv", "ffmpeg", "ffprobe", "parec"):
        lines.append((exe, shutil.which(exe) or "not found"))
    lines += [
        ("audio cards", _audio_status()),
        ("library", f"{lib} ({'exists' if os.path.isdir(lib) else 'created on first fetch'})"),
        ("cache", CACHE),
        ("socket", os.path.join(sock_dir, "deadtui-mpv.sock")),
        ("TERM", os.environ.get("TERM", "")),
        ("TERMINFO_DIRS", os.environ.get("TERMINFO_DIRS", "")),
        ("terminfo", _terminfo_status()),
        ("re-exec", str(self_command(["gdarchive", "fetch", "<id>"]))),
    ]
    if h:
        lines.append(("host", f"{h.name} ({'the command line' if 'POSEIDON_HOST' in os.environ else 'remembered in state.json'})"))
        lines += _host_status(h)
    for k, v in lines:
        print(f"{k}: {v}")


def main(argv=None):
    argv = pop_host_flags(sys.argv[1:] if argv is None else argv)
    _terminfo_fallback()
    tool = _tool_from_argv0()
    if tool:
        return run(tool, argv)
    if argv and argv[0] in ("--version", "-V"):
        print(f"poseidon {version()}")
        return
    if argv and argv[0] in ("--help", "-h"):
        print(__doc__)
        return
    if argv and argv[0] == "doctor":
        return doctor()
    if argv and argv[0] in SUBCOMMANDS:
        return run(TOOLS[argv[0]], argv[1:])
    if argv and argv[0] in TUI_VERBS:
        return run(TUI, argv)
    if argv:
        sys.exit(f"poseidon: unknown tool {argv[0]!r}; one of {', '.join(SUBCOMMANDS + TUI_VERBS)}, doctor, --version")
    return run(TUI, [])


if __name__ == "__main__":
    main()
