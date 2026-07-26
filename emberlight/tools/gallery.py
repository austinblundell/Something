#!/usr/bin/env python3
"""
gallery.py -- one clean photograph of every cutscene, from the running ROM.

Watches the engine's own state: when the picture pointer matches a known
scene, the fade has reached full and no dialogue box is covering the art, that
frame is the portrait of that scene.  Runs the same pass on both hardware
targets so the DMG and Game Boy Color versions can be compared honestly.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw
from pyboy import PyBoy

from capture import load_symbols, Player, ROM, ROM_DMG, SHOTS, SYM

SCENES = [
    ('title', 'THE TOWER'),
    ('storm', 'CHAPTER ONE: THE STORM'),
    ('lamproom', 'THE LAMP ROOM'),
    ('village', 'CHAPTER TWO: THE DROWNED VILLAGE'),
    ('signal', 'CHAPTER THREE: THE SIGNAL'),
    ('rescue', 'ENDING A: THE SHOALS'),
    ('vigil', 'ENDING B: THE VIGIL'),
    ('dawn', 'CHAPTER FOUR: DAWN'),
]


def banked_symbols():
    """Symbols keyed by (bank, address).

    Pictures in different banks routinely share an address -- pic_lamproom and
    pic_vigil are both at $4000 -- so identifying the loaded scene needs the
    bank as well as the pointer.
    """
    import re
    out = {}
    with open(SYM) as f:
        for line in f:
            m = re.match(r'^([0-9a-fA-F]{2}):([0-9a-fA-F]{4})\s+(\S+)', line)
            if m:
                out.setdefault(m.group(3),
                               (int(m.group(1), 16), int(m.group(2), 16)))
    return out


def collect(cgb, choice, frames=15000):
    syms = load_symbols()
    banked = banked_symbols()
    want = {}
    for name, _ in SCENES:
        sym = 'pic_' + name
        if sym in banked:
            want[banked[sym]] = name

    pb = PyBoy(ROM if cgb else ROM_DMG, window='null', cgb=cgb,
               sound_emulated=False)
    p = Player(pb, syms, choice=choice)
    m = pb.memory
    got = {}
    stable = 0
    prev = None
    for f in range(frames):
        p.step(f)
        pb.tick(1, True)

        # Skip anything transient: a blanked LCD during a picture load reads
        # as a white frame, and a lightning flash whites the palettes out.
        if not (m[0xFF40] & 0x80) or m[syms['wFadeLevel']] != 4 or m[syms['wBoxOpen']]:
            stable = 0
            continue
        ptr = m[syms['wPicPtr']] | (m[syms['wPicPtr'] + 1] << 8)
        name = want.get((m[syms['wPicBank']], ptr))
        if name != prev:
            prev = name
            stable = 0
        stable += 1
        if name and stable == 14 and name not in got:
            got[name] = pb.screen.image.convert('RGB')
    pb.stop()
    return got


def sheet(images, path, title, cols=4, scale=2):
    w, h = 160 * scale, 144 * scale
    pad, label, head = 8, 14, 26
    rows = -(-len(images) // cols)
    out = Image.new('RGB', (cols * w + pad * (cols + 1),
                            head + rows * (h + label) + pad * (rows + 1)),
                    (16, 16, 20))
    d = ImageDraw.Draw(out)
    d.text((pad, 8), title, fill=(220, 220, 210))
    for i, (cap, im) in enumerate(images):
        x = pad + (i % cols) * (w + pad)
        y = head + pad + (i // cols) * (h + label + pad)
        d.text((x, y), cap, fill=(150, 150, 145))
        out.paste(im.resize((w, h), Image.NEAREST), (x, y + label))
    out.save(path)
    return path


def main():
    os.makedirs(SHOTS, exist_ok=True)

    colour = collect(True, 'a')
    colour.update({k: v for k, v in collect(True, 'b').items() if k not in colour})
    mono = collect(False, 'a')
    mono.update({k: v for k, v in collect(False, 'b').items() if k not in mono})

    ordered = [(cap, colour[name]) for name, cap in SCENES if name in colour]
    missing = [n for n, _ in SCENES if n not in colour]
    if missing:
        print('not reached:', ', '.join(missing))
    sheet(ordered, os.path.join(SHOTS, 'gallery-gbc.png'),
          'EMBERLIGHT  --  every cutscene, Game Boy Color  --  live emulator capture')
    print('wrote gallery-gbc.png (%d scenes)' % len(ordered))

    ordered_m = [(cap, mono[name]) for name, cap in SCENES if name in mono]
    sheet(ordered_m, os.path.join(SHOTS, 'gallery-dmg.png'),
          'EMBERLIGHT  --  the same ROM on an original Game Boy')
    print('wrote gallery-dmg.png (%d scenes)' % len(ordered_m))

    # Side-by-side: the same frames, both machines.
    pairs = []
    for name, cap in SCENES:
        if name in colour and name in mono:
            pairs.append(('%s  [DMG]' % cap, mono[name]))
            pairs.append(('%s  [GBC]' % cap, colour[name]))
    sheet(pairs, os.path.join(SHOTS, 'gallery-compare.png'),
          'EMBERLIGHT  --  one ROM, two machines', cols=2, scale=2)
    print('wrote gallery-compare.png')

    for name in colour:
        colour[name].resize((480, 432), Image.NEAREST).save(
            os.path.join(SHOTS, 'scene-%s.png' % name))


if __name__ == '__main__':
    main()
