#!/usr/bin/python3
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
  rain       Matrix-green falling glyph columns, spawned where the music is loud
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

Stock packages only: python3-numpy, pulseaudio-utils (parec via pipewire-pulse).
"""

import curses
import math
import os
import subprocess
import threading
import time

import numpy as np

RATE = 44100
CHUNK = 1024          # samples per parec read
WINDOW = 2048         # FFT size
BANDS = 48
FPS = 24
MODES = ["bars", "plasma", "scope", "rings", "waterfall", "fire", "rain", "stars",
         "wave", "radial", "particles", "meters", "spiral", "life", "poseidon"]

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

    def run(self):
        cmd = ["parec", "--raw", "--format=s16le", f"--rate={RATE}", "--channels=2",
               "-d", "@DEFAULT_MONITOR@", "--latency-msec=40"]
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError as e:
            self.error = f"parec: {e}"
            return
        need = CHUNK * 2 * 2
        while self.alive:
            data = self.proc.stdout.read(need)
            if not data:
                self.error = "parec ended (is a sink present?)"
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
    """Interpolate a list of (r, g, b) 0..5 cube corners into 6 colours per segment plus the last one."""
    ramp = []
    for a, b in zip(steps[:-1], steps[1:]):
        for t in np.linspace(0, 1, 7)[:-1]:
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

    def line(self, x0, y0, x1, y1, col=0.5):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        if n == 1:
            self.dot(x0, y0, col)
            return
        for t in np.linspace(0.0, 1.0, n):
            self.dot(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, col)

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
        st = self.cap.samples()[-1200:]
        cv = Canvas(h, w)
        gain = 0.9 / max(0.05, float(np.abs(st).max()) if len(st) else 1.0)
        gain = min(gain, 12.0)
        col = 0.3 + self.an.bass * 0.7
        for l, r in st[::2]:
            cv.dot((l * gain * 0.5 + 0.5) * (cv.gw - 1), (0.5 - r * gain * 0.5) * (cv.gh - 1), col)
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

    # ---- waterfall (spectrogram scrolling up, newest row at the bottom)
    def draw_waterfall(self, h, w):
        st = self.state("waterfall", h, w, lambda: {"rows": []})
        rows = st["rows"]
        rows.append(self.an.level[self.band_cols(w - 1)])
        del rows[:-(h - 1)]
        v = np.zeros((h - 1, w - 1))
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
                    col = 0.98 if k == 0 else 0.1 + fade * 0.5 + lvl[x] * 0.25   # white head, green tail
                    self.put(yy, int(x), ch, self.fg(col, k == 0, base=RAIN_FG))

    # ---- stars (warp field, faster with the bass)
    def draw_stars(self, h, w):
        an = self.an
        n = 180
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
        for chan, (top, hh) in enumerate(((0, half), (half, cv.gh - half))):
            ys = top + hh / 2 - st[idx, chan] * gain * (hh / 2 - 1)
            amp = np.abs(st[idx, chan] * gain)                # loud swings go white, quiet stays cyan
            for x in range(1, n):
                cv.line(x - 1, ys[x - 1], x, ys[x], 0.3 + min(1.0, amp[x]) * 0.7)
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
        for i in range(BANDS):
            r = rmin + an.level[i] * (rmax - rmin)
            col = 0.2 + an.level[i] * 0.8                     # quiet bands orange, loud ones gold
            for sign in (1, -1):
                a = -math.pi / 2 + rot + sign * (i + 0.5) / BANDS * math.pi
                cv.line(cx + math.cos(a) * rmin, cy + math.sin(a) * rmin,
                        cx + math.cos(a) * r, cy + math.sin(a) * r, col)
        cv.circle(cx, cy, rmin * 0.85, 0.6 + an.bass * 0.4)
        cv.paint(self, an.beat > 0.3, base=RADIAL_FG)

    # ---- particles (fireworks: each beat launches a burst in its own colour)
    def draw_particles(self, h, w):
        an = self.an
        st = self.state("particles", h, w, lambda: {"p": np.zeros((0, 6))})
        p = st["p"]                                       # x, y, vx, vy, life, hue
        k = int(an.beat * 80 + an.rms * 10)
        if k:
            if an.beat > 0.15:                            # a real beat: one shell, one colour, off-centre
                ox = (w - 1) * (0.25 + self.rng.random() * 0.5)
                oy = (h - 1) * (0.25 + self.rng.random() * 0.4)
                hue = np.full(k, self.rng.random()) + self.rng.random(k) * 0.08
            else:                                         # quiet trickle: a few sparks of every colour
                ox, oy = (w - 1) / 2, (h - 1) * 0.6
                hue = self.rng.random(k)
            ang = self.rng.random(k) * 2 * math.pi
            spd = (0.4 + self.rng.random(k)) * (0.6 + an.bass * 2)
            new = np.column_stack([np.full(k, ox), np.full(k, oy),
                                   np.cos(ang) * spd * 2.2, np.sin(ang) * spd - 0.3 - an.beat,
                                   np.ones(k), hue % 1.0])
            p = np.vstack([p, new])
        if len(p):
            p[:, 0] += p[:, 2]
            p[:, 1] += p[:, 3]
            p[:, 3] += 0.07                               # gravity
            p[:, 2] *= 0.985
            p[:, 4] -= 0.015 + 0.02 * (1 - min(1.0, an.rms * 4))
            keep = ((p[:, 4] > 0) & (p[:, 0] >= 0) & (p[:, 0] < w - 1)
                    & (p[:, 1] >= 0) & (p[:, 1] < h - 1))
            p = p[keep][-700:]
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
        for arm in range(arms):
            px = py = None
            for k in range(n):
                f = k / (n - 1)
                lvl = an.level[int(f * (BANDS - 1))]
                rad = f * big * (0.5 + lvl * 0.5)
                a = f * math.pi * twist + rot + arm * 2 * math.pi / arms
                x, y = cx + math.cos(a) * rad, cy + math.sin(a) * rad
                if px is not None:
                    cv.line(px, py, x, y, min(1.0, f * 0.6 + lvl * 0.4))   # purple core -> pink tips
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
            frame = frames[(self.frame // 8) % len(frames)]
            fw, fh = len(frame[0]), len(frame)
            alive = True
            if k == "shark":
                f["x"] += f["dir"] * (0.22 + an.bass * 0.35 + an.beat * 0.3)
                y = f["y"] + math.sin(self.t * 1.5) * 0.8
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
        Viz(scr, title_fn=lambda: "deadviz standalone  (v next mode, V previous, 1-9/0 pick, Esc quits)").run()
    os.environ.setdefault("ESCDELAY", "25")
    curses.wrapper(go)


if __name__ == "__main__":
    main()
