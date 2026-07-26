#!/usr/bin/env python3
"""
build_assets.py -- paint every scene, convert it, and emit RGBASM sources.

Outputs into assets/gen/:
    font.inc      64 resident font / dialogue-box / gauge tiles
    sprites.inc   16 effect and reticle sprite tiles
    pic_*.inc     one picture per file, each pinned to a ROM bank
    story.inc     the opcode stream and prose from tools/story.py
    manifest.inc  the include list, so main.asm never needs editing
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

import gbfont
import scenes
import story
from tileconv import (Picture, ART_MAX, ART_BASE, db_block, emit_picture,
                      pack_1bpp_tile, pack_tile)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GEN = os.path.join(ROOT, 'assets', 'gen')

# Each picture is ~3.6 KB, so four fit in a 16 KB bank with room to spare.
PICS_PER_BANK = 4
FIRST_PIC_BANK = 2
STORY_BANK = 1

# Draw order matters only for which bank things land in; keep it stable so
# rebuilds are reproducible.
SCENE_ORDER = ['title', 'storm', 'lamproom', 'village',
               'signal', 'rescue', 'vigil', 'dawn']


# --------------------------------------------------------------------------
#  resident tiles
# --------------------------------------------------------------------------

def emit_font():
    data = bytearray()
    for cell in gbfont.font_tiles():
        data += pack_1bpp_tile(cell, ink=3, paper=0)
    return ('; Font, dialogue-box chrome and gauge cells: ASCII 32..95.\n'
            '; Generated from tools/gbfont.py -- do not edit.\n'
            'SECTION "font", ROM0\n'
            'FontTiles::\n' + db_block(bytes(data)) + '\n')


def sprite_cells():
    """The sixteen resident sprite tiles, as 8x8 arrays of colour indices.

    Colour 0 is transparent for sprites, so highlights are drawn in colour 1
    and the object palettes put white there.
    """
    blank = [[0] * 8 for _ in range(8)]

    def cell():
        return [[0] * 8 for _ in range(8)]

    # --- rain, long: a 7px streak leaning with the wind -------------------
    rain_long = cell()
    for i in range(7):
        x = 5 - (i * 2) // 3
        rain_long[i][max(0, x)] = 1
    # --- rain, short ------------------------------------------------------
    rain_short = cell()
    for i in range(4):
        rain_short[i + 2][4 - i // 2] = 1

    # --- ember spark: bright core, dim shoulders --------------------------
    spark = cell()
    spark[3][3] = 1
    spark[3][4] = 1
    spark[4][3] = 1
    spark[4][4] = 1
    spark[2][3] = 2
    spark[5][4] = 2

    # --- snow / dust dot ---------------------------------------------------
    dot = cell()
    dot[3][3] = 1
    dot[3][4] = 1
    dot[4][3] = 1
    dot[4][4] = 1

    # --- reticle corners ---------------------------------------------------
    def corner(flip_x, flip_y):
        # A bright L with a dark inner edge: legible over a black sky and
        # over a lit lamp room alike.
        c = cell()
        for i in range(6):
            c[0][i] = 1
            c[i][0] = 1
        for i in range(1, 5):
            c[1][i] = 3
            c[i][1] = 3
        if flip_x:
            c = [row[::-1] for row in c]
        if flip_y:
            c = c[::-1]
        return c

    # --- water glint: a short bright dash ----------------------------------
    glint = cell()
    for x in range(1, 7):
        glint[4][x] = 1
    glint[3][3] = 1
    glint[3][4] = 1

    return [rain_long, rain_short, spark, dot,
            corner(False, False), corner(True, False),
            corner(False, True), corner(True, True),
            glint, blank, blank, blank, blank, blank, blank, blank]


def emit_sprites():
    data = bytearray()
    for cell in sprite_cells():
        data += pack_tile(cell)
    return ('; Effect and reticle sprites. Generated -- do not edit.\n'
            'SECTION "sprites", ROM0\n'
            'SpriteTiles::\n' + db_block(bytes(data)) + '\n')


# --------------------------------------------------------------------------
#  main
# --------------------------------------------------------------------------

def main():
    os.makedirs(GEN, exist_ok=True)
    reg = scenes.all_scenes()

    with open(os.path.join(GEN, 'font.inc'), 'w') as f:
        f.write(emit_font())
    with open(os.path.join(GEN, 'sprites.inc'), 'w') as f:
        f.write(emit_sprites())

    includes = ['font.inc', 'sprites.inc']
    total_tiles = 0
    for i, name in enumerate(SCENE_ORDER):
        if name not in reg:
            raise SystemExit('scene %r is referenced but not painted' % name)
        fn, meta = reg[name]
        canvas, pal, cgbpals, bgp = fn()
        idx = canvas.quantize()
        pic = Picture(name, idx, pal=pal, budget=ART_MAX, base=ART_BASE)
        bank = FIRST_PIC_BANK + i // PICS_PER_BANK
        src = emit_picture(pic, cgbpals, bgp, bank=bank)
        fname = 'pic_%s.inc' % name
        with open(os.path.join(GEN, fname), 'w') as f:
            f.write(src + '\n')
        includes.append(fname)
        total_tiles += pic.tile_count
        flag = '  merged from %d' % pic.exact_unique if pic.tile_count < pic.exact_unique else ''
        print('  %-10s bank %-2d  %3d tiles%s' % (name, bank, pic.tile_count, flag))

    sc = story.build()
    with open(os.path.join(GEN, 'story.inc'), 'w') as f:
        f.write(sc.emit(STORY_BANK) + '\n')
    includes.append('story.inc')

    n_ops = sum(1 for o in sc.ops if o[0] != 'label')
    n_str = sum(1 for v in sc.blobs.values() if not isinstance(v, tuple))
    n_bytes = sum(len(v) for v in sc.blobs.values() if not isinstance(v, tuple))
    print('  script     bank %-2d  %d ops, %d strings, %d text bytes'
          % (STORY_BANK, n_ops, n_str, n_bytes))

    with open(os.path.join(GEN, 'manifest.inc'), 'w') as f:
        f.write('; Generated by tools/build_assets.py -- do not edit.\n')
        for inc in includes:
            f.write('INCLUDE "%s"\n' % inc)
    print('  %d pictures, %d picture tiles total' % (len(SCENE_ORDER), total_tiles))


if __name__ == '__main__':
    main()
