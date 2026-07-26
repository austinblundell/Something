#!/usr/bin/env python3
"""
capture.py -- play EMBERLIGHT headlessly and photograph it.

Drives the ROM in PyBoy and saves screenshots.  It is a real player, not a
scripted frame list: it reads a handful of engine variables out of WRAM (via
the linker's symbol file) so it knows when the game has handed control to the
explore reticle or the ember mini-game, and plays those properly instead of
mashing A into a wall.

    python3 tools/capture.py [--dmg] [--frames N] [--choice a|b]
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from PIL import Image, ImageDraw
from pyboy import PyBoy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ROM = os.path.join(ROOT, 'build', 'emberlight.gb')
SYM = os.path.join(ROOT, 'build', 'emberlight.sym')
SHOTS = os.path.join(ROOT, 'shots')

# Where the reticle should visit in the lamp room, in cursor coordinates,
# with the hotspot that ends the segment last.
EXPLORE_TARGETS = [(72, 58), (22, 45), (128, 45), (32, 112), (76, 112)]


def load_symbols():
    syms = {}
    with open(SYM) as f:
        for line in f:
            m = re.match(r'^([0-9a-fA-F]{2}):([0-9a-fA-F]{4})\s+(\S+)', line)
            if m:
                syms.setdefault(m.group(3), int(m.group(2), 16))
    return syms


def frame_signature(img):
    a = np.asarray(img.convert('L'), dtype=np.int16)
    # Ignore the dialogue box rows: text churn is not a new scene.
    return a[:104:4, ::4]


def difference(a, b):
    if a is None or b is None:
        return 1e9
    return float(np.abs(a.astype(np.int32) - b.astype(np.int32)).mean())


class Player:
    """Presses buttons the way a person would, given what the game is doing."""

    def __init__(self, pb, syms, choice='a'):
        self.pb = pb
        self.s = syms
        self.choice = choice
        self.held = set()
        self.target = 0
        self.examined_at = -999
        self.choice_made = False

    def var(self, name):
        return self.pb.memory[self.s[name]]

    def set_buttons(self, want):
        for b in self.held - want:
            self.pb.button_release(b)
        for b in want - self.held:
            self.pb.button_press(b)
        self.held = set(want)

    def step(self, f):
        want = set()

        if self.var('wTendActive'):
            # Breathe on the ember: a steady mash beats the decay.
            if (f % 8) < 3:
                want.add('a')

        elif self.var('wExploreActive'):
            tx, ty = EXPLORE_TARGETS[min(self.target, len(EXPLORE_TARGETS) - 1)]
            cx, cy = self.var('wCurX'), self.var('wCurY')
            if abs(cx - tx) > 2:
                want.add('right' if cx < tx else 'left')
            if abs(cy - ty) > 2:
                want.add('down' if cy < ty else 'up')
            if not want and f - self.examined_at > 30:
                if (f % 10) < 3:
                    want.add('a')
                if f % 10 == 9:
                    self.examined_at = f
                    self.target += 1

        else:
            # Ordinary dialogue: tap A on a human cadence.
            if not self.choice_made and self.var('wChoiceSel') is not None:
                pass
            if (f % 40) < 3:
                want.add('a')

        # Steer the one branch in the story toward the requested ending.
        if self.choice == 'b' and not self.choice_made:
            if self.var('wBoxOpen') and 5200 < f < 5600 and (f % 40) in (10, 11):
                want = {'down'}
            if f > 5600:
                self.choice_made = True

        self.set_buttons(want)


def run(cgb=True, total_frames=20000, choice='a', settle=30,
        diff_threshold=7.0, min_gap=45, dialogue_delay=190):
    syms = load_symbols()
    pb = PyBoy(ROM, window='null', cgb=cgb, sound_emulated=False)
    player = Player(pb, syms, choice)

    shots = []
    last_sig = None
    last_shot = -999
    pending_scene = None
    pending_dialogue = None

    for f in range(total_frames):
        player.step(f)
        pb.tick(1, True)

        sig = frame_signature(pb.screen.image)
        if difference(sig, last_sig) > diff_threshold:
            pending_scene = f + settle              # shoot once the fade lands
            pending_dialogue = f + dialogue_delay   # and again with text up
        last_sig = sig

        for slot in ('scene', 'dialogue'):
            due = pending_scene if slot == 'scene' else pending_dialogue
            if due is not None and f >= due:
                if slot == 'scene':
                    pending_scene = None
                else:
                    pending_dialogue = None
                if f - last_shot >= min_gap:
                    shots.append((f, pb.screen.image.convert('RGB')))
                    last_shot = f

    pb.stop()
    return shots


def contact_sheet(shots, path, cols=3, scale=2, title=''):
    if not shots:
        raise SystemExit('captured nothing')
    w, h = 160 * scale, 144 * scale
    pad, label, head = 6, 13, (22 if title else 0)
    rows = -(-len(shots) // cols)
    sheet = Image.new('RGB', (cols * w + pad * (cols + 1),
                              head + rows * (h + label) + pad * (rows + 1)),
                      (18, 18, 22))
    d = ImageDraw.Draw(sheet)
    if title:
        d.text((pad, 6), title, fill=(215, 215, 205))
    for i, (f, im) in enumerate(shots):
        cx, cy = i % cols, i // cols
        x = pad + cx * (w + pad)
        y = head + pad + cy * (h + label + pad)
        d.text((x, y), 'frame %d' % f, fill=(150, 150, 145))
        sheet.paste(im.resize((w, h), Image.NEAREST), (x, y + label))
    sheet.save(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dmg', action='store_true')
    ap.add_argument('--frames', type=int, default=20000)
    ap.add_argument('--choice', default='a', choices=['a', 'b'])
    ap.add_argument('--out', default=None)
    ap.add_argument('--max', type=int, default=18)
    ap.add_argument('--cols', type=int, default=3)
    args = ap.parse_args()

    os.makedirs(SHOTS, exist_ok=True)
    shots = run(cgb=not args.dmg, total_frames=args.frames, choice=args.choice)
    print('captured %d distinct screens over %d frames' % (len(shots), args.frames))

    if len(shots) > args.max:
        keep = np.linspace(0, len(shots) - 1, args.max).round().astype(int)
        shots = [shots[i] for i in dict.fromkeys(keep.tolist())]

    tag = 'dmg' if args.dmg else 'gbc'
    mode = 'DMG' if args.dmg else 'GAME BOY COLOR'
    out = args.out or os.path.join(SHOTS, 'playthrough-%s.png' % tag)
    contact_sheet(shots, out, cols=args.cols,
                  title='EMBERLIGHT  --  %s  --  live emulator capture' % mode)
    print('wrote', out)

    for i, (f, im) in enumerate(shots):
        im.resize((320, 288), Image.NEAREST).save(
            os.path.join(SHOTS, 'shot-%s-%02d.png' % (tag, i)))


if __name__ == '__main__':
    main()
