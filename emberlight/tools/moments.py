#!/usr/bin/env python3
"""
moments.py -- capture specific interactive moments rather than a whole run.

The contact sheet from capture.py samples the story by scene change, which
tends to miss the parts a player actually touches: the blinking title prompt,
the explore reticle, the ember gauge, the branch menu.  This drives the ROM to
each of those states and photographs it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw
from pyboy import PyBoy

from capture import load_symbols, Player, contact_sheet, ROM, SHOTS


def grab(cgb=True, frames=14000):
    syms = load_symbols()
    pb = PyBoy(ROM, window='null', cgb=cgb, sound_emulated=False)
    p = Player(pb, syms, choice='a')
    got = {}
    last_explore = [-9999]

    def mem(n):
        return pb.memory[syms[n]]

    for f in range(frames):
        # Let the title screen breathe before the auto-player skips past it.
        if f > 300:
            p.step(f)
        pb.tick(1, True)

        # The title prompt blinks; catch it on an "on" frame.
        if 'title' not in got and 120 < f < 300 and mem('wPromptShown'):
            got['title'] = ('title screen, prompt lit', pb.screen.image.convert('RGB'))

        # Reticle up, dialogue closed: this is the point-and-click state.
        if 'explore' not in got and mem('wExploreActive') and not mem('wBoxOpen'):
            if f % 7 == 0:
                got['explore'] = ('explore mode: the reticle over the lens',
                                  pb.screen.image.convert('RGB'))

        # Something the reticle found.  The engine hides the reticle while
        # she speaks, so look for a box that opened just after explore mode.
        if mem('wExploreActive'):
            last_explore[0] = f
        if ('examine' not in got and mem('wBoxOpen')
                and 0 < f - last_explore[0] < 400 and mem('wTextLine') >= 1):
            got['examine'] = ('examining a hotspot', pb.screen.image.convert('RGB'))

        # The ember gauge, part-filled.
        if mem('wTendActive') and 4 <= mem('wGauge') <= 14:
            got['tend'] = ('tending the ember', pb.screen.image.convert('RGB'))

        # The branch menu.
        if 'choice' not in got and mem('wChoiceSel') is not None:
            pass
    pb.stop()
    return got


def grab_choice(cgb=True, frames=14000):
    """A second pass that stops on the two-option menu."""
    syms = load_symbols()
    pb = PyBoy(ROM, window='null', cgb=cgb, sound_emulated=False)
    p = Player(pb, syms, choice='a')
    shot = None
    prev_sel_seen = False
    for f in range(frames):
        p.step(f)
        pb.tick(1, True)
        # The menu is the only place the cursor tile sits in the frame column.
        row = 14 * 32 + 1
        if pb.memory[0x9800 + row] == syms_cursor():
            shot = ('the choice at the shoals', pb.screen.image.convert('RGB'))
            break
    pb.stop()
    return shot


def syms_cursor():
    # TILE_FONT_BASE + (';' - 32)
    return 176 + (ord(';') - 32)


def main():
    os.makedirs(SHOTS, exist_ok=True)
    got = grab()
    ch = grab_choice()
    if ch:
        got['choice'] = ch
    order = ['title', 'explore', 'examine', 'tend', 'choice']
    shots = []
    for k in order:
        if k in got:
            shots.append(got[k])
        else:
            print('missed:', k)

    if not shots:
        raise SystemExit('captured nothing')

    w, h, scale = 160, 144, 2
    pad, label = 6, 13
    cols = min(3, len(shots))
    rows = -(-len(shots) // cols)
    sheet = Image.new('RGB', (cols * w * scale + pad * (cols + 1),
                              22 + rows * (h * scale + label) + pad * (rows + 1)),
                      (18, 18, 22))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 6), 'EMBERLIGHT  --  interactive moments  --  live emulator capture',
           fill=(215, 215, 205))
    for i, (cap, im) in enumerate(shots):
        cx, cy = i % cols, i // cols
        x = pad + cx * (w * scale + pad)
        y = 22 + pad + cy * (h * scale + label + pad)
        d.text((x, y), cap, fill=(150, 150, 145))
        sheet.paste(im.resize((w * scale, h * scale), Image.NEAREST), (x, y + label))
    out = os.path.join(SHOTS, 'moments.png')
    sheet.save(out)
    print('wrote', out, '(%d moments)' % len(shots))


if __name__ == '__main__':
    main()
