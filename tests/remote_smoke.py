#!/usr/bin/env python3
"""--host mode against tests/fake-ssh: the "box" is this machine, in a throwaway HOME.

Never touches a real ~/.cache/deadtui or a running mpv: HOME is a fresh temp dir, XDG_RUNTIME_DIR
is unset (so both sockets land under that HOME), and the mpv started "on the box" reads
$HOME/.config/mpv/mpv.conf, which says ao=null. The temp dir is under /tmp on purpose: a unix
socket path must stay under 108 bytes.
"""
import importlib.util
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
POSEIDON = os.path.join(SCRIPTS, "poseidon.py")
failed = []


def check(ok, what, detail=""):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failed.append(what)
        if detail:
            print("     " + detail.strip().replace("\n", "\n     "))


def pid_in(path):
    try:
        with open(path) as f:
            return int(f.read().strip() or 0)
    except (OSError, ValueError):
        return 0


def alive(pid):
    try:
        os.kill(pid, 0)
        with open(f"/proc/{pid}/stat") as f:
            return pid > 0 and f.read().rsplit(")", 1)[1].split()[0] != "Z"   # a zombie answers kill 0
    except OSError:
        return False


def cli(*args, timeout=60):
    return subprocess.run([sys.executable, POSEIDON, *args], capture_output=True, text=True, timeout=timeout)


def main():
    if not shutil.which("mpv"):
        sys.exit("remote smoke: mpv is needed")
    sb = tempfile.mkdtemp(prefix="deadtui-remote.")
    os.makedirs(os.path.join(sb, "bin"))
    os.symlink(os.path.join(HERE, "fake-ssh"), os.path.join(sb, "bin", "ssh"))   # first on PATH: the stand-in is `ssh`
    os.environ.update(HOME=sb, PATH=os.path.join(sb, "bin") + os.pathsep + os.environ["PATH"], FAKE_SSH_LOG=os.path.join(sb, "ssh.log"),
                      POSEIDON_HOST="fakehost", POSEIDON_HOST_LIBRARY=os.path.join(sb, "dead"))
    os.environ.pop("XDG_RUNTIME_DIR", None)
    os.makedirs(os.path.join(sb, ".config", "mpv"))
    with open(os.path.join(sb, ".config", "mpv", "mpv.conf"), "w") as f:
        f.write("ao=null\n")
    cache = os.path.join(sb, ".cache", "deadtui")
    os.makedirs(cache)
    remote_sock = os.path.join(cache, "deadtui-mpv.sock")
    sys.path.insert(0, SCRIPTS)
    import poseidon
    spec = importlib.util.spec_from_file_location("tui", os.path.join(SCRIPTS, "May-The_Lord_Poseidon-Convey-You.py"))
    tui = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tui)
    host = poseidon.host()
    mpv = tui.Mpv(host)
    try:
        out = cli("doctor").stdout
        check("host: fakehost (the command line)" in out, "doctor names the box", out)
        check("host ssh: ok" in out, "doctor reaches it", out)
        check("host socket: " + remote_sock + " (absent)" in out, "doctor: no player there yet", out)
        check("host library: " + os.path.join(sb, "dead") + " (missing" in out, "doctor: library missing", out)
        dac = out.split("host DAC: ")[1].splitlines()[0] if "host DAC: " in out else ""
        check(dac == "closed" or dac.isdigit(), f"doctor: the box's DAC rate or closed, not the fraction ({dac!r})", out)
        check("\nhost audio cards: " in out and "(no check)" in out.split("host audio cards: ")[1].splitlines()[0]
              or "host audio cards: " in out and "card(s)" in out.split("host audio cards: ")[1].splitlines()[0],
              "doctor: the audio check ran on the box", out)

        r = cli("play", "status")
        check(r.returncode != 0 and "nothing is playing on fakehost" in r.stderr, "play status with no player", r.stderr)

        mpv.start()
        check(not mpv.adopted, "start: ours, not inherited")
        check(mpv.get("playlist-count") == 0, "start: the player answers through the forward")
        check(host.remote_sock == remote_sock and os.path.exists(remote_sock), "start: the box's socket, under its runtime dir")
        check(mpv.path == os.path.join(cache, "deadtui-mpv@fakehost.sock"), "start: the forwarded socket here")
        with open(os.environ["FAKE_SSH_LOG"]) as f:
            log = f.read()
        check("setsid -f mpv " in log and "--input-ipc-server=" + remote_sock in log, "start: mpv in its own session on the box", log)
        check("ao=null" not in log, "start: the same mpv flags as at home")

        other = tui.Mpv(host)
        other.start()
        check(other.adopted and other.get("playlist-count") == 0, "a second TUI adopts the same player")
        other.sock.close()

        r = cli("play", "status")
        check(r.returncode == 0 and r.stdout.strip() == "idle", "play status beside a running master", r.stdout + r.stderr)
        check(alive(pid_in(host.ctl)), "play status left the TUI's master alone")

        def mpvs():
            r = subprocess.run(["pgrep", "-f", "--", "(^|/)mpv .*--input-ipc-server=" + remote_sock + "$"], capture_output=True, text=True)
            return len(r.stdout.split())

        # the forward is gone but the player is not: start() must not take "nothing answers" at its
        # word, unlink the box's socket and start a second mpv over the one still playing
        relay = pid_in(host.ctl + ".fwd")
        os.kill(relay, signal.SIGKILL)
        time.sleep(0.3)
        check(mpv.get("playlist-count") is None and mpv.sock is None, "a dropped forward is noticed")
        t0 = time.time()
        try:
            mpv.start()
            check(False, "start over a dead forward raised")
        except OSError as e:
            check("running but not answering" in str(e), "start over a dead forward: refuses to start another", str(e))
        check(mpvs() == 1, f"start over a dead forward: still one mpv on the box ({mpvs()})")
        check(host.mpv_alive() is True and host.sock_present(), "the box: its mpv alive, its socket still there")
        check(time.time() - t0 < 10, f"start over a dead forward: gave up in {time.time() - t0:.1f}s")

        master, relay = pid_in(host.ctl), pid_in(host.ctl + ".fwd")
        os.kill(master, signal.SIGKILL)
        if alive(relay):
            os.kill(relay, signal.SIGKILL)
        time.sleep(0.3)
        check(mpv.sock is None and not mpv.adopt(), "a dropped link is noticed")
        check(mpv.reconnect() and mpv.get("playlist-count") == 0, "reconnect: new master, forward, adopted")
        check(alive(pid_in(host.ctl)) and pid_in(host.ctl) != master, "reconnect: a new master")

        try:
            import deadviz
        except ImportError:
            deadviz = None
            print("skip the tap: numpy is missing")
        if deadviz:
            os.environ["FAKE_SSH_PAREC"] = "sine"
            cap = deadviz.Capture(host)
            cap.start()
            deadline = time.time() + 5
            while time.time() < deadline and not cap.samples().any():
                time.sleep(0.1)
            an = deadviz.Analyzer()
            an.update(cap.samples())
            check(cap.error is None and an.rms > 0.1 and an.bass > an.treble, f"the tap: a 60 Hz sine from the box reads as bass (rms {an.rms:.2f})")
            cap.stop()
            os.environ.pop("FAKE_SSH_PAREC")
            with open(os.environ["FAKE_SSH_LOG"]) as f:
                check("-- parec --raw --format=s16le" in f.read(), "the tap: parec on the box, over the master")

        show = os.path.join(sb, "dead", "shows", "1977", "1977-05-08.gd77-05-08.sbd.hicks.4982.sbeok.shnf")
        os.makedirs(show)
        for name in ("gd77-05-08d1t01.flac", "gd77-05-08d1t02.flac", "gd77-05-08d1t03.flac.part"):
            open(os.path.join(show, name), "w").close()
        doc = {"date": "1977-05-08", "identifier": "gd77-05-08.sbd.hicks.4982.sbeok.shnf", "collection": ["GratefulDead"]}
        lib = tui.RemoteLibrary(host)
        check(not lib.has(doc), "library: nothing until the box is asked")
        check(lib.refresh(), "library: the box answers")
        check(lib.root == os.path.join(sb, "dead") and lib.has(doc), "library: the box's own root, the show on it")
        files = lib.files(doc)
        check(sorted(files) == ["gd77-05-08d1t01", "gd77-05-08d1t02"] and files["gd77-05-08d1t01"][".flac"] == os.path.join(show, "gd77-05-08d1t01.flac"),
              "library: the box's paths for the tracks, the .part left out", str(files))
        check(lib.count("shows", 1977) == 1 and lib.count("jgb", 1977) == 0 and lib.night_on_disk("1977-05-08") and not lib.night_on_disk("1977-05-09"),
              "library: counts and nights")
        again = tui.RemoteLibrary(host)
        check(again.has(doc) and again.root == lib.root, "library: the cached index serves a start on a bad link")
        host.library = "~/dead"
        check(lib.refresh() and lib.root == os.path.join(sb, "dead"), "library: ~/ is the box's home")
        argv = tui.remote_fetch_argv(host, "gd77-05-08.sbd.hicks.4982.sbeok.shnf")
        check(argv[:2] == ["bash", "-lc"] and "gdarchive fetch --dest " in argv[2] and "$HOME" in argv[2], "fetch: poseidon on the box, into its library", str(argv))

        hw = os.path.join(sb, "hw_params")
        with open(hw, "w") as f:
            f.write("access: MMAP_INTERLEAVED\nformat: S32_LE\nrate: 44100 (44100/1)\n")
        tui.HW_PARAMS = hw
        rates = [tui.dac_rate(host) for _ in range(5)]
        with open(os.environ["FAKE_SSH_LOG"]) as f:
            cats = f.read().count("-- cat " + hw)
        check(rates == [44100] * 5 and cats == 1, f"DAC rate from the box, read once for five asks ({cats} reads)")

        mpv.stop()
        check(mpv.probe() is None, "stop: nothing answers on the box any more")
        check(not os.path.exists(remote_sock), "stop: the file mpv left behind is gone")
        check(os.path.exists(mpv.path), "stop: the forwarded socket is the master's, left alone")
        master = pid_in(host.ctl)
        host.close()
        check(not alive(master) and not os.path.exists(host.ctl), "close: the master is gone")
    finally:
        if os.path.exists(remote_sock):          # a player left by a failed step
            try:
                s = socket.socket(socket.AF_UNIX)
                s.connect(remote_sock)
                s.sendall(b'{"command":["quit"]}\n')
                s.close()
            except OSError:
                pass
        for p in (host.ctl, host.ctl + ".fwd"):
            if alive(pid_in(p)):
                os.kill(pid_in(p), signal.SIGKILL)
        time.sleep(0.2)
        shutil.rmtree(sb, ignore_errors=True)
    if failed:
        sys.exit(f"remote smoke: {len(failed)} failed")
    print("remote smoke: ok")


if __name__ == "__main__":
    main()
