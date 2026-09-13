# May The Lord Poseidon Convey You

A terminal player for the archive.org Grateful Dead collection, and the audio
plumbing around it. Stock Python 3 (curses), mpv, PipeWire. No pip.

```
scripts/May-The_Lord_Poseidon-Convey-You.py   # the TUI (scripts/deadtui.py is a symlink)
scripts/gdarchive.py                          # search and download shows, tag them, shn -> flac
scripts/deadviz.py                            # the light show: 15 modes, one of them is Poseidon
scripts/radio.py                              # lossless classical radio stations
scripts/restore-playlist.py                   # snapshot / restore the mpv playlist
```

The TUI browses years, dates, sources and tracks; plays local FLAC when a show
has been fetched and streams otherwise; has JGB, Firesign Theatre, Jokes,
Tears, Rain and Snow, Random show, a memory set list, History and Now Playing;
adopts an mpv it finds already running (q keeps the music, Q stops it); and
starts with Poseidon, trident raised.

`SYSTEM.md` is the reference: the setup, every key, every script, and the
facts about archive.org that shape what you get (soundboards stream only,
audience tapes download lossless). `AUDIO-ANSIBLE.md` is the spec for the
PipeWire side.

MIT license.
