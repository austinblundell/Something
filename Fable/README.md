# FABLE — Title Screen

A Game Boy title screen for *FABLE*, rendered at the DMG's native
160×144 resolution using only the four original Game Boy green shades:

| Shade | Hex       | Use |
|-------|-----------|-----|
| 0     | `#0f380f` | silhouettes, outlines, night sky |
| 1     | `#306230` | shadows, water, mid sky |
| 2     | `#8bac0f` | moonlit rims, highlights |
| 3     | `#9bbc0f` | moon, lit windows, logo |

## The scene

- Bayer-dithered night sky fading from near-black to a pale horizon glow
- A cratered moon with a dragon silhouette crossing it
- Procedurally built castle on a crag — crenellated towers, spires with
  pennants, lit windows, and a glowing gate
- Moonlit lake with a broken-glade reflection and a wavering castle mirror
- Pine-framed foreground banks
- Hand-set beveled **FABLE** logotype with outline, drop shadow, and
  flanking diamond sparks
- `PRESS START` in a 3×5 pixel font

## Files

- `title_screen.png` — the real thing, 160×144, indexed 4-color
- `title_screen_4x.png` — 4× nearest-neighbor preview
- `make_title.py` — generator; every pixel is placed procedurally
  (no external art assets). Regenerate with:

```sh
python3 make_title.py   # requires Pillow
```
