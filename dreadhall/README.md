# DREADHALL

A first-person shooter for the original Game Boy (DMG), written in RGBDS
assembly. Raycast 3D walls with distance shading, scaled enemy billboards,
hitscan combat, pickups and a status bar — running at a steady 30 fps on
1978-vintage hardware.

**`dreadhall.gb` is the playable ROM** — checked in at the top of this folder,
ready to drop into an emulator or a flash cart. To rebuild it:

```
make            # builds build/dreadhall.gb and refreshes ./dreadhall.gb
```

Runs on real DMG hardware and any accurate emulator. Cartridge is MBC5, 32 KB
(two banks: code and tables in bank 0, artwork and level data in bank 1).

## Controls

| Input | Action |
| --- | --- |
| D-pad up/down | Walk forward / back |
| D-pad left/right | Turn |
| B + left/right | Strafe |
| A | Fire |
| Start | Begin / continue |

Find the exit. Everything in here is already awake.

## How the renderer works

The Game Boy has no framebuffer, no divide instruction and no multiply. The
whole design falls out of working around those three facts.

**The viewport is a tilemap, not a bitmap.** The 3D view is 20 × 14 tiles
(160 × 112 px) above a 4-row status bar, with one raycast column per tile
column. Writing pixels is impossible — there is nowhere near enough VRAM
bandwidth — so a wall column is instead *assembled out of a static tile set*:

```
[ceiling] [top cap] [wall body] × n [bottom cap] [floor]
```

The horizon sits at y=56, which is exactly a tile boundary. That is the trick
that makes the whole thing work: because a wall column is always centred on the
horizon, its top and bottom edges can never land in the same tile, so a wall of
*any* height is covered by 15 tiles per shading level (1 body, 7 top caps, 7
bottom caps). Six shading levels plus ceiling and floor is 92 tiles total.

Rendering a frame is therefore 280 tilemap bytes, not 3.6 KB of pixels.

**Double-buffered maps, so nothing tears.** 280 bytes is still more than fits in
one vblank, so the two background maps at `$9800` and `$9C00` are used as front
and back buffers. Half the frame is pushed per vblank with stack-pointer reads
(`pop de` / `ld [hl],e` / `inc l` — 4.5 cycles a byte), and when the last row
lands the buffers are swapped by flipping one bit of `LCDC`. The renderer fills
a second WRAM buffer while the first is draining, so the frame period is
`max(render, upload)` rather than their sum. That is what gets it to 30 fps.

**No division anywhere.** The DDA grid walk needs `1/|cos|` and `1/|sin|`, and
the projection needs `height = k / distance`. All of it is precomputed into
page-aligned tables so a lookup is `ld h, HIGH(tab)+k` / `ld l, index` /
`ld a, [hl]`. The per-column wall-height tables also fold in the fisheye
correction, so there is no cosine multiply in the hot path at all.

**The inner loop is branch-duplicated.** The DDA steps X and Y in two separate
copies of the code, so which axis was crossed is implied by *which hit label you
reach* — no side flag to store or test. That keeps the grid step at ~37 cycles.

Sprites are 8×16 OBJs. Enemies are billboards drawn from four pre-scaled
versions of the artwork, picked by distance and positioned so their feet land on
the floor line. Sprites 0–21 are reserved for the weapon, because when more than
ten sprites share a scanline the DMG keeps the ones earliest in OAM — put the
gun last and a close enemy erases it.

## Layout

```
src/
  main.asm      init, game-state machine, vblank uploader, math helpers
  render.asm    raycaster and tilemap column builder
  player.asm    movement, wall sliding, weapon and hitscan
  entity.asm    enemy AI, billboard projection, OAM assembly
  hud.asm       status bar
  screens.asm   title / death / escape screens
  sound.asm     one-shot effects
  gen/          generated: tiles, tables, level  (produced by the Makefile)
tools/
  gen_assets.py all artwork, math tables and the level, emitted as .inc files
  shot.py       headless PyBoy capture harness
  demo.py       autopilot that plays the game through the joypad
```

Everything under `src/gen/` is generated. `tools/gen_assets.py` draws the tiles
and sprites procedurally, computes the lookup tables, and carves the level with
a recursive-backtracker maze that is then braided and opened into rooms. It
asserts that the exit and every enemy and pickup is reachable before emitting
anything, so an unwinnable level fails the build.

## Testing

`tools/demo.py` is an autopilot: it reads the player position out of WRAM, runs
a BFS over the same level data the ROM was built from, and presses the d-pad to
follow the path, shooting whatever lines up with the crosshair. It plays the
level start to finish through the real input path, which makes it an end-to-end
test of movement, collision, the raycaster, billboard projection and hit
detection all at once.

```
python3 tools/demo.py build/dreadhall.gb --out shots --sheet shots/sheet.png
```
