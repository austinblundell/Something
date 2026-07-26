#!/usr/bin/env python3
"""
Autopilot capture run for DREADHALL.

Drives the ROM entirely through the joypad -- no memory pokes -- by reading the
player's position out of WRAM, running a BFS over the same level data the ROM
was built from, and pressing the d-pad to follow the path. It shoots whenever an
enemy silhouette sits under the crosshair.

That makes the screenshots a genuine playthrough, and doubles as an end-to-end
test of movement, collision, the raycaster and the hit detection.

  python3 tools/demo.py build/dreadhall.gb --out shots
"""

import argparse
import os
import sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shot import Runner, save_all, contact_sheet          # noqa: E402
import gen_assets as G                                    # noqa: E402

# angle units: 0 = +X (east), 64 = +Y (south), 128 = -X, 192 = -Y
DIR_ANGLE = {(1, 0): 0, (0, 1): 64, (-1, 0): 128, (0, -1): 192}


def load_symbols(path):
    sym = {}
    for line in open(path):
        parts = line.split()
        if len(parts) == 2 and ":" in parts[0]:
            sym[parts[1]] = int(parts[0].split(":")[1], 16)
    return sym


class Bot:
    def __init__(self, rom, symfile):
        self.r = Runner(rom)
        self.sym = load_symbols(symfile)
        self.m = self.r.pyboy.memory
        self.grid, self.start, self.enemies, self.pickups, self.exit, self.ang0 = \
            G.parse_level()

    # ---- state accessors -------------------------------------------------
    def cell(self):
        return (self.m[self.sym["wPlayerX"] + 1], self.m[self.sym["wPlayerY"] + 1])

    def angle(self):
        return self.m[self.sym["wPlayerAng"]]

    def hp(self):
        return self.m[self.sym["wPlayerHp"]]

    def state(self):
        return self.m[self.sym["wGameState"]]

    def visible_enemy(self):
        """Nearest-to-centre visible enemy as (offset, screenX, halfWidth)."""
        best = None
        for i in range(6):
            if not self.m[self.sym["wEsVis"] + i]:
                continue
            sx = self.m[self.sym["wEsX"] + i]
            hw = self.m[self.sym["wEsW"] + i]
            d = abs(sx - 80)
            if best is None or d < best[0]:
                best = (d, sx, hw)
        return best

    def target_under_crosshair(self):
        v = self.visible_enemy()
        return v is not None and v[0] < max(v[2], 6)

    def fight_frame(self):
        """Aim at and shoot the nearest visible enemy. True if engaged."""
        v = self.visible_enemy()
        if v is None:
            return False
        d, sx, hw = v
        self.r.release("up")
        if d > max(hw // 2, 5):
            self.r.release("a")
            self.r.hold("left" if sx < 80 else "right")
        else:
            self.r.release("left", "right")
            # the weapon triggers on a fresh press, so the button has to be
            # pulsed rather than held
            self._trig = not getattr(self, "_trig", False)
            if self._trig:
                self.r.hold("a")
            else:
                self.r.release("a")
        self.r.tick(1)
        return True

    # ---- navigation ------------------------------------------------------
    def path_to(self, goal):
        src = self.cell()
        prev = {src: None}
        q = deque([src])
        while q:
            c = q.popleft()
            if c == goal:
                break
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (c[0] + d[0], c[1] + d[1])
                if (0 <= n[0] < G.MAP_W and 0 <= n[1] < G.MAP_H
                        and self.grid[n[1]][n[0]] == 0 and n not in prev):
                    prev[n] = c
                    q.append(n)
        if goal not in prev:
            return []
        out, c = [], goal
        while c != src:
            out.append(c)
            c = prev[c]
        return out[::-1]

    def step_toward(self, waypoint, shoot=True):
        """One frame of input aiming at an adjacent cell."""
        cx, cy = self.cell()
        d = (waypoint[0] - cx, waypoint[1] - cy)
        want = DIR_ANGLE.get(d)
        if want is None:
            self.r.tick(1)
            return
        diff = (want - self.angle()) & 0xFF
        if diff > 6 and diff < 250:
            self.r.hold("right" if diff < 128 else "left")
            self.r.release("up")
        else:
            self.r.release("left", "right")
            self.r.hold("up")
        self.r.release("a")
        self.r.tick(1)

    def travel(self, goal, max_frames=1500, on_frame=None, shoot=True,
               fight_budget=240):
        frames = 0
        fighting = 0
        while frames < max_frames and self.state() == 1:
            if self.cell() == goal:
                break
            if shoot and fighting < fight_budget and self.fight_frame():
                fighting += 1
                frames += 1
                if on_frame:
                    on_frame(frames)
                continue
            path = self.path_to(goal)
            if not path:
                break
            self.step_toward(path[0], shoot=False)
            frames += 1
            if on_frame:
                on_frame(frames)
        self.r.release_all()
        self.r.tick(4)
        return frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--out", default="shots")
    ap.add_argument("--sheet", default=None)
    ap.add_argument("--sym", default=None)
    args = ap.parse_args()
    symfile = args.sym or args.rom.rsplit(".", 1)[0] + ".sym"

    bot = Bot(args.rom, symfile)
    r = bot.r
    r.boot()
    r.shot("01_title", "Title")
    r.tap("start", 6, 40)
    r.shot("02_spawn", "Spawn: looking down the hall")

    grabbed = {"n": 0}

    def watcher(_f):
        # grab a frame whenever an enemy comes into view, up to a few times
        if bot.target_under_crosshair() and grabbed["n"] < 4:
            grabbed["n"] += 1
            r.shot("1%d_contact" % grabbed["n"],
                   "Contact  (hp %d)" % bot.hp())

    # tour the level: pickups first, then the exit, fighting on the way
    waypoints = ([tuple(p[:2]) for p in bot.pickups[:2]]
                 + [tuple(e) for e in bot.enemies[:3]]
                 + [tuple(p[:2]) for p in bot.pickups[2:]]
                 + [bot.exit])
    labels = ["Ammo crate", "Medkit", "Hunting", "Hunting", "Hunting",
              "Ammo crate", "Medkit", "The way out"]
    for i, wp in enumerate(waypoints):
        used = bot.travel(wp, on_frame=watcher)
        if bot.state() != 1:
            break
        r.shot("%02d_wp" % (i + 3),
               "%s  kills %d  hp %d" % (labels[min(i, len(labels) - 1)],
                                        bot.m[bot.sym["wKills"]], bot.hp()))

    r.tick(120)
    r.shot("09_end", "Outcome  state=%d" % bot.state())
    print("final state=%d  kills=%d  hp=%d  ammo=%d"
          % (bot.state(), bot.m[bot.sym["wKills"]], bot.hp(),
             bot.m[bot.sym["wAmmo"]]))

    paths = save_all(r, args.out, 3)
    if args.sheet:
        contact_sheet(r, args.sheet, cols=4, scale=2)
    r.stop()
    for p in paths:
        print(p)


if __name__ == "__main__":
    main()
