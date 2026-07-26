; ============================================================================
;  video.asm  --  picture loading, tile-map plumbing, colour palettes
; ============================================================================

; Picture descriptor, as emitted by tools/tileconv.py:
;   +0  db  tile count
;   +1  db  first VRAM tile
;   +2  dw  tile data
;   +4  dw  20x18 tile map
;   +6  dw  20x18 CGB attribute map (0 = none)
;   +8  dw  CGB palette data (0 = none)
;   +10 db  CGB palette count
;   +11 db  DMG BGP
;   +12 db  DMG OBP0
DEF PIC_SIZE EQU 13

SECTION "video", ROM0

; ----------------------------------------------------------------------------
; LoadPicture -- a = ROM bank, hl = descriptor address.
; Blanks the LCD for the transfer, so callers should already be faded out.
; ----------------------------------------------------------------------------
LoadPicture::
    ld  [wPicBank], a
    ld  a, l
    ld  [wPicPtr], a
    ld  a, h
    ld  [wPicPtr + 1], a
    ld  a, [wPicBank]
    call SetRomBank

    ; Snapshot the descriptor into WRAM so we can keep using hl freely.
    ld  a, [wPicPtr]
    ld  l, a
    ld  a, [wPicPtr + 1]
    ld  h, a
    ld  de, wPicDesc
    ld  c, PIC_SIZE
    call MemCopySmall

    call LcdOff

    ; --- tiles -------------------------------------------------------------
    ld  a, [wPicDesc + 1]       ; first tile
    ld  h, 0
    ld  l, a
    add hl, hl                  ; *16 -> byte offset into VRAM
    add hl, hl
    add hl, hl
    add hl, hl
    ld  de, _VRAM8000
    add hl, de
    ld  d, h
    ld  e, l                    ; de = VRAM destination
    ld  a, [wPicDesc + 2]
    ld  l, a
    ld  a, [wPicDesc + 3]
    ld  h, a                    ; hl = tile source
    ld  a, [wPicDesc]           ; tile count
    ld  b, 0
    ld  c, a
    ; bc = count * 16
    sla c
    rl  b
    sla c
    rl  b
    sla c
    rl  b
    sla c
    rl  b
    call MemCopy

    ; --- tile map ----------------------------------------------------------
    ld  a, [wPicDesc + 4]
    ld  l, a
    ld  a, [wPicDesc + 5]
    ld  h, a
    ld  de, _SCRN0
    call CopyScreenRows

    ; --- CGB attribute map -------------------------------------------------
    ld  a, [wIsCGB]
    and a
    jr  z, .noAttr
    ld  a, [wPicDesc + 6]
    ld  c, a
    ld  a, [wPicDesc + 7]
    ld  b, a
    or  c
    jr  z, .noAttr
    ld  a, 1
    ld  [rVBK], a
    ld  h, b
    ld  l, c
    ld  de, _SCRN0
    call CopyScreenRows
    xor a
    ld  [rVBK], a
.noAttr:

    ; --- palettes ----------------------------------------------------------
    ld  a, [wPicDesc + 10]
    ld  [wPalCount], a
    ld  a, [wIsCGB]
    and a
    jr  z, .dmgPal
    ld  a, [wPicDesc + 8]
    ld  c, a
    ld  a, [wPicDesc + 9]
    ld  b, a
    or  c
    jr  z, .dmgPal
    ld  h, b
    ld  l, c
    call LoadCgbPalettes
.dmgPal:
    ld  a, [wPicDesc + 11]
    ld  [wPicBGP], a
    ld  a, [wPicDesc + 12]
    ld  [wPicOBP], a

    call ApplyFade
    call PushPalettes           ; safe: the LCD is still off
    call LcdOn
    ret

; CopyScreenRows -- hl = 20x18 source, de = map base.  Handles the 32-wide
; stride of the hardware map.
CopyScreenRows:
    ld  b, SCRN_ROWS
.row:
    push de
    ld  c, SCRN_COLS
    call MemCopySmall
    pop de
    ld  a, e
    add MAP_STRIDE
    ld  e, a
    ld  a, d
    adc 0
    ld  d, a
    dec b
    jr  nz, .row
    ret

; ----------------------------------------------------------------------------
; LoadCgbPalettes -- hl = packed colour data, wPalCount palettes of 4 colours.
; Everything lands in wBGPalBase; the fade derives the shadow from it.
; ----------------------------------------------------------------------------
LoadCgbPalettes:
    ld  a, [wPalCount]
    and a
    ret z
    ld  b, a
    ld  de, wBGPalBase
.pal:
    ld  c, 8                    ; four BGR555 colours
    push bc
    call MemCopySmall
    pop bc
    dec b
    jr  nz, .pal

    ; Sprites get their own two palettes rather than borrowing the picture's.
    ; Rain, spray and the reticle are highlights: they have to stay brighter
    ; than whatever they are drawn over, including a lit lamp room.
    ld  hl, EffectPalette
    ld  de, wOBPalBase
    ld  c, 8
    call MemCopySmall
    ld  hl, EmberPalette
    ld  de, wOBPalBase + 8
    ld  c, 8
    call MemCopySmall
    call InstallUiPalettes
    ret

; Object palette 0: cold highlights -- rain, snow, spray, the reticle.
EffectPalette:
    dw $0000                    ; entry 0 is never drawn (transparent)
    dw (31) | (31 << 5) | (30 << 10)
    dw (19) | (24 << 5) | (29 << 10)
    dw (3) | (5 << 5) | (10 << 10)

; Object palette 1: warm highlights -- embers and sparks.
EmberPalette:
    dw $0000
    dw (31) | (29 << 5) | (20 << 10)
    dw (30) | (18 << 5) | (5 << 10)
    dw (10) | (4 << 5) | (2 << 10)

; InstallUiPalettes -- BG palette 6 is the chapter card, 7 the dialogue box.
; Both are fixed, and both are re-installed with every picture so a scene can
; never leave them scaled by a stale fade.
InstallUiPalettes::
    ld  a, [wIsCGB]
    and a
    ret z
    ld  hl, BoxPalette
    ld  de, wBGPalBase + 7 * 8
    ld  c, 8
    call MemCopySmall
    ld  hl, CardPalette
    ld  de, wBGPalBase + 6 * 8
    ld  c, 8
    call MemCopySmall
    ret

; The parchment the dialogue box is printed on: warm, not paper-white.
BoxPalette:
    dw (31) | (30 << 5) | (26 << 10)
    dw (25) | (21 << 5) | (16 << 10)
    dw (10) | (8 << 5) | (7 << 10)
    dw (2) | (2 << 5) | (4 << 10)

; Chapter cards run the other way round: dark ground, light lettering.
; The font draws ink in colour 3, so entry 3 is the bright one.
CardPalette:
    dw (1) | (2 << 5) | (4 << 10)
    dw (4) | (5 << 5) | (9 << 10)
    dw (14) | (15 << 5) | (18 << 10)
    dw (30) | (30 << 5) | (28 << 10)

; ----------------------------------------------------------------------------
; PushPalettes -- shadow -> hardware.  Called from VBlank (or with LCD off).
; ----------------------------------------------------------------------------
PushPalettes::
    ld  a, [wIsCGB]
    and a
    ret z
    ld  a, $80                  ; auto-increment from index 0
    ld  [rBCPS], a
    ld  hl, wBGPalShadow
    ld  b, 64
.bg:
    ld  a, [hl+]
    ld  [rBCPD], a
    dec b
    jr  nz, .bg
    ld  a, $80
    ld  [rOCPS], a
    ld  hl, wOBPalShadow
    ld  b, 16
.ob:
    ld  a, [hl+]
    ld  [rOCPD], a
    dec b
    jr  nz, .ob
    ret

; ----------------------------------------------------------------------------
; ClearBgMap -- fill the visible map with blank tiles and reset attributes.
; ----------------------------------------------------------------------------
ClearBgMap::
    ld  hl, _SCRN0
    ld  bc, 32 * 32
    ld  a, TILE_BLANK
    call MemFill
    ld  a, [wIsCGB]
    and a
    ret z
    ld  a, 1
    ld  [rVBK], a
    ld  hl, _SCRN0
    ld  bc, 32 * 32
    xor a
    call MemFill
    xor a
    ld  [rVBK], a
    ret

; FillBgMapRows -- b = first row, c = row count, a = tile.  LCD-off only.
FillBgMapRows::
    ld  d, a
    ld  hl, _SCRN0
    ld  a, b
    and a
    jr  z, .atRow
.advance:
    ld  a, l
    add MAP_STRIDE
    ld  l, a
    ld  a, h
    adc 0
    ld  h, a
    dec b
    jr  nz, .advance
.atRow:
    ld  b, c
.row:
    push hl
    ld  c, SCRN_COLS
.col:
    ld  a, d
    ld  [hl+], a
    dec c
    jr  nz, .col
    pop hl
    ld  a, l
    add MAP_STRIDE
    ld  l, a
    ld  a, h
    adc 0
    ld  h, a
    dec b
    jr  nz, .row
    ret

; ----------------------------------------------------------------------------
; Resident graphics
; ----------------------------------------------------------------------------
LoadFontTiles::
    ld  hl, FontTiles
    ld  de, _VRAM8000 + TILE_FONT_BASE * 16
    ld  bc, 64 * 16
    call MemCopy
    ret

LoadSpriteTiles::
    ld  hl, SpriteTiles
    ld  de, _VRAM8000 + TILE_SPRITE_BASE * 16
    ld  bc, 16 * 16
    call MemCopy
    ret

; MapAddr -- b = row, c = column -> hl = map address.
MapAddr::
    ld  hl, _SCRN0
    ld  a, b
    and a
    jr  z, .noRows
.rows:
    ld  a, l
    add MAP_STRIDE
    ld  l, a
    ld  a, h
    adc 0
    ld  h, a
    dec b
    jr  nz, .rows
.noRows:
    ld  a, l
    add c
    ld  l, a
    ld  a, h
    adc 0
    ld  h, a
    ret

SECTION "video ram", WRAM0
wPicDesc:: ds PIC_SIZE
