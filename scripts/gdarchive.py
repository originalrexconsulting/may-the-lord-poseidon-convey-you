#!/usr/bin/env python3
"""gdarchive.py - search and download Grateful Dead shows from archive.org.

Stock python3 only (urllib, json). No pip installs.

Facts about the archive.org Grateful Dead collection that shape this tool:

  * Soundboard (SBD) and matrix items are "stream only". Their lossless
    originals (FLAC/SHN) return HTTP 401 on download. The VBR MP3 and Ogg
    derivatives that the web player uses ARE downloadable, so --format best
    silently falls back to mp3 for those items and says so.
  * Audience (AUD) items are fully downloadable, lossless (FLAC or SHN).
  * SHN (Shorten) plays fine with mpv/ffmpeg. Convert with `shntool conv -o flac`.
  * Most taper FLACs carry no tags, so players index them with blank titles.
    After download, FLAC/MP3/OGG files are tagged (title, artist, album, date,
    track) from the item's file list. Tagging changes the file's byte md5, so the
    archive md5 is stored in a GDARCHIVE_MD5 tag and used on later runs to
    recognise the file as verified. The taper's .ffp audio fingerprints are
    unaffected. SHN cannot hold tags, so SHN downloads are converted to FLAC
    (ffmpeg, decoded audio compared before the .shn is removed) unless
    --keep-shn is given. `convert` does the same for shows already on disk.

Examples:

  # top-rated shows containing Jack Straw, any source, 1977
  gdarchive.py search --song "Jack Straw" --year 1977 --min-reviews 5

  # every SBD Jack Straw from 1981, as mp3 (SBD = stream only)
  gdarchive.py songs --song "Jack Straw" --year 1981 --source sbd

  # every Jack Straw from 1977, one per show, matrix > sbd > aud (default --prefer)
  gdarchive.py songs --song "Jack Straw" --year 1977

  # whole show, lossless if the item allows it
  gdarchive.py fetch gd1981-03-14.nak700.glassberg.motb.84826.sbeok.flac16

  # what's in an item, and what can actually be downloaded
  gdarchive.py show gd77-05-08.sbd.hicks.4982.sbeok.shnf

  # direct URLs for mpv:  gdarchive.py urls ID --song "Jack Straw" | xargs mpv
"""

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_SEARCH = "https://archive.org/advancedsearch.php"
API_META = "https://archive.org/metadata/"
DL_BASE = "https://archive.org/download/"
DEFAULT_DEST = os.path.expanduser("~/projects/audiophile/dead")
# archive.org collection -> subdirectory of DEFAULT_DEST for whole shows.
# "JGB" is Melvin Seals & JGB (1996 on): the band Jerry left behind. Jerry's own
# Garcia Band tapes were removed from archive.org at the estate's request.
COLLECTION_DIRS = {"GratefulDead": "shows", "JGB": "jgb", "album_recordings": "lp"}
DEFAULT_COLLECTION = "GratefulDead"


def collection_dir(coll):
    """Subdirectory for an item's collection list (or a single collection name)."""
    if isinstance(coll, str):
        coll = [coll]
    for c in coll or []:
        if c in COLLECTION_DIRS:
            return COLLECTION_DIRS[c]
    return COLLECTION_DIRS[DEFAULT_COLLECTION]
UA = "gdarchive.py/1.0 (+https://github.com/; home audio library tool)"

LOSSLESS = (".flac", ".shn")
LOSSY = (".mp3", ".ogg")
AUDIO = LOSSLESS + LOSSY
FORMAT_ORDER = {"best": [".flac", ".shn", ".mp3", ".ogg"],
                "flac": [".flac"], "shn": [".shn"], "mp3": [".mp3"], "ogg": [".ogg"],
                "lossless": [".flac", ".shn"]}


# --------------------------------------------------------------------------- http

def _get(url, timeout=60, retries=3):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=timeout)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            if isinstance(e, urllib.error.HTTPError) and e.code in (401, 403, 404):
                raise
            time.sleep(2 * (attempt + 1))
    raise last


def _json(url):
    with _get(url) as r:
        return json.load(r)


def metadata(identifier):
    return _json(API_META + urllib.parse.quote(identifier))


# --------------------------------------------------------------------------- model

def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def song_matches(song, title):
    """True if `song` appears in track title, ignoring punctuation and segue marks."""
    return norm(song) in norm(title)


def source_kind(meta_or_doc):
    """Classify an item as sbd / aud / matrix / other.

    Identifier tokens win over free-text source notes, because AUD tapers often
    mention "sbd patch" in their lineage and SBD seeders mention "aud patches".
    """
    ident = (meta_or_doc.get("identifier") or "").lower()
    src = str(meta_or_doc.get("source") or "").lower()
    coll = meta_or_doc.get("collection") or []
    if isinstance(coll, str):
        coll = [coll]
    if re.search(r"\b(matrix|mtx)\b", ident.replace(".", " ")):
        return "matrix"
    if re.search(r"\b(sbd|dsbd|prefm|orefm|fm)\b", ident.replace(".", " ").replace("-", " ")):
        return "sbd"
    if re.search(r"\b(aud|nak\w*|schoeps|senn\w*|beyer\w*|akg\w*|sony\w*|ecm\w*|fob|dfc)\b", ident.replace(".", " ").replace("-", " ")):
        return "aud"
    if "matrix" in src:
        return "matrix"
    if ("audience" in src or re.search(r"\baud\b", src)
            or re.search(r"nakamichi|schoeps|beyer|sennheiser|\bakg\b|shure|neumann|b&k|\becm-?\d|\bmics?\b|taped by|recorded by", src)):
        return "aud"
    if "soundboard" in src or re.search(r"\b(sbd|dsbd)\b", src):
        return "sbd"
    if "stream_only" in coll:
        return "sbd"
    return "other"


def is_stream_only(meta):
    coll = meta.get("metadata", {}).get("collection") or []
    if isinstance(coll, str):
        coll = [coll]
    return "stream_only" in coll or str(meta.get("metadata", {}).get("access-restricted-item")) == "true"


def audio_files(meta):
    """Audio files from an item, annotated with .ext, .title, .track index."""
    out = []
    for f in meta.get("files", []):
        name = f["name"]
        ext = os.path.splitext(name)[1].lower()
        if ext not in AUDIO or os.path.splitext(name)[0].endswith("_sample"):
            continue  # archive.org LP items carry 30 s _sample.mp3 previews
        out.append({**f, "ext": ext, "title": f.get("title") or os.path.splitext(os.path.basename(name))[0],
                    "track": f.get("track")})
    out.sort(key=lambda f: (f["ext"], f["name"]))
    return out


def choose_files(meta, fmt="best", song=None):
    """Pick one file per track in the preferred format that is actually downloadable."""
    stream_only = is_stream_only(meta)
    order = FORMAT_ORDER[fmt]
    if stream_only:
        order = [e for e in order if e in LOSSY]
        if not order:
            return [], stream_only, None
    files = audio_files(meta)
    by_ext = {}
    for f in files:
        by_ext.setdefault(f["ext"], []).append(f)
    for ext in order:
        chosen = by_ext.get(ext)
        if chosen:
            if song:
                chosen = [f for f in chosen if song_matches(song, f["title"]) or song_matches(song, f["name"])]
            return chosen, stream_only, ext
    return [], stream_only, None


# --------------------------------------------------------------------------- search

def build_query(args):
    q = [f"collection:{getattr(args, 'collection', None) or DEFAULT_COLLECTION}", "mediatype:etree"]
    if getattr(args, "year", None):
        q.append(f"date:[{args.year}-01-01 TO {args.year}-12-31]")
    if getattr(args, "date", None):
        q.append(f"date:{args.date}")
    if getattr(args, "song", None):
        q.append(f'description:("{args.song}")')
    if getattr(args, "min_rating", None):
        q.append(f"avg_rating:[{args.min_rating} TO 5]")
    if getattr(args, "min_reviews", None):
        q.append(f"num_reviews:[{args.min_reviews} TO *]")
    if getattr(args, "source", None) == "aud":
        q.append("NOT collection:stream_only")
    if getattr(args, "downloadable", False):
        q.append("NOT collection:stream_only")
    if getattr(args, "query", None):
        q.append(f"({args.query})")
    return " AND ".join(q)


def search(args):
    q = build_query(args)
    docs, page = [], 1
    while len(docs) < args.limit:
        params = {"q": q, "fl[]": ["identifier", "date", "title", "avg_rating", "num_reviews", "downloads",
                                   "source", "collection", "venue", "coverage", "format"],
                  "rows": min(1000, args.limit - len(docs)), "page": page, "output": "json", "sort[]": args.sort}
        resp = _json(API_SEARCH + "?" + urllib.parse.urlencode(params, doseq=True))["response"]
        docs.extend(resp["docs"])
        if len(docs) >= resp["numFound"] or not resp["docs"]:
            break
        page += 1
    for d in docs:
        d["kind"] = source_kind(d)
        d["date"] = (d.get("date") or "")[:10]
    if getattr(args, "source", None) and args.source != "any":
        docs = [d for d in docs if d["kind"] == args.source]
    return q, docs


def verify_song(docs, song, workers=6):
    """Confirm via file metadata which items really have a track titled `song`."""
    def one(d):
        try:
            m = metadata(d["identifier"])
        except Exception as e:
            d["error"] = str(e)
            return d
        files, so, ext = choose_files(m, "best", song)
        d["stream_only"] = so
        d["tracks"] = [{"name": f["name"], "title": f["title"], "size": int(f.get("size") or 0)} for f in files]
        d["ext"] = ext
        d["lossless_avail"] = any(f["ext"] in LOSSLESS for f in audio_files(m))
        return d
    with cf.ThreadPoolExecutor(workers) as ex:
        return list(ex.map(one, docs))


def cmd_search(args):
    q, docs = search(args)
    if args.song:
        docs = [d for d in verify_song(docs, args.song) if d.get("tracks")]
    if args.json:
        json.dump(docs, sys.stdout, indent=1)
        return
    print(f"# query: {q}", file=sys.stderr)
    print(f"# {len(docs)} items", file=sys.stderr)
    print(f"{'date':10} {'kind':6} {'rate':4} {'rev':>4} {'dl':>7}  identifier")
    for d in docs:
        rating = d.get("avg_rating")
        rating = f"{float(rating):.2f}" if rating else "  - "
        line = f"{d['date']:10} {d['kind']:6} {rating:4} {d.get('num_reviews') or 0:>4} {d.get('downloads') or 0:>7}  {d['identifier']}"
        if args.song and d.get("tracks"):
            line += "   [" + "; ".join(t["title"] for t in d["tracks"]) + "]"
        print(line)


def rating_for(identifier):
    """avg_rating / num_reviews live in the search index, not in item metadata."""
    params = {"q": f'identifier:"{identifier}"', "fl[]": ["avg_rating", "num_reviews", "downloads"],
              "rows": 1, "output": "json"}
    try:
        docs = _json(API_SEARCH + "?" + urllib.parse.urlencode(params, doseq=True))["response"]["docs"]
        return docs[0] if docs else {}
    except Exception:
        return {}


def cmd_show(args):
    m = metadata(args.identifier)
    md = m["metadata"]
    md.update({k: v for k, v in rating_for(args.identifier).items() if v is not None})
    so = is_stream_only(m)
    print(f"identifier : {args.identifier}")
    print(f"title      : {md.get('title')}")
    print(f"date       : {md.get('date')}")
    print(f"venue      : {md.get('venue') or md.get('coverage')}")
    print(f"source     : {md.get('source')}")
    print(f"lineage    : {md.get('lineage')}")
    print(f"taper      : {md.get('taper')}")
    print(f"rating     : {md.get('avg_rating')} ({md.get('num_reviews')} reviews)")
    print(f"stream only: {so}  -> downloadable formats: {'mp3/ogg only' if so else 'flac/shn originals'}")
    files = audio_files(m)
    exts = sorted({f["ext"] for f in files})
    print(f"formats    : {' '.join(exts)}")
    shown = next((e for e in [".flac", ".shn", ".mp3", ".ogg"] if e in exts), None)
    total = 0
    print("tracks:")
    for f in files:
        if f["ext"] != shown:
            continue
        size = int(f.get("size") or 0)
        total += size
        length = f.get("length") or ""
        print(f"  {f['name']:40} {size/1e6:7.1f} MB  {length:>9}  {f['title']}")
    print(f"total ({shown}): {total/1e9:.2f} GB")


# --------------------------------------------------------------------------- download

def _md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(identifier, f, dest_path, verify=True, quiet=False):
    """Download one file with resume support and md5 verification. Returns True on success."""
    url = DL_BASE + urllib.parse.quote(identifier) + "/" + urllib.parse.quote(f["name"])
    size = int(f.get("size") or 0)
    want_md5 = f.get("md5")
    if os.path.exists(dest_path):
        untouched = not size or os.path.getsize(dest_path) == size
        if untouched and (not verify or not want_md5 or _md5(dest_path) == want_md5):
            if not quiet:
                print(f"  ok      {os.path.basename(dest_path)} (exists)")
            return True
        if want_md5 and stored_md5(dest_path) == want_md5:
            if not quiet:
                print(f"  ok      {os.path.basename(dest_path)} (exists, tagged)")
            return True
    elif dest_path.lower().endswith(".shn") and want_md5:
        flac = os.path.splitext(dest_path)[0] + ".flac"
        if os.path.exists(flac) and stored_md5(flac) == want_md5:
            if not quiet:
                print(f"  ok      {os.path.basename(flac)} (converted from shn)")
            return True
    part = dest_path + ".part"
    have = os.path.getsize(part) if os.path.exists(part) else 0
    headers = {"User-Agent": UA}
    if have and size and have < size:
        headers["Range"] = f"bytes={have}-"
    elif have >= size and size:
        have = 0
        os.remove(part)
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as r, open(part, "ab" if have else "wb") as out:
                if have and r.status != 206:
                    out.seek(0); out.truncate(); have = 0
                got = have
                t0 = time.time()
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
                    got += len(chunk)
                    if not quiet and size:
                        el = time.time() - t0 or 1e-6
                        print(f"\r  {got*100//size:3d}%  {os.path.basename(dest_path)}  {(got-have)/el/1e6:5.1f} MB/s", end="", flush=True)
            break
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                print(f"\n  DENIED  {f['name']} (HTTP {e.code}: stream-only item)")
                return False
            if e.code == 416:
                os.remove(part); have = 0; headers.pop("Range", None); continue
            print(f"\n  retry   {f['name']} (HTTP {e.code})")
            time.sleep(3 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            have = os.path.getsize(part) if os.path.exists(part) else 0
            headers["Range"] = f"bytes={have}-"
            print(f"\n  retry   {f['name']} ({e})")
            time.sleep(3 * (attempt + 1))
    else:
        return False
    if size and os.path.getsize(part) != size:
        print(f"\n  SIZE MISMATCH {f['name']}: {os.path.getsize(part)} != {size}")
        return False
    if verify and want_md5 and _md5(part) != want_md5:
        print(f"\n  MD5 MISMATCH {f['name']}")
        return False
    os.replace(part, dest_path)
    if not quiet:
        print(f"\r  done    {os.path.basename(dest_path)}{' '*30}")
    return True


# --------------------------------------------------------------------------- tags

ARTIST = "Grateful Dead"
MD5_TAG = "GDARCHIVE_MD5"


def _open_tags(path):
    """Return a mutagen tag object for path, or None if the format can't be tagged."""
    try:
        import mutagen.flac, mutagen.oggvorbis, mutagen.easyid3, mutagen.mp3
    except ImportError:
        return None
    ext = os.path.splitext(path)[1].lower()
    if ext == ".flac":
        return mutagen.flac.FLAC(path)
    if ext == ".ogg":
        return mutagen.oggvorbis.OggVorbis(path)
    if ext == ".mp3":
        mutagen.easyid3.EasyID3.RegisterTXXXKey(MD5_TAG.lower(), MD5_TAG)
        try:
            return mutagen.mp3.EasyMP3(path)
        except mutagen.mp3.HeaderNotFoundError:
            return None
    return None


def stored_md5(path):
    """The archive.org md5 recorded in the file's tags when it was tagged, or None."""
    try:
        t = _open_tags(path)
        if t is None:
            return None
        v = t.get(MD5_TAG) or t.get(MD5_TAG.lower())
        return v[0] if v else None
    except Exception:
        return None


def show_tags(md, f, index, total):
    """Vorbis-style tag dict for track `f` of the item described by `md`."""
    date = (md.get("date") or "")[:10]
    venue = md.get("venue") or md.get("coverage") or ""
    return {"title": f["title"], "artist": ARTIST, "albumartist": ARTIST,
            "album": f"{date} {venue}".strip(), "date": date,
            "tracknumber": str(index), "tracktotal": str(total),
            "comment": "https://archive.org/details/" + md["identifier"]}


def tag_file(path, tags, archive_md5=None):
    """Write tags if they differ from what's in the file. Returns True if written."""
    ext = os.path.splitext(path)[1].lower()
    t = _open_tags(path)
    if t is None:
        return False
    want = dict(tags)
    if ext == ".mp3":
        # EasyID3 has no tracktotal or comment keys; ID3 encodes total as "n/total"
        want["tracknumber"] = f"{want['tracknumber']}/{want.pop('tracktotal')}"
        want.pop("comment", None)
    if archive_md5:
        want[MD5_TAG if ext != ".mp3" else MD5_TAG.lower()] = archive_md5
    changed = False
    for k, v in want.items():
        cur = t.get(k)
        if not cur or cur[0] != v:
            t[k] = v
            changed = True
    if changed:
        t.save()
    return changed


def _pcm_md5(path):
    """md5 of the decoded PCM stream, format independent."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "md5", "-"],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip().split("=")[-1]


def shn_to_flac(shn_path, tags=None, archive_md5=None, keep=False):
    """Losslessly convert one .shn to .flac beside it, tag it, verify, remove the .shn.

    Returns the .flac path, or None on failure (the .shn is left untouched)."""
    flac_path = os.path.splitext(shn_path)[0] + ".flac"
    tmp = flac_path + ".part"
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", shn_path, "-c:a", "flac", "-f", "flac", tmp],
                       capture_output=True, text=True, check=True)
        if _pcm_md5(shn_path) != _pcm_md5(tmp):
            print(f"  AUDIO MISMATCH after conversion: {os.path.basename(shn_path)}")
            os.remove(tmp)
            return None
        os.replace(tmp, flac_path)
        if tags:
            tag_file(flac_path, tags, archive_md5)
        if not keep:
            os.remove(shn_path)
        return flac_path
    except subprocess.CalledProcessError as e:
        print(f"  CONVERT FAILED {os.path.basename(shn_path)}: {e.stderr.strip()[-200:]}")
        if os.path.exists(tmp):
            os.remove(tmp)
        return None


def convert_show(outdir, m, keep=False):
    """Convert every .shn in a show directory that matches the item's file list."""
    md = m["metadata"]
    files = [f for f in audio_files(m) if f["ext"] == ".shn"]
    n = 0
    for i, f in enumerate(files, 1):
        shn = os.path.join(outdir, os.path.basename(f["name"]))
        flac = os.path.splitext(shn)[0] + ".flac"
        if os.path.exists(flac) and stored_md5(flac) == f.get("md5"):
            continue
        if not os.path.exists(shn):
            continue
        print(f"\r  convert {os.path.basename(shn)}", end="", flush=True)
        if shn_to_flac(shn, show_tags(md, f, i, len(files)), f.get("md5"), keep=keep):
            n += 1
    if n:
        print(f"\r  converted {n} shn -> flac{' ' * 30}")
    return n


def show_dir(dest, meta):
    md = meta["metadata"]
    date = (md.get("date") or "0000-00-00")[:10]
    return os.path.join(dest, collection_dir(md.get("collection")), date[:4], f"{date}.{md['identifier']}")


def fetch_item(identifier, dest, fmt="best", song=None, verify=True, dry_run=False, tag=True, keep_shn=False):
    m = metadata(identifier)
    md = m["metadata"]
    files, so, ext = choose_files(m, fmt, song)
    date = (md.get("date") or "")[:10]
    label = f"{date} {md.get('venue') or md.get('coverage') or ''} [{identifier}]"
    if not files:
        why = "stream-only item; only mp3/ogg derivatives are downloadable" if so else "no files match"
        print(f"SKIP {label}: {why} (format={fmt}, song={song})")
        return 0
    if so and ext in LOSSY and fmt in ("best", "lossless", "flac", "shn"):
        print(f"NOTE {label}: stream-only item, falling back to {ext[1:]} derivative")
    if song:
        outdir = os.path.join(dest, "songs", re.sub(r"\s+", "-", norm(song)))
    else:
        outdir = show_dir(dest, m)
    total = sum(int(f.get("size") or 0) for f in files)
    print(f"{'DRY ' if dry_run else ''}FETCH {label}: {len(files)} x {ext[1:]} = {total/1e6:.0f} MB -> {outdir}")
    if dry_run:
        for f in files:
            print(f"    {f['name']:40} {int(f.get('size') or 0)/1e6:7.1f} MB  {f['title']}")
        return 0
    os.makedirs(outdir, exist_ok=True)
    n = tagged = 0
    for i, f in enumerate(files, 1):
        if song:
            slug = re.sub(r"\s+", "-", norm(f["title"]))[:60]
            name = f"{date}_{slug}_{identifier}{ext}"
        else:
            name = os.path.basename(f["name"])
        path = os.path.join(outdir, name)
        if download(identifier, f, path, verify=verify):
            n += 1
            if tag and ext != ".shn":
                try:
                    tagged += tag_file(path, show_tags(md, f, i, len(files)), f.get("md5"))
                except Exception as e:
                    print(f"  TAG FAILED {name}: {e}")
    if tagged:
        print(f"  tagged  {tagged} file(s)")
    if ext == ".shn" and not song and not keep_shn:
        convert_show(outdir, m)
    if not song:
        # keep the taper's info/txt files and a metadata snapshot next to the audio
        for f in m.get("files", []):
            if f["name"].lower().endswith((".txt", ".md5", ".ffp", ".nfo")) and "/" not in f["name"]:
                download(identifier, f, os.path.join(outdir, f["name"]), verify=verify, quiet=True)
        with open(os.path.join(outdir, "archive-metadata.json"), "w") as fh:
            json.dump({k: md.get(k) for k in ("identifier", "title", "date", "venue", "coverage", "source",
                                                "lineage", "taper", "transferer", "notes", "description",
                                                "avg_rating", "num_reviews", "collection")}, fh, indent=1)
    return n


def cmd_fetch(args):
    for ident in args.identifier:
        fetch_item(ident, args.dest, args.format, args.song, verify=not args.no_verify, dry_run=args.dry_run,
                   tag=not args.no_tag, keep_shn=args.keep_shn)


def doc_lossless_downloadable(d):
    """From search-index fields alone: has FLAC/SHN and is not stream-only."""
    fmts = d.get("format") or []
    if isinstance(fmts, str):
        fmts = [fmts]
    coll = d.get("collection") or []
    if isinstance(coll, str):
        coll = [coll]
    has_lossless = any(f.lower() in ("flac", "24bit flac", "shorten") for f in fmts)
    return has_lossless and "stream_only" not in coll


def cmd_songs(args):
    if not args.song:
        sys.exit("--song is required")
    q, docs = search(args)
    print(f"# query: {q}  ({len(docs)} candidate items)", file=sys.stderr)
    if args.all_sources:
        chosen = [d for d in verify_song(docs, args.song) if d.get("tracks")]
    else:
        # Rank per show date from search-index fields, then verify candidates in
        # rank order until one actually contains the track. One metadata call per
        # date in the common case instead of one per item.
        prefer = [k.strip() for k in args.prefer.split(",") if k.strip()]

        def rank(d):
            kind_rank = -prefer.index(d["kind"]) if d["kind"] in prefer else -len(prefer)
            lossless = doc_lossless_downloadable(d)
            return ((lossless, kind_rank) if args.lossless_first else (kind_rank, lossless),
                    float(d.get("avg_rating") or 0), int(d.get("num_reviews") or 0))

        by_date = {}
        for d in docs:
            by_date.setdefault(d["date"], []).append(d)

        def pick(cands):
            # popular dates have dozens of seeds; the unrated tail is never the best pick
            for d in sorted(cands, key=rank, reverse=True)[:args.max_candidates]:
                v = verify_song([d], args.song)[0]
                if v.get("tracks"):
                    return v
            return None

        with cf.ThreadPoolExecutor(6) as ex:
            chosen = [d for d in ex.map(pick, by_date.values()) if d]
        chosen.sort(key=lambda d: d["date"])
    print(f"# {len(chosen)} shows with '{args.song}'", file=sys.stderr)
    for d in chosen:
        fetch_item(d["identifier"], args.dest, args.format, args.song, verify=not args.no_verify, dry_run=args.dry_run,
                   tag=not args.no_tag, keep_shn=args.keep_shn)


def cmd_convert(args):
    for ident in args.identifier:
        m = metadata(ident)
        outdir = show_dir(args.dest, m)
        if not os.path.isdir(outdir):
            print(f"SKIP {ident}: {outdir} not found")
            continue
        print(f"CONVERT {ident} -> {outdir}")
        convert_show(outdir, m, keep=args.keep_shn)


def cmd_urls(args):
    m = metadata(args.identifier)
    files, so, ext = choose_files(m, args.format, args.song)
    for f in files:
        print(DL_BASE + urllib.parse.quote(args.identifier) + "/" + urllib.parse.quote(f["name"]))


# --------------------------------------------------------------------------- cli

def add_search_args(p):
    p.add_argument("--collection", default=DEFAULT_COLLECTION, choices=["GratefulDead", "JGB"],
                   help="archive.org collection: GratefulDead (default) or JGB (Melvin Seals & JGB, 1996 on)")
    p.add_argument("--year", type=int)
    p.add_argument("--date", help="YYYY-MM-DD")
    p.add_argument("--song", help="track title to look for, e.g. 'Jack Straw'")
    p.add_argument("--source", choices=["sbd", "aud", "matrix", "any"], default="any")
    p.add_argument("--min-rating", type=float)
    p.add_argument("--min-reviews", type=int)
    p.add_argument("--downloadable", action="store_true", help="exclude stream-only items")
    p.add_argument("--query", help="extra raw Lucene query, e.g. 'venue:(Cornell)'")
    p.add_argument("--sort", default="date asc", help="e.g. 'avg_rating desc', 'num_reviews desc', 'date asc'")
    p.add_argument("--limit", type=int, default=500)


def add_fetch_args(p):
    p.add_argument("--dest", default=DEFAULT_DEST)
    p.add_argument("--format", choices=list(FORMAT_ORDER), default="best")
    p.add_argument("--no-verify", action="store_true", help="skip md5 verification")
    p.add_argument("--no-tag", action="store_true", help="leave downloaded files untagged")
    p.add_argument("--keep-shn", action="store_true", help="do not convert downloaded .shn to tagged .flac")
    p.add_argument("--dry-run", "-n", action="store_true")


def main():
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("search", help="search the GratefulDead collection")
    add_search_args(p)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("show", help="describe one item and its tracks")
    p.add_argument("identifier")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("fetch", help="download whole shows (or --song tracks) by identifier")
    p.add_argument("identifier", nargs="+")
    p.add_argument("--song")
    add_fetch_args(p)
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("songs", help="search + download every matching track, e.g. all SBD Jack Straws from 1981")
    add_search_args(p)
    add_fetch_args(p)
    p.add_argument("--all-sources", action="store_true", help="fetch from every item per date, not just the best one")
    p.add_argument("--prefer", default="matrix,sbd,aud",
                   help="source kinds in order of preference when several items exist for a date (default: %(default)s)")
    p.add_argument("--max-candidates", type=int, default=8,
                   help="per show date, how many ranked items to check for the track before giving up")
    p.add_argument("--lossless-first", action="store_true",
                   help="rank a lossless-downloadable item above a preferred-kind item that is stream-only (mp3)")
    p.set_defaults(func=cmd_songs)

    p = sub.add_parser("convert", help="convert an already-downloaded SHN show to tagged FLAC")
    p.add_argument("identifier", nargs="+")
    p.add_argument("--dest", default=DEFAULT_DEST)
    p.add_argument("--keep-shn", action="store_true", help="keep the .shn files after conversion")
    p.set_defaults(func=cmd_convert)

    p = sub.add_parser("urls", help="print direct download/stream URLs (pipe to mpv)")
    p.add_argument("identifier")
    p.add_argument("--song")
    p.add_argument("--format", choices=list(FORMAT_ORDER), default="best")
    p.set_defaults(func=cmd_urls)

    args = ap.parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
