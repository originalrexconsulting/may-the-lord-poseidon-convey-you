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
import re
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
    """`pactl list cards` -> [{index, name, description, profiles, active, pinned}]. One tab is a
    key on the card, two is a line inside the block the last one-tab key opened."""
    cards, card, block = [], None, None
    for line in text.splitlines():
        key = line.strip()
        if line.startswith("Card #"):
            card = {"index": key[len("Card #"):], "name": "", "description": "",
                    "profiles": [], "active": "", "pinned": ""}
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
        elif block == "Properties:" and key.startswith("device.profile = "):
            card["pinned"] = key.partition("=")[2].strip().strip('"')   # a monitor.alsa.rules pin
        elif block == "Profiles:" and ": " in key:
            name, _, rest = key.partition(": ")    # names like output:analog-stereo hold a colon
            card["profiles"].append((name.strip(), rest))
    return cards


def _parse_sinks(text):
    """`pactl list sinks` -> [{name, device}], device being the `device.id` property, which
    pipewire-pulse sets to the owning card's index."""
    sinks, sink = [], None
    for line in text.splitlines():
        key = line.strip()
        if line.startswith("Sink #"):
            sink = {"name": "", "device": ""}
            sinks.append(sink)
        elif sink is None:
            continue
        elif key.startswith("Name:") and not line.startswith("\t\t"):
            sink["name"] = key.partition(":")[2].strip()
        elif key.startswith("device.id = "):
            sink["device"] = key.partition("=")[2].strip().strip('"')
    return sinks


def _card_has_sink(card, sinks):
    """By device.id, else by name: `alsa_card.X` owns `alsa_output.X.<profile device>`."""
    stem = card["name"].partition(".")[2]
    return any(s["device"] == card["index"] or
               (stem and s["name"].partition(".")[2].startswith(stem + "."))
               for s in sinks)


def _sink_count(card, profile):
    """How many sinks the named profile promises, per `pactl list cards`; 0 if unknown."""
    for key, rest in card["profiles"]:
        if key == profile:
            m = re.search(r"sinks: (\d+)", rest)
            return int(m.group(1)) if m else 0
    return 0


def _audio_check():
    """Two ways a card is plugged in and enumerated yet gives mpv nothing, so it silently
    lands on the fallback device -- connected, and no sound. Parked at profile `off`
    (the Rotel, 2026-09-29), or on an output profile whose sink node never got built
    (2026-10-01, WirePlumber on a hot-plug: "Object activation aborted"); the profile
    reads fine there, so only the sink list shows it. Either one hits the Rotel about one
    power-on in eight (2026-10-03). Returns (cards, faults, sinks_known) or a "(no check)"
    string; a fault is (card, "off", profile to set) or (card, "nosink", active profile).
    A switched-off amp is gone from USB, so it is no card and no fault."""
    if not shutil.which("pactl"):
        return "pactl not found (no check)"
    try:
        r = subprocess.run(["pactl", "list", "cards"], capture_output=True, text=True, timeout=3)
        s = subprocess.run(["pactl", "list", "sinks"], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return "pactl failed (no check)"
    if r.returncode != 0:
        return "no pipewire/pulse server (no check)"
    cards = _parse_cards(r.stdout)
    sinks = _parse_sinks(s.stdout) if s.returncode == 0 else None
    faults = []
    for c in cards:
        if c["active"] == "off":
            p = (c["pinned"] if c["pinned"] != "off" and _sink_count(c, c["pinned"])
                 else _best_output_profile(c["profiles"]))
            if p:                                   # off with no way out is not actionable
                faults.append((c, "off", p))
        elif sinks is not None and _sink_count(c, c["active"]) and not _card_has_sink(c, sinks):
            faults.append((c, "nosink", c["active"]))
    return cards, faults, sinks is not None


def _fault_text(card, kind, profile):
    label = card["description"] or card["name"]
    if kind == "off":
        return f"{label} is OFF, no sink"
    return f"{label} is on {profile} but has no sink (node never built)"


def _quiet(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, timeout=15).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _fix_audio(faults):
    """Apply the remedy; returns what was done, in words. A card at `off` gets its profile
    set: the card's own pin (`device.profile`, the Rotel's pro-audio) when it has one,
    else the best by priority. A restart would not do, since WirePlumber saves a profile
    choice and puts a remembered `off` straight back (2026-10-03). A missing node wants
    WirePlumber restarted: after a failed build its device bookkeeping can be stale
    (alsa.lua threw on the unplug, 2026-10-02), so toggling the profile is only the
    fallback for a session without the user service."""
    done = []
    for c, kind, p in faults:
        if kind == "off":
            ok = _quiet(["pactl", "set-card-profile", c["name"], p])
            done.append(f"set profile {p}" + ("" if ok else " (failed)"))
    nosink = [(c, p) for c, kind, p in faults if kind == "nosink"]
    if nosink and shutil.which("systemctl") and _quiet(["systemctl", "--user", "is-active", "--quiet", "wireplumber"]):
        ok = _quiet(["systemctl", "--user", "restart", "wireplumber"])
        done.append("restarted wireplumber" + ("" if ok else " (failed)"))
    elif nosink:
        for c, p in nosink:
            ok = (_quiet(["pactl", "set-card-profile", c["name"], "off"]) and
                  _quiet(["pactl", "set-card-profile", c["name"], p]))
            done.append(f"toggled profile {p}" + ("" if ok else " (failed)"))
    return done


def _audio_status():
    """Check, and on a fault fix it and check again: doctor is where the no-sound case
    gets looked at, so it repairs what it finds rather than printing the command."""
    got = _audio_check()
    if isinstance(got, str):
        return got
    cards, faults, sinks_known = got
    if not faults:
        if not sinks_known:
            return f"{len(cards)} card(s), none parked at off (sink list unavailable)"
        return f"{len(cards)} card(s), every output profile has its sink"
    was = "; ".join(_fault_text(*f) for f in faults)
    done = ", ".join(_fix_audio(faults))
    for _ in range(20):                             # WirePlumber takes a second or two to rebuild
        time.sleep(0.5)
        got = _audio_check()
        if isinstance(got, str) or not got[1]:
            break
    if isinstance(got, str):
        return f"{was} -- {done}; recheck failed: {got}"
    if not got[1]:
        return f"{was} -- fixed ({done})"
    left = "; ".join(_fault_text(*f) for f in got[1])
    hint = ("unplug and replug it" if "restarted wireplumber" in done
            else "try systemctl --user restart wireplumber")
    return f"{was} -- tried: {done}; still: {left}; {hint}"


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
        ("audio cards", _audio_status()),
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
