#!/usr/bin/env python3
"""restore-playlist.py - reload a saved mpv playlist into the running deadtui mpv.

  scripts/restore-playlist.py dead/playlist-2026-09-13.json          # from where it was saved
  scripts/restore-playlist.py dead/playlist-2026-09-13.json --from 0  # from the top

The file is what `snapshot` writes: {"pos": n, "time": secs, "files": [...]}. Talks to
the TUI's mpv over $XDG_RUNTIME_DIR/deadtui-mpv.sock (start the TUI first, or it adopts
the mpv this leaves behind). To take a snapshot of what is playing now:

  scripts/restore-playlist.py --snapshot dead/playlist-$(date +%F).json
"""
import json, os, socket, sys, time

SOCK = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or os.path.expanduser("~/.cache/deadtui"), "deadtui-mpv.sock")


def main():
    args = sys.argv[1:]
    s = socket.socket(socket.AF_UNIX)
    try:
        s.connect(SOCK)
    except OSError:
        if args and args[0] == "--snapshot":
            sys.exit("no player running on " + SOCK)
        # no TUI and no player: start the same mpv the TUI starts, detached, so the
        # TUI adopts it later
        import subprocess
        ua = "gdarchive.py/1.0 (+https://github.com/; home audio library tool)"
        subprocess.Popen(["mpv", "--no-video", "--no-terminal", "--idle=yes", "--force-window=no", "--audio-display=no",
                          "--gapless-audio=yes", "--prefetch-playlist=yes", "--cache=yes", "--demuxer-max-bytes=64MiB",
                          "--user-agent=" + ua, "--input-ipc-server=" + SOCK], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        for _ in range(100):
            if os.path.exists(SOCK):
                break
            time.sleep(0.05)
        time.sleep(0.2)
        s = socket.socket(socket.AF_UNIX)
        s.connect(SOCK)
        print("started a player (the TUI will adopt it)")
    f = s.makefile("rw")

    def q(*cmd):
        f.write(json.dumps({"command": list(cmd)}) + "\n")
        f.flush()
        while True:
            r = json.loads(f.readline())
            if "event" not in r:
                return r
    if args and args[0] == "--snapshot":
        pl = q("get_property", "playlist")["data"]
        snap = {"saved": time.strftime("%Y-%m-%d %H:%M"), "pos": q("get_property", "playlist-pos")["data"],
                "time": q("get_property", "time-pos")["data"], "files": [e["filename"] for e in pl]}
        json.dump(snap, open(args[1], "w"), indent=1)
        print(f"saved {len(pl)} tracks, at {snap['pos']}, to {args[1]}")
        return
    snap = json.load(open(args[0]))
    start = int(args[args.index("--from") + 1]) if "--from" in args else snap["pos"]
    files = snap["files"]
    q("loadfile", files[start], "replace")
    for x in files[start + 1:]:
        q("loadfile", x, "append")
    if start == snap["pos"] and snap.get("time"):
        time.sleep(1)
        q("seek", snap["time"], "absolute")
    print(f"loaded {len(files) - start} tracks from #{start}: {os.path.basename(files[start])}")


if __name__ == "__main__":
    main()
