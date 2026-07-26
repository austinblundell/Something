#!/usr/bin/env python3
"""Asset + table generator for GB HORIZON.

Produces src/gen/*.inc consumed by src/main.asm.

Screen model
------------
  y =  0..47   sky / HUD band (fixed SCX + BGP)
  y = 48..143  road band, 96 scanlines == 12 background rows (rows 6..17)

The road is drawn once, straight, into the background map.  Curves come from
rewriting SCX every scanline; forward motion comes from rewriting BGP every
scanline (palette banding), so no tile data is ever touched at runtime.

Palette index usage inside road tiles:
  0 grass      1 asphalt      2 rumble strip      3 lane dashes
"""

import os
import textwrap

OUT = os.path.join(os.path.dirname(__file__), "..", "src", "gen")

# ---------------------------------------------------------------- geometry --
SCREEN_W = 160
ROAD_TOP = 48                  # first road scanline
ROAD_BOT = 143                 # last road scanline
ROAD_LINES = ROAD_BOT - ROAD_TOP + 1        # 96
ROAD_ROWS = ROAD_LINES // 8                 # 12 background rows
ROW_FIRST = ROAD_TOP // 8                   # background row 6

BG_CENTER = 128                # road centre in background space
HALFW_MAX = 64                 # road half width at the bottom scanline
SCX_BASE = BG_CENTER - SCREEN_W // 2        # 48 -> road centred on screen

# depth mapping: z(y) = ZC / (y - ZY0)
ZC = 365700
ZY0 = 23

# curve accumulator: shape(y) runs 0 at the bottom to SHAPE_MAX at the horizon
SHAPE_MAX = 128
CURVE_LIMIT = 88               # |curve|; horizon offset in px == curve/2

PAL_SKY = 0xE4                 # sky band, standard ramp
PAL_A = 0x38                   # grass w, asphalt dark, rumble black, dash w
PAL_B = 0xDC                   # grass w, asphalt black, rumble lgray, dash off
PAL_FAR = 0x58                 # distant road, no banding


def half_width(y):
    """Road half width in pixels at scanline y (linear == correct perspective)."""
    t = (y - (ROAD_TOP - 1)) / float(ROAD_LINES)
    return int(round(HALFW_MAX * t))


def z_at(y):
    return int(round(ZC / float(y - ZY0)))


# ------------------------------------------------------------------ tiles ---
def blank(w, h):
    return [[0] * w for _ in range(h)]


def to_2bpp(tile):
    """tile: 8x8 list of rows of palette indices -> 16 bytes."""
    out = []
    for row in tile:
        lo = hi = 0
        for x in range(8):
            p = row[x]
            lo = (lo << 1) | (p & 1)
            hi = (hi << 1) | ((p >> 1) & 1)
        out.append(lo)
        out.append(hi)
    return bytes(out)


class TileBank:
    """Tile store, optionally deduplicating.

    8x16 sprites must keep their two halves in consecutive slots, so the
    object bank never dedupes.
    """

    def __init__(self, dedupe=True):
        self.tiles = []
        self.index = {}
        self.dedupe = dedupe

    def add(self, tile):
        key = to_2bpp(tile)
        if not self.dedupe:
            self.tiles.append(key)
            return len(self.tiles) - 1
        if key not in self.index:
            self.index[key] = len(self.tiles)
            self.tiles.append(key)
        return self.index[key]

    def add_raw(self, data):
        if data not in self.index:
            self.index[data] = len(self.tiles)
            self.tiles.append(data)
        return self.index[data]

    def blob(self):
        return b"".join(self.tiles)


def cut(img, w, h, bank):
    """Cut a pixel buffer into 8x8 tiles, returning a tilemap."""
    cols, rows = w // 8, h // 8
    tmap = []
    for ty in range(rows):
        for tx in range(cols):
            tile = [img[ty * 8 + j][tx * 8:tx * 8 + 8] for j in range(8)]
            tmap.append(bank.add(tile))
    return tmap


# ------------------------------------------------------------- road image ---
def build_road(bank):
    img = blank(256, ROAD_LINES)
    for y in range(ROAD_TOP, ROAD_BOT + 1):
        j = y - ROAD_TOP
        hw = half_width(y)
        t = (y - (ROAD_TOP - 1)) / float(ROAD_LINES)
        rumble = max(1, int(round(7 * t)))
        lane_w = max(1, int(round(2 * t)))
        lane_at = hw // 3                    # two dashed dividers -> 3 lanes
        row = img[j]
        for x in range(256):
            d = x - BG_CENTER
            ad = abs(d)
            if ad > hw:
                continue                     # grass, index 0
            if ad > hw - rumble:
                row[x] = 2                   # rumble strip
                continue
            row[x] = 1                       # asphalt
            if hw > 10 and abs(ad - lane_at) <= lane_w:
                row[x] = 3                   # lane divider
    return cut(img, 256, ROAD_LINES, bank)


# ------------------------------------------------------------------ font ----
FONT5 = {
    " ": [0, 0, 0, 0, 0, 0, 0],
    "A": [0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
    "B": [0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E],
    "C": [0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E],
    "D": [0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E],
    "E": [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F],
    "F": [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10],
    "G": [0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F],
    "H": [0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
    "I": [0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E],
    "J": [0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C],
    "K": [0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11],
    "L": [0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F],
    "M": [0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11],
    "N": [0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11],
    "O": [0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    "P": [0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10],
    "Q": [0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D],
    "R": [0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11],
    "S": [0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E],
    "T": [0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04],
    "U": [0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    "V": [0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04],
    "W": [0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11],
    "X": [0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11],
    "Y": [0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04],
    "Z": [0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F],
    "0": [0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E],
    "1": [0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E],
    "2": [0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F],
    "3": [0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E],
    "4": [0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02],
    "5": [0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E],
    "6": [0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E],
    "7": [0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08],
    "8": [0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E],
    "9": [0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C],
    "-": [0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00],
    ".": [0x00, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C],
    "/": [0x01, 0x02, 0x02, 0x04, 0x08, 0x08, 0x10],
    "!": [0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04],
    "<": [0x02, 0x04, 0x08, 0x10, 0x08, 0x04, 0x02],
    ">": [0x08, 0x04, 0x02, 0x01, 0x02, 0x04, 0x08],
    "=": [0x00, 0x00, 0x1F, 0x00, 0x1F, 0x00, 0x00],
    "#": [0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F],
    "*": [0x1F, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1F],
}

CHARSET = (" ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-./!<>=#*")


def build_font(bank, color=3):
    """Returns (first_tile_index, {char: tile}) -- glyphs are contiguous."""
    mapping = {}
    for ch in CHARSET:
        rows = FONT5[ch]
        tile = blank(8, 8)
        for j, bits in enumerate(rows):
            for x in range(5):
                if bits & (0x10 >> x):
                    tile[j][x + 1] = color
        mapping[ch] = bank.add(tile)
    return mapping


# ------------------------------------------------------------- car sprites --
def rect(img, x0, y0, x1, y1, c):
    for y in range(max(0, y0), min(len(img), y1 + 1)):
        for x in range(max(0, x0), min(len(img[0]), x1 + 1)):
            img[y][x] = c


def art(rows, w):
    """ASCII-art sprite: '.' transparent, '1'..'3' palette entries."""
    out = []
    for r in rows:
        assert len(r) == w, "row is %d wide, expected %d: %r" % (len(r), w, r)
        out.append([0 if c == "." else int(c) for c in r])
    return out


def sym(w, *spans):
    """Build one row from centred (width, colour) pairs, outermost first."""
    row = ["."] * w
    used = 0
    for width, colour in spans:
        start = (w - width) // 2
        for x in range(start, start + width):
            row[x] = colour
        used = width
    del used
    return "".join(row)


# Bodies are light grey with black outlines so they read against dark asphalt.
PLAYER_ART = [
    sym(32, (32, ".")),
    sym(32, (32, ".")),
    sym(32, (12, "3")),
    sym(32, (14, "3"), (12, "2")),
    sym(32, (14, "3"), (12, "2")),
    sym(32, (16, "3"), (12, "2")),
    sym(32, (18, "3"), (16, "1")),
    sym(32, (20, "3"), (18, "1")),
    sym(32, (22, "3"), (20, "1")),
    sym(32, (22, "3"), (20, "1")),
    "...." + "3" + "11" + "333" + "1" * 12 + "333" + "11" + "3" + "....",
    "...." + "3" + "11" + "333" + "1" * 12 + "333" + "11" + "3" + "....",
    sym(32, (24, "3"), (22, "1")),
    sym(32, (26, "3")),
    ".." + "3333" + "." * 20 + "3333" + "..",
    ".." + "3333" + "." * 20 + "3333" + "..",
]

BIG_ART = [
    sym(16, (16, ".")),
    sym(16, (16, ".")),
    sym(16, (16, ".")),
    sym(16, (16, ".")),
    sym(16, (16, ".")),
    sym(16, (6, "3")),
    sym(16, (8, "3"), (6, "2")),
    sym(16, (8, "3"), (6, "2")),
    sym(16, (10, "3"), (8, "1")),
    sym(16, (12, "3"), (10, "1")),
    sym(16, (12, "3"), (10, "1")),
    ".." + "3" + "1" + "33" + "1111" + "33" + "1" + "3" + "..",
    sym(16, (12, "3"), (10, "1")),
    sym(16, (14, "3")),
    "." + "33" + "." * 10 + "33" + ".",
    "." + "33" + "." * 10 + "33" + ".",
]

MED_ART = [
    "........",
    "........",
    "........",
    "........",
    "........",
    "........",
    "........",
    "........",
    "..3333..",
    ".322223.",
    ".311113.",
    "31111113",
    "31331131",
    "31111113",
    "33333333",
    "33....33",
]

FAR_ART = [
    "........",
    "........",
    "........",
    "........",
    "........",
    "........",
    "........",
    "........",
    "........",
    "........",
    "........",
    "........",
    "..3333..",
    ".311113.",
    ".311113.",
    ".333333.",
]


def cut_sprite(img, w, h, bank):
    """Cut into 8x16 sprite columns; returns list of even tile indices."""
    ids = []
    for tx in range(w // 8):
        top = [img[j][tx * 8:tx * 8 + 8] for j in range(8)]
        bot = [img[8 + j][tx * 8:tx * 8 + 8] for j in range(8)]
        a = bank.add(top)
        b = bank.add(bot)
        assert b == a + 1, "8x16 sprite tiles must stay paired"
        ids.append(a)
    return ids


# ------------------------------------------------------- start-screen cars --
def showcase_car(kind, w=56, h=40):
    """Chunky 3/4-ish rear view for the car-select screen."""
    img = blank(w, h)
    cx = w // 2
    if kind == 0:            # hatchback
        rect(img, 8, 14, w - 9, 30, 2)
        rect(img, 14, 8, w - 15, 15, 1)
        rect(img, 16, 10, w - 17, 13, 3)
        rect(img, 6, 26, w - 7, 31, 2)
        rect(img, 5, 29, 13, 35, 3)
        rect(img, w - 14, 29, w - 6, 35, 3)
        rect(img, 9, 22, 15, 25, 3)
        rect(img, w - 16, 22, w - 10, 25, 3)
        rect(img, 18, 17, w - 19, 20, 1)
    elif kind == 1:          # low sports car
        rect(img, 5, 18, w - 6, 30, 2)
        rect(img, 15, 12, w - 16, 19, 1)
        rect(img, 17, 14, w - 18, 17, 3)
        rect(img, 3, 24, w - 4, 30, 2)
        rect(img, 2, 28, 11, 34, 3)
        rect(img, w - 12, 28, w - 3, 34, 3)
        rect(img, 6, 21, 13, 23, 3)
        rect(img, w - 14, 21, w - 7, 23, 3)
        rect(img, 12, 30, w - 13, 32, 1)   # rear diffuser
        rect(img, 10, 10, w - 11, 11, 3)   # wing
        rect(img, 12, 11, 14, 14, 3)
        rect(img, w - 15, 11, w - 13, 14, 3)
    else:                    # truck / SUV
        rect(img, 7, 10, w - 8, 32, 2)
        rect(img, 11, 4, w - 12, 12, 1)
        rect(img, 13, 6, w - 14, 10, 3)
        rect(img, 5, 26, w - 6, 33, 2)
        rect(img, 3, 29, 14, 37, 3)
        rect(img, w - 15, 29, w - 4, 37, 3)
        rect(img, 9, 16, 16, 20, 3)
        rect(img, w - 17, 16, w - 10, 20, 3)
        rect(img, 18, 22, w - 19, 26, 1)
        rect(img, 10, 13, w - 11, 14, 3)   # roof rack line
    rect(img, cx - 1, 33, cx + 1, 34, 0)
    return img


# --------------------------------------------------------------- arrows -----
def arrow_tiles(bank):
    """16x16 turn arrows (left, right) drawn as four BG tiles each."""
    out = []
    for direction in (-1, 1):
        img = blank(16, 16)
        rect(img, 2, 6, 9, 9, 3)                     # shaft
        for dx in range(5):                          # solid triangular head
            h = 4 - dx
            for dy in range(-h, h + 1):
                img[8 + dy][9 + dx] = 3
        if direction < 0:
            img = [list(reversed(r)) for r in img]
        tiles = []
        for ty in range(2):
            for tx in range(2):
                tile = [img[ty * 8 + j][tx * 8:tx * 8 + 8] for j in range(8)]
                tiles.append(bank.add(tile))
        out.append(tiles)
    return out


# ------------------------------------------------------------- emit helpers -
def db_lines(data, per=16):
    lines = []
    for i in range(0, len(data), per):
        chunk = ", ".join("$%02X" % b for b in data[i:i + per])
        lines.append("    db " + chunk)
    return "\n".join(lines)


def write(name, text):
    path = os.path.join(OUT, name)
    with open(path, "w") as f:
        f.write(text)
    return path


# ------------------------------------------------------------------ main ----
def main():
    os.makedirs(OUT, exist_ok=True)

    # ---- background tiles: road, sky, font, arrows -------------------------
    bg = TileBank()
    sky_tile = bg.add([[1] * 8 for _ in range(8)])
    blank_tile = bg.add(blank(8, 8))
    road_map = build_road(bg)
    road_tile_count = len(bg.tiles)
    font_map = build_font(bg)
    arrows = arrow_tiles(bg)

    # showcase cars are uploaded on demand into a fixed slot range
    show = TileBank()
    show_maps = []
    for kind in range(3):
        img = showcase_car(kind)
        show_maps.append(cut(img, 56, 40, show))
    show_w, show_h = 56 // 8, 40 // 8

    # ---- sprite tiles ------------------------------------------------------
    ob = TileBank(dedupe=False)
    player_ids = cut_sprite(art(PLAYER_ART, 32), 32, 16, ob)
    big_ids = cut_sprite(art(BIG_ART, 16), 16, 16, ob)
    med_ids = cut_sprite(art(MED_ART, 8), 8, 16, ob)
    far_ids = cut_sprite(art(FAR_ART, 8), 8, 16, ob)

    # ---- tables ------------------------------------------------------------
    ztab = [z_at(y) for y in range(ROAD_TOP, ROAD_BOT + 1)]

    # first scanline (from the top) where a 256-unit band spans >= 2 lines
    band_start = 0
    for i in range(ROAD_LINES - 1):
        y = ROAD_TOP + i
        if abs(z_at(y) - z_at(y + 1)) <= 128:
            band_start = i
            break

    width_tab = [half_width(y) for y in range(ROAD_TOP, ROAD_BOT + 1)]

    # rz -> scanline, indexed by rz >> 7 (0..127)
    y_from_rz = []
    for idx in range(128):
        rz = idx << 7
        if rz <= 0:
            y_from_rz.append(255)
            continue
        y = ZY0 + ZC / float(rz)
        if y > ROAD_BOT:
            y_from_rz.append(255)            # nearer than the bottom scanline
        elif y < ROAD_TOP:
            y_from_rz.append(0)              # beyond the horizon
        else:
            y_from_rz.append(int(round(y)))

    # curve accumulator shape: quadratic in screen position
    shape = []
    for y in range(ROAD_BOT, ROAD_TOP - 1, -1):
        t = (ROAD_BOT - y) / float(ROAD_LINES - 1)
        shape.append(int(round(SHAPE_MAX * t * t)))
    deltas = [shape[i + 1] - shape[i] for i in range(len(shape) - 1)]
    assert all(d >= 0 for d in deltas)
    assert sum(deltas) == SHAPE_MAX, sum(deltas)

    # ---- write everything --------------------------------------------------
    hdr = "; Generated by tools/gen_assets.py -- do not edit.\n"

    write("consts.inc", hdr + textwrap.dedent(f"""
        DEF ROAD_TOP      EQU {ROAD_TOP}
        DEF ROAD_BOT      EQU {ROAD_BOT}
        DEF ROAD_LINES    EQU {ROAD_LINES}
        DEF ROAD_ROWS     EQU {ROAD_ROWS}
        DEF ROW_FIRST     EQU {ROW_FIRST}
        DEF SCX_BASE      EQU {SCX_BASE}
        DEF HALFW_MAX     EQU {HALFW_MAX}
        DEF CURVE_LIMIT   EQU {CURVE_LIMIT}
        DEF BAND_START    EQU {band_start}
        DEF PAL_SKY       EQU ${PAL_SKY:02X}
        DEF PAL_A         EQU ${PAL_A:02X}
        DEF PAL_B         EQU ${PAL_B:02X}
        DEF PAL_FAR       EQU ${PAL_FAR:02X}
        DEF TILE_SKY      EQU {sky_tile}
        DEF TILE_BLANK    EQU {blank_tile}
        DEF SHOW_W        EQU {show_w}
        DEF SHOW_H        EQU {show_h}
        DEF SHOW_TILES    EQU {len(show.tiles)}
        DEF BG_TILE_COUNT EQU {len(bg.tiles)}
        DEF OB_TILE_COUNT EQU {len(ob.tiles)}
        DEF SPR_PLAYER0   EQU {player_ids[0]}
        DEF SPR_PLAYER1   EQU {player_ids[1]}
        DEF SPR_PLAYER2   EQU {player_ids[2]}
        DEF SPR_PLAYER3   EQU {player_ids[3]}
        DEF SPR_BIG0      EQU {big_ids[0]}
        DEF SPR_BIG1      EQU {big_ids[1]}
        DEF SPR_MED       EQU {med_ids[0]}
        DEF SPR_FAR       EQU {far_ids[0]}
        DEF FONT_BASE     EQU {font_map[' ']}
        DEF ARROW_L       EQU {arrows[0][0]}
        DEF ARROW_R       EQU {arrows[1][0]}
        """))

    write("bgtiles.inc", hdr + "BgTiles:\n" + db_lines(bg.blob()) +
          "\nBgTilesEnd:\n")
    write("obtiles.inc", hdr + "ObTiles:\n" + db_lines(ob.blob()) +
          "\nObTilesEnd:\n")
    write("showtiles.inc", hdr + "ShowTiles:\n" + db_lines(show.blob()) +
          "\nShowTilesEnd:\n")

    write("roadmap.inc", hdr + "RoadMap:\n" + db_lines(road_map, 16) + "\n")

    show_txt = hdr
    for i, m in enumerate(show_maps):
        show_txt += "ShowMap%d:\n" % i + db_lines(m, 7) + "\n"
    write("showmaps.inc", show_txt)

    arrow_txt = hdr + "ArrowMaps:\n"
    for a in arrows:
        arrow_txt += db_lines(a, 4) + "\n"
    write("arrows.inc", arrow_txt)

    ztxt = hdr + "ZTable:\n"
    zb = []
    for z in ztab:
        zb.append(z & 0xFF)
        zb.append((z >> 8) & 0xFF)
    ztxt += db_lines(zb) + "\n"
    ztxt += "WidthTable:\n" + db_lines(width_tab) + "\n"

    # LaneTable[line][lane] -- signed pixel offset from the road centre.
    # Opponents sit in one of 16 lanes, which turns the per-sprite multiply
    # (|lat| * halfWidth / 64) into a single table read.
    lane_rows = []
    for i, hw in enumerate(width_tab):
        for lane in range(16):
            units = (lane - 7.5) * 8.0            # -60 .. +60 road units
            px = int(round(units * hw / 64.0))
            lane_rows.append(px & 0xFF)
    ztxt += "LaneTable:\n" + db_lines(lane_rows, 16) + "\n"
    ztxt += "YFromRz:\n" + db_lines(y_from_rz) + "\n"
    write("tables.inc", ztxt)

    # font lookup: ASCII 32..95 -> tile id
    fl = []
    for code in range(32, 96):
        ch = chr(code)
        fl.append(font_map.get(ch, font_map[" "]))
    write("fontmap.inc", hdr + "FontMap:\n" + db_lines(fl) + "\n")

    # unrolled SCX table builder
    body = ["; unrolled curve accumulator: 96 stores, %d adds" % sum(deltas)]
    for i, s in enumerate(shape):
        body.append("    STORE_SCX")
        if i < len(deltas):
            body.extend(["    add hl, bc"] * deltas[i])
    write("scxbuild.inc", hdr + "\n".join(body) + "\n")

    print("road tiles      : %d" % (road_tile_count - 2))
    print("bg tiles total  : %d  (limit 256)" % len(bg.tiles))
    print("showcase tiles  : %d" % len(show.tiles))
    print("sprite tiles    : %d  (limit 128)" % len(ob.tiles))
    print("band start line : y=%d" % (ROAD_TOP + band_start))
    print("z range         : %d .. %d" % (ztab[-1], ztab[0]))
    print("shape adds      : %d" % sum(deltas))
    assert len(bg.tiles) + len(show.tiles) <= 256, "bg tile overflow"
    assert len(ob.tiles) <= 128, "sprite tile overflow"


if __name__ == "__main__":
    main()
