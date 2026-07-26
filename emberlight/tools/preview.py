#!/usr/bin/env python3
"""preview.py -- paint scenes, convert them, and dump a PNG contact sheet.

Shows the *post-conversion* reconstruction, so what you see is exactly what
the Game Boy will put on screen, tile budget and all.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from PIL import Image, ImageDraw

import scenes
from gbart import indices_to_image, DMG_GREEN, DMG_GREY
from tileconv import Picture, ART_MAX

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHOTS = os.path.join(ROOT, 'shots')


def cgb_palette_image(idx, attr, palettes, scale=1):
    """Render using the Game Boy Color palettes + attribute map."""
    h, w = idx.shape
    out = np.zeros((h, w, 3), dtype=np.uint8)
    rows, cols = h // 8, w // 8
    for ty in range(rows):
        for tx in range(cols):
            p = palettes[min(attr[ty * cols + tx], len(palettes) - 1)] if attr is not None else palettes[0]
            sub = idx[ty * 8:(ty + 1) * 8, tx * 8:(tx + 1) * 8]
            block = out[ty * 8:(ty + 1) * 8, tx * 8:(tx + 1) * 8]
            for i, rgb in enumerate(p):
                block[sub == i] = rgb
    img = Image.fromarray(out, 'RGB')
    if scale != 1:
        img = img.resize((w * scale, h * scale), Image.NEAREST)
    return img


def main():
    os.makedirs(SHOTS, exist_ok=True)
    names = sys.argv[1:] or list(scenes.all_scenes().keys())
    reg = scenes.all_scenes()
    panels = []
    for name in names:
        fn, meta = reg[name]
        c, pal, cgbpals, bgp = fn()
        idx = c.quantize()
        pic = Picture(name, idx, pal=pal, budget=ART_MAX)
        print('%-14s %3d unique -> %3d tiles  (budget %d)%s'
              % (name, pic.exact_unique, pic.tile_count, ART_MAX,
                 '  MERGED' if pic.tile_count < pic.exact_unique else ''))
        g = indices_to_image(pic.recon, DMG_GREEN, scale=2)
        col = cgb_palette_image(pic.recon, pic.attr, cgbpals, scale=2)
        panels.append((name, g, col))

    pad = 8
    label = 14
    pw, ph = 320, 288
    cols = 2
    rows = len(panels)
    sheet = Image.new('RGB', (cols * pw + pad * (cols + 1),
                              rows * (ph + label) + pad * (rows + 1)),
                      (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    for r, (name, g, col) in enumerate(panels):
        y = pad + r * (ph + label + pad)
        d.text((pad, y), '%s   [DMG]                                    [GBC]' % name.upper(),
               fill=(200, 200, 190))
        sheet.paste(g, (pad, y + label))
        sheet.paste(col, (pad * 2 + pw, y + label))
    out = os.path.join(SHOTS, 'preview.png')
    sheet.save(out)
    print('wrote', out)


if __name__ == '__main__':
    main()
