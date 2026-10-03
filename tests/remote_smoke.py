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

        master, relay = pid_in(host.ctl), pid_in(host.ctl + ".fwd")
        os.kill(master, signal.SIGKILL)
        os.kill(relay, signal.SIGKILL)
        time.sleep(0.3)
        check(mpv.get("playlist-count") is None and mpv.sock is None, "a dropped link is noticed")
        check(mpv.reconnect() and mpv.get("playlist-count") == 0, "reconnect: new master, forward, adopted")
        check(alive(pid_in(host.ctl)) and pid_in(host.ctl) != master, "reconnect: a new master")

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
