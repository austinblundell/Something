# GB HORIZON

A pseudo-3D racing game for the original Game Boy (DMG), written in RGBDS
assembly.

Real polygonal 3D is not on the table at 4 MHz with no multiplier, so the road
is built the way *Out Run* and *Top Gear* built theirs: a flat background image
reshaped by the raster beam, one scanline at a time.

```
   left bend            straight             right bend
  ___________         ___________         ___________
```

## Building

Needs [RGBDS](https://rgbds.gbdev.io/) 0.9+ and Python 3.

```sh
make                       # -> build/gbhorizon.gb
python3 tools/shot.py out.png 400 --hold a@90-93   # headless screenshot
```

`make` runs `tools/gen_assets.py` first, which generates every tile, tilemap
and lookup table into `src/gen/`. Nothing under `src/gen/` is hand-edited.

## Controls

| | |
|---|---|
| D-pad left/right | steer |
| B | brake — you need it for the hairpins |
| A / Start | start the race (on the car-select screen) |

Throttle is automatic; you accelerate up to the car's top speed unless you are
braking, on the grass, or leaning on the car in front.

## How the road works

The screen is split into two bands:

```
y =  0..47    sky / HUD      fixed SCX, fixed BGP
y = 48..143   road           per-scanline SCX and BGP
```

The background map holds **one straight road in perspective**, drawn once at
build time and never touched again. Everything else is raster trickery:

* **Curves** come from rewriting `SCX` on every one of the 96 road scanlines.
  The horizontal offset at a given scanline is `curve * shape(y)`, where
  `shape()` rises quadratically from 0 at the bottom of the screen to 192 at
  the horizon. Rather than multiply once per scanline, `BuildScxTable` walks
  the screen bottom-to-top adding `curve` into a 16-bit accumulator once per
  unit of `shape()` — 192 additions in total, emitted fully unrolled by the
  generator. That is ~8 cycles per scanline instead of ~60.

* **Forward motion** comes from rewriting `BGP` on every road scanline. Road
  tiles use palette index 1 for asphalt, 2 for the rumble strips and 3 for the
  lane dashes, so swapping the palette makes bands of road light up and slide
  toward the camera without touching a single tile. A scanline's band is just
  bit 0 of the high byte of `camZ + z(y)`, with `z(y)` precomputed. Near the
  horizon the perspective squeezes bands below two scanlines, so that stretch
  uses a flat palette instead of shimmering.

Because no tile data changes at run time, the entire frame budget is free for
physics, opponents and the HUD.

## Why the road is 93px wide

The background is 256px across and the screen window is 160px, so the road
repeats every 256px. If the gap between repeats is narrower than the window,
some scroll value will show the road at *both* screen edges at once. That gap
is `256 - roadWidth`, so a road wider than 95px puts a hard ceiling on how far
the curve may scroll before it visibly wraps — which is exactly what caps how
tight a corner can be.

Holding the road at 93px (half width 46) makes the gap 163px, wider than the
window, so **no scroll value can ever show the road twice** and the curve
offset becomes unbounded. That is what buys the hairpins: the road can sweep
clean off the side of the screen. It also leaves grass either side, which is
where roadside scenery will go.

## Corners

Track curvature is a byte per segment. Roughly:

| magnitude | corner |
|---|---|
| ~40 | sweeper |
| ~70 | proper corner |
| 96+ | hairpin — sweeps the road off the screen edge |

The warning icon reflects this: a single arrow for a normal corner, a doubled
chevron for a hairpin.

Curvature eases toward its target faster when the gap is large, otherwise a
hairpin would still be unwinding when its segment ended. The comparison is
done in biased (+128) space so the gap between two opposite curvatures cannot
overflow a signed byte.

Carrying speed doubles the centrifugal pull, so a hairpin has to be braked
for. That is what makes the grip stat matter: the SPORTSTER is the fastest car
and the only one that cannot hold a hairpin flat out — taken at full throttle
it spends about a tenth of the lap on the grass, and braking for the tight
stuff is worth roughly 11 units of average speed over not braking.

## Frame budget

The raster loop owns scanlines 47–143, so all game logic has to fit in vertical
blank plus the 47 sky lines — about 6500 cycles. Overrunning it means the road
effect misses its start line and the screen renders flat for a whole frame, so
the loop is deliberately cheap:

| stage | cost |
|---|---|
| DMA + HUD | ~4 lines |
| input + player physics | ~3 lines |
| `BuildScxTable` | ~11 lines |
| `BuildBgpTable` | ~10 lines |
| `BuildOam` (opponents + sprites) | ~13 lines |

Total ~42 of the 57 available lines. Two decisions bought most of that
headroom: opponents occupy one of 16 discrete lanes so their screen position is
a `LaneTable[line][lane]` lookup instead of a software multiply, and opponent
physics runs in the same walk that builds the sprite list.

## Opponents

Eleven cars, each holding a relative depth `rz`, a lane and a speed. They are
drawn at one of three sprite sizes depending on which scanline they land on,
and recycled off-screen when they fall too far behind or run too far ahead, so
traffic is continuous. Running into one clamps you to its speed until you pull
out of its slipstream.

## Cars

| | top speed | accel | grip |
|---|---|---|---|
| HATCH GT | 88 | 3 | 4 |
| SPORTSTER | 112 | 3 | 3 |
| BRUTE 4X4 | 76 | 2 | 5 |

Grip is the steering rate, which is what keeps the SPORTSTER honest — it is the
fastest car and the hardest to hold through a bend.

## Layout

```
src/main.asm         the game
src/hardware.inc     register definitions
tools/gen_assets.py  generates all of src/gen/ (tiles, maps, tables)
tools/shot.py        headless PyBoy screenshot harness
```

## Not done yet

* No sound.
* Roadside scenery is empty.
* Opponents are not depth-sorted against each other, so two cars at nearly the
  same distance can overlap in the wrong order for a frame.
* No lap counter, timer or finish line — it is an endless road today.
* Going off onto the grass drags you down to a crawl rather than stopping you;
  the penalty is bigger than any car's acceleration, so draining it to zero
  would strand you there with no way to drive back on.
