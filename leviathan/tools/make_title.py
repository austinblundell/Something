#!/usr/bin/env python3
"""
make_title.py -- paint the LEVIATHAN title screen and export it.

Outputs into out/:

    title.png        160x144, indexed, exactly four DMG greens
    title@4x.png     the same image at 4x for looking at
    title.2bpp       deduplicated Game Boy tile data
    title.tilemap    20x18 map indexing into it

Run with `make` (or `python3 tools/make_title.py`) from the leviathan
directory.  The generator is deterministic -- reruns are byte-identical.

Composition notes, because the drawing order matters:

    the moon sits left of centre and the head is painted straight over it,
    so the most detailed silhouette in the picture is backlit and needs no
    outline at all.  Everything on the right half stands against dark sky
    instead, and gets a hard moonlit rim so it still reads.  The sea ramps
    from near-white at the horizon to near-black in the foreground, which
    keeps the bottom of the screen quiet enough to hold lettering.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gbcanvas import (H, W, BLACK, DARK, LIGHT, WHITE, Canvas, disc, discs,
                      dilate, edge, hard, neighbour, outline, poly, rect,
                      ribbon, spline, split_plan, stroke, taper, to_tiles)
from gbfont import logo_text, logo_width, small_text, small_width

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out')

rng = np.random.default_rng(0x1E71)

HORIZON = 98
MOON = (76.0, 68.0, 27.0)           # cx, cy, r
TITLE_BAND = 38                     # sky above this stays dark for the logo

YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)

c = Canvas()


# ============================================================== 1. the sky

def sky():
    mx, my, mr = MOON

    # A shallow ramp: the whole sky lives inside a single shade step, so it
    # stipples gently instead of churning through every grey on the way down.
    t = np.clip(YY / float(HORIZON), 0, 1)
    L = 0.015 + 0.30 * t ** 1.8

    # Moonglow -- tight corona plus a wide wash, faded out towards the top of
    # the frame so the lettering always has dark sky behind it.
    # Kept deliberately weak: the disc has to stay a hard white edge against
    # the sky, and a corona bright enough to be pretty swallows the limb.
    d = np.hypot(XX - mx, YY - my)
    glow = (np.exp(-np.maximum(d - mr, 0) / 7.0) * 0.15
            + np.exp(-np.maximum(d - mr, 0) / 40.0) * 0.13)
    glow *= np.clip((YY - TITLE_BAND + 14) / 16.0, 0.0, 1.0)
    L += glow

    # Faint haze lying along the sea, brightest under the moon.
    L += 0.10 * np.exp(-((YY - HORIZON) / 22.0) ** 2) \
        * np.exp(-((XX - mx) / 90.0) ** 2)

    c.L[:HORIZON] = np.clip(L, 0.0, 1.0)[:HORIZON]
    c.d[:HORIZON] = 1.0


def stars():
    for _ in range(220):
        x = int(rng.integers(0, W))
        y = int(rng.integers(0, 88))
        if c.L[y, x] > 0.14:
            continue
        c.L[y, x] = WHITE if rng.random() < 0.4 else LIGHT
        c.d[y, x] = 0.0


# ============================================================= 2. the moon

def moon():
    mx, my, mr = MOON
    body = hard(disc(mx, my, mr))

    # Flat white disc, then a dithered terminator down the lower left so it
    # reads as a sphere.  The ramp is deliberately short -- most of the face
    # stays pure white, because the head is about to be drawn across it.
    lam = ((XX - mx) * 0.55 + (my - YY) * 0.84) / mr
    L = 1.0 - 0.32 * np.clip(-lam - 0.18, 0, 1) ** 1.2
    c.L[body] = L[body]
    c.d[body] = 1.0

    # Maria and craters, placed around the lower right of the disc -- the
    # only part of it the head does not cover.  The DMG's two pale greens
    # are barely a shade apart, so a mare painted flat in the second-lightest
    # one disappears; these are painted mid-scale and left to dither into a
    # stipple of light and dark, which is what actually reads as grey.
    maria = hard(discs([
        (93, 82, 8, 6.5), (88, 91, 6, 4), (99, 70, 6.5, 9),
        (96, 55, 5.5, 4.5), (84, 60, 4, 5),
    ])) & body
    c.L[maria] = 0.60
    c.d[maria] = 1.0
    bites = hard(discs([(95, 79, 3.5, 3), (99, 66, 3, 3.5),
                        (94, 53, 2, 2)])) & maria
    c.L[bites] = 0.80

    for cx, cy, r in [(88, 76, 4.6), (99, 60, 4.0), (84, 92, 3.4),
                      (97, 88, 3.0), (71, 92, 2.8), (101, 74, 2.6),
                      (93, 48, 2.4), (79, 46, 2.2), (103, 66, 1.8),
                      (89, 86, 1.6), (67, 88, 1.6)]:
        ring = hard(disc(cx, cy, r)) & body
        floor = hard(disc(cx + r * 0.24, cy + r * 0.24, r * 0.62)) & body
        c.L[ring] = WHITE
        c.d[ring] = 0.0
        if r >= 3.0:
            c.L[floor] = DARK          # big ones punch a hard shadow
            c.d[floor] = 0.0
        else:
            c.L[floor] = 0.52
            c.d[floor] = 1.0

    c.L[edge(body, [(0, 1), (0, -1), (1, 0), (-1, 0)])] = WHITE


# =========================================================== 3. storm cloud

def cloud(items, rim_dirs, rim_value, base=BLACK, ragged=0.45):
    m = hard(discs(items))
    c.L[m] = base
    c.d[m] = 0.0
    lit = edge(m, rim_dirs)
    lit |= edge(m & ~lit, rim_dirs) & (rng.random((H, W)) < ragged)
    c.L[lit] = rim_value
    c.d[lit] = 0.0
    return m


def clouds():
    # High bank across the top right, underlit by the moon far below it.
    cloud([(118, 40, 20, 5), (142, 36, 20, 6), (162, 41, 16, 5),
           (130, 45, 16, 4), (152, 45, 12, 3)],
          [(1, 0), (1, -1)], DARK)

    # Torn wisp drifting over the lower half of the moon, rimmed white.
    cloud([(26, 79, 14, 2.4), (50, 77, 16, 2.8), (72, 80, 13, 2.2),
           (90, 78, 10, 1.8), (60, 81, 9, 1.8)],
          [(1, 0), (1, 1), (1, -1)], WHITE, ragged=0.55)

    # A low streak far right, catching only the faintest light.
    cloud([(126, 70, 16, 2.2), (146, 68, 14, 2.0), (158, 72, 10, 1.8)],
          [(1, 0)], DARK, ragged=0.3)


# ============================================================== 4. the sea

def sea():
    mx = MOON[0]

    # Crest rows, spaced out in perspective: dense at the horizon, a few
    # big swells by the time they reach the bottom of the frame.
    crests, step = [float(HORIZON) + 1.0], 1.3
    while crests[-1] < H + 16:
        crests.append(crests[-1] + step)
        step *= 1.30
    n = len(crests)

    x = np.arange(W, dtype=np.float32)
    curves = []
    for k, y0 in enumerate(crests):
        amp = 0.15 + 0.34 * k
        f1, f2 = 0.130 + 0.026 * (k % 3), 0.39 - 0.02 * (k % 4)
        curves.append(y0 + amp * np.sin(x * f1 + 0.7 * k)
                      + amp * 0.45 * np.sin(x * f2 + 2.1 * k))

    # Depth ramp, by row rather than by band: a bright strip of moonlit water
    # at the horizon falling away to near black in the foreground, which is
    # what keeps the lettering legible down there.
    # Sideways, brightness follows the moon's path on the water and falls
    # away towards both edges, so the sea never competes with the disc.
    span = float(H - HORIZON)
    sheen = 0.42 + 0.58 * np.exp(-((x - mx) / 56.0) ** 2)
    for k in range(n - 1):
        for xi in range(W):
            y0 = max(int(round(curves[k][xi])), HORIZON)
            y1 = min(int(round(curves[k + 1][xi])), H)
            if y1 <= y0:
                continue
            rows = np.arange(y0, y1, dtype=np.float32)
            base = 0.86 - 0.86 * ((rows - HORIZON) / span) ** 0.62
            face = np.linspace(0.13, -0.15, y1 - y0)   # lit face into trough
            c.L[y0:y1, xi] = (base + face) * sheen[xi]
            c.d[y0:y1, xi] = 1.0

    # Crest lines, whitecaps and the moon's glitter path.  Only the swells
    # from the middle distance in get a hard line; nearer the horizon the
    # water is left as tone, or it turns into a contour map.
    for k in range(3, n - 1):
        hw = 5.0 + (crests[k] - HORIZON) * 1.30
        for xi in range(W):
            y0 = int(round(curves[k][xi]))
            if not (HORIZON < y0 < H):
                continue
            c.L[y0, xi] = 0.74 * (0.55 + 0.45 * float(sheen[xi]))
            c.d[y0, xi] = 0.0
            if k >= 6 and y0 + 1 < H:
                c.L[y0 + 1, xi] = 0.02      # the trough behind the crest
                c.d[y0 + 1, xi] = 0.0

            dx = abs(xi - mx) / hw
            p = 0.80 * max(0.0, 1.0 - dx * dx) ** 1.2 if dx < 1 else 0.0
            p += 0.035 if k >= 6 else 0.0
            if rng.random() < p:
                c.L[y0, xi] = WHITE
                if k >= 7 and y0 - 1 > HORIZON:
                    c.L[y0 - 1, xi] = WHITE
                    c.d[y0 - 1, xi] = 0.0

    # The far edge of the sea: one hard line, brightest where the moon is
    # standing on it and dying away into the dark at either end.
    c.L[HORIZON, :] = np.where(sheen > 0.85, WHITE,
                               np.where(sheen > 0.60, LIGHT, DARK))
    c.d[HORIZON, :] = 0.0


# ============================================================== 5. the ship

def ship():
    """A brig riding the swell under the moon, for scale.  Pure silhouette,
    because everything behind her -- moonlit water, the disc itself -- is at
    the top of the range."""
    hull = hard(poly([(55, 110), (81, 109), (79, 115), (74, 117),
                      (60, 117), (56, 114)]))
    deck = hard(poly([(55, 108), (82, 107), (82, 109.5), (55, 110.5)]))
    masts = (hard(stroke([(63, 92), (63, 110)], 1))
             | hard(stroke([(72, 90), (72, 110)], 1)))
    yards = (hard(stroke([(58, 95), (69, 95)], 1))
             | hard(stroke([(67, 93), (78, 93)], 1)))
    sails = (hard(poly([(63, 95), (69, 97), (70, 105), (63, 105)]))
             | hard(poly([(72, 93), (78, 96), (78, 106), (72, 106)]))
             | hard(poly([(78, 99), (82, 100), (81, 107)])))

    c.paint(hull | deck | masts | yards | sails, BLACK)

    # Wake, streaming off to leeward.
    for dx in range(1, 15):
        y = 117 + dx // 6
        if rng.random() < 0.6:
            c.paint(hard(rect(55 - dx, y, 56 - dx, y + 1)), WHITE)


# ========================================================= 6. the leviathan

BODY = np.zeros((H, W), dtype=bool)
BANDS = np.zeros((H, W), dtype=bool)


def add(mask):
    global BODY
    BODY |= hard(mask) if mask.dtype != bool else mask


def segment(ctrl, radii, spines=None, bands=None, n=340):
    """Sweep a tapering body along a spline.

    `spines` crests it with dorsal fins; `bands` rules the hide into
    segments, which is most of what stops a long black shape reading as a
    hole in the picture.
    """
    global BANDS
    path = spline(ctrl, n)
    r = taper(len(path), *radii)
    add(ribbon(path, r))

    t = np.gradient(path, axis=0)
    t /= np.maximum(np.hypot(t[:, 0], t[:, 1]), 1e-9)[:, None]
    nrm = np.stack([-t[:, 1], t[:, 0]], axis=1)

    if spines:
        first, last, count, hgt, side = spines
        for i in np.linspace(first, last, count).astype(int):
            base, nv, tv, rr = path[i], nrm[i] * side, t[i], r[i]
            h = hgt * (0.5 + 0.5 * rr / float(max(r)))
            add(poly([tuple(base + nv * (rr - 1.5) - tv * rr * 0.62),
                      tuple(base + nv * (rr + h) - tv * rr * 0.10),
                      tuple(base + nv * (rr - 1.5) + tv * rr * 0.62)]))

    if bands:
        first, last, count, side = bands
        for i in np.linspace(first, last, count).astype(int):
            base, nv, tv, rr = path[i], nrm[i] * side, t[i], r[i]
            a = base + nv * rr * 0.05
            b = base - nv * rr * 1.05
            BANDS |= hard(poly([tuple(a - tv * 1.1), tuple(b - tv * 1.6),
                                tuple(b + tv * 1.6), tuple(a + tv * 1.1)]))
    return path


def head():
    # Upper jaw: back of the skull at the left, snout out to the right.
    add(poly([(28, 64), (25, 54), (28, 45), (36, 39), (47, 38), (57, 41),
              (67, 46), (79, 52), (72, 54), (60, 55.5), (48, 57.5),
              (36, 62)]))
    # Lower jaw, hinged wide open.
    add(poly([(33, 62), (48, 63), (63, 66), (81, 71), (73, 73.5),
              (57, 70), (43, 67), (32, 66.5)]))
    # Backswept horns and cheek fins.
    add(poly([(30, 45), (16, 36), (19, 45), (31, 51)]))
    add(poly([(28, 52), (13, 52), (17, 59), (29, 58)]))
    add(poly([(31, 59), (19, 65), (25, 68), (33, 64)]))
    add(poly([(40, 38.5), (39, 31), (46, 37.5)]))
    # Teeth: upper row hanging into the gape, lower row biting up.
    for tx, tw, th in [(46, 2.1, 4.0), (53, 1.9, 3.6), (59, 1.7, 3.2),
                       (65, 1.5, 2.8), (70, 1.3, 2.4)]:
        ty = 58.0 - (tx - 46) * 0.18
        add(poly([(tx - tw, ty - 1), (tx + tw, ty - 1), (tx, ty + th)]))
    for tx, tw, th in [(50, 1.9, 3.4), (58, 1.7, 3.0), (66, 1.5, 2.6),
                       (73, 1.3, 2.2)]:
        ty = 63.5 + (tx - 50) * 0.24
        add(poly([(tx - tw, ty + 1), (tx + tw, ty + 1), (tx, ty - th)]))


def leviathan():
    bg = c.L.copy()

    # Neck: out of the water on the left and up into the head.
    segment([(40, 120), (33, 104), (25, 88), (27, 75), (32, 66)],
            [(0, 9.5), (0.45, 7.5), (1, 5.4)],
            spines=(70, 320, 8, 6.0, -1), bands=(40, 320, 13, -1))
    head()

    # The great coil, breaking the surface again on the right.
    segment([(96, 126), (101, 102), (111, 80), (127, 69), (142, 78),
             (150, 100), (152, 126)],
            [(0, 9.5), (0.35, 8.5), (0.7, 7.5), (1, 8.5)],
            spines=(30, 290, 11, 6.5, 1), bands=(15, 320, 22, 1))

    # ------------------------------------------------------------ shading
    c.paint(BODY, BLACK)
    c.paint(BANDS & BODY, DARK)          # segmented hide

    # Moonlit rim, but only where the backdrop behind it is dark -- across
    # the face of the moon the silhouette is already at full contrast.
    dirs = [(-1, 0), (0, 1), (-1, 1)]
    rim = edge(BODY, dirs)
    behind = np.zeros((H, W), dtype=np.float32)
    for dy, dx in dirs:
        b = np.zeros((H, W), dtype=np.float32)
        b[max(0, -2 * dy):H - max(0, 2 * dy),
          max(0, -2 * dx):W - max(0, 2 * dx)] = \
            bg[max(0, 2 * dy):H - max(0, -2 * dy),
               max(0, 2 * dx):W - max(0, -2 * dx)]
        behind = np.maximum(behind, b)
    dim = rim & (behind < 0.5)
    c.paint(dim, WHITE)
    inner = edge(BODY & ~rim, [(-1, 0), (0, 1)]) & (rng.random((H, W)) < 0.5)
    c.paint(inner & (behind < 0.5), LIGHT)

    # Scale texture: sparse flecks on the moonward flank of the coil.
    lit = BODY & ~rim & ~inner & (XX > 86) & (YY > 60) & (YY < 118)
    c.paint(lit & (rng.random((H, W)) < 0.07), DARK)

    # Water sheeting off the parts that have just come up out of the sea.
    for _ in range(90):
        x = int(rng.integers(0, W))
        y = int(rng.integers(HORIZON - 16, H - 2))
        if BODY[y, x] and not rim[y, x] and rng.random() < 0.5:
            c.paint(hard(rect(x, y, x + 1, y + 2 + int(rng.integers(0, 3)))),
                    LIGHT)

    # Bone structure, drawn one step up from black: on a silhouette this
    # large a flat fill reads as a hole, and dark-on-black is the only
    # contrast pair quiet enough not to break the silhouette.
    for pts in [[(31, 44), (46, 41.5), (62, 45), (74, 50)],   # skull ridge
                [(34, 55), (41, 59), (49, 61)],               # cheek
                [(40, 66.5), (56, 66.5), (72, 70)],           # jawline
                [(30, 49), (33, 56)]]:                        # temple
        c.paint(hard(stroke(pts, 1)) & BODY, DARK)

    # The eye: white sclera, black slit pupil, one pixel of catchlight.
    c.paint(hard(disc(37.5, 49.5, 3.4)), WHITE)
    c.paint(hard(poly([(36.2, 46.6), (39.8, 48.0), (39.8, 51.6),
                       (36.2, 51.0)])), BLACK)
    c.paint(hard(rect(35.4, 48.0, 36.6, 50.0)), WHITE)
    c.paint(hard(poly([(31, 45.0), (43, 46.4), (43, 47.8), (31, 46.6)])),
            BLACK)                                            # heavy brow
    c.paint(hard(disc(70, 50.5, 1.4)), LIGHT)                 # nostril


def splashes():
    """Foam wherever the body cuts the surface, plus airborne spray."""
    # Sample well below the horizon, where the two legs of the coil have
    # separated -- higher up they merge and the foam lands in open water.
    band = BODY[HORIZON + 6:HORIZON + 16].any(axis=0)
    runs, start = [], None
    for xi in range(W + 1):
        hit = xi < W and band[xi]
        if hit and start is None:
            start = xi
        elif not hit and start is not None:
            runs.append((start, xi - 1))
            start = None

    for x0, x1 in runs:
        cx = (x0 + x1) / 2.0
        wid = min(13.0, max(7.0, (x1 - x0) * 0.70))
        base = HORIZON + 9 + int(cx) % 5

        # Foam reads as horizontal streaks torn along the swell, not as
        # blobs -- so lay short runs of white, thinning outwards and upwards.
        for dy in range(-4, 6):
            y = base + dy
            if not (HORIZON < y < H):
                continue
            fall = 1.0 - abs(dy + 1) / 6.5
            xi = int(cx - wid)
            while xi < cx + wid:
                run = int(rng.integers(2, 7))
                near = 1.0 - abs(xi + run / 2 - cx) / wid
                if (rng.random() < 0.75 * max(0.0, near) * max(0.0, fall)
                        and 0 <= xi < W):
                    seg = hard(rect(xi, y, min(xi + run, W), y + 1))
                    c.paint(seg & ~BODY, WHITE)
                xi += run + int(rng.integers(1, 4))

        # A little spray thrown clear of the surface.
        for _ in range(30):
            x = float(rng.normal(cx, wid * 0.7))
            y = float(rng.normal(base - 8, 6))
            if 0 <= x < W and HORIZON - 16 <= y < H:
                if not BODY[int(y), int(x)] and rng.random() < 0.4:
                    c.paint(hard(rect(x, y, x + 1, y + 1)), WHITE)


# ================================================================ 7. titling

def titling():
    word = 'LEVIATHAN'
    lx, ly = (W - logo_width(word)) // 2, 4
    g = logo_text(word, lx, ly)

    # Cast shadow down and right, then a two-pixel keyline, then the face.
    sh = np.zeros_like(g)
    for dy, dx in [(2, 2), (3, 3), (3, 2), (2, 3), (4, 4)]:
        sh |= neighbour(g, -dy, -dx)
    c.paint(sh & ~g, BLACK)
    c.paint(outline(g, 2), BLACK)
    c.paint(g, WHITE)

    # Emboss.  A light-on-lighter bevel is invisible on this hardware -- the
    # two pale greens are a hair apart -- so the relief is cut in the dark
    # half of the ramp instead: one pixel of shadow inside the bottom and
    # right edge of every stroke.  Any thicker and a four-pixel stem is all
    # bevel and no face.
    c.paint(edge(g, [(1, 0), (0, 1), (1, 1)]), DARK)

    # Tagline, ruled off either side.
    tag = 'THE DEEP REMEMBERS'
    tw = small_width(tag)
    tx, ty = (W - tw) // 2, 28
    t = small_text(tag, tx, ty)
    c.paint(outline(t, 1), BLACK)
    c.paint(t, WHITE)
    for sx in (tx - 17, tx + tw + 5):
        rule = hard(rect(sx, ty + 3, sx + 12, ty + 4))
        dia = hard(poly([(sx + 6, ty + 0.5), (sx + 9.5, ty + 3.5),
                         (sx + 6, ty + 6.5), (sx + 2.5, ty + 3.5)]))
        c.paint(outline(rule | dia, 1), BLACK)
        c.paint(rule | dia, LIGHT)
        c.paint(hard(disc(sx + 6, ty + 3.5, 1.0)), BLACK)

    # Prompt on a keylined plate, and the imprint under it.
    p = 'PRESS START'
    px, pw = (W - small_width(p)) // 2, small_width(p)
    plate = hard(rect(px - 6, 123, px + pw + 6, 134))
    c.paint(dilate(plate, 1) & ~plate, WHITE)
    c.paint(plate, BLACK)
    c.paint(edge(plate, [(-1, 0), (0, -1), (1, 0), (0, 1)]), DARK)
    c.paint(small_text(p, px, 126), WHITE)

    imp = '@2026 TIDEBORNE SOFT'
    im = small_text(imp, (W - small_width(imp)) // 2, 136)
    c.paint(outline(im, 1), BLACK)
    c.paint(im, LIGHT)


# =================================================================== render

def main():
    sky()
    stars()
    moon()
    clouds()
    sea()
    ship()
    leviathan()
    splashes()
    titling()

    os.makedirs(OUT, exist_ok=True)
    c.image().save(os.path.join(OUT, 'title.png'))
    c.image(scale=4).save(os.path.join(OUT, 'title@4x.png'))

    idx = c.indices()
    data, packed, tmap, count = to_tiles(idx)
    with open(os.path.join(OUT, 'title.2bpp'), 'wb') as f:
        f.write(data)
    with open(os.path.join(OUT, 'title.tilemap'), 'wb') as f:
        f.write(packed)

    hist = np.bincount(idx.ravel(), minlength=4)
    names = ['darkest', 'dark', 'light', 'lightest']
    print('shades      :', ', '.join(
        f'{n} {100.0 * h / idx.size:.1f}%' for n, h in zip(names, hist)))
    print(f'unique tiles: {count} of 360 (VRAM holds 384)')
    print(f'tile data   : {len(data)} bytes')

    if count <= 256:
        print('display     : one tile-data base, no tricks needed')
    else:
        plan = split_plan(tmap)
        if plan is None:
            print('display     : DOES NOT FIT -- no LCDC bit 4 split works')
        else:
            print(f"display     : split at tile row {plan['row']} "
                  f"(y={plan['row'] * 8}) -- {plan['top_only']} tiles above "
                  f"only, {plan['bottom_only']} below only, "
                  f"{plan['shared']} shared")


if __name__ == '__main__':
    main()
