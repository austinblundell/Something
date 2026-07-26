; ============================================================================
;  fade.asm  --  cross-fades that work on both DMG and Game Boy Color
;
;  On DMG there is one background palette register, so fading means walking
;  BGP through a ramp that pushes every shade toward black.  On CGB the real
;  colours are scaled component-wise, which gives a proper dip to black
;  instead of a four-step posterised lurch.
; ============================================================================

SECTION "fade", ROM0

; ----------------------------------------------------------------------------
; ApplyFade -- rebuild every shadow palette for the current wFadeLevel.
; ----------------------------------------------------------------------------
ApplyFade::
    ld  a, [wFadeLevel]
    cp  FADE_MAX + 1
    jr  c, .levelOk
    ld  a, FADE_MAX
    ld  [wFadeLevel], a
.levelOk:
    ; Chapter cards print light-on-dark, which on DMG means walking BGP down
    ; an inverted ramp -- there is only the one background palette register.
    ld  hl, DmgFadeTable
    ld  d, a
    ld  a, [wPalMode]
    and a
    jr  z, .haveTable
    ld  hl, DmgFadeTableInv
.haveTable:
    ld  a, d
    add l
    ld  l, a
    ld  a, h
    adc 0
    ld  h, a
    ld  a, [hl]
    ld  [wBGPShadow], a
    ld  a, [wFadeLevel]
    ld  hl, ObjFadeTable
    add l
    ld  l, a
    ld  a, h
    adc 0
    ld  h, a
    ld  a, [hl]
    ld  [wOBP0Shadow], a
    ld  [wOBP1Shadow], a

    ld  a, [wIsCGB]
    and a
    ret z

    ; wScalePtr = PalScale + level * 32
    ld  a, [wFadeLevel]
    ld  h, 0
    ld  l, a
    add hl, hl
    add hl, hl
    add hl, hl
    add hl, hl
    add hl, hl
    ld  de, PalScale
    add hl, de
    ld  a, l
    ld  [wScalePtr], a
    ld  a, h
    ld  [wScalePtr + 1], a

    ld  hl, wBGPalBase
    ld  de, wBGPalShadow
    ld  b, 32
    call ScaleColours

    ld  hl, wOBPalBase
    ld  de, wOBPalShadow
    ld  b, 8
    call ScaleColours

    ld  a, 1
    ld  [wPalDirty], a
    ret

; ScaleColours -- hl = source colours, de = destination, b = colour count.
ScaleColours:
.colour:
    ld  a, [hl+]
    ld  [wFadeLo], a
    ld  a, [hl+]
    ld  [wFadeHi], a
    push hl
    push bc

    ; red = lo & 31
    ld  a, [wFadeLo]
    and 31
    call ScaleComp
    ld  [wFadeR], a

    ; green = (lo >> 5) | ((hi & 3) << 3)
    ld  a, [wFadeLo]
    rlca
    rlca
    rlca
    and 7
    ld  c, a
    ld  a, [wFadeHi]
    and 3
    add a
    add a
    add a
    or  c
    call ScaleComp
    ld  [wFadeG], a

    ; blue = (hi >> 2) & 31
    ld  a, [wFadeHi]
    rrca
    rrca
    and 31
    call ScaleComp
    ld  [wFadeB], a

    ; repack low byte: red | ((green & 7) << 5)
    ld  a, [wFadeG]
    and 7
    rrca
    rrca
    rrca
    ld  c, a
    ld  a, [wFadeR]
    or  c
    ld  [wFadeOutLo], a
    ; repack high byte: (green >> 3) | (blue << 2)
    ld  a, [wFadeG]
    rrca
    rrca
    rrca
    and 3
    ld  c, a
    ld  a, [wFadeB]
    add a
    add a
    or  c
    ld  [wFadeOutHi], a

    pop bc
    pop hl
    ld  a, [wFadeOutLo]
    ld  [de], a
    inc de
    ld  a, [wFadeOutHi]
    ld  [de], a
    inc de
    dec b
    jr  nz, .colour
    ret

; ScaleComp -- a = 0..31 component -> a = component scaled by the fade level.
ScaleComp:
    push hl
    ld  hl, wScalePtr
    ld  c, [hl]
    inc hl
    ld  b, [hl]
    ld  h, b
    ld  l, c
    add l
    ld  l, a
    ld  a, h
    adc 0
    ld  h, a
    ld  a, [hl]
    pop hl
    ret

; ----------------------------------------------------------------------------
; FadeOut / FadeIn -- b = frames to hold each of the five steps.
; ----------------------------------------------------------------------------
FadeOut::
    ld  a, [wFadeLevel]
    and a
    ret z
.step:
    ld  a, [wFadeLevel]
    dec a
    ld  [wFadeLevel], a
    call ApplyFade
    push bc
    call WaitFrames
    pop bc
    ld  a, [wFadeLevel]
    and a
    jr  nz, .step
    ret

FadeIn::
    ld  a, [wFadeLevel]
    cp  FADE_MAX
    ret z
.step:
    ld  a, [wFadeLevel]
    inc a
    ld  [wFadeLevel], a
    call ApplyFade
    push bc
    call WaitFrames
    pop bc
    ld  a, [wFadeLevel]
    cp  FADE_MAX
    jr  nz, .step
    ret

; SetFade -- a = level, applied immediately.
SetFade::
    ld  [wFadeLevel], a
    call ApplyFade
    ret

; ----------------------------------------------------------------------------
; FlashScreen -- b = number of flashes.  Lightning, or the ember catching.
; ----------------------------------------------------------------------------
FlashScreen::
.loop:
    push bc
    ld  a, $00                  ; every shade to white
    ld  [wBGPShadow], a
    ld  a, [wIsCGB]
    and a
    jr  z, .noWhite
    call PalToWhite
.noWhite:
    ld  b, 3
    call WaitFrames
    call ApplyFade
    ld  b, 5
    call WaitFrames
    pop bc
    dec b
    jr  nz, .loop
    ret

PalToWhite:
    ld  hl, wBGPalShadow
    ld  b, 64
.fill:
    ld  a, $FF
    ld  [hl+], a
    dec b
    jr  nz, .fill
    ld  a, 1
    ld  [wPalDirty], a
    ret

; ----------------------------------------------------------------------------
;  data
; ----------------------------------------------------------------------------
; BGP values for fade levels 0..4.  Field order is [c3][c2][c1][c0].
DmgFadeTable:
    db $FF      ; 3 3 3 3  -- black
    db $FE      ; 3 3 3 2
    db $F9      ; 3 3 2 1
    db $F8      ; 3 3 2 0
    db $E4      ; 3 2 1 0  -- normal

; The same ramp for light-on-dark chapter cards: colour 0 is the dark ground
; and colour 3 the lettering, so the shades run the other way.
DmgFadeTableInv:
    db $FF      ; everything black
    db $FF
    db $BF      ; 2 3 3 3
    db $6F      ; 1 2 3 3
    db $1B      ; 0 1 2 3  -- normal

; Sprites keep colour 1 at full white for as long as possible: rain and
; sparks are highlights, and a grey highlight reads as dirt.
ObjFadeTable:
    db $FF
    db $F8      ; 3 3 2 -
    db $F4      ; 3 3 1 -
    db $F0      ; 3 3 0 -
    db $E0      ; 3 2 0 -

; PalScale[level][component] = component * level / 4.
PalScale:
FOR LVL, 0, 5
FOR COMP, 0, 32
    db (COMP * LVL) / 4
ENDR
ENDR

SECTION "fade ram", WRAM0
wFadeLo::     db
wFadeHi::     db
wFadeR::      db
wFadeG::      db
wFadeB::      db
wFadeOutLo::  db
wFadeOutHi::  db
wScalePtr::   dw
