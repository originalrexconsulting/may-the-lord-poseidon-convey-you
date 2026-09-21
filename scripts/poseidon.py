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

This file is stdlib only and imports nothing from its siblings at module level: they
import it (for user_agent, library_dir), so that would be a cycle.
"""
import functools
import os
import shutil
import subprocess
import sys
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


def doctor():
    """One "key: value" line each; always exits 0. CI greps the lines it needs."""
    lib = library_dir()
    sock_dir = os.environ.get("XDG_RUNTIME_DIR") or CACHE
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
        ("library", f"{lib} ({'exists' if os.path.isdir(lib) else 'created on first fetch'})"),
        ("cache", CACHE),
        ("socket", os.path.join(sock_dir, "deadtui-mpv.sock")),
        ("TERM", os.environ.get("TERM", "")),
        ("TERMINFO_DIRS", os.environ.get("TERMINFO_DIRS", "")),
        ("terminfo", _terminfo_status()),
        ("re-exec", str(self_command(["gdarchive", "fetch", "<id>"]))),
    ]
    for k, v in lines:
        print(f"{k}: {v}")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
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
