"""
tileconv.py -- turn a 160x144 Game Boy index image into VRAM-ready data.

The Game Boy background layer can only see 256 tiles at once, and EMBERLIGHT
spends 64 of those on the font and 16 on sprites, so a full-screen picture has
to fit in 176 unique tiles.  A 20x18 screen is 360 cells, so every picture
needs roughly 2:1 deduplication.

Exact deduplication gets most of the way there (skies and water repeat
heavily).  Whatever is left over is handled by `reduce_to_budget`, which
repeatedly folds the cheapest tile into its nearest surviving neighbour --
cheapest meaning "fewest uses on screen, times how different its replacement
looks".  That makes the fit *guaranteed* for any input, and the quality loss
lands on rare, low-contrast tiles first.
"""

import numpy as np

TILE_W = 8
TILE_H = 8
COLS = 20
ROWS = 18

# ---- VRAM budget ---------------------------------------------------------
ART_BASE = 0            # picture tiles occupy $8000 + 0..175
ART_MAX = 176
FONT_BASE = 176         # ASCII 32..95 -> 176..239
FONT_COUNT = 64
SPRITE_BASE = 240       # 240..255, sixteen tiles for effects and actors
SPRITE_COUNT = 16


def pack_tile(cell):
    """8x8 array of 0..3 -> 16 bytes of Game Boy 2bpp tile data."""
    out = bytearray()
    for y in range(TILE_H):
        lo = 0
        hi = 0
        for x in range(TILE_W):
            v = int(cell[y][x]) & 3
            bit = 7 - x
            lo |= (v & 1) << bit
            hi |= ((v >> 1) & 1) << bit
        out.append(lo)
        out.append(hi)
    return bytes(out)


def pack_1bpp_tile(bitmap, ink=3, paper=0):
    """8x8 array of 0/1 -> 2bpp tile data using two chosen shades."""
    cell = [[ink if bitmap[y][x] else paper for x in range(TILE_W)]
            for y in range(TILE_H)]
    return pack_tile(cell)


def split_tiles(idx):
    """Cut an index image into (rows, cols) tiles. Returns (n,64) int16 array."""
    h, w = idx.shape
    rows, cols = h // TILE_H, w // TILE_W
    cells = np.zeros((rows * cols, TILE_H * TILE_W), dtype=np.int16)
    for ty in range(rows):
        for tx in range(cols):
            block = idx[ty * TILE_H:(ty + 1) * TILE_H, tx * TILE_W:(tx + 1) * TILE_W]
            cells[ty * cols + tx] = block.reshape(-1)
    return cells, rows, cols


def dedup(cells):
    """Exact deduplication. Returns (unique (n,64), cellmap (m,))."""
    uniq = {}
    order = []
    cellmap = np.zeros(len(cells), dtype=np.int32)
    for i, c in enumerate(cells):
        key = c.tobytes()
        j = uniq.get(key)
        if j is None:
            j = len(order)
            uniq[key] = j
            order.append(c)
        cellmap[i] = j
    return np.array(order, dtype=np.int16), cellmap


def reduce_to_budget(uniq, cellmap, budget):
    """Greedily merge tiles until `budget` remain. Returns (uniq, cellmap)."""
    n = len(uniq)
    if n <= budget:
        return uniq, cellmap

    tiles = uniq.astype(np.float32)
    # Pairwise squared pixel distance between every pair of tiles.
    d = ((tiles[:, None, :] - tiles[None, :, :]) ** 2).sum(axis=2)
    np.fill_diagonal(d, np.inf)

    counts = np.bincount(cellmap, minlength=n).astype(np.float64)
    alive = np.ones(n, dtype=bool)
    remap = np.arange(n, dtype=np.int32)
    live = n

    while live > budget:
        # For each living tile, its nearest living replacement.
        dm = d.copy()
        dm[~alive, :] = np.inf
        dm[:, ~alive] = np.inf
        nearest = np.argmin(dm, axis=1)
        best = dm[np.arange(n), nearest]
        # Cost of folding a tile away: how many cells suffer, times how much.
        usable = alive & np.isfinite(best)
        finite_best = np.where(usable, best, 0.0)
        cost = np.where(usable, counts * np.maximum(finite_best, 1e-6), np.inf)
        victim = int(np.argmin(cost))
        target = int(nearest[victim])
        if not np.isfinite(cost[victim]) or not alive[target]:
            break
        remap[remap == victim] = target
        counts[target] += counts[victim]
        counts[victim] = 0
        alive[victim] = False
        live -= 1

    # Compact surviving tiles into a dense index space.
    survivors = np.flatnonzero(alive)
    compact = {int(s): i for i, s in enumerate(survivors)}
    new_uniq = uniq[survivors]
    new_map = np.array([compact[int(remap[c])] for c in cellmap], dtype=np.int32)
    return new_uniq, new_map


def cell_majority(pal, rows, cols):
    """Reduce a per-pixel palette map to one palette index per tile."""
    out = np.zeros(rows * cols, dtype=np.uint8)
    for ty in range(rows):
        for tx in range(cols):
            block = pal[ty * TILE_H:(ty + 1) * TILE_H, tx * TILE_W:(tx + 1) * TILE_W]
            vals, cnt = np.unique(block, return_counts=True)
            out[ty * cols + tx] = vals[int(np.argmax(cnt))]
    return out


class Picture:
    """A converted full-screen picture, ready to be emitted."""

    def __init__(self, name, idx, pal=None, budget=ART_MAX, base=ART_BASE):
        cells, rows, cols = split_tiles(idx)
        uniq, cellmap = dedup(cells)
        self.exact_unique = len(uniq)
        uniq, cellmap = reduce_to_budget(uniq, cellmap, budget)

        self.name = name
        self.rows = rows
        self.cols = cols
        self.base = base
        self.tiles = uniq
        self.cellmap = cellmap
        self.tile_count = len(uniq)
        self.attr = cell_majority(pal, rows, cols) if pal is not None else None

        # Reconstruct exactly what VRAM will show, for previews and review.
        recon = np.zeros_like(idx)
        for ty in range(rows):
            for tx in range(cols):
                t = uniq[cellmap[ty * cols + tx]].reshape(TILE_H, TILE_W)
                recon[ty * TILE_H:(ty + 1) * TILE_H, tx * TILE_W:(tx + 1) * TILE_W] = t
        self.recon = recon

    def tile_bytes(self):
        out = bytearray()
        for t in self.tiles:
            out += pack_tile(t.reshape(TILE_H, TILE_W))
        return bytes(out)

    def map_bytes(self):
        return bytes(int(self.base + c) & 0xFF for c in self.cellmap)

    def attr_bytes(self):
        return bytes(int(a) & 0x07 for a in self.attr) if self.attr is not None else None


# --------------------------------------------------------------------------
#  RGBASM emission
# --------------------------------------------------------------------------

def db_block(data, indent='    ', per_line=16):
    lines = []
    for i in range(0, len(data), per_line):
        chunk = data[i:i + per_line]
        lines.append(indent + 'db ' + ','.join('$%02X' % b for b in chunk))
    return '\n'.join(lines)


def dw_block(words, indent='    ', per_line=8):
    lines = []
    for i in range(0, len(words), per_line):
        chunk = words[i:i + per_line]
        lines.append(indent + 'dw ' + ','.join('$%04X' % w for w in chunk))
    return '\n'.join(lines)


def rgb555(r, g, b):
    """Pack 8-bit RGB into Game Boy Color BGR555."""
    return ((r >> 3) & 31) | (((g >> 3) & 31) << 5) | (((b >> 3) & 31) << 10)


def emit_picture(pic, palettes, bgp, obp0=0xE4, section=None, bank=None):
    """Render one picture (plus its descriptor) as RGBASM source text."""
    n = pic.name
    sec = section or ('"pic %s"' % n)
    where = 'ROMX' if bank is None else 'ROMX, BANK[%d]' % bank
    L = []
    L.append('; ==========================================================')
    L.append(';  %s  --  %d unique tiles (%d before budget merge)'
             % (n, pic.tile_count, pic.exact_unique))
    L.append('; ==========================================================')
    L.append('SECTION %s, %s' % (sec, where))
    L.append('')
    L.append('pic_%s::' % n)
    L.append('    db  %d                  ; tile count' % pic.tile_count)
    L.append('    db  %d                  ; first VRAM tile' % pic.base)
    L.append('    dw  pic_%s_tiles' % n)
    L.append('    dw  pic_%s_map' % n)
    L.append('    dw  %s' % ('pic_%s_attr' % n if pic.attr is not None else '0'))
    L.append('    dw  %s' % ('pic_%s_pal' % n if palettes else '0'))
    L.append('    db  %d                  ; CGB palette count' % len(palettes))
    L.append('    db  $%02X                ; DMG BGP' % bgp)
    L.append('    db  $%02X                ; DMG OBP0' % obp0)
    L.append('')
    L.append('pic_%s_tiles::' % n)
    L.append(db_block(pic.tile_bytes()))
    L.append('')
    L.append('pic_%s_map::' % n)
    L.append(db_block(pic.map_bytes(), per_line=20))
    L.append('')
    if pic.attr is not None:
        L.append('pic_%s_attr::' % n)
        L.append(db_block(pic.attr_bytes(), per_line=20))
        L.append('')
    if palettes:
        L.append('pic_%s_pal::' % n)
        words = []
        for p in palettes:
            for (r, g, b) in p:
                words.append(rgb555(r, g, b))
        L.append(dw_block(words, per_line=4))
        L.append('')
    return '\n'.join(L)
