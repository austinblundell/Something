#!/usr/bin/env python3
"""
Headless capture harness for DREADHALL.

Boots the ROM in PyBoy, drives the pad through a scripted sequence and writes
PNGs (optionally scaled up, optionally arranged into a labelled contact sheet).

  python3 tools/shot.py build/dreadhall.gb --out shots
"""

import argparse
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BUTTONS = ("up", "down", "left", "right", "a", "b", "start", "select")


class Runner:
    def __init__(self, rom, scale=3):
        from pyboy import PyBoy
        self.pyboy = PyBoy(rom, window="null", sound_emulated=False)
        self.scale = scale
        self.held = set()
        self.shots = []

    def hold(self, *btns):
        for b in btns:
            if b not in self.held:
                self.pyboy.button_press(b)
                self.held.add(b)

    def release(self, *btns):
        for b in btns or tuple(self.held):
            if b in self.held:
                self.pyboy.button_release(b)
                self.held.discard(b)

    def release_all(self):
        for b in list(self.held):
            self.pyboy.button_release(b)
        self.held.clear()

    def tick(self, n=1):
        # One frame at a time: a multi-frame tick() coalesces queued pad events,
        # so short presses get dropped. render=True is required or screen.image
        # hands back a stale frame.
        for _ in range(n):
            self.pyboy.tick(1, True)

    def tap(self, btn, frames=4, after=4):
        self.hold(btn)
        self.tick(frames)
        self.release(btn)
        self.tick(after)

    def walk(self, frames, *btns):
        self.hold(*btns)
        self.tick(frames)
        self.release(*btns)

    def boot(self):
        """PyBoy runs its own boot ROM animation for ~150 frames; pad presses
        before the cartridge takes over are simply lost."""
        self.tick(200)

    def image(self):
        return self.pyboy.screen.image.convert("RGB")

    def shot(self, name, label=None):
        img = self.image()
        self.shots.append((name, label or name, img.copy()))
        return img

    def stop(self):
        self.pyboy.stop(save=False)


def save_all(runner, outdir, scale):
    os.makedirs(outdir, exist_ok=True)
    paths = []
    for name, _label, img in runner.shots:
        p = os.path.join(outdir, f"{name}.png")
        img.resize((160 * scale, 144 * scale), Image.NEAREST).save(p)
        paths.append(p)
    return paths


def contact_sheet(runner, path, cols=3, scale=2, pad=10, label_h=16):
    if not runner.shots:
        return None
    w, h = 160 * scale, 144 * scale
    n = len(runner.shots)
    rows = (n + cols - 1) // cols
    W = cols * w + pad * (cols + 1)
    H = rows * (h + label_h) + pad * (rows + 1)
    sheet = Image.new("RGB", (W, H), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    for i, (_name, label, img) in enumerate(runner.shots):
        r, c = divmod(i, cols)
        x = pad + c * (w + pad)
        y = pad + r * (h + label_h + pad)
        sheet.paste(img.resize((w, h), Image.NEAREST), (x, y))
        d.rectangle([x - 1, y - 1, x + w, y + h], outline=(90, 90, 100))
        d.text((x + 2, y + h + 3), label, fill=(210, 210, 200))
    sheet.save(path)
    return path


# ---------------------------------------------------------------------------
def scripted(runner):
    """Boot -> title -> a tour of the level."""
    runner.boot()
    runner.shot("01_title", "Title screen")

    runner.tap("start", 6, 30)
    runner.tick(20)
    runner.shot("02_spawn", "Spawn: corridor view")

    runner.walk(24, "up")
    runner.tick(6)
    runner.shot("03_forward", "Walking forward")

    runner.walk(26, "right")
    runner.tick(8)
    runner.shot("04_turn", "Turned right")

    runner.walk(40, "up")
    runner.tick(8)
    runner.shot("05_corridor", "Down the corridor")

    runner.tap("a", 4, 4)
    runner.shot("06_fire", "Firing")
    runner.tick(20)

    runner.walk(30, "left")
    runner.walk(50, "up")
    runner.tick(8)
    runner.shot("07_explore", "Exploring")

    runner.walk(40, "up")
    runner.tick(8)
    runner.shot("08_more", "Deeper in")
    return runner


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--out", default="shots")
    ap.add_argument("--scale", type=int, default=3)
    ap.add_argument("--sheet", default=None)
    args = ap.parse_args()

    r = Runner(args.rom)
    scripted(r)
    paths = save_all(r, args.out, args.scale)
    r.stop()
    for p in paths:
        print(p)
    if args.sheet:
        print(contact_sheet(r, args.sheet))


if __name__ == "__main__":
    main()
