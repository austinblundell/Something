"""
scenes.py -- every full-screen picture in EMBERLIGHT, painted in code.

Each entry returns (canvas, palette_regions, cgb_palettes, dmg_bgp).
`palette_regions` is a per-pixel palette index (0..6) used to build the Game
Boy Color attribute map; palette 7 is reserved for the dialogue box.
"""

import numpy as np

from gbart import (Canvas, L_WHITE, L_LIGHT, L_DARK, L_BLACK, SCREEN_W, SCREEN_H,
                   SHADES as SHADES_L)

# --------------------------------------------------------------------------
#  shared palettes
# --------------------------------------------------------------------------
PAL_MOONLIT = [(0xDE, 0xEA, 0xFF), (0x7E, 0x9C, 0xD4), (0x2E, 0x44, 0x7C), (0x07, 0x0C, 0x1E)]
PAL_LAMP = [(0xFF, 0xF6, 0xD2), (0xF2, 0xB4, 0x54), (0x8A, 0x46, 0x1C), (0x16, 0x0C, 0x10)]
PAL_STORM = [(0xD6, 0xDE, 0xDA), (0x84, 0x96, 0x96), (0x36, 0x48, 0x50), (0x08, 0x10, 0x16)]
PAL_SEA = [(0xC8, 0xE0, 0xEE), (0x6A, 0x9A, 0xB8), (0x24, 0x50, 0x74), (0x06, 0x12, 0x22)]
PAL_DUSK = [(0xFF, 0xE0, 0xB8), (0xE0, 0x92, 0x72), (0x74, 0x40, 0x58), (0x18, 0x10, 0x22)]
PAL_DAWN = [(0xFF, 0xF2, 0xDC), (0xFF, 0xB8, 0x8E), (0x9A, 0x62, 0x74), (0x22, 0x1A, 0x30)]
PAL_MEMORY = [(0xF6, 0xEC, 0xD4), (0xC6, 0xA8, 0x84), (0x74, 0x5C, 0x48), (0x1C, 0x16, 0x14)]
PAL_DEEP = [(0x9E, 0xC4, 0xC0), (0x4E, 0x82, 0x8C), (0x1C, 0x40, 0x54), (0x04, 0x0E, 0x18)]
PAL_ASH = [(0xE4, 0xE0, 0xD8), (0x9C, 0x94, 0x8C), (0x4C, 0x48, 0x48), (0x0C, 0x0C, 0x10)]

BGP_STD = 0xE4          # %11100100 -- identity shade mapping

_registry = {}


def scene(name, **meta):
    def wrap(fn):
        _registry[name] = (fn, meta)
        return fn
    return wrap


def all_scenes():
    return dict(_registry)


# --------------------------------------------------------------------------
#  reusable pieces of world
# --------------------------------------------------------------------------

def night_sky(c, horizon, top=0.06, bottom=0.46, seed=11, stars=90, cloud=0.0):
    """Vertical night gradient, optional cloud banding, stars above horizon."""
    c.L[:] = c.grad_v(0, horizon, top, bottom, ease=1.6)
    if cloud > 0.0:
        n = c.noise(seed + 5, cells=5, octaves=3)
        band = c.grad_v(horizon * 0.18, horizon * 0.85, 1.0, 0.0)
        c.add((n - 0.45) * band, cloud)
    if stars:
        c.stars(stars, seed, y_max=int(horizon * 0.8))
    return c


def sea(c, horizon, bottom_v=0.10, seed=23, chop=0.10, glint_x=None, top_v=0.42,
        stops=None):
    """Water: darkening gradient plus horizontal chop, optional light column."""
    water = c.ramp_v(stops or [(horizon, top_v), (horizon + 14, top_v * 0.78),
                               (horizon + 30, (top_v + bottom_v) * 0.45),
                               (SCREEN_H, bottom_v)])
    c.L[horizon:] = water[horizon:]
    yy = np.arange(SCREEN_H, dtype=np.float32)[:, None]
    xx = np.arange(SCREEN_W, dtype=np.float32)[None, :]
    # Waves get longer and taller as they approach the viewer.
    depth = np.clip((yy - horizon) / max(1.0, SCREEN_H - horizon), 0.0, 1.0)
    ripple = np.sin(xx * (0.5 - depth * 0.34) + yy * 0.9) * np.sin(yy * 0.55 + xx * 0.05)
    mask = np.zeros((SCREEN_H, SCREEN_W), dtype=bool)
    mask[horizon:] = True
    c.L = np.where(mask, np.clip(c.L + ripple * chop * (0.25 + depth), 0, 1), c.L)
    if glint_x is not None:
        col = np.exp(-((xx - glint_x) ** 2) / (2 * 15.0 ** 2))
        streak = (np.sin(yy * 1.7) * 0.5 + 0.5) * col * depth
        c.L = np.where(mask, np.clip(c.L + streak * 0.55, 0, 1), c.L)
    return c


def lighthouse(c, bx, base_y, top_y, half_bot, half_top, lit=True, bands=()):
    """A tapering tower with gallery, lamp room and cap. Returns lamp centre.

    top_y is the roof apex; the lamp room sits just below it and the shaft
    runs down to base_y.
    """
    room_top = top_y + 10
    room_bot = room_top + 11
    lw = half_top + 3

    # Shaft, tapering from half_bot at the rock to half_top at the gallery.
    shaft = [(bx - half_bot, base_y), (bx - half_top, room_bot + 2),
             (bx + half_top, room_bot + 2), (bx + half_bot, base_y)]
    shaft_mask = c.mask(lambda d: d.polygon(shaft, fill=255))
    c.paint(shaft_mask, L_BLACK)
    # Daymark stripes, clipped to the taper so nothing spills into the sky.
    for (y0, y1, shade) in bands:
        band = c.mask(lambda d, a=y0, b=y1: d.rectangle(
            (bx - half_bot - 2, a, bx + half_bot + 2, b), fill=255))
        c.flat(band & shaft_mask, shade)

    # Lamp room and the gallery deck it stands on.
    c.rect((bx - lw, room_top, bx + lw, room_bot), 3)
    c.rect((bx - lw - 2, room_bot, bx + lw + 2, room_bot + 2), 3)
    # Conical cap and finial.
    c.poly([(bx - lw - 1, room_top + 1), (bx, top_y - 6), (bx + lw + 1, room_top + 1)], 3)
    c.line([(bx, top_y - 6), (bx, top_y - 10)], 3)

    if lit:
        glass = (bx - lw + 2, room_top + 2, bx + lw - 2, room_bot - 2)
        c.rect(glass, 0)
        c.no_dither(c.mask(lambda d: d.rectangle(glass, fill=255)))
        # Two mullions so it reads as a lens assembly, not a white blob.
        c.line([(bx - 2, room_top + 2), (bx - 2, room_bot - 2)], 2)
        c.line([(bx + 2, room_top + 2), (bx + 2, room_bot - 2)], 2)
    return (bx, (room_top + room_bot) // 2)


def rim_light(c, bx, base_y, top_y, half_bot, half_top, shade=1, side=+1):
    """One-pixel highlight down the moonward edge of a silhouetted tower.

    Without it a black tower against a black sky simply vanishes.
    """
    room_bot = top_y + 21
    span = max(1, base_y - (room_bot + 2))
    for i in range(span + 1):
        y = room_bot + 2 + i
        t = i / span
        hw = half_top + (half_bot - half_top) * t
        x = int(round(bx + side * hw))
        if 0 <= y < SCREEN_H and 0 <= x < SCREEN_W:
            c.L[y, x] = SHADES_L[shade]
            c.dither[y, x] = 0.0
    return c


def beam(c, lx, ly, spread_up, spread_dn, to_x, strength=0.6, reach=170, blur=1.4,
         core=0.42):
    """A searchlight cone: soft outer haze plus a brighter inner core.

    One flat cone quantises to a single flat shade and reads as a grey wedge;
    the two-layer version keeps a hot centre line, which is what makes it look
    like light rather than paint.
    """
    def cone(up, dn, b):
        pts = [(lx, ly), (to_x, ly - up), (to_x, ly + dn)]
        return c.soft_mask(lambda d: d.polygon(pts, fill=255), blur=b)

    fade = c.grad_r(lx, ly, 6, reach, 1.0, 0.0) ** 1.15
    c.blend(cone(spread_up, spread_dn, blur * 2.0) * fade * strength * 0.55, L_WHITE)
    c.blend(cone(max(1, int(spread_up * core)), max(1, int(spread_dn * core)), blur)
            * fade * strength, L_WHITE)
    return c


def rain(c, count, seed, length=7, slant=2, value=L_WHITE, region=None):
    rng = np.random.default_rng(seed)
    for _ in range(count):
        x = int(rng.integers(-8, SCREEN_W))
        y = int(rng.integers(0, SCREEN_H))
        if region is not None and not region(x, y):
            continue
        c.line([(x, y), (x + slant, y + length)], value=value, width=1)
    return c


def sine_poly(c, y_base, amp, freq, phase, shade, crest_shade=None,
              bottom=SCREEN_H, amp2=0.0, freq2=0.0):
    """Fill everything below a sine profile: one wave, one hill, one bank."""
    xs = np.arange(SCREEN_W + 1, dtype=np.float32)
    ys = y_base + np.sin(xs * freq + phase) * amp
    if amp2:
        ys = ys + np.sin(xs * freq2 + phase * 1.7) * amp2
    pts = [(int(x), int(round(y))) for x, y in zip(xs, ys)]
    c.poly(pts + [(SCREEN_W, bottom), (0, bottom)], shade)
    if crest_shade is not None:
        c.line(pts, crest_shade)
    return ys


def cloudscape(c, y0, y1, seed, cells=6, octaves=4,
               thresholds=(0.60, 0.47), shades=(1, 2, 3), rim=None):
    """Three-tone storm cloud masses.

    Thresholding fractal noise gives hard organic edges that quantise cleanly,
    instead of the fine grey fizz you get from dithering the noise directly.
    """
    n = c.noise(seed, cells=cells, octaves=octaves)
    inside = np.zeros((SCREEN_H, SCREEN_W), dtype=bool)
    inside[y0:y1] = True
    hi, mid = thresholds
    c.flat(inside & (n > hi), shades[0])
    c.flat(inside & (n > mid) & (n <= hi), shades[1])
    c.flat(inside & (n <= mid), shades[2])
    if rim is not None:
        # One-pixel bright edge along the top of the brightest masses.
        core = inside & (n > hi)
        above = np.zeros_like(core)
        above[1:] = core[1:] & ~core[:-1]
        c.flat(above, rim)
    return n


def person(c, x, y, h=22, shade=3, coat=True, lantern=None, face_right=True):
    """A small standing figure: coat, hood, one arm. Reads at 22px tall."""
    hw = max(2, h // 6)
    head_r = max(2, h // 8)
    hy = y - h + head_r
    # Hooded head
    c.ellipse((x - head_r - 1, hy - head_r, x + head_r + 1, hy + head_r + 1), shade)
    # Body: a slightly flared coat
    c.poly([(x - hw, hy + head_r), (x + hw, hy + head_r),
            (x + hw + (2 if coat else 0), y), (x - hw - (2 if coat else 0), y)], shade)
    # Arm toward the lantern side
    ax = x + (hw + 1) * (1 if face_right else -1)
    c.line([(x, hy + head_r + 3), (ax, hy + head_r + 8)], shade)
    if lantern is not None:
        lx2 = ax + (2 if face_right else -2)
        ly2 = hy + head_r + 11
        c.glow(lx2, ly2, lantern, 0.85)
        c.rect((lx2 - 2, ly2 - 2, lx2 + 2, ly2 + 2), 0)
        c.no_dither(c.mask(lambda d: d.rectangle(
            (lx2 - 2, ly2 - 2, lx2 + 2, ly2 + 2), fill=255)))
        c.line([(ax, hy + head_r + 8), (lx2, ly2 - 2)], shade)
    return c


# ==========================================================================
#  2. THE STORM  --  the tower taking a beating from below
# ==========================================================================
@scene('storm', bgp=BGP_STD)
def s_storm():
    c = Canvas()
    c.L[:] = 0.0
    cloudscape(c, 0, 92, seed=404, cells=5, octaves=4,
               thresholds=(0.615, 0.475), shades=(1, 2, 3), rim=0)

    # Rain, baked in behind the tower; sprites add the moving layer on top.
    for i in range(70):
        rng = np.random.default_rng(900 + i)
        x = int(rng.integers(-6, SCREEN_W))
        y = int(rng.integers(0, 120))
        c.line([(x, y), (x + 3, y + 9)], 0)

    # The stack, seen closer and steeper than on the title card.
    c.poly([(0, 128), (16, 110), (34, 96), (52, 92), (74, 98), (96, 116), (120, 136),
            (SCREEN_W, SCREEN_H), (0, SCREEN_H)], 3)
    c.line([(16, 110), (34, 96), (52, 92), (74, 98)], 2)

    lamp = lighthouse(c, 52, 96, 16, 11, 6, lit=True, bands=((44, 51, 1), (68, 75, 1)))
    rim_light(c, 52, 96, 16, 11, 6, shade=1, side=-1)
    lx, ly = lamp
    beam(c, lx, ly, 16, 5, SCREEN_W + 10, strength=0.5, reach=150)
    c.glow(lx, ly, 12, 0.8)

    # Sea smashing against the rock: three overlapping swells plus spray.
    sine_poly(c, 118, 7, 0.075, 0.0, 2, crest_shade=0, amp2=3, freq2=0.21)
    sine_poly(c, 130, 6, 0.055, 2.1, 3, crest_shade=1, amp2=2, freq2=0.17)
    spray = c.soft_mask(lambda d: d.ellipse((6, 88, 78, 132), fill=255), blur=6.0)
    c.blend(spray * 0.55, L_WHITE)
    c.snap(0.55, mask=(c.grad_v(88, 134, 1.0, 1.0) > 0.5) &
           c.mask(lambda d: d.ellipse((6, 88, 78, 132), fill=255)))
    sine_poly(c, 140, 4, 0.09, 1.0, 3, crest_shade=0)

    pal = np.zeros((SCREEN_H, SCREEN_W), dtype=np.uint8)
    pal[c.mask(lambda d: d.rectangle((lx - 9, ly - 9, lx + 9, ly + 8), fill=255))] = 1
    return c, pal, [PAL_STORM, PAL_LAMP], BGP_STD


# ==========================================================================
#  3. THE LAMP ROOM  --  the great lens and the dying ember
# ==========================================================================
@scene('lamproom', bgp=BGP_STD)
def s_lamproom():
    c = Canvas()
    c.L[:] = 0.0

    # Iron floor plates and the curved wall behind the lens.
    c.rect((0, 118, SCREEN_W, SCREEN_H), 2)
    for x in range(0, SCREEN_W, 16):
        c.line([(x, 118), (x, SCREEN_H)], 3)
    c.line([(0, 118), (SCREEN_W, 118)], 3)
    c.line([(0, 124), (SCREEN_W, 124)], 3)

    # Two window arches looking out into the storm.
    for wx in (14, 118):
        c.rect((wx, 26, wx + 28, 92), 3)
        c.mask(lambda d: d.rectangle((wx, 26, wx + 28, 92), fill=255))
        c.ellipse((wx, 14, wx + 28, 44), 3)
        inner = c.mask(lambda d, a=wx: (d.rectangle((a + 3, 30, a + 25, 89), fill=255),
                                        d.ellipse((a + 3, 19, a + 25, 43), fill=255)))
        c.paint(inner, 0.30)
        c.line([(wx + 14, 22), (wx + 14, 89)], 3)
        c.line([(wx + 3, 58), (wx + 25, 58)], 3)
        for i in range(14):
            rng = np.random.default_rng(50 + wx + i)
            rx = int(rng.integers(wx + 3, wx + 25))
            ry = int(rng.integers(24, 86))
            c.line([(rx, ry), (rx + 2, ry + 6)], 0)

    # The great Fresnel lens: concentric prism rings around a hot core.
    cx, cy = 80, 66
    c.glow(cx, cy, 66, 0.42)
    for r in range(46, 8, -6):
        c.outline((cx - r, cy - int(r * 1.18), cx + r, cy + int(r * 1.18)),
                  1 if (r // 6) % 2 else 2, width=2, kind='ellipse')
    lens = c.mask(lambda d: d.ellipse((cx - 46, cy - 54, cx + 46, cy + 54), fill=255))
    # Vertical prism divisions
    for x in range(cx - 44, cx + 45, 11):
        c.paint(c.mask(lambda d, a=x: d.line([(a, cy - 54), (a, cy + 54)], fill=255,
                                             width=1)) & lens, L_DARK)
    # Brass frame ribs
    c.paint(c.mask(lambda d: d.ellipse((cx - 46, cy - 54, cx + 46, cy + 54),
                                       outline=255, width=3)), L_BLACK)
    c.line([(cx - 52, cy - 56), (cx + 52, cy - 56)], 3, width=3)
    c.line([(cx - 52, cy + 56), (cx + 52, cy + 56)], 3, width=3)

    # The ember at the heart of it -- small, and clearly failing.
    c.glow(cx, cy, 26, 1.0)
    core = c.mask(lambda d: d.ellipse((cx - 6, cy - 8, cx + 6, cy + 8), fill=255))
    c.flat(core, 0).no_dither(core)
    c.flat(c.mask(lambda d: d.ellipse((cx - 3, cy - 4, cx + 3, cy + 5), fill=255)), 1)

    # The keeper, small, at the foot of the machine.
    person(c, 34, 122, h=26, lantern=None)

    c.vignette(0.45)

    pal = np.zeros((SCREEN_H, SCREEN_W), dtype=np.uint8)
    pal[:] = 2                                   # iron
    pal[c.mask(lambda d: d.ellipse((cx - 58, cy - 64, cx + 58, cy + 64), fill=255))] = 1
    pal[c.mask(lambda d: (d.rectangle((14, 12, 42, 92), fill=255),
                          d.rectangle((118, 12, 146, 92), fill=255)))] = 0
    return c, pal, [PAL_STORM, PAL_LAMP, PAL_ASH], BGP_STD


# ==========================================================================
#  4. THE DROWNED VILLAGE  --  rowing over the rooftops of home
# ==========================================================================
@scene('village', bgp=BGP_STD)
def s_village():
    c = Canvas()
    horizon = 76
    c.L[:] = c.ramp_v([(0, 0.00), (40, 0.03), (54, 0.30), (75, 0.34)])
    mx, my, mr = 44, 30, 15
    c.glow(mx, my, 38, 0.16)
    sea(c, horizon, seed=91, chop=0.07, glint_x=mx,
        stops=[(horizon, 0.60), (horizon + 5, 0.34), (horizon + 26, 0.28),
               (horizon + 46, 0.14), (SCREEN_H, 0.04)])
    c.snap(0.78)
    seam = c.mask(lambda d: d.rectangle((0, horizon - 2, SCREEN_W, horizon - 1), fill=255))
    c.flat(seam, 0).no_dither(seam)
    c.stars(40, 55, y_max=42)
    disc = c.mask(lambda d: d.ellipse((mx - mr, my - mr, mx + mr, my + mr), fill=255))
    c.flat(disc, 0).no_dither(disc)
    c.flat(c.mask(lambda d: d.ellipse((mx - 7, my - 6, mx - 1, my, ), fill=255)) & disc, 1)
    c.flat(c.mask(lambda d: d.ellipse((mx + 2, my + 3, mx + 9, my + 10), fill=255)) & disc, 1)

    # The far bluff, and the tower still standing on it.
    sine_poly(c, 70, 3, 0.03, 0.6, 3, crest_shade=2, bottom=horizon + 1, amp2=2, freq2=0.11)
    lamp = lighthouse(c, 138, 72, 30, 6, 4, lit=True, bands=((52, 57, 1),))
    lx, ly = lamp
    beam(c, lx, ly, 14, 4, -20, strength=0.34, reach=170)
    c.glow(lx, ly, 9, 0.9)

    # Rooftops: gables and a chimney poking through flat water.
    def roof(x, w, h, y_water, shade=3, ridge=1):
        c.poly([(x, y_water), (x + w // 2, y_water - h), (x + w, y_water)], shade)
        c.line([(x, y_water), (x + w // 2, y_water - h)], ridge)
        # Reflection: a few broken horizontal dashes under the eaves.
        for i in range(1, 5):
            yy = y_water + i * 2
            if yy < SCREEN_H:
                c.line([(x + 2 + i, yy), (x + w - 2 - i, yy)], 3)

    roof(10, 34, 15, 100)
    roof(52, 26, 11, 92)
    roof(96, 40, 18, 112)
    c.rect((122, 84, 130, 96), 3)          # a chimney
    c.line([(122, 84), (130, 84)], 1)
    roof(4, 22, 9, 128)

    # The boat, low in the water, lantern lit, the keeper rowing.
    bx, by = 66, 130
    c.poly([(bx - 22, by), (bx + 22, by), (bx + 16, by + 7), (bx - 16, by + 7)], 3)
    c.line([(bx - 22, by), (bx + 22, by)], 1)
    c.line([(bx - 20, by + 2), (bx - 34, by + 9)], 3)     # oar
    c.line([(bx + 20, by + 2), (bx + 34, by + 9)], 3)
    person(c, bx + 2, by, h=20, lantern=None)
    c.glow(bx - 16, by - 12, 15, 0.9)
    lant = c.mask(lambda d: d.rectangle((bx - 18, by - 15, bx - 14, by - 10), fill=255))
    c.flat(lant, 0).no_dither(lant)
    c.line([(bx - 16, by - 10), (bx - 16, by - 2)], 3)

    pal = np.zeros((SCREEN_H, SCREEN_W), dtype=np.uint8)
    pal[c.mask(lambda d: d.rectangle((bx - 26, by - 22, bx - 6, by + 4), fill=255))] = 1
    pal[c.mask(lambda d: d.rectangle((lx - 7, ly - 7, lx + 7, ly + 7), fill=255))] = 1
    return c, pal, [PAL_SEA, PAL_LAMP], BGP_STD


# ==========================================================================
#  1. TITLE
# ==========================================================================
@scene('title', bgp=BGP_STD)
def s_title():
    c = Canvas()
    horizon = 100

    # Value plan: black overhead, a dark-grey band low in the sky, a bright
    # seam exactly at the waterline, then the sea sinking back to black.
    c.L[:] = c.ramp_v([(0, 0.00), (66, 0.02), (76, 0.33), (99, 0.36)])
    n = c.noise(31, cells=16, octaves=2)
    band = c.grad_v(72, 94, 0.0, 1.0) * c.grad_v(94, 99, 1.0, 0.0)
    c.add((n - 0.5) * band, 0.22)

    # Moon, low and to the right.
    mx, my, mr = 116, 56, 21
    c.glow(mx, my, 46, 0.14)
    sea(c, horizon, seed=7, chop=0.09, glint_x=mx,
        stops=[(horizon, 0.66), (horizon + 4, 0.36), (horizon + 18, 0.30),
               (horizon + 32, 0.12), (SCREEN_H, 0.02)])
    # Poster the sky and sea into flat bands before any hard-edged art lands.
    c.snap(0.78)
    seam = c.mask(lambda d: d.rectangle((0, horizon - 2, SCREEN_W, horizon - 1), fill=255))
    c.flat(seam, 0).no_dither(seam)
    c.stars(58, 101, y_max=64)
    c.waves(horizon + 2, SCREEN_H - 2, 46, 77, min_len=3, max_len=24)

    disc = c.mask(lambda d: d.ellipse((mx - mr, my - mr, mx + mr, my + mr), fill=255))
    c.flat(disc, 0).no_dither(disc)
    for box in ((mx - 11, my - 9, mx - 3, my - 1), (mx + 3, my + 2, mx + 12, my + 11),
                (mx - 5, my + 9, mx + 1, my + 14)):
        c.flat(c.mask(lambda d, b=box: d.ellipse(b, fill=255)) & disc, 1)

    # The stack the tower stands on.
    rock = [(0, horizon + 18), (9, horizon + 3), (19, horizon - 6), (31, horizon - 9),
            (44, horizon - 3), (55, horizon + 8), (66, horizon + 22), (0, SCREEN_H)]
    c.poly(rock, 3)
    c.line([(19, horizon - 6), (31, horizon - 9), (44, horizon - 3)], 1)
    lamp = lighthouse(c, 30, horizon - 7, 24, 9, 5, lit=True,
                      bands=((58, 64, 1), (78, 84, 1)))
    rim_light(c, 30, horizon - 7, 24, 9, 5, shade=1, side=+1)

    lx, ly = lamp
    beam(c, lx, ly, 22, 6, SCREEN_W + 8, strength=0.66, reach=180)
    beam(c, lx, ly, 6, 12, -12, strength=0.22, reach=64)
    c.glow(lx, ly, 13, 0.95)

    # Logotype.
    c.text_center('EMBERLIGHT', 8, shade_index=0, tracking=6, scale=2, shadow=3)
    c.rect((20, 25, 139, 25), 0)
    c.text_center('KEEPER OF THE LAST LIGHT', 30, shade_index=0, tracking=6, shadow=3)

    pal = np.zeros((SCREEN_H, SCREEN_W), dtype=np.uint8)
    # Only the lamp room itself reads warm -- one attribute cell wide either way.
    pal[c.mask(lambda d: d.rectangle((lx - 9, ly - 8, lx + 9, ly + 8), fill=255))] = 1
    return c, pal, [PAL_MOONLIT, PAL_LAMP], BGP_STD


def figure_back(c, x, base_y, w=26, h=42, shade=3, hood=True, rim=None):
    """An over-the-shoulder silhouette: hood, shoulders, no face.

    Reads instantly at Game Boy resolution and puts the player behind the
    keeper's eyes, which is what these compositions are for.
    """
    hw = w // 2
    head_w = max(6, w // 3)
    head_h = int(head_w * 1.15)
    hy = base_y - h
    # Shoulders: a wide, slightly domed trapezoid.
    c.poly([(x - hw, base_y), (x - hw + 2, hy + head_h + 3),
            (x - head_w, hy + head_h - 1), (x + head_w, hy + head_h - 1),
            (x + hw - 2, hy + head_h + 3), (x + hw, base_y)], shade)
    if hood:
        c.poly([(x - head_w, hy + head_h + 1), (x - head_w + 1, hy + 4),
                (x - head_w // 2, hy), (x + head_w // 2, hy),
                (x + head_w - 1, hy + 4), (x + head_w, hy + head_h + 1)], shade)
    else:
        c.ellipse((x - head_w, hy, x + head_w, hy + head_h), shade)
    if rim is not None:
        # Light catching one shoulder and the edge of the hood.
        c.line([(x + head_w - 1, hy + 5), (x + hw - 2, hy + head_h + 4),
                (x + hw - 1, base_y)], rim)
    return c


# ==========================================================================
#  5. THE SIGNAL  --  over her shoulder, a light where nothing should be
# ==========================================================================
@scene('signal', bgp=BGP_STD)
def s_signal():
    c = Canvas()
    horizon = 84
    c.L[:] = c.ramp_v([(0, 0.02), (34, 0.10), (60, 0.30), (83, 0.34)])
    cloudscape(c, 0, 66, seed=717, cells=6, octaves=3,
               thresholds=(0.63, 0.50), shades=(1, 2, 3))
    sea(c, horizon, seed=311, chop=0.08,
        stops=[(horizon, 0.44), (horizon + 8, 0.30), (horizon + 26, 0.18),
               (SCREEN_H, 0.04)])
    c.snap(0.76)
    seam = c.mask(lambda d: d.rectangle((0, horizon - 1, SCREEN_W, horizon - 1), fill=255))
    c.flat(seam, 1).no_dither(seam)
    c.waves(horizon + 3, 118, 34, 313, min_len=3, max_len=18)

    # The signal: one small hard light, and its long reach on the water.
    sx, sy = 124, 79
    c.glow(sx, sy, 22, 0.85)
    core = c.mask(lambda d: d.rectangle((sx - 1, sy - 1, sx + 1, sy + 1), fill=255))
    c.flat(core, 0).no_dither(core)
    path = c.soft_mask(lambda d: d.polygon(
        [(sx - 1, horizon), (sx + 2, horizon), (sx + 12, SCREEN_H), (sx - 11, SCREEN_H)],
        fill=255), blur=3.0)
    c.blend(path * c.grad_v(horizon, SCREEN_H, 0.55, 0.12), L_WHITE)

    # Baked rain behind the figure; sprites carry the moving layer.
    for i in range(46):
        rng = np.random.default_rng(2200 + i)
        x = int(rng.integers(-6, SCREEN_W))
        y = int(rng.integers(0, 110))
        c.line([(x, y), (x + 3, y + 8)], 0)

    # The prow of her father's boat, and her back filling the near frame.
    c.poly([(0, SCREEN_H), (0, 122), (46, 112), (96, 118), (112, SCREEN_H)], 3)
    c.line([(0, 122), (46, 112), (96, 118)], 1)
    figure_back(c, 54, 126, w=44, h=62, rim=1)

    pal = np.zeros((SCREEN_H, SCREEN_W), dtype=np.uint8)
    pal[c.mask(lambda d: d.rectangle((sx - 10, sy - 10, sx + 10, sy + 10), fill=255))] = 1
    return c, pal, [PAL_STORM, PAL_LAMP], BGP_STD


# ==========================================================================
#  6. RESCUE  --  four men alive, and a tower going dark behind her
# ==========================================================================
@scene('rescue', bgp=BGP_STD)
def s_rescue():
    c = Canvas()
    horizon = 62
    c.L[:] = c.ramp_v([(0, 0.03), (30, 0.12), (52, 0.32), (61, 0.34)])
    cloudscape(c, 0, 50, seed=515, cells=6, octaves=3,
               thresholds=(0.64, 0.51), shades=(1, 2, 3))
    sea(c, horizon, seed=99, chop=0.10,
        stops=[(horizon, 0.40), (horizon + 10, 0.30), (horizon + 34, 0.16),
               (SCREEN_H, 0.05)])
    c.snap(0.74)
    c.waves(horizon + 2, 132, 44, 555, min_len=4, max_len=22)

    # The point, far off on the left. The tower is a stump of black: no lamp.
    c.poly([(0, horizon + 6), (10, horizon - 2), (22, horizon + 2), (30, horizon + 8),
            (0, horizon + 14)], 3)
    lighthouse(c, 13, horizon + 1, horizon - 30, 4, 3, lit=False)

    # Swell, drawn as two long crests so the boats sit in a trough.
    sine_poly(c, 96, 8, 0.045, 0.4, 2, crest_shade=0, amp2=3, freq2=0.14)
    sine_poly(c, 124, 7, 0.06, 2.4, 3, crest_shade=1, amp2=2, freq2=0.2)

    # Their boat, low and crowded, with the storm lantern they kept swinging.
    bx, by = 96, 108
    c.poly([(bx - 26, by), (bx + 26, by), (bx + 19, by + 8), (bx - 19, by + 8)], 3)
    c.line([(bx - 26, by), (bx + 26, by)], 1)
    for i, (dx, hh) in enumerate(((-16, 15), (-6, 18), (5, 16), (15, 13))):
        person(c, bx + dx, by, h=hh)
    c.glow(bx + 24, by - 20, 20, 0.95)
    lant = c.mask(lambda d: d.rectangle((bx + 22, by - 23, bx + 27, by - 17), fill=255))
    c.flat(lant, 0).no_dither(lant)
    c.line([(bx + 24, by - 17), (bx + 24, by - 2)], 3)

    # Her boat, nearer, cutting in from the right of frame.
    c.poly([(30, SCREEN_H), (36, 128), (100, 132), (140, 140), (150, SCREEN_H)], 3)
    c.line([(36, 128), (100, 132), (140, 140)], 1)
    figure_back(c, 62, 138, w=34, h=48, rim=1)

    for i in range(40):
        rng = np.random.default_rng(3300 + i)
        x = int(rng.integers(-6, SCREEN_W))
        y = int(rng.integers(0, 96))
        c.line([(x, y), (x + 4, y + 9)], 0)

    pal = np.zeros((SCREEN_H, SCREEN_W), dtype=np.uint8)
    pal[c.mask(lambda d: d.rectangle((bx + 12, by - 32, bx + 34, by - 6), fill=255))] = 1
    return c, pal, [PAL_STORM, PAL_LAMP], BGP_STD


# ==========================================================================
#  7. VIGIL  --  she keeps the light, and watches the signal stop
# ==========================================================================
@scene('vigil', bgp=BGP_STD)
def s_vigil():
    c = Canvas()
    horizon = 92

    # The lamp is directly overhead and out of frame, so the value plan runs
    # bright at the top of the picture and falls away -- the exact opposite of
    # the other night scenes, which is what sells "standing under the light".
    c.L[:] = c.ramp_v([(0, 0.95), (14, 0.72), (26, 0.34), (44, 0.06),
                       (68, 0.04), (80, 0.28), (91, 0.32)])
    n = c.noise(808, cells=12, octaves=2)
    band = c.grad_v(56, 84, 0.0, 1.0) * c.grad_v(84, 91, 1.0, 0.0)
    c.add((n - 0.5) * band, 0.24)

    sea(c, horizon, seed=421, chop=0.08,
        stops=[(horizon, 0.52), (horizon + 6, 0.32), (horizon + 24, 0.20),
               (SCREEN_H, 0.05)])
    c.snap(0.76)
    seam = c.mask(lambda d: d.rectangle((0, horizon - 1, SCREEN_W, horizon - 1), fill=255))
    c.flat(seam, 0).no_dither(seam)
    c.waves(horizon + 3, 124, 26, 423, min_len=3, max_len=16)

    # Far out: the signal, small and stubborn.
    sx, sy = 132, 88
    c.glow(sx, sy, 12, 0.7)
    core = c.mask(lambda d: d.rectangle((sx, sy - 1, sx + 1, sy), fill=255))
    c.flat(core, 0).no_dither(core)

    # Light spilling past the gallery roof, thrown out over the water.
    beam(c, 60, 8, 4, 62, SCREEN_W + 20, strength=0.30, reach=210, blur=3.0)
    beam(c, 96, 4, 4, 58, -24, strength=0.22, reach=150, blur=3.0)

    # The gallery rail across the lower third, and her hands on it.
    c.rect((0, 118, SCREEN_W, 121), 3)
    c.rect((0, 136, SCREEN_W, 139), 3)
    for x in range(6, SCREEN_W, 13):
        c.rect((x, 120, x + 2, 138), 3)
    c.line([(0, 117), (SCREEN_W, 117)], 1)

    figure_back(c, 46, 142, w=40, h=66, rim=1)

    # A full-width band for the lit sky: no vertical attribute edges to give
    # the 8x8 colour grid away.
    pal = np.zeros((SCREEN_H, SCREEN_W), dtype=np.uint8)
    pal[0:24, :] = 1
    return c, pal, [PAL_MOONLIT, PAL_LAMP], BGP_STD


# ==========================================================================
#  8. DAWN  --  the sea lies down as if nothing had happened
# ==========================================================================
@scene('dawn', bgp=BGP_STD)
def s_dawn():
    c = Canvas()
    horizon = 88
    # Dawn inverts the night scenes: the value mass is light, not dark.
    c.L[:] = c.ramp_v([(0, 0.34), (30, 0.52), (62, 0.78), (86, 0.97)])
    n = c.noise(66, cells=13, octaves=2)
    band = c.grad_v(24, 62, 0.0, 1.0) * c.grad_v(62, 84, 1.0, 0.0)
    c.add((n - 0.52) * band, 0.26)

    # The sun, barely up, sitting right on the seam.
    sx, sy, sr = 104, 86, 13
    c.glow(sx, sy, 54, 0.5)
    sea(c, horizon, seed=61, chop=0.05, glint_x=sx,
        stops=[(horizon, 0.92), (horizon + 8, 0.66), (horizon + 26, 0.50),
               (horizon + 44, 0.34), (SCREEN_H, 0.24)])
    c.snap(0.72)
    disc = c.mask(lambda d: d.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=255))
    c.flat(disc, 0).no_dither(disc)
    c.waves(horizon + 4, SCREEN_H - 2, 30, 62, value=L_WHITE, min_len=4, max_len=26)

    # The point, and the tower she either kept or lost.
    c.poly([(0, horizon + 4), (14, horizon - 6), (30, horizon - 12), (44, horizon - 7),
            (56, horizon + 3), (64, horizon + 12), (0, horizon + 20)], 3)
    lighthouse(c, 29, horizon - 10, horizon - 54, 6, 4, lit=False,
               bands=((46, 51, 1),))

    # Gulls: three dashes, which is all a gull needs at this size.
    for (gx, gy) in ((70, 34), (84, 26), (58, 44), (96, 40)):
        c.line([(gx, gy + 1), (gx + 2, gy)], 3)
        c.line([(gx + 2, gy), (gx + 4, gy + 1)], 3)

    # One palette only: a second one around the sun would announce itself as a
    # hard rectangle, because attributes are per 8x8 cell.
    pal = np.zeros((SCREEN_H, SCREEN_W), dtype=np.uint8)
    return c, pal, [PAL_DAWN], BGP_STD
