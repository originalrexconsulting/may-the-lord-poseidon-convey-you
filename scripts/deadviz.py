#!/usr/bin/env python3
"""deadviz.py - terminal light show driven by whatever PipeWire is playing.

Captures the default sink's monitor (so it hears exactly what the Rotel gets,
from any player) with parec, runs a small FFT with numpy, and draws patterns
in curses. Used by May-The_Lord_Poseidon-Convey-You.py, formerly deadtui.py (key v, and as an idle screensaver) and runs on
its own for testing:

    deadviz.py            # v next mode (V previous), 1-9/0 pick the first ten, Esc quits

Modes:
  bars       mirrored spectrum with peak markers
  plasma     blue/green colour field that breathes with the bass
  scope      stereo Lissajous in braille
  rings      pulsing tunnel
  waterfall  blue/cyan scrolling spectrogram, newest at the bottom
  fire       red/orange/yellow flames whose heat comes from the spectrum
  rain       blue falling glyph columns, white at the head, spawned where the music is loud
  stars      blue/white warp-speed starfield, faster with the bass
  wave       cyan/white stereo waveform, left over right
  radial     orange/gold spectrum around a circle, bass at the top
  particles  fireworks: every beat launches a burst in its own colour
  meters     big green/yellow/red VU meters: L, R, bass, mid, treble with peak hold
  spiral     purple/pink rotating three-arm spiral that flares with each band
  life       green/white Conway's Life, seeded by the beat
  poseidon   the Earth Shaker swims a night sea: the bass raises the swell, the
             treble puts stars in the sky and foam on the crests, a real beat shakes
             the earth and lights the trident. He gets bored (or the music goes
             quiet), dives, lurks on the bottom with his eyes burning, and a big
             beat brings him back up. Company drops by now and then, never all at
             once: sharks (more with the bass), a whale that spouts, dolphins that
             jump on the beat, drifting jellyfish, a crab on the bottom
  enik       Enik the Altrusian, head to foot, lumbering the way the costume did:
             the pose only changes four times a second, in angular jolts, and a
             step lands on the beat. The bass opens the time doorway behind him,
             the treble lights the crystal matrix (one crystal per band), a beat
             flashes his eyes and he hisses; quiet music stops him, arms down,
             and the doorway will not open
  cyclops    Polyphemus lounges in his cave, breathing with the bass, his one eye on
             the loudest band. Sheep graze at his feet (more with the treble); a few
             are men, some of them hiding underneath. A big beat and he reaches down,
             picks a man, and eats him: a tally on the wall keeps count. Silence puts
             him to sleep, and if it lasts, a glowing stake comes in from the mouth of
             the cave, he wakes up roaring that Nobody did it, the flock runs out with
             the men under it, and the cave starts over
  convey     May the Lord Poseidon convey you: the voyage Polyphemus promised. A black
             ship rows west across the night sea toward Ithaca, faster the louder the
             music, oars on the beat, sail full with the mids. On a big beat the Earth
             Shaker rises ahead of it, trident up, and conveys it his way: a wave
             throws the ship back east and takes a companion. Lose them all and
             Odysseus is alone on a raft. Reach Ithaca at last and it starts over
             at the Cyclops's island, boulder and all
  athena     the grey-eyed goddess, as her owl: the little owl on an olive branch,
             big as the screen, under the moon over the Parthenon. Its wings are the
             spectrum, one feather per band, fanning open as the music gets loud and
             snapping wide on a beat. The eyes dilate with the bass and follow the
             stereo balance; the head snaps toward the loudest band the way an owl's
             does. Quiet music and it asks the only question an owl asks; the answer
             here is Nobody. Long enough and it turns its head all the way round.
             The bough sways in a wind that gusts with the music, and she rides it
  althea     the healer, not the goddess: Althaea, at the hearth in Calydon with the
             brand that holds her son's life. The fire is the spectrum, one flame per
             band, the ember of the log glows with the bass, sparks fly on a beat and
             the smoke thickens with the mids. Hollyhocks, her own plant, bloom with
             the treble. She dances seated, hair a beat behind her shoulders, one hand
             keeping time on her knee. Music too hot for too long and she draws the
             brand out and raises a palm: cool down boy. Settled, she puts it back.
             Silence and she stirs the embers: easy Jim
  scylla     the strait, the next chapter of the voyage: Scylla's rock on the left with
             her cave and six necks swaying out of it, Charybdis on the right, a whirlpool
             that dips the sea and spins faster and wider with the bass. The ship rows
             west between them. Near the whirlpool the bass drags on the oars and spins
             the ship, and if it stays high she drinks it down and spits it back three
             seconds later, one companion fewer. In reach of the rock a big beat sends a
             head down to the deck and Scylla takes one. Through the strait, it starts
             again from the east with six at the oars
  sleestak   the Lost City at night: the pylon's crystals lit by the bass, columns in
             the dark, and Will and Holly Marshall with the torch, whose flame is the
             bass. The Sleestak come out of the dark on either side, eyes first, and
             chase them the way Sleestak do: slow, arms out, each on its own step, only
             while the music is warm, faster the warmer, dead still when it goes quiet.
             The torch's light is all that keeps them back: the Marshalls back away from
             whichever side is pressing, cornered against a column they wave the torch
             and push through, and a flare sends the Sleestak back with an arm up. A beat
             flashes their eyes and they hiss, a big one and a crossbow bolt flies wide.
             Long enough in the cold and they go back where they came from
  stealie    steal your face: the skull in the ring, the thirteen points around it one
             group of bands each, spinning faster with the music, the lightning bolt
             flashing white on a beat. The red half warms with the bass, the blue half
             with the treble, the eye sockets widen with the bass
  wall       the Wall of Sound, 1974: the PA as stacks of cabinets, one stack per
             instrument in the places they stood: Bob, Phil's quad bass (four columns,
             one per string), the vocal cluster in the middle and tallest, Jerry, Keith,
             the drums. Each stack lights from the bottom with its own bands, the peak
             cabinet holds, a beat shakes the scaffold

Stock packages only: python3-numpy, pulseaudio-utils (parec via pipewire-pulse).
On macOS there is no monitor source: install BlackHole (brew install blackhole-2ch),
set it as the output device (or a Multi-Output Device with it and the DAC), and the
tap reads it back through ffmpeg's avfoundation input. DEADVIZ_DEVICE names the
device (default "BlackHole 2ch"); DEADVIZ_CAPTURE forces parec or ffmpeg.
"""

import curses
import math
import os
import shutil
import subprocess
import sys
import threading
import time

import numpy as np

RATE = 44100
CHUNK = 1024          # samples per parec read
WINDOW = 2048         # FFT size
BANDS = 48
FPS = 24
REF_H, REF_W = 40, 140   # the terminal the cell-counted modes were drawn for; Viz.density() scales them from here
MODES = ["bars", "plasma", "scope", "rings", "waterfall", "fire", "rain", "stars",
         "wave", "radial", "particles", "meters", "spiral", "life", "poseidon", "enik", "cyclops", "convey",
         "athena", "althea", "scylla", "sleestak", "stealie", "wall"]

BLOCKS = " ▁▂▃▄▅▆▇█"
BRAILLE_BASE = 0x2800
BRAILLE_DOTS = [[0x01, 0x08], [0x02, 0x10], [0x04, 0x20], [0x40, 0x80]]  # [row][col]
GLYPHS = "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ0123456789Z:."


# --------------------------------------------------------------------------- audio

class Capture(threading.Thread):
    """Keeps the last WINDOW stereo samples from the default sink monitor."""

    def __init__(self):
        super().__init__(daemon=True)
        self.buf = np.zeros((WINDOW, 2), dtype=np.float32)
        self.lock = threading.Lock()
        self.proc = None
        self.error = None
        self.alive = True

    @staticmethod
    def backend():
        """(name, command) for the audio tap on this machine, or (None, why)."""
        want = os.environ.get("DEADVIZ_CAPTURE", "auto")
        if want in ("auto", "parec") and shutil.which("parec"):
            return "parec", ["parec", "--raw", "--format=s16le", f"--rate={RATE}", "--channels=2",
                             "-d", "@DEFAULT_MONITOR@", "--latency-msec=40"]
        if want in ("auto", "ffmpeg") and shutil.which("ffmpeg") and (sys.platform == "darwin" or want == "ffmpeg"):
            # macOS: no monitor source exists, so route output through a loopback device
            # (BlackHole, free) set as the system output, and read that device back.
            dev = os.environ.get("DEADVIZ_DEVICE", "BlackHole 2ch")
            return "ffmpeg", ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "avfoundation", "-i", f":{dev}",
                              "-ac", "2", "-ar", str(RATE), "-f", "s16le", "-"]
        if sys.platform == "darwin":
            return None, "no audio tap: brew install ffmpeg blackhole-2ch, set BlackHole as output (DEADVIZ_DEVICE names it)"
        return None, "no audio tap: parec (pulseaudio-utils, via pipewire-pulse) is not installed"

    def run(self):
        name, cmd = self.backend()
        if not name:
            self.error = cmd
            return
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError as e:
            self.error = f"{name}: {e}"
            return
        need = CHUNK * 2 * 2
        while self.alive:
            data = self.proc.stdout.read(need)
            if not data:
                self.error = (f"{name} ended (is a sink present?)" if name == "parec"
                              else f"{name} ended (is the loopback device present? DEADVIZ_DEVICE)")
                return
            frames = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            frames = frames.reshape(-1, 2)
            with self.lock:
                self.buf = np.concatenate([self.buf[len(frames):], frames])

    def stop(self):
        self.alive = False
        if self.proc:
            self.proc.kill()

    def samples(self):
        with self.lock:
            return self.buf.copy()


class Analyzer:
    """Log-spaced band magnitudes in 0..1 with attack/decay smoothing, plus bass/mid/treble energy."""

    def __init__(self):
        self.window = np.hanning(WINDOW).astype(np.float32)
        freqs = np.fft.rfftfreq(WINDOW, 1.0 / RATE)
        edges = np.geomspace(35, 16000, BANDS + 1)
        self.bins = [np.where((freqs >= lo) & (freqs < hi))[0] for lo, hi in zip(edges[:-1], edges[1:])]
        for i, b in enumerate(self.bins):           # make sure every band owns at least one bin
            if len(b) == 0:
                self.bins[i] = np.array([min(len(freqs) - 1, int(edges[i] / freqs[1]))])
        self.level = np.zeros(BANDS)
        self.peak = np.zeros(BANDS)
        self.bass = self.mid = self.treble = 0.0
        self.beat = 0.0
        self.rms = 0.0
        self.rms_lr = (0.0, 0.0)
        self._bass_hist = []

    def update(self, stereo):
        mono = stereo.mean(axis=1)
        spec = np.abs(np.fft.rfft(mono * self.window)) / (WINDOW / 4)   # full-scale sine -> ~1.0 (0 dB)
        mags = np.array([spec[b].max() for b in self.bins])
        db = 20 * np.log10(mags + 1e-6)
        norm = np.clip((db + 60) / 60, 0, 1)          # -60 dB .. 0 dB -> 0..1
        # tilt: the ear + music both roll off; lift the top so bars look balanced
        norm = np.clip(norm * np.linspace(1.0, 1.35, BANDS), 0, 1)
        self.level = np.where(norm > self.level, norm * 0.6 + self.level * 0.4, self.level * 0.85)
        self.peak = np.where(self.level > self.peak, self.level, self.peak - 0.015)
        third = BANDS // 3
        self.bass = float(self.level[:third].mean())
        self.mid = float(self.level[third:2 * third].mean())
        self.treble = float(self.level[2 * third:].mean())
        self._bass_hist.append(self.bass)
        self._bass_hist = self._bass_hist[-30:]
        avg = sum(self._bass_hist) / len(self._bass_hist)
        self.beat = max(0.0, self.bass - avg) * 4
        self.rms = float(np.sqrt((mono ** 2).mean()))
        self.rms_lr = tuple(float(x) for x in np.sqrt((stereo ** 2).mean(axis=0)))


# --------------------------------------------------------------------------- palette

# Each ramp is 31 colours on the 256-colour cube, registered as a block of colour pairs starting at
# the number below (fg = ink on the default background, bg = background colour). Pairs 1-3 belong to
# deadtui; eight blocks of 31 from pair 4 end at 251, so any 256-colour terminal is fine. Blocks beyond
# that need extended pairs (ncurses 6 / python 3.10+, COLOR_PAIRS 65536); where they are missing,
# build_palette() aliases the block to the main ramp instead.
RAMPS = {   # name: (first pair, kind, cube corners (r, g, b in 0..5), 8-colour fallback)
    "main_fg":  (4,   "fg", [(1, 0, 3), (3, 0, 5), (5, 0, 4), (5, 1, 2), (5, 3, 0), (5, 5, 1)],
                 ["MAGENTA", "RED", "YELLOW", "WHITE"]),           # purple -> magenta -> orange -> yellow
    "main_bg":  (35,  "bg", [(1, 0, 3), (3, 0, 5), (5, 0, 4), (5, 1, 2), (5, 3, 0), (5, 5, 1)],
                 ["MAGENTA", "RED", "YELLOW", "WHITE"]),
    "fire_bg":  (66,  "bg", [(1, 0, 0), (3, 0, 0), (5, 0, 0), (5, 2, 0), (5, 4, 0), (5, 5, 3)],
                 ["RED", "RED", "YELLOW", "WHITE"]),               # dark red -> red -> orange -> yellow -> white
    "star_fg":  (97,  "fg", [(0, 0, 2), (0, 1, 4), (1, 2, 5), (2, 4, 5), (4, 5, 5), (5, 5, 5)],
                 ["BLUE", "BLUE", "CYAN", "WHITE"]),               # navy -> blue -> sky -> white
    "rain_fg":  (128, "fg", [(0, 1, 0), (0, 2, 0), (0, 4, 0), (1, 5, 1), (3, 5, 3), (5, 5, 5)],
                 ["GREEN", "GREEN", "GREEN", "WHITE"]),            # dark green -> green -> pale green -> white
    "water_bg": (159, "bg", [(0, 0, 1), (0, 0, 3), (0, 1, 5), (0, 3, 5), (0, 5, 5), (3, 5, 5)],
                 ["BLUE", "BLUE", "CYAN", "CYAN"]),                # navy -> blue -> cyan -> pale cyan
    "life_bg":  (190, "bg", [(0, 1, 0), (0, 3, 0), (0, 5, 0), (2, 5, 2), (4, 5, 4), (5, 5, 5)],
                 ["GREEN", "GREEN", "GREEN", "WHITE"]),            # dark green -> green -> pale green -> white
    "spark_fg": (221, "fg", [(5, 0, 0), (5, 5, 0), (0, 5, 0), (0, 5, 5), (0, 0, 5), (5, 0, 5)],
                 ["RED", "YELLOW", "GREEN", "CYAN"]),              # hue wheel: red -> yellow -> green -> cyan -> blue -> magenta
    "spiral_fg": (256, "fg", [(1, 0, 2), (2, 0, 4), (4, 0, 5), (5, 0, 4), (5, 2, 4), (5, 4, 5)],
                 ["MAGENTA", "MAGENTA", "MAGENTA", "WHITE"]),      # deep purple -> violet -> magenta -> pink
    "wave_fg":  (287, "fg", [(0, 2, 2), (0, 3, 3), (0, 5, 5), (2, 5, 5), (4, 5, 5), (5, 5, 5)],
                 ["CYAN", "CYAN", "CYAN", "WHITE"]),               # teal -> cyan -> pale cyan -> white
    "radial_fg": (318, "fg", [(3, 1, 0), (5, 2, 0), (5, 3, 0), (5, 4, 0), (5, 5, 1), (5, 5, 3)],
                 ["RED", "YELLOW", "YELLOW", "WHITE"]),            # burnt orange -> orange -> gold -> pale gold
    "meter_fg": (349, "fg", [(0, 4, 0), (0, 5, 0), (0, 5, 0), (2, 5, 0), (5, 5, 0), (5, 0, 0)],
                 ["GREEN", "GREEN", "YELLOW", "RED"]),             # VU: green to ~65%, yellow, red at the top
    "plasma_bg": (380, "bg", [(0, 0, 3), (0, 1, 5), (0, 3, 4), (0, 5, 3), (2, 5, 1), (0, 3, 4)],
                 ["BLUE", "CYAN", "GREEN", "CYAN"]),               # blue -> azure -> teal -> green and back, so it wraps smoothly
}
# curses attributes carry the pair number in 8 bits, so every pair must stay below 256
# whatever the terminal claims. 13 ramps x 16 steps from pair 8 ends at 215. The "first
# pair" written above is only a label; the real bases are assigned here in order.
STEPS_PER_SEGMENT = 3
RAMP_LEN = 5 * STEPS_PER_SEGMENT + 1
for _i, _k in enumerate(RAMPS):
    RAMPS[_k] = (8 + _i * RAMP_LEN,) + tuple(RAMPS[_k][1:])
assert 8 + len(RAMPS) * RAMP_LEN <= 256
ALIAS = {}  # pair base -> substitute base, for ramps the terminal has no room for
MAIN_FG = RAMPS["main_fg"][0]
MAIN_BG = RAMPS["main_bg"][0]
FIRE_BG = RAMPS["fire_bg"][0]
STAR_FG = RAMPS["star_fg"][0]
RAIN_FG = RAMPS["rain_fg"][0]
WATER_BG = RAMPS["water_bg"][0]
LIFE_BG = RAMPS["life_bg"][0]
SPARK_FG = RAMPS["spark_fg"][0]
SPIRAL_FG = RAMPS["spiral_fg"][0]
WAVE_FG = RAMPS["wave_fg"][0]
RADIAL_FG = RAMPS["radial_fg"][0]
METER_FG = RAMPS["meter_fg"][0]
PLASMA_BG = RAMPS["plasma_bg"][0]


def _ramp(steps):
    """Interpolate a list of (r, g, b) 0..5 cube corners into STEPS_PER_SEGMENT colours per segment plus the last one."""
    ramp = []
    for a, b in zip(steps[:-1], steps[1:]):
        for t in np.linspace(0, 1, STEPS_PER_SEGMENT + 1)[:-1]:
            r, g, bl = (round(a[i] + (b[i] - a[i]) * t) for i in range(3))
            ramp.append(16 + 36 * r + 6 * g + bl)
    e = steps[-1]
    ramp.append(16 + 36 * e[0] + 6 * e[1] + e[2])
    return ramp


def build_palette():
    """Register every ramp in RAMPS as colour pairs. Returns the number of steps per ramp."""
    n = None
    ALIAS.clear()
    for base, kind, corners, fallback in RAMPS.values():
        colours = _ramp(corners) if curses.COLORS >= 256 else [getattr(curses, "COLOR_" + c) for c in fallback]
        if base + len(colours) > curses.COLOR_PAIRS:
            ALIAS[base] = MAIN_FG if kind == "fg" else MAIN_BG
            continue
        for i, c in enumerate(colours):
            if kind == "fg":
                curses.init_pair(base + i, c, -1)
            else:
                curses.init_pair(base + i, -1, c)
        n = len(colours)
    return n


# --------------------------------------------------------------------------- braille canvas

class Canvas:
    """Braille dot canvas over the drawing area: (w-1)*2 dots wide, (h-1)*4 dots tall (roughly square dots)."""

    def __init__(self, h, w):
        self.gw, self.gh = max(2, (w - 1) * 2), max(4, (h - 1) * 4)
        self.cells = {}   # (row, col) -> [bits, colour 0..1]

    def dot(self, px, py, col=0.5):
        px, py = int(px), int(py)
        if 0 <= px < self.gw and 0 <= py < self.gh:
            key = (py // 4, px // 2)
            bit = BRAILLE_DOTS[py % 4][px % 2]
            c = self.cells.get(key)
            if c is None:
                self.cells[key] = [bit, col]
            else:
                c[0] |= bit
                c[1] = max(c[1], col)

    def blob(self, px, py, col=0.5, size=1):
        """A dot, or a size x size square of dots: a point that stays visible on a fine grid."""
        if size <= 1:
            self.dot(px, py, col)
            return
        px, py = int(px) - (size - 1) // 2, int(py) - (size - 1) // 2
        for j in range(size):
            for i in range(size):
                self.dot(px + i, py + j, col)

    def line(self, x0, y0, x1, y1, col=0.5, width=1):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        if n == 1:
            self.dot(x0, y0, col)
            return
        if width > 1:                                        # parallel strokes, offset across the line
            L = math.hypot(x1 - x0, y1 - y0) or 1.0
            nx, ny = -(y1 - y0) / L, (x1 - x0) / L
            for k in range(width):
                o = k - (width - 1) / 2
                self.line(x0 + nx * o, y0 + ny * o, x1 + nx * o, y1 + ny * o, col)
            return
        for t in np.linspace(0.0, 1.0, n):
            self.dot(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, col)

    def ellipse(self, cx, cy, rx, ry, col=0.5):
        """Filled ellipse."""
        for py in range(int(cy - ry), int(cy + ry) + 1):
            f = 1 - ((py - cy) / max(ry, 0.5)) ** 2
            if f < 0:
                continue
            half = rx * math.sqrt(f)
            for px in range(int(cx - half), int(cx + half) + 1):
                self.dot(px, py, col)

    def poly(self, pts, col=0.5):
        """Filled polygon, scanline by scanline."""
        ys = [p[1] for p in pts]
        n = len(pts)
        for py in range(int(min(ys)), int(max(ys)) + 1):
            xs = []
            for i in range(n):
                (xa, ya), (xb, yb) = pts[i], pts[(i + 1) % n]
                if (ya <= py < yb) or (yb <= py < ya):
                    xs.append(xa + (py - ya) * (xb - xa) / (yb - ya))
            xs.sort()
            for xa, xb in zip(xs[0::2], xs[1::2]):
                for px in range(int(xa), int(xb) + 1):
                    self.dot(px, py, col)

    def circle(self, cx, cy, r, col=0.5, n=None):
        n = n or max(12, int(r * 3))
        for a in np.linspace(0, 2 * math.pi, n, endpoint=False):
            self.dot(cx + math.cos(a) * r, cy + math.sin(a) * r, col)

    def paint(self, viz, bold=False, base=None):
        for (cy, cx), (bits, col) in self.cells.items():
            viz.put(cy, cx, chr(BRAILLE_BASE + bits), viz.fg(col, bold) if base is None else viz.fg(col, bold, base))


# --------------------------------------------------------------------------- renderers

class Viz:
    def __init__(self, scr, title_fn=None, on_key=None, mode="bars"):
        self.scr = scr
        self.title_fn = title_fn or (lambda: "")
        self.on_key = on_key or (lambda ch: False)
        self.mode = mode if mode in MODES else MODES[0]
        self.cap = Capture()
        self.an = Analyzer()
        self.t0 = time.time()
        self.t = 0.0
        self.frame = 0
        self.hue = 0.0
        self.npal = build_palette()
        self.rng = np.random.default_rng()
        self.states = {}   # per-mode persistent state (fire heat, star positions, ...)
        self.flow = "down"   # the waterfall's direction: newest row at the top and falling, or rising; the arrows flip it

    def fg(self, x, bold=False, base=MAIN_FG):
        """Foreground attr for 0..1 on the main ramp or another fg ramp such as STAR_FG."""
        i = int(max(0.0, min(0.999, x)) * self.npal)
        return curses.color_pair(ALIAS.get(base, base) + i) | (curses.A_BOLD if bold else 0)

    def bg(self, x):
        i = int(max(0.0, min(0.999, x)) * self.npal)
        return curses.color_pair(MAIN_BG + i)

    def put(self, y, x, s, attr=0):
        try:
            self.scr.addstr(y, x, s, attr)
        except curses.error:
            pass

    def density(self, h, w):
        """How much finer than the reference grid this terminal is: 1.0 at 40x140 cells, about 2.0 once the
        font is shrunk to half size. Anything counted in cells or dots (stars, sparks, stroke widths, cabinets)
        scales by it, so the picture keeps its size on the glass and gains resolution instead of shrinking."""
        return max(0.5, min(4.0, math.sqrt(h * w / (REF_H * REF_W))))

    def stroke(self, h, w):
        """Braille stroke width in dots for a hairline at this density."""
        return max(1, int(round(self.density(h, w))))

    def state(self, name, h, w, init):
        """Per-mode state dict, rebuilt by init() when the terminal size changes."""
        st = self.states.get(name)
        if st is None or st["_dims"] != (h, w):
            st = init()
            st["_dims"] = (h, w)
            self.states[name] = st
        return st

    def field(self, v, mask=None, base=MAIN_BG):
        """Paint a 2D array of 0..1 values as runs of background colour (rows/cols from the array shape).
        base picks the colour-pair block: MAIN_BG, or one of the mode ramps such as FIRE_BG."""
        idx = (np.clip(v, 0, 0.999) * self.npal).astype(np.int16)
        base = ALIAS.get(base, base)
        if mask is not None:
            idx = np.where(mask, idx, -1)
        for yy in range(idx.shape[0]):
            row = idx[yy]
            change = np.flatnonzero(np.diff(row)) + 1
            starts = np.concatenate(([0], change))
            ends = np.concatenate((change, [len(row)]))
            for s, e in zip(starts, ends):
                i = int(row[s])
                if i >= 0:
                    self.put(yy, int(s), " " * int(e - s), curses.color_pair(base + i))

    def band_cols(self, n):
        """Band index for each of n columns across the width."""
        return (np.arange(n) * BANDS / max(1, n)).astype(int)

    # ---- bars
    def draw_bars(self, h, w):
        an = self.an
        area_h = h - 2
        n = BANDS
        bw = max(1, (w - 2) // n)
        gap = 1 if bw > 2 else 0
        x0 = (w - n * bw) // 2
        mid = area_h // 2
        for i in range(n):
            lvl = an.level[i] * (mid - 1)
            full = int(lvl)
            frac = lvl - full
            col = self.fg(i / n * 0.6 + an.level[i] * 0.4 + self.hue * 0.2, an.level[i] > 0.7)
            for y in range(full):
                self.put(mid - 1 - y, x0 + i * bw, "█" * (bw - gap), col)
                self.put(mid + 1 + y, x0 + i * bw, "█" * (bw - gap), col)
            if full < mid - 1 and frac > 0:
                c = BLOCKS[int(frac * 8)]
                self.put(mid - 1 - full, x0 + i * bw, c * (bw - gap), col)
                self.put(mid + 1 + full, x0 + i * bw, "▀" * (bw - gap) if frac > 0.5 else " " * (bw - gap), col)
            pk = int(an.peak[i] * (mid - 1))
            if pk > full:
                self.put(mid - 1 - pk, x0 + i * bw, "▁" * (bw - gap), self.fg(0.95, True))
        self.put(mid, 0, "─" * (w - 1), self.fg(0.5 + an.bass * 0.5))

    # ---- plasma
    def draw_plasma(self, h, w):
        an = self.an
        t = self.t
        ys, xs = np.mgrid[0:h - 1, 0:w - 1]
        x = xs / max(1, w) * 2 * math.pi * (1.5 + an.treble * 2)
        y = ys / max(1, h) * 2 * math.pi * (1.0 + an.mid)
        speed = t * (0.6 + an.bass * 2.5)
        v = (np.sin(x + speed) + np.sin((y + speed * 0.7) * 1.3)
             + np.sin((x + y) * 0.5 + speed * 1.1)
             + np.sin(np.sqrt((xs - w / 2) ** 2 * 0.25 + (ys - h / 2) ** 2) * (0.25 + an.beat) - speed * 2))
        v = (v + 4) / 8                                  # 0..1
        v = np.clip(v * (0.7 + an.rms * 3) + self.hue % 1.0, 0, 1.999) % 1.0
        self.field(v, base=PLASMA_BG)

    # ---- scope (stereo Lissajous in braille)
    def draw_scope(self, h, w):
        k = self.density(h, w)
        st = self.cap.samples()[-int(1200 * k):]          # a finer grid gets more of the buffer, so the trace stays dense
        cv = Canvas(h, w)
        gain = 0.9 / max(0.05, float(np.abs(st).max()) if len(st) else 1.0)
        gain = min(gain, 12.0)
        col = 0.3 + self.an.bass * 0.7
        size = self.stroke(h, w)
        for l, r in st[::2 if k < 1.5 else 1]:
            cv.blob((l * gain * 0.5 + 0.5) * (cv.gw - 1), (0.5 - r * gain * 0.5) * (cv.gh - 1), col, size)
        cv.paint(self, self.an.beat > 0.2)
        # spectrum ghost along the bottom
        n = min(BANDS, w - 2)
        for i in range(n):
            lvl = self.an.level[int(i * BANDS / n)]
            self.put(h - 2, 1 + i, BLOCKS[int(lvl * 8)], self.fg(i / n, False))

    # ---- rings
    def draw_rings(self, h, w):
        an = self.an
        t = self.t
        cy, cx = (h - 1) / 2, (w - 1) / 2
        ys, xs = np.mgrid[0:h - 1, 0:w - 1]
        d = np.sqrt(((xs - cx) * 0.5) ** 2 + (ys - cy) ** 2)
        ang = np.arctan2(ys - cy, (xs - cx) * 0.5)
        v = np.sin(d * (0.8 + an.treble) - t * (2 + an.bass * 6) + np.sin(ang * 3 + t) * an.mid * 2)
        v = (v + 1) / 2
        v = (v * (0.5 + an.rms * 4) + self.hue) % 1.0
        chars = " ·∘○◎●"
        for yy in range(h - 1):
            for xx in range(w - 1):
                val = v[yy, xx]
                if val < 0.3:
                    continue
                self.put(yy, xx, chars[min(5, int(val * 6))], self.fg(val, val > 0.8))

    # ---- waterfall (spectrogram: newest row at the top and falling, as water does; the up arrow makes it rise)
    def draw_waterfall(self, h, w):
        st = self.state("waterfall", h, w, lambda: {"rows": []})
        rows = st["rows"]
        rows.append(self.an.level[self.band_cols(w - 1)])
        del rows[:-(h - 1)]
        v = np.zeros((h - 1, w - 1))
        if self.flow == "down":
            v[:len(rows)] = np.array(rows[::-1])
        else:
            v[h - 1 - len(rows):] = np.array(rows)
        self.field(v, mask=v > 0.05, base=WATER_BG)

    # ---- fire (classic cellular flame, fed by the spectrum along the bottom)
    def draw_fire(self, h, w):
        an = self.an
        st = self.state("fire", h, w, lambda: {"heat": np.zeros((h, w - 1))})
        heat = st["heat"]
        cols = w - 1
        src = an.level[self.band_cols(cols)] * 0.9 + an.rms * 2 + an.beat * 0.5
        heat[-1] = np.clip(src * (0.5 + self.rng.random(cols) * 0.7), 0, 1)
        below = heat[1:]
        spread = (np.roll(below, 1, axis=1) + below * 2 + np.roll(below, -1, axis=1)) / 4
        cool = self.rng.random((h - 1, cols)) * (0.05 + 0.12 * (1 - an.bass))
        heat[:-1] = np.clip(spread - cool, 0, 1)
        self.field(heat[:-1] ** 0.8, mask=heat[:-1] > 0.04, base=FIRE_BG)

    # ---- rain (falling glyph columns, spawned where the music is loud)
    def draw_rain(self, h, w):
        an = self.an
        cols = w - 1
        st = self.state("rain", h, w, lambda: {"y": np.full(cols, -1.0), "spd": np.zeros(cols),
                                                "len": np.zeros(cols, dtype=int)})
        lvl = an.level[self.band_cols(cols)]
        idle = st["y"] < 0
        spawn = idle & (self.rng.random(cols) < lvl * 0.12 + an.beat * 0.2 + 0.005)
        k = int(spawn.sum())
        if k:
            st["y"][spawn] = 0
            st["spd"][spawn] = 0.3 + self.rng.random(k) * 0.7
            st["len"][spawn] = self.rng.integers(3, max(4, h // 2), k)
        active = st["y"] >= 0
        st["y"][active] += st["spd"][active] * (0.4 + an.treble * 1.5 + an.bass * 0.8)
        g = len(GLYPHS)
        for x in np.flatnonzero(active):
            y, L = int(st["y"][x]), int(st["len"][x])
            if y - L > h - 2:
                st["y"][x] = -1
                continue
            for k in range(L):
                yy = y - k
                if 0 <= yy < h - 1:
                    ch = GLYPHS[(x * 7 + yy * 13 + self.frame // 4) % g]
                    fade = 1 - k / L
                    col = 0.98 if k == 0 else 0.1 + fade * 0.5 + lvl[x] * 0.25   # white head, blue tail
                    self.put(yy, int(x), ch, self.fg(col, k == 0, base=STAR_FG))   # blue rain (the green ramp keeps its old name for the Sleestak and the leaves)

    # ---- stars (warp field, faster with the bass)
    def draw_stars(self, h, w):
        an = self.an
        n = int(180 * self.density(h, w) ** 2)            # the same stars per square inch of glass at any font size
        st = self.state("stars", h, w, lambda: {"p": self.rng.random((n, 3)) * [2, 2, 1] - [1, 1, 0]})
        p = st["p"]                                       # x, y in -1..1, z depth 0..1 (small is near)
        speed = 0.006 + an.bass * 0.05 + an.beat * 0.08
        p[:, 2] -= speed
        cx, cy = (w - 1) / 2, (h - 1) / 2
        trail = int(an.bass * 4 + an.beat * 3)
        for i in range(n):
            x, y, z = p[i]
            if z <= 0.02:
                p[i] = [self.rng.random() * 2 - 1, self.rng.random() * 2 - 1, 1.0]
                continue
            sx, sy = int(cx + x / z * cx), int(cy + y / z * cy)
            if not (0 <= sx < w - 1 and 0 <= sy < h - 1):
                p[i] = [self.rng.random() * 2 - 1, self.rng.random() * 2 - 1, 1.0]
                continue
            for k in range(trail, 0, -1):                 # streaks behind the star when the bass is up
                zz = z + speed * k * 2
                tx, ty = int(cx + x / zz * cx), int(cy + y / zz * cy)
                if (tx, ty) != (sx, sy) and 0 <= tx < w - 1 and 0 <= ty < h - 1:
                    self.put(ty, tx, "·", self.fg((1 - z) * 0.5, base=STAR_FG))
            ch = "·" if z > 0.6 else ("•" if z > 0.3 else "●")
            self.put(sy, sx, ch, self.fg(1 - z, z < 0.25, base=STAR_FG))

    # ---- wave (stereo waveform, left above right)
    def draw_wave(self, h, w):
        an = self.an
        st = self.cap.samples()
        cv = Canvas(h, w)
        n = cv.gw
        idx = np.linspace(0, len(st) - 1, n).astype(int)
        gain = min(8.0, 0.9 / max(0.05, float(np.abs(st).max())))
        half = cv.gh // 2
        lw = self.stroke(h, w)
        for chan, (top, hh) in enumerate(((0, half), (half, cv.gh - half))):
            ys = top + hh / 2 - st[idx, chan] * gain * (hh / 2 - 1)
            amp = np.abs(st[idx, chan] * gain)                # loud swings go white, quiet stays cyan
            for x in range(1, n):
                cv.line(x - 1, ys[x - 1], x, ys[x], 0.3 + min(1.0, amp[x]) * 0.7, width=lw)
        cv.paint(self, an.beat > 0.3, base=WAVE_FG)
        self.put(0, 1, "L", self.fg(0.5, base=WAVE_FG))
        self.put((h - 1) // 2, 1, "R", self.fg(0.5, base=WAVE_FG))

    # ---- radial (spectrum around a circle, bass at the top, mirrored left/right)
    def draw_radial(self, h, w):
        an = self.an
        cv = Canvas(h, w)
        cx, cy = cv.gw / 2, cv.gh / 2
        rmax = min(cx, cy) * 0.95
        rmin = rmax * (0.18 + an.beat * 0.1)
        rot = self.hue * 2 * math.pi
        lw = self.stroke(h, w)
        for i in range(BANDS):
            r = rmin + an.level[i] * (rmax - rmin)
            col = 0.2 + an.level[i] * 0.8                     # quiet bands orange, loud ones gold
            for sign in (1, -1):
                a = -math.pi / 2 + rot + sign * (i + 0.5) / BANDS * math.pi
                cv.line(cx + math.cos(a) * rmin, cy + math.sin(a) * rmin,
                        cx + math.cos(a) * r, cy + math.sin(a) * r, col, width=lw)
        for o in range(lw):
            cv.circle(cx, cy, rmin * 0.85 - o, 0.6 + an.bass * 0.4)
        cv.paint(self, an.beat > 0.3, base=RADIAL_FG)

    # ---- particles (fireworks: each beat launches a burst in its own colour)
    def draw_particles(self, h, w):
        an = self.an
        st = self.state("particles", h, w, lambda: {"p": np.zeros((0, 6))})
        p = st["p"]                                       # x, y, vx, vy, life, hue
        d = self.density(h, w)                            # speeds are in cells per frame: a finer grid needs faster sparks
        k = int((an.beat * 80 + an.rms * 10) * d)
        if k:
            if an.beat > 0.15:                            # a real beat: one shell, one colour, off-centre
                ox = (w - 1) * (0.25 + self.rng.random() * 0.5)
                oy = (h - 1) * (0.25 + self.rng.random() * 0.4)
                hue = np.full(k, self.rng.random()) + self.rng.random(k) * 0.08
            else:                                         # quiet trickle: a few sparks of every colour
                ox, oy = (w - 1) / 2, (h - 1) * 0.6
                hue = self.rng.random(k)
            ang = self.rng.random(k) * 2 * math.pi
            spd = (0.4 + self.rng.random(k)) * (0.6 + an.bass * 2) * d
            new = np.column_stack([np.full(k, ox), np.full(k, oy),
                                   np.cos(ang) * spd * 2.2, np.sin(ang) * spd - (0.3 + an.beat) * d,
                                   np.ones(k), hue % 1.0])
            p = np.vstack([p, new])
        if len(p):
            p[:, 0] += p[:, 2]
            p[:, 1] += p[:, 3]
            p[:, 3] += 0.07 * d                           # gravity
            p[:, 2] *= 0.985
            p[:, 4] -= 0.015 + 0.02 * (1 - min(1.0, an.rms * 4))
            keep = ((p[:, 4] > 0) & (p[:, 0] >= 0) & (p[:, 0] < w - 1)
                    & (p[:, 1] >= 0) & (p[:, 1] < h - 1))
            p = p[keep][-int(700 * d * d):]
            for x, y, _, _, life, hue in p:
                self.put(int(y), int(x), "●" if life > 0.7 else ("•" if life > 0.35 else "·"),
                         self.fg(hue, life > 0.85, base=SPARK_FG))
        st["p"] = p

    # ---- meters (big VU: L, R, bass, mid, treble with peak hold)
    def draw_meters(self, h, w):
        an = self.an
        st = self.state("meters", h, w, lambda: {"pk": np.zeros(5)})
        l, r = an.rms_lr
        to_db = lambda x: min(1.0, max(0.0, (20 * math.log10(x + 1e-6) + 42) / 42))   # -42..0 dB -> 0..1
        vals = np.array([to_db(l), to_db(r), an.bass, an.mid, an.treble])
        st["pk"] = np.where(vals > st["pk"], vals, st["pk"] - 0.006)
        names = ["L", "R", "bass", "mid", "treble"]
        rows = max(1, (h - 1) // 5)
        bar_h = max(1, rows - 1)
        x0, segs = 8, max(4, w - 10)
        for m in range(5):
            y0 = m * rows + (rows - bar_h) // 2
            if y0 + bar_h > h - 1:
                break
            self.put(y0 + bar_h // 2, 1, f"{names[m]:>6}", self.fg(vals[m], vals[m] > 0.85, base=METER_FG))
            filled = int(vals[m] * segs)
            i = 0
            while i < filled:                             # runs of equal colour along the green/yellow/red scale
                c = int(i / segs * self.npal)
                j = i
                while j < filled and int(j / segs * self.npal) == c:
                    j += 1
                for yy in range(bar_h):
                    self.put(y0 + yy, x0 + i, "█" * (j - i), self.fg(i / segs, base=METER_FG))
                i = j
            pk = min(segs - 1, int(st["pk"][m] * segs))
            if pk > filled:
                for yy in range(bar_h):
                    self.put(y0 + yy, x0 + pk, "▌", self.fg(pk / segs, True, base=METER_FG))
            for yy in range(bar_h):                       # faint scale
                for x in range(filled + 1, segs, 10):
                    if x != pk:
                        self.put(y0 + yy, x0 + x, "·", curses.A_DIM)

    # ---- spiral (rotating three-arm spiral that flares with each band)
    def draw_spiral(self, h, w):
        an = self.an
        cv = Canvas(h, w)
        cx, cy = cv.gw / 2, cv.gh / 2
        big = min(cx, cy) * 0.95
        arms, n = 3, 160
        rot = self.t * (0.4 + an.bass * 2.5) + self.hue * 2
        twist = 2.2 + an.mid * 2
        lw = self.stroke(h, w)
        for arm in range(arms):
            px = py = None
            for k in range(n):
                f = k / (n - 1)
                lvl = an.level[int(f * (BANDS - 1))]
                rad = f * big * (0.5 + lvl * 0.5)
                a = f * math.pi * twist + rot + arm * 2 * math.pi / arms
                x, y = cx + math.cos(a) * rad, cy + math.sin(a) * rad
                if px is not None:
                    cv.line(px, py, x, y, min(1.0, f * 0.6 + lvl * 0.4), width=lw)   # purple core -> pink tips
                px, py = x, y
        cv.paint(self, an.beat > 0.3, base=SPIRAL_FG)

    # ---- life (Conway's Life, seeded by the beat where the spectrum is loud)
    def draw_life(self, h, w):
        an = self.an
        hh, ww = h - 1, w - 1

        def init():
            g = (self.rng.random((hh, ww)) < 0.12).astype(np.uint8)
            return {"g": g, "age": g.astype(np.int32), "tick": 0}

        st = self.state("life", h, w, init)
        st["tick"] += 1
        every = max(1, int(5 - min(1.0, an.rms * 5) * 4))     # louder -> faster generations
        if st["tick"] % every == 0:
            g = st["g"]
            nb = sum(np.roll(np.roll(g, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx)
            g = ((nb == 3) | ((g == 1) & (nb == 2))).astype(np.uint8)
            prob = an.level[self.band_cols(ww)] * (0.003 + an.beat * 0.08)
            g |= (self.rng.random((hh, ww)) < prob[None, :]).astype(np.uint8)
            st["age"] = np.where(g, st["age"] + 1, 0)
            st["g"] = g
        v = np.clip(st["age"] / 25.0, 0, 1)                  # newborn dark green -> old cells white
        self.field(v, mask=st["g"] == 1, base=LIFE_BG)

    # ---- loop
    # ---- poseidon (the Earth Shaker swims the swell, dives, and lurks on the bottom)
    SWIM = [  # two stroke frames, facing right; mirrored for left. Ψ is the trident, ò ó the eyes.
        ["        Ψ    ", "  (ò_ó)_|__  ", " _/ \\  )  \\_ ", "      \\/     "],
        ["        Ψ    ", "  (ò_ó)_|__  ", " _/ \\  )  \\_ ", "     /\\      "],
    ]
    LURK = [  # crouched on the bottom, trident across the knees, eyes open
        ["   (ò_ó)     ", "  _/   \\_    ", " /  Ψ==== \\  ", "_|_______|_  "],
        ["   (ò_ó)     ", "  _/   \\_    ", " /  Ψ==== \\  ", "_|_______|_  "],
    ]
    MIRROR = str.maketrans("/\\()òó<>`'", "\\/)(óò><'`")
    # the cast (all drawn facing right; mirrored when they swim left)
    FAUNA = {
        "shark": {"frames": [["        /\\      ", "  ~~^~~/  \\____ ", " <__  o      __>", "    \\/\\/      "]],
                  "base": "wave", "col": 0.55, "bold": False},
        "whale": {"frames": [["       _.--~~~~~~~--._    ", "  _.-'`    o           `-.", "   `~~~~~~~~~~~~~~~~~~~~~'"]],
                  "base": "wave", "col": 0.75, "bold": True},
        "dolphin": {"frames": [["   __,-.      ", "  (   `-.__/\\ ", "   `-.____)   "]],
                    "base": "star", "col": 0.95, "bold": True},
        "jelly": {"frames": [[" .-\"-. ", "(     )", " `|||' ", "  |||  ", "  | |  "],
                             [" .--.  ", "(    ) ", " `||'  ", "  ||   ", "  ||   "]],
                  "base": "spiral", "col": 0.7, "bold": False},
        "crab": {"frames": [["(\\/) (°,,°) (\\/)", "   /\\/\\/\\/\\   "], ["(\\/) (°,,°) (\\/)", "   \\/\\/\\/\\/   "]],
                 "base": "radial", "col": 0.6, "bold": True},
    }
    FAUNA_BASE = {"wave": "WAVE_FG", "star": "STAR_FG", "spiral": "SPIRAL_FG", "radial": "RADIAL_FG"}

    def spawn_fauna(self, st, h, w, surf, an):
        """Now and then someone else shows up. Never everyone at once: three at most, one of a kind
        (two jellyfish), and the music has a say: bass brings sharks, beats launch dolphins."""
        fauna = st["fauna"]
        if len(fauna) >= 3:
            return
        kinds = [f["kind"] for f in fauna]
        p = self.rng.random()
        per_s = 1 / FPS
        sw = len(self.FAUNA["shark"]["frames"][0][0])
        bottom = h - 2
        if "dolphin" not in kinds and ((an.beat > 0.4 and p < 0.35) or p < per_s / 60):
            d = 1 if self.rng.random() < 0.5 else -1
            fauna.append({"kind": "dolphin", "x": -14.0 if d > 0 else float(w), "dir": d, "prog": 0.0,
                          "jx": self.rng.random() * (w - 40) + 20})
        elif "shark" not in kinds and p < per_s / (40 - an.bass * 30):
            d = 1 if self.rng.random() < 0.5 else -1
            fauna.append({"kind": "shark", "x": -sw if d > 0 else float(w), "dir": d,
                          "y": float(self.rng.integers(int(surf.max()) + 2, max(int(surf.max()) + 3, bottom - 6)))})
        elif "whale" not in kinds and p < per_s / 90:
            d = 1 if self.rng.random() < 0.5 else -1
            fauna.append({"kind": "whale", "x": -26.0 if d > 0 else float(w), "dir": d, "spout": 0})
        elif kinds.count("jelly") < 2 and p < per_s / 25:
            fauna.append({"kind": "jelly", "x": float(self.rng.integers(2, max(3, w - 10))), "dir": 1,
                          "y": float(self.rng.integers(int(surf.max()) + 2, max(int(surf.max()) + 3, bottom - 5))),
                          "ph": self.rng.random() * 6.28, "life": 20 + self.rng.random() * 25})
        elif "crab" not in kinds and p < per_s / 50:
            d = 1 if self.rng.random() < 0.5 else -1
            fauna.append({"kind": "crab", "x": -16.0 if d > 0 else float(w), "dir": d, "life": 40 + self.rng.random() * 40,
                          "pause": 0})

    def draw_fauna(self, st, h, w, surf, an):
        keep = []
        for f in st["fauna"]:
            k = f["kind"]
            spec = self.FAUNA[k]
            frames = spec["frames"]
            fph = f.setdefault("fph", int(self.rng.integers(16)))       # its own stroke: no two swim in step
            frame = frames[((self.frame + fph) // 8) % len(frames)]
            fw, fh = len(frame[0]), len(frame)
            alive = True
            if k == "shark":
                f["x"] += f["dir"] * (0.22 + an.bass * 0.35 + an.beat * 0.3)
                y = f["y"] + math.sin(self.t * 1.5 + fph) * 0.8
                alive = -fw < f["x"] < w
            elif k == "whale":
                f["x"] += f["dir"] * 0.07
                cx = min(max(int(f["x"]) + fw // 2, 0), w - 2)
                y = surf[cx] - 1                                  # back just breaking the surface
                if an.bass > 0.45 and f["spout"] <= 0:
                    f["spout"] = 18
                if f["spout"] > 0:                                # the spout, from the blowhole
                    f["spout"] -= 1
                    hx = int(f["x"]) + (fw // 2 + 2 if f["dir"] > 0 else fw // 2 - 3)
                    for r, ch in enumerate(("'", ":", "'", ".", " "[:1])[:min(4, f["spout"] // 4 + 1)]):
                        self.put(int(y) - 1 - r, hx + (r % 2) * (1 if r % 3 else -1), ch, self.fg(0.9, True, base=WAVE_FG))
                alive = -fw < f["x"] < w
            elif k == "dolphin":
                f["x"] += f["dir"] * 0.55
                cx = min(max(int(f["x"]) + fw // 2, 0), w - 2)
                dist = abs(f["x"] + fw / 2 - f["jx"])
                jump = max(0.0, 1 - (dist / 14) ** 2)             # a parabola over the jump point
                y = surf[cx] - 1 - jump * (5 + an.beat * 4)
                if 0 < dist < 2 and jump > 0.9 and self.frame % 2 == 0:
                    self.put(int(surf[cx]), cx, "*", self.fg(1.0, True, base=WAVE_FG))   # the splash
                alive = -fw < f["x"] < w
            elif k == "jelly":
                f["life"] -= 1 / FPS
                f["x"] += math.sin(self.t * 0.4 + f["ph"]) * 0.06
                f["y"] += math.cos(self.t * 0.25 + f["ph"]) * 0.05 - an.beat * 0.2
                y = min(max(f["y"], surf.max() + 1), h - 2 - fh)
                alive = f["life"] > 0 and 0 <= f["x"] < w - fw
            elif k == "crab":
                f["life"] -= 1 / FPS
                if f["pause"] > 0:
                    f["pause"] -= 1
                else:
                    f["x"] += f["dir"] * (0.12 + an.beat * 0.5)
                    if self.rng.random() < 0.004:
                        f["pause"] = int(FPS * (1 + self.rng.random() * 2))
                    if self.rng.random() < 0.003 and 0 < f["x"] < w - fw:
                        f["dir"] *= -1
                y = h - 1 - fh
                alive = -fw < f["x"] < w and (f["life"] > 0 or (0 <= f["x"] < w - fw))
                if f["life"] <= 0 and 0 <= f["x"] < w - fw:      # time to go: walk off the nearest edge
                    f["dir"] = -1 if f["x"] < w / 2 else 1
            if not alive:
                continue
            keep.append(f)
            px, py = int(f["x"]), int(y)
            base = globals()[self.FAUNA_BASE[spec["base"]]]
            col = spec["col"] + (0.25 * abs(math.sin(self.t * 3)) if k == "jelly" else 0)
            for i, row in enumerate(frame):
                if f["dir"] < 0:
                    row = row[::-1].translate(self.MIRROR)
                first = len(row) - len(row.lstrip())
                last = len(row.rstrip())
                yy = py + i
                if not (0 <= yy < h - 1):
                    continue
                if yy >= surf[min(max(px + fw // 2, 0), w - 2)] - 1:   # a dark halo, but only under water
                    x0, x1 = max(0, px + first), min(w - 1, px + last)
                    if x1 > x0:
                        self.put(yy, x0, " " * (x1 - x0), curses.color_pair(WATER_BG))
                for j, ch in enumerate(row):
                    xx = px + j
                    if ch != " " and 0 <= xx < w - 1:
                        self.put(yy, xx, ch, self.fg(col, spec["bold"], base=base))
        st["fauna"] = keep

    def draw_poseidon(self, h, w):
        an = self.an
        st = self.state("poseidon", h, w, lambda: {
            "x": 2.0, "y": None, "dir": 1, "phase": "surface", "until": self.t + 8, "quiet": 0.0,
            "bub": np.zeros((0, 3)), "shake": 0, "fauna": [],
            "stars": np.column_stack([self.rng.random(50) * (w - 1), self.rng.random(50) * max(1, h // 3),
                                      self.rng.random(50)])})
        hz = int(h * 0.3)                                        # horizon row
        t = self.t
        x = np.arange(w - 1)
        amp = 0.5 + an.bass * (h * 0.10) + an.beat * 1.5         # swell height in rows
        surf = (hz + amp * np.sin(x * 0.16 - t * 1.6) + amp * 0.4 * np.sin(x * 0.37 + t * 2.4)
                + 0.4 * np.sin(x * 0.06 + t * 0.5))
        if an.beat > 0.35:                                       # Earth Shaker
            st["shake"] = 3
        dx = dy = 0
        if st["shake"] > 0:
            st["shake"] -= 1
            dx, dy = int(self.rng.integers(-1, 2)), int(self.rng.integers(-1, 2))
        # sky: a few stars, twinkling with the treble
        for sx, sy, ph in st["stars"]:
            band = int(sx / max(1, w - 1) * (BANDS // 2)) + BANDS // 2
            tw = 0.2 + 0.8 * abs(math.sin(t * 1.5 + ph * 6.28)) * (0.3 + an.level[min(BANDS - 1, band)])
            if sy + dy < surf[min(int(sx), w - 2)] - 1 and tw > 0.45:
                self.put(int(sy) + dy, int(sx) + dx, "✦" if tw > 0.85 else "·", self.fg(tw, tw > 0.85, base=STAR_FG))
        # sea: dark, depth-shaded, brighter near the surface so the figure stands out below
        rows = np.arange(h - 1)[:, None]
        depth = (rows - surf[None, :]) / max(1.0, (h - 1) - hz)
        under = rows >= surf[None, :]
        v = np.clip(0.55 - depth * 0.9 + an.bass * 0.1, 0.0, 0.999)
        self.field(v, mask=under, base=WATER_BG)
        # foam only on the crests
        for xx in range(0, w - 1):
            yy = int(surf[xx])
            if 0 <= yy < h - 1 and surf[xx] <= surf[max(0, xx - 1)] and surf[xx] <= surf[min(w - 2, xx + 1)]:
                self.put(yy + dy, xx + dx, "≈" if an.treble > 0.35 else "~", self.fg(0.9, an.treble > 0.35, base=WAVE_FG))
        # the others: sharks, a whale, dolphins, jellyfish, a crab; behind Poseidon
        self.spawn_fauna(st, h, w, surf, an)
        self.draw_fauna(st, h, w, surf, an)
        # ---- where is he: surface -> dive -> lurk -> rise -> surface
        sw, sh = len(self.SWIM[0][0]), len(self.SWIM[0])
        bottom = h - 1 - sh
        cx = min(max(int(st["x"]) + sw // 2, 0), w - 2)
        top_y = surf[cx] - 2
        if st["y"] is None:
            st["y"] = top_y
        st["quiet"] = st["quiet"] + 1 / FPS if an.rms < 0.06 else 0.0
        ph = st["phase"]
        if ph == "surface":
            st["y"] = top_y
            if t > st["until"] or st["quiet"] > 3:            # bored, or the music went quiet: down he goes
                st["phase"], st["until"] = "dive", t + 60
        elif ph == "dive":
            st["y"] += 0.12 + an.bass * 0.1
            if st["y"] >= bottom:
                st["y"] = bottom
                st["phase"], st["until"] = "lurk", t + 6 + self.rng.random() * 10
        elif ph == "lurk":
            st["y"] = bottom
            if t > st["until"] or an.beat > 0.55:             # a big beat wakes the Earth Shaker
                st["phase"], st["until"] = "rise", t + 60
        elif ph == "rise":
            st["y"] -= 0.25 + an.beat * 0.6 + an.bass * 0.15
            if st["y"] <= top_y:
                st["phase"], st["until"] = "surface", t + 8 + self.rng.random() * 12
        speed = {"surface": 0.12 + an.rms * 1.6, "dive": 0.05, "lurk": 0.02, "rise": 0.1}[st["phase"]]
        st["x"] += st["dir"] * speed
        if st["x"] > w - sw - 2:
            st["dir"] = -1
        if st["x"] < 1:
            st["dir"] = 1
        px, py = int(st["x"]) + dx, int(st["y"]) + dy
        frames = self.LURK if st["phase"] == "lurk" else self.SWIM
        frame = frames[(self.frame // 6) % 2]
        # a dark halo behind him so he reads against the water
        for i in range(sh):
            self.put(py + i, px, " " * sw, curses.color_pair(WATER_BG))
        for i, row in enumerate(frame):
            if st["dir"] < 0:
                row = row[::-1].translate(self.MIRROR)
            for j, ch in enumerate(row):
                if ch == " ":
                    continue
                yy, xx = py + i, px + j
                if not (0 <= yy < h - 1 and 0 <= xx < w - 1):
                    continue
                if ch == "Ψ":
                    self.put(yy, xx, ch, self.fg(0.7 + an.beat, True, base=RADIAL_FG))
                    if an.beat > 0.3 and st["phase"] != "lurk":       # the trident lights the sky
                        for k in range(1, yy + 1):
                            zig = xx + int(math.sin(k * 1.3 + t * 40) * 1.2 * an.beat * 3)
                            self.put(yy - k, zig, "│" if k % 3 else "╱", self.fg(0.95, True, base=WAVE_FG))
                elif ch in "òó":
                    self.put(yy, xx, ch, self.fg(1.0, True, base=RADIAL_FG))   # the eyes burn
                elif ch == "=":
                    self.put(yy, xx, ch, self.fg(0.6, False, base=RADIAL_FG))
                else:
                    self.put(yy, xx, ch, self.fg(0.99, True, base=WAVE_FG))
        # bubbles: a trail while he moves under water, a few while he lurks
        bub = st["bub"]
        k = int(an.mid * 2 + an.beat * 3) if st["phase"] in ("dive", "rise") else (1 if self.frame % 24 == 0 else 0)
        if k and st["phase"] != "surface":
            new = np.column_stack([px + sw // 2 + self.rng.random(k) * 4 - 2, np.full(k, py - 0.0), np.ones(k)])
            bub = np.vstack([bub, new])
        if len(bub):
            bub[:, 1] -= 0.2 + an.mid * 0.4
            bub[:, 0] += (self.rng.random(len(bub)) - 0.5) * 0.5
            bub[:, 2] -= 0.015
            keep = (bub[:, 2] > 0) & (bub[:, 0] >= 0) & (bub[:, 0] < w - 1) & (bub[:, 1] >= 0)
            bub = bub[keep][-120:]
            for bx, by, life in bub:
                if by >= surf[min(int(bx), w - 2)]:
                    self.put(int(by) + dy, int(bx) + dx, "°" if life > 0.5 else "·", self.fg(0.85, False, base=WAVE_FG))
        st["bub"] = bub
        if an.beat > 0.5:
            self.put(1, max(0, (w - 12) // 2) + dx, "EARTH SHAKER", self.fg(1.0, True, base=RADIAL_FG))
        self.put(h - 2, 1, {"surface": "", "dive": "diving…", "lurk": "lurking", "rise": "rising!"}[st["phase"]],
                 self.fg(0.5, False, base=WAVE_FG))

    # ---- enik (the Altrusian, head to foot, moving the way the costume did)
    HISS = ["sss", "Ssssss", "SSSssss", "sssSSS"]
    ENIK_SAYS = ["the doorway will not open", "you are not my ancestors", "I must return to Altrusia",
                 "do not touch the crystals", "the Mageti has been moved"]

    def draw_enik(self, h, w):
        an = self.an
        t = self.t
        st = self.state("enik", h, w, lambda: {
            "x": 0.5, "dir": 1, "phase": 0, "tick": -1, "arm": [70.0, 70.0], "fore": [40.0, 40.0],
            "lean": 0.0, "look": 0.0, "quiet": 0.0, "hiss": 0, "say": None, "say_until": 0.0,
            "bob": 0.0, "swing": 0.0, "crystals": np.zeros(BANDS)})
        cv = Canvas(h, w)
        gw, gh = cv.gw, cv.gh
        # the pose changes only on the tick, four times a second, and each change is a jolt
        tick = int(t * 4)
        moved = tick != st["tick"]
        st["quiet"] = st["quiet"] + 1 / FPS if an.rms < 0.05 else 0.0
        quiet = st["quiet"] > 2
        if moved:
            st["tick"] = tick
            if not quiet:
                st["phase"] = (st["phase"] + 1 + (1 if an.beat > 0.3 else 0)) % 8   # a beat lands a step early
                jolt = 8 + an.beat * 25
                for i in range(2):
                    st["arm"][i] = float(np.clip(70 + self.rng.integers(-1, 2) * jolt + an.beat * 15, 40, 100))
                    st["fore"][i] = float(np.clip(40 + self.rng.integers(-1, 2) * jolt - an.beat * 20, -10, 80))
                st["lean"] = float(self.rng.integers(-1, 2)) * (0.02 + an.beat * 0.04)
                step = 0.012 + an.rms * 0.03
                st["x"] += st["dir"] * step
                if st["x"] > 0.78 or st["x"] < 0.22:
                    st["dir"] *= -1
                    st["look"] = 0.0
                else:
                    st["look"] = st["dir"] * 0.012
            else:                                              # nothing to hear: he stops, arms down
                st["arm"] = [max(20.0, a - 10) for a in st["arm"]]
                st["fore"] = [max(-20.0, f - 10) for f in st["fore"]]
                st["lean"] = 0.0
            if an.beat > 0.4 and st["hiss"] <= 0:
                st["hiss"] = 10
            if quiet and t > st["say_until"]:
                st["say"] = self.ENIK_SAYS[int(self.rng.integers(len(self.ENIK_SAYS)))] if self.rng.random() < 0.5 else None
                st["say_until"] = t + 6
        st["hiss"] = max(0, st["hiss"] - 1)
        # geometry: H is his height in dots; everything is a fraction of it
        floor = h - 2                                          # the row he stands on
        H = min(floor * 4 - 8, gw / 1.05)
        top = floor * 4 - 2 - H
        cx0 = st["x"] * gw
        ph = st["phase"]
        lift_l = (0, 0.5, 1, 0.5, 0, 0, 0, 0)[ph]              # which foot is off the ground, quantised
        lift_r = (0, 0, 0, 0, 0, 0.5, 1, 0.5)[ph]
        bob = -(lift_l + lift_r) * 0.015 * H                   # he rises a little on the lifted step
        sway = (lift_l - lift_r) * 0.035 * H                   # weight over the standing leg
        lean = st["lean"] * H

        def P(u, v):                                          # figure units -> canvas dots
            return cx0 + sway + u * H + v * lean, top + bob + v * H
        # ---- the time doorway behind him: three broken rings that open with the bass
        door = Canvas(h, w)
        dcx, dcy = P(0, 0.42)
        for k in range(3):
            r = (0.16 + k * 0.10) * H * (0.6 + an.bass * 1.2)
            spin = t * (0.8 - k * 0.3) * (1 if k % 2 else -1)
            for a in np.linspace(0, 2 * math.pi, int(r * 3), endpoint=False):
                if (a + spin) % (math.pi / 2) < math.pi / 2.6:   # four arcs with gaps
                    door.dot(dcx + math.cos(a) * r * 1.0, dcy + math.sin(a) * r, 0.3 + k * 0.2 + an.bass * 0.3)
        # ---- the body: green hide, front view
        body = Canvas(h, w)
        tunic = Canvas(h, w)
        eyes = Canvas(h, w)
        gem = Canvas(h, w)
        skin = 0.45 + an.mid * 0.3
        lw = max(2, int(H / 60))                               # limb width in dots
        # head: dome, then the jaw tapering to the chin
        hx, hy = P(0, 0.13)
        body.ellipse(hx, hy, 0.145 * H, 0.13 * H, skin)
        body.poly([P(-0.12, 0.17), P(0.12, 0.17), P(0.05, 0.30), P(-0.05, 0.30)], skin)
        # brow ridge, darker
        body.line(*P(-0.11, 0.105), *P(-0.02, 0.09), skin * 0.5, width=lw)
        body.line(*P(0.02, 0.09), *P(0.11, 0.105), skin * 0.5, width=lw)
        # the eyes: huge, dark, and they flash on the beat
        flash = 0.12 + min(1.0, an.beat * 2.5) * 0.88
        for sx in (-1, 1):
            ex, ey = P(sx * 0.065 + st["look"], 0.155)
            eyes.ellipse(ex, ey, 0.04 * H, 0.05 * H, flash)
        # mouth: a slit, open when he hisses
        if st["hiss"] > 0:
            body.poly([P(-0.045, 0.245), P(0.045, 0.245), P(0.025, 0.275), P(-0.025, 0.275)], 0.1)
        else:
            body.line(*P(-0.04, 0.255), *P(0.04, 0.255), skin * 0.4, width=lw)
        # neck and shoulders
        body.line(*P(0, 0.29), *P(0, 0.35), skin, width=lw * 2)
        # the tunic, and the medallion at the collar
        tunic.poly([P(-0.19, 0.34), P(0.19, 0.34), P(0.16, 0.66), P(-0.16, 0.66)], 0.25 + an.bass * 0.2)
        tunic.line(*P(-0.19, 0.34), *P(0.19, 0.34), 0.6, width=lw)
        gx, gy = P(0, 0.405)
        gem.ellipse(gx, gy, 0.035 * H, 0.035 * H, (self.hue + 0.5) % 1.0)
        # arms: stiff, out and up, jointed at angles that only change on the tick
        for i, sx in enumerate((-1, 1)):
            a1 = math.radians(st["arm"][i])
            a2 = math.radians(st["arm"][i] + st["fore"][i])
            s0 = P(sx * 0.19, 0.36)
            e = (s0[0] + sx * math.sin(a1) * 0.19 * H, s0[1] + math.cos(a1) * 0.19 * H)
            hnd = (e[0] + sx * math.sin(a2) * 0.18 * H, e[1] + math.cos(a2) * 0.18 * H)
            body.line(*s0, *e, skin, width=lw + 1)
            body.line(*e, *hnd, skin, width=lw)
            for k in (-1, 0, 1):                               # three claws, fanned
                ca = a2 + k * 0.45
                body.line(*hnd, hnd[0] + sx * math.sin(ca) * 0.05 * H, hnd[1] + math.cos(ca) * 0.05 * H, skin * 0.8)
        # legs: the lifted one bends at the knee, out to the side, and the foot comes up
        for sx, lift in ((-1, lift_l), (1, lift_r)):
            hip = P(sx * 0.08, 0.64)
            knee = (hip[0] + sx * (0.02 + lift * 0.07) * H, hip[1] + (0.18 - lift * 0.03) * H)
            foot = (knee[0] + sx * 0.01 * H, knee[1] + (0.18 - lift * 0.07) * H)
            body.line(*hip, *knee, skin, width=lw + 1)
            body.line(*knee, *foot, skin, width=lw + 1)
            body.line(foot[0] - 0.02 * H, foot[1], foot[0] + sx * 0.07 * H, foot[1], skin * 0.8, width=lw)
        # ---- paint: floor, the crystal matrix, the doorway, then him in front of it all
        self.put(floor, 0, "▔" * (w - 1), self.fg(0.3 + an.bass * 0.3, False, base=RADIAL_FG))
        # the crystal matrix: one crystal per band, lit by its level, in the pylon's corner
        cols, rows = 12, 3
        st["crystals"] = np.maximum(an.level, st["crystals"] * 0.9)
        mx = w - 2 - cols * 2
        for c in range(cols):
            lvl = st["crystals"][int(c * BANDS / cols)]
            for r in range(rows):
                lit = lvl > (r + 0.5) / rows
                self.put(floor - 1 - r, mx + c * 2, "◆" if lit else "◇",
                         self.fg(c / cols, lit, base=SPARK_FG) if lit else curses.A_DIM)
        door.paint(self, bold=an.bass > 0.4, base=SPIRAL_FG)
        for (cy, cx), _ in body.cells.items():                 # a dark halo so he reads against the doorway
            self.put(cy, cx, " ")
        tunic.paint(self, bold=False, base=RADIAL_FG)
        body.paint(self, bold=True, base=RAIN_FG)
        eyes.paint(self, bold=an.beat > 0.3, base=STAR_FG)
        gem.paint(self, bold=True, base=SPARK_FG)
        # ---- words
        if st["hiss"] > 0:
            mxx, myy = P(0.13, 0.25)
            self.put(int(myy / 4), int(mxx / 2), self.HISS[(self.frame // 3) % len(self.HISS)],
                     self.fg(0.95, True, base=RAIN_FG))
        if an.beat > 0.5:
            self.put(1, max(0, (w - 4) // 2), "ENIK", self.fg(1.0, True, base=RAIN_FG))
        if quiet and st["say"]:
            self.put(h - 2, 1, st["say"], self.fg(0.6, False, base=RAIN_FG))

    # ---- cyclops (Polyphemus at home)
    SHEEP = [["  ,ww,  ", "°(wwww) ", "  ll ll "], ["  ,ww,  ", "°(wwww) ", "  ll ll "]]
    SHEEP_HIDING = [["  ,ww,  ", "°(wwww) ", " ll l ll"], ["  ,ww,  ", "°(wwww) ", "l ll ll "]]
    MAN = [[" o ", "/|\\", "/ \\"], [" o ", "/|\\", " | "]]
    GRABBED = [" o ", "\\|/", "/ \\"]

    def draw_cyclops(self, h, w):
        an = self.an
        t = self.t
        floor = h - 2
        st = self.state("cyclops", h, w, lambda: {
            "tick": -1, "phase": "lounge", "step": 0, "hand": None, "target": None, "held": None,
            "eaten": 0, "cool": 0.0, "quiet": 0.0, "asleep": False, "sleep_t": 0.0, "stake": None,
            "roar": 0.0, "shake": 0, "blink": 0, "flock": [], "zz": [], "reset_at": 0.0})
        cv_gw, cv_gh = max(2, (w - 1) * 2), max(4, (h - 1) * 4)
        # ---- clock: the giant moves on the tick, four times a second, like Enik
        tick = int(t * 4)
        moved = tick != st["tick"]
        st["tick"] = tick
        st["quiet"] = st["quiet"] + 1 / FPS if an.rms < 0.05 else 0.0
        ph = st["phase"]
        # ---- geometry: H is the cave height in dots; he spans most of the width
        H = min(floor * 4 - 8, cv_gw * 0.95)
        ox = 4.0
        oy = floor * 4 - 2 - 0.92 * H
        shake = 0
        if st["shake"] > 0:
            st["shake"] -= 1
            shake = int(self.rng.integers(-2, 3))

        def P(u, v):
            return ox + u * H + shake, oy + v * H
        # ---- the flock: sheep and men on the floor rows, wandering on the tick
        flock = st["flock"]
        want = 3 + int(an.treble * 6)
        if ph != "roar" and len(flock) < want and self.rng.random() < 0.05:
            kind = "man" if sum(f["kind"] == "man" for f in flock) < 3 and self.rng.random() < 0.4 else "sheep"
            flock.append({"kind": kind, "x": float(w - 9), "dir": -1, "hide": kind == "man" and self.rng.random() < 0.5,
                          "until": t + 4 + self.rng.random() * 8, "run": False})
        keep = []
        for f in flock:
            if f["run"]:                                             # out of the cave, fast
                f["x"] += 1.6 + an.rms * 2
                if f["x"] < w:
                    keep.append(f)
                continue
            if moved:
                if self.rng.random() < 0.3:
                    f["dir"] = -f["dir"] if self.rng.random() < 0.3 else f["dir"]
                    f["x"] += f["dir"] * (1 + an.treble * 2)
                if f["kind"] == "man" and t > f["until"]:            # men slip under a sheep, and back out
                    f["hide"] = not f["hide"]
                    f["until"] = t + 4 + self.rng.random() * 10
            f["x"] = min(max(f["x"], 0.32 * H / 2), w - 9)           # not through the giant
            for g in keep:                                           # and not through each other
                if abs(g["x"] - f["x"]) < 7:
                    f["x"] += 7 if f["x"] >= g["x"] else -7
                    f["x"] = min(max(f["x"], 0.32 * H / 2), w - 9)
            if ph != "roar" and len(flock) > want and self.rng.random() < 0.002:
                continue
            keep.append(f)
        st["flock"] = keep
        # ---- the giant's mood: lounge -> reach -> lift -> chew -> wipe -> lounge; or asleep -> stake -> roar
        mouth = P(0.30, 0.27)
        rest = P(0.30, 0.68)
        if ph == "lounge":
            if st["quiet"] > 8 and not st["asleep"]:
                st["asleep"], st["sleep_t"] = True, t
            if an.rms > 0.08 and st["asleep"] and st["stake"] is None:
                st["asleep"] = False
            if st["asleep"] and st["stake"] is None and t - st["sleep_t"] > st.get("nap", 10):
                st["stake"] = {"x": float(cv_gw), "y": P(0, 0.20)[1], "at": None}
            if not st["asleep"] and an.beat > 0.5 and t > st["cool"]:
                men = [f for f in st["flock"] if f["kind"] == "man" and not f["hide"] and not f["run"]]
                if men:
                    st["target"] = min(men, key=lambda f: f["x"])
                    st["phase"], st["step"] = "reach", 0
            if st["hand"] is None:
                st["hand"] = rest
        if moved and ph in ("reach", "lift", "chew", "wipe"):
            st["step"] += 1
        if ph == "reach":
            tf = st["target"]
            k = min(1.0, st["step"] / 3)
            goal = (tf["x"] * 2 + 3, (floor - 1) * 4) if tf in st["flock"] else rest
            st["hand"] = (rest[0] + (goal[0] - rest[0]) * k, rest[1] + (goal[1] - rest[1]) * k)
            if st["step"] >= 3:
                if tf in st["flock"]:
                    st["flock"].remove(tf)
                    st["held"] = st["hand"]
                    st["phase"], st["step"], st["grab_from"] = "lift", 0, st["hand"]
                else:
                    st["phase"], st["step"] = "wipe", 0
        elif ph == "lift":
            k = min(1.0, st["step"] / 3)
            g = st["grab_from"]
            st["hand"] = (g[0] + (mouth[0] - g[0]) * k, g[1] + (mouth[1] - g[1]) * k)
            if st["step"] >= 3:
                st["phase"], st["step"], st["eaten"] = "chew", 0, st["eaten"] + 1
        elif ph == "chew":
            st["hand"] = mouth
            if st["step"] >= 4:
                st["phase"], st["step"] = "wipe", 0
        elif ph == "wipe":
            k = min(1.0, st["step"] / 3)
            st["hand"] = (mouth[0] + (rest[0] - mouth[0]) * k + (1 - k) * 6 * math.sin(t * 12),
                          mouth[1] + (rest[1] - mouth[1]) * k)
            if st["step"] >= 3:
                st["phase"], st["cool"] = "lounge", t + 3 + self.rng.random() * 4
        # the stake, and the roar
        stake = st["stake"]
        if stake is not None and ph == "lounge":
            if stake["at"] is None:
                stake["x"] -= 3.5
                if stake["x"] <= P(0.28, 0)[0]:
                    stake["at"] = t
            elif t - stake["at"] > 0.6 and (an.beat > 0.3 or t - stake["at"] > 2):
                st["phase"], st["roar"], st["asleep"] = "roar", t, False
                for f in st["flock"]:
                    f["run"], f["hide"] = True, f["kind"] == "man"
        if ph == "roar":
            st["shake"] = 2
            if t - st["roar"] > 5:
                st["phase"], st["stake"], st["eaten"], st["cool"] = "lounge", None, 0, t + 3
                st["flock"], st["quiet"], st["nap"] = [], 0.0, 20 + self.rng.random() * 40
        asleep = st["asleep"]
        # ---- draw: the cave, the tally, the flock, the giant, his eye
        wall = Canvas(h, w)
        prev = None
        for x in range(0, cv_gw, 2):                               # the ceiling: a jagged edge, stone hanging from it
            y = 3 + 4 * abs(math.sin(x * 0.11)) + 3 * abs(math.sin(x * 0.037 + 1))
            if prev is not None:
                wall.line(x - 2, prev, x, y, 0.2)
            prev = y
            if x % 28 == 0:
                wall.line(x, y, x + 1, y + 6 + 5 * abs(math.sin(x)), 0.15)
        wall.paint(self, bold=False, base=SPIRAL_FG)
        self.put(floor, 0, "▔" * (w - 1), self.fg(0.25 + an.bass * 0.2, False, base=RADIAL_FG))
        tally = st["eaten"]
        marks = "".join("||||/ " if i < tally // 5 else "" for i in range(tally // 5)) + "|" * (tally % 5)
        if marks:
            self.put(3, max(1, w - 3 - len(marks)), marks[-(w - 4):], self.fg(0.8, True, base=RADIAL_FG))
        for f in st["flock"]:
            if f["kind"] == "sheep" or f["hide"]:
                frame = (self.SHEEP_HIDING if f["kind"] == "man" else self.SHEEP)[(self.frame // 6) % 2]
                attr = self.fg(0.9, True, base=STAR_FG)
            else:
                frame = self.MAN[(self.frame // 6) % 2]
                attr = self.fg(0.95, True, base=WAVE_FG)
            for i, row in enumerate(frame):
                self.put(floor - len(frame) + i, int(f["x"]) + shake, row, attr)
        # the giant
        body = Canvas(h, w)
        hair = Canvas(h, w)
        skin = 0.35 + an.mid * 0.15
        breath = 0.012 * H * (0.5 + math.sin(t * 1.2) * 0.5) + an.bass * 0.03 * H
        lw = max(3, int(H / 40))
        # legs first (he lies on them): the far one straight along the floor, the near one bent up
        hip = P(0.28, 0.72)
        body.line(*hip, *P(0.90, 0.86), skin * 0.9, width=lw + 4)
        body.line(*P(0.90, 0.86), *P(0.99, 0.84), skin * 0.9, width=lw + 2)   # a foot
        knee = P(0.60, 0.50)
        body.line(*hip, *knee, skin, width=lw + 5)
        body.line(*knee, *P(0.70, 0.90), skin, width=lw + 4)
        body.line(*P(0.66, 0.90), *P(0.80, 0.90), skin, width=lw + 2)         # the other foot
        # torso, reclined against the wall, breathing
        body.poly([P(0.12, 0.34), P(0.40, 0.36), P(0.44, 0.72), P(0.10, 0.74)], skin)
        body.poly([(P(0.12, 0.34)[0], P(0.12, 0.34)[1] - breath), (P(0.40, 0.36)[0], P(0.40, 0.36)[1] - breath),
                   P(0.42, 0.55), P(0.11, 0.55)], skin)
        # the far arm rests on the knee
        body.line(*P(0.38, 0.40), *P(0.52, 0.52), skin * 0.9, width=lw + 2)
        body.line(*P(0.52, 0.52), *knee, skin * 0.9, width=lw + 2)
        # head, beard, hair
        hx, hy = P(0.24, 0.20)
        body.ellipse(hx, hy, 0.115 * H, 0.12 * H, skin)
        hair.poly([P(0.13, 0.28), P(0.35, 0.28), P(0.32, 0.40), P(0.24, 0.43), P(0.16, 0.40)], 0.12)  # the beard
        hair.poly([P(0.13, 0.15), P(0.36, 0.15), P(0.30, 0.08), P(0.19, 0.08)], 0.12)                 # the hair
        # the near arm: shoulder to the hand, wherever the hand is, with an elbow that hangs below the line
        sh = P(0.16, 0.40)
        hand = st["hand"] or rest
        mx, my = (sh[0] + hand[0]) / 2, (sh[1] + hand[1]) / 2
        dx, dy = hand[0] - sh[0], hand[1] - sh[1]
        L = math.hypot(dx, dy) or 1.0
        bend = max(0.0, 0.32 * H - L * 0.5)
        elbow = (mx + dy / L * bend, my - dx / L * bend)                    # off to the side, away from the body
        body.line(*sh, *elbow, skin, width=lw + 3)
        body.line(*elbow, *hand, skin, width=lw + 2)
        body.ellipse(hand[0], hand[1], 0.035 * H, 0.03 * H, skin)
        for (cy, cx), _ in body.cells.items():
            self.put(cy, cx, " ")
        body.paint(self, bold=False, base=RADIAL_FG)
        hair.paint(self, bold=True, base=RADIAL_FG)
        # the mouth: shut, chewing, or roaring
        mth = Canvas(h, w)
        if ph == "chew":
            o = 0.02 * H * (1 if (self.frame // 3) % 2 else 0.4)
            mth.ellipse(mouth[0], mouth[1], 0.035 * H, o, 0.05)
        elif ph == "roar":
            mth.ellipse(mouth[0], mouth[1] + 0.02 * H, 0.05 * H, 0.05 * H, 0.05)
        else:
            mth.line(mouth[0] - 0.03 * H, mouth[1], mouth[0] + 0.03 * H, mouth[1], 0.1, width=2 * self.stroke(h, w))
        mth.paint(self, bold=False, base=RADIAL_FG)
        # the eye: one, on the loudest band; blinks; shut asleep; put out after the stake
        ex, ey = P(0.28, 0.19)
        eye = Canvas(h, w)
        if moved and self.rng.random() < 0.06:
            st["blink"] = 3
        st["blink"] = max(0, st["blink"] - 1)
        if ph == "roar" or (stake is not None and stake["at"] is not None and t - stake["at"] > 0.6):
            eye.line(ex - 0.04 * H, ey - 0.04 * H, ex + 0.04 * H, ey + 0.04 * H, 0.9, width=3 * self.stroke(h, w))
            eye.line(ex - 0.04 * H, ey + 0.04 * H, ex + 0.04 * H, ey - 0.04 * H, 0.9, width=3 * self.stroke(h, w))
            eye.paint(self, bold=True, base=RADIAL_FG)
        elif asleep or st["blink"] > 0:
            eye.line(ex - 0.05 * H, ey, ex + 0.05 * H, ey, 0.2, width=2 * self.stroke(h, w))
            eye.paint(self, bold=False, base=RADIAL_FG)
        else:
            eye.ellipse(ex, ey, 0.055 * H, 0.035 * H, 0.95)
            eye.paint(self, bold=True, base=STAR_FG)
            loud = int(np.argmax(an.level)) / BANDS if an.rms > 0.02 else 0.5
            pupil = Canvas(h, w)
            pupil.ellipse(ex + (loud - 0.5) * 0.06 * H, ey, 0.018 * H, 0.02 * H, 0.05)
            pupil.paint(self, bold=False, base=STAR_FG)
        # the man in his hand
        if ph == "lift" or (ph == "chew" and st["step"] < 2):
            hx2, hy2 = int(hand[0] / 2), int(hand[1] / 4) - 1
            for i, row in enumerate(self.GRABBED):
                self.put(hy2 + i - 1, hx2 - 1, row, self.fg(0.95, True, base=WAVE_FG))
        # words and effects
        if ph == "chew" and st["step"] < 3:
            self.put(int(mouth[1] / 4) - 2, int(mouth[0] / 2) + 4 + shake, "CRUNCH", self.fg(0.9, True, base=RADIAL_FG))
        if asleep:
            if self.frame % 12 == 0:
                st["zz"].append([hx + 0.1 * H, hy - 0.1 * H, 0])
            for z in st["zz"]:
                z[1] -= 1.0
                z[2] += 1
                self.put(int(z[1] / 4), int(z[0] / 2) + (z[2] // 6) % 3, "z" if z[2] < 18 else "Z",
                         self.fg(0.6, False, base=STAR_FG))
            st["zz"] = [z for z in st["zz"] if z[1] > 4][-8:]
        else:
            st["zz"] = []
        if stake is not None and ph == "lounge":
            x1 = stake["x"] if stake["at"] is None else P(0.28, 0)[0]
            glow = 0.7 + 0.3 * abs(math.sin(t * 20))
            stk = Canvas(h, w)
            stk.line(x1, stake["y"], min(cv_gw - 1, x1 + 0.6 * H), stake["y"] + 0.03 * H, glow, width=3 * self.stroke(h, w))
            stk.paint(self, bold=True, base=RADIAL_FG)
            for k in range(3):
                self.put(int(stake["y"] / 4) - 1 - k // 2, int(x1 / 2) + k * 2, "*", self.fg(1.0, True, base=RADIAL_FG))
        if ph == "roar":
            msg = "NOBODY!" if (self.frame // 8) % 2 else "NOBODY HAS BLINDED ME!"
            self.put(1, max(0, (w - len(msg)) // 2) + shake, msg, self.fg(1.0, True, base=RADIAL_FG))
        elif an.beat > 0.5 and ph == "lounge" and not asleep:
            self.put(1, max(0, (w - 10) // 2), "POLYPHEMUS", self.fg(0.9, True, base=RADIAL_FG))

    # ---- convey (the voyage Polyphemus promised: the Earth Shaker sees Odysseus home)
    RAFT = ["    o    ", "   /|\\   ", "~[=====]~"]
    ITHACA = ["         ⌂  ", "    __/‾‾‾\\__", " __/         \\__"]
    CYCLOPS_ISLE = ["    /‾‾‾‾‾\\    ", " __/  (o)  \\__ ", "/             \\"]

    def ship_rows(self, n, oar_frame, wind):
        """The black ship, bow to the left: n companions on deck, oars in one of three positions."""
        deck = "  \\___" + "".join("o___" if i < n else "____" for i in range(6)) + "__/"
        W = len(deck)
        sail_l, sail_r = ("(", ")") if wind else ("|", "|")
        inner = W - 16
        mast = " " * 19 + "|"
        rows = [mast, mast + "\\",
                " " * 7 + "_" * 11 + "|_" + "_" * (inner - 1),
                " " * 7 + sail_l + " " * (inner + 10) + sail_r,
                " " * 7 + sail_l + " " * (inner + 10) + sail_r,
                " " * 7 + sail_l + " " * (inner + 10) + sail_r,
                " " * 7 + "|" + "_" * (inner + 10) + "|",
                mast,
                deck,
                "   \\" + "_" * (W - 6) + "/"]
        oar = "\\|/"[oar_frame]
        rows.append("      " + "".join(f"{oar}   " for i in range(6) if i < n))
        return rows

    def draw_convey(self, h, w):
        an = self.an
        t = self.t
        st = self.state("convey", h, w, lambda: {
            "x": float(w - 44), "n": 6, "raft": False, "god": None, "cool": t + 6, "shake": 0,
            "text": None, "rock": None, "arrived": None, "reset_at": None, "spray": [],
            "stars": np.column_stack([self.rng.random(60) * (w - 1), self.rng.random(60) * max(1, h // 3),
                                      self.rng.random(60)])})
        hz = int(h * 0.32)
        x = np.arange(w - 1)
        amp = 0.5 + an.bass * (h * 0.09) + an.beat * 1.2
        surf = (hz + amp * np.sin(x * 0.16 - t * 1.6) + amp * 0.4 * np.sin(x * 0.37 + t * 2.4)
                + 0.4 * np.sin(x * 0.06 + t * 0.5))
        god = st["god"]
        if god is not None:                                        # his wave rolls east toward the ship
            surf = surf + god["amp"] * np.exp(-((x - god["wave"]) / 7.0) ** 2)
        if an.beat > 0.35:
            st["shake"] = max(st["shake"], 2)
        dx = dy = 0
        if st["shake"] > 0:
            st["shake"] -= 1
            dx, dy = int(self.rng.integers(-1, 2)), int(self.rng.integers(-1, 2))
        # sky and sea, as in the poseidon mode
        for sx, sy, ph in st["stars"]:
            band = int(sx / max(1, w - 1) * (BANDS // 2)) + BANDS // 2
            tw = 0.2 + 0.8 * abs(math.sin(t * 1.5 + ph * 6.28)) * (0.3 + an.level[min(BANDS - 1, band)])
            if sy + dy < surf[min(int(sx), w - 2)] - 1 and tw > 0.45:
                self.put(int(sy) + dy, int(sx) + dx, "✦" if tw > 0.85 else "·", self.fg(tw, tw > 0.85, base=STAR_FG))
        rows = np.arange(h - 1)[:, None]
        depth = (rows - surf[None, :]) / max(1.0, (h - 1) - hz)
        under = rows >= surf[None, :]
        self.field(np.clip(0.5 - depth * 0.9 + an.bass * 0.1, 0.0, 0.999), mask=under, base=WATER_BG)
        for xx in range(0, w - 1):
            yy = int(surf[xx])
            if 0 <= yy < h - 1 and surf[xx] <= surf[max(0, xx - 1)] and surf[xx] <= surf[min(w - 2, xx + 1)]:
                self.put(yy + dy, xx + dx, "≈" if an.treble > 0.35 else "~", self.fg(0.9, an.treble > 0.35, base=WAVE_FG))

        def sprite(rows_, px, py, attr_fn, halo=True):
            for i, row in enumerate(rows_):
                yy = py + i
                if not (0 <= yy < h - 1):
                    continue
                first, last = len(row) - len(row.lstrip()), len(row.rstrip())
                if halo and last > first:
                    x0, x1 = max(0, px + first), min(w - 1, px + last)
                    if x1 > x0 and yy >= surf[min(max(px + len(row) // 2, 0), w - 2)] - 1:
                        self.put(yy, x0, " " * (x1 - x0), curses.color_pair(WATER_BG))
                for j, ch in enumerate(row):
                    if ch != " " and 0 <= px + j < w - 1:
                        self.put(yy, px + j, ch, attr_fn(ch))
        # the islands: Ithaca on the western horizon once it is near, the Cyclops's isle astern at the start
        ship_w = 42
        prog = 1 - (st["x"] - 2) / max(1, w - ship_w - 2)          # 0 at the start, 1 at Ithaca
        if prog > 0.55:
            ix = 1 - int((1 - min(1.0, (prog - 0.55) / 0.35)) * 16)
            sprite(self.ITHACA, ix + dx, int(surf[:20].min()) - 3 + dy, lambda ch: self.fg(0.75, ch == "⌂", base=RADIAL_FG))
        if prog < 0.35:
            cx = w - 16 + int(min(1.0, prog / 0.35) * 18)
            sprite(self.CYCLOPS_ISLE, cx + dx, int(surf[-20:].min()) - 3 + dy,
                   lambda ch: self.fg(0.95 if ch in "(o)" else 0.5, ch in "(o)", base=RADIAL_FG))
        # the god: on a big beat he rises ahead of the ship and sends his wave
        if god is None and an.beat > 0.55 and t > st["cool"] and st["arrived"] is None and st["x"] > 30:
            gx = max(2, int(st["x"]) - 30 - int(self.rng.integers(0, 12)))
            st["god"] = god = {"x": gx, "wave": float(gx + 8), "amp": 5 + an.bass * 5, "until": t + 3.5, "hit": False}
            st["text"] = ("MAY THE LORD POSEIDON CONVEY YOU", t + 3)
        if god is not None:
            god["wave"] += 1.1 + an.bass * 0.6
            ship_cx = st["x"] + (4 if st["raft"] else ship_w // 2)
            if not god["hit"] and god["wave"] >= ship_cx:            # the wave takes the ship
                god["hit"] = True
                st["x"] = min(float(w - ship_w - 2), st["x"] + 14 + an.bass * 10)
                st["shake"] = 6
                if st["n"] > 0:
                    st["n"] -= 1
                    if st["n"] == 0:
                        st["raft"] = True
                        st["text"] = ("IN ANOTHER'S SHIP, HAVING LOST ALL COMPANIONS", t + 4)
                st["spray"] = [[ship_cx + self.rng.random() * 30 - 15, surf[min(int(ship_cx), w - 2)] - 6 - self.rng.random() * 6, 1.0]
                               for _ in range(24)]
            if t > god["until"] and god["wave"] > w:
                st["god"] = None
                st["cool"] = t + 5 + self.rng.random() * 8
            elif t < god["until"]:
                gx, gy = god["x"] + dx, int(surf[min(god["x"] + 6, w - 2)]) - 3 + dy
                frame = self.SWIM[(self.frame // 6) % 2]
                for i, row in enumerate(frame):
                    for j, ch in enumerate(row):
                        if ch == " " or not (0 <= gy + i < h - 1 and 0 <= gx + j < w - 1):
                            continue
                        if ch == "Ψ":
                            self.put(gy + i, gx + j, ch, self.fg(0.7 + an.beat, True, base=RADIAL_FG))
                            for k in range(1, gy + i + 1):          # the trident lights the sky
                                zig = gx + j + int(math.sin(k * 1.3 + t * 40) * 2)
                                self.put(gy + i - k, zig, "│" if k % 3 else "╱", self.fg(0.95, True, base=WAVE_FG))
                        elif ch in "òó":
                            self.put(gy + i, gx + j, ch, self.fg(1.0, True, base=RADIAL_FG))
                        else:
                            self.put(gy + i, gx + j, ch, self.fg(0.99, True, base=WAVE_FG))
        # the ship, or the raft, riding the swell
        if st["arrived"] is None:
            speed = (0.05 + an.rms * 0.4) * (0.5 if st["raft"] else 1.0)
            st["x"] -= speed
        cx = min(max(int(st["x"]) + (4 if st["raft"] else ship_w // 2), 0), w - 2)
        if st["raft"]:
            rows_ = self.RAFT
            py = int(surf[cx]) - 2
            sprite(rows_, int(st["x"]) + dx, py + dy,
                   lambda ch: self.fg(0.95, True, base=WAVE_FG) if ch in "o/|\\" else self.fg(0.6, False, base=RADIAL_FG))
        else:
            oar = int(self.frame / max(2, 8 - int(an.rms * 12))) % 3
            rows_ = self.ship_rows(st["n"], oar, an.mid > 0.25)
            py = int(surf[cx]) - 9
            sprite(rows_, int(st["x"]) + dx, py + dy,
                   lambda ch: (self.fg(0.95, True, base=STAR_FG) if ch in "()|" else
                               self.fg(0.98, True, base=WAVE_FG) if ch == "o" else
                               self.fg(0.55, False, base=RADIAL_FG)))
        spray = []
        for sp in st["spray"]:
            sp[1] -= 0.4
            sp[2] -= 0.05
            if sp[2] > 0 and 0 <= sp[1] < h - 1 and 0 <= sp[0] < w - 1:
                self.put(int(sp[1]) + dy, int(sp[0]) + dx, "*" if sp[2] > 0.5 else "·", self.fg(0.9, True, base=WAVE_FG))
                spray.append(sp)
        st["spray"] = spray
        # Ithaca at last; then the Cyclops sees him off again
        if st["arrived"] is None and st["x"] <= 3:
            st["arrived"] = t
            st["text"] = ("ITHACA, AT LAST" + (", ALONE" if st["raft"] else ""), t + 4)
        if st["arrived"] is not None and t - st["arrived"] > 4:
            st.update({"x": float(w - ship_w - 2), "n": 6, "raft": False, "arrived": None, "god": None,
                       "cool": t + 8, "text": ("COME BACK, ODYSSEUS", t + 2.5), "reset_at": t})
            st["rock"] = {"t0": t + 2.5, "x0": float(w - 8), "x1": float(w - ship_w - 12)}
        if st["reset_at"] is not None and 2.5 < t - st["reset_at"] < 5.5 and st["text"] is None:
            st["text"] = ("MY FATHER WILL CONVEY YOU HOME", t + 3)
        rock = st["rock"]
        if rock is not None and t >= rock["t0"]:
            k = (t - rock["t0"]) / 1.6
            if k >= 1:
                st["rock"] = None
                st["shake"] = 4
                st["spray"] = [[rock["x1"] + self.rng.random() * 12 - 6, surf[min(max(int(rock["x1"]), 0), w - 2)] - 4 - self.rng.random() * 5, 1.0]
                               for _ in range(20)]
            else:
                rx = rock["x0"] + (rock["x1"] - rock["x0"]) * k
                ry = surf[min(max(int(rx), 0), w - 2)] - 4 - 14 * math.sin(k * math.pi)
                self.put(int(ry) + dy, int(rx) + dx, "●", self.fg(0.4, True, base=RADIAL_FG))
        # words
        if st["text"] and t < st["text"][1]:
            msg = st["text"][0]
            self.put(1, max(0, (w - len(msg)) // 2) + dx, msg[:w - 1], self.fg(1.0, True, base=RADIAL_FG))
        elif st["text"] and t >= st["text"][1]:
            st["text"] = None
        self.put(h - 2, 1, f"companions {st['n']}  ·  {int(prog * 100)}% of the way home", self.fg(0.5, False, base=WAVE_FG))

    # ---- athena (the grey-eyed goddess, as her owl)
    def draw_athena(self, h, w):
        an = self.an
        t = self.t
        floor = h - 2

        def grow():                                                 # the bough's twigs, fixed for the life of the screen
            twigs, u = [], 0.05
            while u < 0.94:
                if not 0.40 < u < 0.60:                             # nothing sprouts where she stands
                    up = self.rng.random() < 0.55
                    twigs.append({"u": u, "up": up, "L": self.rng.uniform(0.09, 0.14),
                                  "ang": -self.rng.uniform(0.5, 1.0) if up else self.rng.uniform(0.35, 0.75),
                                  "pairs": int(self.rng.integers(2, 4)), "olives": self.rng.random() < 0.5,
                                  "ph": self.rng.uniform(0, 2 * math.pi)})
                u += self.rng.uniform(0.08, 0.13)
            return twigs
        st = self.state("athena", h, w, lambda: {
            "tick": -1, "turn": 0, "quiet": 0.0, "lid": 0.0, "blink": 0, "hoot": 0, "around": 0.0,
            "spread": 0.2, "said": None, "say_until": 0.0, "twigs": grow(),
            "wind": 0.0, "gust": 0.0, "gust_at": 0.0, "bend": 0.0, "bend_v": 0.0,
            "phase": 0.0, "amp": 0.0, "period": 0.5, "last_beat": -9.0, "y": 0.0, "vy": 0.0})
        tick = int(t * 4)
        moved = tick != st["tick"]
        st["tick"] = tick
        st["quiet"] = st["quiet"] + 1 / FPS if an.rms < 0.05 else 0.0
        quiet = st["quiet"] > 3
        if moved:                                                  # an owl's head does not glide
            if an.rms > 0.05:
                loud = int(np.argmax(an.level)) / BANDS
                goal = int(round((loud - 0.5) * 6))
                st["turn"] += int(np.sign(goal - st["turn"])) * (2 if an.beat > 0.3 else 1)
                st["turn"] = max(-3, min(3, st["turn"]))
            if self.rng.random() < 0.05:
                st["blink"] = 2
            if an.beat > 0.45 and st["hoot"] <= 0:
                st["hoot"] = 8
            if st["quiet"] > 10 and st["around"] == 0.0 and self.rng.random() < 0.15:
                st["around"] = t                                   # all the way round, and back
            if quiet and t > st["say_until"]:
                st["said"] = {None: "who?", "who?": "nobody.", "nobody.": None}.get(st["said"])
                st["say_until"] = t + 2.5
        if not quiet:
            st["said"] = None
        st["blink"] = max(0, st["blink"] - 1)
        st["hoot"] = max(0, st["hoot"] - 1)
        if st["around"] and t - st["around"] > 4:
            st["around"] = 0.0
            st["quiet"] = 0.0
        around = bool(st["around"])
        target = 1.0 if an.beat > 0.45 else min(1.0, 0.1 + an.rms * 2.2)
        st["spread"] += (target - st["spread"]) * (0.5 if target > st["spread"] else 0.08)
        spread = st["spread"]
        lid_goal = 0.55 if quiet else 0.0
        st["lid"] += (lid_goal - st["lid"]) * 0.1
        # the dance: the head snaps, the body glides.  A sway locked to the beat, weight from foot
        # to foot; a beat drops her and she springs back up taller; the head lags the shoulders
        # the way an owl holds its gaze still while the body moves underneath it.
        dt = 1 / FPS
        if an.beat > 0.45 and t - st["last_beat"] > 0.2:
            gap = t - st["last_beat"]
            if gap < 1.6:
                st["period"] = st["period"] * 0.7 + gap * 0.3
            st["last_beat"] = t
            st["vy"] += 7 * min(1.0, an.beat)
        st["vy"] += (-90 * st["y"] - 6 * st["vy"]) * dt
        st["y"] += st["vy"] * dt
        dancing = t - st["last_beat"] < 2.5 and not quiet
        amp_goal = min(1.0, 0.25 + an.rms * 2.5) if dancing else 0.0
        st["amp"] += (amp_goal - st["amp"]) * (0.06 if amp_goal > st["amp"] else 0.03)
        if st["amp"] > 0.02:
            st["phase"] += math.pi * dt / max(0.25, st["period"])   # one side per beat, a sway per two
        sway = math.sin(st["phase"]) * st["amp"] * 0.13            # lateral shift per unit of height
        bob = st["y"] * 0.10                                        # down on the beat, in units of H
        stretch = -st["y"] * 0.25                                   # squashed on the dip, tall on the rebound
        # geometry
        gw, gh = max(2, (w - 1) * 2), max(4, (h - 1) * 4)
        H = min(floor * 4 - 18, gw * 0.9)
        cx0 = gw / 2
        top = floor * 4 - 12 - 0.96 * H
        feet_v = 0.94                                               # she pivots on her talons
        # the olive bough: rooted off the left edge, thick there and a whip at the tip.  A wind
        # gusts across it, harder when the music is loud; the bough is a cantilever, so it bends
        # most at the tip, springs back past level, and settles; the twigs bend further and the
        # leaves flutter.  When she lands a beat the bough gives under her and the far end dips
        # with it.  Her feet are wherever the bough is: she rides the sway, and dances on top.
        y0 = floor * 4 - 13                                         # over the architrave, the leaves in the sky
        wind_A = 0.15 * H                                           # a full gust lifts the tip this far
        if t >= st["gust_at"]:
            st["gust_at"] = t + self.rng.uniform(1.5, 4.0)
            st["gust"] = self.rng.uniform(-0.4, 1.0) * (0.5 + 0.5 * min(1.0, an.rms * 2.5))
        st["wind"] += (st["gust"] - st["wind"]) * dt / 0.7
        wind = st["wind"]
        st["bend_v"] += (32 * (-wind * wind_A - st["bend"]) - 4 * st["bend_v"]) * dt
        st["bend"] += st["bend_v"] * dt
        load = 0.7 * bob * H                                        # her weight, landing the beat
        perch_u, end_u = 0.5, 0.965

        def bough(u):                                               # (x, y, thickness) of the bough's centreline
            base = y0 + 0.025 * H * math.sin(u * 7.5 + 0.6)
            r = min(u, perch_u) / perch_u
            s = r * r * (3 - r) / 2 if u <= perch_u else 1 + 1.5 * (u - perch_u) / perch_u
            return u * gw, base + st["bend"] * u ** 1.6 + load * s, 4.5 - 3.2 * u
        px_, py_, pth = bough(perch_u)
        feet_y = py_ - pth / 2 - 1

        def P(u, v):
            return cx0 + u * H, top + v * H

        def B(u, v, follow=1.0):                                    # she sways, dips, stretches from the feet up
            lift = feet_v - v
            return (cx0 + u * H * (1 - 0.35 * stretch) + sway * follow * lift * H,
                    feet_y - lift * H * (1 + stretch))
        # the moon, and the Parthenon along the bottom
        moon = Canvas(h, w)
        mx, my = P(0.36, 0.10)
        moon.ellipse(mx, my, 0.09 * H, 0.09 * H, 0.35 + an.treble * 0.6)
        moon.paint(self, bold=an.treble > 0.4, base=STAR_FG)
        cols = max(4, (w - 2) // 6)
        for c in range(cols):
            xx = 1 + c * 6
            for r in range(3):
                self.put(floor - 1 - r, xx, "┃", self.fg(0.15, False, base=SPIRAL_FG))
        self.put(floor - 4, 0, "━" * (w - 1), self.fg(0.2, False, base=SPIRAL_FG))
        self.put(floor, 0, "▔" * (w - 1), self.fg(0.2, False, base=SPIRAL_FG))
        # the bough, its twigs, the leaves in pairs the way olive leaves grow, and the olives
        wood = Canvas(h, w)
        leaves = Canvas(h, w)
        bend = st["bend"] / wind_A                                  # -1..1, the tip's lift as a fraction of a full gust
        leaf_col = 0.5 + 0.3 * min(1.0, an.treble * 1.5)
        pts = [bough(end_u * i / 60) for i in range(61)]
        for i, ((xa, ya, wa), (xb, yb, wb)) in enumerate(zip(pts, pts[1:])):
            wood.line(xa, ya, xb, yb, 0.32, width=max(1, int(round((wa + wb) / 2))))
            if i % 3 == 1:                                         # bark, a fleck on the underside
                wood.dot(xa, ya + wa / 2 + 1, 0.2)

        def leaf(x, y, a, L):
            dx, dy = math.cos(a), math.sin(a)
            m, wd = L * 0.45, L * 0.2
            leaves.poly([(x, y), (x + dx * m - dy * wd, y + dy * m + dx * wd), (x + dx * L, y + dy * L),
                         (x + dx * m + dy * wd, y + dy * m - dx * wd)], leaf_col)
        for tw in st["twigs"]:
            x, y, th = bough(tw["u"])
            slope = math.atan2(bough(tw["u"] + 0.01)[1] - y, 0.01 * gw)
            flutter = 0.1 + 0.3 * abs(wind) + 0.15 * an.treble
            a = tw["ang"] + slope - bend * 0.3 + math.sin(t * 4.5 + tw["ph"]) * flutter * 0.4
            L = tw["L"] * H
            sx, sy = x, y + (-th / 2 if tw["up"] else th / 2)
            ex, ey = sx + math.cos(a) * L, sy + math.sin(a) * L
            wood.line(sx, sy, ex, ey, 0.35, width=(2 if L > 16 else 1) * self.stroke(h, w))
            for j in range(tw["pairs"] + 1):
                f = (j + 1) / (tw["pairs"] + 1)
                lx, ly = sx + (ex - sx) * f, sy + (ey - sy) * f
                ll = 0.065 * H * (1 - 0.25 * f)
                if j == tw["pairs"]:                                # the tip leaf carries on the twig's line
                    leaf(lx, ly, a + math.sin(t * 7 + tw["ph"]) * flutter, ll)
                    continue
                for k in (-1, 1):                                  # opposite pairs
                    wob = math.sin(t * 7 + tw["ph"] + j * 1.7 + k) * flutter
                    leaf(lx, ly, a + k * 0.85 + wob, ll)
                if tw["olives"] and j == tw["pairs"] - 1:          # a pair of olives hanging at the node
                    for k in (-1, 1):
                        wood.ellipse(lx + k * 2.5 - bend * 2, ly + 4 + abs(bend), 1.5, 2.2, 0.12)
        wood.paint(self, bold=False, base=RAIN_FG)
        leaves.paint(self, bold=True, base=RAIN_FG)
        # the wings: one feather per band, fanned from the shoulders, long when the band is loud
        wings = Canvas(h, w)
        half = BANDS // 2
        for side in (-1, 1):
            sx, sy = B(side * 0.16, 0.50)
            sy += side * sway * 0.35 * H                            # the far wing lifts against the lean, a dancer's arms
            for i in range(half):
                band = (half - 1 - i) if side < 0 else (half + i)   # bass at the body, treble at the tips
                lvl = float(an.level[band])
                a = math.radians(95 - spread * (95 - 5) * (i + 1) / half)   # from hanging to horizontal
                L = (0.12 + lvl * 0.45 + spread * 0.10) * H
                ex, ey = sx + side * math.sin(a) * L, sy + math.cos(a) * L
                wings.line(sx, sy, ex, ey, 0.25 + lvl * 0.7, width=2 * self.stroke(h, w))
                wings.dot(ex, ey, 0.95)
        wings.paint(self, bold=an.beat > 0.3, base=WAVE_FG)
        # the goddess: body, head, face, eyes, beak
        body = Canvas(h, w)
        face = Canvas(h, w)
        eyes = Canvas(h, w)
        dark = Canvas(h, w)
        gleam = Canvas(h, w)                                       # the catchlight, painted last so the pupil cannot cover it
        bx, by = B(0, 0.64)
        tall = 1 + stretch
        body.ellipse(bx, by, 0.21 * H * (1 - 0.35 * stretch), 0.30 * H * tall, 0.22 + an.mid * 0.1)
        for r in range(5):                                         # the breast: rows of chevrons
            yy = by - 0.10 * H * tall + r * 0.07 * H * tall
            for k in range(-3, 4):
                xx = bx + k * 0.05 * H + (0.025 * H if r % 2 else 0)
                dark.line(xx - 0.015 * H, yy, xx, yy + 0.02 * H, 0.1)
                dark.line(xx, yy + 0.02 * H, xx + 0.015 * H, yy, 0.1)
        turn = st["turn"] * 0.02 * H
        hx, hy = B(0, 0.28, follow=0.6)                            # the head holds steadier than the body
        body.ellipse(hx + turn * 0.5, hy, 0.22 * H, 0.20 * H, 0.28)
        if not around:
            for side in (-1, 1):                                   # the facial discs
                fx, fy = hx + turn + side * 0.095 * H, hy
                face.ellipse(fx, fy, 0.10 * H, 0.095 * H, 0.55)
            look = (an.rms_lr[1] - an.rms_lr[0]) * 2.0 if an.rms > 0.02 else 0.0
            pup = (0.02 + min(1.0, an.bass * 1.6) * 0.03) * H
            # grey-eyed: the irises are grey at rest and give light with the music, brightest on a beat,
            # and the light falls on the facial discs around them
            glow = 0.62 + 0.33 * min(1.0, an.rms * 1.5 + an.beat)
            for side in (-1, 1):
                ex, ey = hx + turn + side * 0.095 * H, hy
                eyes.ellipse(ex, ey, 0.072 * H, 0.072 * H, glow)
                if st["blink"] > 0:
                    dark.ellipse(ex, ey, 0.075 * H, 0.075 * H, 0.05)
                else:
                    face.circle(ex, ey, 0.085 * H, 0.55 + (glow - 0.62) * 0.9, n=int(0.085 * H * 3))
                    px = ex + look * 0.03 * H
                    dark.ellipse(px, ey, pup, pup, 0.02)
                    d = math.hypot(mx - px, my - ey) or 1.0        # the catchlight is the moon
                    gleam.dot(px + (mx - px) / d * pup * 0.45, ey + (my - ey) / d * pup * 0.45, 1.0)
                    if st["lid"] > 0.05:                           # heavy lids when the music is gone
                        dark.poly([(ex - 0.08 * H, ey - 0.08 * H), (ex + 0.08 * H, ey - 0.08 * H),
                                   (ex + 0.08 * H, ey - 0.08 * H + st["lid"] * 0.16 * H),
                                   (ex - 0.08 * H, ey - 0.08 * H + st["lid"] * 0.16 * H)], 0.28)
            kx, ky = hx + turn, hy + 0.06 * H
            dark.poly([(kx - 0.025 * H, ky), (kx + 0.025 * H, ky), (kx, ky + 0.06 * H)], 0.1)
        else:                                                      # the back of the head: rings of feathers
            for r in (0.06, 0.12, 0.18):
                face.circle(hx, hy, r * H, 0.4, n=int(r * H * 3))
        # the talons: three toes forward from each ankle over the bough, each claw hooking under
        # the far side of it, so however it sways she is on it
        claws = Canvas(h, w)
        for side in (-1, 1):
            ax, ay = bx + side * 0.07 * H, feet_y - 0.05 * H
            for k in (-1, 0, 1):
                tx = ax + k * 0.035 * H
                _, ty, tth = bough(min(end_u, max(0.0, tx / gw)))
                claws.line(ax, ay, tx, ty - tth / 2, 0.3, width=2 * self.stroke(h, w))
                claws.line(tx, ty - tth / 2, tx + (1.5 if k >= 0 else -1.5), ty + tth / 2 + 1.5, 0.35, width=2 * self.stroke(h, w))
        for (cy, cx), _ in body.cells.items():
            self.put(cy, cx, " ")
        body.paint(self, bold=False, base=RADIAL_FG)
        face.paint(self, bold=False, base=RADIAL_FG)
        eyes.paint(self, bold=True, base=STAR_FG)
        dark.paint(self, bold=False, base=RADIAL_FG)
        gleam.paint(self, bold=True, base=STAR_FG)
        claws.paint(self, bold=True, base=RAIN_FG)
        # words
        if st["hoot"] > 0 and not around:
            self.put(int(hy / 4) + 2, int((hx + turn) / 2) + 8, "hoo" if st["hoot"] > 4 else "hoo-hoo",
                     self.fg(0.9, True, base=STAR_FG))
        if an.beat > 0.5:
            self.put(1, max(0, (w - 6) // 2), "ATHENA", self.fg(1.0, True, base=STAR_FG))
        if st["said"] and t < st["say_until"] and not around:
            self.put(int(hy / 4) + 2, int((hx + turn) / 2) + 8, st["said"], self.fg(0.8, False, base=STAR_FG))

    # ---- althea (the healer, at the hearth in Calydon)
    def draw_althea(self, h, w):
        an = self.an
        t = self.t
        floor = h - 2
        st = self.state("althea", h, w, lambda: {
            "tick": -1, "quiet": 0.0, "heat": 0.0, "mode": "fire", "since": 0.0, "said": None, "say_until": 0.0,
            "blink": 0, "phase": 0.0, "amp": 0.0, "period": 0.5, "last_beat": -9.0, "y": 0.0, "vy": 0.0,
            "hair": 0.0, "hand": None, "palm": None, "scale": 1.0, "sparks": [], "smoke": [], "tap": 0.0})
        dt = 1 / FPS
        tick = int(t * 4)
        moved = tick != st["tick"]
        st["tick"] = tick
        st["quiet"] = st["quiet"] + dt if an.rms < 0.05 else 0.0
        quiet = st["quiet"] > 3
        # the heat of the music: too much of it and she takes the brand out of the fire
        st["heat"] = max(0.0, min(1.6, st["heat"] + (0.45 * an.rms + 0.35 * min(1.0, an.beat) - 0.18) * dt
                                  - (0.35 * dt if st["mode"] == "cool" else 0.0)))
        mode = st["mode"]
        if quiet and mode != "easy":
            mode, st["since"] = "easy", t
            st["said"], st["say_until"] = "easy Jim", t + 4
        elif not quiet and mode == "easy":
            mode, st["since"] = "fire", t
        elif mode == "fire" and st["heat"] > 1.2:
            mode, st["since"] = "cool", t
            st["said"], st["say_until"] = "cool down boy", t + 3
        elif mode == "cool" and st["heat"] < 0.3 and t - st["since"] > 4:
            mode, st["since"] = "fire", t
            st["said"], st["say_until"] = "settle back", t + 2.5
        st["mode"] = mode
        if moved and self.rng.random() < 0.04:
            st["blink"] = 2
        st["blink"] = max(0, st["blink"] - 1)
        # the dance, seated: the owl's sway and spring, hair a beat behind the shoulders
        if an.beat > 0.45 and t - st["last_beat"] > 0.2:
            gap = t - st["last_beat"]
            if gap < 1.6:
                st["period"] = st["period"] * 0.7 + gap * 0.3
            st["last_beat"] = t
            st["vy"] += 6 * min(1.0, an.beat)
            st["tap"] = 1.0
        st["vy"] += (-90 * st["y"] - 6 * st["vy"]) * dt
        st["y"] += st["vy"] * dt
        st["tap"] = max(0.0, st["tap"] - 4 * dt)
        dancing = t - st["last_beat"] < 2.5 and not quiet
        amp_goal = min(1.0, 0.25 + an.rms * 2.5) if dancing else 0.0
        st["amp"] += (amp_goal - st["amp"]) * (0.06 if amp_goal > st["amp"] else 0.03)
        if st["amp"] > 0.02:
            st["phase"] += math.pi * dt / max(0.25, st["period"])
        sway = math.sin(st["phase"]) * st["amp"] * 0.10
        st["hair"] += (sway - st["hair"]) * 0.18
        scale_goal = {"fire": 1.0, "cool": 0.45, "easy": 0.15}[mode]
        st["scale"] += (scale_goal - st["scale"]) * 0.06
        scale = st["scale"]
        # geometry: figure units, (0, 0) top centre, v down; she sits left of centre, the hearth right
        gw, gh = max(2, (w - 1) * 2), max(4, (h - 1) * 4)
        H = min(floor * 4 - 10, gw * 0.9)
        cx0 = gw / 2
        top = floor * 4 - 4 - 0.96 * H
        hips = 0.70

        def P(u, v):
            return cx0 + u * H, top + v * H

        def B(u, v, follow=1.0):                                    # her: sways and nods from the hips up
            lift = max(0.0, hips - v) / hips
            return (cx0 + u * H + sway * follow * lift * hips * H,
                    top + v * H + st["y"] * 0.03 * lift * H)
        # ---- the hollyhocks, her own plant, blooming with the treble
        stalks = Canvas(h, w)
        blooms = Canvas(h, w)
        for k, u in enumerate((-0.47, -0.41, 0.42, 0.48)):
            bend = math.sin(st["phase"] * 0.5 + k) * st["amp"] * 0.03 + math.sin(t * 0.7 + k) * 0.01
            prev = P(u, 0.94)
            for j, v in enumerate(np.linspace(0.94, 0.22, 10)):
                x, y = P(u + bend * (0.94 - v) / 0.72, v)
                stalks.line(prev[0], prev[1], x, y, 0.35, width=2 * self.stroke(h, w))
                if j % 2 == 1 and j < 9:
                    side = -1 if (j // 2 + k) % 2 else 1
                    stalks.line(x, y, x + side * 0.04 * H, y + 0.02 * H, 0.5)
                    r = (0.014 + an.treble * 0.045) * H
                    bx, by = x + side * 0.025 * H, y - 0.01 * H
                    blooms.circle(bx, by, r, 0.75 + an.treble * 0.25)
                    for p in range(5):
                        pa = p * 2 * math.pi / 5 + t * 0.3
                        blooms.dot(bx + math.cos(pa) * r * 0.55, by + math.sin(pa) * r * 0.55, 0.9)
                    blooms.ellipse(bx, by, r * 0.25, r * 0.25, 0.4)
                prev = (x, y)
        # ---- the hearth: a ring of stones, the fire above it, the spectrum as flames
        stones = Canvas(h, w)
        fire = Canvas(h, w)
        f0, f1, fv = 0.12, 0.42, 0.88
        for i in range(9):
            sx, sy = P(f0 - 0.02 + (f1 - f0 + 0.04) * i / 8, 0.92)
            stones.ellipse(sx, sy, 0.03 * H, 0.02 * H, 0.2 + 0.1 * (i % 2))
        for i in range(BANDS):
            lvl = float(an.level[i])
            u = f0 + (f1 - f0) * (i + 0.5) / BANDS
            x0, y0 = P(u, fv)
            L = (0.03 + lvl * 0.36 + min(1.0, an.beat) * 0.08) * H * scale
            wob = math.sin(t * 9 + i * 1.7) * 0.02 * H * scale
            fire.line(x0, y0, x0 + wob, y0 - L, 0.45 + lvl * 0.55, width=2 * self.stroke(h, w))
            fire.line(x0, y0, x0 + wob * 0.5, y0 - L * 0.55, 0.9, width=2 * self.stroke(h, w))
        if mode == "easy":                                          # embers, breathing slowly
            for i in range(0, BANDS, 3):
                x0, y0 = P(f0 + (f1 - f0) * (i + 0.5) / BANDS, fv - 0.01)
                fire.dot(x0, y0, 0.3 + 0.3 * (0.5 + 0.5 * math.sin(t * 1.5 + i)))
        # sparks on the beat, smoke with the mids
        if an.beat > 0.4 and mode == "fire":
            for _ in range(int(3 + an.beat * 8)):
                x0, y0 = P(f0 + (f1 - f0) * self.rng.random(), fv - 0.2 - an.bass * 0.2)
                st["sparks"].append([x0, y0, (self.rng.random() - 0.5) * 1.5, -(1.0 + self.rng.random() * 2.5), 20])
        for s in st["sparks"]:
            s[0] += s[2]
            s[1] += s[3]
            s[3] += 0.03
            s[4] -= 1
            fire.dot(s[0], s[1], 0.6 + 0.4 * s[4] / 20)
        st["sparks"] = [s for s in st["sparks"] if s[4] > 0 and s[1] > 0]
        smoke = Canvas(h, w)
        if len(st["smoke"]) < 14 and self.rng.random() < 0.15 + an.mid * 0.4:
            x0, y0 = P(f0 + (f1 - f0) * (0.3 + 0.4 * self.rng.random()), fv - 0.25 * scale)
            st["smoke"].append([x0, y0, self.rng.random() * 6.3])
        for p in st["smoke"]:
            p[1] -= 0.6 + an.mid * 1.2
            p[0] += math.sin(t * 1.3 + p[2]) * 0.4
            smoke.dot(p[0], p[1], 0.12)
            smoke.dot(p[0] + 1, p[1], 0.12)
        st["smoke"] = [p for p in st["smoke"] if p[1] > 2]
        # ---- Althea: seated, in a long dress, hair down, facing the fire
        skin = Canvas(h, w)
        dress = Canvas(h, w)
        hair = Canvas(h, w)
        dark = Canvas(h, w)
        lw = max(2, int(H / 60))
        hx, hy = B(-0.15, 0.30, follow=0.75)                      # the head, a little steadier than the shoulders
        skin.ellipse(hx, hy, 0.072 * H, 0.085 * H, 0.75)
        hs = (st["hair"] - sway) * 0.7 * H                          # the hair lags the body
        for k in range(-3, 4):                                      # hair: strands over the crown, falling to the shoulders
            a = math.radians(-90 + k * 22)
            x1, y1 = hx + math.cos(a) * 0.085 * H, hy + math.sin(a) * 0.095 * H
            side = -1 if k <= 0 else 1
            hair.line(x1, y1, x1 + side * 0.03 * H + hs, hy + 0.20 * H, 0.35 + abs(k) * 0.06, width=2 * self.stroke(h, w))
        hair.ellipse(hx, hy - 0.05 * H, 0.085 * H, 0.05 * H, 0.4)
        ex, ey = hx + 0.035 * H, hy - 0.005 * H                    # eyes on the fire (or closed for a blink)
        for dx in (-0.045 * H, 0.0):
            if st["blink"] > 0:
                dark.line(ex + dx - 0.012 * H, ey, ex + dx + 0.012 * H, ey, 0.1)
            else:
                dark.ellipse(ex + dx, ey, 0.011 * H, 0.011 * H, 0.05)
        dark.line(hx + 0.005 * H, hy + 0.045 * H, hx + 0.035 * H, hy + 0.04 * H, 0.1)   # a mouth, turned to the fire
        nx, ny = B(-0.15, 0.38, follow=0.85)
        sx2, sy2 = B(-0.15, 0.44)
        skin.line(nx, ny, sx2, sy2, 0.7, width=lw * 2)
        dress.poly([B(-0.27, 0.44), B(-0.03, 0.44), B(-0.06, 0.60), B(0.05, 0.75), P(0.07, 0.94),
                    P(-0.37, 0.94), B(-0.35, 0.75), B(-0.24, 0.60)], 0.35 + an.mid * 0.15)
        dress.line(*B(-0.27, 0.44), *B(-0.03, 0.44), 0.7, width=lw)   # the neckline
        for k in range(1, 4):                                       # folds in the skirt
            fx0, fy0 = B(-0.15 + (k - 2) * 0.06, 0.62)
            fx1, fy1 = P(-0.15 + (k - 2) * 0.11, 0.94)
            dark.line(fx0, fy0, fx1, fy1, 0.15)
        # the right arm holds the brand: in the fire, drawn back to her lap, or stirring the embers
        shoulder = B(-0.05, 0.47)
        if mode == "cool":
            goal = B(-0.10, 0.66)
        elif mode == "easy":
            goal = (P(f0 + 0.02, 0.66)[0] + math.sin(t * 1.4) * 0.05 * H, P(0, 0.64)[1])
        else:
            goal = P(f0 + 0.03, 0.64)
        if st["hand"] is None:
            st["hand"] = list(goal)
        st["hand"][0] += (goal[0] - st["hand"][0]) * 0.1
        st["hand"][1] += (goal[1] - st["hand"][1]) * 0.1
        hand = tuple(st["hand"])
        mid = ((shoulder[0] + hand[0]) / 2, (shoulder[1] + hand[1]) / 2)
        elbow = (mid[0] - 0.02 * H, mid[1] + 0.08 * H)
        skin.line(*shoulder, *elbow, 0.7, width=lw + 1)
        skin.line(*elbow, *hand, 0.7, width=lw)
        skin.ellipse(hand[0], hand[1], 0.018 * H, 0.018 * H, 0.8)
        # the brand: the half-burnt log, its ember end in the fire, or across her lap
        brand = Canvas(h, w)
        if mode == "cool":
            tip = (hand[0] - 0.20 * H, hand[1] - 0.02 * H)
        else:
            tip = (hand[0] + 0.22 * H, hand[1] + 0.20 * H * (1 if mode == "fire" else 1.02))
        brand.line(*hand, *tip, 0.2, width=lw + 2)
        ember = Canvas(h, w)
        glow = 0.5 + min(1.0, an.bass * 1.6) * 0.5
        ember.ellipse(tip[0], tip[1], 0.03 * H, 0.02 * H, glow)
        # the left hand: keeps time on her knee, or comes up, palm out, the healer's hand
        shoulder2 = B(-0.26, 0.47)
        if mode == "cool":
            goal2 = B(-0.36, 0.40)
        else:
            k = B(-0.30, 0.74)
            goal2 = (k[0], k[1] - st["tap"] * 0.05 * H)
        if st["palm"] is None:
            st["palm"] = list(goal2)
        st["palm"][0] += (goal2[0] - st["palm"][0]) * 0.15
        st["palm"][1] += (goal2[1] - st["palm"][1]) * 0.15
        palm = tuple(st["palm"])
        mid2 = ((shoulder2[0] + palm[0]) / 2, (shoulder2[1] + palm[1]) / 2)
        elbow2 = (mid2[0] - 0.06 * H, mid2[1] + (0.02 if mode == "cool" else 0.06) * H)
        skin.line(*shoulder2, *elbow2, 0.7, width=lw + 1)
        skin.line(*elbow2, *palm, 0.7, width=lw)
        skin.ellipse(palm[0], palm[1], 0.02 * H, 0.022 * H, 0.8)
        rings = Canvas(h, w)
        if mode == "cool":                                          # the calm going out from the palm
            for k in range(3):
                r = ((t - st["since"]) * 0.12 + k * 0.08) % 0.24 * H
                rings.circle(palm[0], palm[1], r, 0.9 - r / (0.24 * H) * 0.7)
        # ---- paint: floor, hollyhocks, smoke, hearth and fire, then her in front of the glow
        self.put(floor, 0, "▔" * (w - 1), self.fg(0.25, False, base=RADIAL_FG))
        stalks.paint(self, bold=False, base=RAIN_FG)
        blooms.paint(self, bold=an.treble > 0.35, base=SPIRAL_FG)
        smoke.paint(self, bold=False, base=STAR_FG)
        stones.paint(self, bold=False, base=RADIAL_FG)
        fire.paint(self, bold=an.beat > 0.3 or an.bass > 0.4, base=MAIN_FG)
        for cv in (skin, dress, hair):
            for (cy, cx), _ in cv.cells.items():
                self.put(cy, cx, " ")
        dress.paint(self, bold=False, base=SPIRAL_FG)
        hair.paint(self, bold=False, base=RADIAL_FG)
        skin.paint(self, bold=True, base=RADIAL_FG)
        dark.paint(self, bold=False, base=RADIAL_FG)
        brand.paint(self, bold=False, base=RADIAL_FG)
        ember.paint(self, bold=True, base=MAIN_FG)
        rings.paint(self, bold=True, base=STAR_FG)
        # ---- words
        if an.beat > 0.5:
            self.put(1, max(0, (w - 6) // 2), "ALTHEA", self.fg(1.0, True, base=SPIRAL_FG))
        if st["said"] and t < st["say_until"]:
            self.put(max(2, int(hy / 4) - 1), int(hx / 2) + 6, st["said"], self.fg(0.85, True, base=STAR_FG))

    # ---- shared by the new modes: a text sprite drawn char by char, with an optional halo of sea behind it
    def sprite_at(self, h, w, rows_, px, py, attr_fn, mirror=False, surf=None):
        for i, row in enumerate(rows_):
            yy = py + i
            if not (0 <= yy < h - 1):
                continue
            if mirror:
                row = row[::-1].translate(self.MIRROR)
            if surf is not None:
                first, last = len(row) - len(row.lstrip()), len(row.rstrip())
                x0, x1 = max(0, px + first), min(w - 1, px + last)
                if x1 > x0 and yy >= surf[min(max(px + len(row) // 2, 0), w - 2)] - 1:
                    self.put(yy, x0, " " * (x1 - x0), curses.color_pair(WATER_BG))
            for j, ch in enumerate(row):
                if ch != " " and 0 <= px + j < w - 1:
                    self.put(yy, px + j, ch, attr_fn(ch))

    # ---- scylla (the strait: six heads on one side, the whirlpool on the other)
    ROCK_GRAIN = [0xFF, 0xF7, 0xDF, 0xFE, 0xBF, 0xFB, 0xEF, 0x7F, 0xFD, 0xF6, 0xDB, 0xBE]
    SCYLLA_SAYS = {"take": "SCYLLA TAKES ONE", "drink": "CHARYBDIS DRINKS THE SEA", "spit": "...AND SPITS IT BACK",
                   "through": "THROUGH THE STRAIT", "alone": "THE MAST AND THE KEEL, AND THE FIG TREE"}

    def draw_scylla(self, h, w):
        an = self.an
        t = self.t
        st = self.state("scylla", h, w, lambda: {
            "x": float(w - 44), "n": 6, "raft": False, "heads": [{"reach": 0.0, "target": None, "t0": 0.0, "sway": self.rng.random() * 6.28}
                                                                for _ in range(6)],
            "taken": 0, "cool": t + 4, "suck": 0.0, "swallowed": None, "grace": 0.0, "spin": 0.0, "text": None, "shake": 0, "spray": [],
            "stars": np.column_stack([self.rng.random(50) * (w - 1), self.rng.random(50) * max(1, h // 3),
                                      self.rng.random(50)])})
        hz = int(h * 0.36)
        x = np.arange(w - 1)
        amp = 0.5 + an.bass * (h * 0.08) + an.beat * 1.2
        surf = (hz + amp * np.sin(x * 0.16 - t * 1.6) + amp * 0.4 * np.sin(x * 0.37 + t * 2.4)
                + 0.4 * np.sin(x * 0.06 + t * 0.5))
        # Charybdis: the whirlpool, right of centre, a dip in the surface that deepens with the bass
        wx = int(w * 0.68)
        pull = 0.25 + an.bass * 0.75                                   # 0..1: how hard she drinks
        rad = 4 + pull * min(14, w * 0.12)
        surf = surf + pull * 3.0 * np.exp(-((x - wx) / max(3.0, rad)) ** 2)
        if an.beat > 0.35:
            st["shake"] = max(st["shake"], 2)
        dx = dy = 0
        if st["shake"] > 0:
            st["shake"] -= 1
            dx, dy = int(self.rng.integers(-1, 2)), int(self.rng.integers(-1, 2))
        # sky and sea
        for sx, sy, ph in st["stars"]:
            band = int(sx / max(1, w - 1) * (BANDS // 2)) + BANDS // 2
            tw = 0.2 + 0.8 * abs(math.sin(t * 1.5 + ph * 6.28)) * (0.3 + an.level[min(BANDS - 1, band)])
            if sy + dy < surf[min(int(sx), w - 2)] - 1 and tw > 0.45 and sx > w * 0.26:
                self.put(int(sy) + dy, int(sx) + dx, "✦" if tw > 0.85 else "·", self.fg(tw, tw > 0.85, base=STAR_FG))
        rows = np.arange(h - 1)[:, None]
        depth = (rows - surf[None, :]) / max(1.0, (h - 1) - hz)
        under = rows >= surf[None, :]
        self.field(np.clip(0.5 - depth * 0.9 + an.bass * 0.1, 0.0, 0.999), mask=under, base=WATER_BG)
        for xx in range(0, w - 1):
            yy = int(surf[xx])
            if 0 <= yy < h - 1 and surf[xx] <= surf[max(0, xx - 1)] and surf[xx] <= surf[min(w - 2, xx + 1)]:
                self.put(yy + dy, xx + dx, "≈" if an.treble > 0.35 else "~", self.fg(0.9, an.treble > 0.35, base=WAVE_FG))
        # the whirlpool: rings of water turning under the dip, faster and wider the harder she drinks
        wy = int(surf[min(wx, w - 2)])
        spin = t * (1.5 + pull * 6)
        for k in range(1, int(rad / 2) + 2):
            rr = k * 2.0
            for a in np.linspace(0, 2 * math.pi, int(rr * 4) + 8, endpoint=False):
                if (a + spin * (1 + k * 0.15)) % (math.pi / 2) < math.pi / 3:
                    px, py = wx + math.cos(a) * rr * 1.0 + dx, wy + 1 + math.sin(a) * rr * 0.35 + k * 0.5 + dy
                    if 0 <= px < w - 1 and 0 <= py < h - 1 and py >= surf[min(max(int(px), 0), w - 2)]:
                        self.put(int(py), int(px), "≈" if k % 2 else "~", self.fg(0.35 + pull * 0.5 - k * 0.05, k < 3, base=WAVE_FG))
        self.put(wy + 1 + dy, wx + dx, "◎", self.fg(0.99, True, base=WAVE_FG))
        # Scylla's rock: the cliff on the left, from the sky down into the sea, her cave in it
        cw = int(w * 0.24)
        cliff = Canvas(h, w)
        edge = [(cw * 2 + int(math.sin(k * 0.9) * 4), k * 4) for k in range(0, int(surf[:cw].max()) + 2)]
        cliff.poly([(0, 0)] + edge + [(0, edge[-1][1] + 4)], 0.45)
        for (ry, rx), cell in cliff.cells.items():                     # rock, not a slab: a fixed grain in the dots
            cell[0] &= self.ROCK_GRAIN[(ry * 3 + rx * 5) % len(self.ROCK_GRAIN)]
            cell[1] = 0.3 + ((ry * 7 + rx * 3) % 5) * 0.06
        cliff.paint(self, bold=False, base=RADIAL_FG)
        for k in range(0, min(h - 2, int(surf[:cw].max()) + 1)):
            self.put(k, max(0, cw - 6 + int(math.sin(k * 0.9))), "▐", self.fg(0.25, False, base=RADIAL_FG))
        cave_y = max(2, int(h * 0.12))
        self.put(cave_y, max(0, cw - 12), "▄▄▟████▙▄▄", self.fg(0.05, False, base=RADIAL_FG))
        self.put(cave_y + 1, max(0, cw - 12), "▀▀▜████▛▀▀", self.fg(0.05, False, base=RADIAL_FG))
        # the ship, rowing west through the strait; Charybdis slows and spins it when the bass is high
        ship_w = 42
        cx = int(st["x"]) + (4 if st["raft"] else ship_w // 2)
        near = abs(cx - wx) < rad * 2.2
        if st["swallowed"] is not None:
            if t > st["swallowed"] + 3:                                 # spat back, upstream of the maw
                st["swallowed"] = None
                st["x"] = min(float(w - ship_w - 2), st["x"] + 20)   # spat back east, and safe for a while
                st["grace"] = t + 8
                st["text"] = (self.SCYLLA_SAYS["spit"], t + 3)
                st["shake"] = 6
                st["spray"] = [[wx + self.rng.random() * 24 - 12, surf[min(wx, w - 2)] - 4 - self.rng.random() * 8, 1.0]
                               for _ in range(30)]
        else:
            speed = (0.05 + an.rms * 0.4) * (0.5 if st["raft"] else 1.0)
            if near:
                st["suck"] = min(2.5, st["suck"] + pull * (1 / FPS) * 1.0)
                speed *= max(0.1, 1 - pull * 1.1)
                st["spin"] += pull * 0.4
                if pull > 0.72 and st["suck"] > 2.0 and t > st["grace"]:   # only a big, sustained bass drinks the ship
                    st["swallowed"] = t
                    st["suck"] = 0.0
                    st["text"] = (self.SCYLLA_SAYS["drink"], t + 3)
                    st["spray"] = [[wx + self.rng.random() * 16 - 8, surf[min(wx, w - 2)] - 2 - self.rng.random() * 6, 1.0]
                                   for _ in range(24)]
                    if st["n"] > 0:
                        st["n"] -= 1
                        if st["n"] == 0:
                            st["raft"] = True
                            st["text"] = (self.SCYLLA_SAYS["alone"], t + 4)
            else:
                st["suck"] = max(0.0, st["suck"] - 1 / FPS)
            st["x"] -= speed
        # the heads: six necks out of the cave, swaying; in reach of the ship a big beat sends one down
        heads = st["heads"]
        anchor = (max(0, cw - 8) * 2, cave_y * 4 + 4)
        in_reach = st["swallowed"] is None and cw - 4 < cx < w * 0.55
        if in_reach and an.beat > 0.5 and t > st["cool"]:
            idle = [hd for hd in heads if hd["target"] is None]
            if idle:
                hd = idle[int(self.rng.integers(len(idle)))]
                hd["target"], hd["t0"] = (cx, int(surf[min(cx, w - 2)]) - (2 if st["raft"] else 5)), t
                st["cool"] = t + 3 + self.rng.random() * 3
        necks = Canvas(h, w)
        jaws = []
        cv_gw, cv_gh = max(2, (w - 1) * 2), max(4, (h - 1) * 4)
        for i, hd in enumerate(heads):
            base_a = 0.05 + i * 0.17                                     # a fan of resting angles below the horizontal, in radians
            L = min(cv_gw * 0.2, cv_gh * 0.35) * (0.75 + 0.05 * i) * (0.8 + an.mid * 0.4)   # neck length in dots
            sway = math.sin(t * 1.3 + hd["sway"]) * 0.12 + an.treble * 0.1 * math.sin(t * 4 + i)
            rest = (anchor[0] + math.cos(base_a + sway) * L, anchor[1] + math.sin(base_a + sway) * L * 0.6)
            k = 0.0
            if hd["target"] is not None:
                k = (t - hd["t0"]) / 0.9
                if k >= 1:                                            # back in the cave
                    hd["target"], hd["bit"], k = None, False, 0.0
                elif k >= 0.45 and not hd.get("bit"):                 # the jaws reach the deck
                    hd["bit"] = True
                    if st["n"] > 0 and not st["raft"]:
                        st["n"] -= 1
                        st["taken"] += 1
                        st["text"] = (self.SCYLLA_SAYS["take"], t + 2)
                        st["shake"] = 4
                        if st["n"] == 0:
                            st["raft"] = True
                            st["text"] = (self.SCYLLA_SAYS["alone"], t + 4)
            if hd["target"] is not None and k > 0:
                reach = math.sin(min(1.0, k * 2) * math.pi / 2) if k < 0.5 else math.cos((k - 0.5) * math.pi)
                tx, ty = hd["target"][0] * 2, hd["target"][1] * 4
                end = (rest[0] + (tx - rest[0]) * reach, rest[1] + (ty - rest[1]) * reach)
            else:
                end = rest
            # a bowed neck: quadratic curve through a control point above the chord
            ctrl = ((anchor[0] + end[0]) / 2 + 10, min(anchor[1], end[1]) - 12)
            prev = anchor
            for s in np.linspace(0, 1, 14)[1:]:
                px = (1 - s) ** 2 * anchor[0] + 2 * (1 - s) * s * ctrl[0] + s ** 2 * end[0]
                py = (1 - s) ** 2 * anchor[1] + 2 * (1 - s) * s * ctrl[1] + s ** 2 * end[1]
                necks.line(prev[0], prev[1], px, py, 0.5 + (0.45 if hd["target"] is not None else 0.0), width=2 * self.stroke(h, w))
                prev = (px, py)
            jaws.append((int(end[1] / 4), int(end[0] / 2), hd["target"] is not None))
        necks.paint(self, bold=an.beat > 0.3, base=RAIN_FG)
        for jy, jx, biting in jaws:
            if 0 <= jy < h - 1 and 0 <= jx < w - 2:
                self.put(jy, jx, "◖<" if biting else "◖‹", self.fg(0.95 if biting else 0.7, biting, base=RAIN_FG))
        # the ship, or the raft, on the swell; swallowed, it is under the whirlpool
        if st["swallowed"] is None:
            if st["raft"]:
                py = int(surf[min(max(cx, 0), w - 2)]) - 2
                self.sprite_at(h, w, self.RAFT, int(st["x"]) + dx, py + dy,
                               lambda ch: self.fg(0.95, True, base=WAVE_FG) if ch in "o/|\\" else self.fg(0.6, False, base=RADIAL_FG),
                               surf=surf)
            else:
                oar = (int(st["spin"]) if near and pull > 0.4 else int(self.frame / max(2, 8 - int(an.rms * 12)))) % 3
                rows_ = self.ship_rows(st["n"], oar, an.mid > 0.25)
                py = int(surf[min(max(cx, 0), w - 2)]) - 9
                self.sprite_at(h, w, rows_, int(st["x"]) + dx, py + dy,
                               lambda ch: (self.fg(0.95, True, base=STAR_FG) if ch in "()|" else
                                           self.fg(0.98, True, base=WAVE_FG) if ch == "o" else
                                           self.fg(0.55, False, base=RADIAL_FG)), surf=surf)
        else:
            k = (t - st["swallowed"]) / 3
            gy = wy + 3 + int(k * 6)
            if 0 <= gy < h - 1:
                self.put(gy, max(0, wx - 4 + dx), "~\\___/~", self.fg(0.4, False, base=RADIAL_FG))
        spray = []
        for sp in st["spray"]:
            sp[1] -= 0.4
            sp[2] -= 0.05
            if sp[2] > 0 and 0 <= sp[1] < h - 1 and 0 <= sp[0] < w - 1:
                self.put(int(sp[1]) + dy, int(sp[0]) + dx, "*" if sp[2] > 0.5 else "·", self.fg(0.9, True, base=WAVE_FG))
                spray.append(sp)
        st["spray"] = spray
        # through the strait: past the rock, it starts again from the east, six at the oars
        if st["x"] <= 1:
            st["text"] = (self.SCYLLA_SAYS["through"] + (f", {st['n']} LEFT" if st["n"] else ", ALONE"), t + 4)
            st.update({"x": float(w - ship_w - 2), "n": 6, "raft": False, "cool": t + 6, "suck": 0.0, "swallowed": None})
        if st["text"] and t < st["text"][1]:
            msg = st["text"][0]
            self.put(1, max(0, (w - len(msg)) // 2) + dx, msg[:w - 1], self.fg(1.0, True, base=RADIAL_FG))
        elif st["text"] and t >= st["text"][1]:
            st["text"] = None
        self.put(h - 2, 1, f"companions {st['n']}  ·  Scylla has taken {st['taken']}  ·  Charybdis drinks {int(pull * 100)}%",
                 self.fg(0.5, False, base=WAVE_FG))

    # ---- sleestak (the Lost City at night)
    SLEESTAK = [  # the walk, four phases, facing right; O are the eyes; the arms are out in front and swing as it goes
        ["  .-==-. ", " ( O  O )", "  \\ ‾‾ / ", "  _||‾‾> ", "   ||    ", "  / \\    ", " ^   ^   "],
        ["  .-==-. ", " ( O  O )", "  \\ ‾‾ / ", "  _||--> ", "   ||    ", "   ||    ", "   ^^    "],
        ["  .-==-. ", " ( O  O )", "  \\ ‾‾ / ", "  _||__> ", "   ||    ", "  / \\    ", " ^   ^   "],
        ["  .-==-. ", " ( O  O )", "  \\ ‾‾ / ", "  _||--> ", "   ||    ", "   ||    ", "   ^^    "],
    ]
    SLEESTAK_UP = ["  .-==-./", " ( O  O )", "  \\ ‾‾ /|", "  _||  | ", "   ||    ", "  / \\    ", " ^   ^   "]  # an arm up: torch in its face, or a hiss
    WILL = [[" o ", "/|\\", " | ", "/ \\"], [" o ", "/|\\", " | ", " | "]]       # the torch bearer, facing right
    HOLLY = [["=o=", "/|\\", "/ \\"], ["=o=", "/|\\", " | "]]                   # pigtails, behind him
    SLEESTAK_SAYS = ["the Sleestak are cold-blooded; in the cold they sleep", "ssssss", "the Marshalls are in the Lost City",
                     "Enik would not approve", "do not let the torch go out"]
    MARSHALL_SAYS = ["HOLLY, STAY BEHIND ME", "Will!", "keep the torch up", "they're slow, keep moving", "Dad!", "the pylon, Will, get to the pylon"]

    def draw_sleestak(self, h, w):
        an = self.an
        t = self.t
        floor = h - 3
        st = self.state("sleestak", h, w, lambda: {
            "quiet": 0.0, "warm": 0.0, "sleestak": [], "bolts": [], "say": None, "say_until": 0.0, "beat_prev": 0.0,
            "hx": w * 0.5 + 3, "hdir": 1, "hnext": 0.0, "charge_until": 0.0, "hstep": 0, "shout": None, "shout_until": 0.0, "shout_next": 0.0,
            "stars": np.column_stack([self.rng.random(40) * (w - 1), self.rng.random(40) * max(1, h // 2), self.rng.random(40)])})
        dt = 1 / FPS
        st["quiet"] = st["quiet"] + dt if an.rms < 0.05 else 0.0
        quiet = st["quiet"] > 4
        onset = an.beat > 0.4 >= st["beat_prev"]                    # the first frame of a beat
        st["beat_prev"] = an.beat
        # the warmth of the music: cold-blooded, they only move when it is warm
        st["warm"] = max(0.0, min(1.0, st["warm"] + (an.rms * 5.0 + an.beat * 0.5 - 0.25) * dt * 2))   # anything over the quiet line warms them
        warm = st["warm"]
        # the sky: a few stars over the ruins, twinkling with the treble
        for sx, sy, ph in st["stars"]:
            tw = 0.2 + 0.8 * abs(math.sin(t * 1.2 + ph * 6.28)) * (0.3 + an.treble)
            if tw > 0.5 and sy < floor - 12:
                self.put(int(sy), int(sx), "·" if tw < 0.85 else "✦", self.fg(tw, False, base=STAR_FG))
        cols_x = [int(w * f) for f in (0.08, 0.2, 0.8, 0.92)]          # the Lost City's columns; drawn last, everyone passes behind them
        # the torch is in Will's hand, held out toward whichever side is pressing; the flame is the bass, and
        # its light is all that keeps them back
        hx, hdir = st["hx"], st["hdir"]
        tx = int(hx) + (3 if hdir > 0 else -1)
        flame_h = 2 + int(an.bass * 7 + an.beat * 3)
        light = 8 + flame_h * 3
        # the floor: a pool of torch light, dark beyond it
        pool = 0.15 + 0.6 * np.clip(1 - np.abs(np.arange(w - 1) - tx) / light, 0, 1) ** 1.5
        q = (pool * 12).astype(int)
        x0 = 0
        for x1 in range(1, w):
            if x1 == w - 1 or q[x1] != q[x0]:
                self.put(floor, x0, "▔" * (x1 - x0), self.fg(pool[x0], False, base=RADIAL_FG))
                x0 = x1
        # the Sleestak: they come out of the dark on either side, eyes first, and chase the torch at their own pace,
        # each on its own step; cold-blooded, they only step while the music is warm, faster the warmer
        sl = st["sleestak"]
        want = min(2 + int(an.rms * 8), 3 + w // 60)
        if len(sl) < want and self.rng.random() < dt:                       # about one a second while short
            side = -1 if self.rng.random() < 0.5 else 1
            sl.append({"x": float(-2 if side > 0 else w - 8), "dir": side, "ph": 0, "up": 0, "flash": 0, "hiss": 0,
                       "next": t + self.rng.random() * 0.3, "gone": False})
        near = [None, None]                                                 # the closest on the left / right, from the light's edge
        keep = []
        for s_ in sl:
            edge = tx - light - 9 if s_["dir"] > 0 else tx + light          # the sprite is nine wide
            for o in sl:                                                    # the one behind waits for the one ahead
                if o is not s_ and o["dir"] == s_["dir"] and not o["gone"] and (o["x"] - s_["x"]) * s_["dir"] > 0:
                    edge = min(edge, o["x"] - 11) if s_["dir"] > 0 else max(edge, o["x"] + 11)
            inside = (s_["x"] - edge) * s_["dir"]                           # > 0: the light is on it
            if quiet and self.rng.random() < 0.002:                         # cold long enough, they go back into the dark
                s_["gone"] = True
            if s_["gone"]:
                s_["x"] -= s_["dir"] * 0.5
                if -10 <= s_["x"] <= w:
                    keep.append(s_)
                continue
            keep.append(s_)
            side = 0 if s_["dir"] > 0 else 1
            if near[side] is None or -inside < near[side]:
                near[side] = -inside
            if onset and s_["next"] > t + 0.08:                             # a beat lands the step early
                s_["next"] = t
            if t >= s_["next"] and warm > 0.2:                              # cold-blooded: no warmth, no step
                s_["next"] = t + 0.35 - 0.2 * warm
                if inside < -2:                                             # room ahead: a step toward the torch
                    s_["x"] += s_["dir"] * (1 + warm * 2)
                    s_["ph"] = (s_["ph"] + 1) % 4
                elif inside > 1:                                            # the light is in its face: back, arm up
                    s_["x"] -= s_["dir"] * 2
                    s_["ph"] = (s_["ph"] + 1) % 4
                    s_["up"] = 6
                elif self.rng.random() < 0.4:                               # at the edge: it shifts and reaches
                    s_["ph"] = 1 if s_["ph"] == 0 else 0
            if onset and an.beat > 0.45:
                s_["flash"] = 6
                if inside > -8 and self.rng.random() < 0.5:                 # the ones at the light hiss and reach
                    s_["up"] = 7
                    s_["hiss"] = 8
                if an.beat > 0.5 and -5 < inside < 2 and not st["bolts"] and self.rng.random() < 0.35:  # a crossbow bolt
                    st["bolts"].append({"x": s_["x"] + (8 if s_["dir"] > 0 else 0), "y": floor - 4.0, "vx": s_["dir"] * 1.3, "vy": -0.1})
            s_["flash"] = max(0, s_["flash"] - 1)
            s_["up"] = max(0, s_["up"] - 1)
            eyes = s_["flash"] > 0
            lit = max(0.0, 1 - max(0.0, -inside) / (w * 0.3))               # deep in the dark only the eyes show
            frame = self.SLEESTAK_UP if s_["up"] else self.SLEESTAK[s_["ph"]]
            if lit < 0.15:
                frame = ["".join(c if c == "O" else " " for c in row) for row in frame]
            self.sprite_at(h, w, frame, int(s_["x"]), floor - len(frame),
                           lambda ch, eyes=eyes, lit=lit: (self.fg(1.0, True, base=STAR_FG) if ch == "O" and eyes else
                                                           self.fg(0.55 + an.treble * 0.4, an.treble > 0.3, base=STAR_FG) if ch == "O" else
                                                           self.fg(0.2 + lit * 0.5 + warm * 0.2, warm > 0.5 and lit > 0.5, base=RAIN_FG)),
                           mirror=s_["dir"] < 0)
            if s_["hiss"] > 0:
                s_["hiss"] -= 1
                self.put(floor - len(frame) - 1, int(s_["x"]) + 2, self.HISS[(self.frame // 3) % len(self.HISS)], self.fg(0.95, True, base=RAIN_FG))
        st["sleestak"] = keep
        # the bolts: they never hit anything
        bolts = []
        for b in st["bolts"]:
            b["x"] += b["vx"]
            b["vy"] += 0.02
            b["y"] += b["vy"]
            if b["y"] >= floor - 1 or abs(b["x"] - tx) < 3 or not (0 <= b["x"] < w - 2):
                self.put(floor - 1, int(min(max(b["x"], 0), w - 2)), "✧", self.fg(0.9, True, base=RADIAL_FG))
                continue
            self.put(int(b["y"]), int(b["x"]), "─>" if b["vx"] > 0 else "<─", self.fg(0.6, False, base=RADIAL_FG))
            bolts.append(b)
        st["bolts"] = bolts
        # the Marshalls back away from whichever side is pressing, torch out, and the columns pen them in;
        # with nobody pressing they edge back toward the pylon
        lo, hi = cols_x[1] + 6, cols_x[2] - 8
        press_l = near[0] is not None and near[0] < 4
        press_r = near[1] is not None and near[1] < 4
        charging = t < st["charge_until"]                                  # cornered, they wave the torch and push through
        if charging:
            pass
        elif press_l and press_r:
            hdir = -1 if near[0] < near[1] else 1
        elif press_l or press_r:
            hdir = -1 if press_l else 1
        cornered = False
        if t >= st["hnext"] and not quiet:
            st["hnext"] = t + 0.18
            if charging:
                ahead = near[0 if hdir < 0 else 1]
                if (ahead is None or ahead > -4) and lo <= hx + hdir * 2 <= hi:   # up to the Sleestak, not through it
                    hx, st["hstep"] = hx + hdir * 2, st["hstep"] ^ 1
            elif press_l or press_r:
                nx = hx - hdir * 2
                if lo <= nx <= hi:
                    hx, st["hstep"] = nx, st["hstep"] ^ 1
                else:
                    cornered = True
                    st["charge_until"] = t + 2.0
            elif abs(hx - (w * 0.5 + 3)) > 2:
                hx, st["hstep"] = hx + (1 if hx < w * 0.5 + 3 else -1), st["hstep"] ^ 1
        st["hx"], st["hdir"] = hx, hdir
        if cornered and t > st["shout_next"]:
            st["shout"] = self.MARSHALL_SAYS[int(self.rng.integers(len(self.MARSHALL_SAYS)))]
            st["shout_until"], st["shout_next"] = t + 2.5, t + 6
        hx_ = int(hx)
        tx = hx_ + (3 if hdir > 0 else -1)                                 # the torch goes with the turn
        for k in range(flame_h):
            fl = "▲" if k == flame_h - 1 else ("▓" if k > flame_h // 2 else "█")
            self.put(floor - 3 - k, tx + int(math.sin(t * 9 + k) * (1 if k > 1 else 0)), fl,
                     self.fg(0.35 + k / max(1, flame_h) * 0.6, True, base=RADIAL_FG))
        self.put(floor - 2, tx, "|", self.fg(0.5, False, base=RADIAL_FG))
        self.sprite_at(h, w, self.WILL[st["hstep"]], hx_, floor - 4, lambda ch: self.fg(0.75, False, base=RADIAL_FG), mirror=hdir < 0)
        self.sprite_at(h, w, self.HOLLY[st["hstep"]], hx_ - hdir * 4, floor - 3, lambda ch: self.fg(0.65, False, base=RADIAL_FG), mirror=hdir < 0)
        if st["shout"] and t < st["shout_until"]:
            self.put(floor - 9, max(0, hx_ + 1 - len(st["shout"]) // 2), st["shout"], self.fg(0.9, True, base=RADIAL_FG))
        # the Lost City in front of them all: columns, dim, and the pylon off to one side, its crystals lit by the bass
        for cxx in cols_x:
            top = max(1, floor - 10 - int(an.mid * 3))
            self.put(top, cxx - 1, "╔═╗", self.fg(0.25, False, base=RADIAL_FG))
            for yy in range(top + 1, floor):
                self.put(yy, cxx, "║", self.fg(0.18 + 0.1 * (yy % 2), False, base=RADIAL_FG))
        px_ = int(w * 0.14)                                                # in the dark, between the outer columns
        for k in range(6):
            yy = floor - 1 - k
            lit = an.level[min(BANDS - 1, k * 3)] > 0.35
            self.put(yy, px_, "▐" + ("◆" if lit else "◇") + "▌", self.fg(0.9, lit, base=SPARK_FG) if lit else self.fg(0.2, False, base=RADIAL_FG))
        self.put(floor - 7, px_, "▟█▙", self.fg(0.3, False, base=RADIAL_FG))
        if quiet and t > st["say_until"]:
            st["say"] = self.SLEESTAK_SAYS[int(self.rng.integers(len(self.SLEESTAK_SAYS)))] if self.rng.random() < 0.6 else None
            st["say_until"] = t + 6
        if quiet and st["say"]:
            self.put(h - 2, 1, st["say"], self.fg(0.6, False, base=RAIN_FG))
        else:
            self.put(h - 2, 1, f"warmth {int(warm * 100)}%  ·  {len(keep)} Sleestak  ·  torch {flame_h}", self.fg(0.4, False, base=RAIN_FG))

    # ---- stealie (steal your face)
    def draw_stealie(self, h, w):
        an = self.an
        t = self.t
        st = self.state("stealie", h, w, lambda: {"flash": 0.0, "spin": 0.0, "peak": np.zeros(13), "say": 0.0})
        cv_gw, cv_gh = max(2, (w - 1) * 2), max(4, (h - 1) * 4)
        cx, cy = cv_gw / 2, cv_gh / 2 - 2
        R = min(cv_gw / 2, cv_gh / 2) * (0.82 + an.beat * 0.03)
        st["flash"] = max(st["flash"] * 0.85, min(1.0, an.beat * 2))
        st["spin"] += (0.15 + an.rms * 1.2) / FPS
        red, blue, white, bolt, rim = (Canvas(h, w) for _ in range(5))
        # the bolt: a zigzag down the middle of the cranium, in units of R
        path = [(-0.20, -0.80), (0.10, -0.28), (-0.10, -0.22), (0.22, 0.28)]

        def bolt_x(v):                                             # the bolt's centre line at height v (units of R)
            for (ax, ay), (bx, by) in zip(path, path[1:]):
                if ay <= v <= by:
                    return ax + (bx - ax) * (v - ay) / (by - ay)
            return path[0][0] if v < path[0][1] else path[-1][0]
        brow = -0.08                                               # the cranium ends here; the face is below
        Ri = R * 0.80
        for py in range(int(cy - Ri), int(cy + Ri) + 1):
            v = (py - cy) / R
            half = math.sqrt(max(0.0, Ri * Ri - (py - cy) ** 2))
            for px in range(int(cx - half), int(cx + half) + 1):
                u = (px - cx) / R
                if v < brow:
                    bx = bolt_x(v)
                    if abs(u - bx) < 0.07:
                        bolt.dot(px, py, 0.99)
                    elif u < bx:
                        red.dot(px, py, 0.02 + an.bass * 0.08)
                    else:
                        blue.dot(px, py, 0.80 - an.treble * 0.1)
                else:
                    # the face: eye sockets (wider with the bass), the nose, the teeth
                    ex = 0.30 + an.bass * 0.03
                    if ((u - ex) / 0.19) ** 2 + ((v - 0.18) / (0.14 + an.bass * 0.05)) ** 2 < 1 or \
                       ((u + ex) / 0.19) ** 2 + ((v - 0.18) / (0.14 + an.bass * 0.05)) ** 2 < 1:
                        continue
                    if 0.34 < v < 0.52 and abs(u) < 0.06 * (v - 0.34) / 0.18:
                        continue
                    if 0.58 < v < 0.76 and abs(u) < 0.34 and (int((u + 0.34) / 0.085) % 2 == 1 or abs(v - 0.67) < 0.015):
                        continue
                    white.dot(px, py, 0.97)
        # the ring, and the thirteen points around it: each one a group of bands
        ring = Canvas(h, w)
        ring.circle(cx, cy, R * 0.84, 0.9, n=int(R * 3))
        ring.circle(cx, cy, R * 0.86, 0.9, n=int(R * 3))
        st["peak"] = np.maximum(st["peak"] * 0.92, np.array([an.level[int(i * BANDS / 13):int((i + 1) * BANDS / 13)].max() for i in range(13)]))
        for i in range(13):
            a = -math.pi / 2 + i * 2 * math.pi / 13 + st["spin"]
            L = R * (0.88 + 0.12 * st["peak"][i])
            for rr in np.linspace(R * 0.87, L, max(2, int((L - R * 0.87)) + 1)):
                spread = 0.06 * (1 - (rr - R * 0.87) / max(1, L - R * 0.87))
                for da in (-spread, 0, spread):
                    rim.dot(cx + math.cos(a + da) * rr, cy + math.sin(a + da) * rr, 0.3 + st["peak"][i] * 0.7)
            hx, hy = cx + math.cos(a) * R * 0.99, cy + math.sin(a) * R * 0.99
            rim.dot(hx, hy, 0.9)
        rim.paint(self, bold=an.treble > 0.3, base=STAR_FG)
        ring.paint(self, bold=False, base=STAR_FG)
        red.paint(self, bold=an.bass > 0.3, base=SPARK_FG)
        blue.paint(self, bold=an.treble > 0.3, base=SPARK_FG)
        white.paint(self, bold=True, base=STAR_FG)
        bolt.paint(self, bold=True, base=STAR_FG if st["flash"] > 0.3 else WAVE_FG)
        if an.beat > 0.5:
            st["say"] = t + 1.5
        if t < st["say"]:
            msg = "STEAL YOUR FACE RIGHT OFF YOUR HEAD"
            self.put(1, max(0, (w - len(msg)) // 2), msg[:w - 1], self.fg(0.99, True, base=STAR_FG))

    # ---- wall (the Wall of Sound, 1974)
    # (label, x as a fraction of the width, columns side by side, cabinets tall, first band, last band, ramp)
    WALL = [("BOB", 0.09, 2, 8, 12, 24, "wave"), ("PHIL", 0.25, 4, 12, 0, 12, "star"), ("VOCALS", 0.50, 3, 14, 18, 36, "radial"),
            ("JERRY", 0.68, 2, 9, 14, 30, "spark"), ("KEITH", 0.83, 2, 6, 8, 30, "spiral"), ("DRUMS", 0.94, 1, 5, 36, 48, "rain")]
    WALL_BASES = {"wave": "WAVE_FG", "star": "STAR_FG", "radial": "RADIAL_FG", "spark": "SPARK_FG", "spiral": "SPIRAL_FG", "rain": "RAIN_FG"}

    def draw_wall(self, h, w):
        an = self.an
        t = self.t
        floor = h - 4                                                  # the labels' row; the stage is under it
        st = self.state("wall", h, w, lambda: {"peak": {}, "shake": 0, "lit": 0})
        if an.beat > 0.45:
            st["shake"] = 2
        dx = 0
        if st["shake"] > 0:
            st["shake"] -= 1
            dx = int(self.rng.integers(-1, 2))
        s = self.stroke(h, w)                                          # a cabinet is 4x2 cells at the reference font, 8x4 at half size
        cw, ch_ = 4 * s, 2 * s
        avail = max(4, (floor - 3) // ch_)                             # cabinet rows that fit
        tallest = max(s_[3] for s_ in self.WALL)
        scale = min(1.0, avail / tallest)
        lit_total = cab_total = 0
        # the scaffold behind the wall
        for yy in range(max(1, floor - int(tallest * scale) * ch_ - 1), floor):
            self.put(yy, 1, "│", self.fg(0.15, False, base=RADIAL_FG))
            self.put(yy, w - 3, "│", self.fg(0.15, False, base=RADIAL_FG))
        box = ["└" + "─" * (cw - 2) + "┘"] + ["│" + " " * (cw - 2) + "│"] * (ch_ - 2) + ["┌" + "─" * (cw - 2) + "┐"]
        for label, xf, ncol, tall, lo, hi, ramp in self.WALL:
            base = globals()[self.WALL_BASES[ramp]]
            rows_ = max(2, int(tall * scale))
            width = ncol * (cw + 1)
            x0 = int(w * xf) - width // 2 + dx
            bands = an.level[lo:hi]
            per = max(1, len(bands) // ncol)
            for c in range(ncol):
                lvl = float(bands[c * per:(c + 1) * per].mean()) if len(bands) else 0.0
                key = (label, c)
                st["peak"][key] = max(lvl, st["peak"].get(key, 0.0) - 0.012)
                filled = lvl * rows_
                peak_row = int(st["peak"][key] * rows_ + 0.5)
                for r in range(rows_):
                    yy = floor - 1 - r * ch_                           # the cabinet's bottom row
                    if yy - ch_ + 1 < 1:
                        break
                    xx = x0 + c * (cw + 1)
                    cab_total += 1
                    lit = r < filled
                    if lit:
                        lit_total += 1
                        col = 0.25 + 0.7 * r / max(1, rows_ - 1)
                        for k in range(ch_):                           # grille on the lower half, solid above
                            top = k >= ch_ // 2
                            self.put(yy - k, xx, "▐" + ("█" if top else "▓") * (cw - 2) + "▌",
                                     self.fg(col, top and r > rows_ * 0.6, base=base))
                    else:
                        attr = self.fg(0.6, False, base=base) if r == peak_row and peak_row > 0 else curses.A_DIM
                        for k in range(ch_):
                            self.put(yy - k, xx, box[k], attr)
            self.put(floor, max(0, x0 + (width - len(label)) // 2), label, self.fg(0.8, an.beat > 0.3, base=base))
        # the stage
        self.put(floor + 1, 0, "▔" * (w - 1), self.fg(0.3 + an.bass * 0.3, False, base=RADIAL_FG))
        st["lit"] = lit_total
        self.put(h - 2, 1, f"the Wall of Sound, 1974  ·  {lit_total} of {cab_total} cabinets lit"
                 + ("  ·  PHIL'S QUAD" if an.bass > 0.6 else ""), self.fg(0.5, False, base=WAVE_FG))

    def next_mode(self, step=1):
        self.mode = MODES[(MODES.index(self.mode) + step) % len(MODES)]

    def run(self, idle_exit=None):
        """Draw until a key is pressed that on_key() does not swallow (Esc, normally). Returns the key (or -1)."""
        self.cap.start()
        self.scr.nodelay(True)
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        frame = 1.0 / FPS
        last = 0
        while True:
            now = time.time()
            if now - last >= frame:
                last = now
                self.t = now - self.t0
                self.frame += 1
                self.an.update(self.cap.samples())
                self.hue = (self.hue + 0.002 + self.an.beat * 0.01) % 1.0
                h, w = self.scr.getmaxyx()
                self.scr.erase()
                getattr(self, "draw_" + self.mode)(h, w)
                title = self.title_fn()
                foot = f" {self.mode}  ·  {title}" if title else f" {self.mode}"
                if self.cap.error:
                    foot = f" {self.cap.error}"
                self.put(h - 1, 0, foot[:w - 1], curses.A_DIM)
                self.scr.refresh()
            ch = self.scr.getch()
            if ch == -1:
                time.sleep(0.005)
                continue
            if ch == curses.KEY_RESIZE:
                continue
            if ch in (ord("v"), ord("m")):
                self.next_mode(1)
                continue
            if ch in (ord("V"), ord("M")):
                self.next_mode(-1)
                continue
            if ch in (curses.KEY_UP, curses.KEY_DOWN):    # which way the waterfall runs
                self.flow = "up" if ch == curses.KEY_UP else "down"
                continue
            if ord("0") <= ch <= ord("9"):
                i = (ch - ord("1")) % 10                  # 1-9 then 0 pick the first ten modes
                if i < len(MODES):
                    self.mode = MODES[i]
                continue
            if self.on_key(ch):
                continue
            break
        self.cap.stop()
        self.scr.nodelay(False)
        return ch


def main():
    def go(scr):
        curses.use_default_colors()
        Viz(scr, title_fn=lambda: "deadviz standalone  (v next mode, V previous, 1-9/0 pick, ↑↓ waterfall direction, Esc quits)").run()
    os.environ.setdefault("ESCDELAY", "25")
    curses.wrapper(go)


if __name__ == "__main__":
    main()
