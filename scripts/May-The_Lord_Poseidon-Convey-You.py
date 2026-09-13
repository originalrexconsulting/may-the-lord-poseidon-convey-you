#!/usr/bin/env python3
"""May-The_Lord_Poseidon-Convey-You.py (formerly deadtui.py) - browse and play the archive.org Grateful Dead collection in a terminal.

Stock python3 (curses) + mpv. No pip installs. Search/metadata code is reused
from gdarchive.py in the same directory. Runs on Linux and macOS (see README:
brew install mpv; numpy for the light show, mutagen for tagging fetched shows;
the DAC rate readout is Linux-only and simply stays blank elsewhere).

Levels:  home  >  years  >  dates in a year  >  sources for a date  >  tracks
The home screen is sectioned: Now (▶ Now playing, 🎲 Random show), The Dead
(the years, Tears, JGB), Memories, Not Dead (classical radio, Firesign, Jokes),
Everything (History). Section headers are skipped by the cursor.
Home rows in detail: `♪ Classical radio` (radio.py's lossless stations);
`Firesign Theatre` and `Jokes` (LPs, one 24-bit FLAC per side, from library vinyl
transfers); `Tears` (the weepers: ↵ on a song runs the song search across every
show); one ✦ row per MEMORIES entry (an evening kept as a set list; a plays it
through); `History` (every track played, newest first, from
~/.cache/deadtui/history.jsonl; ↵ plays it again); `JGB`: Melvin Seals & JGB, the
band Jerry left behind, 1996 on (archive.org collection JGB; Jerry's own Garcia
Band tapes were removed from archive.org at the estate's request). JGB shows
fetched with d land in dead/jgb/<year>/ and play from disk like Dead shows.
`Jokes` starts with CLIPS: moments inside shows played from an offset, such as the
"Penalized for Your Dependence on Batteries (or a Well Deserved Break)" at 7:42 of
Mission in the Rain, Boston 6/12/76.
`🎲 Random show` picks a year and a night in it (rated 4+ when the year has such),
opens it, and plays the best source. `☔ Rain and Snow` plays weather and water
songs (RAIN_SONGS): a random song, a random night's version of it (on-disk shows
first some of the time), four to start, and three more each time the last one begins.
Playback goes through mpv (JSON IPC over a unix socket), which plays through
PipeWire like everything else on the laptop. Shows already fetched into
dead/shows/ are played from the local lossless files instead of the stream.

Keys:
  (Poseidon, trident raised, greets you for SPLASH_SECS at start; any key skips.)
  Up/Down j/k   move            Enter/l   open (or play, on a track)
  Left/h/Bksp   back            p         play this date's best source / this source
  Space         pause           n / b     next / previous track
  Left/Right    (while playing) seek -10 / +10 s      < / >  seek -60 / +60 s
  /             filter list     g         go to YYYY or YYYY-MM-DD (1996 on jumps into JGB)
  f             find a song across all years (one row per show date, best source);
                there: Enter opens the show at that track, p plays from it,
                a plays every version in date order as one playlist
  d             download this show with gdarchive.py (background)
  c             classical radio (the lossless FLAC stations from radio.py);
                also the first entry of the top-level list. i probes a station.
  r             resume the last thing played, at the position it was at
  w             what's playing: the whole current playlist (also the first top-level
                row while something plays); ▶ marks the track, Enter jumps to one
  v             light show (deadviz.py): patterns driven by an FFT of what the
                Rotel is playing. Inside it v steps to the next of 15 modes
                (bars, plasma, scope, rings, waterfall, fire, rain, stars, wave,
                radial, particles, meters, spiral, life, poseidon), V steps back, 1-9/0
                pick the first ten, space/n/b/arrows still control playback,
                Esc (or any other key) returns.
                Also starts by itself after SCREENSAVER_SECS idle while playing.
  s             stop            q         quit; the music keeps playing and the next
                                          start adopts it (see below)
                                Q         quit and stop the music

If an mpv from an earlier run is still on the socket (the TUI died without q: closed
terminal, hangup, crash), it is adopted rather than replaced: its playlist is read
back, shows on disk and archive.org URLs are recognised, and the status line, n/b,
seek and q all work on it as if this instance had started it.

On quit the show, track and position (or the radio station) are saved to
~/.cache/deadtui/state.json; the next start re-opens that view with the
cursor on the track, and r resumes playback from the saved position.
Search-index and metadata responses are cached under ~/.cache/deadtui/ so
re-visiting a year is instant. Delete that directory to refresh.
"""

import concurrent.futures as cf
import curses
import random
import json
import os
import socket
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdarchive as gd  # noqa: E402
import radio  # noqa: E402
try:
    import deadviz  # noqa: E402
except ImportError:  # python3-numpy missing
    deadviz = None

CACHE = os.path.expanduser("~/.cache/deadtui")
STATE = os.path.join(CACHE, "state.json")
HISTORY = os.path.join(CACHE, "history.jsonl")   # one line per track played, newest last
HISTORY_ROWS = 500
CACHE_TTL = 7 * 86400
YEARS = list(range(1965, 1996))
JGB = "jgb"      # sentinel entry at the bottom of the years list
FIRESIGN = "firesign"  # sentinel below JGB: the Firesign Theatre LPs
JOKES = "jokes"        # sentinel: other comedy LPs
TEARS = "tears"        # sentinel: the weepers, each row a song search
MEMORY = "memory"      # sentinel: set lists of evenings worth keeping
HIST = "history"       # sentinel: everything played, newest first
QUEUE = "queue"        # sentinel: the playlist mpv is playing right now
RANDOM = "random"      # sentinel: a random Dead show, best source, straight into play
RAIN = "rain"          # sentinel: Rain and Snow, random weather and water songs, one version after another
RAIN_SONGS = [
    "Cold Rain and Snow", "Looks Like Rain", "Mission in the Rain", "Box of Rain", "Morning Dew",
    "Here Comes Sunshine", "Sunshine Daydream", "Big River", "Row Jimmy", "Ship of Fools", "Lost Sailor",
    "Saint of Circumstance", "Weather Report Suite", "Let It Grow", "Black Muddy River", "Wharf Rat",
    "The Wheel", "Lazy Lightning", "Franklin's Tower", "Mississippi Half-Step", "Wave to the Wind",
    "Ripple", "Estimated Prophet", "Crazy Fingers", "Brokedown Palace",
]
RAIN_BATCH = 4         # versions fetched per roll; more are added as the last one starts
YEARS_GD = ("years", "GratefulDead")   # home row that opens the Dead years
HDR = "hdr"            # (HDR, text): a section header on the home screen, not selectable
# LP menus. archive.org library vinyl transfers: one 24-bit FLAC per side, titled from
# the mp3 cut list. Stream-only items (post-1972 mostly) play cut by cut as mp3.
# Fetched with d they land in dead/lp/<year>/.  (identifier, year, artist, title)
ALBUMS = {
    FIRESIGN: [
        ("lp_waiting-for-the-electrician-or-someone_the-firesign-theatre", 1968, "Firesign Theatre", "Waiting for the Electrician or Someone Like Him"),
        ("lp_how-can-you-be-in-two-places-at-once-wh_the-firesign-theatre", 1969, "Firesign Theatre", "How Can You Be in Two Places at Once When You're Not Anywhere at All"),
        ("lp_dont-crush-that-dwarf-hand-me-the-pliers_the-firesign-theatre", 1970, "Firesign Theatre", "Don't Crush That Dwarf, Hand Me the Pliers"),
        ("lp_dear-friends_the-firesign-theatre", 1972, "Firesign Theatre", "Dear Friends"),
    ],
    JOKES: [
        ("lp_way-out-humor_lord-buckley", 1959, "Lord Buckley", "Way Out Humor"),
        ("lp_lord-buckley-in-concert_lord-buckley", 1964, "Lord Buckley", "In Concert"),
        ("lp_the-best-of-lenny-bruce_lenny-bruce", 1962, "Lenny Bruce", "The Best of Lenny Bruce"),
        ("lp_live-at-the-curran-theater_lenny-bruce", 1971, "Lenny Bruce", "Live at the Curran Theater"),
        ("lp_at-sunset_mort-sahl", 1958, "Mort Sahl", "At Sunset"),
        ("lp_inside-shelley-berman_shelley-berman_0", 1959, "Shelley Berman", "Inside Shelley Berman"),
        ("lp_down-to-earth_jonathan-winters", 1960, "Jonathan Winters", "Down to Earth"),
        ("lp_behind-the-button-down-mind-of-bob-newhart_bob-newhart", 1961, "Bob Newhart", "Behind the Button-Down Mind"),
        ("lp_beyond-the-fringe_beyond-the-fringe", 1962, "Beyond the Fringe", "Beyond the Fringe"),
        ("lp_the-best-of-the-goon-shows-no-2_peter-sellers-harry-secombe-spike-m", 1963, "The Goons", "The Best of the Goon Shows No. 2"),
        ("lp_the-best-of-the-stan-freberg-shows_stan-freberg-daws-butler-june-fo", 1958, "Stan Freberg", "The Best of the Stan Freberg Shows"),
        ("lp_laff-your-head-off_redd-foxx", 1965, "Redd Foxx", "Laff Your Head Off"),
        ("lp_cowboys-colored-people_flip-wilson", 1967, "Flip Wilson", "Cowboys & Colored People"),
        ("lp_abraham-martin-john_moms-mabley", 1969, "Moms Mabley", "Abraham, Martin & John"),
        ("lp_monty-pythons-flying-circus_monty-python", 1970, "Monty Python", "Monty Python's Flying Circus"),
        ("lp_craps-after-hours_richard-pryor", 1971, "Richard Pryor", "Craps (After Hours)"),
    ],
}
COLLECTIONS = {  # archive.org collection -> title and year span
    "GratefulDead": {"title": "Grateful Dead", "years": YEARS},
    "JGB": {"title": "JGB · Melvin Seals & Jerry Garcia Band", "years": list(range(1996, time.gmtime().tm_year + 1))},
}
MENU_TITLES = {FIRESIGN: "Firesign Theatre", JOKES: "Jokes"}
# Clips: a moment inside a show, played from an offset. Listed at the top of Jokes.
CLIPS = [
    {"clip": True, "title": "Penalized for Your Dependence on Batteries (or a Well Deserved Break)",
     "note": "Dead stage banter, Boston Music Hall, at the end of Mission in the Rain",
     "identifier": "gd1976-06-12.fm.sbd.moore.berger.100328.flac16", "date": "1976-06-12", "collection": ["GratefulDead"],
     "kind": "sbd", "song": "Mission in the Rain", "start": 7 * 60 + 42},
]
# Memories: an evening as a set list. Each row: (collection, identifier, date, first song,
# last song or "*" for the rest of the show or None for just that song, note).
# ↵/p plays a row; a plays the whole evening in order, as one gapless playlist.
MEMORIES = {
    "crazyPosiedonEarthShakerMemoryof20260913GenesisDay": [
        ("GratefulDead", "gd1970-02-13.123814.aud.cooper.flac16", "1970-02-13", "China Cat Sunflower", "I Know You Rider",
         "Fillmore East late show, 2nd row centre. The classical radio went quiet and this came up."),
        ("GratefulDead", "gd1976-06-12.fm.sbd.moore.berger.100328.flac16", "1976-06-12", "Mission in the Rain", "*",
         "Boston Music Hall FM soundboard. Mission, eight minutes in: 'hilarious'. Then the rest of the night."),
        ("JGB", "jgb2006-01-13.sbd.flac16", "2006-01-13", "Tears of Rage", None,
         "Melvin Seals & JGB at the Great American Music Hall. The Dead never played it; this is where it lives."),
        ("GratefulDead", "gd1970-02-13.123814.aud.cooper.flac16", "1970-02-13", "Dark Star", "*",
         "Dark Star > Cryptical > Drums > The Other One > Cryptical > Lovelight > And We Bid You Goodnight."),
    ],
}
# Tears: the weepers. ↵ runs the song search (same as f) so every version is a row.
# (song, collection) - Tears of Rage lives only in the Melvin Seals JGB collection.
TEARS_LIST = [
    ("Tears of Rage", "JGB"),
    ("Stella Blue", "GratefulDead"),
    ("Black Peter", "GratefulDead"),
    ("Wharf Rat", "GratefulDead"),
    ("Morning Dew", "GratefulDead"),
    ("Brokedown Palace", "GratefulDead"),
    ("Ripple", "GratefulDead"),
    ("Attics of My Life", "GratefulDead"),
    ("Mission in the Rain", "GratefulDead"),
    ("Comes a Time", "GratefulDead"),
    ("To Lay Me Down", "GratefulDead"),
    ("China Doll", "GratefulDead"),
    ("He's Gone", "GratefulDead"),
    ("Ship of Fools", "GratefulDead"),
    ("Box of Rain", "GratefulDead"),
    ("Sing Me Back Home", "GratefulDead"),
    ("Row Jimmy", "GratefulDead"),
    ("High Time", "GratefulDead"),
    ("It Must Have Been the Roses", "GratefulDead"),
    ("Standing on the Moon", "GratefulDead"),
    ("Black Muddy River", "GratefulDead"),
    ("So Many Roads", "GratefulDead"),
    ("Days Between", "GratefulDead"),
    ("Knockin' on Heaven's Door", "GratefulDead"),
    ("Death Don't Have No Mercy", "GratefulDead"),
    ("And We Bid You Goodnight", "GratefulDead"),
]

PREFER = ["matrix", "sbd", "aud", "other"]
KIND_SHORT = {"matrix": "mtx", "sbd": "sbd", "aud": "aud", "other": "?"}
STREAM_ORDER_OPEN = [".flac", ".mp3", ".ogg", ".shn"]
STREAM_ORDER_RESTRICTED = [".mp3", ".ogg"]
RADIO = "radio"  # sentinel entry at the top of the years list
SPLASH_SECS = 2.0        # the Earth Shaker greets you at start; any key skips, 0 disables. SPLASH_STYLE picks the art.
SPLASH_STYLE = "crowned"   # "crowned" (the keeper), "storm" (rising from the sea), or "random"
SPLASHES = {
    "crowned": r"""
                                       ▲
                                  ╲    ║    ╱
                                   ╲   ║   ╱
                                    ╲  ║  ╱
                                     ╲ ║ ╱
                                      ╲║╱
                ▲ ▲ ▲ ▲ ▲              ║
               ▐█████████▌             ║        ⚡
              ██▀▀▀▀▀▀▀▀▀██            ║
             ██  ▄▄   ▄▄  ██           ║
            ▐█   ██   ██   █▌          ║
            ▐█    ▀   ▀    █▌          ║
             ██     ▄▄    ██           ║
             ▐█▄  ▀▀▀▀▀▀ ▄█▌           ║
           ▄███████████████████▄       ║
        ▄██▀▀   ▐███████▌   ▀▀██▄      ║
      ▄██▀       ▐█████▌       ▀██▄    ║
     ██▀          ▐███▌          ▀██   ║
    ██            ▐███▌            ██  ║
   ▐█             ▐███▌             █▌ ║
   █▌              ▐█▌              ▐█ ║
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
""".strip("\n").splitlines(),
    "storm": r"""
        ⚡                                                   ⚡
                 ⚡                     ▲
                                  ╲    ║    ╱          ⚡
                                   ╲   ║   ╱
                                    ╲  ║  ╱
                                     ╲ ║ ╱
       ⚡                              ╲║╱
                                       ║              ⚡
              ▄▄▄▄▄▄▄▄▄▄▄▄▄            ║
            ▄█▀▀   ▄   ▄   ▀▀█▄        ║
           ██   ▄▄█▀  ▀█▄▄    ██       ║
          ▐█   ▀▀██▄▄▄▄██▀▀    █▌      ║
          ▐█   ▄▄▄      ▄▄▄    █▌      ║
          ▐█  ▐█▓█▌    ▐█▓█▌   █▌      ║
           ██  ▀▀▀  ▄▄  ▀▀▀   ██       ║
           ▐█▄     ▀██▀      ▄█▌       ║
            ▀██▄▄  ▀▀▀▀▀▀  ▄▄██▀       ║
          ▄▄▄██▀███▄▄▄▄▄▄███▀██▄▄▄     ║
        ▄██▀▀     ▀▀▀██▀▀▀     ▀▀██▄   ║
      ▄██▀           ▐█▌           ▀██▄ ║
    ▄██▀             ▐█▌             ▀██║
   ██▀               ▐█▌               ▀█▌
  ▐█        ▲        ▐█▌        ▲       █▌
 ~~██~~~~~~~█~~~~~~~~█▀█~~~~~~~~█~~~~~~~██~~~~~~~~~~
~~~~▀█▄~~~~▀~~~~~~~~~▀~~~~~~~~~▀~~~~~~▄█▀~~~~~~~~~~~~~
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
""".strip("\n").splitlines(),
}
SPLASH_EYES = {"crowned": (10, 11), "storm": ()}   # rows whose inner blocks are the eyes; ▓ is always an eye
SCREENSAVER_SECS = 180   # idle time (while playing) before the light show starts; 0 disables
HW_PARAMS = "/proc/asound/R20/pcm0p/sub0/hw_params"

# Stations beyond radio.py's lossless list go here: key: (name, url, nominal format, notes).
# KDFC is absent on purpose: every StreamTheWorld mount that used to serve it
# (KDFCFMAAC, KDFCFM, *_SC, with and without dist=kdfc) answered
# "430 Invalid Mount" on 2026-09-12 and kdfc.com no longer exposes a stream URL
# in its HTML. Add it back once a working URL is found (browser dev tools,
# Network tab, while the web player runs).
EXTRA_STATIONS = {}


def stations():
    out = []
    for key, (name, url, fmt, notes) in {**radio.STATIONS, **EXTRA_STATIONS}.items():
        out.append({"key": key, "name": name, "url": url, "fmt": fmt, "notes": notes})
    return out


def quality(st):
    """Measured stream quality from mpv: codec, bit depth (lossless only), rate, bitrate."""
    if not st or not st.get("codec"):
        return ""
    p = st.get("params") or {}
    fmt = str(p.get("format") or "")
    depth = ""
    if st["codec"] in ("flac", "alac", "pcm_s16le", "pcm_s24le", "pcm_s32le", "wavpack", "ape", "shorten"):
        depth = {"s16": "16", "s16p": "16", "s32": "24", "s32p": "24", "s24": "24"}.get(fmt, "")
    rate = p.get("samplerate")
    out = st["codec"]
    if rate:
        out += f" {depth + '/' if depth else ''}{rate / 1000:g}k"
    if st.get("bitrate"):
        out += f" {round(st['bitrate'] / 1000)}kbps"
    return out


def dac_rate():
    """What the Rotel is actually clocked at, or None when absent/closed."""
    try:
        with open(HW_PARAMS) as f:
            for line in f:
                if line.startswith("rate:"):
                    return int(line.split()[1])
    except (OSError, ValueError):
        pass
    return None


# --------------------------------------------------------------------------- cache / data


def _cache_path(name):
    os.makedirs(CACHE, exist_ok=True)
    return os.path.join(CACHE, name.replace("/", "_") + ".json")


def cached(name, fn, ttl=CACHE_TTL):
    p = _cache_path(name)
    try:
        if time.time() - os.path.getmtime(p) < ttl:
            with open(p) as f:
                return json.load(f)
    except (OSError, ValueError):
        pass
    data = fn()
    if data is None:
        return None
    with open(p + ".tmp", "w") as f:
        json.dump(data, f)
    os.replace(p + ".tmp", p)
    return data


def year_docs(year, collection=gd.DEFAULT_COLLECTION):
    def fetch():
        args = SimpleNamespace(collection=collection, year=year, date=None, song=None, min_rating=None,
                               min_reviews=None, source="any", downloadable=False, query=None,
                               sort="date asc", limit=5000)
        return gd.search(args)[1]
    tag = "" if collection == gd.DEFAULT_COLLECTION else f"{collection}-"
    return cached(f"year-{tag}{year}", fetch)


def doc_collection(doc):
    for c in doc.get("collection") or []:
        if c in COLLECTIONS:
            return c
    return gd.DEFAULT_COLLECTION


def item_meta(identifier):
    return cached(f"meta-{identifier}", lambda: gd.metadata(identifier))


def rating(doc):
    try:
        return float(doc.get("avg_rating") or 0)
    except ValueError:
        return 0.0


def reviews(doc):
    try:
        return int(doc.get("num_reviews") or 0)
    except ValueError:
        return 0


def local_show_dir(doc):
    date = doc["date"]
    return os.path.join(gd.DEFAULT_DEST, gd.collection_dir(doc.get("collection")), date[:4],
                        f"{date}.{doc['identifier']}")


def source_rank(doc):
    kind = PREFER.index(doc["kind"]) if doc["kind"] in PREFER else len(PREFER)
    return (kind, -rating(doc), -reviews(doc), -int(doc.get("downloads") or 0))


def group_dates(docs):
    by = {}
    for d in docs:
        by.setdefault(d["date"], []).append(d)
    out = []
    for date in sorted(by):
        items = sorted(by[date], key=source_rank)
        best = items[0]
        kinds = "".join(letter for k, letter in (("matrix", "M"), ("sbd", "S"), ("aud", "A"))
                        if any(i["kind"] == k for i in items))
        venue = ", ".join(x for x in (best.get("venue"), best.get("coverage")) if x)
        out.append({"date": date, "items": items, "venue": venue,
                    "kinds": kinds, "rating": max(rating(i) for i in items),
                    "local": any(os.path.isdir(local_show_dir(i)) for i in items)})
    return out


def secs(v):
    if v in (None, ""):
        return None
    s = str(v)
    try:
        if ":" in s:
            t = 0.0
            for part in s.split(":"):
                t = t * 60 + float(part)
            return t
        return float(s)
    except ValueError:
        return None


def fmt_time(t):
    if t is None:
        return "--:--"
    t = int(t)
    if t >= 3600:
        return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"
    return f"{t // 60}:{t % 60:02d}"


def show_title(doc, meta):
    md = meta.get("metadata", {})
    if doc.get("lp"):
        return f"{doc.get('artist')}: {doc.get('title') or md.get('title')} ({doc['date'][:4]})"
    return f"{doc['date']} {md.get('venue') or md.get('coverage') or ''}".strip()


def album_docs(menu=None):
    menus = [menu] if menu else list(ALBUMS)
    return [{"identifier": i, "date": f"{y}-01-01", "title": t, "artist": a, "collection": ["album_recordings"],
             "kind": "other", "lp": menu_} for menu_ in menus for i, y, a, t in ALBUMS[menu_]]


def tracks_for(doc):
    """One entry per track: title, length, and where to play it from (local file or URL)."""
    meta = item_meta(doc["identifier"])
    stream_only = gd.is_stream_only(meta)
    files = gd.audio_files(meta)
    by_base = {}
    for f in files:
        by_base.setdefault(os.path.splitext(f["name"])[0], {})[f["ext"]] = f
    show_dir = local_show_dir(doc)
    local = {}
    if os.path.isdir(show_dir):
        for name in os.listdir(show_dir):
            ext = os.path.splitext(name)[1].lower()
            if ext in gd.AUDIO and not name.endswith(".part"):
                local.setdefault(os.path.splitext(name)[0], {})[ext] = os.path.join(show_dir, name)
    order = STREAM_ORDER_RESTRICTED if stream_only else STREAM_ORDER_OPEN
    if doc.get("lp") and not stream_only:
        # LP transfers: "<id>_disc1side1.flac" (untitled 24-bit original) next to
        # "01.01. This Side.mp3" (titled derivatives, one per cut). One track per
        # side, the FLAC, titled from the side's first cut. Stream-only LPs fall
        # through and play cut by cut as mp3.
        sides, first_cut = {}, {}
        for f in files:
            if f["ext"] == ".flac":
                m = gd.re.search(r"disc(\d+)side(\d+)\.flac$", f["name"])
                if m:
                    sides[(int(m.group(1)), int(m.group(2)))] = f
            elif f["ext"] == ".mp3":
                m = gd.re.match(r"(?:disc(\d+)/)?(\d+)\.(\d+)\. ", f["name"])
                if m:
                    key = (int(m.group(1) or 1), int(m.group(2)))
                    if key not in first_cut or int(m.group(3)) < first_cut[key][0]:
                        first_cut[key] = (int(m.group(3)), f["title"])
        if sides:
            out = []
            for key in sorted(sides):
                f = sides[key]
                title = first_cut.get(key, (0, f["title"]))[1]
                if not gd.re.match(r"side \d", title, gd.re.I):
                    title = f"Side {key[1]}: {title}"
                base = os.path.splitext(os.path.basename(f["name"]))[0]
                loc = local.get(base, {}).get(".flac")
                src = loc or gd.DL_BASE + gd.urllib.parse.quote(doc["identifier"]) + "/" + gd.urllib.parse.quote(f["name"])
                out.append({"title": title, "length": secs(f.get("length")), "src": src,
                            "how": "local flac" if loc else "stream flac", "track": len(out) + 1})
            return out, meta
    out = []
    for base in sorted(by_base):
        exts = by_base[base]
        rep = next((exts[e] for e in (".flac", ".shn", ".mp3", ".ogg") if e in exts))
        src, how = None, None
        for e in (".flac", ".mp3", ".ogg", ".shn"):
            if e in local.get(base, {}):
                src, how = local[base][e], f"local {e[1:]}"
                break
        if not src:
            for e in order:
                if e in exts:
                    src = gd.DL_BASE + gd.urllib.parse.quote(doc["identifier"]) + "/" + gd.urllib.parse.quote(exts[e]["name"])
                    how = f"stream {e[1:]}"
                    break
        if not src:
            continue
        out.append({"title": rep["title"], "length": secs(rep.get("length")), "src": src, "how": how,
                    "track": rep.get("track") or len(out) + 1})
    return out, meta


# --------------------------------------------------------------------------- song search

class SongSearch(threading.Thread):
    """Find every show with `song`: one item per date, best source that really has the track.

    Runs in the background; `results` fills in date order while the UI keeps drawing.
    Uses the search index for candidates and cached item metadata to verify.
    """

    def __init__(self, song, collection=gd.DEFAULT_COLLECTION):
        super().__init__(daemon=True)
        self.song = song
        self.collection = collection
        self.results = []
        self.total = self.checked = 0
        self.done = False
        self.error = None

    def rank(self, d):
        kind = PREFER.index(d["kind"]) if d["kind"] in PREFER else len(PREFER)
        return (not os.path.isdir(local_show_dir(d)), kind, not gd.doc_lossless_downloadable(d),
                -rating(d), -reviews(d))

    def pick(self, cands):
        for d in sorted(cands, key=self.rank)[:8]:
            try:
                files, so, ext = gd.choose_files(item_meta(d["identifier"]), "best", self.song)
            except Exception:
                continue
            if files:
                d["song_tracks"] = [f["title"] for f in files]
                return d
        return None

    def run(self):
        key = "song-" + ("" if self.collection == gd.DEFAULT_COLLECTION else self.collection + "-") \
            + gd.norm(self.song).replace(" ", "-")
        try:
            hit = cached(key, lambda: None)
        except Exception:
            hit = None
        if hit:
            self.results.extend(hit)
            self.total = self.checked = len(hit)
            self.done = True
            return
        try:
            args = SimpleNamespace(collection=self.collection, year=None, date=None, song=self.song,
                                   min_rating=None, min_reviews=None, source="any", downloadable=False,
                                   query=None, sort="date asc", limit=10000)
            docs = gd.search(args)[1]
            by_date = {}
            for d in docs:
                by_date.setdefault(d["date"], []).append(d)
            self.total = len(by_date)
            with cf.ThreadPoolExecutor(10) as ex:
                for d in ex.map(self.pick, [by_date[k] for k in sorted(by_date)]):
                    self.checked += 1
                    if d:
                        self.results.append(d)
            with open(_cache_path(key), "w") as f:
                json.dump(self.results, f)
        except Exception as e:
            self.error = str(e)
        self.done = True


# --------------------------------------------------------------------------- mpv

class Mpv:
    def __init__(self):
        run = os.environ.get("XDG_RUNTIME_DIR") or CACHE
        self.path = os.path.join(run, "deadtui-mpv.sock")
        self.proc = None
        self.sock = None
        self.rid = 0
        self.buf = b""
        self.adopted = False   # True when we attached to an mpv that was already running on the socket

    def start(self):
        if os.path.exists(self.path) and self.adopt():
            return
        if os.path.exists(self.path):
            os.unlink(self.path)
        self.proc = subprocess.Popen(
            ["mpv", "--no-video", "--no-terminal", "--idle=yes", "--force-window=no", "--audio-display=no",
             "--gapless-audio=yes", "--prefetch-playlist=yes", "--cache=yes", "--demuxer-max-bytes=64MiB",
             "--user-agent=" + gd.UA, "--input-ipc-server=" + self.path],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            if os.path.exists(self.path):
                break
            time.sleep(0.05)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.path)
        self.sock.settimeout(0.3)

    def adopt(self):
        """Attach to an mpv left running by an earlier instance (closed terminal, hangup, crash).

        mpv keeps its playlist and keeps playing when the TUI dies; only q stops it. Rather
        than start a second player over it, take it over: same socket, same commands.
        """
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            sock.connect(self.path)
            sock.sendall(b'{"command":["get_property","playlist-count"],"request_id":1}\n')
            data = b""
            while b"\n" not in data:
                chunk = sock.recv(65536)
                if not chunk:
                    raise OSError("closed")
                data += chunk
            ok = any(json.loads(l).get("request_id") == 1 for l in data.split(b"\n") if l)
        except (OSError, ValueError):
            return False
        if not ok:
            return False
        sock.settimeout(0.3)
        self.sock, self.adopted, self.proc = sock, True, None
        return True

    def cmd(self, *args):
        if not self.sock:
            return None
        self.rid += 1
        rid = self.rid
        try:
            self.sock.sendall(json.dumps({"command": list(args), "request_id": rid}).encode() + b"\n")
        except OSError:
            return None
        deadline = time.time() + 3
        while time.time() < deadline:
            while b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if msg.get("request_id") == rid:
                    return msg
            try:
                data = self.sock.recv(65536)
            except socket.timeout:
                continue
            except OSError:
                return None
            if not data:
                return None
            self.buf += data
        return None

    def get(self, prop, default=None):
        r = self.cmd("get_property", prop)
        return r["data"] if r and r.get("error") == "success" else default

    def play(self, srcs, start=0):
        """Replace the playlist with srcs, starting at index `start`, without a blip of track 0."""
        self.cmd("loadfile", srcs[start], "replace")
        for s in srcs[start + 1:]:
            self.cmd("loadfile", s, "append")
        for i, s in enumerate(srcs[:start]):
            self.cmd("loadfile", s, "append")
            n = self.get("playlist-count", 1)
            self.cmd("playlist-move", n - 1, i)
        self.cmd("set_property", "pause", False)

    def status(self):
        pos = self.get("playlist-pos", -1)
        if pos is None or pos < 0:
            return None
        return {"pos": pos, "count": self.get("playlist-count", 0), "time": self.get("time-pos"),
                "dur": self.get("duration"), "paused": bool(self.get("pause", False)),
                "buffering": bool(self.get("paused-for-cache", False)),
                "media_title": self.get("media-title"), "codec": self.get("audio-codec-name"),
                "params": self.get("audio-params") or {}, "bitrate": self.get("audio-bitrate")}

    def stop(self):
        if self.sock:
            self.cmd("quit")
        if self.proc:
            try:
                self.proc.wait(2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        elif self.adopted:
            for _ in range(20):   # the adopted mpv is not our child; wait for its socket to go
                if not os.path.exists(self.path):
                    break
                time.sleep(0.1)
        if os.path.exists(self.path):
            os.unlink(self.path)


# --------------------------------------------------------------------------- ui

class Level:
    def __init__(self, kind, title, items, render, ctx=None):
        self.kind, self.title, self.items, self.render, self.ctx = kind, title, items, render, ctx or {}
        self.cursor, self.top, self.filter = 0, 0, ""

    def visible(self):
        if not self.filter:
            return list(enumerate(self.items))
        f = self.filter.lower()
        return [(i, it) for i, it in enumerate(self.items) if f in self.render(it, 500).lower()]


class App:
    def __init__(self, stdscr):
        self.scr = stdscr
        self.mpv = Mpv()
        self.stack = []
        self.msg = ""
        self.msg_until = 0
        self.now = None           # {"doc", "tracks", "date"} of what mpv is playing
        self.logged = None        # (id(now), pos) last written to history.jsonl
        self.detach = False       # q while playing: quit the TUI, leave mpv playing (Q stops it)
        self.fetches = []         # (identifier, Popen, logpath)
        self.state = self.load_state()
        curses.curs_set(0)
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_RED, -1)
        self.scr.timeout(500)
        self.last_status = None
        self.pending_seek = None
        self.last_key = time.time()
        self.viz_mode = self.load_state().get("viz_mode", "bars")
        self.rng = random.Random()
        self.splash()
        self.push_home()
        self.restore_view()

    def splash(self):
        """Poseidon Earth Shaker, crowned, trident raised, for SPLASH_SECS or until a key."""
        if not SPLASH_SECS:
            return
        h, w = self.scr.getmaxyx()
        style = SPLASH_STYLE if SPLASH_STYLE in SPLASHES else sorted(SPLASHES)[int(time.time()) % len(SPLASHES)]
        art = SPLASHES[style]
        aw = max(len(r) for r in art)
        lines = art + ["", "MAY THE LORD POSEIDON CONVEY YOU", "E A R T H   S H A K E R", "archive.org  ·  Grateful Dead"]
        top = max(0, (h - len(lines)) // 2)
        gold = curses.color_pair(3) | curses.A_BOLD
        red = curses.color_pair(4) | curses.A_BOLD
        white = curses.A_BOLD
        sea = curses.color_pair(1)
        self.scr.erase()
        for i, row in enumerate(lines):
            y = top + i
            if y >= h - 1:
                break
            if i < len(art):
                x = max(0, (w - aw) // 2)
                ink = [c for c in range(len(row)) if row[c] != " "]
                for c, ch in enumerate(row):
                    if ch == " ":
                        continue
                    if ch in "║╲╱▲⚡":
                        attr = gold
                    elif ch == "~":
                        attr = sea
                    elif ch == "▓" or (i in SPLASH_EYES[style] and ch in "█▀" and ink and ink[1] < c < ink[-2]):
                        attr = red                                  # the eyes
                    else:
                        attr = white
                    self.put(y, x + c, ch, attr)
            else:
                x = max(0, (w - len(row)) // 2)
                attr = {len(art) + 1: curses.color_pair(1) | curses.A_BOLD, len(art) + 2: gold}.get(i, curses.A_DIM)
                self.put(y, x, row[:w - 1], attr)
        self.scr.refresh()
        end = time.time() + SPLASH_SECS
        while True:                      # terminals send a KEY_RESIZE right after start; it must not cut the splash short
            left = end - time.time()
            if left <= 0:
                break
            self.scr.timeout(int(left * 1000))
            ch = self.scr.getch()
            if ch == -1 or ch != curses.KEY_RESIZE:
                break
        self.scr.timeout(500)

    # ---- state

    def load_state(self):
        try:
            with open(STATE) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def save_state(self, doc, track_i, time_pos=None):
        self.state = {"last": "show", "year": doc["date"][:4], "date": doc["date"], "identifier": doc["identifier"],
                      "track": track_i, "time": time_pos, "collection": doc_collection(doc), "lp": doc.get("lp", False)}
        self.write_state()

    def save_radio_state(self, key):
        self.state = {**self.state, "last": "radio", "radio": key}
        self.write_state()

    def write_state(self):
        os.makedirs(CACHE, exist_ok=True)
        with open(STATE + ".tmp", "w") as f:
            json.dump(self.state, f)
        os.replace(STATE + ".tmp", STATE)

    def save_position(self):
        """Called on quit: remember where in the track we were."""
        st = self.last_status
        if self.now and self.now.get("doc") and st:
            self.save_state(self.now["doc"], st["pos"], st.get("time"))

    def restore_view(self):
        """Re-open the view saved by the previous run: the last show at its track, or the radio list."""
        st = self.state
        try:
            if st.get("last") == "radio":
                self.push_radio(st.get("radio"))
                return
            if not st.get("identifier"):
                return
            if st.get("lp"):
                self.push_albums(st["lp"] if st["lp"] in ALBUMS else FIRESIGN, st["identifier"])
                doc = next((d for d in album_docs() if d["identifier"] == st["identifier"]), None)
                if doc:
                    self.push_tracks(doc, int(st.get("track") or 0))
                    if st.get("time"):
                        self.say(f"r resumes at {fmt_time(st['time'])}", 8)
                return
            year = int(st["year"])
            coll = st.get("collection") or gd.DEFAULT_COLLECTION
            self.push_years(coll)
            self.push_dates(year, st["date"], coll)
            lvl = self.stack[-1]
            if lvl.kind != "dates":
                return
            entry = next((d for d in lvl.items if d["date"] == st["date"]), None)
            if not entry:
                return
            self.push_sources(entry, st["identifier"])
            doc = next((d for d in entry["items"] if d["identifier"] == st["identifier"]), None)
            if not doc:
                return
            self.push_tracks(doc, int(st.get("track") or 0))
            if st.get("time"):
                self.say(f"r resumes at {fmt_time(st['time'])}", 8)
        except Exception as e:
            self.say(f"could not re-open last show: {e}", 8)

    def say(self, text, secs_=4):
        self.msg, self.msg_until = text, time.time() + secs_

    def loading(self, text):
        self.msg, self.msg_until = text, time.time() + 60
        self.draw()

    # ---- levels

    def push(self, level, select=None):
        if select is not None:
            level.cursor = max(0, min(select, len(level.items) - 1))
        self.stack.append(level)

    HOME = [
        (HDR, "Now"),
        QUEUE, RANDOM,
        (HDR, "The Dead"),
        YEARS_GD, RAIN, TEARS, JGB,
        (HDR, "Memories"),
        # one row per MEMORIES entry goes here
        (HDR, "Not Dead"),
        RADIO, FIRESIGN, JOKES,
        (HDR, "Everything"),
        HIST,
    ]
    HOME_TEXT = {
        QUEUE: "▶ Now playing        the current playlist",
        RANDOM: "🎲 Random show       any night, 1965-1995, best source, straight into play",
        YEARS_GD: "Grateful Dead        1965-1995, by year",
        RAIN: "☔ Rain and Snow      random weather and water songs, a random night's version of each, on and on",
        TEARS: "Tears                the weepers: Stella Blue, Black Peter, Wharf Rat, Morning Dew...",
        JGB: "JGB                  Melvin Seals & Jerry Garcia Band, 1996 on, after Jerry",
        RADIO: "♪ Classical radio    lossless FLAC stations",
        FIRESIGN: "Firesign Theatre     the LPs, 24-bit vinyl transfers",
        JOKES: "Jokes                comedy LPs: Buckley, Bruce, Sahl, Newhart, Pryor, the Goons, Python...",
        HIST: "History              everything played, newest first",
    }

    def home_items(self):
        items = []
        for it in self.HOME:
            items.append(it)
            if it == (HDR, "Memories"):
                items.extend((MEMORY, m) for m in MEMORIES)
        return items

    def push_home(self):
        def render(it, w):
            if isinstance(it, tuple) and it[0] == HDR:
                return f"{it[1]}"
            if isinstance(it, tuple) and it[0] == MEMORY:
                return f"    ✦ {it[1]}"
            return "    " + self.HOME_TEXT[it]
        items = self.home_items()
        lvl = Level("home", "Poseidon", items, render, {"home": True})
        st = self.state
        want = RADIO if st.get("last") == "radio" else (
            (st.get("lp") if st.get("lp") in ALBUMS else FIRESIGN) if st.get("lp") else (
                JGB if st.get("collection") == "JGB" else YEARS_GD))
        self.push(lvl, items.index(want) if want in items else items.index(YEARS_GD))

    def push_years(self, collection=gd.DEFAULT_COLLECTION):
        subdir = gd.collection_dir(collection)

        def render(y, w):
            n = 0
            d = os.path.join(gd.DEFAULT_DEST, subdir, str(y))
            if os.path.isdir(d):
                n = len(os.listdir(d))
            return f"  {y}" + (f"    {n} on disk" if n else "")
        items = list(COLLECTIONS[collection]["years"])
        lvl = Level("years", COLLECTIONS[collection]["title"], items, render, {"collection": collection})
        year = int(self.state["year"]) if self.state.get("year") else None
        same = (self.state.get("collection") or gd.DEFAULT_COLLECTION) == collection
        self.push(lvl, items.index(year) if same and year in items else 0)

    def random_version(self, song):
        """A random night's version of `song`: (doc, track index, tracks, meta), or None."""
        key = "song-index-" + gd.norm(song).replace(" ", "-")

        def fetch():
            args = SimpleNamespace(collection=gd.DEFAULT_COLLECTION, year=None, date=None, song=song, min_rating=None,
                                   min_reviews=None, source="any", downloadable=False, query=None,
                                   sort="date asc", limit=3000)
            return gd.search(args)[1]
        docs = list(cached(key, fetch) or [])
        self.rng.shuffle(docs)
        if self.rng.random() < 0.4:                                         # some of the time, what is on disk first
            docs.sort(key=lambda d: not os.path.isdir(local_show_dir(d)))
        for d in docs[:10]:
            try:
                files, _, _ = gd.choose_files(item_meta(d["identifier"]), "best", song)
                if not files:
                    continue
                idx, tracks, meta = self.song_track_index(d, song)
                return d, idx, tracks, meta
            except Exception:
                continue
        return None

    def rain_tracks(self, n):
        out = []
        for song in self.rng.sample(RAIN_SONGS, min(n, len(RAIN_SONGS))):
            self.loading(f"☔ looking for a {song}...")
            hit = self.random_version(song)
            if not hit:
                continue
            doc, idx, tracks, meta = hit
            t = dict(tracks[idx])
            t["title"] = f"{show_title(doc, meta)}: {t['title']}"
            out.append(t)
        return out

    def rain(self):
        tracks = self.rain_tracks(RAIN_BATCH)
        if not tracks:
            self.say("no rain today (archive.org?)")
            return
        self.now = {"doc": None, "tracks": tracks, "title": "☔ Rain and Snow", "rain": True}
        self.mpv.play([t["src"] for t in tracks], 0)
        self.say(f"☔ {len(tracks)} songs to start; more fall as it goes", 8)
        self.push_queue()

    def rain_more(self):
        """Called from the main loop when the last queued song starts: add a few more."""
        more = self.rain_tracks(3)
        for t in more:
            self.mpv.cmd("loadfile", t["src"], "append")
        self.now["tracks"].extend(more)
        self.msg_until = 0

    def random_show(self):
        """Any night: a random year, a random date in it (rated 4+ when the year has such), best source."""
        year = self.rng.choice(YEARS)
        self.loading(f"rolling the dice... {year}")
        try:
            dates = group_dates(year_docs(year))
        except Exception as e:
            self.say(f"archive.org: {e}")
            return
        if not dates:
            self.say(f"nothing in {year}, roll again")
            return
        good = [d for d in dates if d["rating"] >= 4.0] or dates
        entry = self.rng.choice(good)
        doc = self.best_source(entry)
        del self.stack[1:]
        self.push_years(gd.DEFAULT_COLLECTION)
        self.stack[-1].cursor = self.stack[-1].items.index(year)
        self.push_dates(year, entry["date"], gd.DEFAULT_COLLECTION)
        self.push_sources(entry, doc["identifier"])
        self.play_doc(doc)
        self.push_tracks(doc, 0)

    def push_albums(self, menu=FIRESIGN, select_id=None):
        def render(d, w):
            loc = "*" if os.path.isdir(local_show_dir(d)) else " "
            if d.get("clip"):
                return f"{loc} ✂ {d['title']}   {d['date']} at {fmt_time(d['start'])}: {d['note']}"[:w]
            who = "" if menu == FIRESIGN else f"{d['artist']:18} "
            return f"{loc} {d['date'][:4]}  {who}{d['title']}"[:w]
        items = (list(CLIPS) if menu == JOKES else []) + album_docs(menu)
        lvl = Level("albums", MENU_TITLES[menu], items, render, {"lp": menu})
        sel = next((i for i, d in enumerate(items) if d["identifier"] == select_id), 0) if select_id else 0
        self.push(lvl, sel)

    def push_tears(self):
        def render(t, w):
            song, coll = t
            who = "" if coll == gd.DEFAULT_COLLECTION else f"   ({COLLECTIONS[coll]['title']})"
            return f"  {song}{who}"[:w]
        lvl = Level("tears", "Tears", TEARS_LIST, render, {"tears": True})
        self.push(lvl, 0)

    # ---- adoption

    def doc_for_src(self, src):
        """Best-effort doc for a playlist entry: a local show dir under dead/, or an archive.org URL."""
        dest = os.path.realpath(gd.DEFAULT_DEST)
        if not src.startswith(("http://", "https://")):
            src = os.path.realpath(src)
        if src.startswith(dest + os.sep):
            rel = os.path.relpath(os.path.dirname(src), dest).split(os.sep)
            if len(rel) == 3 and "." in rel[2]:
                subdir, _, dirname = rel
                date, ident = dirname.split(".", 1)
                coll = next((c for c, d in gd.COLLECTION_DIRS.items() if d == subdir), gd.DEFAULT_COLLECTION)
                return {"identifier": ident, "date": date, "collection": [coll], "kind": gd.source_kind({"identifier": ident}),
                        "lp": (FIRESIGN if any(ident == a[0] for a in ALBUMS[FIRESIGN]) else JOKES) if subdir == "lp" else False,
                        "artist": next((a[2] for m in ALBUMS for a in ALBUMS[m] if a[0] == ident), None),
                        "title": next((a[3] for m in ALBUMS for a in ALBUMS[m] if a[0] == ident), None)}
        if src.startswith(gd.DL_BASE):
            ident = gd.urllib.parse.unquote(src[len(gd.DL_BASE):].split("/", 1)[0])
            try:
                md = item_meta(ident).get("metadata", {})
            except Exception:
                return None
            coll = md.get("collection") or []
            return {"identifier": ident, "date": (md.get("date") or "0000-00-00")[:10], "collection": coll,
                    "kind": gd.source_kind({"identifier": ident, "source": md.get("source")}),
                    "lp": FIRESIGN if "album_recordings" in coll else False, "title": md.get("title")}
        return None

    def adopt_playlist(self):
        """Describe what the adopted mpv is playing so the status line and n/b/seek make sense."""
        pl = self.mpv.get("playlist") or []
        if not pl:
            return
        self.loading(f"adopting running mpv: {len(pl)} tracks...")
        st = next((s_ for s_ in stations() if any(e.get("filename") == s_["url"] for e in pl)), None)
        if st and len(pl) == 1:
            self.now = {"doc": None, "radio": st["key"], "title": st["name"],
                        "tracks": [{"title": st["name"], "how": st["fmt"], "src": st["url"], "length": None}]}
            self.say(f"adopted running mpv: {st['name']}", 8)
            return
        docs, by_src = {}, {}
        for e in pl:
            src = e.get("filename") or ""
            key = os.path.dirname(src)
            if key not in docs:
                docs[key] = self.doc_for_src(src)
                if docs[key]:
                    try:
                        tracks, meta = tracks_for(docs[key])
                        docs[key] = (docs[key], show_title(docs[key], meta))
                        by_src.update({(t["src"] if t["src"].startswith("http") else os.path.realpath(t["src"])): t
                                       for t in tracks})
                    except Exception:
                        docs[key] = None
        combined = []
        for e in pl:
            src = e.get("filename") or ""
            key = src if src.startswith("http") else os.path.realpath(src)
            t = dict(by_src.get(key) or {"title": os.path.basename(src), "src": src, "length": None,
                                          "how": "stream" if src.startswith("http") else "local " + src.rsplit(".", 1)[-1]})
            shows = docs.get(os.path.dirname(src))
            if shows and len({k for k, v in docs.items() if v}) > 1:
                t["title"] = f"{shows[1]}: {t['title']}"
            combined.append(t)
        real = [v for v in docs.values() if v]
        if len(real) == 1:
            doc, title = real[0]
            whole = [t["src"] for t in by_src.values()]
            # the doc is kept only when mpv holds the complete show in order, so the tracks
            # view's ▶ and the saved state line up; a partial run keeps the title only
            self.now = {"doc": doc if [t["src"] for t in combined] == whole else None,
                        "tracks": combined, "title": title}
        else:
            self.now = {"doc": None, "tracks": combined, "title": f"adopted playlist ({len(pl)} tracks)"}
        pos = self.mpv.get("playlist-pos", 0) or 0
        self.say(f"adopted running mpv: {len(pl)} tracks, at {pos + 1}: {combined[min(pos, len(combined) - 1)]['title']}", 10)

    # ---- history

    def log_history(self, track):
        """Append what just started playing. Enough is kept to play it again from History."""
        doc = self.now.get("doc")
        rec = {"ts": time.strftime("%Y-%m-%d %H:%M"), "show": self.now.get("title"), "title": track.get("title"),
               "src": track.get("src"), "how": track.get("how"), "radio": self.now.get("radio")}
        if doc:
            rec["doc"] = {k: doc.get(k) for k in ("identifier", "date", "collection", "kind", "lp", "artist", "title")}
            rec["track"] = self.last_status["pos"] if self.last_status else 0
        try:
            os.makedirs(CACHE, exist_ok=True)
            with open(HISTORY, "a") as f:
                f.write(json.dumps(rec) + "\n")
        except OSError:
            pass

    def history(self):
        try:
            with open(HISTORY) as f:
                lines = f.readlines()[-HISTORY_ROWS:]
        except OSError:
            return []
        out = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
        return out[::-1]

    def push_history(self):
        def render(r, w):
            show = r.get("show") or ""
            title = r.get("title") or ""
            if r.get("radio"):
                return f"  {r['ts']}  {show}"[:w]
            return f"  {r['ts']}  {show}  ·  {title}"[:w]
        items = self.history()
        lvl = Level("history", "History", items, render, {"history": True})
        self.push(lvl, 0)

    def play_history(self, r):
        if r.get("radio"):
            s_ = next((x for x in stations() if x["key"] == r["radio"]), None)
            if s_:
                self.play_station(s_)
            else:
                self.say("station no longer listed")
            return
        doc = r.get("doc")
        if doc and doc.get("identifier"):
            self.play_doc(doc, int(r.get("track") or 0))
            return
        if r.get("src"):
            self.now = {"doc": None, "title": r.get("show") or "", "tracks": [{"title": r.get("title"), "src": r["src"],
                        "how": r.get("how") or "", "length": None}]}
            self.mpv.play([r["src"]], 0)
            self.say(f"playing {r.get('title')}")

    def memory_doc(self, entry):
        coll, ident, date, first, last, note = entry
        return {"identifier": ident, "date": date, "collection": [coll], "kind": gd.source_kind({"identifier": ident})}

    def push_memory(self, name):
        def render(e, w):
            coll, ident, date, first, last, note = e
            span = first if not last else (f"{first} > ... (rest of show)" if last == "*" else f"{first} > {last}")
            who = "" if coll == gd.DEFAULT_COLLECTION else "JGB "
            left = f"  {who}{date}  {span}"
            return (left.ljust(46) + "  " + note)[:w]
        lvl = Level("memory", name, MEMORIES[name], render, {"memory": name})
        self.push(lvl, 0)

    def memory_tracks(self, entry):
        """The tracks an entry covers: from its first song through its last (or the show's end)."""
        coll, ident, date, first, last, note = entry
        doc = self.memory_doc(entry)
        i, tracks, meta = self.song_track_index(doc, first)
        if last is None:
            j = i
        elif last == "*":
            j = len(tracks) - 1
        else:
            j = next((k for k in range(i, len(tracks)) if gd.song_matches(last, tracks[k]["title"])), i)
        return doc, i, tracks[i:j + 1], meta

    def play_memory(self, lvl, entry=None):
        entries = [entry] if entry else list(lvl.items)
        self.loading("queueing the evening..." if not entry else f"loading {entry[1]}...")
        combined = []
        for e in entries:
            try:
                doc, i, tracks, meta = self.memory_tracks(e)
            except Exception as ex:
                self.say(f"metadata: {ex}")
                return
            for t in tracks:
                t = dict(t)
                t["title"] = f"{show_title(doc, meta)}: {t['title']}"
                combined.append(t)
        if not combined:
            self.say("nothing playable")
            return
        if entry and len(entries) == 1 and entry[4] == "*":
            self.play_doc(self.memory_doc(entry), i)   # the whole rest of the show, with state saved
            return
        self.now = {"doc": None, "tracks": combined, "title": f"✦ {lvl.ctx['memory']}"}
        self.mpv.play([t["src"] for t in combined], 0)
        self.say(f"playing {len(combined)} tracks")

    def push_queue(self):
        if not self.now or not self.now.get("tracks"):
            self.say("nothing is playing")
            return
        tracks = self.now["tracks"]

        def render(t, w):
            right = f" {fmt_time(t.get('length'))}  {t.get('how') or '':12}"
            left = f"  {tracks.index(t) + 1:>3}  {t['title']}"
            return left[:max(0, w - len(right))].ljust(w - len(right)) + right
        lvl = Level("queue", f"▶ {self.now['title']}", tracks, render, {"queue": True, "now": self.now})
        st = self.last_status
        self.push(lvl, st["pos"] if st else 0)

    def play_clip(self, c):
        self.loading(f"loading {c['identifier']}...")
        try:
            idx, tracks, meta = self.song_track_index(c, c["song"])
        except Exception as e:
            self.say(f"metadata: {e}")
            return
        self.play_doc(c, idx, seek_to=c["start"])
        self.say(f"✂ {c['title']}: {c['song']} from {fmt_time(c['start'])}", 8)

    def push_radio(self, select_key=None):
        def render(s_, w):
            right = f"  {s_['fmt']:13}"
            left = f"  {s_['name']:26} {s_['notes']}"
            return left[:max(0, w - len(right))].ljust(w - len(right)) + right
        items = stations()
        lvl = Level("radio", "♪ Classical radio", items, render)
        sel = next((i for i, s_ in enumerate(items) if s_["key"] == select_key), 0) if select_key else 0
        self.push(lvl, sel)

    def play_station(self, s_):
        self.now = {"doc": None, "radio": s_["key"], "title": s_["name"],
                    "tracks": [{"title": s_["name"], "how": s_["fmt"], "src": s_["url"], "length": None}]}
        self.mpv.play([s_["url"]], 0)
        self.save_radio_state(s_["key"])
        self.say(f"tuning {s_['name']} ({s_['fmt']})")

    def probe_station(self, s_):
        self.loading(f"probing {s_['name']}...")
        kv, err = radio.ffprobe(s_["url"])
        if err:
            self.say(f"{s_['name']}: {err}", 10)
        else:
            self.say(f"{s_['name']}: {radio.fmt_probe(kv)}", 15)

    def push_dates(self, year, select_date=None, collection=gd.DEFAULT_COLLECTION):
        who = "" if collection == gd.DEFAULT_COLLECTION else f"{collection} "
        self.loading(f"loading {who}{year} from archive.org...")
        try:
            docs = year_docs(year, collection)
        except Exception as e:
            self.say(f"archive.org: {e}")
            return
        dates = group_dates(docs)

        def render(d, w):
            venue = d["venue"]
            r = f"{d['rating']:.1f}" if d["rating"] else " - "
            loc = "*" if d["local"] else " "
            right = f" {d['kinds']:3} {r:>3} {len(d['items']):>3}"
            left = f"{loc} {d['date']}  {venue}"
            return left[:max(0, w - len(right))].ljust(w - len(right)) + right
        lvl = Level("dates", str(year), dates, render, {"year": year, "collection": collection})
        sel = next((i for i, d in enumerate(dates) if d["date"] == select_date), 0) if select_date else 0
        self.push(lvl, sel)
        self.msg_until = 0

    def push_sources(self, date_entry, select_id=None):
        def render(d, w):
            r = f"{rating(d):.2f}" if rating(d) else "  -  "
            local = "local " if os.path.isdir(local_show_dir(d)) else "      "
            so = "stream" if "stream_only" in (d.get("collection") or []) else "dl    "
            return f"  {KIND_SHORT[d['kind']]:3}  {r} ({reviews(d):>3})  {so}  {local} {d['identifier']}"[:w]
        items = date_entry["items"]
        lvl = Level("sources", date_entry["date"], items, render, {"date": date_entry})
        sel = next((i for i, d in enumerate(items) if d["identifier"] == select_id), 0) if select_id else 0
        self.push(lvl, sel)

    def push_tracks(self, doc, select=0):
        self.loading(f"loading {doc['identifier']}...")
        try:
            tracks, meta = tracks_for(doc)
        except Exception as e:
            self.say(f"metadata: {e}")
            return
        if not tracks:
            self.say("no playable files in this item")
            return

        def render(t, w):
            right = f" {fmt_time(t['length'])}  {t['how']:12}"
            left = f"  {t['track']:>2}  {t['title']}"
            return left[:max(0, w - len(right))].ljust(w - len(right)) + right
        title = show_title(doc, meta)
        lvl = Level("tracks", title, tracks, render, {"doc": doc, "tracks": tracks, "title": title})
        self.push(lvl, select)
        self.msg_until = 0

    def push_songs(self, song, collection=None):
        srch = SongSearch(song, collection or self.collection())
        srch.start()

        def render(d, w):
            venue = ", ".join(x for x in (d.get("venue"), d.get("coverage")) if x)
            r = f"{rating(d):.1f}" if rating(d) else " - "
            loc = "*" if os.path.isdir(local_show_dir(d)) else " "
            so = "mp3 " if "stream_only" in (d.get("collection") or []) else "    "
            right = f" {KIND_SHORT[d['kind']]:3} {r:>3} {so}"
            left = f"{loc} {d['date']}  {venue}"
            return left[:max(0, w - len(right))].ljust(w - len(right)) + right
        coll = srch.collection
        title = f"♪ {song}" if coll == gd.DEFAULT_COLLECTION else f"♪ {song}  ({COLLECTIONS[coll]['title']})"
        lvl = Level("songs", title, srch.results, render, {"song": song, "search": srch, "collection": coll})
        self.push(lvl)

    def song_track_index(self, doc, song):
        tracks, meta = tracks_for(doc)
        for i, t in enumerate(tracks):
            if gd.song_matches(song, t["title"]) or gd.song_matches(song, os.path.basename(t["src"])):
                return i, tracks, meta
        return 0, tracks, meta

    def play_all_versions(self, lvl):
        song, srch = lvl.ctx["song"], lvl.ctx["search"]
        docs = [d for _, d in lvl.visible()]
        if not docs:
            self.say("no versions yet")
            return
        self.loading(f"queueing {len(docs)} versions of {song}...")
        combined = []
        for d in docs:
            try:
                i, tracks, meta = self.song_track_index(d, song)
            except Exception:
                continue
            if not tracks:
                continue
            t = dict(tracks[i])
            venue = d.get("venue") or d.get("coverage") or ""
            t["title"] = f"{d['date']} {venue}: {t['title']}"
            combined.append(t)
        if not combined:
            self.say("nothing playable")
            return
        self.now = {"doc": None, "tracks": combined, "title": f"♪ {song} ({len(combined)} versions)"}
        self.mpv.play([t["src"] for t in combined], 0)
        self.say(f"playing {len(combined)} versions of {song} in date order")

    def pop(self):
        if len(self.stack) > 1:
            self.stack.pop()

    # ---- playback

    def play_doc(self, doc, start=0, seek_to=None):
        try:
            tracks, meta = tracks_for(doc)
        except Exception as e:
            self.say(f"metadata: {e}")
            return
        if not tracks:
            self.say("no playable files in this item")
            return
        self.now = {"doc": doc, "tracks": tracks, "title": show_title(doc, meta)}
        self.mpv.play([t["src"] for t in tracks], start)
        self.pending_seek = seek_to if seek_to and seek_to > 5 else None
        self.save_state(doc, start, self.pending_seek)
        self.say(f"playing {KIND_SHORT[doc['kind']]} {doc['identifier']}"
                 + (f" from {fmt_time(seek_to)}" if self.pending_seek else ""))

    def best_source(self, date_entry):
        items = date_entry["items"]
        local = [d for d in items if os.path.isdir(local_show_dir(d))]
        return sorted(local or items, key=source_rank)[0]

    def resume(self):
        st = self.state
        if st.get("last") == "radio" and st.get("radio"):
            s_ = next((x for x in stations() if x["key"] == st["radio"]), None)
            if s_:
                self.play_station(s_)
                return
        if not st.get("identifier"):
            self.say("nothing to resume")
            return
        doc = None
        if st.get("lp"):
            doc = next((d for d in album_docs() if d["identifier"] == st["identifier"]), None)
        try:
            for d in ([] if doc else year_docs(int(st["year"]), st.get("collection") or gd.DEFAULT_COLLECTION)):
                if d["identifier"] == st["identifier"]:
                    doc = d
        except Exception as e:
            self.say(f"archive.org: {e}")
            return
        if not doc:
            self.say("last show not found in index")
            return
        self.play_doc(doc, int(st.get("track") or 0), st.get("time"))

    def light_show(self):
        if deadviz is None:
            self.say("light show needs python3-numpy (apt install python3-numpy)", 8)
            return

        def title():
            st = self.mpv.status() if self.mpv.sock else None
            if not (st and self.now):
                return "stopped"
            t = self.now["tracks"][st["pos"]] if st["pos"] < len(self.now["tracks"]) else {"title": "?"}
            name = st.get("media_title") if self.now.get("radio") and st.get("media_title") not in (None, "") \
                and st["media_title"] not in t["src"] else t["title"]
            return f"{self.now['title']}  ·  {name}  {fmt_time(st['time'])}" + ("  ⏸" if st["paused"] else "")

        def on_key(ch):
            if ch == ord(" "):
                self.mpv.cmd("cycle", "pause")
            elif ch == ord("n"):
                self.mpv.cmd("playlist-next")
            elif ch == ord("b"):
                self.mpv.cmd("playlist-prev")
            elif ch == curses.KEY_RIGHT:
                self.mpv.cmd("seek", 10)
            elif ch == curses.KEY_LEFT:
                self.mpv.cmd("seek", -10)
            else:
                return False
            return True

        viz = deadviz.Viz(self.scr, title_fn=title, on_key=on_key, mode=self.viz_mode)
        try:
            viz.run()
        finally:
            self.viz_mode = viz.mode
            self.state["viz_mode"] = viz.mode
            self.write_state()
            self.scr.timeout(500)
            self.last_key = time.time()

    def download(self, doc):
        if os.path.isdir(local_show_dir(doc)) and any(
                n.endswith((".flac", ".mp3", ".ogg")) for n in os.listdir(local_show_dir(doc))):
            self.say("already on disk (re-fetch with gdarchive.py fetch to re-tag)")
            return
        os.makedirs(CACHE, exist_ok=True)
        log = os.path.join(CACHE, f"fetch-{doc['identifier']}.log")
        p = subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "gdarchive.py"),
                              "fetch", doc["identifier"]], stdin=subprocess.DEVNULL,
                             stdout=open(log, "w"), stderr=subprocess.STDOUT, start_new_session=True)
        self.fetches.append((doc["identifier"], p, log))
        self.say(f"fetching {doc['identifier']} (log: {log})", 6)

    # ---- drawing

    def draw(self):
        scr = self.scr
        scr.erase()
        h, w = scr.getmaxyx()
        lvl = self.stack[-1]
        crumb = " › ".join(l.title for l in self.stack)
        head = f" {crumb}"
        if lvl.filter:
            head += f"   [/{lvl.filter}]"
        self.put(0, 0, head[:w - 1].ljust(w - 1), curses.color_pair(1) | curses.A_BOLD)
        list_h = h - 5
        vis = lvl.visible()
        if lvl.cursor >= len(vis):
            lvl.cursor = max(0, len(vis) - 1)
        if lvl.cursor < lvl.top:
            lvl.top = lvl.cursor
        if lvl.cursor >= lvl.top + list_h:
            lvl.top = lvl.cursor - list_h + 1
        for row in range(list_h):
            idx = lvl.top + row
            if idx >= len(vis):
                break
            i, item = vis[idx]
            text = lvl.render(item, w - 2)
            hdr = isinstance(item, tuple) and item[0] == HDR
            attr = (curses.color_pair(1) | curses.A_BOLD) if hdr else (curses.A_REVERSE if idx == lvl.cursor else 0)
            if self.now and ((lvl.kind == "tracks" and self.now.get("doc") is lvl.ctx["doc"])
                             or (lvl.kind == "queue" and lvl.ctx.get("now") is self.now)):
                st = self.last_status
                if st and st["pos"] == i:
                    text = "▶" + text[1:]
                    attr |= curses.color_pair(2)
            self.put(1 + row, 0, text[:w - 1].ljust(w - 1), attr)
        if not vis:
            self.put(1, 2, "(nothing)" if lvl.items else "(empty)", curses.A_DIM)
        # status block
        y = h - 4
        self.put(y, 0, "─" * (w - 1), curses.A_DIM)
        st = self.last_status
        if self.now and st:
            t = self.now["tracks"][st["pos"]] if st["pos"] < len(self.now["tracks"]) else {"title": "?", "how": ""}
            state = "⏸" if st["paused"] else ("…" if st["buffering"] or st["time"] is None else "▶")
            rate = dac_rate()
            dac = f"  DAC {rate / 1000:g}k" if rate else ""
            if self.now.get("radio"):
                icy = st.get("media_title") or ""
                if not icy or icy in t["src"]:  # FLAC Icecast streams carry no ICY title; mpv falls back to the filename
                    icy = "(no now-playing metadata on this stream)"
                line1 = f" {state} {self.now['title']}  ·  {icy}"
                line2 = f"   {fmt_time(st['time'])}  {quality(st) or t['how']}{dac}"
            else:
                line1 = f" {state} {self.now['title']}  ·  {t['title']}"
                dur = st["dur"] or t.get("length")
                q = quality(st)
                how = t["how"].split()[0] + " " + q if q else t["how"]
                bar_w = max(10, w - 34 - len(dac) - len(how))
                frac = (st["time"] or 0) / dur if dur else 0
                bar = "=" * int(bar_w * min(1, frac)) + ">"
                line2 = (f"   {fmt_time(st['time'])} / {fmt_time(dur)}  [{bar[:bar_w].ljust(bar_w)}]  "
                         f"{st['pos'] + 1}/{st['count']}  {how}{dac}")
            self.put(y + 1, 0, line1[:w - 1], curses.color_pair(2))
            self.put(y + 2, 0, line2[:w - 1])
        else:
            self.put(y + 1, 0, " stopped", curses.A_DIM)
        active = [f for f in self.fetches if f[1].poll() is None]
        srch = lvl.ctx.get("search")
        if time.time() < self.msg_until and self.msg:
            self.put(y + 3, 0, f" {self.msg}"[:w - 1], curses.color_pair(3))
        elif srch and not srch.done:
            self.put(y + 3, 0, f" searching: {srch.checked}/{srch.total or '?'} dates checked, "
                               f"{len(srch.results)} shows so far"[:w - 1], curses.color_pair(3))
        elif srch and srch.error:
            self.put(y + 3, 0, f" search failed: {srch.error}"[:w - 1], curses.color_pair(3))
        else:
            if lvl.kind == "songs":
                keys = " ↵ open at song  p play from song  a all versions  ␣ pause  n/b trk  / filter  d fetch  q quit"
            elif lvl.kind == "radio":
                keys = " ↵/p tune  i probe (codec, rate, now playing)  ␣ pause  s stop  h back  q quit (music stays)"
            elif lvl.kind == "tears":
                keys = " ↵/p find every version of this song (one row per show)  h back  q quit (music stays)"
            elif lvl.kind == "memory":
                keys = " ↵/p play this part  a play the whole evening in order  ␣ pause  n/b trk  h back  q quit (music stays)"
            elif lvl.kind == "history":
                keys = " ↵/p play it again  / filter  ␣ pause  h back  q quit (music stays)"
            elif lvl.kind == "home":
                keys = " ↵ open  p play  w now playing  c radio  f song  g goto  r resume  v show  q quit (music stays)  Q stop & quit"
            elif lvl.kind == "queue":
                keys = " ↵/p jump to track  ␣ pause  n/b trk  ←→ seek  / filter  h back  q quit (music stays)  Q quit and stop"
            else:
                keys = " ↵ open  p play  ␣ pause  n/b trk  ←→ seek  / filter  f song  g goto  v show  d fetch  r resume  q quit (music stays)  Q stop & quit"
            if active:
                keys = f" ↓{len(active)} fetching " + keys
            self.put(y + 3, 0, keys[:w - 1], curses.A_DIM)
        scr.refresh()

    def put(self, y, x, text, attr=0):
        try:
            self.scr.addstr(y, x, text, attr)
        except curses.error:
            pass

    # ---- input

    def prompt(self, label):
        h, w = self.scr.getmaxyx()
        curses.curs_set(1)
        curses.echo()
        self.scr.timeout(-1)
        self.put(h - 1, 0, " " * (w - 1))
        self.put(h - 1, 0, f" {label}: ")
        self.scr.refresh()
        try:
            s = self.scr.getstr(h - 1, len(label) + 3, 60).decode(errors="replace").strip()
        except (curses.error, KeyboardInterrupt):
            s = ""
        curses.noecho()
        curses.curs_set(0)
        self.scr.timeout(500)
        return s

    def current(self):
        lvl = self.stack[-1]
        vis = lvl.visible()
        return (vis[lvl.cursor][0], vis[lvl.cursor][1]) if vis else (None, None)

    def open(self):
        lvl = self.stack[-1]
        i, item = self.current()
        if item is None:
            return
        if lvl.kind == "home" and isinstance(item, tuple) and item[0] == HDR:
            return
        elif lvl.kind == "home" and item == RADIO:
            self.push_radio(self.state.get("radio"))
        elif lvl.kind == "home" and item == YEARS_GD:
            self.push_years(gd.DEFAULT_COLLECTION)
        elif lvl.kind == "home" and item == JGB:
            self.push_years("JGB")
        elif lvl.kind == "home" and item in ALBUMS:
            self.push_albums(item)
        elif lvl.kind == "home" and item == TEARS:
            self.push_tears()
        elif lvl.kind == "home" and isinstance(item, tuple) and item[0] == MEMORY:
            self.push_memory(item[1])
        elif lvl.kind == "memory":
            self.play_memory(lvl, item)
        elif lvl.kind == "home" and item == HIST:
            self.push_history()
        elif lvl.kind == "history":
            self.play_history(item)
        elif lvl.kind == "home" and item == QUEUE:
            self.push_queue()
        elif lvl.kind == "home" and item == RANDOM:
            self.random_show()
        elif lvl.kind == "home" and item == RAIN:
            self.rain()
        elif lvl.kind == "queue":
            self.mpv.cmd("playlist-play-index", i)
        elif lvl.kind == "tears":
            self.push_songs(item[0], item[1])
        elif lvl.kind == "albums" and item.get("clip"):
            self.play_clip(item)
        elif lvl.kind == "albums":
            self.push_tracks(item)
        elif lvl.kind == "years":
            coll = lvl.ctx["collection"]
            same = str(item) == str(self.state.get("year")) and \
                (self.state.get("collection") or gd.DEFAULT_COLLECTION) == coll
            self.push_dates(item, self.state.get("date") if same else None, coll)
        elif lvl.kind == "radio":
            self.play_station(item)
        elif lvl.kind == "dates":
            self.push_sources(item)
        elif lvl.kind == "sources":
            self.push_tracks(item)
        elif lvl.kind == "tracks":
            self.play_doc(lvl.ctx["doc"], i)
        elif lvl.kind == "songs":
            self.loading(f"loading {item['identifier']}...")
            try:
                idx, _, _ = self.song_track_index(item, lvl.ctx["song"])
            except Exception as e:
                self.say(f"metadata: {e}")
                return
            self.push_tracks(item, idx)

    def play_here(self):
        lvl = self.stack[-1]
        i, item = self.current()
        if item is None:
            return
        if lvl.kind == "home" and isinstance(item, tuple) and item[0] == HDR:
            return
        elif lvl.kind == "home" and item == RADIO:
            self.push_radio(self.state.get("radio"))
        elif lvl.kind == "home" and item == YEARS_GD:
            self.push_years(gd.DEFAULT_COLLECTION)
        elif lvl.kind == "home" and item == JGB:
            self.push_years("JGB")
        elif lvl.kind == "home" and item in ALBUMS:
            self.push_albums(item)
        elif lvl.kind == "home" and item == TEARS:
            self.push_tears()
        elif lvl.kind == "home" and isinstance(item, tuple) and item[0] == MEMORY:
            self.push_memory(item[1])
        elif lvl.kind == "memory":
            self.play_memory(lvl, item)
        elif lvl.kind == "home" and item == HIST:
            self.push_history()
        elif lvl.kind == "history":
            self.play_history(item)
        elif lvl.kind == "home" and item == QUEUE:
            self.push_queue()
        elif lvl.kind == "home" and item == RANDOM:
            self.random_show()
        elif lvl.kind == "home" and item == RAIN:
            self.rain()
        elif lvl.kind == "queue":
            self.mpv.cmd("playlist-play-index", i)
        elif lvl.kind == "tears":
            self.push_songs(item[0], item[1])
        elif lvl.kind == "albums" and item.get("clip"):
            self.play_clip(item)
        elif lvl.kind == "albums":
            self.play_doc(item)
        elif lvl.kind == "years":
            self.push_dates(item, None, lvl.ctx["collection"])
        elif lvl.kind == "radio":
            self.play_station(item)
        elif lvl.kind == "dates":
            self.play_doc(self.best_source(item))
        elif lvl.kind == "sources":
            self.play_doc(item)
        elif lvl.kind == "tracks":
            self.play_doc(lvl.ctx["doc"], i)
        elif lvl.kind == "songs":
            try:
                idx, _, _ = self.song_track_index(item, lvl.ctx["song"])
            except Exception as e:
                self.say(f"metadata: {e}")
                return
            self.play_doc(item, idx)

    def find_song(self):
        song = self.prompt("song")
        if song:
            self.push_songs(song)

    def goto(self):
        s = self.prompt("go to (YYYY or YYYY-MM-DD)")
        if not s:
            return
        year = s[:4]
        coll = self.collection()
        if year.isdigit() and int(year) not in COLLECTIONS[coll]["years"]:
            coll = next((c for c, v in COLLECTIONS.items() if int(year) in v["years"]), None)
        if not year.isdigit() or not coll:
            self.say("year must be 1965-1995 (Dead) or 1996 on (JGB)")
            return
        del self.stack[1:]
        self.stack[0].cursor = self.stack[0].items.index(JGB if coll != gd.DEFAULT_COLLECTION else YEARS_GD)
        self.push_years(coll)
        self.stack[-1].cursor = self.stack[-1].items.index(int(year))
        self.push_dates(int(year), s if len(s) == 10 else None, coll)

    @staticmethod
    def skip_headers(lvl, cur, step):
        vis = lvl.visible()
        while 0 <= cur < len(vis) and isinstance(vis[cur][1], tuple) and vis[cur][1][0] == HDR:
            cur += step
        return min(max(cur, 0), max(0, len(vis) - 1)) if not (0 <= cur < len(vis)) else cur

    def collection(self):
        """The archive.org collection the current view belongs to."""
        for lvl in reversed(self.stack):
            if lvl.ctx and lvl.ctx.get("collection"):
                return lvl.ctx["collection"]
        return gd.DEFAULT_COLLECTION

    def handle(self, ch):
        lvl = self.stack[-1]
        vis_n = len(lvl.visible())
        playing = self.last_status is not None
        if ch == ord("q"):
            self.detach = self.last_status is not None   # something is loaded: leave it playing
            return False
        if ch == ord("Q"):
            return False
        if ch in (curses.KEY_DOWN, ord("j")):
            lvl.cursor = self.skip_headers(lvl, min(lvl.cursor + 1, max(0, vis_n - 1)), 1)
        elif ch in (curses.KEY_UP, ord("k")):
            lvl.cursor = self.skip_headers(lvl, max(lvl.cursor - 1, 0), -1)
        elif ch == curses.KEY_NPAGE:
            lvl.cursor = min(lvl.cursor + 20, max(0, vis_n - 1))
        elif ch == curses.KEY_PPAGE:
            lvl.cursor = max(lvl.cursor - 20, 0)
        elif ch in (curses.KEY_HOME, ord("^")):
            lvl.cursor = 0
        elif ch in (curses.KEY_END, ord("$")):
            lvl.cursor = max(0, vis_n - 1)
        elif ch in (curses.KEY_ENTER, 10, 13, ord("l")):
            self.open()
        elif ch in (curses.KEY_BACKSPACE, 127, 8, ord("h")):
            self.pop()
        elif ch == curses.KEY_LEFT:
            if playing:
                self.mpv.cmd("seek", -10)
            else:
                self.pop()
        elif ch == curses.KEY_RIGHT:
            if playing:
                self.mpv.cmd("seek", 10)
            else:
                self.open()
        elif ch == ord("<"):
            self.mpv.cmd("seek", -60)
        elif ch == ord(">"):
            self.mpv.cmd("seek", 60)
        elif ch == ord(" "):
            self.mpv.cmd("cycle", "pause")
        elif ch == ord("n"):
            self.mpv.cmd("playlist-next")
        elif ch == ord("b"):
            self.mpv.cmd("playlist-prev")
        elif ch == ord("s"):
            self.mpv.cmd("stop")
            self.now = None
        elif ch == ord("p"):
            self.play_here()
        elif ch == ord("r"):
            self.resume()
        elif ch == ord("w"):
            if lvl.kind != "queue":
                self.push_queue()
        elif ch == ord("g"):
            self.goto()
        elif ch == ord("f"):
            self.find_song()
        elif ch == ord("c"):
            if lvl.kind != "radio":
                self.push_radio(self.state.get("radio"))
        elif ch == ord("v"):
            self.light_show()
        elif ch == ord("i") and lvl.kind == "radio":
            i, item = self.current()
            if item:
                self.probe_station(item)
        elif ch == ord("a") and lvl.kind == "songs":
            self.play_all_versions(lvl)
        elif ch == ord("a") and lvl.kind == "memory":
            self.play_memory(lvl)
        elif ch == ord("/"):
            lvl.filter = self.prompt("filter")
            lvl.cursor = 0
        elif ch == 27:  # Esc clears filter
            lvl.filter = ""
        elif ch == ord("d"):
            i, item = self.current()
            if lvl.kind in ("sources", "songs", "albums") and item:
                self.download(item)
            elif lvl.kind == "tracks":
                self.download(lvl.ctx["doc"])
            elif lvl.kind == "dates" and item:
                self.download(self.best_source(item))
            else:
                self.say("d works on a date, source or track list")
        elif ch == curses.KEY_RESIZE:
            pass
        return True

    def run(self):
        try:
            self.mpv.start()
            if self.mpv.adopted:
                self.adopt_playlist()
        except FileNotFoundError:
            self.say("mpv is not installed (apt install mpv / brew install mpv)", 60)
        except Exception as e:
            self.say(f"mpv failed to start: {e}", 30)
        while True:
            st = self.mpv.status() if self.mpv.sock else None
            if st and self.now and self.now.get("rain") and st["count"] == len(self.now["tracks"]) \
                    and st["pos"] >= st["count"] - 1 and not st["paused"]:
                self.rain_more()
                st = self.mpv.status()
            if st and (not self.now or st["count"] != len(self.now["tracks"])):
                # something else loaded a playlist into our mpv (restore-playlist.py, a hand-typed
                # loadfile): describe it the same way an adopted mpv is described
                self.adopt_playlist()
            if st and self.pending_seek is not None and st["time"] is not None:
                self.mpv.cmd("seek", self.pending_seek, "absolute")
                self.pending_seek = None
            if st and self.now and self.now.get("doc") and st["pos"] != (self.last_status or {}).get("pos"):
                self.save_state(self.now["doc"], st["pos"])
            key = (id(self.now), st["pos"]) if st and self.now else None
            if key and key != self.logged and st["pos"] < len(self.now["tracks"]) and not st["paused"]:
                self.last_status = st
                self.log_history(self.now["tracks"][st["pos"]])
                self.logged = key
            self.last_status = st
            self.draw()
            try:
                ch = self.scr.getch()
            except KeyboardInterrupt:
                break
            if ch == -1:
                if (SCREENSAVER_SECS and st and not st["paused"] and deadviz
                        and time.time() - self.last_key > SCREENSAVER_SECS):
                    self.light_show()
                continue
            self.last_key = time.time()
            try:
                if not self.handle(ch):
                    break
            except Exception as e:  # keep the UI alive on a bad API response
                self.say(f"error: {e}", 8)
        self.save_position()
        if self.detach:
            if self.mpv.sock:
                self.mpv.sock.close()
            print("music left playing; start again to adopt it, or quit it with:")
            print(f"  echo '{{\"command\":[\"quit\"]}}' | socat - UNIX-CONNECT:{self.mpv.path}")
        else:
            self.mpv.stop()
        return [f for f in self.fetches if f[1].poll() is None]


def main():
    if os.environ.get("TERM", "").startswith("tmux"):
        os.environ.setdefault("ESCDELAY", "25")
    still = curses.wrapper(lambda scr: App(scr).run())
    for ident, p, log in still:
        print(f"still fetching {ident} in the background; log: {log}")


if __name__ == "__main__":
    main()
