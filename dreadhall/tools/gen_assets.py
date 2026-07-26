#!/usr/bin/env python3
"""
DREADHALL - asset generator.

Emits RGBDS .inc files: background tiles, sprite tiles, math lookup tables and
the level map. Everything the renderer needs is precomputed here so the Game
Boy only ever does adds, shifts and table lookups at run time.

Rendering model
---------------
The 3D view is 20 tiles wide x 14 tiles tall (160x112 px). One raycast column
per tile column. Because the horizon sits at y=56, which is a tile boundary,
the top and bottom edges of a wall column always land in different tiles, so a
wall column is always built from:

    [ceiling] [top cap] [solid]* [bottom cap] [floor]

That means a small static tile set covers every possible wall height.
"""

import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "gen")

# ---------------------------------------------------------------------------
# geometry / engine constants (kept in sync with the assembly via gen_consts)
# ---------------------------------------------------------------------------
VIEW_COLS   = 20          # ray columns == tile columns
VIEW_ROWS   = 14          # tile rows of 3D viewport
VIEW_H      = VIEW_ROWS * 8   # 112 px
HORIZON     = VIEW_H // 2     # 56 px  (tile boundary: row 7)
MAX_H2      = HORIZON         # max half-height of a wall column
FOV_DEG     = 60.0
PROJ        = (160 / 2) / __import__("math").tan(__import__("math").radians(FOV_DEG / 2))
MAX_DIST    = 16.0        # cells; distance tables cover [0,16)
NUM_MAT     = 6           # wall shading levels
MAP_W       = 32
MAP_H       = 32

import math

# ---------------------------------------------------------------------------
# tile helpers
# ---------------------------------------------------------------------------

def blank(w=8, h=8, c=0):
    return [[c] * w for _ in range(h)]


def encode_tile(px):
    """8x8 list of colour indices (0..3) -> 16 bytes of Game Boy 2bpp."""
    out = []
    for y in range(8):
        lo = hi = 0
        for x in range(8):
            c = px[y][x] & 3
            bit = 7 - x
            if c & 1:
                lo |= 1 << bit
            if c & 2:
                hi |= 1 << bit
        out.append(lo)
        out.append(hi)
    return out


def cut_tiles(img, w, h):
    """Cut a w*h pixel image into 8x8 tiles, row major."""
    tiles = []
    for ty in range(h // 8):
        for tx in range(w // 8):
            t = [[img[ty * 8 + y][tx * 8 + x] for x in range(8)] for y in range(8)]
            tiles.append(t)
    return tiles


def cut_tiles_obj(img, w, h):
    """Cut into 8x16 sprite tile-pairs, column major (OAM 8x16 order)."""
    tiles = []
    for tx in range(w // 8):
        for ty in range(h // 16):
            for half in range(2):
                t = [[img[ty * 16 + half * 8 + y][tx * 8 + x] for x in range(8)]
                     for y in range(8)]
                tiles.append(t)
    return tiles


# ---------------------------------------------------------------------------
# wall materials
# ---------------------------------------------------------------------------
# Six brightness levels from "right in front of you" to "swallowed by the dark".
# Each is a base colour plus an optional dither colour, and a mortar colour used
# for the brick joints and for the hard silhouette edge against ceiling/floor.
#   dither: None = solid, 'checker' = 50%, 'quarter' = 25%
MATERIALS = [
    # base, dither colour, dither kind, mortar
    (0, 0, None,      2),   # 0 nearest: lit white stone, dark joints
    (0, 1, 'checker', 2),   # 1
    (1, 1, None,      3),   # 2
    (1, 2, 'checker', 3),   # 3
    (2, 2, None,      3),   # 4
    (2, 3, 'checker', 3),   # 5 farthest: dissolving into the dark
]

CEIL_COLOR = 3


def dither_on(kind, x, y):
    if kind is None:
        return False
    if kind == 'checker':
        return (x + y) & 1 == 0
    if kind == 'quarter':
        return (x & 1) == 0 and (y & 1) == 0
    raise ValueError(kind)


def wall_pixel(m, x, y):
    """Brick texture for material m at tile-local (x,y). 8x4 bricks, running bond."""
    base, dcol, dkind, mortar = MATERIALS[m]
    # horizontal joints every 4 rows
    if y == 0 or y == 4:
        return mortar
    # vertical joints, offset by half a brick between courses
    if y < 4 and x == 0:
        return mortar
    if y >= 4 and x == 4:
        return mortar
    return dcol if dither_on(dkind, x, y) else base


def floor_pixel(x, y):
    # dark grey ground with a sparse darker speckle; no perspective, but a
    # noise-like pattern reads far better than a static grid when you move.
    return 3 if ((x & 1) == 0 and (y & 1) == 0) else 2


def build_wall_tiles():
    """Returns (tiles, index_of) for ceiling, floor and all material tiles."""
    tiles = []

    ceil = [[CEIL_COLOR] * 8 for _ in range(8)]
    tiles.append(ceil)                                    # index 0
    tiles.append([[floor_pixel(x, y) for x in range(8)] for y in range(8)])  # 1

    for m in range(NUM_MAT):
        mortar = MATERIALS[m][3]
        # +0 solid body
        tiles.append([[wall_pixel(m, x, y) for x in range(8)] for y in range(8)])
        # +1..+7 top cap: ceiling above row b, wall from row b down.
        for b in range(1, 8):
            t = blank()
            for y in range(8):
                for x in range(8):
                    if y < b:
                        t[y][x] = CEIL_COLOR
                    elif y == b:
                        t[y][x] = mortar          # hard top edge
                    else:
                        t[y][x] = wall_pixel(m, x, y)
            tiles.append(t)
        # +8..+14 bottom cap: wall down to row k-1, floor below.
        for k in range(1, 8):
            t = blank()
            for y in range(8):
                for x in range(8):
                    if y < k - 1:
                        t[y][x] = wall_pixel(m, x, y)
                    elif y == k - 1:
                        t[y][x] = mortar          # hard bottom edge
                    else:
                        t[y][x] = floor_pixel(x, y)
            tiles.append(t)
    return tiles


# ---------------------------------------------------------------------------
# 5x7 font in an 8x8 cell
# ---------------------------------------------------------------------------
FONT = {
    'A': ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    'B': ["11110", "10001", "11110", "10001", "10001", "10001", "11110"],
    'C': ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    'D': ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    'E': ["11111", "10000", "11110", "10000", "10000", "10000", "11111"],
    'F': ["11111", "10000", "11110", "10000", "10000", "10000", "10000"],
    'G': ["01110", "10001", "10000", "10111", "10001", "10001", "01111"],
    'H': ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    'I': ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    'J': ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    'K': ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    'L': ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    'M': ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    'N': ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    'O': ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    'P': ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    'Q': ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    'R': ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    'S': ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    'T': ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    'U': ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    'V': ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    'W': ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    'X': ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    'Y': ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    'Z': ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    '0': ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    '1': ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    '2': ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    '3': ["11111", "00010", "00100", "00010", "00001", "10001", "01110"],
    '4': ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    '5': ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    '6': ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    '7': ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    '8': ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    '9': ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
    ' ': ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    '.': ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    '-': ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    '!': ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
    ':': ["00000", "01100", "01100", "00000", "01100", "01100", "00000"],
    '/': ["00001", "00010", "00010", "00100", "01000", "01000", "10000"],
    '%': ["11001", "11010", "00010", "00100", "01000", "01011", "10011"],
    '*': ["00000", "10101", "01110", "11111", "01110", "10101", "00000"],
}

FONT_CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-!:/%*"


def font_tile(ch, fg=0, bg=3):
    """8x8 tile for a character, glyph shifted 1px right / 1px down."""
    t = [[bg] * 8 for _ in range(8)]
    rows = FONT.get(ch, FONT[' '])
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c == '1':
                t[y + 1][x + 1] = fg
    return t


def text_bitmap(s):
    """Render a string into a (len*8) x 8 bitmap of 0/1."""
    w = len(s) * 8
    img = [[0] * w for _ in range(8)]
    for i, ch in enumerate(s):
        rows = FONT.get(ch, FONT[' '])
        for y, row in enumerate(rows):
            for x, c in enumerate(row):
                if c == '1':
                    img[y + 1][i * 8 + x + 1] = 1
    return img, w


# ---------------------------------------------------------------------------
# title logo: bold 2x scaled text with an outline and drop shadow
# ---------------------------------------------------------------------------

def make_logo(text):
    src, sw = text_bitmap(text)
    # 2x scale + horizontal bolding
    w, h = sw * 2, 16
    big = [[0] * w for _ in range(h)]
    for y in range(8):
        for x in range(sw):
            if src[y][x]:
                for dy in range(2):
                    for dx in range(2):
                        big[y * 2 + dy][x * 2 + dx] = 1
    # pad for outline / shadow
    W, H = w + 8, h + 8
    img = [[0] * W for _ in range(H)]
    ox, oy = 3, 2

    def at(bx, by):
        return 0 <= bx < w and 0 <= by < h and big[by][bx]

    for y in range(H):
        for x in range(W):
            bx, by = x - ox, y - oy
            if at(bx, by):
                # body: light on top, mid lower down for a beveled look
                img[y][x] = 0 if by < h // 2 else 1
            elif at(bx - 2, by - 2):
                img[y][x] = 2        # drop shadow
            else:
                img[y][x] = 3        # black field
    return img, W, H


# ---------------------------------------------------------------------------
# sprite art
# ---------------------------------------------------------------------------

def art(rows, pal=None):
    """ASCII art -> colour grid. ' '=transparent 0, '.'=1, '+'=2, '#'=3."""
    pal = pal or {' ': 0, '.': 1, '+': 2, '#': 3}
    return [[pal[c] for c in row] for row in rows]


def make_gun():
    """First person blaster, 48x48, anchored to the bottom of the viewport.

    Drawn for OBP1: 1 = white, 2 = light grey, 3 = black, 0 = transparent.
    The weapon is kept white and the hands grey so the two read as separate
    objects rather than merging into one blob at Game Boy scale.
    """
    W, H = 48, 48
    img = [[0] * W for _ in range(H)]

    def rect(x0, y0, x1, y1, c):
        for y in range(max(0, y0), min(H, y1)):
            for x in range(max(0, x0), min(W, x1)):
                img[y][x] = c

    def outline(x0, y0, x1, y1, c):
        for x in range(max(0, x0), min(W, x1)):
            if 0 <= y0 < H: img[y0][x] = c
            if 0 <= y1 - 1 < H: img[y1 - 1][x] = c
        for y in range(max(0, y0), min(H, y1)):
            if 0 <= x0 < W: img[y][x0] = c
            if 0 <= x1 - 1 < W: img[y][x1 - 1] = c

    # Foreshortened: you are looking down the top of the weapon, so the body
    # dominates and the barrel is a short stub rather than a tall post.

    # ---- muzzle + barrel stub ----
    rect(17, 0, 31, 4, 1)
    outline(17, 0, 31, 4, 3)
    rect(20, 1, 28, 3, 3)           # bore
    rect(15, 3, 33, 14, 1)
    outline(15, 3, 33, 14, 3)
    rect(27, 5, 32, 13, 2)          # shaded right flank
    for y in (6, 9, 12):            # cooling ribs
        rect(16, y, 32, y + 1, 3)
        rect(18, y, 25, y + 1, 2)

    # ---- receiver: the big shape that reads at a glance ----
    rect(4, 12, 44, 33, 1)
    outline(4, 12, 44, 33, 3)
    rect(32, 14, 43, 32, 2)         # shaded right half
    rect(7, 15, 26, 20, 3)          # ejection slot
    rect(9, 16, 24, 19, 2)
    rect(7, 24, 41, 32, 3)          # recessed underside
    rect(9, 25, 24, 30, 1)          # charge cell glow
    rect(30, 25, 39, 30, 2)
    rect(20, 10, 28, 13, 2)         # top sight
    outline(20, 10, 28, 13, 3)

    # ---- both hands, darker so the weapon reads on top of them ----
    rect(0, 31, 48, 48, 2)
    outline(0, 31, 48, 48, 3)
    for x in (5, 11, 17, 31, 37, 43):    # knuckle creases
        rect(x, 35, x + 1, 48, 3)
    rect(2, 33, 5, 38, 1)                # thumb highlights
    rect(44, 33, 47, 38, 1)
    rect(22, 35, 26, 48, 3)              # gap between the hands
    return img, W, H


def make_flash():
    """Muzzle flash, 24x16, drawn above the barrel when you fire."""
    W, H = 24, 16
    img = [[0] * W for _ in range(H)]
    cx, cy = 12, 10
    for y in range(H):
        for x in range(W):
            dx, dy = (x - cx) / 1.0, (y - cy) / 0.8
            d = math.hypot(dx, dy)
            spike = 1.0 + 0.55 * math.cos(4 * math.atan2(dy, dx if dx else 0.01))
            r = d / max(spike, 0.2)
            if r < 4.5:
                img[y][x] = 1          # white hot core
            elif r < 7.0:
                img[y][x] = 2
            elif r < 8.0:
                img[y][x] = 3          # hard rim
    return img, W, H


def make_enemy(pose):
    """Hulking 32x32 brute. pose 0 = advancing, 1 = hit/dying."""
    W, H = 32, 32
    img = [[0] * W for _ in range(H)]

    def rect(x0, y0, x1, y1, c):
        for y in range(max(0, y0), min(H, y1)):
            for x in range(max(0, x0), min(W, x1)):
                img[y][x] = c

    def ellipse(cx, cy, rx, ry, c):
        for y in range(H):
            for x in range(W):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                    img[y][x] = c

    if pose == 0:
        # legs
        rect(9, 24, 14, 32, 3);  rect(10, 25, 13, 31, 2)
        rect(18, 24, 23, 32, 3); rect(19, 25, 22, 31, 2)
        # torso
        ellipse(16, 18, 9, 8, 3)
        ellipse(16, 18, 7, 6, 2)
        rect(13, 14, 19, 22, 1)          # chest plate
        rect(14, 16, 18, 20, 2)
        # arms held wide
        rect(4, 13, 9, 25, 3);  rect(5, 14, 8, 24, 2)
        rect(23, 13, 28, 25, 3); rect(24, 14, 27, 24, 2)
        rect(3, 22, 9, 27, 3);  rect(23, 22, 29, 27, 3)   # fists
        # head + horns
        ellipse(16, 7, 6, 6, 3)
        ellipse(16, 7, 4, 4, 2)
        rect(8, 1, 11, 6, 3); rect(21, 1, 24, 6, 3)       # horns
        rect(12, 6, 15, 8, 1); rect(17, 6, 20, 8, 1)      # glowing eyes
        rect(13, 10, 19, 12, 3)                            # maw
        for x in range(13, 19, 2):
            rect(x, 10, x + 1, 12, 1)                      # teeth
    else:
        # recoiling / collapsing pose
        rect(8, 26, 14, 32, 3);  rect(18, 26, 24, 32, 3)
        ellipse(16, 21, 10, 7, 3)
        ellipse(16, 21, 8, 5, 2)
        rect(2, 18, 9, 23, 3);  rect(23, 18, 30, 23, 3)   # arms flung out
        ellipse(16, 11, 6, 6, 3)
        ellipse(16, 11, 4, 4, 2)
        rect(8, 5, 11, 10, 3); rect(21, 5, 24, 10, 3)
        rect(12, 10, 15, 12, 3); rect(17, 10, 20, 12, 3)  # eyes shut
        rect(12, 14, 20, 17, 1)                            # screaming mouth
    return img, W, H


def downscale(img, sw, sh, dw, dh):
    """Box downscale that keeps the silhouette: transparent only wins on majority."""
    out = [[0] * dw for _ in range(dh)]
    for y in range(dh):
        for x in range(dw):
            counts = {}
            n = 0
            for sy in range(y * sh // dh, max(y * sh // dh + 1, (y + 1) * sh // dh)):
                for sx in range(x * sw // dw, max(x * sw // dw + 1, (x + 1) * sw // dw)):
                    c = img[sy][sx]
                    counts[c] = counts.get(c, 0) + 1
                    n += 1
            opaque = {c: v for c, v in counts.items() if c != 0}
            if not opaque or counts.get(0, 0) * 2 > n:
                out[y][x] = 0
            else:
                out[y][x] = max(opaque.items(), key=lambda kv: kv[1])[0]
    return out


def pad_to(img, sw, sh, dw, dh):
    """Centre a small image inside a larger transparent canvas (top aligned)."""
    out = [[0] * dw for _ in range(dh)]
    ox = (dw - sw) // 2
    for y in range(sh):
        for x in range(sw):
            out[y][ox + x] = img[y][x]
    return out


def make_crosshair():
    """Thin 8x8 reticle for OBP1: black arms with a white edge either side, so
    it stays legible against both a lit wall and the black ceiling."""
    t = [[0] * 8 for _ in range(8)]
    for y in (0, 1, 6, 7):          # vertical arms
        t[y][3] = 3
        t[y][2] = 1
        t[y][4] = 1
    for x in (0, 1, 6, 7):          # horizontal arms
        t[3][x] = 3
        t[2][x] = 1
        t[4][x] = 1
    return t


# ---------------------------------------------------------------------------
# level
# ---------------------------------------------------------------------------
# The level is generated rather than hand drawn: a perfect maze is carved with
# a recursive backtracker (which guarantees every cell is connected), then extra
# walls are knocked through to create loops and a handful of open rooms, which
# give the raycaster something better to show than endless 1-wide corridors.
# The seed is fixed so builds are reproducible.
LEVEL_SEED = 20260726


def generate_level(seed=LEVEL_SEED):
    import random
    rnd = random.Random(seed)
    W, H = MAP_W, MAP_H
    g = [[1] * W for _ in range(H)]

    # ---- perfect maze over the odd-numbered cells ----
    stack = [(1, 1)]
    g[1][1] = 0
    while stack:
        cx, cy = stack[-1]
        opts = []
        for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
            nx, ny = cx + dx, cy + dy
            if 1 <= nx <= W - 2 and 1 <= ny <= H - 2 and g[ny][nx] == 1:
                opts.append((nx, ny, dx, dy))
        if not opts:
            stack.pop()
            continue
        nx, ny, dx, dy = rnd.choice(opts)
        g[cy + dy // 2][cx + dx // 2] = 0
        g[ny][nx] = 0
        stack.append((nx, ny))

    # ---- braid: remove some dead ends so the map loops back on itself ----
    for _ in range(90):
        x = rnd.randrange(2, W - 2)
        y = rnd.randrange(2, H - 2)
        if g[y][x] != 1:
            continue
        horiz = g[y][x - 1] == 0 and g[y][x + 1] == 0
        vert = g[y - 1][x] == 0 and g[y + 1][x] == 0
        if horiz != vert:
            g[y][x] = 0

    # ---- open rooms ----
    rooms = []
    tries = 0
    while len(rooms) < 5 and tries < 400:
        tries += 1
        rw = rnd.randrange(4, 8)
        rh = rnd.randrange(4, 8)
        rx = rnd.randrange(2, W - rw - 2)
        ry = rnd.randrange(2, H - rh - 2)
        # proper AABB overlap test with a margin, so rooms stay distinct
        # instead of merging into one giant hall
        if any(rx < ox + ow + 3 and ox < rx + rw + 3 and
               ry < oy + oh + 3 and oy < ry + rh + 3
               for ox, oy, ow, oh in rooms):
            continue
        rooms.append((rx, ry, rw, rh))
        for y in range(ry, ry + rh):
            for x in range(rx, rx + rw):
                g[y][x] = 0

    # walls facing a room are metal, so rooms read differently from corridors
    for (rx, ry, rw, rh) in rooms:
        for x in range(rx - 1, rx + rw + 1):
            for y in (ry - 1, ry + rh):
                if 0 < x < W - 1 and 0 < y < H - 1 and g[y][x] == 1:
                    g[y][x] = 2
        for y in range(ry - 1, ry + rh + 1):
            for x in (rx - 1, rx + rw):
                if 0 < x < W - 1 and 0 < y < H - 1 and g[y][x] == 1:
                    g[y][x] = 2

    # ---- solid border ----
    for i in range(W):
        g[0][i] = g[H - 1][i] = 1
        g[i][0] = g[i][W - 1] = 1

    open_cells = [(x, y) for y in range(H) for x in range(W) if g[y][x] == 0]

    def bfs(src):
        from collections import deque
        dist = {src: 0}
        q = deque([src])
        while q:
            x, y = q.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (x + dx, y + dy)
                if (0 <= n[0] < W and 0 <= n[1] < H and g[n[1]][n[0]] == 0
                        and n not in dist):
                    dist[n] = dist[(x, y)] + 1
                    q.append(n)
        return dist

    # start in a corner region, exit at the furthest reachable cell
    start = min(open_cells, key=lambda c: c[0] + c[1])
    dist = bfs(start)
    assert len(dist) == len(open_cells), "maze is not fully connected"
    exit_pos = max(dist, key=lambda c: dist[c])

    # ---- enemies: spread out, never too close to the spawn ----
    ordered = sorted(dist, key=lambda c: -dist[c])
    enemies = []
    for c in ordered:
        if dist[c] < 14:
            continue
        if all(abs(c[0] - e[0]) + abs(c[1] - e[1]) > 7 for e in enemies) and c != exit_pos:
            enemies.append(c)
        if len(enemies) == 6:
            break

    # ---- pickups: mid-distance, away from enemies ----
    pickups = []
    for c in sorted(dist, key=lambda c: dist[c]):
        if not 8 <= dist[c] <= 40 or c == exit_pos or c == start:
            continue
        if all(abs(c[0] - p[0]) + abs(c[1] - p[1]) > 9 for p, _k in pickups) and \
           all(abs(c[0] - e[0]) + abs(c[1] - e[1]) > 2 for e in enemies):
            pickups.append((c, len(pickups) % 2))
        if len(pickups) == 4:
            break

    # face the spawn down whichever direction has the longest clear run
    best_ang, best_run = 0, -1
    for ang, (dx, dy) in ((0, (1, 0)), (64, (0, 1)), (128, (-1, 0)), (192, (0, -1))):
        run, x, y = 0, start[0], start[1]
        while True:
            x, y = x + dx, y + dy
            if not (0 <= x < W and 0 <= y < H) or g[y][x] != 0:
                break
            run += 1
        if run > best_run:
            best_ang, best_run = ang, run

    return g, start, enemies, [(c[0], c[1], k) for c, k in pickups], exit_pos, best_ang


def parse_level():
    grid, start, enemies, pickups, exit_pos, start_ang = generate_level()

    # everything the player has to reach must actually be reachable
    from collections import deque
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if (0 <= n[0] < MAP_W and 0 <= n[1] < MAP_H
                    and grid[n[1]][n[0]] == 0 and n not in seen):
                seen.add(n)
                q.append(n)
    assert exit_pos in seen, "exit is walled off"
    for e in enemies:
        assert e in seen, "enemy at %s is walled off" % (e,)
    for (px, py, _k) in pickups:
        assert (px, py) in seen, "pickup at %d,%d is walled off" % (px, py)
    return grid, start, enemies, pickups, exit_pos, start_ang


def level_ascii(grid, start, enemies, pickups, exit_pos):
    ch = {0: ".", 1: "#", 2: "="}
    rows = [[ch[c] for c in row] for row in grid]
    for (x, y) in enemies:
        rows[y][x] = "e"
    for (x, y, k) in pickups:
        rows[y][x] = "a" if k == 0 else "h"
    rows[start[1]][start[0]] = "S"
    rows[exit_pos[1]][exit_pos[0]] = "X"
    return "\n".join("".join(r) for r in rows)


# ---------------------------------------------------------------------------
# emit helpers
# ---------------------------------------------------------------------------

def fmt_db(vals, per=16):
    lines = []
    for i in range(0, len(vals), per):
        lines.append("    db " + ",".join("$%02X" % (v & 0xFF) for v in vals[i:i + per]))
    return "\n".join(lines)


def fmt_dw(vals, per=8):
    lines = []
    for i in range(0, len(vals), per):
        lines.append("    dw " + ",".join("$%04X" % (v & 0xFFFF) for v in vals[i:i + per]))
    return "\n".join(lines)


def emit_tiles(name, tiles):
    body = []
    for t in tiles:
        body.append("    db " + ",".join("$%02X" % b for b in encode_tile(t)))
    return "%s::\n%s\n%s_END::\n" % (name, "\n".join(body), name)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUT, exist_ok=True)

    # ---------------- background tiles ----------------
    bg = build_wall_tiles()
    T_CEIL, T_FLOOR = 0, 1
    MAT_BASE = 2                       # material m -> 2 + 15*m
    idx = 2 + NUM_MAT * 15
    assert len(bg) == idx

    T_FONT = idx
    for ch in FONT_CHARS:
        bg.append(font_tile(ch))
    idx += len(FONT_CHARS)

    # HUD chrome ------------------------------------------------------------
    T_HUD = idx
    # 0: solid black panel
    bg.append([[3] * 8 for _ in range(8)])
    # 1: top border (light rule over black)
    t = [[3] * 8 for _ in range(8)]
    for x in range(8):
        t[0][x] = 1
        t[1][x] = 2
    bg.append(t)
    # 2..6: health bar segment at five fill levels (4 units per tile,
    # 8 tiles across = the 32 units of a full health bar)
    for fillw in (0, 2, 4, 6, 8):
        t = [[3] * 8 for _ in range(8)]
        for y in range(2, 6):
            for x in range(8):
                if x < fillw:
                    t[y][x] = 0 if y < 4 else 1
                else:
                    t[y][x] = 2
        bg.append(t)
    # 7: bar end cap left, 8: right
    for side in (0, 1):
        t = [[3] * 8 for _ in range(8)]
        for y in range(1, 7):
            t[y][7 if side == 0 else 0] = 2
        for x in range(8):
            t[1][x] = 2
            t[6][x] = 2
        bg.append(t)
    idx += 9

    # title logo ------------------------------------------------------------
    logo, LW, LH = make_logo("DREADHALL")
    LW8 = (LW + 7) // 8 * 8
    LH8 = (LH + 7) // 8 * 8
    padded = [[3] * LW8 for _ in range(LH8)]
    for y in range(LH):
        for x in range(LW):
            padded[y][x] = logo[y][x]
    T_LOGO = idx
    logo_tiles = cut_tiles(padded, LW8, LH8)
    bg.extend(logo_tiles)
    idx += len(logo_tiles)
    LOGO_TW, LOGO_TH = LW8 // 8, LH8 // 8

    assert idx <= 256, "too many BG tiles: %d" % idx

    # ---------------- sprite tiles ----------------
    obj = []
    gun, gw, gh = make_gun()
    O_GUN = 0
    obj.extend(cut_tiles_obj(gun, gw, gh))          # 6 cols x 2 rows -> 12 sprites
    GUN_COLS, GUN_ROWS = gw // 8, gh // 16

    O_FLASH = len(obj) // 2
    flash, fw, fh = make_flash()
    obj.extend(cut_tiles_obj(flash, fw, fh))
    FLASH_COLS, FLASH_ROWS = fw // 8, fh // 16

    O_CROSS = len(obj) // 2
    ch_t = make_crosshair()
    obj.append(ch_t)
    obj.append(blank())

    # enemy: four sizes for pose 0, two for pose 1
    enemy_sets = []                                  # (tile index, cols, rows_px)
    ENEMY_SIZES = [(32, 32), (24, 32), (16, 16), (8, 16)]
    for pose in (0, 1):
        src, sw, sh = make_enemy(pose)
        sizes = ENEMY_SIZES if pose == 0 else [(32, 32), (16, 16)]
        entry = []
        for (w, h) in sizes:
            if w == 32 and h == 32:
                small = src
                cw, chh = 32, 32
            elif w == 24:
                small = downscale(src, sw, sh, 24, 24)
                small = pad_to(small, 24, 24, 24, 32)
                cw, chh = 24, 32
            elif w == 16:
                small = downscale(src, sw, sh, 16, 16)
                cw, chh = 16, 16
            else:
                small = downscale(src, sw, sh, 8, 8)
                small = pad_to(small, 8, 8, 8, 16)
                cw, chh = 8, 16
            entry.append((len(obj) // 2, cw // 8, chh))
            obj.extend(cut_tiles_obj(small, cw, chh))
        enemy_sets.append(entry)

    # pickups: a small crate (ammo) and a medkit
    O_PICKUP = len(obj) // 2
    pick = [[0] * 16 for _ in range(16)]
    for y in range(3, 14):
        for x in range(2, 14):
            pick[y][x] = 2
    for x in range(2, 14):
        pick[3][x] = 3; pick[13][x] = 3
    for y in range(3, 14):
        pick[y][2] = 3; pick[y][13] = 3
    for y in range(6, 11):
        for x in range(5, 11):
            pick[y][x] = 3
    for y in range(7, 10):
        for x in range(6, 10):
            pick[y][x] = 1
    obj.extend(cut_tiles_obj(pick, 16, 16))

    med = [[0] * 16 for _ in range(16)]
    for y in range(3, 14):
        for x in range(2, 14):
            med[y][x] = 1
    for x in range(2, 14):
        med[3][x] = 3; med[13][x] = 3
    for y in range(3, 14):
        med[y][2] = 3; med[y][13] = 3
    for y in range(6, 11):
        for x in range(4, 12):
            med[y][x] = 3
    for y in range(5, 12):
        for x in range(6, 10):
            med[y][x] = 3
    O_MED = O_PICKUP + 2
    obj.extend(cut_tiles_obj(med, 16, 16))

    assert len(obj) <= 128, "too many OBJ tiles: %d" % len(obj)

    # ---------------- math tables ----------------
    # sin, extended by 64 entries so cos(a) == sinx[a+64]
    # scaled by 255 (not 256) so |sin| always fits in a byte: the multiply
    # helper takes an 8-bit magnitude, which keeps the hot path cheap.
    sinx = [max(-255, min(255, int(round(math.sin(i * 2 * math.pi / 256) * 255))))
            for i in range(256 + 64)]
    # 1/|sin| in 8.8, clamped; 1/|cos(a)| == recip[a+64]
    RECIP_CLAMP = 0x4000
    recips = []
    for i in range(256 + 64):
        s = abs(math.sin(i * 2 * math.pi / 256))
        v = RECIP_CLAMP if s < 1e-6 else min(RECIP_CLAMP, int(round(256.0 / s)))
        recips.append(v)

    # per-column ray angle offsets and fisheye correction
    col_off = []
    col_cos = []
    for c in range(VIEW_COLS):
        camx = (2.0 * (c + 0.5) / VIEW_COLS) - 1.0
        ang = math.atan(camx * math.tan(math.radians(FOV_DEG / 2)))
        col_off.append(int(round(ang * 256 / (2 * math.pi))) & 0xFF)
        col_cos.append(math.cos(ang))

    # 10 unique height tables (columns are symmetric about the screen centre)
    NUM_HTAB = VIEW_COLS // 2
    htabs = []
    for k in range(NUM_HTAB):
        tab = []
        for i in range(256):
            d = i / 16.0
            if d <= 0.0:
                h2 = MAX_H2
            else:
                h2 = (PROJ / 2.0) / (d * col_cos[k])
            tab.append(max(1, min(MAX_H2, int(round(h2)))))
        htabs.append(tab)
    col_tab = [min(c, VIEW_COLS - 1 - c) for c in range(VIEW_COLS)]

    # 1/d in 8.8 for billboard projection
    recip_d = []
    for i in range(256):
        d = i / 16.0
        recip_d.append(0x1000 if d <= 0 else min(0x1000, int(round(256.0 / d))))

    # distance -> shade level (material index), before the wall-side bump
    shade = []
    for i in range(256):
        d = i / 16.0
        if   d < 1.0:  s = 0
        elif d < 1.75: s = 1
        elif d < 2.75: s = 2
        elif d < 4.0:  s = 3
        elif d < 6.0:  s = 4
        else:          s = 5
        shade.append(s)

    # ---------------- level ----------------
    grid, start, enemies, pickups, exit_pos, start_ang = parse_level()
    flat = [grid[y][x] for y in range(MAP_H) for x in range(MAP_W)]

    # ---------------- write files ----------------
    with open(os.path.join(OUT, "consts.inc"), "w") as f:
        f.write("; generated by tools/gen_assets.py -- do not edit\n")
        f.write("IF !DEF(GEN_CONSTS_INC)\nDEF GEN_CONSTS_INC EQU 1\n\n")
        for k, v in [
            ("VIEW_COLS", VIEW_COLS), ("VIEW_ROWS", VIEW_ROWS),
            ("VIEW_H", VIEW_H), ("HORIZON", HORIZON), ("MAX_H2", MAX_H2),
            ("NUM_MAT", NUM_MAT), ("MAP_W", MAP_W), ("MAP_H", MAP_H),
            ("T_CEIL", T_CEIL), ("T_FLOOR", T_FLOOR), ("MAT_BASE", MAT_BASE),
            ("MAT_STRIDE", 15),
            ("T_FONT", T_FONT), ("T_HUD", T_HUD),
            ("T_HUD_PANEL", T_HUD + 0), ("T_HUD_TOP", T_HUD + 1),
            ("T_BAR0", T_HUD + 2), ("T_BARFULL", T_HUD + 6),
            ("T_BARL", T_HUD + 7), ("T_BARR", T_HUD + 8),
            ("T_DIGIT0", T_FONT + 27),
            ("T_LOGO", T_LOGO), ("LOGO_TW", LOGO_TW), ("LOGO_TH", LOGO_TH),
            ("BG_TILE_COUNT", idx),
            ("O_GUN", O_GUN), ("GUN_COLS", GUN_COLS), ("GUN_ROWS", GUN_ROWS),
            ("O_FLASH", O_FLASH), ("FLASH_COLS", FLASH_COLS),
            ("O_CROSS", O_CROSS),
            ("O_PICKUP", O_PICKUP), ("O_MED", O_MED),
            ("OBJ_TILE_COUNT", len(obj)),
            ("NUM_ENEMY", len(enemies)), ("NUM_PICKUP", len(pickups)),
            ("START_X", start[0]), ("START_Y", start[1]),
            ("EXIT_X", exit_pos[0]), ("EXIT_Y", exit_pos[1]),
            ("START_ANG", start_ang),
            ("RECIP_CLAMP", RECIP_CLAMP),
        ]:
            f.write("DEF %-16s EQU %d\n" % (k, v))
        f.write("\n; enemy billboard sets: tile, cols, height px\n")
        for pose, entry in enumerate(enemy_sets):
            for si, (ti, cols, hpx) in enumerate(entry):
                f.write("DEF E%d_S%d_TILE EQU %d\n" % (pose, si, ti * 2))
                f.write("DEF E%d_S%d_COLS EQU %d\n" % (pose, si, cols))
                f.write("DEF E%d_S%d_H    EQU %d\n" % (pose, si, hpx))
        f.write("\n; charmap: `db \"TEXT\"` emits font tile indices directly\n")
        for i, ch in enumerate(FONT_CHARS):
            f.write('CHARMAP "%s", T_FONT+%d\n' % (ch, i))
        f.write("\nENDC\n")

    with open(os.path.join(OUT, "tiles.inc"), "w") as f:
        f.write("; generated by tools/gen_assets.py\n")
        f.write(emit_tiles("BgTiles", bg))
        f.write("\n")
        f.write(emit_tiles("ObjTiles", obj))

    with open(os.path.join(OUT, "tables.inc"), "w") as f:
        f.write("; generated by tools/gen_assets.py\n")
        f.write("SinTab::\n%s\n\n" % fmt_dw(sinx))
        f.write("RecipTab::\n%s\n\n" % fmt_dw(recips))
        f.write("ColAngle::\n%s\n\n" % fmt_db(col_off))
        f.write("ColTab::\n%s\n\n" % fmt_db(col_tab))
        f.write("RecipDist::\n%s\n\n" % fmt_dw(recip_d))

    # ShadeTab and HeightTabs are indexed as base_high:index, so each needs to
    # start on its own 256 byte boundary -- hence separate files, placed in
    # separate ALIGN[8] sections by main.asm.
    with open(os.path.join(OUT, "shade.inc"), "w") as f:
        f.write("; generated by tools/gen_assets.py\n")
        f.write("ShadeTab::\n%s\n" % fmt_db(shade))

    with open(os.path.join(OUT, "height.inc"), "w") as f:
        f.write("; generated by tools/gen_assets.py\n")
        f.write("HeightTabs::\n")
        for k in range(NUM_HTAB):
            f.write("; column pair %d\n%s\n" % (k, fmt_db(htabs[k])))

    with open(os.path.join(OUT, "map.inc"), "w") as f:
        f.write("; generated by tools/gen_assets.py\n")
        f.write("LevelMap::\n%s\n\n" % fmt_db(flat, 32))
        f.write("EnemySpawns::\n")
        for (x, y) in enemies:
            f.write("    db %d,%d\n" % (x, y))
        f.write("\nPickupSpawns::\n")
        for (x, y, kind) in pickups:
            f.write("    db %d,%d,%d\n" % (x, y, kind))
        f.write("\n")

    print(level_ascii(grid, start, enemies, pickups, exit_pos))
    print("BG tiles      : %d / 256" % idx)
    print("OBJ tiles     : %d / 128" % len(obj))
    print("logo          : %dx%d tiles" % (LOGO_TW, LOGO_TH))
    print("enemies       : %d   pickups: %d" % (len(enemies), len(pickups)))
    print("proj const    : %.2f  (h2 = %.1f/d)" % (PROJ, PROJ / 2))
    print("tables bytes  : %d" % (len(sinx) * 2 + len(recips) * 2 + 256 * NUM_HTAB
                                  + len(recip_d) * 2 + 256 + VIEW_COLS * 2))


if __name__ == "__main__":
    main()
