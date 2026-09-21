#!/usr/bin/env python3
"""radio.py - lossless (FLAC) classical internet radio through Strawberry.

Stock python3 only. Needs ffprobe (probe/now) and a running Strawberry.

Plays a station in a Strawberry playlist tab called "Radio" so the current
playlist (usually a Dead show) is left alone. First run creates the tab;
later runs switch to it and replace its contents with the new station.
PipeWire follows the stream's rate, so a 48 kHz station (CRo D-dur) should
show rate: 48000 in /proc/asound/R20/pcm0p/sub0/hw_params. `now` checks that.

Stations were verified live with ffprobe on 2026-09-11 (the FLAC ones),
2026-09-13 (CRo Vltava FLAC and the first lossy tier) and 2026-09-20 (everything
from KDFC down, ffprobe plus a few seconds of mpv --ao=null each). Dead ones:
Mother Earth Klassik (24/192, station closed), AZPM Classical 90.3 KUAT (HLS
FLAC, connection timed out from Oakland), Radio Klassik Stephansdom (I/O error),
WCRB Boston, WETA Washington, WRTI Philadelphia, WCLV Cleveland (every guessed
mount 404). KDFC's 256 kbps StreamTheWorld mount is gone for good ("Invalid
Mount"); KDFCFMAAC96 is what the station serves now. BBC Radio 3's 320 kbps
feed is UK-only (403 from here); the world feed is 96 kbps HE-AAC.

Examples:

  radio.py list                 # stations
  radio.py probe                # codec / rate / depth / now-playing for each
  radio.py play naim            # start Naim Classical in the Radio tab
  radio.py play random          # any station, the dice decide
  radio.py now                  # what Strawberry plays + the DAC's actual rate
  radio.py back                 # return to the previous playlist tab
"""

import argparse
import glob
import os
import random
import re
import sqlite3
import subprocess
import sys
import time

STATIONS = {
    # key: (name, url, nominal format, notes)
    "naim":  ("Naim Classical", "http://mscp3.live-streams.nl:8250/class-flac.flac",
              "FLAC 16/44.1", "Naim Audio (UK). Curated, mainstream repertoire."),
    "ddur":  ("CRo D-dur", "http://amp.cesnet.cz:8000/cro-d-dur.flac",
              "FLAC 16/48", "Czech Radio classical. 48 kHz: exercises rate switching."),
    "klasu": ("Rondo Classic Klasu", "http://iradio.fi:8000/klasu.flac",
              "FLAC 16/44.1", "Finnish classical, mixed periods."),
    "klasupro": ("Rondo Classic Klasu Pro", "http://iradio.fi:8000/klasupro.flac",
              "FLAC 16/44.1", "Rondo's full-works channel."),
    "sector": ("SECTOR Nota", "http://89.223.45.5:8000/nota-flac",
              "FLAC 24/44.1", "Russian. 24-bit container; depth of source unknown."),
    "vltava": ("CRo Vltava", "http://amp.cesnet.cz:8000/cro3.flac",
              "FLAC 16/48", "Czech Radio culture channel: classical, opera, spoken word between."),
    # ---- lossy, but the best of the big classical broadcasters (verified 2026-09-13)
    "fmusique": ("France Musique", "https://icecast.radiofrance.fr/francemusique-hifi.aac",
              "AAC 192/48", "Radio France's classical network, live concerts most evenings."),
    "fmbaroque": ("France Musique Baroque", "https://icecast.radiofrance.fr/francemusiquebaroque-hifi.aac",
              "AAC 192/48", "All baroque."),
    "fmconcerts": ("France Musique Concerts", "https://icecast.radiofrance.fr/francemusiqueconcertsradiofrance-hifi.aac",
              "AAC 192/48", "Radio France's own orchestras and choir, concert recordings only."),
    "fmopera": ("France Musique Opéra", "https://icecast.radiofrance.fr/francemusiqueopera-hifi.aac",
              "AAC 192/48", "Opera, whole works."),
    "linn": ("Linn Classical", "http://radio.linn.co.uk:8004/autodj",
              "MP3 320/44.1", "Linn Records (Scotland): their own catalogue, so whole movements."),
    "npo4": ("NPO Radio 4", "https://icecast.omroep.nl/radio4-bb-mp3",
              "MP3 192/48", "Dutch public classical."),
    "wqxr": ("WQXR", "https://stream.wqxr.org/wqxr",
              "MP3 128/48", "New York."),
    "wfmt": ("WFMT", "https://wfmt.streamguys1.com/main-mp3",
              "MP3 128/48", "Chicago. Fine presenters."),
    "venice": ("Venice Classic Radio", "https://uk2.streamingpulse.com/ssl/vcr1",
              "MP3 128/44.1", "Italian, all-day chamber and baroque, no talk."),
    # ---- home turf (verified 2026-09-20)
    "kdfc": ("KDFC", "https://playerservices.streamtheworld.com/api/livestream-redirect/KDFCFMAAC96",
              "AAC 96/44.1", "San Francisco, Classical California. 96 kbps is all StreamTheWorld serves now."),
    "kusc": ("KUSC", "https://playerservices.streamtheworld.com/api/livestream-redirect/KUSCAAC96",
              "AAC 96/44.1", "Los Angeles, KDFC's sister station."),
    "king": ("Classical KING FM", "https://classicalking.streamguys1.com/king-fm-aac",
              "AAC 256/44.1", "Seattle. Best-sounding US stream in the list."),
    # ---- lossy, 192 kbps and up (verified 2026-09-20)
    "rai3": ("Rai Radio 3", "https://icestreaming.rai.it/3.mp3",
              "MP3 320/44.1", "Italy's culture channel: classical, opera, spoken word between."),
    "musiq3": ("Musiq3", "https://radios.rtbf.be/musiq3-128.mp3",
              "MP3 320/44.1", "Belgian French-language classical (RTBF); mount says 128, serves 320."),
    "brklassik": ("BR-Klassik", "https://dispatcher.rndfnk.com/br/brklassik/live/mp3/high",
              "MP3 256/48", "Bavarian Radio: its own symphony orchestra and chorus, many concerts."),
    "wdr3": ("WDR 3", "https://wdr-wdr3-live.icecastssl.wdr.de/wdr/wdr3/live/mp3/256/stream.mp3",
              "MP3 256/48", "Cologne. Classical by day, jazz and new music late."),
    "hr2": ("hr2-kultur", "https://dispatcher.rndfnk.com/hr/hr2/live/mp3/high",
              "MP3 256/48", "Frankfurt. hr-Sinfonieorchester concerts."),
    "swrkultur": ("SWR Kultur", "https://liveradio.swr.de/sw282p3/swr2/play.mp3",
              "MP3 256/48", "Stuttgart and Baden-Baden; the old SWR2."),
    "concertzender": ("Concertzender", "https://streams.greenhost.nl:8006/live",
              "MP3 256/48", "Dutch volunteer station, deep catalogue, early music to contemporary."),
    "abc": ("ABC Classic", "https://streaming.abc-cdn.net.au/audio/hls/classicnsw.m3u8",
              "AAC 256/44.1", "Australia (Sydney feed), HLS. Daytime there is night here."),
    "baroque1fm": ("1.FM Otto's Baroque", "http://strm112.1.fm/baroque_mobile_mp3",
              "MP3 256/44.1", "All baroque, no talk; commercial, so the odd advert."),
    "fmclassiqueplus": ("France Musique Classique+", "https://icecast.radiofrance.fr/francemusiqueclassiqueplus-hifi.aac",
              "AAC 192/48", "The core repertoire, no talk."),
    "fmpianozen": ("France Musique Piano Zen", "https://icecast.radiofrance.fr/francemusiquepianozen-hifi.aac",
              "AAC 192/48", "Solo piano, all day."),
    "fmcontemporaine": ("France Musique Contemp.", "https://icecast.radiofrance.fr/francemusiquelacontemporaine-hifi.aac",
              "AAC 192/48", "Twentieth century onward."),
    "nrk": ("NRK Klassisk", "https://lyd.nrk.no/nrk_radio_klassisk_mp3_h",
              "MP3 192/48", "Norwegian public classical, little talk."),
    "oe1": ("Ö1", "https://orf-live.ors-shoutcast.at/oe1-q2a",
              "MP3 192/48", "Austrian public radio culture channel: Vienna's orchestras, spoken word between."),
    "rbb": ("rbbKultur", "https://dispatcher.rndfnk.com/rbb/rbbkultur/live/mp3/high",
              "MP3 192/48", "Berlin."),
    "klassikradio": ("Klassik Radio", "https://stream.klassikradio.de/live/mp3-192/",
              "MP3 192/44.1", "German commercial: light classics and film music, adverts."),
    # ---- lossy, 128 kbps (verified 2026-09-20)
    "bbc3": ("BBC Radio 3", "https://a.files.bbci.co.uk/ms6/live/3441A116-B12E-4D2F-ACA8-C1984642FA4B/audio/simulcast/hls/nonuk/pc_hd_abr_v2/ak/bbc_radio_three.m3u8",
              "AAC 96/48", "The world feed (HLS); the 320 one is UK-only. Proms in summer."),
    "swissclassic": ("Radio Swiss Classic", "http://stream.srg-ssr.ch/m/rsc_de/mp3_128",
              "MP3 128/48", "Swiss, no talk, no news."),
    "radioclassique": ("Radio Classique", "https://radioclassique.ice.infomaniak.ch/radioclassique-high.mp3",
              "MP3 128/48", "Paris, commercial; talk in the mornings."),
    "klara": ("Klara", "https://icecast.vrtcdn.be/klara-high.mp3",
              "MP3 128/44.1", "Belgian Flemish-language classical (VRT)."),
    "klaracontinuo": ("Klara Continuo", "https://icecast.vrtcdn.be/klaracontinuo-high.mp3",
              "MP3 128/44.1", "Klara's no-talk channel."),
    "drp2": ("DR P2", "https://live-icy.dr.dk/A/A04H.mp3",
              "MP3 128/44.1", "Danish public classical."),
    "ndrkultur": ("NDR Kultur", "https://icecast.ndr.de/ndr/ndrkultur/live/mp3/128/stream.mp3",
              "MP3 128/48", "Hamburg."),
    "mdrklassik": ("MDR Klassik", "https://mdr-284350-0.sslcast.mdr.de/mdr/284350/0/mp3/high/stream.mp3",
              "MP3 128/48", "Leipzig: Gewandhaus and the MDR orchestra, little talk."),
    "rneclasica": ("Radio Clásica", "https://dispatcher.rndfnk.com/crtve/rnerc/main/mp3/high",
              "MP3 128/48", "Spanish public classical (RNE)."),
    "antena2": ("Antena 2", "https://radiocast.rtp.pt/antena280a.mp3",
              "MP3 128/44.1", "Portuguese public classical (RTP)."),
    "espace2": ("RTS Espace 2", "https://stream.srg-ssr.ch/m/espace-2/mp3_128",
              "MP3 128/48", "Swiss French-language culture channel."),
    "classicfm": ("Classic FM", "https://media-ssl.musicradio.com/ClassicFMMP3",
              "MP3 128/44.1", "UK commercial: popular classics, adverts."),
    "mpr": ("Classical MPR", "https://cms.stream.publicradio.org/cms.mp3",
              "MP3 128/44.1", "Minnesota Public Radio; feeds Classical 24 overnight."),
    "choral": ("YourClassical Choral", "https://choral.stream.publicradio.org/choral.mp3",
              "MP3 128/44.1", "MPR's all-choral channel."),
    "wcpe": ("WCPE", "https://audio-mp3.ibiblio.org/wcpe.mp3",
              "MP3 128/44.1", "The Classical Station, North Carolina; listener-supported, whole works."),
    "allclassical": ("All Classical Portland", "https://allclassical.streamguys1.com/ac128kmp3",
              "MP3 128/48", "Oregon."),
    "kbaq": ("KBAQ", "https://kbaq.streamguys1.com/kbaq_mp3_128",
              "MP3 128/44.1", "Phoenix."),
    "operavore": ("WQXR Operavore", "https://stream.wqxr.org/operavore",
              "MP3 128/48", "WQXR's all-opera stream."),
}
PLAYLIST = "Radio"
HW_PARAMS = "/proc/asound/R20/pcm0p/sub0/hw_params"
DB = os.path.expanduser("~/.local/share/strawberry/strawberry/strawberry.db")


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def station(key):
    k = key.lower()
    if k == "random":
        return random.choice(list(STATIONS.values()))
    if k in STATIONS:
        return STATIONS[k]
    hits = [v for kk, v in STATIONS.items() if k in kk or k in v[0].lower()]
    if len(hits) == 1:
        return hits[0]
    die(f"unknown station {key!r}; try: {' '.join(STATIONS)}")


def ffprobe(url, timeout=25):
    cmd = ["ffprobe", "-v", "error", "-of", "default=nw=1",
           "-show_entries", "stream=codec_name,sample_rate,bits_per_raw_sample,channels",
           "-show_entries", "format_tags=icy-name,StreamTitle", url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    if r.returncode:
        return None, (r.stderr.strip().splitlines() or ["failed"])[-1]
    kv = dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)
    return kv, None


def fmt_probe(kv):
    depth = kv.get("bits_per_raw_sample", "?")
    rate = kv.get("sample_rate", "?")
    try:
        rate = f"{int(rate)/1000:g}"
    except ValueError:
        pass
    s = f"{kv.get('codec_name','?')} {depth}/{rate}"
    if kv.get("TAG:StreamTitle"):
        s += f"  now: {kv['TAG:StreamTitle']}"
    return s


def strawberry(*args):
    r = subprocess.run(["strawberry", *args], capture_output=True, text=True)
    if r.returncode:
        die(f"strawberry {' '.join(args)}: {r.stderr.strip()}")


def strawberry_running():
    return subprocess.run(["pgrep", "-x", "strawberry"], capture_output=True).returncode == 0


def playlist_exists(name):
    if not os.path.exists(DB):
        return False
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        return c.execute("select 1 from playlists where name=?", (name,)).fetchone() is not None
    finally:
        c.close()


def mpris(prop):
    r = subprocess.run(["busctl", "--user", "get-property", "org.mpris.MediaPlayer2.strawberry",
                        "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player", prop],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def now_playing():
    meta = mpris("Metadata")
    out = {}
    for key in ("xesam:title", "xesam:artist", "xesam:album", "xesam:url", "xesam:comment"):
        m = re.search(r'"%s" (?:s|as \d+) "([^"]*)"' % re.escape(key), meta)
        if m:
            out[key.split(":")[1]] = m.group(1)
    st = mpris("PlaybackStatus")
    m = re.search(r'"([^"]*)"', st)
    out["status"] = m.group(1) if m else "unknown"
    return out


def hw_params():
    try:
        with open(HW_PARAMS) as f:
            txt = f.read()
    except OSError:
        return None
    if txt.strip() == "closed":
        return {"state": "closed"}
    d = dict(l.split(": ", 1) for l in txt.splitlines() if ": " in l)
    return {"format": d.get("format"), "rate": d.get("rate", "").split()[0]}


# --------------------------------------------------------------------------- commands
def cmd_list(_):
    for k, (name, url, fmt, notes) in STATIONS.items():
        print(f"{k:9} {name:24} {fmt:13} {notes}")
        print(f"{'':9} {url}")


def cmd_probe(args):
    keys = [args.station] if args.station else list(STATIONS)
    for k in keys:
        name, url, fmt, _ = station(k)
        kv, err = ffprobe(url)
        print(f"{name:24} {'DOWN: ' + err if err else fmt_probe(kv)}")


def cmd_now(_):
    np = now_playing()
    print(f"strawberry: {np.get('status')}  {np.get('artist','')} - {np.get('title','')}")
    if np.get("album"):
        print(f"            {np['album']}")
    if np.get("url"):
        print(f"            {np['url']}")
    hw = hw_params()
    if hw is None:
        print("dac:        R20 not present")
    elif hw.get("state") == "closed":
        print("dac:        idle (pcm closed)")
    else:
        print(f"dac:        {hw['format']} @ {hw['rate']} Hz")


def cmd_play(args):
    name, url, fmt, _ = station(args.station)
    if not strawberry_running():
        die("Strawberry is not running; start it first so playback goes to the existing instance.")
    kv, err = ffprobe(url)
    if err:
        die(f"{name} is not answering ({err}); pick another station.")
    print(f"{name}: {fmt_probe(kv)}")
    if playlist_exists(PLAYLIST):
        strawberry("--play-playlist", PLAYLIST)   # make Radio the current tab
        time.sleep(1)
        strawberry("--load", url)                 # replace its contents, plays
    else:
        strawberry("--create", PLAYLIST, url)     # new tab with the station
        time.sleep(1)
        strawberry("--play-playlist", PLAYLIST)
    if args.no_verify:
        return
    time.sleep(args.settle)
    np = now_playing()
    hw = hw_params()
    ok = np.get("status") == "Playing" and np.get("url", "").startswith(url.split("?")[0])
    print(f"strawberry: {np.get('status')}  {np.get('title','')}")
    if hw and hw.get("rate"):
        want = kv.get("sample_rate")
        match = "matches stream" if hw["rate"] == want else f"MISMATCH, stream is {want}"
        print(f"dac:        {hw['format']} @ {hw['rate']} Hz ({match})")
        ok = ok and hw["rate"] == want
    else:
        print("dac:        pcm not open yet")
        ok = False
    if not ok:
        print("not confirmed; run `radio.py now` in a few seconds", file=sys.stderr)
        sys.exit(2)


def cmd_back(_):
    """Go back to the first non-Radio playlist and start it."""
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = c.execute("select name from playlists where name<>? order by ui_order", (PLAYLIST,)).fetchall()
    c.close()
    if not rows:
        die("no other playlist")
    strawberry("--play-playlist", rows[0][0])
    print(f"switched to playlist {rows[0][0]!r}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="show stations").set_defaults(fn=cmd_list)
    p = sub.add_parser("probe", help="ffprobe stations")
    p.add_argument("station", nargs="?")
    p.set_defaults(fn=cmd_probe)
    p = sub.add_parser("play", help="play a station in the Radio tab")
    p.add_argument("station")
    p.add_argument("--settle", type=float, default=6, help="seconds before verifying (default 6)")
    p.add_argument("--no-verify", action="store_true")
    p.set_defaults(fn=cmd_play)
    sub.add_parser("now", help="what is playing and the DAC's actual rate").set_defaults(fn=cmd_now)
    sub.add_parser("back", help="return to the previous playlist tab").set_defaults(fn=cmd_back)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
