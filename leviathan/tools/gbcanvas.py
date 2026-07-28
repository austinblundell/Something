"""
gbcanvas.py -- a small painting library for four-shade Game Boy artwork.

Paint in continuous luminance (0.0 black .. 1.0 white) with ordinary 2D
primitives, then run one ordered-dither pass at the end to land on the DMG's
four shades.  Every pixel also carries a *dither strength*: 1.0 lets the Bayer
matrix break the value into stipple, 0.0 snaps it to the nearest shade.  Flat
art -- silhouettes, lettering, rim lights -- is painted with strength 0 so it
stays razor sharp, while skies, water and the moon's limb are painted with
strength 1 so they break into clean stipple gradients.

Shapes are rasterised 4x oversampled and thresholded at 50% coverage, which
gives smooth curves without ever introducing a fifth grey.

Everything is deterministic: seeds are explicit, no wall-clock input, so the
generator reproduces byte-identical output.
"""

import numpy as np
from PIL import Image, ImageDraw

W, H = 160, 144
SS = 4  # oversampling factor for shape rasterisation

# The four shades as luminance.
BLACK, DARK, LIGHT, WHITE = 0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0

# The original DMG's four greens, darkest first.
DMG_PALETTE = [
    (0x0F, 0x38, 0x0F),
    (0x30, 0x62, 0x30),
    (0x8B, 0xAC, 0x0F),
    (0x9B, 0xBC, 0x0F),
]

# 8x8 Bayer matrix normalised to (0,1).
_BAYER = np.array([
    [0, 32, 8, 40, 2, 34, 10, 42],
    [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44, 4, 36, 14, 46, 6, 38],
    [60, 28, 52, 20, 62, 30, 54, 22],
    [3, 35, 11, 43, 1, 33, 9, 41],
    [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47, 7, 39, 13, 45, 5, 37],
    [63, 31, 55, 23, 61, 29, 53, 21],
], dtype=np.float32)
_BAYER = (_BAYER + 0.5) / 64.0


# --------------------------------------------------------------- rasterising

def raster(draw_fn, w=W, h=H):
    """Rasterise a shape 4x oversampled, return per-pixel coverage in 0..1."""
    img = Image.new('L', (w * SS, h * SS), 0)
    draw_fn(ImageDraw.Draw(img), SS)
    a = np.asarray(img, dtype=np.float32).reshape(h, SS, w, SS)
    return a.mean(axis=(1, 3)) / 255.0


def hard(cov):
    """Coverage -> boolean mask at the 50% threshold."""
    return cov > 0.5


def poly(points, holes=()):
    """Filled polygon, optional polygonal holes punched out of it."""
    def fn(d, s):
        d.polygon([(x * s, y * s) for x, y in points], fill=255)
        for h in holes:
            d.polygon([(x * s, y * s) for x, y in h], fill=0)
    return raster(fn)


def rect(x0, y0, x1, y1):
    return poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def disc(cx, cy, rx, ry=None):
    ry = rx if ry is None else ry
    return raster(lambda d, s: d.ellipse(
        [(cx - rx) * s, (cy - ry) * s, (cx + rx) * s, (cy + ry) * s], fill=255))


def discs(items):
    """Union of many ellipses in one pass -- (cx, cy, rx, ry) tuples."""
    def fn(d, s):
        for cx, cy, rx, ry in items:
            d.ellipse([(cx - rx) * s, (cy - ry) * s,
                       (cx + rx) * s, (cy + ry) * s], fill=255)
    return raster(fn)


def stroke(points, width):
    return raster(lambda d, s: d.line(
        [(x * s, y * s) for x, y in points], fill=255, width=max(1, int(width * s))))


# ------------------------------------------------------------------- splines

def spline(ctrl, n=400):
    """Catmull-Rom through the control points, sampled to n points."""
    P = np.asarray(ctrl, dtype=np.float64)
    P = np.vstack([P[0] + (P[0] - P[1]), P, P[-1] + (P[-1] - P[-2])])
    segs = len(P) - 3
    per = max(2, n // segs)
    out = []
    for i in range(segs):
        p0, p1, p2, p3 = P[i:i + 4]
        t = np.linspace(0.0, 1.0, per, endpoint=(i == segs - 1))[:, None]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t
                          + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    return np.vstack(out)


def normals(path):
    """Unit normals along a sampled path."""
    t = np.gradient(path, axis=0)
    t /= np.maximum(np.hypot(t[:, 0], t[:, 1]), 1e-9)[:, None]
    return np.stack([-t[:, 1], t[:, 0]], axis=1)


def ribbon(path, radii):
    """A variable-width band swept along a path, with round caps."""
    n = normals(path)
    r = np.asarray(radii, dtype=np.float64)[:, None]
    left = path + n * r
    right = path - n * r
    outline = np.vstack([left, right[::-1]])
    cov = poly([tuple(p) for p in outline])
    caps = discs([(path[0, 0], path[0, 1], r[0, 0], r[0, 0]),
                  (path[-1, 0], path[-1, 1], r[-1, 0], r[-1, 0])])
    return np.maximum(cov, caps)


def taper(n, *stops):
    """Piecewise-linear radius profile: taper(n, (0,9), (0.5,11), (1,4))."""
    xs = np.array([s[0] for s in stops], dtype=np.float64)
    ys = np.array([s[1] for s in stops], dtype=np.float64)
    return np.interp(np.linspace(0, 1, n), xs, ys)


# ----------------------------------------------------------- mask arithmetic

def neighbour(mask, dy, dx):
    """Array N where N[y,x] == mask[y+dy, x+dx] (False off-canvas)."""
    out = np.zeros_like(mask, dtype=bool)
    ys = slice(max(0, -dy), H - max(0, dy))
    xs = slice(max(0, -dx), W - max(0, dx))
    yd = slice(max(0, dy), H - max(0, -dy))
    xd = slice(max(0, dx), W - max(0, -dx))
    out[ys, xs] = mask[yd, xd]
    return out


def dilate(mask, r=1):
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= neighbour(mask, dy, dx)
    return out


def edge(mask, dirs):
    """Pixels of mask whose neighbour in any of dirs lies outside it."""
    out = np.zeros_like(mask, dtype=bool)
    for dy, dx in dirs:
        out |= mask & ~neighbour(mask, dy, dx)
    return out


def outline(mask, r=1):
    return dilate(mask, r) & ~mask


# -------------------------------------------------------------------- canvas

class Canvas:
    def __init__(self, fill=BLACK):
        self.L = np.full((H, W), float(fill), dtype=np.float32)
        self.d = np.ones((H, W), dtype=np.float32)

    def paint(self, mask, value, dither=0.0):
        """Set luminance where mask is true (mask may be bool or coverage)."""
        m = hard(mask) if mask.dtype != bool else mask
        self.L[m] = value if np.isscalar(value) else np.asarray(value)[m]
        self.d[m] = dither

    def blend(self, amount, value, dither=None):
        """Blend towards value by a 0..1 per-pixel amount."""
        a = np.clip(amount, 0.0, 1.0).astype(np.float32)
        self.L = self.L * (1 - a) + np.float32(value) * a
        if dither is not None:
            self.d = np.where(a > 0.5, np.float32(dither), self.d)

    def shade(self, mask, delta):
        """Add to luminance inside a mask, keeping the existing dither."""
        m = hard(mask) if mask.dtype != bool else mask
        self.L[m] = np.clip(self.L[m] + delta, 0.0, 1.0)

    # ------------------------------------------------------------ resolving
    def indices(self):
        """Quantise to shade indices 0 (darkest) .. 3 (lightest)."""
        bayer = np.tile(_BAYER, (H // 8 + 1, W // 8 + 1))[:H, :W]
        wobble = (bayer - 0.5) * (1.0 / 3.0) * self.d
        return np.clip(np.rint((self.L + wobble) * 3.0), 0, 3).astype(np.uint8)

    def image(self, scale=1):
        idx = self.indices()
        img = Image.fromarray(idx, mode='P')
        pal = []
        for c in DMG_PALETTE:
            pal.extend(c)
        img.putpalette(pal + [0, 0, 0] * (256 - len(DMG_PALETTE)))
        if scale > 1:
            img = img.resize((W * scale, H * scale), Image.NEAREST)
        return img


# ----------------------------------------------------------- tile conversion

def to_tiles(idx):
    """Pack shade indices into DMG 2bpp tiles; return (tiledata, tilemap)."""
    seen, data, tmap = {}, bytearray(), []
    for ty in range(H // 8):
        for tx in range(W // 8):
            block = 3 - idx[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8]  # 0=white
            raw = bytearray()
            for row in block:
                lo = hi = 0
                for px in row:
                    lo = (lo << 1) | (int(px) & 1)
                    hi = (hi << 1) | ((int(px) >> 1) & 1)
                raw += bytes((lo, hi))
            key = bytes(raw)
            if key not in seen:
                seen[key] = len(seen)
                data += raw
            tmap.append(seen[key])
    # A background map entry is one byte, so the map packs to bytes when the
    # screen fits in 256 tiles; past that it is emitted as 16-bit indices and
    # the display needs the split described in split_plan().
    if len(seen) <= 256:
        packed = bytes(i & 0xFF for i in tmap)
    else:
        packed = b''.join(int(i).to_bytes(2, 'little') for i in tmap)
    return bytes(data), packed, tmap, len(seen)


def split_plan(tmap):
    """Can this screen be shown on a DMG, and how?

    A background map entry is 8 bits, so only 256 tiles are addressable at
    once: LCDC bit 4 picks between $8000 (tiles 0..255, unsigned) and $8800
    (tiles 128..383, signed).  Rewriting that bit from an LCD STAT interrupt
    part way down the frame gives the top and bottom of the screen different
    windows onto the same 384 tiles.

    Returns the tile row to switch at and the three bucket sizes, or None if
    no split works.  Feasibility at row r: neither half may want more than
    256 tiles, no more than 128 may be needed by both halves (only 128..255
    is reachable from either base), and the union must fit in 384.
    """
    tw = W // 8
    best = None
    for r in range(1, H // 8):
        top = set(tmap[:r * tw])
        bot = set(tmap[r * tw:])
        both = top & bot
        if (len(top) <= 256 and len(bot) <= 256 and len(both) <= 128
                and len(top | bot) <= 384):
            slack = 128 - len(both)
            if best is None or slack > best[3]:
                best = (r, len(top - bot), len(bot - top), slack, len(both))
    if best is None:
        return None
    return {'row': best[0], 'top_only': best[1], 'bottom_only': best[2],
            'shared': best[4]}
