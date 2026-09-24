#!/usr/bin/env python3
"""May-The_Lord_Poseidon-Convey-You.py (formerly deadtui.py) - browse and play the archive.org Grateful Dead collection in a terminal.

Stock python3 (curses) + mpv. No pip installs. Search/metadata code is reused
from gdarchive.py in the same directory. Runs on Linux and macOS (see README:
brew install mpv; numpy for the light show, mutagen for tagging fetched shows;
the DAC rate readout is Linux-only and simply stays blank elsewhere).

Levels:  home  >  years  >  dates in a year  >  sources for a date  >  tracks
The home screen is sectioned: Now (▶ Now playing, 🎲 Random show, 📅 This day), The Dead
(the years, 🚌 Tours, Dark Star, Not Fade Away, Seastones, Rain and Snow, Tears, JGB),
Not Dead (classical radio, 📻 On the air, Firesign, Jokes), Everything (History,
★ Bookmarks, Stats). Section headers are skipped by the cursor.
`📅 This day`: every Dead show played on today's month and day, any year (one query,
the 31 dates OR'd; TOUR_LIST-style dates list, so ↵ sources, p best source, d fetch).
`🚌 Tours` (TOUR_LIST): the famous runs; ↵ opens one night by night under a random-night
row and a whole-run row (every night's best source as one playlist, in order); p on a
tour plays a random night. `📻 On the air` (ONAIR_DOCS): the one Grateful Dead Hour
archive.org holds (#242, 1993), the KFOG New Year's Eve 1990 broadcast, two Dead to the
World nights. `★ Bookmarks`: * anywhere pins what is playing at the second it is at (or,
stopped, the show under the cursor) to ~/.cache/deadtui/bookmarks.json; ↵ plays from
there, x unpins. `Stats`: history.jsonl added up (tracks, shows, hours, most played songs
and years, the longest Dark Star heard). `i` (outside the radio list) shows the taper's
notes and the reviews of the show under the cursor or the one playing.
Home rows in detail: `♪ Classical radio` (radio.py's lossless stations);
`Firesign Theatre` and `Jokes` (LPs, one 24-bit FLAC per side, from library vinyl
transfers); `Tears` (the weepers: ↵ on a song runs the song search across every
show); `History` (every track played, newest first, from
~/.cache/deadtui/history.jsonl; ↵ plays it again); `JGB`: Jerry Garcia Band and
the rest of Jerry's own bands, 1970-1995 (Legion of Mary, Garcia/Saunders,
Reconstruction, the acoustic band). archive.org has no collection for them any
more (the estate had it taken down); the tapes sit in taperssection under creator
"Jerry Garcia", which gdarchive.py's "JerryGarcia" pseudo-collection searches.
JGB shows fetched with d land in dead/jgb/<year>/ and play from disk like Dead
shows. The years overlap the Dead's, so g stays in whichever is open.
`Jokes` starts with CLIPS: moments inside shows played from an offset, such as the
"Penalized for Your Dependence on Batteries (or a Well Deserved Break)" at 7:42 of
Mission in the Rain, Boston 6/12/76.
`🎲 Random show` picks a year and a night in it (rated 4+ when the year has such),
opens it, and plays the best source. `★ Dark Star` and `♥ Not Fade Away` (NIGHTS) list the
famous ones (DARK_STARS, NFA_NIGHTS: date and why; ↵ plays that night from the song on, best
source that really has it, on disk first) below a row that plays a random one, then another,
and another, and a row that runs the song search for every version. `≋ Seastones` lists every 1974 night archive.org
has a Phil Lesh and Ned Lagin set for (SEASTONES_NIGHTS, Miami 6/23 to Winterland 10/20; ↵ plays
that night from the Seastones set on, whatever the tapers called it: Seastones, Phil & Ned,
Phil 'n' Ned...), a random-one-after-another row, and the 1975-06-06 Dominican College evening
of it with Jerry and Mickey (SEASTONES_DOCS). `☔ Rain and Snow` plays weather and water
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
  /             filter list     g         go to YYYY or YYYY-MM-DD (Dead or JGB, whichever is open)
  f             find a song across all years (one row per show date, best source);
                there: Enter opens the show at that track, p plays from it,
                a plays every version in date order as one playlist
  d             download this show (poseidon gdarchive fetch <id>, in the background)
  i             the taper's notes and the reviews of this show (source, lineage, setlist,
                every review with its stars); in the radio list, probe the station
  *             pin a bookmark: what is playing at this second, or the show under the cursor
  c             classical radio (radio.py's stations, lossless first); also the first
                entry of the top-level list. Its first row tunes a random station and
                parks the cursor on it. i probes a station.
  r             resume the last thing played, at the position it was at
  w             what's playing: the whole current playlist (also the first top-level
                row while something plays); ▶ marks the track, Enter jumps to one
  v             light show (deadviz.py): patterns driven by an FFT of what the
                Rotel is playing. Inside it v steps to the next of 24 modes
                (bars, plasma, scope, rings, waterfall, fire, rain, stars, wave,
                radial, particles, meters, spiral, life, poseidon, enik, cyclops, convey, athena, althea,
                scylla, sleestak, stealie, wall), V steps back, 1-9/0
                pick the first ten, space/n/b/←/→ still control playback,
                ↑/↓ set the waterfall's direction, Esc (or any other key) returns.
                Also starts by itself after SCREENSAVER_SECS idle while playing.
  V             stop the light show starting by itself (V again lets it; the setting
                is remembered). v still opens it by hand.
                While something plays, the panel is held awake (the X idle counter is put
                back with xset, plus a logind idle inhibitor) for as long as the light
                show is on the screen, and with the list on the screen until
                DISPLAY_SLEEP_SECS past the last key; after that the screen sleeps as the
                desktop says, on its own settings, which are never touched. 0 disables
                and hands the screen back.
  t             sleep timer: minutes, or 'track' (the end of this track) or 'show' (the end
                of the playlist); the gain fades over the last minute, then playback pauses
                and the gain comes back. 0 cancels. The status line shows 💤 and what is left.
  R             the phone remote: a page on the LAN (http://<this machine>:8402/) with
                play, pause, next, seek, volume, mute, sleep, stop and the queue; R again
                turns it off; the setting is remembered. `poseidon remote` serves the same
                page for a player started without the TUI.
  s             stop            q         quit; the music keeps playing and the next
                                          start adopts it (see below)
                                Q         quit and stop the music

The command line, no TUI (`poseidon play ...`, the next TUI start adopts the player):
  poseidon play 1977-05-08 [--song "Morning Dew"] [--source aud] [--track 3] [--volume 60]
  poseidon play random                  # a night rated 4+ from a random year, best source
  poseidon play <identifier>            # any archive.org item
  poseidon play radio naim              # a station from radio.py; radio random picks one
  poseidon play stop | pause | next | prev | status
An mpv started this way is in its own session, so cron can run `poseidon play random`
at 7 and `poseidon play stop` at 8 and the shell that started it may go away.

If an mpv from an earlier run is still on the socket (the TUI died without q: closed
terminal, hangup, crash), it is adopted rather than replaced: its playlist is read
back, shows on disk and archive.org URLs are recognised, and the status line, n/b,
seek and q all work on it as if this instance had started it.

On quit the show, track and position (or the radio station) are saved to
~/.cache/deadtui/state.json; the next start re-opens that view with the
cursor on the track, and r resumes playback from the saved position. A built
playlist (Rain and Snow, a Dark Star stream, every version of
a song, an adopted list) is saved whole, titles and sources and position, and r
rebuilds it, refilling included.
Search-index and metadata responses are cached under ~/.cache/deadtui/ so
re-visiting a year is instant. Delete that directory to refresh.
"""

import argparse
import concurrent.futures as cf
import curses
import html
import http.server
import random
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import textwrap
import threading
import time
import urllib.parse
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdarchive as gd  # noqa: E402
import poseidon  # noqa: E402
import radio  # noqa: E402
try:
    import deadviz  # noqa: E402
except ImportError:  # python3-numpy missing
    deadviz = None

CACHE = os.path.expanduser("~/.cache/deadtui")
STATE = os.path.join(CACHE, "state.json")
HISTORY = os.path.join(CACHE, "history.jsonl")   # one line per track played, newest last
BOOKMARKS_FILE = os.path.join(CACHE, "bookmarks.json")   # a list, newest first
HISTORY_ROWS = 500
THISDAY = "thisday"    # sentinel: every show played on today's month and day, 1965-1995
TOURS = "tours"        # sentinel: the famous runs, night by night, a random night, or the whole run
TOUR_LIST = [          # (name, first date, last date, why), oldest first
    ("Fillmore West, Feb-Mar 1969", "1969-02-27", "1969-03-02", "the four nights Live/Dead was cut from"),
    ("Fillmore East, April 1971", "1971-04-25", "1971-04-29", "the closing run, five nights; Ladies and Gentlemen"),
    ("Europe '72", "1972-04-07", "1972-05-26", "Wembley to the Lyceum, 22 shows, the Bozos and the Bolos"),
    ("Wall of Sound, 1974", "1974-03-23", "1974-10-20", "the Cow Palace debut to the Winterland farewell, under the Wall"),
    ("Winterland, October 1974", "1974-10-16", "1974-10-20", "the five farewell nights before the hiatus, The Grateful Dead Movie"),
    ("May '77", "1977-05-01", "1977-06-09", "New Haven to Winterland: Barton Hall, Buffalo, Hartford, Chicago, the Palladium"),
    ("Red Rocks '78", "1978-07-07", "1978-07-08", "two nights in the rocks"),
    ("Egypt '78", "1978-09-14", "1978-09-16", "three nights at the Sphinx, Hamza El Din, the lunar eclipse"),
    ("Closing of Winterland", "1978-12-30", "1978-12-31", "the last two nights, New Year's Eve with the Blues Brothers opening"),
    ("Warfield and Radio City, 1980", "1980-09-25", "1980-10-31", "the fifteenth anniversary: acoustic set, two electric, Reckoning and Dead Set"),
    ("Greek Theatre '85", "1985-06-14", "1985-06-16", "the twentieth anniversary weekend in Berkeley"),
    ("Alpine Valley '89", "1989-07-17", "1989-07-19", "three nights in Wisconsin, the summer before Hampton"),
    ("Hampton '89, the Warlocks", "1989-10-08", "1989-10-09", "billed as Formerly The Warlocks; Dark Star and Attics come back"),
    ("Spring '90", "1990-03-14", "1990-04-03", "Capital Centre to the Omni, Brent's last spring; Without a Net"),
    ("Europe '90", "1990-10-13", "1990-11-01", "Stockholm to Wembley, the first tour with Vince and Bruce"),
]
ONAIR = "onair"        # sentinel: the Dead on the radio: the Grateful Dead Hour, Dead to the World, the KFOG NYE broadcast
ONAIR_DOCS = [         # archive.org has one Grateful Dead Hour episode and a few of David Gans's KPFA nights; ↵ plays the item
    {"identifier": "grateful-dead-hour-242-david-gans-1993-kpfa", "date": "1993-05-01", "collection": ["radioprograms"],
     "kind": "other", "onair": True, "title": "Grateful Dead Hour #242, May 1993",
     "note": "David Gans on KPFA. An hour of Dark Stars, in two parts."},
    {"identifier": "grateful-dead-nye-1990-oakland-coliseum-kfog", "date": "1990-12-31", "collection": ["radioprograms"],
     "kind": "other", "onair": True, "title": "New Year's Eve 1990, the KFOG broadcast",
     "note": "Oakland Coliseum live on FM, David Gans and Ken Nordine announcing. Lossless, forty tracks."},
    {"identifier": "deadtotheworldkpfa", "date": "2020-01-14", "collection": ["radioprograms"],
     "kind": "other", "onair": True, "title": "Dead to the World, January 2020",
     "note": "Two Wednesday nights of David Gans's KPFA show, two hours each."},
    {"identifier": "dead-to-the-world-david-gans-kpfa-feb.-2022", "date": "2022-02-26", "collection": ["radioprograms"],
     "kind": "other", "onair": True, "title": "Dead to the World marathon, February 2022",
     "note": "KPFA's annual marathon night with David Gans and Tim Lynch."},
]
BOOKMARKS = "bookmarks"  # sentinel: shows and moments pinned with *
STATS = "stats"          # sentinel: what History adds up to
CACHE_TTL = 7 * 86400
YEARS = list(range(1965, 1996))
JGB = "jgb"      # sentinel entry at the bottom of the years list
FIRESIGN = "firesign"  # sentinel below JGB: the Firesign Theatre LPs
JOKES = "jokes"        # sentinel: other comedy LPs
TEARS = "tears"        # sentinel: the weepers, each row a song search
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
DARKSTAR = "darkstar"  # sentinel: the Dark Star section
DARK_STARS = [         # (date, why), oldest first; ↵ plays that night from Dark Star on
    ("1969-02-27", "Fillmore West. The Live/Dead one."),
    ("1970-02-13", "Fillmore East, late show. Dark Star > Other One > Lovelight, then goodnight."),
    ("1971-10-31", "Ohio Theatre, Columbus. Halloween, the Keith Godchaux era begins."),
    ("1972-04-08", "Wembley. The Europe '72 opener's Dark Star."),
    ("1972-05-11", "Rotterdam. Forty minutes; the one people mean by 'the long one'."),
    ("1972-07-18", "Roosevelt Stadium, Jersey City. Dark Star > Comes a Time."),
    ("1972-08-27", "Veneta, Oregon. The Sunshine Daydream field."),
    ("1972-09-21", "The Spectrum, Philadelphia. Dark Star > Morning Dew."),
    ("1973-11-11", "Winterland. Dark Star > Eyes of the World, the 1973 sound at its best."),
    ("1973-12-06", "Cleveland. The Dark Star > Eyes that ends with the wonderful jam."),
    ("1974-02-24", "Winterland. Wall of Sound spring."),
    ("1974-06-23", "Miami. Dark Star > Spanish Jam > U.S. Blues."),
    ("1974-10-18", "Winterland, the farewell run before the hiatus. Dark Star > Morning Dew."),
    ("1989-10-09", "Hampton. The Warlocks. Dark Star returns after five years."),
    ("1990-03-29", "Nassau Coliseum, with Branford Marsalis. The last great one."),
]
NOTFADE = "notfade"    # sentinel: the Not Fade Away section
NFA_NIGHTS = [         # (date, why), oldest first; ↵ plays that night from Not Fade Away on
    ("1970-02-14", "Fillmore East, the night after the Dark Star. Not Fade Away > Mason's Children > Caution."),
    ("1970-05-15", "Fillmore East, late show. St. Stephen > Not Fade Away > Lovelight."),
    ("1971-04-06", "Manhattan Center. Not Fade Away > Goin' Down the Road > Not Fade Away, the 1971 shape of it."),
    ("1971-04-28", "Fillmore East, the closing run. St. Stephen > Not Fade Away > Goin' Down the Road > Not Fade Away."),
    ("1972-04-14", "Tivoli, Copenhagen. Europe '72's first week. Not Fade Away > Goin' Down the Road > Not Fade Away."),
    ("1972-05-04", "L'Olympia, Paris. Goin' Down the Road > Not Fade Away, then One More Saturday Night."),
    ("1972-05-26", "Lyceum, London, the last night of Europe '72. Not Fade Away > Goin' Down the Road > Not Fade Away."),
    ("1973-06-10", "RFK Stadium, the day with the Allman Brothers. Not Fade Away > Goin' Down the Road > Drums."),
    ("1974-10-20", "Winterland, the last night before the hiatus. Drums > Not Fade Away > Drums > The Other One."),
    ("1977-05-08", "Barton Hall, Cornell. St. Stephen > Not Fade Away > St. Stephen > Morning Dew."),
    ("1978-01-22", "MacArthur Court, Eugene, the Close Encounters night. St. Stephen > Not Fade Away."),
    ("1979-10-27", "Cape Cod Coliseum. Drums with Phil > Not Fade Away > Black Peter."),
]
# The song sections: home row -> (menu title, icon, song, nights). One menu, two songs.
NIGHTS = {DARKSTAR: ("★ Dark Star", "★", "Dark Star", DARK_STARS),
          NOTFADE: ("♥ Not Fade Away", "♥", "Not Fade Away", NFA_NIGHTS)}
SEASTONES = "seastones"  # sentinel: Phil and Ned between sets, 1974, the experiments
# What the tapers call the set. Any of these marks the track; norm() drops the punctuation.
SEASTONES_TITLES = ["Seastones", "Phil & Ned", "Phil and Ned", "Phil 'n' Ned", "Ned & Phil", "Phil Lesh and Ned Lagin"]
SEASTONES_NIGHTS = [  # (date, where), oldest first: every 1974 night archive.org has the set for
    ("1974-06-23", "Jai-Alai Fronton, Miami. The first one: Phil and Ned alone with the Wall of Sound."),
    ("1974-06-26", "Providence Civic Center."),
    ("1974-06-28", "Boston Garden."),
    ("1974-06-30", "Springfield Civic Center."),
    ("1974-07-19", "Selland Arena, Fresno."),
    ("1974-07-21", "Hollywood Bowl."),
    ("1974-07-27", "Roanoke Civic Center."),
    ("1974-07-31", "Dillon Stadium, Hartford."),
    ("1974-08-04", "Philadelphia Civic Center, night one."),
    ("1974-08-05", "Philadelphia Civic Center, night two."),
    ("1974-08-06", "Roosevelt Stadium, Jersey City."),
    ("1974-09-10", "Alexandra Palace, London, night one."),
    ("1974-09-11", "Alexandra Palace, London. Jerry and Billy join in and it becomes a jam."),
    ("1974-09-14", "Olympiahalle, Munich."),
    ("1974-09-18", "Parc des Expositions, Dijon."),
    ("1974-09-21", "Palais des Sports, Paris. The last night in Europe."),
    ("1974-10-16", "Winterland, the farewell run, night one. Jerry joins and it opens into space."),
    ("1974-10-17", "Winterland, night two."),
    ("1974-10-18", "Winterland, night three."),
    ("1974-10-19", "Winterland, night four."),
    ("1974-10-20", "Winterland, the last night before the hiatus, and of The Grateful Dead Movie."),
]
SEASTONES_DOCS = [  # whole evenings of it, outside the Dead collection; ↵ plays the item
    {"identifier": "jg75-06-06.013994.seastones.sbd.jim.sbeok.t-flac16", "date": "1975-06-06",
     "collection": ["taperssection"], "kind": "sbd", "seastones": True,
     "venue": "Angelico Hall, Dominican College, San Rafael",
     "note": "Jerry, Mickey, Phil and Ned, an hour of it in nine pieces. Soundboard."},
]
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
    "JerryGarcia": {"title": "Jerry Garcia Band", "years": list(range(1970, 1996))},
}
MENU_TITLES = {FIRESIGN: "Firesign Theatre", JOKES: "Jokes"}
# Clips: a moment inside a show, played from an offset. Listed at the top of Jokes.
CLIPS = [
    {"clip": True, "title": "Penalized for Your Dependence on Batteries (or a Well Deserved Break)",
     "note": "Dead stage banter, Boston Music Hall, at the end of Mission in the Rain",
     "identifier": "gd1976-06-12.fm.sbd.moore.berger.100328.flac16", "date": "1976-06-12", "collection": ["GratefulDead"],
     "kind": "sbd", "song": "Mission in the Rain", "start": 7 * 60 + 42},
]
# Tears: the weepers. ↵ runs the song search (same as f) so every version is a row.
# (song, collection) - the Dead never played Tears of Rage; the Garcia Band did, 1990 on.
TEARS_LIST = [
    ("Tears of Rage", "JerryGarcia"),
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
DISPLAY_SLEEP_SECS = 5400  # hold the panel awake this long past the last key, while playing; 0 disables
VOLUME_STEP = 5          # +/- move mpv's software volume by this much; m mutes. The level is remembered.
VOLUME_MAX = 100         # unity gain; mpv allows 130 but that only clips before the DAC
HW_PARAMS = "/proc/asound/R20/pcm0p/sub0/hw_params"
SLEEP_FADE = 60          # the sleep timer fades the gain to nothing over its last minute, then pauses
REMOTE_PORT = 8402       # the phone remote: R in the TUI, or poseidon remote; http://<this machine>:8402/

# Stations beyond radio.py's list go here: key: (name, url, nominal format, notes).
# KDFC lives in radio.py since 2026-09-20 (StreamTheWorld's KDFCFMAAC96 mount;
# the 256 kbps one is gone for good).
EXTRA_STATIONS = {}


def stations():
    out = []
    for key, (name, url, fmt, notes) in {**radio.STATIONS, **EXTRA_STATIONS}.items():
        out.append({"key": key, "name": name, "url": url, "fmt": fmt, "notes": notes})
    return out


def volume_tag(st):
    """'  muted' or '  vol 80%' for the status line; nothing at unity, the normal case."""
    if not st:
        return ""
    if st.get("mute"):
        return "  muted"
    v = st.get("volume")
    return f"  vol {v:g}%" if v is not None and round(v) != VOLUME_MAX else ""


def sleep_tag(sleep, st):
    """'  💤 12m', '  💤 end of track', '  💤 end of show', or '  💤 fading' for the status line."""
    if not sleep:
        return ""
    if sleep.get("fading"):
        return "  💤 fading"
    if sleep["mode"] == "minutes":
        left = max(0, int(sleep["at"] - time.time()))
        return f"  💤 {left // 60}m" if left >= 60 else f"  💤 {left}s"
    return "  💤 end of " + ("track" if sleep["mode"] == "track" else "show")


def lan_ip():
    """The address the phone should use: the interface that routes out, without sending a packet."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return socket.gethostname()


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


def day_docs(month_day):
    """Every Dead show played on this month and day, any year: one query, 31 dates OR'd together."""
    def fetch():
        dates = " OR ".join(f"{y}-{month_day}" for y in YEARS)
        args = SimpleNamespace(collection=gd.DEFAULT_COLLECTION, year=None, date=None, song=None, min_rating=None,
                               min_reviews=None, source="any", downloadable=False, query=f"date:({dates})",
                               sort="date asc", limit=5000)
        return gd.search(args)[1]
    return cached(f"day-{month_day}", fetch)


def tour_docs(tour):
    """The shows of a tour: the years' cached docs, cut to the tour's dates."""
    name, first, last, why = tour
    docs = []
    for year in range(int(first[:4]), int(last[:4]) + 1):
        docs.extend(d for d in (year_docs(year) or []) if first <= d["date"] <= last)
    return docs


def date_row(d, w):
    """One line for a show date: on-disk star, date, venue, then the source kinds, rating and count."""
    r = f"{d['rating']:.1f}" if d["rating"] else " - "
    loc = "*" if d["local"] else " "
    right = f" {d['kinds']:3} {r:>3} {len(d['items']):>3}"
    left = f"{loc} {d['date']}  {d['venue']}"
    return left[:max(0, w - len(right))].ljust(w - len(right)) + right


def strip_html(s):
    s = re.sub(r"<br\s*/?>|</div>|</p>", "\n", str(s or ""))
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).replace("\r", "")


def notes_lines(doc, meta, width):
    """The taper's notes and the reviews of an item, wrapped to the screen: what the item says about itself."""
    md = meta.get("metadata", {})
    out = []

    def para(label, text, indent="    "):
        text = strip_html(text).strip()
        if not text:
            return
        out.append(f"  {label}")
        for line in text.splitlines():
            out.extend(textwrap.wrap(line, width - len(indent), initial_indent=indent, subsequent_indent=indent) or [""])
        out.append("")
    head = f"{doc.get('date', '')} {gd.venue_of(md) or ''}".strip()
    cover = md.get("coverage")
    out.append(f"  {head}" + (f", {cover}" if cover and cover not in head else ""))
    out.append(f"  {doc['identifier']}")
    kind = KIND_SHORT.get(doc.get("kind"), doc.get("kind") or "")
    so = "stream only" if gd.is_stream_only(meta) else "downloadable"
    r = rating(doc)
    out.append(f"  {kind}  {so}  " + (f"{r:.2f} from {reviews(doc)} reviews" if r else "unrated"))
    out.append("")
    for key in ("source", "lineage", "taper", "transferer", "notes"):
        if md.get(key):
            para(key, md[key])
    if md.get("description"):
        para("setlist / description", md["description"])
    revs = meta.get("reviews") or []
    if revs:
        out.append(f"  ── {len(revs)} review{'s' if len(revs) != 1 else ''} ──")
        out.append("")
        for rv in sorted(revs, key=lambda x: x.get("reviewdate") or "", reverse=True):
            try:
                stars = "★" * int(float(rv.get("stars") or 0))
            except ValueError:
                stars = ""
            who = f"{stars} {rv.get('reviewer') or '?'}  {(rv.get('reviewdate') or '')[:10]}"
            title = strip_html(rv.get("reviewtitle")).strip()
            para(f"{who}  {title}" if title else who, rv.get("reviewbody"))
    return out


def load_bookmarks():
    try:
        with open(BOOKMARKS_FILE) as f:
            return list(json.load(f))
    except (OSError, ValueError):
        return []


def save_bookmarks(marks):
    os.makedirs(CACHE, exist_ok=True)
    with open(BOOKMARKS_FILE + ".tmp", "w") as f:
        json.dump(marks, f)
    os.replace(BOOKMARKS_FILE + ".tmp", BOOKMARKS_FILE)


def song_key_title(title):
    """A track title reduced to the song: the show prefix a built playlist puts in front
    ("1977-05-08 Barton Hall: Scarlet Begonias ->") and the segue marks come off."""
    t = str(title or "")
    if re.match(r"\d{4}-\d{2}-\d{2}.*?: ", t):
        t = t.split(": ", 1)[1]
    return re.sub(r"\s*(->|-->|>|~>|\*)\s*$", "", t).strip()


def song_key(title):
    return gd.norm(song_key_title(title))


def onair_doc(identifier):
    return next((d for d in ONAIR_DOCS if d["identifier"] == identifier), None)


SETTINGS = ("viz_mode", "volume", "remote", "screensaver")   # state keys that outlive what was last played


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def write_state(state):
    os.makedirs(CACHE, exist_ok=True)
    with open(STATE + ".tmp", "w") as f:
        json.dump(state, f)
    os.replace(STATE + ".tmp", STATE)


def show_state(old, doc, track_i, time_pos=None):
    """The state.json for a show at a track: the settings kept, everything else replaced."""
    kept = {k: old[k] for k in SETTINGS if k in old}
    return {**kept, "last": "show", "year": doc["date"][:4], "date": doc["date"],
            "identifier": doc["identifier"], "track": track_i, "time": time_pos,
            "collection": doc_collection(doc), "lp": doc.get("lp", False),
            "seastones": doc.get("seastones", False), "onair": doc.get("onair", False)}


def best_source(date_entry):
    """The source to play for a date: on disk first, then matrix > sbd > aud, rating, reviews."""
    items = date_entry["items"]
    local = [d for d in items if os.path.isdir(local_show_dir(d))]
    return sorted(local or items, key=source_rank)[0]


def append_history(rec):
    try:
        os.makedirs(CACHE, exist_ok=True)
        with open(HISTORY, "a") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass


def doc_collection(doc):
    c = gd.collection_of(doc)
    return c if c in COLLECTIONS else gd.DEFAULT_COLLECTION


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
    return os.path.join(gd.DEFAULT_DEST, gd.collection_dir(doc), date[:4],
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
    if doc.get("onair"):
        return doc.get("title") or md.get("title") or doc["identifier"]
    return f"{doc['date']} {gd.venue_of(md) or doc.get('venue') or ''}".strip()


def seastones_doc(identifier):
    return next((d for d in SEASTONES_DOCS if d["identifier"] == identifier), None)


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
        self.lock = threading.RLock()   # the remote's server thread shares the socket with the UI loop

    def start(self, detach=False):
        """Adopt the mpv on the socket, else start one. detach=True (the command line) puts it in its
        own session so it outlives the shell that started it; the next TUI adopts it."""
        if os.path.exists(self.path) and self.adopt():
            return
        if os.path.exists(self.path):
            os.unlink(self.path)
        self.proc = subprocess.Popen(
            ["mpv", "--no-video", "--no-terminal", "--idle=yes", "--force-window=no", "--audio-display=no",
             "--gapless-audio=yes", "--prefetch-playlist=yes", "--cache=yes", "--demuxer-max-bytes=64MiB",
             "--user-agent=" + gd.UA, "--input-ipc-server=" + self.path],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=detach)
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
        with self.lock:
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
                "params": self.get("audio-params") or {}, "bitrate": self.get("audio-bitrate"),
                "volume": self.get("volume"), "mute": bool(self.get("mute", False))}

    def set_volume(self, level):
        """Software gain, 0-100. 100 is unity: mpv would go to 130 but that only clips the DAC."""
        level = max(0, min(VOLUME_MAX, int(round(level))))
        self.cmd("set_property", "volume", level)
        return level

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


class KeepAwake(threading.Thread):
    """Hold the screen awake while the music plays, until DISPLAY_SLEEP_SECS past the last key.

    mpv runs here with --no-video --force-window=no, so its own stop-screensaver never
    fires: there is no window to inhibit from, and the desktop blanks the panel out from
    under the light show a few minutes in. The light show is the whole point of the
    player in a room with people in it, so hold the blankers off while something is
    playing and the light show is on the screen, for as long as it is on the screen.
    With the list on the screen instead, the hold lasts DISPLAY_SLEEP_SECS past the
    last key, so a player left open overnight with the show switched off (V) still
    lets the panel sleep.

    The window used to bound the light show too, counted from the last key, and that
    is how tiro's panel went dark mid-show again on 2026-09-23: the ordinary evening
    here is a show started over ssh, the light show coming on by itself three minutes
    later, and nobody touching a key for hours, so the hold lapsed 90 minutes in and
    the desktop blanked the panel five minutes after that. Keys inside the light show
    never reached the count either (deadviz reads them itself). A light show is on the
    screen because somebody put it there or because the music is playing; a dark
    panel is not what either of them wanted, and the music stopping releases the hold
    in any case.

    The hold is `xset s reset` on every poll, which is what mpv itself does on X11: it
    puts the server's idle counter back to zero, and on X everything that blanks a screen
    counts from that one counter -- the server's own screen saver, DPMS, and a userspace
    screensaver like xfce4-screensaver, which polls XScreenSaverQueryInfo and activates
    once the idle time passes its timeout. Nothing is switched off, so there is nothing
    to put back: a TUI that is killed without unwinding simply stops resetting the
    counter, and the desktop blanks on its own timeout as it always did.

    Switching the blankers off with `xset s off -dpms` and restoring whatever `xset q`
    reported is the obvious alternative, and it is what this did until 2026-09-19. It is
    worse in two ways. xfce4-screensaver does not ignore the X state, whatever its
    reputation: 4.18's listener sets the server's timeout itself and skips its check
    entirely while the state reads disabled, so `xset s off` switched the desktop's
    screensaver off rather than holding it for a while. And a TUI that was killed left it
    that way for good, with the next run saving the broken state as the one to restore --
    one kill disabled the screensaver on that machine until somebody noticed by hand.

    The reset goes to the display the panel is actually on, which find_display works out
    rather than reading $DISPLAY: this rig is driven from tmux on a tty, and such a
    session has no DISPLAY at all, so gating the reset on the environment meant it never
    ran on the one machine it was written for.

    A logind idle inhibitor (systemd-inhibit --what=idle) is held alongside it for
    whatever watches logind rather than X -- not for xfce4-screensaver, which does not
    honour it: it reported itself "not inhibited" with the inhibitor held. The child
    sleeps for DISPLAY_SLEEP_SECS rather than forever so a TUI that dies without
    unwinding cannot pin the inhibitor past the window it was asked for. Whatever is
    missing is skipped, and a machine with neither keeps the behaviour it had.

    This has to be a thread: light_show() blocks in deadviz's frame loop until a key is
    pressed, which is exactly the stretch the panel must stay lit for, so the UI loop is
    in no position to do the poking.
    """

    POLL = 15                                 # has to stay well under any blanker's timeout

    def __init__(self, mpv, idle_since, showing=lambda: False):
        super().__init__(daemon=True)
        self.mpv = mpv
        self.idle_since = idle_since          # callable: when the last key was pressed
        self.showing = showing                # callable: whether the light show is on the screen
        self.stopping = threading.Event()
        self.inhibitor = None
        self.display = self.find_display() if shutil.which("xset") else None
        self.can_inhibit = bool(shutil.which("systemd-inhibit"))

    def run(self):
        if not DISPLAY_SLEEP_SECS:
            return
        while not self.stopping.wait(self.POLL):
            try:
                if self.playing() and (self.showing() or time.time() - self.idle_since() < DISPLAY_SLEEP_SECS):
                    self.hold()
                else:
                    self.release()
            except Exception:
                pass                          # never take the player down over a screen saver
        try:
            self.release()
        except Exception:
            pass

    def stop(self):
        self.stopping.set()

    def playing(self):
        st = self.mpv.status() if self.mpv.sock else None
        return bool(st and not st["paused"])

    def hold(self):
        if self.display is None:              # X may have come up after the TUI did
            self.display = self.find_display() if shutil.which("xset") else None
        if self.display:
            self.xset(self.display, "s", "reset")
        if self.can_inhibit and (self.inhibitor is None or self.inhibitor.poll() is not None):
            self.inhibitor = subprocess.Popen(
                ["systemd-inhibit", "--what=idle", "--who=poseidon", "--why=the light show",
                 "sleep", str(DISPLAY_SLEEP_SECS)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def release(self):
        if self.inhibitor is not None:
            self.inhibitor.terminate()
            self.inhibitor = None

    @staticmethod
    def find_display():
        """The X display the panel is on, or None if there is no X to ask.

        Not simply $DISPLAY. The ordinary way this rig is driven is a tmux session on a
        tty (or over ssh) while the panel shows X, and such a session has no DISPLAY at
        all, so reading the environment said "no X here" and the reset never ran -- the
        counter climbed to the desktop's timeout and the panel blanked mid-show anyway.
        xset takes -display, and the server does not care which session asks, so find
        the display instead: logind knows which one the user's graphical session is on,
        and failing that the server is listening on a socket that names it.
        """
        if os.environ.get("DISPLAY"):
            return os.environ["DISPLAY"]
        if shutil.which("loginctl"):
            try:
                def ask(*args):
                    return subprocess.run(["loginctl", *args, "--value"], stdin=subprocess.DEVNULL,
                                          capture_output=True, text=True, timeout=5).stdout.strip()
                session = ask("show-user", str(os.getuid()), "-p", "Display")
                display = ask("show-session", session, "-p", "Display") if session else ""
                if display:
                    return display
            except Exception:
                pass
        try:
            socks = sorted(s for s in os.listdir("/tmp/.X11-unix") if re.fullmatch(r"X\d+", s))
        except OSError:
            socks = []
        return ":" + socks[0][1:] if socks else None

    @staticmethod
    def xset(display, *args):
        subprocess.run(["xset", "-display", display, *args], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)


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
        self.sleep = None         # the sleep timer: {"mode": "minutes"|"track"|"show", ...}
        self.remote = None        # the phone remote's server thread, when R has turned it on
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
        self.showing = False                  # the light show is on the screen
        self.awake = KeepAwake(self.mpv, lambda: self.last_key, lambda: self.showing)
        self.awake.start()
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
                        attr = sea                                  # the eyes, the colour of the water
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
        return load_state()

    SETTINGS = SETTINGS

    def save_state(self, doc, track_i, time_pos=None):
        self.state = show_state(self.state, doc, track_i, time_pos)
        self.write_state()

    def save_radio_state(self, key):
        self.state = {**self.state, "last": "radio", "radio": key}
        self.write_state()

    def write_state(self):
        write_state(self.state)

    def save_position(self):
        """Called on quit: remember where in the track we were. A built playlist (Rain and Snow,
        a Dark Star stream, every version of a song, an adopted list) has no
        single show behind it, so the queue itself is saved: titles, sources, position."""
        st = self.last_status
        if not (self.now and st):
            return
        if self.now.get("doc"):
            self.save_state(self.now["doc"], st["pos"], st.get("time"))
        elif not self.now.get("radio") and self.now.get("tracks"):
            self.state = {**self.state, "last": "queue",
                          "queue": {"title": self.now["title"], "pos": st["pos"], "time": st.get("time"),
                                    "rain": self.now.get("rain"),
                                    "tracks": [{k: t.get(k) for k in ("title", "src", "how", "length")}
                                               for t in self.now["tracks"]]}}
            self.write_state()

    def resume_queue(self):
        q = self.state.get("queue") or {}
        tracks = q.get("tracks") or []
        if not tracks:
            self.say("nothing to resume")
            return
        pos = min(int(q.get("pos") or 0), len(tracks) - 1)
        self.now = {"doc": None, "tracks": [dict(t) for t in tracks], "title": q.get("title") or "resumed playlist",
                    "rain": q.get("rain")}
        self.mpv.play([t["src"] for t in tracks], pos)
        self.pending_seek = q.get("time") if q.get("time") and q["time"] > 5 else None
        self.say(f"resuming {self.now['title']} at {pos + 1}/{len(tracks)}"
                 + (f" from {fmt_time(q['time'])}" if self.pending_seek else ""), 8)
        self.push_queue()

    def restore_view(self):
        """Re-open the view saved by the previous run: the last show at its track, or the radio list."""
        st = self.state
        try:
            if st.get("last") == "radio":
                self.push_radio(st.get("radio"))
                return
            if st.get("last") == "queue" and st.get("queue"):
                q = st["queue"]
                self.say(f"r resumes {q.get('title')} at {int(q.get('pos') or 0) + 1}/{len(q.get('tracks') or [])}", 10)
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
            if st.get("seastones"):
                doc = seastones_doc(st["identifier"])
                if doc:
                    self.push_seastones(doc)
                    self.push_tracks(doc, int(st.get("track") or 0))
                    if st.get("time"):
                        self.say(f"r resumes at {fmt_time(st['time'])}", 8)
                return
            if st.get("onair"):
                doc = onair_doc(st["identifier"])
                if doc:
                    self.push_onair(doc["identifier"])
                    self.push_tracks(doc, int(st.get("track") or 0))
                    if st.get("time"):
                        self.say(f"r resumes at {fmt_time(st['time'])}", 8)
                return
            year = int(st["year"])
            coll = st.get("collection") if st.get("collection") in COLLECTIONS else gd.DEFAULT_COLLECTION
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

    # ---- volume

    def volume(self, delta):
        """Nudge mpv's software volume by delta and remember the level for the next start."""
        if not self.mpv.sock:
            self.say("no player")
            return
        cur = self.mpv.get("volume")
        if cur is None:
            self.say("no player")
            return
        level = self.mpv.set_volume(cur + delta)
        if self.mpv.get("mute"):
            self.mpv.cmd("set_property", "mute", False)
        self.state["volume"] = level
        self.write_state()
        self.say(f"volume {level}%", 2)

    def toggle_mute(self):
        if not self.mpv.sock:
            self.say("no player")
            return
        self.mpv.cmd("cycle", "mute")
        self.say("muted" if self.mpv.get("mute") else f"volume {self.mpv.get('volume', VOLUME_MAX):g}%", 2)

    # ---- sleep timer

    def set_sleep(self, spec):
        """t: minutes, 'track' (the end of this track), 'show' (the end of the playlist); empty or 0 cancels.
        The gain fades over the last SLEEP_FADE seconds, then playback pauses and the gain comes back."""
        spec = (spec or "").strip().lower()
        if self.sleep and self.sleep.get("fading"):
            self.mpv.set_volume(self.sleep["vol"])
        if spec in ("", "0", "off", "cancel"):
            self.sleep = None
            self.say("sleep timer off", 3)
            return
        st = self.last_status
        vol = st["volume"] if st and st.get("volume") is not None else self.state.get("volume", VOLUME_MAX)
        if spec.startswith("t"):
            if not st:
                self.say("nothing is playing")
                return
            self.sleep = {"mode": "track", "pos": st["pos"], "vol": vol, "fading": False}
            self.say("💤 pausing at the end of this track", 4)
        elif spec.startswith("s"):
            if not st:
                self.say("nothing is playing")
                return
            self.sleep = {"mode": "show", "vol": vol, "fading": False}
            self.say("💤 pausing at the end of the playlist", 4)
        else:
            try:
                mins = float(spec.rstrip("m"))
            except ValueError:
                self.say("sleep: minutes, 'track' or 'show'")
                return
            self.sleep = {"mode": "minutes", "at": time.time() + mins * 60, "vol": vol, "fading": False}
            self.say(f"💤 pausing in {mins:g} minutes", 4)

    def tick_sleep(self, st):
        """Called every half second from the main loop with mpv's status (None when nothing is loaded)."""
        sl = self.sleep
        if not sl:
            return
        if st is None:                                               # the playlist ended, or s: done
            if sl.get("fading"):
                self.mpv.set_volume(sl["vol"])
            self.sleep = None
            return
        if sl["mode"] == "minutes":
            left = sl["at"] - time.time()
        elif sl["mode"] == "track":
            if st["pos"] != sl["pos"]:
                left = 0.0
            else:
                left = (st["dur"] - st["time"]) if st.get("dur") and st.get("time") is not None else SLEEP_FADE + 1
        else:
            if st["pos"] < st["count"] - 1:
                left = SLEEP_FADE + 1
            else:
                left = (st["dur"] - st["time"]) if st.get("dur") and st.get("time") is not None else SLEEP_FADE + 1
        if left <= 0:
            self.mpv.cmd("set_property", "pause", True)
            self.mpv.set_volume(sl["vol"])
            self.sleep = None
            self.say("💤 paused; the volume is back where it was", 8)
            return
        if left <= SLEEP_FADE and not st["paused"]:
            sl["fading"] = True
            self.mpv.set_volume(sl["vol"] * max(0.0, left / SLEEP_FADE))
        elif sl.get("fading") and st["paused"]:                      # paused by hand mid-fade: put the gain back
            sl["fading"] = False
            self.mpv.set_volume(sl["vol"])

    # ---- the phone remote

    def describe_now(self):
        sleep = sleep_tag(self.sleep, self.last_status).strip()
        if not self.now:
            return {"title": "", "tracks": [], "radio": False, "sleep": sleep}
        return {"title": self.now.get("title") or "", "radio": bool(self.now.get("radio")), "sleep": sleep,
                "tracks": [t.get("title") or "" for t in self.now.get("tracks") or []]}

    def toggle_remote(self):
        if self.remote:
            self.remote.shutdown()
            self.remote = None
            self.state["remote"] = False
            self.write_state()
            self.say("remote off", 3)
            return
        try:
            self.remote = Remote(self.mpv, self.describe_now, on_sleep=self.set_sleep)
            self.remote.start()
        except OSError as e:
            self.remote = None
            self.say(f"remote: {e}", 8)
            return
        self.state["remote"] = True
        self.write_state()
        self.say(f"remote: {self.remote.url()}  (R again turns it off)", 15)

    def screensaver_on(self):
        """Whether the light show starts by itself after SCREENSAVER_SECS idle (V toggles, remembered)."""
        return bool(SCREENSAVER_SECS) and self.state.get("screensaver", True)

    def toggle_screensaver(self):
        if not SCREENSAVER_SECS:
            self.say("the light show never starts by itself here (SCREENSAVER_SECS is 0)", 6)
            return
        on = not self.state.get("screensaver", True)
        self.state["screensaver"] = on
        self.write_state()
        if on:
            self.say(f"light show starts by itself after {SCREENSAVER_SECS // 60} minutes idle  (V stops it)", 6)
        else:
            self.say("light show stays off until you press v  (V lets it start by itself again)", 6)

    # ---- levels

    def push(self, level, select=None):
        if select is not None:
            level.cursor = max(0, min(select, len(level.items) - 1))
        self.stack.append(level)

    HOME = [
        (HDR, "Now"),
        QUEUE, RANDOM, THISDAY,
        (HDR, "The Dead"),
        YEARS_GD, TOURS, DARKSTAR, NOTFADE, SEASTONES, RAIN, TEARS, JGB,
        (HDR, "Not Dead"),
        RADIO, ONAIR, FIRESIGN, JOKES,
        (HDR, "Everything"),
        HIST, BOOKMARKS, STATS,
    ]
    HOME_TEXT = {
        QUEUE: "▶ Now playing        the current playlist",
        RANDOM: "🎲 Random show       any night, 1965-1995, best source, straight into play",
        THISDAY: "📅 This day          every show played on today's date, 1965-1995",
        YEARS_GD: "Grateful Dead        1965-1995, by year",
        TOURS: "🚌 Tours             Europe '72, the Wall of Sound, May '77, Egypt, Winterland's last nights... a night, or the whole run",
        ONAIR: "📻 On the air        the Grateful Dead Hour, Dead to the World, the KFOG New Year's broadcast",
        BOOKMARKS: "★ Bookmarks          shows and moments pinned with *",
        STATS: "Stats                what History adds up to: songs, years, shows, hours",
        DARKSTAR: "★ Dark Star          the famous ones, a random one after another, every one",
        NOTFADE: "♥ Not Fade Away      the famous ones, a random one after another, every one",
        SEASTONES: "≋ Seastones          Phil and Ned between sets, 1974: the experiments, night by night",
        RAIN: "☔ Rain and Snow      random weather and water songs, a random night's version of each, on and on",
        TEARS: "Tears                the weepers: Stella Blue, Black Peter, Wharf Rat, Morning Dew...",
        JGB: "JGB                  Jerry Garcia Band, 1970-1995, and Legion of Mary, Garcia/Saunders, Reconstruction, the acoustic band",
        RADIO: "♪ Classical radio    lossless FLAC stations",
        FIRESIGN: "Firesign Theatre     the LPs, 24-bit vinyl transfers",
        JOKES: "Jokes                comedy LPs: Buckley, Bruce, Sahl, Newhart, Pryor, the Goons, Python...",
        HIST: "History              everything played, newest first",
    }

    def home_items(self):
        return list(self.HOME)

    def push_home(self):
        def render(it, w):
            if isinstance(it, tuple) and it[0] == HDR:
                return f"{it[1]}"
            return "    " + self.HOME_TEXT[it]
        items = self.home_items()
        lvl = Level("home", "Poseidon", items, render, {"home": True})
        st = self.state
        want = RADIO if st.get("last") == "radio" else SEASTONES if st.get("seastones") else ONAIR if st.get("onair") else (
            (st.get("lp") if st.get("lp") in ALBUMS else FIRESIGN) if st.get("lp") else (
                JGB if st.get("collection") == "JerryGarcia" else YEARS_GD))
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

    def rain_tracks(self, n, songs=RAIN_SONGS, icon="☔", avoid=()):
        out = []
        seen = set(avoid)
        picks = self.rng.sample(songs, min(n, len(songs))) if len(songs) > 1 else [songs[0]] * n
        for song in picks:
            self.loading(f"{icon} looking for a {song}...")
            hit = None
            for _ in range(4):                       # not one we already have queued
                hit = self.random_version(song)
                if not hit or hit[2][hit[1]]["src"] not in seen:
                    break
            if not hit or hit[2][hit[1]]["src"] in seen:
                continue
            doc, idx, tracks, meta = hit
            seen.add(tracks[idx]["src"])
            t = dict(tracks[idx])
            t["title"] = f"{show_title(doc, meta)}: {t['title']}"
            out.append(t)
        return out

    def rain(self, songs=RAIN_SONGS, title="☔ Rain and Snow", icon="☔", batch=RAIN_BATCH, more=3):
        """A stream of random versions of random songs from `songs`, refilled as it plays."""
        tracks = self.rain_tracks(batch, songs, icon)
        if not tracks:
            self.say("nothing found (archive.org?)")
            return
        self.now = {"doc": None, "tracks": tracks, "title": title, "rain": {"songs": songs, "icon": icon, "more": more}}
        self.mpv.play([t["src"] for t in tracks], 0)
        self.say(f"{icon} {len(tracks)} to start; more come as it goes", 8)
        self.push_queue()

    def rain_more(self):
        """Called from the main loop when the last queued song starts: add a few more."""
        r = self.now["rain"]
        more = self.rain_tracks(r["more"], r["songs"], r["icon"], avoid={t["src"] for t in self.now["tracks"]})
        for t in more:
            self.mpv.cmd("loadfile", t["src"], "append")
        self.now["tracks"].extend(more)
        self.msg_until = 0

    # ---- Dark Star

    @staticmethod
    def night_on_disk(date):
        d = os.path.join(gd.DEFAULT_DEST, "shows", date[:4])
        return os.path.isdir(d) and any(n.startswith(date) for n in os.listdir(d))

    def push_nights(self, key):
        """A song's section (NIGHTS): the famous ones, a random one after another, every one."""
        title, icon, song, nights = NIGHTS[key]

        def render(it, w):
            if it == "random":
                return f"  {icon} A random {song}, then another, and another"
            if it == "every":
                return f"  ♪ Every {song} archive.org has, one row per show"
            date, why = it
            return f"{'*' if self.night_on_disk(date) else ' '} {date}  {why}"[:w]
        items = ["random", "every"] + list(nights)
        lvl = Level("nights", title, items, render, {"nights": key})
        self.push(lvl, 0)

    # ---- Seastones

    def push_seastones(self, select=None):
        def render(it, w):
            if it == "random":
                return "  ≋ A random Seastones, then another, and another"
            if isinstance(it, dict):
                loc = "*" if os.path.isdir(local_show_dir(it)) else " "
                return f"{loc} {it['date']}  {it['venue']}. {it['note']}"[:w]
            date, why = it
            return f"{'*' if self.night_on_disk(date) else ' '} {date}  {why}"[:w]
        items = ["random"] + list(SEASTONES_NIGHTS) + list(SEASTONES_DOCS)
        lvl = Level("seastones", "≋ Seastones", items, render, {"seastones": True})
        self.push(lvl, items.index(select) if select in items else 0)

    def play_from_song(self, date, songs, icon):
        """That night, from the first track titled like any of `songs` on: the best source
        that really has it, on disk first."""
        year = int(date[:4])
        self.loading(f"{icon} {date}: finding {songs[0]}...")
        try:
            entry = next((d for d in group_dates(year_docs(year)) if d["date"] == date), None)
        except Exception as e:
            self.say(f"archive.org: {e}")
            return
        if not entry:
            self.say(f"{date} is not in the index")
            return
        items = sorted(entry["items"], key=source_rank)
        items.sort(key=lambda d: not os.path.isdir(local_show_dir(d)))
        for doc in items[:8]:
            try:
                meta = item_meta(doc["identifier"])
                if not any(gd.choose_files(meta, "best", s)[0] for s in songs):
                    continue
                idx, tracks, meta = self.song_track_index(doc, songs)
            except Exception:
                continue
            self.play_doc(doc, idx)
            self.push_tracks(doc, idx)
            return
        self.say(f"no source of {date} lists {songs[0]}")

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

    # ---- this day

    def push_this_day(self):
        """Every show played on today's month and day, any year: a dates list like a year's."""
        today = time.localtime()
        md = time.strftime("%m-%d", today)
        title = time.strftime("📅 %B %-d", today)
        self.loading(f"{title}: every year, from archive.org...")
        try:
            dates = group_dates(day_docs(md) or [])
        except Exception as e:
            self.say(f"archive.org: {e}")
            return
        if not dates:
            self.say(f"no show on {time.strftime('%B %-d', today)}, any year")
            return
        lvl = Level("dates", title, dates, date_row, {"collection": gd.DEFAULT_COLLECTION, "day": md})
        self.push(lvl, 0)
        self.msg_until = 0

    # ---- tours

    def push_tours(self):
        def render(t, w):
            name, first, last, why = t
            return f"  {name:32} {first} to {last}   {why}"[:w]
        lvl = Level("tours", "🚌 Tours", TOUR_LIST, render, {"tours": True})
        self.push(lvl, 0)

    def push_tour(self, tour):
        name, first, last, why = tour
        self.loading(f"🚌 {name}: loading the run from archive.org...")
        try:
            dates = group_dates(tour_docs(tour))
        except Exception as e:
            self.say(f"archive.org: {e}")
            return
        if not dates:
            self.say(f"nothing in the index for {name}")
            return

        def render(it, w):
            if it == "random":
                return f"  🎲 A random night of {name}, best source, straight into play"
            if it == "whole":
                return f"  ♪ The whole run, {len(dates)} shows in order, one playlist"
            return date_row(it, w)
        lvl = Level("tour", f"🚌 {name}", ["random", "whole"] + dates, render,
                    {"tour": tour, "collection": gd.DEFAULT_COLLECTION})
        self.push(lvl, 0)
        self.msg_until = 0

    def tour_random(self, lvl):
        dates = [d for d in lvl.items if isinstance(d, dict)]
        entry = self.rng.choice(dates)
        doc = self.best_source(entry)
        self.push_sources(entry, doc["identifier"])
        self.play_doc(doc)
        self.push_tracks(doc, 0)

    def tour_whole(self, lvl):
        """Every night of the run, best source each, as one playlist in date order."""
        name = lvl.ctx["tour"][0]
        dates = [d for d in lvl.items if isinstance(d, dict)]
        combined = []
        for k, entry in enumerate(dates):
            doc = self.best_source(entry)
            self.loading(f"🚌 {name}: {k + 1}/{len(dates)} {entry['date']}...")
            try:
                tracks, meta = tracks_for(doc)
            except Exception:
                continue
            show = show_title(doc, meta)
            for t in tracks:
                t = dict(t)
                t["title"] = f"{show}: {t['title']}"
                combined.append(t)
        if not combined:
            self.say("nothing playable")
            return
        self.now = {"doc": None, "tracks": combined, "title": f"🚌 {name}"}
        self.mpv.play([t["src"] for t in combined], 0)
        self.say(f"🚌 {name}: {len(dates)} shows, {len(combined)} tracks, in order", 8)
        self.push_queue()

    # ---- on the air

    def push_onair(self, select_id=None):
        def render(d, w):
            loc = "*" if os.path.isdir(local_show_dir(d)) else " "
            return f"{loc} {d['date'][:4]}  {d['title']:44} {d['note']}"[:w]
        items = list(ONAIR_DOCS)
        lvl = Level("onair", "📻 On the air", items, render, {"onair": True})
        sel = next((i for i, d in enumerate(items) if d["identifier"] == select_id), 0) if select_id else 0
        self.push(lvl, sel)

    # ---- the taper's notes

    def doc_here(self):
        """The show the cursor is on, or the one playing: for i (notes), * (bookmark) and d (fetch)."""
        lvl = self.stack[-1]
        i, item = self.current()
        if lvl.kind == "tracks":
            return lvl.ctx["doc"]
        if lvl.kind in ("sources", "songs", "albums", "onair") and isinstance(item, dict) and item.get("identifier"):
            return item
        if lvl.kind == "seastones" and isinstance(item, dict):
            return item
        if lvl.kind in ("dates", "tour") and isinstance(item, dict) and item.get("items"):
            return self.best_source(item)
        if lvl.kind in ("history", "bookmarks") and isinstance(item, dict) and (item.get("doc") or {}).get("identifier"):
            return item["doc"]
        if lvl.kind in ("queue", "home") and self.now and self.now.get("doc"):
            return self.now["doc"]
        return None

    def push_notes(self, doc):
        """What the item says about itself: source, lineage, the taper's notes, the setlist, the reviews."""
        self.loading(f"reading the notes on {doc['identifier']}...")
        try:
            meta = item_meta(doc["identifier"])
        except Exception as e:
            self.say(f"metadata: {e}")
            return
        h, w = self.scr.getmaxyx()
        lines = notes_lines(doc, meta, max(40, w - 4))
        lvl = Level("notes", f"notes: {doc['identifier']}", lines, lambda s, w_: s[:w_], {"doc": doc})
        self.push(lvl, 0)
        self.msg_until = 0

    # ---- bookmarks

    def bookmark_here(self):
        """* pins what is playing, at the second it is at; with nothing playing, the show under the cursor."""
        st = self.last_status
        rec = {"ts": time.strftime("%Y-%m-%d %H:%M")}
        if self.now and st and not self.now.get("radio") and st["pos"] < len(self.now["tracks"]):
            t = self.now["tracks"][st["pos"]]
            rec.update({"show": self.now.get("title"), "title": t.get("title"), "src": t.get("src"),
                        "how": t.get("how"), "length": t.get("length"), "time": st.get("time") or 0})
            doc = self.now.get("doc")
            if doc:
                rec["doc"] = {k: doc.get(k) for k in ("identifier", "date", "collection", "kind", "lp", "artist", "title",
                                                       "seastones", "onair")}
                rec["track"] = st["pos"]
        else:
            doc = self.doc_here()
            if not doc:
                self.say("* pins what is playing, or the show under the cursor")
                return
            lvl = self.stack[-1]
            i, item = self.current()
            rec.update({"show": f"{doc.get('date', '')} {doc.get('venue') or doc.get('coverage') or doc.get('title') or ''}".strip(),
                        "title": item.get("title") if lvl.kind == "tracks" else "", "time": 0,
                        "track": i if lvl.kind == "tracks" else 0,
                        "doc": {k: doc.get(k) for k in ("identifier", "date", "collection", "kind", "lp", "artist", "title",
                                                         "seastones", "onair")}})
        marks = load_bookmarks()
        marks.insert(0, rec)
        save_bookmarks(marks)
        where = f" at {fmt_time(rec['time'])}" if rec.get("time") else ""
        self.say(f"★ pinned {rec.get('show')}{': ' + rec['title'] if rec.get('title') else ''}{where}", 6)
        lvl = self.stack[-1]
        if lvl.kind == "bookmarks":
            lvl.items[:] = marks

    def push_bookmarks(self):
        def render(r, w):
            when = f"  at {fmt_time(r['time'])}" if r.get("time") else ""
            show = r.get("show") or ""
            title = f"  ·  {r['title']}" if r.get("title") else ""
            return f"  {r['ts']}  {show}{title}{when}"[:w]
        lvl = Level("bookmarks", "★ Bookmarks", load_bookmarks(), render, {"bookmarks": True})
        self.push(lvl, 0)

    def delete_bookmark(self, lvl, i):
        if i is None or i >= len(lvl.items):
            return
        gone = lvl.items.pop(i)
        save_bookmarks(lvl.items)
        self.say(f"unpinned {gone.get('show')}", 4)

    # ---- stats

    def stats_lines(self):
        """What the whole history.jsonl adds up to."""
        try:
            with open(HISTORY) as f:
                recs = [json.loads(l) for l in f if l.strip()]
        except (OSError, ValueError):
            recs = []
        recs = [r for r in recs if isinstance(r, dict)]
        if not recs:
            return ["  nothing played yet"]
        plays = [r for r in recs if not r.get("radio")]
        tunings = [r for r in recs if r.get("radio")]
        songs, years, shows, timed = {}, {}, {}, []
        for r in plays:
            k = song_key(r.get("title"))
            if k:
                songs.setdefault(k, [0, r.get("title")])
                songs[k][0] += 1
            show = r.get("show") or ""
            title = str(r.get("title") or "")
            if re.match(r"\d{4}-\d{2}-\d{2}.*?: ", title):       # a built playlist: the night is in the track title
                show = title.split(": ", 1)[0]
            y = ((r.get("doc") or {}).get("date") or show)[:4]
            if y.isdigit():
                years[y] = years.get(y, 0) + 1
            if show:
                shows[show] = shows.get(show, 0) + 1
            if r.get("length"):
                timed.append((r, show))
        out = [f"  since {recs[0].get('ts', '?')[:10]}: {len(plays)} tracks from {len(shows)} shows, "
               f"{len(tunings)} radio tunings"]
        hours = sum(float(r["length"]) for r, _ in timed) / 3600
        if timed:
            out.append(f"  {hours:.1f} hours of music, counting the {len(timed)} tracks whose length was logged")
        out.append("")

        def top(title, table, fmt, n=10):
            if not table:
                return
            out.append(f"  ── {title} ──")
            for k, v in sorted(table.items(), key=lambda kv: -(kv[1][0] if isinstance(kv[1], list) else kv[1]))[:n]:
                out.append(fmt(k, v))
            out.append("")
        top("most played songs", songs, lambda k, v: f"  {v[0]:>4}  {song_key_title(v[1])}")
        top("years", years, lambda k, v: f"  {v:>4}  {k}")
        top("shows", shows, lambda k, v: f"  {v:>4}  {k}")
        longest = {}
        for r, show in timed:
            k = song_key(r.get("title"))
            if k in ("dark star", "playing in the band", "the other one", "eyes of the world") and \
                    float(r["length"]) > longest.get(k, (0, None))[0]:
                longest[k] = (float(r["length"]), show)
        if longest:
            out.append("  ── the longest ones heard ──")
            for k, (L, show) in sorted(longest.items()):
                out.append(f"  {fmt_time(L):>8}  {k.title()}  ·  {show}")
            out.append("")
        return out

    def push_stats(self):
        lvl = Level("stats", "Stats", self.stats_lines(), lambda s, w: s[:w], {"stats": True})
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
               "src": track.get("src"), "how": track.get("how"), "radio": self.now.get("radio"),
               "length": track.get("length")}
        if doc:
            rec["doc"] = {k: doc.get(k) for k in ("identifier", "date", "collection", "kind", "lp", "artist", "title",
                                                   "seastones", "onair")}
            rec["track"] = self.last_status["pos"] if self.last_status else 0
        append_history(rec)

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
            self.play_doc(doc, int(r.get("track") or 0), r.get("time"))
            return
        if r.get("src"):
            self.now = {"doc": None, "title": r.get("show") or "", "tracks": [{"title": r.get("title"), "src": r["src"],
                        "how": r.get("how") or "", "length": r.get("length")}]}
            self.mpv.play([r["src"]], 0)
            self.pending_seek = r.get("time") if r.get("time") and r["time"] > 5 else None
            self.say(f"playing {r.get('title')}")

    def push_queue(self):
        if not self.now or not self.now.get("tracks"):
            self.say("nothing is playing")
            return
        tracks = self.now["tracks"]

        def render(t, w):
            right = f" {fmt_time(t.get('length'))}  {t.get('how') or '':12}"
            left = f"  {next(i for i, x in enumerate(tracks) if x is t) + 1:>3}  {t['title']}"
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
            if s_ == "random":
                return "  🎲 A random station, straight into play (the dice land on its row)"
            right = f"  {s_['fmt']:13}"
            left = f"  {s_['name']:26} {s_['notes']}"
            return left[:max(0, w - len(right))].ljust(w - len(right)) + right
        items = ["random"] + stations()
        lvl = Level("radio", "♪ Classical radio", items, render)
        sel = next((i for i, s_ in enumerate(items) if s_ != "random" and s_["key"] == select_key), 0) if select_key else 0
        self.push(lvl, sel)

    def random_station(self):
        """Any station but the one playing; the cursor follows it when the radio list is open."""
        pool = [s_ for s_ in stations() if s_["key"] != (self.now or {}).get("radio")] or stations()
        s_ = self.rng.choice(pool)
        lvl = self.stack[-1]
        if lvl.kind == "radio" and not lvl.filter:
            lvl.cursor = next((i for i, it in enumerate(lvl.items) if it != "random" and it["key"] == s_["key"]), lvl.cursor)
        return s_

    def play_station(self, s_):
        if s_ == "random":
            s_ = self.random_station()
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
        who = "" if collection == gd.DEFAULT_COLLECTION else f"{COLLECTIONS[collection]['title']} "
        self.loading(f"loading {who}{year} from archive.org...")
        try:
            docs = year_docs(year, collection)
        except Exception as e:
            self.say(f"archive.org: {e}")
            return
        dates = group_dates(docs)
        lvl = Level("dates", str(year), dates, date_row, {"year": year, "collection": collection})
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
        """Index of the first track titled like `song` (one title or a list of them), else 0."""
        songs = [song] if isinstance(song, str) else list(song)
        tracks, meta = tracks_for(doc)
        for i, t in enumerate(tracks):
            if any(gd.song_matches(s, t["title"]) or gd.song_matches(s, os.path.basename(t["src"])) for s in songs):
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
        return best_source(date_entry)

    def resume(self):
        st = self.state
        if st.get("last") == "radio" and st.get("radio"):
            s_ = next((x for x in stations() if x["key"] == st["radio"]), None)
            if s_:
                self.play_station(s_)
                return
        if st.get("last") == "queue":
            self.resume_queue()
            return
        if not st.get("identifier"):
            self.say("nothing to resume")
            return
        doc = None
        if st.get("lp"):
            doc = next((d for d in album_docs() if d["identifier"] == st["identifier"]), None)
        elif st.get("seastones"):
            doc = seastones_doc(st["identifier"])
        elif st.get("onair"):
            doc = onair_doc(st["identifier"])
        try:
            for d in ([] if doc else year_docs(int(st["year"]), st.get("collection")
                                               if st.get("collection") in COLLECTIONS else gd.DEFAULT_COLLECTION)):
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
            note = f"  {self.msg}" if self.msg and time.time() < self.msg_until else volume_tag(st)
            return f"{self.now['title']}  ·  {name}  {fmt_time(st['time'])}" + ("  ⏸" if st["paused"] else "") + note

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
            elif ch in (ord("+"), ord("=")):     # m steps the mode in here, so no mute key in the light show
                self.volume(VOLUME_STEP)
            elif ch in (ord("-"), ord("_")):
                self.volume(-VOLUME_STEP)
            else:
                return False
            return True

        viz = deadviz.Viz(self.scr, title_fn=title, on_key=on_key, mode=self.viz_mode)
        self.showing = True
        try:
            viz.run()
        finally:
            self.showing = False
            self.viz_mode = viz.mode
            self.state["viz_mode"] = viz.mode
            self.write_state()
            self.scr.timeout(500)
            self.last_key = time.time()

    def download(self, doc):
        if os.path.isdir(local_show_dir(doc)) and any(
                n.endswith((".flac", ".mp3", ".ogg")) for n in os.listdir(local_show_dir(doc))):
            self.say("already on disk (re-fetch with poseidon gdarchive fetch <id> to re-tag)")
            return
        os.makedirs(CACHE, exist_ok=True)
        log = os.path.join(CACHE, f"fetch-{doc['identifier']}.log")
        p = subprocess.Popen(poseidon.self_command(["gdarchive", "fetch", doc["identifier"]]), stdin=subprocess.DEVNULL,
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
            dac += volume_tag(st) + sleep_tag(self.sleep, st)
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
            elif lvl.kind == "nights":
                keys = " ↵/p play that night from the song on (or a random one after another, or every version)  h back  q quit (music stays)"
            elif lvl.kind == "seastones":
                keys = " ↵/p play that night from the Seastones set on (or a random one after another)  d fetch  h back  q quit (music stays)"
            elif lvl.kind == "history":
                keys = " ↵/p play it again  i notes  * pin  / filter  ␣ pause  h back  q quit (music stays)"
            elif lvl.kind == "bookmarks":
                keys = " ↵/p play from the pinned second  x unpin  i notes  / filter  ␣ pause  h back  q quit (music stays)"
            elif lvl.kind == "tours":
                keys = " ↵ the run, night by night  p a random night of it, straight into play  h back  q quit (music stays)"
            elif lvl.kind == "tour":
                keys = " ↵ sources  p play best source (or a random night, or the whole run)  i notes  d fetch  * pin  h back  q quit (music stays)"
            elif lvl.kind == "onair":
                keys = " ↵ tracks  p play  i notes  d fetch  h back  q quit (music stays)"
            elif lvl.kind in ("notes", "stats"):
                keys = " ↑↓ scroll  / filter  ␣ pause  n/b trk  h back  q quit (music stays)"
            elif lvl.kind == "home":
                keys = " ↵ open  p play  w now playing  c radio  f song  g goto  r resume  v show  * pin  q quit (music stays)  Q stop & quit"
            elif lvl.kind == "queue":
                keys = " ↵/p jump to track  ␣ pause  n/b trk  ←→ seek  +/- vol  m mute  * pin  i notes  / filter  h back  q quit (music stays)  Q quit and stop"
            else:
                keys = " ↵ open  p play  ␣ pause  n/b trk  ←→ seek  +/- vol  m mute  / filter  f song  g goto  v show  d fetch  i notes  * pin  r resume  q quit (music stays)  Q stop & quit"
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
            self.push_years("JerryGarcia")
        elif lvl.kind == "home" and item in ALBUMS:
            self.push_albums(item)
        elif lvl.kind == "home" and item == TEARS:
            self.push_tears()
        elif lvl.kind == "home" and item == HIST:
            self.push_history()
        elif lvl.kind in ("history", "bookmarks"):
            self.play_history(item)
        elif lvl.kind == "home" and item == QUEUE:
            self.push_queue()
        elif lvl.kind == "home" and item == RANDOM:
            self.random_show()
        elif lvl.kind == "home" and item == THISDAY:
            self.push_this_day()
        elif lvl.kind == "home" and item == TOURS:
            self.push_tours()
        elif lvl.kind == "home" and item == ONAIR:
            self.push_onair()
        elif lvl.kind == "home" and item == BOOKMARKS:
            self.push_bookmarks()
        elif lvl.kind == "home" and item == STATS:
            self.push_stats()
        elif lvl.kind == "tours":
            self.push_tour(item)
        elif lvl.kind == "tour" and item == "random":
            self.tour_random(lvl)
        elif lvl.kind == "tour" and item == "whole":
            self.tour_whole(lvl)
        elif lvl.kind == "tour":
            self.push_sources(item)
        elif lvl.kind == "onair":
            self.push_tracks(item)
        elif lvl.kind in ("notes", "stats"):
            pass
        elif lvl.kind == "home" and item == RAIN:
            self.rain()
        elif lvl.kind == "home" and item in NIGHTS:
            self.push_nights(item)
        elif lvl.kind == "nights" and item == "random":
            title, icon, song, _ = NIGHTS[lvl.ctx["nights"]]
            self.rain([song], title, icon, batch=2, more=1)
        elif lvl.kind == "nights" and item == "every":
            self.push_songs(NIGHTS[lvl.ctx["nights"]][2], gd.DEFAULT_COLLECTION)
        elif lvl.kind == "nights":
            title, icon, song, _ = NIGHTS[lvl.ctx["nights"]]
            self.play_from_song(item[0], [song], icon)
        elif lvl.kind == "home" and item == SEASTONES:
            self.push_seastones()
        elif lvl.kind == "seastones" and item == "random":
            self.rain(["Seastones"], "≋ Seastones", "≋", batch=2, more=1)
        elif lvl.kind == "seastones" and isinstance(item, dict):
            self.play_doc(item)
            self.push_tracks(item)
        elif lvl.kind == "seastones":
            self.play_from_song(item[0], SEASTONES_TITLES, "≋")
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
            self.push_years("JerryGarcia")
        elif lvl.kind == "home" and item in ALBUMS:
            self.push_albums(item)
        elif lvl.kind == "home" and item == TEARS:
            self.push_tears()
        elif lvl.kind == "home" and item == HIST:
            self.push_history()
        elif lvl.kind in ("history", "bookmarks"):
            self.play_history(item)
        elif lvl.kind == "home" and item == QUEUE:
            self.push_queue()
        elif lvl.kind == "home" and item == RANDOM:
            self.random_show()
        elif lvl.kind == "home" and item == THISDAY:
            self.push_this_day()
        elif lvl.kind == "home" and item == TOURS:
            self.push_tours()
        elif lvl.kind == "home" and item == ONAIR:
            self.push_onair()
        elif lvl.kind == "home" and item == BOOKMARKS:
            self.push_bookmarks()
        elif lvl.kind == "home" and item == STATS:
            self.push_stats()
        elif lvl.kind == "tours":
            self.push_tour(item)
            if self.stack[-1].kind == "tour":
                self.tour_random(self.stack[-1])
        elif lvl.kind == "tour" and item == "random":
            self.tour_random(lvl)
        elif lvl.kind == "tour" and item == "whole":
            self.tour_whole(lvl)
        elif lvl.kind == "tour":
            self.play_doc(self.best_source(item))
        elif lvl.kind == "onair":
            self.play_doc(item)
            self.push_tracks(item)
        elif lvl.kind in ("notes", "stats"):
            pass
        elif lvl.kind == "home" and item == RAIN:
            self.rain()
        elif lvl.kind == "home" and item in NIGHTS:
            self.push_nights(item)
        elif lvl.kind == "nights" and item == "random":
            title, icon, song, _ = NIGHTS[lvl.ctx["nights"]]
            self.rain([song], title, icon, batch=2, more=1)
        elif lvl.kind == "nights" and item == "every":
            self.push_songs(NIGHTS[lvl.ctx["nights"]][2], gd.DEFAULT_COLLECTION)
        elif lvl.kind == "nights":
            title, icon, song, _ = NIGHTS[lvl.ctx["nights"]]
            self.play_from_song(item[0], [song], icon)
        elif lvl.kind == "home" and item == SEASTONES:
            self.push_seastones()
        elif lvl.kind == "seastones" and item == "random":
            self.rain(["Seastones"], "≋ Seastones", "≋", batch=2, more=1)
        elif lvl.kind == "seastones" and isinstance(item, dict):
            self.play_doc(item)
            self.push_tracks(item)
        elif lvl.kind == "seastones":
            self.play_from_song(item[0], SEASTONES_TITLES, "≋")
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
            self.say("year must be 1965-1995 (Dead) or 1970-1995 (JGB)")
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
        elif ch in (ord("+"), ord("=")):
            self.volume(VOLUME_STEP)
        elif ch in (ord("-"), ord("_")):
            self.volume(-VOLUME_STEP)
        elif ch == ord("m"):
            self.toggle_mute()
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
        elif ch == ord("V"):
            self.toggle_screensaver()
        elif ch == ord("t"):
            self.set_sleep(self.prompt("sleep: minutes, 'track' (end of this track) or 'show' (end of the playlist); 0 cancels"))
        elif ch == ord("R"):
            self.toggle_remote()
        elif ch == ord("i") and lvl.kind == "radio":
            i, item = self.current()
            if item == "random":
                self.say("move to a station to probe it")
            elif item:
                self.probe_station(item)
        elif ch == ord("i"):
            doc = self.doc_here()
            if doc:
                self.push_notes(doc)
            else:
                self.say("i shows the taper's notes and the reviews of a show: on a date, source or track list, or while one plays")
        elif ch == ord("*"):
            self.bookmark_here()
        elif ch == ord("x") and lvl.kind == "bookmarks":
            i, item = self.current()
            self.delete_bookmark(lvl, i)
        elif ch == ord("a") and lvl.kind == "songs":
            self.play_all_versions(lvl)
        elif ch == ord("/"):
            lvl.filter = self.prompt("filter")
            lvl.cursor = 0
        elif ch == 27:  # Esc clears filter
            lvl.filter = ""
        elif ch == ord("d"):
            doc = self.doc_here() if lvl.kind not in ("queue", "home") else None
            if doc:
                self.download(doc)
            else:
                self.say("d works on a date, source or track list")
        elif ch == curses.KEY_RESIZE:
            pass
        return True

    def run(self):
        try:
            self.mpv.start()
            if self.mpv.adopted:
                self.adopt_playlist()          # its volume is whatever it was left at; the status line shows it
            elif self.state.get("volume") is not None:
                self.mpv.set_volume(self.state["volume"])
        except FileNotFoundError:
            self.say("mpv is not installed (apt install mpv / brew install mpv)", 60)
        except Exception as e:
            self.say(f"mpv failed to start: {e}", 30)
        if self.state.get("remote"):
            self.toggle_remote()               # it was on last time: back on, same port
        try:
            while True:
                st = self.mpv.status() if self.mpv.sock else None
                if st and self.now and self.now.get("rain") and st["count"] == len(self.now["tracks"]) \
                        and st["pos"] >= st["count"] - 1 and not st["paused"] \
                        and not (self.sleep and self.sleep["mode"] == "show"):
                    self.rain_more()
                    st = self.mpv.status()
                self.tick_sleep(st)
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
                ch = self.scr.getch()        # a Ctrl-C here raises out to the handler below
                if ch == -1:
                    if (self.screensaver_on() and st and not st["paused"] and deadviz
                            and time.time() - self.last_key > SCREENSAVER_SECS):
                        self.light_show()
                    continue
                self.last_key = time.time()
                try:
                    if not self.handle(ch):
                        break
                except Exception as e:  # keep the UI alive on a bad API response
                    self.say(f"error: {e}", 8)
        except KeyboardInterrupt:    # Ctrl-C, or the SIGTERM/SIGHUP handler in main()
            pass                     # fall through and put everything back
        self.save_position()
        self.awake.stop()
        self.awake.join(2)        # drop the idle inhibitor before curses lets go
        if self.sleep and self.sleep.get("fading"):
            self.mpv.set_volume(self.sleep["vol"])
        if self.remote:
            self.remote.shutdown()
        if self.detach:
            if self.mpv.sock:
                self.mpv.sock.close()
            print("music left playing; start again to adopt it, or quit it with:")
            print(f"  echo '{{\"command\":[\"quit\"]}}' | socat - UNIX-CONNECT:{self.mpv.path}")
            print("  or: poseidon play stop")
        else:
            self.mpv.stop()
        return [f for f in self.fetches if f[1].poll() is None]


# --------------------------------------------------------------------------- the phone remote

REMOTE_PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Poseidon</title><style>
:root{color-scheme:dark}body{margin:0;background:#0b1020;color:#e6e9f0;font:17px/1.4 -apple-system,system-ui,sans-serif}
header{padding:14px 16px 6px}h1{margin:0;font-size:15px;letter-spacing:.08em;color:#8fb3ff}
#title{font-size:18px;margin-top:6px}#track{color:#ffd166;font-size:20px;margin-top:2px}#time{color:#9aa4b8;font-size:14px;margin-top:4px}
.bar{height:6px;background:#1c2540;border-radius:3px;margin:8px 16px;overflow:hidden}.bar i{display:block;height:100%;background:#8fb3ff;width:0}
.row{display:flex;gap:8px;padding:6px 16px}.row button{flex:1;font-size:26px;padding:16px 0;border:0;border-radius:14px;background:#1c2540;color:#e6e9f0}
.row button.small{font-size:16px;padding:12px 0}.row button:active{background:#33417a}
#vol{color:#9aa4b8;font-size:14px;text-align:center;padding:2px}
ul{list-style:none;margin:8px 0 40px;padding:0}li{padding:10px 16px;border-top:1px solid #151c33;color:#c3c9d6}li.now{color:#ffd166;background:#131a33}
li span{color:#5b6580;margin-right:8px}
</style></head><body>
<header><h1>MAY THE LORD POSEIDON CONVEY YOU</h1><div id="title">…</div><div id="track"></div><div id="time"></div></header>
<div class="bar"><i id="fill"></i></div>
<div class="row"><button onclick="cmd('prev')">⏮</button><button onclick="cmd('pause')" id="pp">⏯</button><button onclick="cmd('next')">⏭</button></div>
<div class="row"><button class="small" onclick="cmd('seek&s=-60')">−60s</button><button class="small" onclick="cmd('seek&s=-10')">−10s</button>
<button class="small" onclick="cmd('seek&s=10')">+10s</button><button class="small" onclick="cmd('seek&s=60')">+60s</button></div>
<div class="row"><button class="small" onclick="cmd('vol&d=-5')">vol −</button><button class="small" onclick="cmd('mute')">mute</button>
<button class="small" onclick="cmd('vol&d=5')">vol +</button></div>
<div class="row"><button class="small" onclick="cmd('sleep&m=30')">💤 30m</button><button class="small" onclick="cmd('sleep&m=60')">💤 60m</button>
<button class="small" onclick="cmd('sleep&m=show')">💤 end</button><button class="small" onclick="cmd('stop')">stop</button></div>
<div id="vol"></div><ul id="q"></ul>
<script>
function fmt(s){if(s==null)return'--:--';s=Math.floor(s);var h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;return(h?h+':'+String(m).padStart(2,'0'):m)+':'+String(x).padStart(2,'0')}
function show(d){document.getElementById('title').textContent=d.title||'stopped';
document.getElementById('track').textContent=d.track||'';
document.getElementById('time').textContent=d.pos>=0?fmt(d.time)+' / '+fmt(d.dur)+'   '+(d.pos+1)+'/'+d.count+(d.paused?'   ⏸':'')+(d.sleep?'   '+d.sleep:''):'';
document.getElementById('fill').style.width=(d.dur?100*Math.min(1,(d.time||0)/d.dur):0)+'%';
document.getElementById('vol').textContent=d.mute?'muted':(d.volume!=null?'volume '+Math.round(d.volume)+'%':'');
var q=document.getElementById('q');if(q.dataset.n!=d.count+':'+d.title){q.innerHTML='';(d.tracks||[]).forEach(function(t,i){var li=document.createElement('li');li.innerHTML='<span>'+(i+1)+'</span>'+t.replace(/&/g,'&amp;').replace(/</g,'&lt;');li.onclick=function(){cmd('play&i='+i)};q.appendChild(li)});q.dataset.n=d.count+':'+d.title}
Array.from(q.children).forEach(function(li,i){li.className=i==d.pos?'now':''})}
function poll(){fetch('/status').then(r=>r.json()).then(show).catch(function(){})}
function cmd(c){fetch('/cmd?do='+c,{method:'POST'}).then(r=>r.json()).then(show).catch(function(){})}
poll();setInterval(poll,2000);
</script></body></html>"""


class Remote(threading.Thread):
    """A page on the LAN with play, pause, next, volume, sleep and the queue: the second remote on
    the same mpv socket. describe() gives the titles (the TUI's `now`; standalone, the filenames)."""

    def __init__(self, mpv, describe, port=REMOTE_PORT, on_sleep=None):
        super().__init__(daemon=True)
        self.mpv, self.describe, self.on_sleep, self.port = mpv, describe, on_sleep, port
        remote = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def send(self, code, body, ctype):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = urllib.parse.urlparse(self.path)
                if path.path == "/status":
                    self.send(200, json.dumps(remote.status()).encode(), "application/json")
                elif path.path == "/":
                    self.send(200, REMOTE_PAGE.encode(), "text/html; charset=utf-8")
                else:
                    self.send(404, b"not here", "text/plain")

            def do_POST(self):
                path = urllib.parse.urlparse(self.path)
                if path.path != "/cmd":
                    self.send(404, b"not here", "text/plain")
                    return
                q = urllib.parse.parse_qs(path.query)
                remote.command(q.get("do", [""])[0], q)
                self.send(200, json.dumps(remote.status()).encode(), "application/json")
        self.server = http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler)
        self.server.daemon_threads = True

    def url(self):
        return f"http://{lan_ip()}:{self.port}/"

    def run(self):
        self.server.serve_forever(poll_interval=0.5)

    def shutdown(self):
        self.server.shutdown()
        self.server.server_close()

    def status(self):
        st = self.mpv.status() if self.mpv.sock else None
        d = self.describe() or {}
        tracks = d.get("tracks") or []
        out = {"title": d.get("title") or "", "pos": -1, "count": 0, "tracks": tracks, "track": "", "time": None,
               "dur": None, "paused": False, "volume": None, "mute": False, "sleep": d.get("sleep") or ""}
        if st:
            pos = st["pos"]
            track = tracks[pos] if pos < len(tracks) else (st.get("media_title") or "")
            if d.get("radio") and st.get("media_title"):
                track = st["media_title"]
            out.update({"pos": pos, "count": st["count"], "track": track, "time": st["time"], "dur": st["dur"],
                        "paused": st["paused"], "volume": st.get("volume"), "mute": st.get("mute")})
        return out

    def command(self, do, q):
        m = self.mpv
        if do == "pause":
            m.cmd("cycle", "pause")
        elif do == "next":
            m.cmd("playlist-next")
        elif do == "prev":
            m.cmd("playlist-prev")
        elif do == "stop":
            m.cmd("stop")
        elif do == "mute":
            m.cmd("cycle", "mute")
        elif do == "seek":
            try:
                m.cmd("seek", float(q.get("s", ["10"])[0]))
            except ValueError:
                pass
        elif do == "vol":
            try:
                cur = m.get("volume")
                if cur is not None:
                    level = m.set_volume(cur + float(q.get("d", ["5"])[0]))
                    st = load_state()
                    st["volume"] = level
                    write_state(st)
            except ValueError:
                pass
        elif do == "play":
            try:
                m.cmd("playlist-play-index", int(q.get("i", ["0"])[0]))
            except ValueError:
                pass
        elif do == "sleep" and self.on_sleep:
            self.on_sleep(q.get("m", [""])[0])


# --------------------------------------------------------------------------- the command line

def cli_doc(what, source=None):
    """A show for `poseidon play`: a date (best source, or the --source kind), an archive.org identifier, or random."""
    if what == "random":
        rng = random.Random()
        for _ in range(4):
            year = rng.choice(YEARS)
            dates = group_dates(year_docs(year) or [])
            if dates:
                good = [d for d in dates if d["rating"] >= 4.0] or dates
                entry = rng.choice(good)
                return best_source(entry), entry
        sys.exit("archive.org gave nothing to play")
    if re.match(r"\d{4}-\d{2}-\d{2}$", what):
        dates = group_dates(year_docs(int(what[:4])) or [])
        entry = next((d for d in dates if d["date"] == what), None)
        if not entry:
            sys.exit(f"{what}: no show in the index")
        if source:
            items = [d for d in entry["items"] if d["kind"] == source]
            if not items:
                sys.exit(f"{what}: no {source} source")
            return sorted(items, key=source_rank)[0], entry
        return best_source(entry), entry
    md = gd.metadata(what).get("metadata", {})
    if not md:
        sys.exit(f"{what}: not on archive.org")
    doc = {"identifier": what, "date": (md.get("date") or "0000-00-00")[:10], "collection": md.get("collection") or [],
           "kind": gd.source_kind({"identifier": what, "source": md.get("source")}), "title": md.get("title"),
           "venue": gd.venue_of(md)}
    return doc, None


def cli_play(argv):
    p = argparse.ArgumentParser(prog="poseidon play", description="Play without the TUI: the next TUI adopts the player.")
    p.add_argument("what", help="YYYY-MM-DD, random, an archive.org identifier, radio <station>, "
                               "or stop | pause | next | prev | status")
    p.add_argument("rest", nargs="*", help="the station key after radio (poseidon radio list)")
    p.add_argument("--song", help="start at the first track titled like this")
    p.add_argument("--track", type=int, default=1, help="start at this track number (1-based)")
    p.add_argument("--source", choices=["matrix", "sbd", "aud"], help="insist on this kind of source for a date")
    p.add_argument("--volume", type=int, help="mpv's software gain, 0-100")
    a = p.parse_args(argv)
    mpv = Mpv()
    try:
        return _cli_play(a, mpv)
    except FileNotFoundError:
        sys.exit("mpv is not installed (apt install mpv / brew install mpv)")


def _cli_play(a, mpv):
    if a.what in ("stop", "pause", "next", "prev", "status"):
        if not (os.path.exists(mpv.path) and mpv.adopt()):
            sys.exit("nothing is playing")
        if a.what == "stop":
            mpv.cmd("quit")
            print("stopped")
        elif a.what == "status":
            st = mpv.status()
            if not st:
                print("idle")
            else:
                print(f"{'⏸' if st['paused'] else '▶'} {st.get('media_title') or ''}  {fmt_time(st['time'])} / {fmt_time(st['dur'])}"
                      f"  {st['pos'] + 1}/{st['count']}{volume_tag(st)}")
        else:
            mpv.cmd({"pause": "cycle", "next": "playlist-next", "prev": "playlist-prev"}[a.what], *(["pause"] if a.what == "pause" else []))
            print(a.what)
        return
    state = load_state()
    if a.what == "radio":
        key = (a.rest or [None])[0]
        s_ = random.choice(stations()) if key == "random" else next((x for x in stations() if x["key"] == key), None)
        if not s_:
            sys.exit("radio <station>: random, or one of " + ", ".join(x["key"] for x in stations()))
        key = s_["key"]
        mpv.start(detach=True)
        mpv.play([s_["url"]], 0)
        if a.volume is not None:
            state["volume"] = mpv.set_volume(a.volume)
        elif not mpv.adopted and state.get("volume") is not None:
            mpv.set_volume(state["volume"])
        write_state({**state, "last": "radio", "radio": key})
        append_history({"ts": time.strftime("%Y-%m-%d %H:%M"), "show": s_["name"], "title": s_["name"], "src": s_["url"],
                        "how": s_["fmt"], "radio": key})
        print(f"tuning {s_['name']} ({s_['fmt']})")
        return
    doc, entry = cli_doc(a.what, a.source)
    tracks, meta = tracks_for(doc)
    if not tracks:
        sys.exit(f"{doc['identifier']}: no playable files")
    start = max(0, min(a.track - 1, len(tracks) - 1))
    if a.song:
        start = next((i for i, t in enumerate(tracks) if gd.song_matches(a.song, t["title"])
                      or gd.song_matches(a.song, os.path.basename(t["src"]))), None)
        if start is None:
            sys.exit(f"{doc['identifier']}: no track titled like {a.song!r}")
    mpv.start(detach=True)
    mpv.play([t["src"] for t in tracks], start)
    if a.volume is not None:
        state["volume"] = mpv.set_volume(a.volume)
    elif not mpv.adopted and state.get("volume") is not None:
        mpv.set_volume(state["volume"])
    write_state(show_state(state, doc, start))
    title = show_title(doc, meta)
    append_history({"ts": time.strftime("%Y-%m-%d %H:%M"), "show": title, "title": tracks[start]["title"],
                    "src": tracks[start]["src"], "how": tracks[start]["how"], "length": tracks[start].get("length"),
                    "doc": {k: doc.get(k) for k in ("identifier", "date", "collection", "kind", "lp", "artist", "title")},
                    "track": start})
    print(f"playing {KIND_SHORT.get(doc['kind'], doc['kind'])} {doc['identifier']}: {title}, from {start + 1}. {tracks[start]['title']}"
          f"  ({'adopted the running' if mpv.adopted else 'started an'} mpv; the TUI adopts it, poseidon play stop quits it)")


def cli_remote(argv):
    p = argparse.ArgumentParser(prog="poseidon remote", description="Serve the phone remote for the running mpv until Ctrl-C.")
    p.add_argument("--port", type=int, default=REMOTE_PORT)
    a = p.parse_args(argv)
    mpv = Mpv()
    mpv.start(detach=True)

    def describe():
        pl = mpv.get("playlist") or []
        st = load_state()
        q = st.get("queue") or {}
        titles = [t.get("title") or "" for t in q.get("tracks") or []]
        if len(titles) != len(pl):
            titles = [os.path.basename(urllib.parse.unquote(e.get("filename") or "")) for e in pl]
        return {"title": q.get("title") or (st.get("date") or "") + " " + (st.get("identifier") or "") if pl else "",
                "tracks": titles, "radio": st.get("last") == "radio"}
    r = Remote(mpv, describe, port=a.port)
    r.start()
    print(f"remote at {r.url()}  ({'adopted the running' if mpv.adopted else 'started an idle'} mpv; Ctrl-C stops serving)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        r.shutdown()


def on_signal(signum, frame):
    """A kill unwinds like a Ctrl-C.

    Without this a SIGTERM stops the process dead: the show's parec child is orphaned,
    the position of what was playing is never written, and curses never hands the
    terminal back -- the shell it was killed from is left with no echo and no cursor.
    KeepAwake used to leave the screen saver switched off this way too. The UI loop
    already treats a KeyboardInterrupt as quit, so raise one in the main thread and let
    every finally: on the way out do its job.
    """
    raise KeyboardInterrupt


def main():
    argv = sys.argv[1:]
    if argv and argv[0] == "play":
        return cli_play(argv[1:])
    if argv and argv[0] == "remote":
        return cli_remote(argv[1:])
    if os.environ.get("TERM", "").startswith("tmux"):
        os.environ.setdefault("ESCDELAY", "25")
    for sig in (signal.SIGTERM, signal.SIGHUP):
        try:
            signal.signal(sig, on_signal)
        except (ValueError, OSError, AttributeError):
            pass                              # not the main thread, or no such signal here
    try:
        still = curses.wrapper(lambda scr: App(scr).run())
    except KeyboardInterrupt:                 # a kill before the UI loop was up
        return
    for ident, p, log in still:
        print(f"still fetching {ident} in the background; log: {log}")


if __name__ == "__main__":
    main()
