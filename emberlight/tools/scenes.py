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


def cloudscape(c, y0, y1, seed, cells=9, octaves=3, aspect=3.2,
               thresholds=(0.62, 0.50), shades=(1, 2, 3), rim=None,
               pile=0.16, keep_sky=True):
    """Layered storm cloud, thresholded into three flat tones.

    Two things stop this reading as camouflage: the noise is stretched wide,
    so masses run along the sky rather than sitting in it, and the threshold
    is biased by height, so cloud piles up toward the horizon and thins out
    overhead.  Flat tones also cost far fewer tiles than dithered noise.
    """
    n = c.noise(seed, cells=cells, octaves=octaves, aspect=aspect)
    ys = np.arange(SCREEN_H, dtype=np.float32)[:, None]
    t = np.clip((ys - y0) / max(1.0, y1 - y0), 0.0, 1.0)
    bias = (0.5 - t) * pile * 2.0          # positive high up = less cloud
    inside = np.zeros((SCREEN_H, SCREEN_W), dtype=bool)
    inside[y0:y1] = True

    hi, mid = thresholds
    bright = inside & (n > (hi + bias))
    midtone = inside & (n > (mid + bias)) & ~bright
    c.flat(bright, shades[0])
    c.flat(midtone, shades[1])
    if not keep_sky:
        c.flat(inside & ~bright & ~midtone, shades[2])
    if rim is not None:
        above = np.zeros_like(bright)
        above[1:] = bright[1:] & ~bright[:-1]
        c.flat(above, rim)
    return n


def lantern(c, x, y, halo=16, strength=0.75, core=2):
    """A small hard light with a tight halo.

    A wide radial glow quantises into a grey lozenge; keeping the halo small
    and the core pure white is what makes it read as a flame.
    """
    c.glow(x, y, halo, strength)
    box = (x - core, y - core, x + core, y + core)
    m = c.mask(lambda d: d.rectangle(box, fill=255))
    c.flat(m, 0).no_dither(m)
    ring = c.mask(lambda d: d.rectangle(
        (x - core - 1, y - core - 1, x + core + 1, y + core + 1),
        outline=255, width=1))
    c.flat(ring & ~m, 1)
    return c


def light_path(c, x, y_top, y_bot, half_top=2, half_bot=13, strength=0.6,
               blur=3.0):
    """The column a light throws down open water toward the viewer."""
    cov = c.soft_mask(lambda d: d.polygon(
        [(x - half_top, y_top), (x + half_top, y_top),
         (x + half_bot, y_bot), (x - half_bot, y_bot)], fill=255), blur=blur)
    fade = c.grad_v(y_top, y_bot, strength, strength * 0.2)
    return c.blend(cov * fade, L_WHITE)


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
    spray = c.soft_mask(lambda d: d.ellipse((14, 100, 64, 128), fill=255), blur=4.0)
    c.blend(spray * 0.45, L_WHITE)
    c.snap(0.66, mask=c.mask(lambda d: d.ellipse((10, 96, 70, 132), fill=255)))
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
    horizon = 62

    # Value plan: black sky, a bright seam at the waterline, then broad dark
    # water so the rooftops and the lantern have something to sit against.
    c.L[:] = c.ramp_v([(0, 0.00), (30, 0.02), (44, 0.28), (61, 0.32)])
    mx, my, mr = 40, 26, 14
    c.glow(mx, my, 34, 0.14)
    sea(c, horizon, seed=91, chop=0.06,
        stops=[(horizon, 0.62), (horizon + 4, 0.32), (horizon + 30, 0.24),
               (horizon + 56, 0.10), (SCREEN_H, 0.03)])
    c.snap(0.78)
    seam = c.mask(lambda d: d.rectangle((0, horizon - 2, SCREEN_W, horizon - 1), fill=255))
    c.flat(seam, 0).no_dither(seam)
    c.stars(44, 55, y_max=44)
    c.waves(horizon + 3, SCREEN_H - 4, 52, 77, min_len=3, max_len=26)

    disc = c.mask(lambda d: d.ellipse((mx - mr, my - mr, mx + mr, my + mr), fill=255))
    c.flat(disc, 0).no_dither(disc)
    for box in ((mx - 7, my - 6, mx - 1, my), (mx + 2, my + 3, mx + 9, my + 10)):
        c.flat(c.mask(lambda d, b=box: d.ellipse(b, fill=255)) & disc, 1)
    light_path(c, mx, horizon, SCREEN_H, half_top=3, half_bot=22, strength=0.28)

    # The far point, still holding its light, small and a long way off.
    sine_poly(c, horizon - 4, 2, 0.035, 0.6, 3, crest_shade=2,
              bottom=horizon - 1, amp2=1, freq2=0.12)
    lamp = lighthouse(c, 136, horizon - 3, horizon - 44, 5, 3, lit=True)
    lx, ly = lamp
    beam(c, lx, ly, 10, 3, -20, strength=0.26, reach=180)
    c.glow(lx, ly, 8, 0.85)

    # Rooftops. Each gets a bright waterline where it cuts the surface: that
    # is what makes them read as standing in the water rather than on it.
    def roof(x, w, hgt, y_water):
        c.poly([(x, y_water), (x + w // 2, y_water - hgt), (x + w, y_water)], 3)
        c.line([(x + 1, y_water - 1), (x + w // 2, y_water - hgt)], 1)
        line = c.mask(lambda d: d.rectangle((x - 3, y_water, x + w + 3, y_water), fill=255))
        c.flat(line, 0).no_dither(line)
        for i in range(1, 4):
            yy = y_water + i * 3
            if yy < SCREEN_H:
                c.line([(x + 3 + i * 2, yy), (x + w - 3 - i * 2, yy)], 3)

    roof(6, 40, 19, 96)
    roof(58, 28, 13, 84)
    roof(100, 46, 22, 108)
    c.rect((128, 74, 137, 88), 3)                 # the forge chimney
    c.line([(128, 74), (137, 74)], 1)
    chim = c.mask(lambda d: d.rectangle((124, 88, 141, 88), fill=255))
    c.flat(chim, 0).no_dither(chim)

    # Her boat, close and low, with the lantern on the bow.
    bx, by = 58, 132
    c.poly([(bx - 30, by), (bx + 30, by - 2), (bx + 22, by + 9), (bx - 22, by + 9)], 3)
    c.line([(bx - 30, by), (bx + 30, by - 2)], 1)
    c.line([(bx - 27, by + 3), (bx - 44, by + 11)], 3)
    figure_back(c, bx + 4, by, w=26, h=30, rim=1, light=-1)
    lantern(c, bx - 26, by - 14, halo=17, strength=0.8, core=2)
    c.line([(bx - 26, by - 11), (bx - 26, by - 1)], 3)

    pal = np.zeros((SCREEN_H, SCREEN_W), dtype=np.uint8)
    pal[c.mask(lambda d: d.rectangle((bx - 36, by - 25, bx - 15, by + 4), fill=255))] = 1
    pal[c.mask(lambda d: d.rectangle((lx - 6, ly - 6, lx + 6, ly + 6), fill=255))] = 1
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


def figure_outline(x, base_y, w, h):
    """One closed contour for a hooded figure seen from behind."""
    hw = w // 2
    head_w = max(5, w // 4)
    head_h = int(head_w * 2.1)
    hy = base_y - h
    neck = hy + head_h
    return [(x - hw, base_y),
            (x - hw + 1, neck + 4),
            (x - head_w - 2, neck + 1),
            (x - head_w, hy + 5),
            (x - head_w // 2, hy),
            (x + head_w // 2, hy),
            (x + head_w, hy + 5),
            (x + head_w + 2, neck + 1),
            (x + hw - 1, neck + 4),
            (x + hw, base_y)]


def figure_back(c, x, base_y, w=26, h=42, shade=3, rim=None, light=+1):
    """An over-the-shoulder silhouette: hood, shoulders, no face.

    The rim is drawn by stamping the same contour one pixel toward the light
    and then the solid figure on top.  A flat black shape against a flat black
    sky is invisible; that single lit edge is the whole read.
    """
    pts = figure_outline(x, base_y, w, h)
    if rim is not None:
        c.poly([(px + light, py - 1) for (px, py) in pts], rim)
    c.poly(pts, shade)
    return c


# ==========================================================================
#  5. THE SIGNAL  --  over her shoulder, a light where nothing should be
# ==========================================================================
@scene('signal', bgp=BGP_STD)
def s_signal():
    c = Canvas()
    horizon = 78
    c.L[:] = c.ramp_v([(0, 0.00), (26, 0.02), (54, 0.26), (77, 0.30)])
    cloudscape(c, 0, 74, seed=717, cells=10, aspect=3.6,
               thresholds=(0.66, 0.555), shades=(1, 2), rim=0, pile=0.18)
    sea(c, horizon, seed=311, chop=0.07,
        stops=[(horizon, 0.50), (horizon + 6, 0.28), (horizon + 24, 0.16),
               (SCREEN_H, 0.03)])
    c.snap(0.78)
    seam = c.mask(lambda d: d.rectangle((0, horizon - 1, SCREEN_W, horizon - 1), fill=255))
    c.flat(seam, 1).no_dither(seam)
    c.waves(horizon + 3, 116, 30, 313, min_len=3, max_len=18)

    # The signal: one small hard light, and its long reach across the water.
    sx, sy = 122, 74
    light_path(c, sx, horizon, SCREEN_H - 6, half_top=2, half_bot=16, strength=0.55)
    lantern(c, sx, sy, halo=15, strength=0.8, core=1)

    for i in range(30):
        rng = np.random.default_rng(2200 + i)
        x = int(rng.integers(-6, SCREEN_W))
        y = int(rng.integers(0, 104))
        c.line([(x, y), (x + 3, y + 8)], 0)

    # The prow of her father's boat, and her back filling the near frame.
    c.poly([(0, SCREEN_H), (0, 126), (52, 114), (104, 121), (120, SCREEN_H)], 3)
    c.line([(0, 126), (52, 114), (104, 121)], 1)
    figure_back(c, 48, 128, w=46, h=64, rim=1, light=+1)

    pal = np.zeros((SCREEN_H, SCREEN_W), dtype=np.uint8)
    pal[c.mask(lambda d: d.rectangle((sx - 9, sy - 9, sx + 9, sy + 9), fill=255))] = 1
    return c, pal, [PAL_STORM, PAL_LAMP], BGP_STD


# ==========================================================================
#  6. RESCUE  --  four men alive, and a tower going dark behind her
# ==========================================================================
@scene('rescue', bgp=BGP_STD)
def s_rescue():
    c = Canvas()
    horizon = 58
    c.L[:] = c.ramp_v([(0, 0.00), (22, 0.03), (44, 0.26), (57, 0.30)])
    cloudscape(c, 0, 54, seed=515, cells=10, aspect=3.4,
               thresholds=(0.65, 0.545), shades=(1, 2), rim=0, pile=0.18)
    sea(c, horizon, seed=99, chop=0.09,
        stops=[(horizon, 0.52), (horizon + 8, 0.30), (horizon + 30, 0.18),
               (SCREEN_H, 0.04)])
    c.snap(0.76)
    seam = c.mask(lambda d: d.rectangle((0, horizon - 1, SCREEN_W, horizon - 1), fill=255))
    c.flat(seam, 1).no_dither(seam)
    c.waves(horizon + 3, 128, 34, 555, min_len=4, max_len=22)

    # The point, far off on the left. The tower is a stump of black: no lamp.
    c.poly([(0, horizon + 4), (12, horizon - 4), (26, horizon), (34, horizon + 7),
            (0, horizon + 13)], 3)
    lighthouse(c, 15, horizon - 1, horizon - 30, 4, 3, lit=False)

    # One long swell so the two boats sit in a trough rather than on a field
    # of competing crests.
    sine_poly(c, 92, 7, 0.040, 0.4, 2, crest_shade=0, amp2=3, freq2=0.13)

    # Their boat, crowded, with the storm lantern they kept swinging.
    # A lit patch of water goes down first: four black figures on black water
    # is a smudge, the same four against a pale trough is a rescue.
    bx, by = 100, 104
    behind = c.soft_mask(lambda d: d.ellipse((bx - 44, by - 34, bx + 46, by + 6),
                                             fill=255), blur=5.0)
    c.blend(behind * 0.40, L_WHITE)
    c.snap(0.70, mask=c.mask(lambda d: d.ellipse(
        (bx - 46, by - 36, bx + 48, by + 8), fill=255)))
    c.poly([(bx - 28, by), (bx + 28, by - 1), (bx + 20, by + 9), (bx - 20, by + 9)], 3)
    c.line([(bx - 28, by), (bx + 28, by - 1)], 1)
    for (dx, hh) in ((-19, 17), (-7, 22), (6, 18), (18, 14)):
        figure_back(c, bx + dx, by, w=10, h=hh, rim=1, light=+1)
    lantern(c, bx + 26, by - 22, halo=19, strength=0.9, core=2)
    c.line([(bx + 26, by - 19), (bx + 26, by - 3)], 3)

    # Her boat, nearer and lower in frame, cutting in from the left.
    sine_poly(c, 122, 6, 0.055, 2.4, 3, crest_shade=1, amp2=2, freq2=0.19)
    c.poly([(0, SCREEN_H), (6, 126), (74, 131), (126, 140), (140, SCREEN_H)], 3)
    c.line([(6, 126), (74, 131), (126, 140)], 1)
    figure_back(c, 40, 136, w=36, h=52, rim=1, light=+1)

    for i in range(30):
        rng = np.random.default_rng(3300 + i)
        x = int(rng.integers(-6, SCREEN_W))
        y = int(rng.integers(0, 92))
        c.line([(x, y), (x + 4, y + 9)], 0)

    pal = np.zeros((SCREEN_H, SCREEN_W), dtype=np.uint8)
    pal[c.mask(lambda d: d.rectangle((bx + 14, by - 34, bx + 38, by - 8), fill=255))] = 1
    return c, pal, [PAL_STORM, PAL_LAMP], BGP_STD



# ==========================================================================
#  7. VIGIL  --  she keeps the light, and watches the signal stop
# ==========================================================================
@scene('vigil', bgp=BGP_STD)
def s_vigil():
    c = Canvas()
    horizon = 88

    # We are standing on the gallery.  The lamp is directly overhead and out
    # of frame, so it arrives as a black roof overhang across the top of the
    # picture with light spilling out from under it -- not as a bright band,
    # which just reads as a sunset.
    c.L[:] = c.ramp_v([(0, 0.00), (34, 0.02), (62, 0.24), (87, 0.30)])
    cloudscape(c, 24, 84, seed=808, cells=11, aspect=3.6,
               thresholds=(0.74, 0.655), shades=(1, 2), rim=None, pile=0.26)
    sea(c, horizon, seed=421, chop=0.07,
        stops=[(horizon, 0.54), (horizon + 5, 0.30), (horizon + 20, 0.18),
               (SCREEN_H, 0.04)])
    c.snap(0.78)
    seam = c.mask(lambda d: d.rectangle((0, horizon - 1, SCREEN_W, horizon - 1), fill=255))
    c.flat(seam, 0).no_dither(seam)
    c.stars(26, 99, y_max=30)
    c.waves(horizon + 3, 116, 22, 423, min_len=3, max_len=16)

    # Far out: the signal, small and stubborn.
    sx, sy = 130, 84
    lantern(c, sx, sy, halo=11, strength=0.7, core=1)

    # The two beams leaving the lamp room above us, and the underside of the
    # gallery roof they pass beneath.
    beam(c, 66, 4, 3, 46, SCREEN_W + 20, strength=0.34, reach=210, blur=3.0)
    beam(c, 66, 4, 3, 34, -24, strength=0.22, reach=150, blur=3.0)
    c.poly([(0, 0), (SCREEN_W, 0), (SCREEN_W, 12), (96, 17), (36, 15), (0, 9)], 3)
    c.line([(0, 9), (36, 15), (96, 17), (SCREEN_W, 12)], 1)

    # The gallery rail in the near frame, and the keeper at it.
    c.rect((0, 118, SCREEN_W, 121), 3)
    c.rect((0, 136, SCREEN_W, 139), 3)
    for x in range(6, SCREEN_W, 13):
        c.rect((x, 120, x + 2, 138), 3)
    c.line([(0, 117), (SCREEN_W, 117)], 1)

    figure_back(c, 44, 142, w=42, h=68, rim=1, light=+1)

    # A full-width band for the lit sky, so no vertical attribute edge gives
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
