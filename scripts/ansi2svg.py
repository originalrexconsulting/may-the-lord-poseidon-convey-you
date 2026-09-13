#!/usr/bin/env python3
"""ansi2svg.py - turn a `tmux capture-pane -e -p` dump into an SVG screenshot.

    tmux capture-pane -e -p -t <pane> | scripts/ansi2svg.py > docs/screenshots/home.svg
    ... | scripts/ansi2svg.py --crop     # drop the blank columns left of a centred splash

Stock python3. Handles the SGR codes curses emits (bold, dim, reverse, the 16 and
256-colour foreground/background sets). Wide glyphs take two cells, like the terminal.
"""
import re
import sys
import unicodedata

CELL_W, CELL_H, PAD = 8.4, 18, 12
FONT = "DejaVu Sans Mono, Menlo, Consolas, monospace"
BG, FG = "#0d1117", "#c9d1d9"
BASIC = ["#0d1117", "#f47067", "#57ab5a", "#c69026", "#539bf5", "#b083f0", "#39c5cf", "#adbac7",
         "#636e7b", "#ff938a", "#6bc46d", "#daaa3f", "#6cb6ff", "#dcbdfb", "#56d4dd", "#cdd9e5"]


def colour(n):
    if n < 16:
        return BASIC[n]
    if n < 232:
        n -= 16
        r, g, b = n // 36, n // 6 % 6, n % 6
        return "#%02x%02x%02x" % tuple(0 if v == 0 else 55 + v * 40 for v in (r, g, b))
    v = 8 + (n - 232) * 10
    return "#%02x%02x%02x" % (v, v, v)


def width(ch):
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else (0 if unicodedata.combining(ch) else 1)


def parse(text):
    """Yield rows of (char, fg, bg, bold) cells."""
    rows = []
    for line in text.split("\n"):
        fg, bg, bold, dim, rev = None, None, False, False, False
        cells = []
        i = 0
        while i < len(line):
            m = re.match(r"\x1b\[([0-9;]*)m", line[i:])
            if m:
                params = [int(p) if p else 0 for p in m.group(1).split(";")] if m.group(1) else [0]
                j = 0
                while j < len(params):
                    p = params[j]
                    if p == 0:
                        fg, bg, bold, dim, rev = None, None, False, False, False
                    elif p == 1:
                        bold = True
                    elif p == 2:
                        dim = True
                    elif p == 7:
                        rev = True
                    elif p == 22:
                        bold = dim = False
                    elif p == 27:
                        rev = False
                    elif 30 <= p <= 37:
                        fg = colour(p - 30)
                    elif 90 <= p <= 97:
                        fg = colour(p - 90 + 8)
                    elif 40 <= p <= 47:
                        bg = colour(p - 40)
                    elif 100 <= p <= 107:
                        bg = colour(p - 100 + 8)
                    elif p == 39:
                        fg = None
                    elif p == 49:
                        bg = None
                    elif p in (38, 48) and j + 2 < len(params) and params[j + 1] == 5:
                        c = colour(params[j + 2])
                        if p == 38:
                            fg = c
                        else:
                            bg = c
                        j += 2
                    elif p in (38, 48) and j + 4 < len(params) and params[j + 1] == 2:
                        c = "#%02x%02x%02x" % tuple(params[j + 2:j + 5])
                        if p == 38:
                            fg = c
                        else:
                            bg = c
                        j += 4
                    j += 1
                i += m.end()
                continue
            if line[i] == "\x1b":          # any other escape: skip it
                m2 = re.match(r"\x1b\[[0-9;?]*[A-Za-z]", line[i:])
                i += m2.end() if m2 else 1
                continue
            f, b = (fg or FG), bg
            if rev:
                f, b = (bg or BG), (fg or FG)
            if dim and not rev:
                f = "#768390"
            cells.append((line[i], f, b, bold))
            i += 1
        rows.append(cells)
    while rows and not any(c[0].strip() for c in rows[-1]):
        rows.pop()
    return rows


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg(rows, cols=None):
    cols = cols or max((sum(width(c[0]) for c in r) for r in rows), default=80)
    W, H = PAD * 2 + cols * CELL_W, PAD * 2 + len(rows) * CELL_H
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" viewBox="0 0 {W:.0f} {H:.0f}">',
           f'<rect width="100%" height="100%" rx="8" fill="{BG}"/>',
           f'<g font-family="{FONT}" font-size="14" xml:space="preserve">']
    for r, cells in enumerate(rows):
        y = PAD + r * CELL_H
        x = 0
        # background runs first, merged while the colour stays the same
        bx, bcol, bw = 0, None, 0
        for ch, f, b, bold in cells + [(" ", None, None, False)]:
            w = width(ch)
            if b != bcol:
                if bcol:
                    out.append(f'<rect x="{PAD + bx * CELL_W:.1f}" y="{y}" width="{bw * CELL_W + 0.5:.1f}" height="{CELL_H}" fill="{bcol}"/>')
                bx, bcol, bw = x, b, 0
            bw += w
            x += w
        # then text, merged into runs of the same style
        x = 0
        run, style, rx = [], None, 0
        def flush():
            if run:
                f, bold = style
                out.append(f'<text x="{PAD + rx * CELL_W:.1f}" y="{y + 14}" fill="{f}"'
                           + (' font-weight="bold"' if bold else "") + f'>{esc("".join(run))}</text>')
        for ch, f, b, bold in cells:
            if (f, bold) != style:
                flush()
                run, style, rx = [], (f, bold), x
            run.append(ch)
            x += width(ch)
        flush()
    out.append("</g></svg>")
    return "\n".join(out)


def crop(rows):
    """Drop blank leading columns shared by every row (for a centred splash)."""
    lead = min((next((i for i, c in enumerate(r) if c[0].strip() or c[2]), len(r)) for r in rows if any(c[0].strip() for c in r)),
               default=0)
    return [r[lead:] for r in rows]


if __name__ == "__main__":
    rows = parse(sys.stdin.read())
    if "--crop" in sys.argv:
        rows = crop(rows)
    sys.stdout.write(svg(rows))
