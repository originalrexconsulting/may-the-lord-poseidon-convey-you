#!/usr/bin/env python3
"""radio.py - lossless (FLAC) classical internet radio through Strawberry.

Stock python3 only. Needs ffprobe (probe/now) and a running Strawberry.

Plays a station in a Strawberry playlist tab called "Radio" so the current
playlist (usually a Dead show) is left alone. First run creates the tab;
later runs switch to it and replace its contents with the new station.
PipeWire follows the stream's rate, so a 48 kHz station (CRo D-dur) should
show rate: 48000 in /proc/asound/R20/pcm0p/sub0/hw_params. `now` checks that.

Stations were verified live with ffprobe between 2026-09-11 and 2026-09-20, the
later ones with a few seconds of mpv --ao=null each. (Dates are no longer per
tier: STATIONS is sorted by quality, so a tier is not a batch.) Dead ones:
Mother Earth Klassik (24/192, station closed), AZPM Classical 90.3 KUAT (HLS
FLAC, connection timed out from Oakland), Radio Klassik Stephansdom (I/O error),
WCRB Boston, WETA Washington, WRTI Philadelphia, WCLV Cleveland (every guessed
mount 404). KDFC's 256 kbps StreamTheWorld mount is gone for good ("Invalid
Mount"); KDFCFMAAC96 is what the station serves now. BBC Radio 3's 320 kbps
feed is UK-only (403 from here); the world feed is 96 kbps HE-AAC.

The piece (2026-10-04). A FLAC Icecast mount carries no in-band title, and HLS and
Radio France's AAC carry none either, so mpv's media-title is the filename and the
TUI's status line said "(no now-playing metadata on this stream)" through a whole
symphony. FEEDS names where each such station publishes the piece out of band, and
piece() fetches it (stock urllib, no key): the Icecast server's own status-json.xsl,
where the sibling MP3/AAC mount of the same programme carries the title the FLAC
mount lacks (Naim, Rondo Klasu, Sector); Triton's nowplaying XML (KDFC, KUSC);
Radio France's livemeta (France Musique and its webradios); WNYC's whats_on (WQXR,
Operavore); ABC's plays API; NPO Klassiek's tracks; BBC's segments; Czech Radio's
playlist API (D-dur and Vltava answer "quiet" more often than not). Identifying the
music by ear was looked at and dropped: AcoustID cannot match a clip from the middle
of a movement, by design, and the alternatives are unofficial or paid.

Examples:

  radio.py list                 # stations
  radio.py probe                # codec / rate / depth / now-playing for each
  radio.py title                # the piece on every station with a feed; title naim for one
  radio.py play naim            # start Naim Classical in the Radio tab
  radio.py play random          # any station, the dice decide
  radio.py now                  # what Strawberry plays + the DAC's actual rate
  radio.py back                 # return to the previous playlist tab
"""

import argparse
import datetime
import glob
import json
import os
import random
import re
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

try:
    import poseidon
    UA = poseidon.user_agent()
except Exception:                              # run from a copy without the dispatcher beside it
    UA = "may-the-lord-poseidon-convey-you (+https://github.com/originalrexconsulting/may-the-lord-poseidon-convey-you)"

STATIONS = {
    # key: (name, url, nominal format, notes)
    #
    # Ordered by what it sounds like, not by the printed number: AAC buys roughly
    # 1.5x MP3 at these rates, so AAC 192 outranks MP3 320. Lossless first, then
    # descending MP3-equivalent. A new station goes in the tier its codec and rate
    # put it in, never at the end. "home turf" is the one deliberate exception.
    # ---- lossless
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
    # ---- home turf: local, whatever the bitrate
    "kdfc": ("KDFC", "https://playerservices.streamtheworld.com/api/livestream-redirect/KDFCFMAAC96",
              "AAC 96/44.1", "San Francisco, Classical California. 96 kbps is all StreamTheWorld serves now."),
    "kusc": ("KUSC", "https://playerservices.streamtheworld.com/api/livestream-redirect/KUSCAAC96",
              "AAC 96/44.1", "Los Angeles, KDFC's sister station."),
    "king": ("Classical KING FM", "https://classicalking.streamguys1.com/king-fm-aac",
              "AAC 256/44.1", "Seattle. Best-sounding US stream in the list."),
    # ---- best lossy: AAC 192 and up, MP3 320
    "abc": ("ABC Classic", "https://streaming.abc-cdn.net.au/audio/hls/classicnsw.m3u8",
              "AAC 256/44.1", "Australia (Sydney feed), HLS. Daytime there is night here."),
    "fmusique": ("France Musique", "https://icecast.radiofrance.fr/francemusique-hifi.aac",
              "AAC 192/48", "Radio France's classical network, live concerts most evenings."),
    "fmbaroque": ("France Musique Baroque", "https://icecast.radiofrance.fr/francemusiquebaroque-hifi.aac",
              "AAC 192/48", "All baroque."),
    "fmconcerts": ("France Musique Concerts", "https://icecast.radiofrance.fr/francemusiqueconcertsradiofrance-hifi.aac",
              "AAC 192/48", "Radio France's own orchestras and choir, concert recordings only."),
    "fmopera": ("France Musique Opéra", "https://icecast.radiofrance.fr/francemusiqueopera-hifi.aac",
              "AAC 192/48", "Opera, whole works."),
    "fmclassiqueplus": ("France Musique Classique+", "https://icecast.radiofrance.fr/francemusiqueclassiqueplus-hifi.aac",
              "AAC 192/48", "The core repertoire, no talk."),
    "fmpianozen": ("France Musique Piano Zen", "https://icecast.radiofrance.fr/francemusiquepianozen-hifi.aac",
              "AAC 192/48", "Solo piano, all day."),
    "fmcontemporaine": ("France Musique Contemp.", "https://icecast.radiofrance.fr/francemusiquelacontemporaine-hifi.aac",
              "AAC 192/48", "Twentieth century onward."),
    "linn": ("Linn Classical", "http://radio.linn.co.uk:8004/autodj",
              "MP3 320/44.1", "Linn Records (Scotland): their own catalogue, so whole movements."),
    "rai3": ("Rai Radio 3", "https://icestreaming.rai.it/3.mp3",
              "MP3 320/44.1", "Italy's culture channel: classical, opera, spoken word between."),
    "musiq3": ("Musiq3", "https://radios.rtbf.be/musiq3-128.mp3",
              "MP3 320/44.1", "Belgian French-language classical (RTBF); mount says 128, serves 320."),
    # ---- MP3 256
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
    "baroque1fm": ("1.FM Otto's Baroque", "http://strm112.1.fm/baroque_mobile_mp3",
              "MP3 256/44.1", "All baroque, no talk; commercial, so the odd advert."),
    # ---- MP3 192
    "npo4": ("NPO Radio 4", "https://icecast.omroep.nl/radio4-bb-mp3",
              "MP3 192/48", "Dutch public classical."),
    "nrk": ("NRK Klassisk", "https://lyd.nrk.no/nrk_radio_klassisk_mp3_h",
              "MP3 192/48", "Norwegian public classical, little talk."),
    "oe1": ("Ö1", "https://orf-live.ors-shoutcast.at/oe1-q2a",
              "MP3 192/48", "Austrian public radio culture channel: Vienna's orchestras, spoken word between."),
    "rbb": ("rbbKultur", "https://dispatcher.rndfnk.com/rbb/rbbkultur/live/mp3/high",
              "MP3 192/48", "Berlin."),
    "klassikradio": ("Klassik Radio", "https://stream.klassikradio.de/live/mp3-192/",
              "MP3 192/44.1", "German commercial: light classics and film music, adverts."),
    # ---- MP3 128, and HE-AAC 96 (which sounds about the same)
    "bbc3": ("BBC Radio 3", "https://a.files.bbci.co.uk/ms6/live/3441A116-B12E-4D2F-ACA8-C1984642FA4B/audio/simulcast/hls/nonuk/pc_hd_abr_v2/ak/bbc_radio_three.m3u8",
              "AAC 96/48", "The world feed (HLS); the 320 one is UK-only. Proms in summer."),
    "wqxr": ("WQXR", "https://stream.wqxr.org/wqxr",
              "MP3 128/48", "New York."),
    "wfmt": ("WFMT", "https://wfmt.streamguys1.com/main-mp3",
              "MP3 128/48", "Chicago. Fine presenters."),
    "venice": ("Venice Classic Radio", "https://uk2.streamingpulse.com/ssl/vcr1",
              "MP3 128/44.1", "Italian, all-day chamber and baroque, no talk."),
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

FEEDS = {
    # key: (kind, arg). Where the station says what it is playing, outside the stream.
    # icecast: the server's status-json.xsl; arg is the sibling mount whose title to
    # take (the FLAC mount's own is empty). Verified 2026-10-04, each of these.
    "naim": ("icecast", "class-high"),
    "klasu": ("icecast", "klasu-hi"),
    "klasupro": ("icecast", "klasupro-hi"),
    "sector": ("icecast", "nota-160"),         # nota-mp3 showed another piece the same minute; check by ear
    "ddur": ("rozhlas", "d-dur"),              # answered "quiet" all afternoon; wired in hope
    "vltava": ("rozhlas", "vltava"),
    "kdfc": ("triton", "KDFCFMAAC96"),
    "kusc": ("triton", "KUSCAAC96"),
    "fmusique": ("radiofrance", 4),            # the music programmes list the piece; talk shows do not
    "fmclassiqueplus": ("radiofrance", 402),
    "fmconcerts": ("radiofrance", 403),
    "fmcontemporaine": ("radiofrance", 406),
    "fmbaroque": ("radiofrance", 408),         # Opéra and Piano Zen: no livemeta id found (401-440 scanned)
    "wqxr": ("wnyc", "wqxr"),
    "operavore": ("wnyc", "operavore"),
    "abc": ("abc", "classic"),
    "npo4": ("npo", None),
    "bbc3": ("bbc", "bbc_radio_three"),        # empty from here on 2026-10-04; may be UK-only or programme-bound
}
FEED_TIMEOUT = 8


def _fetch(url, timeout=FEED_TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _get_json(url, timeout=FEED_TIMEOUT):
    return json.loads(_fetch(url, timeout).decode("utf-8", "replace"))


def _clean(s):
    """A feed string fit for one status line: no double spaces, listener counts or trailing [place] notes."""
    s = re.sub(r"^\s*\d{1,2}\s*[-.]\s+", "", s or "")                 # Naim leads with the track number: "07 - "
    s = re.sub(r"\s*,?\s*Kuuntel\w*:\s*\d+\s*$", "", s)              # Rondo appends its listener count
    s = re.sub(r"\s*\[[^\]]*\]\s*$", "", s)                          # Sector appends "[Salzburg • ...]"
    s = re.sub(r"\s*\((1[0-9]{3}|20[0-9]{2})\s*-\s*(1[0-9]{3}|20[0-9]{2})?\)", "", s)   # composer dates
    return re.sub(r"\s+", " ", s).strip(" -·,")


def _names(v):
    """A string from the shapes feeds use for people: str, {name}, [{name}], [{musician: {name}}]."""
    if not v:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict):
        return _names(v.get("name") or v.get("musician") or v.get("title") or "")
    return ", ".join(n for n in (_names(x) for x in v) if n)


def _feed_icecast(key, mount):
    u = urllib.parse.urlsplit(STATIONS[key][1])
    d = _get_json(f"{u.scheme}://{u.netloc}/status-json.xsl")
    src = d.get("icestats", {}).get("source", [])
    for s in [src] if isinstance(src, dict) else src:
        if os.path.basename(urllib.parse.urlsplit(s.get("listenurl", "")).path).startswith(mount):
            raw = _clean((s.get("title") or "").replace("~", ": "))
            return {"raw": raw} if raw else None
    return None


def _feed_triton(_key, mount):
    xml = _fetch(f"https://np.tritondigital.com/public/nowplaying?mountName={mount}&numberToFetch=1&eventType=track")
    info = ET.fromstring(xml).find("nowplaying-info")
    if info is None:
        return None
    p = {e.get("name"): (e.text or "").strip() for e in info.findall("property")}
    until = None
    try:
        until = int(p["cue_time_start"]) / 1000 + float(p["cue_time_duration"])
    except (KeyError, ValueError):
        pass
    return {"composer": _clean(p.get("track_artist_name")), "work": _clean(p.get("cue_title")), "until": until}


def _feed_radiofrance(_key, sid):
    d = _get_json(f"https://api.radiofrance.fr/livemeta/pull/{sid}")
    now = time.time()
    steps = [s for s in d.get("steps", {}).values() if s.get("start", 0) <= now <= s.get("end", 0)]
    songs = [s for s in steps if s.get("embedType") == "song"] or []
    if not songs:
        return None
    s = max(songs, key=lambda s: s.get("depth", 0))
    return {"composer": _clean(s.get("composers")), "work": _clean(s.get("title")),
            "performers": _clean(s.get("performers") or ""), "album": _clean(s.get("titreAlbum")),
            "until": s.get("end")}


def _feed_wnyc(_key, slug):
    d = _get_json(f"https://api.wnyc.org/api/v1/whats_on/{slug}/")
    item = d.get("current_playlist_item") or {}
    ce = item.get("catalog_entry") or {}
    if not ce.get("title"):
        return None
    who = [_names(ce.get("soloists")), _names(ce.get("ensemble")), _names(ce.get("conductor"))]
    until = None
    if item.get("start_time_ts") and ce.get("length"):
        until = item["start_time_ts"] + ce["length"]
    return {"composer": _clean(_names(ce.get("composer"))), "work": _clean(ce["title"]),
            "performers": ", ".join(w for w in who if w), "album": _clean(_names(ce.get("reclabel"))), "until": until}


def _feed_abc(_key, service):
    d = _get_json(f"https://music.abcradio.net.au/api/v1/plays/{service}/now.json")
    s = (d.get("now") or {}).get("summary") or {}
    if not s.get("title"):
        return None
    until = None
    try:
        until = datetime.datetime.fromisoformat(d["next_updated"]).timestamp()
    except (KeyError, ValueError, TypeError):
        pass
    return {"composer": _clean(s.get("artist")), "work": _clean(s.get("title")),
            "performers": _clean((s.get("properties") or {}).get("performers")),
            "album": _clean((s.get("properties") or {}).get("label")), "until": until}


def _feed_npo(_key, _arg):
    d = _get_json("https://www.npoklassiek.nl/api/tracks")
    t = (d.get("data") or [None])[0]                                  # newest first
    if not t or not t.get("title"):
        return None
    until = None
    try:
        import zoneinfo
        until = datetime.datetime.fromisoformat(t["stopdatetime"]).replace(
            tzinfo=zoneinfo.ZoneInfo("Europe/Amsterdam")).timestamp()
        if until < time.time() - 30:
            return None                                               # the last track is over; nothing listed since
    except Exception:
        pass
    who = [t.get("soloistsEnsemble"), t.get("orchestra"), t.get("director")]
    composer = t.get("composer_name") or t.get("artist") or ""
    if "," in composer:                                               # "Mendelssohn-Bartholdy, Felix"
        last, first = composer.split(",", 1)
        composer = f"{first.strip()} {last.strip()}"
    if "[" in composer:                                               # "Anastasia [cello] Kobekina" is the soloist, whatever the field says
        who.insert(0, re.sub(r"\s*\[[^\]]*\]", "", composer))
        composer = ""
    return {"composer": _clean(composer), "work": _clean(t["title"]),
            "performers": ", ".join(_clean(w) for w in who if w), "album": _clean(t.get("label")), "until": until}


def _feed_bbc(_key, service):
    d = _get_json(f"https://rms.api.bbc.co.uk/v2/services/{service}/segments/latest")
    items = [i for i in d.get("data") or [] if (i.get("offset") or {}).get("now_playing", True)]
    if not items:
        return None
    t = items[0].get("titles") or {}
    return {"composer": _clean(t.get("primary")), "work": _clean(t.get("secondary")),
            "performers": _clean(t.get("tertiary"))}


def _feed_rozhlas(_key, sid):
    d = (_get_json(f"https://api.rozhlas.cz/data/v2/playlist/now/{sid}.json") or {}).get("data") or {}
    if d.get("status") == "quiet" or not (d.get("track") or d.get("title")):
        return None
    until = None
    try:
        until = datetime.datetime.fromisoformat(d["till"]).timestamp()
    except (KeyError, ValueError, TypeError):
        pass
    return {"composer": _clean(d.get("interpret") or d.get("composer")), "work": _clean(d.get("track") or d.get("title")),
            "until": until}


_FEED_KINDS = {"icecast": _feed_icecast, "triton": _feed_triton, "radiofrance": _feed_radiofrance,
               "wnyc": _feed_wnyc, "abc": _feed_abc, "npo": _feed_npo, "bbc": _feed_bbc, "rozhlas": _feed_rozhlas}


def piece(key, timeout=FEED_TIMEOUT):
    """What the station says it is playing, from its feed: {composer, work, performers, album, until, raw}.

    None when the station has no feed, the feed is quiet (talk, news, between pieces) or
    anything at all goes wrong: a status line must never trip over a web service. `until`
    is the epoch second the piece ends, when the feed knows, for the caller's next poll.
    `raw` is the station's own one-line string where it has no fields to split.
    """
    kind, arg = FEEDS.get(key, (None, None))
    if kind is None:
        return None
    try:
        p = _FEED_KINDS[kind](key, arg)
    except Exception:
        return None
    if not p or not (p.get("raw") or p.get("work")):
        return None
    out = {"composer": "", "work": "", "performers": "", "album": "", "until": None, "raw": ""}
    out.update({k: v for k, v in p.items() if v})
    out["kind"] = kind
    return out


def fmt_piece(p):
    """One line: 'Composer: Work · performers', or the station's own string."""
    if not p:
        return ""
    if p.get("raw") and not p.get("work"):
        return p["raw"]
    s = f"{p['composer']}: {p['work']}" if p.get("composer") else p["work"]
    return s + (f"  ·  {p['performers']}" if p.get("performers") else "")


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


def station_key(key):
    """The STATIONS key for what station() accepts (a key, a unique substring, random)."""
    s = station(key)
    return next(k for k, v in STATIONS.items() if v is s)


def cmd_probe(args):
    keys = [station_key(args.station)] if args.station else list(STATIONS)
    for k in keys:
        name, url, fmt, _ = STATIONS[k]
        kv, err = ffprobe(url)
        line = f"{name:24} {'DOWN: ' + err if err else fmt_probe(kv)}"
        p = piece(k)
        print(line + (f"  piece: {fmt_piece(p)}" if p else ""))


def cmd_title(args):
    """The piece on each station with a feed, the way the TUI's status line shows it."""
    keys = [station_key(args.station)] if args.station else [k for k in STATIONS if k in FEEDS]
    for k in keys:
        name = STATIONS[k][0]
        if k not in FEEDS:
            print(f"{name:24} (no feed; the stream's own title is all there is)")
            continue
        p = piece(k)
        if not p:
            print(f"{name:24} (quiet, or the feed did not answer)")
            continue
        print(f"{name:24} {fmt_piece(p)}")
        extra = [f"album: {p['album']}" if p.get("album") else "",
                 f"ends {time.strftime('%H:%M:%S', time.localtime(p['until']))}" if p.get("until") else ""]
        if any(extra):
            print(f"{'':24} {'  '.join(e for e in extra if e)}")


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
    p = sub.add_parser("title", help="the piece playing, from the station's feed")
    p.add_argument("station", nargs="?")
    p.set_defaults(fn=cmd_title)
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
