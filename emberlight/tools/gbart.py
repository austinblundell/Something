"""
gbart.py -- a tiny painting library aimed at 4-shade Game Boy artwork.

The idea: paint in *continuous* luminance (0.0 black .. 1.0 white) using
ordinary 2D primitives, then run one ordered-dither pass at the very end to
land on the Game Boy's four shades.  Flat areas painted with exact quarter
values (0, 1/3, 2/3, 1) survive the dither untouched, so hard silhouettes
stay crisp while skies and water break into clean stipple gradients.

Everything is deterministic -- seeds are explicit, no wall-clock input --
so `make` reproduces byte-identical assets.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SCREEN_W = 160
SCREEN_H = 144

# The four Game Boy shades as luminance, lightest first.
L_WHITE = 1.0
L_LIGHT = 2.0 / 3.0
L_DARK = 1.0 / 3.0
L_BLACK = 0.0
SHADES = (L_WHITE, L_LIGHT, L_DARK, L_BLACK)

# 8x8 Bayer matrix, normalised to (0,1).
_BAYER8 = np.array([
    [0, 32, 8, 40, 2, 34, 10, 42],
    [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44, 4, 36, 14, 46, 6, 38],
    [60, 28, 52, 20, 62, 30, 54, 22],
    [3, 35, 11, 43, 1, 33, 9, 41],
    [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47, 7, 39, 13, 45, 5, 37],
    [63, 31, 55, 23, 61, 29, 53, 21],
], dtype=np.float32)
_BAYER8 = (_BAYER8 + 0.5) / 64.0

# A 4x4 Bayer for coarser, more visible stipple (used on water).
_BAYER4 = np.array([
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
], dtype=np.float32)
_BAYER4 = (_BAYER4 + 0.5) / 16.0


def _tile_to(mat, h, w):
    ry = -(-h // mat.shape[0])
    rx = -(-w // mat.shape[1])
    return np.tile(mat, (ry, rx))[:h, :w]


class Canvas:
    def __init__(self, w=SCREEN_W, h=SCREEN_H, fill=L_WHITE):
        self.w = w
        self.h = h
        self.L = np.full((h, w), float(fill), dtype=np.float32)
        self.dither = np.full((h, w), 1.0, dtype=np.float32)

    # ---------------------------------------------------------------- masks
    def mask(self, fn):
        """Build a boolean mask by drawing into a PIL canvas."""
        img = Image.new('L', (self.w, self.h), 0)
        fn(ImageDraw.Draw(img))
        return np.array(img, dtype=np.uint8) > 127

    def soft_mask(self, fn, blur=2.0):
        """Build a 0..1 float coverage mask, blurred at the edges."""
        img = Image.new('L', (self.w, self.h), 0)
        fn(ImageDraw.Draw(img))
        if blur > 0:
            img = img.filter(ImageFilter.GaussianBlur(blur))
        return np.array(img, dtype=np.float32) / 255.0

    # ------------------------------------------------------------ painting
    def paint(self, mask, value):
        """Set luminance inside a boolean mask (value may be an array)."""
        if np.isscalar(value):
            self.L[mask] = value
        else:
            self.L[mask] = np.asarray(value, dtype=np.float32)[mask]
        return self

    def blend(self, cov, value):
        """Alpha-blend `value` over the canvas using a 0..1 coverage array."""
        v = np.full_like(self.L, value) if np.isscalar(value) else np.asarray(value, np.float32)
        self.L = self.L * (1.0 - cov) + v * cov
        return self

    def shade(self, mask, factor):
        self.L[mask] = np.clip(self.L[mask] * factor, 0.0, 1.0)
        return self

    def lift(self, mask, amount):
        self.L[mask] = np.clip(self.L[mask] + amount, 0.0, 1.0)
        return self

    def add(self, arr, scale=1.0):
        self.L = np.clip(self.L + np.asarray(arr, np.float32) * scale, 0.0, 1.0)
        return self

    def mul(self, arr):
        self.L = np.clip(self.L * np.asarray(arr, np.float32), 0.0, 1.0)
        return self

    def flat(self, mask, shade_index):
        """Paint an exact Game Boy shade (0=white .. 3=black): dither-proof."""
        return self.paint(mask, SHADES[shade_index])

    def no_dither(self, mask):
        self.dither[mask] = 0.0
        return self

    # ----------------------------------------------------------- gradients
    def grad_v(self, y0, y1, v0, v1, ease=1.0):
        """Vertical gradient array spanning the whole width."""
        ys = np.arange(self.h, dtype=np.float32)
        t = np.clip((ys - y0) / max(1e-6, (y1 - y0)), 0.0, 1.0)
        if ease != 1.0:
            t = t ** ease
        col = v0 + (v1 - v0) * t
        return np.repeat(col[:, None], self.w, axis=1)

    def grad_h(self, x0, x1, v0, v1, ease=1.0):
        xs = np.arange(self.w, dtype=np.float32)
        t = np.clip((xs - x0) / max(1e-6, (x1 - x0)), 0.0, 1.0)
        if ease != 1.0:
            t = t ** ease
        row = v0 + (v1 - v0) * t
        return np.repeat(row[None, :], self.h, axis=0)

    def ramp_v(self, stops):
        """Piecewise-linear vertical ramp from [(y, value), ...] breakpoints.

        Lets a scene state its whole value plan up front -- where the black
        sits, where the bright horizon seam goes -- instead of fighting a
        single linear gradient.
        """
        ys = np.array([s[0] for s in stops], dtype=np.float32)
        vs = np.array([s[1] for s in stops], dtype=np.float32)
        col = np.interp(np.arange(self.h, dtype=np.float32), ys, vs).astype(np.float32)
        return np.repeat(col[:, None], self.w, axis=1)

    def grad_r(self, cx, cy, r0, r1, v0, v1, squash=1.0):
        yy, xx = np.mgrid[0:self.h, 0:self.w].astype(np.float32)
        d = np.sqrt((xx - cx) ** 2 + ((yy - cy) * squash) ** 2)
        t = np.clip((d - r0) / max(1e-6, (r1 - r0)), 0.0, 1.0)
        return v0 + (v1 - v0) * t

    # -------------------------------------------------------------- noise
    def noise(self, seed, cells=8, octaves=4, persistence=0.5):
        """Fractal value noise in 0..1, smoothly interpolated."""
        rng = np.random.default_rng(seed)
        total = np.zeros((self.h, self.w), dtype=np.float32)
        amp = 1.0
        norm = 0.0
        c = cells
        for _ in range(octaves):
            gw = max(2, int(c))
            gh = max(2, int(c * self.h / self.w)) if self.w else gw
            grid = rng.random((gh, gw)).astype(np.float32)
            up = Image.fromarray((grid * 255).astype(np.uint8), 'L')
            up = up.resize((self.w, self.h), Image.BICUBIC)
            total += np.array(up, dtype=np.float32) / 255.0 * amp
            norm += amp
            amp *= persistence
            c *= 2
        out = total / max(1e-6, norm)
        return np.clip(out, 0.0, 1.0)

    # ---------------------------------------------------------- primitives
    def rect(self, box, shade_index=None, value=None):
        m = self.mask(lambda d: d.rectangle(box, fill=255))
        return self.paint(m, SHADES[shade_index] if shade_index is not None else value)

    def poly(self, pts, shade_index=None, value=None):
        m = self.mask(lambda d: d.polygon(pts, fill=255))
        return self.paint(m, SHADES[shade_index] if shade_index is not None else value)

    def ellipse(self, box, shade_index=None, value=None):
        m = self.mask(lambda d: d.ellipse(box, fill=255))
        return self.paint(m, SHADES[shade_index] if shade_index is not None else value)

    def line(self, pts, shade_index=None, value=None, width=1):
        m = self.mask(lambda d: d.line(pts, fill=255, width=width))
        return self.paint(m, SHADES[shade_index] if shade_index is not None else value)

    def outline(self, box_or_pts, shade_index, width=1, kind='rect'):
        def draw(d):
            if kind == 'rect':
                d.rectangle(box_or_pts, outline=255, width=width)
            elif kind == 'ellipse':
                d.ellipse(box_or_pts, outline=255, width=width)
            else:
                d.polygon(box_or_pts, outline=255)
        return self.paint(self.mask(draw), SHADES[shade_index])

    # -------------------------------------------------------------- effects
    def glow(self, cx, cy, radius, strength=0.55, squash=1.0):
        """Additive halo -- reads as light spilling into the scene."""
        g = 1.0 - self.grad_r(cx, cy, 0, radius, 0.0, 1.0, squash=squash)
        return self.add(g ** 2, strength)

    def vignette(self, strength=0.35, radius=None):
        r = radius or (max(self.w, self.h) * 0.78)
        g = self.grad_r(self.w / 2, self.h / 2, r * 0.35, r, 0.0, 1.0)
        return self.mul(1.0 - g * strength)

    def stars(self, count, seed, y_max=None, x_range=None, value=L_WHITE, avoid=None):
        rng = np.random.default_rng(seed)
        y_max = self.h if y_max is None else y_max
        x0, x1 = x_range or (0, self.w)
        for _ in range(count):
            x = int(rng.integers(x0, x1))
            y = int(rng.integers(0, y_max))
            if avoid is not None and avoid[y, x]:
                continue
            self.L[y, x] = value
            self.dither[y, x] = 0.0
        return self

    def reflect(self, src_y0, src_y1, dst_y0, amp=2.0, freq=0.22, fade=0.55,
                seed=7, phase=0.0):
        """Mirror a band downward with a horizontal wobble: water reflection."""
        band = self.L[src_y0:src_y1].copy()[::-1]
        bh = band.shape[0]
        rng = np.random.default_rng(seed)
        jitter = rng.random(bh).astype(np.float32) * 0.8
        for i in range(bh):
            dy = dst_y0 + i
            if dy < 0 or dy >= self.h:
                continue
            off = int(round(np.sin(i * freq + phase + jitter[i]) * amp))
            row = np.roll(band[i], off)
            k = fade + (1.0 - fade) * (1.0 - i / max(1, bh - 1))
            # Pull the reflection toward mid-grey as it sinks.
            self.L[dy] = np.clip(row * k + L_DARK * (1.0 - k) * 0.9, 0.0, 1.0)
        return self

    def snap(self, strength=0.72, mask=None):
        """Push luminance toward the four exact shades.

        A plain gradient dithers across its whole span, which on a 4-shade
        display reads as one big field of noise.  Sharpening the fractional
        part collapses most of the span into flat bands and leaves only a
        narrow stipple seam where shades meet -- the poster look real Game Boy
        art uses, and far kinder to the tile budget.
        """
        s = np.clip(self.L, 0.0, 1.0) * 3.0
        base = np.floor(s)
        frac = s - base
        width = max(1e-3, 1.0 - strength)
        frac = np.clip((frac - 0.5) / width + 0.5, 0.0, 1.0)
        out = np.clip((base + frac) / 3.0, 0.0, 1.0)
        self.L = out if mask is None else np.where(mask, out, self.L)
        return self

    def waves(self, y0, y1, count, seed, value=L_WHITE, min_len=6, max_len=26):
        """Crisp horizontal dashes: catch-lights on open water."""
        rng = np.random.default_rng(seed)
        for _ in range(count):
            y = int(rng.integers(y0, y1))
            t = (y - y0) / max(1, y1 - y0)
            ln = int(min_len + (max_len - min_len) * t * rng.random())
            x = int(rng.integers(0, max(1, self.w - ln)))
            self.L[y, x:x + ln] = value
            self.dither[y, x:x + ln] = 0.0
        return self

    def scanlines(self, y0, y1, factor=0.86, step=2):
        for y in range(y0, min(y1, self.h), step):
            self.L[y] = np.clip(self.L[y] * factor, 0.0, 1.0)
        return self

    def hatch(self, mask, value, spacing=3, slope=1):
        yy, xx = np.mgrid[0:self.h, 0:self.w]
        lines = ((xx + yy * slope) % spacing) == 0
        return self.paint(mask & lines, value)

    # ---------------------------------------------------------------- text
    def text(self, s, x, y, shade_index=3, tracking=6, scale=1, shadow=None):
        from gbfont import draw_text
        if shadow is not None:
            pts = []
            draw_text(lambda px, py: pts.append((px, py)), s, x + 1, y + 1,
                      tracking, scale)
            for px, py in pts:
                if 0 <= px < self.w and 0 <= py < self.h:
                    self.L[py, px] = SHADES[shadow]
                    self.dither[py, px] = 0.0
        pts = []
        draw_text(lambda px, py: pts.append((px, py)), s, x, y, tracking, scale)
        for px, py in pts:
            if 0 <= px < self.w and 0 <= py < self.h:
                self.L[py, px] = SHADES[shade_index]
                self.dither[py, px] = 0.0
        return self

    def text_center(self, s, y, **kw):
        # `tracking` is the unscaled advance; draw_text multiplies it by scale.
        tracking = kw.get('tracking', 6)
        scale = kw.get('scale', 1)
        wpx = len(s) * tracking * scale - (tracking - 5) * scale
        return self.text(s, (self.w - wpx) // 2, y, **kw)

    # ------------------------------------------------------------ quantise
    def quantize(self, matrix=_BAYER8):
        """Return an (h, w) uint8 array of Game Boy colour indices 0..3."""
        thresh = _tile_to(matrix, self.h, self.w)
        s = np.clip(self.L, 0.0, 1.0) * 3.0
        base = np.floor(s)
        frac = s - base
        bump = (frac > (thresh * self.dither + (1.0 - self.dither) * 0.5))
        level = np.clip(base + bump, 0, 3).astype(np.uint8)
        return (3 - level).astype(np.uint8)   # GB index: 0 = lightest


# --------------------------------------------------------------------------
#  preview rendering
# --------------------------------------------------------------------------

# A classic DMG green ramp, plus a neutral ramp, for progress screenshots.
DMG_GREEN = [(0xE0, 0xF8, 0xD0), (0x88, 0xC0, 0x70), (0x34, 0x68, 0x56), (0x08, 0x18, 0x20)]
DMG_GREY = [(0xFF, 0xFF, 0xFF), (0xAA, 0xAA, 0xAA), (0x55, 0x55, 0x55), (0x00, 0x00, 0x00)]


def indices_to_image(idx, palette=DMG_GREEN, scale=1):
    h, w = idx.shape
    out = np.zeros((h, w, 3), dtype=np.uint8)
    for i, rgb in enumerate(palette):
        out[idx == i] = rgb
    img = Image.fromarray(out, 'RGB')
    if scale != 1:
        img = img.resize((w * scale, h * scale), Image.NEAREST)
    return img
