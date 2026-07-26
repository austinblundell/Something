#!/usr/bin/env python3
"""Run the ROM headlessly in PyBoy and capture screenshots.

Usage:
  python3 tools/shot.py out.png [frames] [--hold BTN@START-END ...] [--tile N]

Buttons: up down left right a b start select
"""
import sys
import os

from pyboy import PyBoy

ROM = os.path.join(os.path.dirname(__file__), "..", "build", "gbhorizon.gb")

BUTTONS = ("up", "down", "left", "right", "a", "b", "start", "select")


def parse_hold(spec):
    btn, _, rng = spec.partition("@")
    start, _, end = rng.partition("-")
    return btn, int(start), int(end or start)


def main():
    args = [a for a in sys.argv[1:]]
    out = args.pop(0) if args else "shot.png"
    frames = 120
    holds = []
    shots = []
    scale = 3
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--hold":
            holds.append(parse_hold(args[i + 1]))
            i += 2
        elif a == "--at":
            shots = [int(x) for x in args[i + 1].split(",")]
            i += 2
        elif a == "--scale":
            scale = int(args[i + 1])
            i += 2
        else:
            frames = int(a)
            i += 1

    if not shots:
        shots = [frames]
    frames = max(frames, max(shots))

    pyboy = PyBoy(ROM, window="null")
    pyboy.set_emulation_speed(0)

    pressed = set()
    for f in range(frames + 1):
        for btn, s, e in holds:
            if f == s and btn not in pressed:
                pyboy.button_press(btn)
                pressed.add(btn)
            if f == e + 1 and btn in pressed:
                pyboy.button_release(btn)
                pressed.discard(btn)
        pyboy.tick()
        if f in shots:
            img = pyboy.screen.image.convert("RGB")
            if scale > 1:
                img = img.resize((160 * scale, 144 * scale), 0)
            name = out if len(shots) == 1 else out.replace(".png", f"_{f}.png")
            img.save(name)
            print("wrote", name)
    pyboy.stop(save=False)


if __name__ == "__main__":
    main()
