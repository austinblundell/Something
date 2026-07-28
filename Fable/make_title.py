#!/usr/bin/env python3
"""FABLE — Game Boy title screen generator.

Renders a 160x144 title screen using only the four original DMG green
shades. Every element is drawn procedurally: Bayer-dithered sky, moon,
dragon silhouette, castle on a crag, moonlit lake, beveled logo.

Outputs:
  title_screen.png     160x144, exact 4-color DMG palette
  title_screen_4x.png  640x576 nearest-neighbor preview
"""

import os
from PIL import Image

W, H = 160, 144
HORIZON = 97

# Original DMG palette, darkest -> lightest
PAL = [
    (15, 56, 15),     # 0 darkest
    (48, 98, 48),     # 1 dark
    (139, 172, 15),   # 2 light
    (155, 188, 15),   # 3 lightest
]

fb = [[0] * W for _ in range(H)]

BAYER = [
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
]


def hashn(*args):
    h = 2166136261
    for a in args:
        h = ((h ^ (a & 0xFFFF)) * 16777619) & 0xFFFFFFFF
    return h


def px(x, y, c):
    if 0 <= x < W and 0 <= y < H:
        fb[y][x] = c


def get(x, y):
    if 0 <= x < W and 0 <= y < H:
        return fb[y][x]
    return 0


def dith(x, y, a, b, t):
    """Shade a or b chosen by 4x4 Bayer threshold; t = amount of b."""
    return b if t * 16 > BAYER[y % 4][x % 4] else a


def grad(x, y, v):
    """Continuous shade value v in [0,3] -> dithered index."""
    v = max(0.0, min(3.0, v))
    base = int(v)
    if base >= 3:
        return 3
    return dith(x, y, base, base + 1, v - base)


def hline(x0, x1, y, c):
    for x in range(x0, x1 + 1):
        px(x, y, c)


def vline(x, y0, y1, c):
    for y in range(y0, y1 + 1):
        px(x, y, c)


def disc(cx, cy, r, c):
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r + r * 0.6:
                px(x, y, c)


def blit(art, ox, oy, cmap):
    for j, row in enumerate(art):
        for i, ch in enumerate(row):
            if ch in cmap:
                px(ox + i, oy + j, cmap[ch])


def skyline(peaks):
    """Piecewise-linear skyline over full width from (x, y) control points."""
    top = [H] * W
    for (x0, y0), (x1, y1) in zip(peaks, peaks[1:]):
        for x in range(x0, x1 + 1):
            t = 0 if x1 == x0 else (x - x0) / (x1 - x0)
            y = round(y0 + (y1 - y0) * t)
            if 0 <= x < W:
                top[x] = min(top[x], y)
    return top


# ----------------------------------------------------------------------
# SKY — smooth gradient: near-black top, pale glow at the horizon
# ----------------------------------------------------------------------
for y in range(HORIZON):
    t = y / (HORIZON - 1)
    v = 0.12 + 2.35 * (t ** 1.55)          # 0.1 .. ~2.5
    for x in range(W):
        px(x, y, grad(x, y, v))

# ----------------------------------------------------------------------
# STARS — denser up top where the sky is dark
# ----------------------------------------------------------------------
for i in range(140):
    sx = hashn(i, 11) % W
    sy = hashn(i, 37) % (HORIZON - 30)
    if hashn(i, 53) % 100 < (70 if sy < 25 else 30):
        big = hashn(i, 71) % 7 == 0
        px(sx, sy, 3 if hashn(i, 5) % 3 else 2)
        if big and sy < 30:
            px(sx - 1, sy, 2)
            px(sx + 1, sy, 2)
            px(sx, sy - 1, 2)
            px(sx, sy + 1, 2)

# ----------------------------------------------------------------------
# MOON — big, cratered, upper right
# ----------------------------------------------------------------------
MX, MY, MR = 131, 30, 16
disc(MX, MY, MR + 1, 2)                    # halo ring reads as glow
disc(MX, MY, MR, 3)
for y in range(MY - MR, MY + MR + 1):      # soft shaded rim, lower-left
    for x in range(MX - MR, MX + MR + 1):
        d2 = (x - MX) ** 2 + (y - MY) ** 2
        if d2 <= MR * MR + MR * 0.6 and d2 > (MR - 2.4) ** 2:
            if (-(x - MX) + (y - MY)) > 3:
                px(x, y, 2)
disc(MX - 6, MY - 5, 3, 2)                 # craters
disc(MX + 5, MY + 3, 2, 2)
disc(MX - 3, MY + 8, 2, 2)
disc(MX + 8, MY - 7, 1, 2)
px(MX + 2, MY - 3, 2)
px(MX - 9, MY + 3, 2)

# ----------------------------------------------------------------------
# DRAGON — winged silhouette framed inside the moon disc
# ----------------------------------------------------------------------
DRAGON = [
    "    ##         ##       ",
    "    ###       ###       ",
    "    ####     ####       ",
    "    #####   #####       ",
    "   #######.#######      ",
    "  #################   ##",
    " ###  ##########  ######",
    "##     ########      ## ",
    "        ##   ###        ",
    "       ##     ##        ",
    "      #        ##       ",
]
blit(DRAGON, MX - 12, MY - 7, {"#": 0, ".": 0})

# ----------------------------------------------------------------------
# FAR MOUNTAINS — solid dark-mid silhouette, moonlit rims
# ----------------------------------------------------------------------
far = skyline([(0, 76), (14, 62), (30, 74), (44, 56), (60, 72), (74, 64),
               (88, 74), (102, 60), (116, 71), (130, 58), (144, 70),
               (152, 64), (159, 72)])
for x in range(W):
    for y in range(far[x], HORIZON):
        d = y - far[x]
        if d == 0:
            px(x, y, 2)                    # moonlit rim
        else:
            px(x, y, dith(x, y, 1, 0, min(0.55, d * 0.05)))

# ----------------------------------------------------------------------
# NEAR CRAGS + the castle crag — darkest silhouette
# ----------------------------------------------------------------------
near = skyline([(0, 94), (10, 85), (22, 91), (32, 82), (44, 92), (114, 92),
                (128, 83), (142, 90), (159, 86)])
crag = skyline([(50, HORIZON), (58, 90), (66, 86), (74, 84), (86, 84),
                (94, 86), (102, 90), (110, HORIZON)])
for x in range(W):
    top = min(near[x], crag[x])
    for y in range(top, HORIZON):
        c = 0
        if y == top and get(x, y - 1) in (2, 3):
            c = 1                          # faint rim where sky is bright
        px(x, y, c)

# ----------------------------------------------------------------------
# CASTLE — built programmatically: textured walls so it reads against
# the dark crag, crenellated towers, spires, lit windows, glowing gate
# ----------------------------------------------------------------------
def wall(x, y):
    px(x, y, dith(x, y, 0, 1, 0.30))


def window(cx, y):
    px(cx, y, 3)
    px(cx, y + 1, 3)
    px(cx, y - 1, 2)


def spire(cx, tip_y, half):
    for j in range(half + 2):              # pointed roof, solid dark
        hw = min(half, round(j * (half / (half + 1.0))))
        hline(cx - hw, cx + hw, tip_y + j, 0)
    vline(cx, tip_y - 4, tip_y - 1, 0)     # mast
    px(cx + 1, tip_y - 4, 2)               # pennant
    px(cx + 2, tip_y - 4, 2)
    px(cx + 1, tip_y - 3, 2)


def tower(cx, half, top, base, spired=True, windows=(6, 13)):
    for x in range(cx - half - 1, cx + half + 2):  # crenellations
        if (x - cx + half) % 2 == 0:
            vline(x, top - 2, top, 0)
        else:
            px(x, top, 0)
    for y in range(top + 1, base + 1):     # body
        for x in range(cx - half, cx + half + 1):
            if x == cx - half or x == cx + half:
                px(x, y, 0)
            else:
                wall(x, y)
    for dy in windows:
        window(cx, top + dy)
    if spired:
        spire(cx, top - half - 4, half)


def curtain(x0, x1, top, base):
    for x in range(x0, x1 + 1):            # crenellated top
        if (x - x0) % 2 == 0:
            px(x, top - 1, 0)
        px(x, top, 0)
    for y in range(top + 1, base + 1):
        for x in range(x0, x1 + 1):
            wall(x, y)


tower(80, 5, 56, 96, spired=False, windows=(5, 11, 17))   # central keep
spire(80, 45, 6)                                          # tall keep roof
vline(80, 52, 55, 0)
tower(66, 3, 66, 96, windows=(5, 12))                     # left tower
tower(94, 3, 66, 96, windows=(5, 12))                     # right tower
curtain(69, 77, 80, 96)                                   # walls to keep
curtain(83, 91, 80, 96)
# gate: glowing arch at the keep's foot
for j, hw in enumerate((1, 2, 2, 2, 2)):
    hline(80 - hw, 80 + hw, 92 + j, 3)
vline(80 - 3, 92, 96, 0)
vline(80 + 3, 92, 96, 0)
px(80 - 2, 91, 0)
px(80 + 2, 91, 0)
hline(80 - 1, 80 + 1, 90, 0)
for y in (93, 95):                        # portcullis bars
    px(80, y, 1)
# moonlight rim on right-facing edges of the whole castle block
for y in range(40, HORIZON):
    for x in range(58, 104):
        if get(x, y) == 0 and get(x + 1, y) in (2, 3) and hashn(x, y) % 3:
            px(x, y, 1)

# ----------------------------------------------------------------------
# LAKE — dark water, moon glade, wavering castle reflection
# ----------------------------------------------------------------------
for y in range(HORIZON, H):
    t = (y - HORIZON) / (H - HORIZON)
    for x in range(W):
        px(x, y, grad(x, y, 0.9 - t * 0.9))
# bright waterline right at the horizon
for x in range(W):
    if get(x, HORIZON - 1) != 0 or hashn(x, 3) % 4 == 0:
        px(x, HORIZON, dith(x, HORIZON, 2, 3, 0.4))
# castle + crag reflection: mirrored dark smear with row jitter
for dy in range(1, 34):
    y = HORIZON + dy
    for x in range(48, 114):
        jx = x + (hashn(0, dy) % 3) - 1
        if get(jx, HORIZON - dy) == 0 and dy % 5 != 4 and hashn(x, dy) % 4:
            px(x, y, dith(x, y, 0, 1, 0.25))
# moon glade: sparse broken dashes, widest near horizon
for dy in range(1, 40):
    y = HORIZON + dy
    if hashn(dy, 9) % 3 == 0:
        continue
    half = max(1, 6 - dy // 5) + (hashn(dy, 21) % 2)
    cx = MX - 2 + (hashn(dy, 33) % 3) - 1
    for x in range(cx - half, cx + half + 1):
        if hashn(x, y) % 3 and 0 <= x < W:
            px(x, y, 3 if hashn(x, y, 7) % 6 == 0 else 2)
# stray sparkles (kept clear of the PRESS START band)
for i in range(26):
    sx = hashn(i, 77) % W
    sy = HORIZON + 3 + hashn(i, 91) % (H - HORIZON - 12)
    if abs(sx - MX) > 14 and not (116 <= sy <= 130):
        px(sx, sy, 2)
        px(sx + 1, sy, 2 if hashn(i, 13) % 2 else 1)

# ----------------------------------------------------------------------
# FOREGROUND — dark banks with pines framing the corners
# ----------------------------------------------------------------------
def pine(cx, base, h):
    for j in range(h):
        y = base - h + j
        half = 1 + int(j * 0.45)
        hline(cx - half, cx + half, y, 0)
    vline(cx, base, base + 2, 0)
    for j in range(0, h, 3):               # moonlit right fringe
        y = base - h + j
        half = 1 + int(j * 0.45)
        px(cx + half, y, 1)


bankL = skyline([(0, 124), (14, 128), (30, 134), (46, 140), (58, 143)])
bankR = skyline([(102, 143), (118, 139), (134, 132), (150, 126), (159, 123)])
for x in range(W):
    top = min(bankL[x], bankR[x])
    for y in range(top, H):
        px(x, y, 0)
    if top < H and get(x, top - 1) != 0:
        px(x, top, 1 if hashn(x, 8) % 3 else 0)
pine(7, 125, 21)
pine(20, 130, 15)
pine(33, 136, 17)
pine(153, 127, 22)
pine(140, 133, 15)
pine(127, 139, 17)

# ----------------------------------------------------------------------
# FABLE LOGO — hand-set beveled letters, outlined, drop-shadowed
# ----------------------------------------------------------------------
F_ = [
    "###########",
    "###########",
    "####...####",
    "####....##.",
    "####...#...",
    "#########..",
    "#########..",
    "####...#...",
    "####.......",
    "####.......",
    "####.......",
    "######.....",
    "######.....",
]
A_ = [
    "....###....",
    "....###....",
    "...#####...",
    "...#####...",
    "..###.###..",
    "..###.###..",
    ".###...###.",
    ".#########.",
    ".#########.",
    "###.....###",
    "###.....###",
    "####...####",
    "####...####",
]
B_ = [
    "#########..",
    "##########.",
    "####...####",
    "####...####",
    "####..####.",
    "#########..",
    "##########.",
    "####...####",
    "####....###",
    "####....###",
    "####...####",
    "##########.",
    "#########..",
]
L_ = [
    "######.....",
    "######.....",
    "####.......",
    "####.......",
    "####.......",
    "####.......",
    "####.......",
    "####.......",
    "####......#",
    "####...####",
    "####...####",
    "###########",
    "###########",
]
E_ = [
    "###########",
    "###########",
    "####...####",
    "####....##.",
    "####...#...",
    "########...",
    "########...",
    "####...#...",
    "####....#..",
    "####...####",
    "####...####",
    "###########",
    "###########",
]
LETTERS = [F_, A_, B_, L_, E_]
LW, LH = 11, 13
GAP = 4
logo_w = 5 * LW + 4 * GAP
LX = (W - logo_w) // 2
LY = 12


def draw_letter(mask, ox, oy):
    for j in range(LH):                    # drop shadow
        for i in range(LW):
            if mask[j][i] == "#":
                px(ox + i + 1, oy + j + 2, 0)
    for j in range(-1, LH + 1):            # outline
        for i in range(-1, LW + 1):
            if 0 <= j < LH and 0 <= i < LW and mask[j][i] == "#":
                continue
            near = any(
                0 <= j + dj < LH and 0 <= i + di < LW
                and mask[j + dj][i + di] == "#"
                for dj in (-1, 0, 1) for di in (-1, 0, 1))
            if near:
                px(ox + i, oy + j, 0)
    for j in range(LH):                    # beveled body
        for i in range(LW):
            if mask[j][i] != "#":
                continue
            top_edge = j == 0 or mask[j - 1][i] != "#"
            left_edge = i == 0 or mask[j][i - 1] != "#"
            if top_edge or (left_edge and j < LH - 2):
                c = 3
            else:
                c = dith(ox + i, oy + j, 3, 2, j / LH * 1.2)
            px(ox + i, oy + j, c)


for k, mask in enumerate(LETTERS):
    draw_letter(mask, LX + k * (LW + GAP), LY)


def diamond(cx, cy):
    for d in (-1, 1):
        px(cx + d, cy, 2)
        px(cx, cy + d, 2)
        px(cx + 2 * d, cy, 1)
        px(cx, cy + 2 * d, 1)
    px(cx, cy, 3)


diamond(LX - 10, LY + 6)
diamond(LX + logo_w + 10, LY + 6)
# underline swash with center gem
sw_y = LY + LH + 4
hline(LX - 2, LX + logo_w + 2, sw_y, 0)
hline(LX + 3, LX + logo_w - 3, sw_y + 1, 0)
px(LX - 3, sw_y - 1, 0)
px(LX + logo_w + 3, sw_y - 1, 0)
for x in range(LX, LX + logo_w + 1, 2):
    px(x, sw_y, 1)
diamond(W // 2, sw_y + 1)

# ----------------------------------------------------------------------
# SMALL TEXT — 3x5 pixel font
# ----------------------------------------------------------------------
FONT = {
    "A": ["###", "#.#", "###", "#.#", "#.#"],
    "B": ["##.", "#.#", "##.", "#.#", "##."],
    "C": ["###", "#..", "#..", "#..", "###"],
    "E": ["###", "#..", "##.", "#..", "###"],
    "F": ["###", "#..", "##.", "#..", "#.."],
    "K": ["#.#", "##.", "#..", "##.", "#.#"],
    "L": ["#..", "#..", "#..", "#..", "###"],
    "O": ["###", "#.#", "#.#", "#.#", "###"],
    "P": ["###", "#.#", "###", "#..", "#.."],
    "R": ["###", "#.#", "##.", "#.#", "#.#"],
    "S": ["###", "#..", "###", "..#", "###"],
    "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "U": ["#.#", "#.#", "#.#", "#.#", "###"],
    "W": ["#.#", "#.#", "#.#", "###", "#.#"],
    "0": ["###", "#.#", "#.#", "#.#", "###"],
    "2": ["###", "..#", "###", "#..", "###"],
    "6": ["###", "#..", "###", "#.#", "###"],
    " ": ["...", "...", "...", "...", "..."],
}


def text(s, ox, oy, c, shadow=None):
    x = ox
    for ch in s:
        g = FONT[ch]
        if shadow is not None:
            blit(g, x + 1, oy + 1, {"#": shadow})
        blit(g, x, oy, {"#": c})
        x += 4


def text_w(s):
    return len(s) * 4 - 1


msg = "PRESS START"
tw = text_w(msg)
mx0 = (W - tw) // 2
text(msg, mx0, 121, 3, shadow=0)

foot = "2026 FABLEWORKS"
fw = text_w(foot)
text(foot, (W - fw) // 2, 136, 1)

# ----------------------------------------------------------------------
# OUTPUT
# ----------------------------------------------------------------------
img = Image.new("P", (W, H))
img.putpalette([v for rgb in PAL for v in rgb] + [0, 0, 0] * 252)
img.putdata([fb[y][x] for y in range(H) for x in range(W)])

here = os.path.dirname(os.path.abspath(__file__))
img.save(os.path.join(here, "title_screen.png"))
img.convert("RGB").resize((W * 4, H * 4), Image.NEAREST).save(
    os.path.join(here, "title_screen_4x.png"))
print("wrote title_screen.png and title_screen_4x.png")
