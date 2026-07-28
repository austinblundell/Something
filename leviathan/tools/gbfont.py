"""
gbfont.py -- two typefaces for the title screen.

`SMALL` is a 5x7 pixel face used for the tagline and the prompts.  It is
stored as literal pixel art so what you read in the source is what lands on
the screen.

`LOGO` is the display face used for the word LEVIATHAN: 12x20 glyphs
described as polygons on a floating-point grid, so they are rasterised
oversampled and come out with clean diagonals rather than staircases.
"""

import numpy as np

from gbcanvas import poly, rect, hard

# --------------------------------------------------------------- 5x7 pixels

SMALL = {c: g.strip('\n').split('\n') for c, g in {
    'A': """
.###.
#...#
#...#
#####
#...#
#...#
#...#""",
    'B': """
####.
#...#
#...#
####.
#...#
#...#
####.""",
    'C': """
.###.
#...#
#....
#....
#....
#...#
.###.""",
    'D': """
####.
#...#
#...#
#...#
#...#
#...#
####.""",
    'E': """
#####
#....
#....
####.
#....
#....
#####""",
    'F': """
#####
#....
#....
####.
#....
#....
#....""",
    'G': """
.###.
#...#
#....
#.###
#...#
#...#
.###.""",
    'H': """
#...#
#...#
#...#
#####
#...#
#...#
#...#""",
    'I': """
#####
..#..
..#..
..#..
..#..
..#..
#####""",
    'J': """
..###
...#.
...#.
...#.
...#.
#..#.
.##..""",
    'K': """
#...#
#..#.
#.#..
##...
#.#..
#..#.
#...#""",
    'L': """
#....
#....
#....
#....
#....
#....
#####""",
    'M': """
#...#
##.##
#.#.#
#.#.#
#...#
#...#
#...#""",
    'N': """
#...#
##..#
#.#.#
#..##
#...#
#...#
#...#""",
    'O': """
.###.
#...#
#...#
#...#
#...#
#...#
.###.""",
    'P': """
####.
#...#
#...#
####.
#....
#....
#....""",
    'Q': """
.###.
#...#
#...#
#...#
#.#.#
#..#.
.##.#""",
    'R': """
####.
#...#
#...#
####.
#.#..
#..#.
#...#""",
    'S': """
.####
#....
#....
.###.
....#
....#
####.""",
    'T': """
#####
..#..
..#..
..#..
..#..
..#..
..#..""",
    'U': """
#...#
#...#
#...#
#...#
#...#
#...#
.###.""",
    'V': """
#...#
#...#
#...#
#...#
#...#
.#.#.
..#..""",
    'W': """
#...#
#...#
#...#
#.#.#
#.#.#
##.##
#...#""",
    'X': """
#...#
#...#
.#.#.
..#..
.#.#.
#...#
#...#""",
    'Y': """
#...#
#...#
.#.#.
..#..
..#..
..#..
..#..""",
    'Z': """
#####
....#
...#.
..#..
.#...
#....
#####""",
    '0': """
.###.
#...#
#..##
#.#.#
##..#
#...#
.###.""",
    '1': """
..#..
.##..
..#..
..#..
..#..
..#..
.###.""",
    '2': """
.###.
#...#
....#
...#.
..#..
.#...
#####""",
    '3': """
####.
....#
....#
.###.
....#
....#
####.""",
    '4': """
...#.
..##.
.#.#.
#..#.
#####
...#.
...#.""",
    '5': """
#####
#....
####.
....#
....#
#...#
.###.""",
    '6': """
..##.
.#...
#....
####.
#...#
#...#
.###.""",
    '7': """
#####
....#
...#.
..#..
.#...
.#...
.#...""",
    '8': """
.###.
#...#
#...#
.###.
#...#
#...#
.###.""",
    '9': """
.###.
#...#
#...#
.####
....#
...#.
.##..""",
    '.': """
.....
.....
.....
.....
.....
.###.
.###.""",
    '-': """
.....
.....
.....
#####
.....
.....
.....""",
    '@': """
.###.
#...#
#.##.
#.#..
#.##.
#...#
.###.""",
    ' ': """
.....
.....
.....
.....
.....
.....
.....""",
}.items()}

SMALL_W, SMALL_H, SMALL_ADV = 5, 7, 6


def small_text(text, x, y, spacing=SMALL_ADV):
    """Rasterise 5x7 text at a pixel origin; returns a boolean mask."""
    from gbcanvas import H, W
    m = np.zeros((H, W), dtype=bool)
    for i, ch in enumerate(text.upper()):
        g = SMALL.get(ch, SMALL[' '])
        gx = x + i * spacing
        for row, bits in enumerate(g):
            for col, bit in enumerate(bits):
                if bit == '#':
                    py, px = y + row, gx + col
                    if 0 <= py < H and 0 <= px < W:
                        m[py, px] = True
    return m


def small_width(text, spacing=SMALL_ADV):
    return len(text) * spacing - (spacing - SMALL_W)


# ------------------------------------------------------- 12x20 display face
#
# Each glyph is (list of filled polygons, list of holes) on a 12 wide by
# 20 tall grid.  Stems are 3.5 units wide -- heavy enough to hold a
# two-tone fill and a black outline at this size.

_S = 4.0   # stem width
_B = 3.6   # horizontal bar thickness

def _r(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


LOGO = {
    'L': ([_r(0, 0, _S, 20), _r(0, 16.8, 11.6, 20)], []),
    'E': ([_r(0, 0, _S, 20), _r(0, 0, 11.6, _B),
           _r(0, 8.4, 9.6, 11.4), _r(0, 16.8, 11.6, 20)], []),
    'V': ([[(0, 0), (4.1, 0), (6.2, 14.0), (8.3, 0), (12, 0),
            (8.1, 20), (4.3, 20)]], []),
    'I': ([_r(4.0, 0, 8.0, 20), _r(0.8, 0, 11.2, _B),
           _r(0.8, 16.8, 11.2, 20)], []),
    'A': ([[(4.2, 0), (7.8, 0), (12, 20), (8.0, 20), (7.3, 15.4),
            (4.7, 15.4), (4.0, 20), (0, 20)]],
          [[(6.0, 5.4), (7.7, 13.4), (4.3, 13.4)]]),
    'T': ([_r(0, 0, 12, _B), _r(4.0, 0, 8.0, 20)], []),
    'H': ([_r(0, 0, _S, 20), _r(8.5, 0, 12, 20), _r(0, 8.4, 12, 11.4)], []),
    'N': ([[(0, 0), (3.9, 0), (8.2, 12.4), (8.2, 0), (12, 0), (12, 20),
            (8.1, 20), (3.8, 7.6), (3.8, 20), (0, 20)]], []),
}

LOGO_W, LOGO_H = 12, 20


def logo_text(text, x, y):
    """Rasterise display-face text; returns a boolean mask."""
    from gbcanvas import H, W
    acc = np.zeros((H, W), dtype=bool)
    for i, ch in enumerate(text.upper()):
        fills, holes = LOGO[ch]
        ox = x + i * (LOGO_W + 2)
        for f in fills:
            pts = [(px + ox, py + y) for px, py in f]
            hs = [[(hx + ox, hy + y) for hx, hy in h] for h in holes]
            acc |= hard(poly(pts, hs))
    return acc


def logo_width(text):
    return len(text) * (LOGO_W + 2) - 2
