# May The Lord Poseidon Convey You

A terminal player for the archive.org Grateful Dead collection, and the audio
plumbing around it. Stock Python 3 (curses), mpv, PipeWire. No pip: run the scripts
from a clone, or download one self-contained build from
[Releases](https://github.com/originalrexconsulting/may-the-lord-poseidon-convey-you/releases).

It looks like a toy and it is a listening rig. The purpose is more serious than the
light show suggests: play good music as losslessly as the source allows, and make
choosing it instant. Fetched shows play as FLAC from disk, streams take the FLAC
source when the archive offers one, and PipeWire follows the file's rate to the DAC
instead of resampling (`AUDIO-ANSIBLE.md` is that setup). Picking a show is a keypress
in a terminal that already has the list: no web page, no phone app, nothing that
thinks for a second before every screen. Everything else here sits on top of that.

```
scripts/poseidon.py                           # one door to every tool: bare = the TUI,
                                              # poseidon gdarchive|deadviz|radio|restore-playlist ..., poseidon doctor,
                                              # poseidon play 1977-05-08 (no TUI; random, an identifier, radio <station>, stop),
                                              # poseidon remote (the phone remote for a player started that way)
scripts/May-The_Lord_Poseidon-Convey-You.py   # the TUI (scripts/deadtui.py is a symlink)
scripts/gdarchive.py                          # search and download shows, tag them, shn -> flac
scripts/deadviz.py                            # the light show: 24 modes; Poseidon, Enik, Polyphemus, the voyage home, Athena's owl, Althea,
                                              # the strait of Scylla, the Sleestak, the Stealie, the Wall of Sound
scripts/radio.py                              # lossless classical radio stations
scripts/restore-playlist.py                   # snapshot / restore the mpv playlist
```

The TUI browses years, dates, sources and tracks; plays local FLAC when a show
has been fetched and streams otherwise; has JGB (Jerry's own bands, 1970-1995), Firesign
Theatre, Jokes, Tears, Dark Star, Not Fade Away, Seastones (Phil and Ned's 1974 experiments),
Rain and Snow, Random show, This day (every show played on today's date, any year), Tours
(Europe '72, the Wall of Sound, May '77, Egypt, Spring '90... a random night or the whole
run in order), On the air (the Grateful Dead Hour, Dead to the World, the KFOG New Year's
broadcast), History, Bookmarks (`*` pins a show or the second you are at), Stats (what
History adds up to) and Now Playing; shows the taper's notes and the reviews of any source
(`i`); has a sleep timer that fades the gain over its last minute (`t`) and a phone
remote on the LAN (`R`: play, pause, next, seek, volume, sleep and the queue on one page);
adopts an mpv it finds already running (q keeps the music, Q stops it); and starts with
Poseidon, trident raised. `poseidon play 1977-05-08` plays without the TUI, so cron can
run `poseidon play random` at seven and `poseidon play stop` at eight.

## Screenshots

The splash, two seconds of the Earth Shaker:

<img src="docs/screenshots/splash.svg" width="420" alt="splash screen: Poseidon, crowned, trident raised">

The home screen with Barton Hall playing, and a show:

<img src="docs/screenshots/home.svg" width="900" alt="home screen: Now, The Dead, Not Dead, Everything; Morning Dew playing">
<img src="docs/screenshots/tracks.svg" width="900" alt="5/8/77 Barton Hall, Loser playing">

This day (every show played on today's date), Tours, and May '77 night by night:

<img src="docs/screenshots/thisday.svg" width="900" alt="This day: the seven September 14ths, 1974 Munich to 1993 Philadelphia">
<img src="docs/screenshots/tours.svg" width="900" alt="Tours: fifteen runs from Fillmore West '69 to Europe '90">
<img src="docs/screenshots/tour.svg" width="900" alt="May '77: a random night, the whole run, then the 23 nights">

The taper's notes and the reviews of a source (`i`), and the stats History adds up to:

<img src="docs/screenshots/notes.svg" width="900" alt="notes on the 5/11/77 Charlie Miller soundboard: source, lineage, notes, setlist, reviews">
<img src="docs/screenshots/stats.svg" width="900" alt="Stats: tracks, hours, most played songs, years, shows, the longest Dark Star heard">

Now Playing (w), the sleep timer (t) counting down in the status line, the phone remote's
address (R), On the air, Bookmarks:

<img src="docs/screenshots/queue.svg" width="900" alt="the current playlist, Morning Dew marked">
<img src="docs/screenshots/sleep.svg" width="900" alt="the status line with the sleep timer: 30 minutes to go">
<img src="docs/screenshots/remote.svg" width="900" alt="the remote's URL in the message line">
<img src="docs/screenshots/onair.svg" width="900" alt="On the air: the Grateful Dead Hour, the KFOG broadcast, Dead to the World">
<img src="docs/screenshots/bookmarks.svg" width="900" alt="Bookmarks: two pinned nights">

The Jokes menu and the radio list:

<img src="docs/screenshots/jokes.svg" width="900" alt="Jokes: the battery bit and sixteen comedy LPs">
<img src="docs/screenshots/radio.svg" width="900" alt="classical radio stations">

In the light show, `v` cycles the modes forward and `V` backward, so from the first
mode `V` walks through the newest ones: the Wall of Sound, the Stealie, the Sleestak, the strait,
Althea, Athena's owl, the voyage, Polyphemus, Enik, Poseidon.

The Poseidon mode: the bass raises the swell, a beat shakes the earth, and the cast
drops by.

<img src="docs/screenshots/poseidon.svg" width="900" alt="Poseidon swims a night sea; a shark, a dolphin and a jellyfish pass">

Enik the Altrusian, head to foot and moving the way the costume did:
the bass opens the time doorway behind him, the crystal matrix lights one crystal per
band, and a beat flashes his eyes.

<img src="docs/screenshots/enik.svg" width="900" alt="Enik, mid-step, arms out, the crystal matrix lit in the corner">

Polyphemus at home: Poseidon's son, and the reason the Lord Poseidon conveys nobody. He breathes with the bass, his eye follows the loudest band, and on a
big beat he picks a man out of the flock. Leave the music off long enough and Nobody
comes for him.

<img src="docs/screenshots/cyclops.svg" width="900" alt="Polyphemus reclined in his cave, sheep and a man at his feet, one tally mark on the wall">

May the Lord Poseidon convey you: the voyage Polyphemus promised. The black ship rows
west toward Ithaca, faster the louder the music. On a big beat the Earth Shaker rises
ahead of it and conveys it his way, a wave that throws it back and takes a companion.
Lose them all and Odysseus is alone on a raft. Reach Ithaca and the Cyclops sees him
off again, boulder and all.

<img src="docs/screenshots/convey.svg" width="900" alt="the black ship on the night sea, Poseidon rising ahead of it with the trident">

Athena, grey-eyed, as her owl on an olive branch under the moon over the Parthenon. The
wings are the spectrum, one feather per band, fanning open as the music gets loud and
snapping wide on a beat; the grey eyes give light with the music, brightest on a beat, the
moon their catchlight; they dilate with the bass and follow the stereo balance; the
head snaps toward the loudest band the way an owl's does. The body dances: a sway on the
beat from foot to foot, the far wing lifting against the lean like a dancer's arm, a dip
and a spring back taller, the head held steady above it. The olive bough is a real one,
rooted off the left edge and whippy at the tip, in a wind that gusts harder with the
music: it bends, springs back, the twigs bend further and the leaves flutter, and she
rides it, talons hooked under the wood, dancing on top of the sway. Land a beat and the
bough gives under her.
Quiet music, and it asks the
only question an owl asks. The answer here is Nobody.

<img src="docs/screenshots/athena.svg" width="900" alt="Athena's owl, wings spread wide, each feather a band of the spectrum">

Althea is not Athena. Athena is the grey-eyed goddess of wisdom, the owl above. Althea
is the healer: the name is the Greek Althaea, from *althainein*, to heal, and the
marshmallow, Althaea officinalis, is the old healing herb, hollyhock's cousin. In the
myth she is queen of Calydon and Meleager's mother, who took the half-burnt brand off
the fire when the Fates said her son would live only as long as it did, and kept it in
a chest for years. Hunter's Althea is the first kind, the one who tells you to cool
down, settle back, easy Jim. So the mode has her at the hearth in Calydon with the
brand. The fire is the spectrum, one flame per band; the log's ember glows with the
bass, sparks fly on a beat, smoke thickens with the mids, and hollyhocks bloom either
side on the treble. She dances seated, hair a beat behind her shoulders, one hand
keeping time on her knee. Music too hot for too long and she draws the brand out and
raises a palm; when it settles she puts it back. Silence, and she stirs the embers.

The strait is the next chapter of the voyage. Scylla's rock on the left, her cave in it and
six necks swaying out of it over the water; Charybdis on the right, a whirlpool that dips
the sea and spins faster and wider with the bass. The ship rows west between them. Near the
maw the bass drags on the oars and spins the ship, and if it stays high she drinks it down
and spits it back, one companion fewer. In reach of the rock a big beat sends a head down
to the deck and Scylla takes one. Through the strait, it starts again from the east.

<img src="docs/screenshots/scylla.svg" width="900" alt="the strait: Scylla's rock and six necks on the left, the ship with five men, Charybdis turning on the right">

The Sleestak have the Marshalls in the Lost City: the pylon's crystals lit by the bass, Will
and Holly with the torch, its flame the bass. The Sleestak come out of the dark on either
side, eyes first, and chase them the way Sleestak do, slow and arms out, each on its own
step, only while the music is warm and dead still when it goes quiet. The torch's light is
all that keeps them back: the Marshalls back away from whichever side is pressing, and
cornered against a column they wave the torch and push through. A beat flashes the
Sleestak's eyes and they hiss; a big one and a crossbow bolt flies wide.

<img src="docs/screenshots/sleestak.svg" width="900" alt="the Lost City: Will and Holly with the torch between two Sleestak, one coming out from behind a column, a crossbow bolt on the way">

The Stealie, traced from the 1969 design: the skull in the ring, blue and red behind it, the
disc in the cranium red and blue either side of the thirteen-point bolt, which flashes white
on a beat. The red lights with the bass, the blue with the treble, the eye sockets open with
the bass, and the thirteen points around the ring are one group of bands each, turning
faster with the music.

<img src="docs/screenshots/stealie.svg" width="900" alt="the Stealie: the skull in the ring, red and blue, the bolt through the cranium, the thirteen points">

The Wall of Sound, 1974, as the PA it was: stacks of cabinets, one per instrument where
they stood, Bob, Phil's quad bass (four columns, one per string), the vocal cluster in the
middle and tallest, Jerry, Keith, the drums. Each stack lights from the bottom with its own
bands, the peak cabinet holds, and a beat shakes the scaffold.

<img src="docs/screenshots/wall.svg" width="900" alt="the Wall of Sound: six stacks of cabinets, Phil's four columns lit">

Screenshots are SVGs made from `tmux capture-pane -e` by `scripts/ansi2svg.py`; the light
show ones here were driven by a stand-in `parec` playing synthetic drums, since the machine
that took them has no sound card.

## Running it

**Download.** Each [release](https://github.com/originalrexconsulting/may-the-lord-poseidon-convey-you/releases)
has one self-contained file per machine, Python and the light show's numpy included.
The machine needs only mpv (`apt install mpv`, `brew install mpv`); ffmpeg is optional
(SHN tapes to FLAC, the station probe) and on Linux `pulseaudio-utils` gives the light
show its audio tap.

| Machine | File |
|---|---|
| Linux x86_64, and Windows under WSL 2 | `poseidon-<ver>-linux-x86_64` |
| Linux aarch64 (Raspberry Pi 4/5 and up, Graviton) | `poseidon-<ver>-linux-aarch64` |
| Mac, Apple silicon | `poseidon-<ver>-macos-aarch64` |
| Mac, Intel | `poseidon-<ver>-macos-x86_64` |

```
curl -fLo poseidon https://github.com/originalrexconsulting/may-the-lord-poseidon-convey-you/releases/download/v<ver>/poseidon-<ver>-linux-x86_64
chmod +x poseidon
./poseidon doctor        # what this build is and what it found: mpv, ffmpeg, library, terminfo
./poseidon               # the TUI; ./poseidon gdarchive ..., ./poseidon radio list, ./poseidon --help
```

`<ver>` is the release date, e.g. `2026.09.13.2`; copy the link from the release page.
The first run unpacks its Python into `~/.cache/nce` (macOS: `~/Library/Caches/nce`),
which takes a few seconds once and is safe to delete. `poseidon-<ver>.pex` is the same
program for a machine that already has Python 3.11+ on PATH: it uses the system's numpy
(`python3-numpy`) for the light show and is a tenth the size.

Shows fetched with `d` land in `~/Music/dead`; `POSEIDON_LIBRARY=/path/to/dead` moves
the library. From a clone the library is `dead/` next to `scripts/`.

**Or clone.** Per-OS guides: [Linux](docs/setup-linux.md), [macOS](docs/setup-macos.md),
[Windows](docs/setup-windows.md) (WSL 2). The short version:

Linux (Debian): `apt install mpv python3-numpy python3-mutagen pulseaudio-utils ffmpeg`
(numpy is the light show, mutagen tags fetched shows, parec is the light show's audio
tap, ffmpeg converts SHN tapes). Then `scripts/May-The_Lord_Poseidon-Convey-You.py`.

macOS: `brew install mpv ffmpeg python numpy` and `pip3 install mutagen` (both optional:
without numpy there is no light show, without mutagen fetched shows are left untagged).
Playback goes straight to CoreAudio, so pick the DAC in Sound settings. The light show
needs an audio tap, which macOS does not provide by itself: `brew install blackhole-2ch`,
make a Multi-Output Device in Audio MIDI Setup with the DAC and BlackHole, set it as
output, and the tap reads BlackHole back through ffmpeg (`DEADVIZ_DEVICE` names it if
yours is not "BlackHole 2ch"). The status line's DAC rate readout is Linux-only and
stays blank. `radio.py`'s own commands (`play`, `now`) drive Strawberry over D-Bus and
are Linux-only; the station list itself is used by the TUI everywhere.

Windows: run it under WSL 2 as Linux, with the linux-x86_64 download or the Debian
recipe above. Native Windows would need `windows-curses` and a named pipe for mpv; not
done.

`SYSTEM.md` is the reference: the setup, every key, every script, and the
facts about archive.org that shape what you get (soundboards stream only,
audience tapes download lossless). `AUDIO-ANSIBLE.md` is the spec for the
PipeWire side.

## Endorsement

Enik the Altrusian has examined this project from the fifth dimension, by way of the
pylon's crystal matrix, and has approved it. He notes that the Sleestak, being
cold-blooded and slow, prefer the light show's `life` mode; that the time doorway will
not open until 5/8/77 has finished playing; and that the Marshalls, who fell through a
similar doorway on a routine expedition, could have used the `r` key. Do not touch the
crystals in the wrong order.

MIT license.
