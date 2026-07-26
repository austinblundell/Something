; ============================================================================
;  util.asm  --  memory helpers, banking, LCD control, VRAM write queue
; ============================================================================

SECTION "util", ROM0

; MemFill -- hl = dest, bc = count, a = value.  Clobbers a, bc, hl.
MemFill::
    ld  d, a
.loop:
    ld  a, d
    ld  [hl+], a
    dec bc
    ld  a, b
    or  c
    jr  nz, .loop
    ret

; MemCopy -- hl = source, de = dest, bc = count.
MemCopy::
    ld  a, [hl+]
    ld  [de], a
    inc de
    dec bc
    ld  a, b
    or  c
    jr  nz, MemCopy
    ret

; MemCopySmall -- as MemCopy but c = count (1..255), a little tighter.
MemCopySmall::
.loop:
    ld  a, [hl+]
    ld  [de], a
    inc de
    dec c
    jr  nz, .loop
    ret

; SetRomBank -- a = bank number (MBC5, banks 1..255 used here).
SetRomBank::
    ld  [rROMB0], a
    ld  a, 0
    ld  [rROMB1], a
    ret

; ------------------------------------------------------------------ the LCD
LcdOff::
    ld  a, [rLCDC]
    and LCDCF_ON
    ret z                       ; already off
.waitVBlank:
    ld  a, [rLY]
    cp  144
    jr  c, .waitVBlank
    ld  a, [rLCDC]
    and $FF ^ LCDCF_ON
    ld  [rLCDC], a
    ret

LcdOn::
    ld  a, [wLCDCShadow]
    or  LCDCF_ON
    ld  [wLCDCShadow], a
    ld  [rLCDC], a
    ret

; --------------------------------------------------------------- OAM DMA
InstallOamDma::
    ld  hl, OamDmaCode
    ld  de, hOamDma
    ld  c, OamDmaCodeEnd - OamDmaCode
    call MemCopySmall
    ret

OamDmaCode:
    ldh [rDMA], a
    ld  a, 40
.wait:
    dec a
    jr  nz, .wait
    ret
OamDmaCodeEnd:

; --------------------------------------------------------- shadow OAM helpers
; ResetOam -- drop every sprite off-screen and rewind the allocator.
ResetOam::
    ld  hl, wShadowOAM
    ld  b, 40
.loop:
    xor a
    ld  [hl+], a                ; Y = 0 is above the screen
    ld  [hl+], a
    ld  [hl+], a
    ld  [hl+], a
    dec b
    jr  nz, .loop
    xor a
    ld  [wOamNext], a
    ret

; OamPut -- b = Y, c = X, d = tile, e = attributes.  Allocates the next slot.
OamPut::
    ld  a, [wOamNext]
    cp  40
    ret nc
    ld  h, a
    inc a
    ld  [wOamNext], a
    ld  a, h
    add a                       ; *4
    add a
    ld  l, a
    ld  h, HIGH(wShadowOAM)
    ld  a, l
    add LOW(wShadowOAM)
    ld  l, a
    ld  a, b
    ld  [hl+], a
    ld  a, c
    ld  [hl+], a
    ld  a, d
    ld  [hl+], a
    ld  a, e
    ld  [hl+], a
    ret

; ------------------------------------------------------- deferred VRAM writes
; VqPush -- de = VRAM address, a = byte.  Applied during the next VBlank.
VqPush::
    ld  b, a
    ld  a, [wVqCount]
    cp  VQ_MAX
    ret nc
    ld  c, a
    inc a
    ld  [wVqCount], a
    ; wVqValue[c] = b
    ld  hl, wVqValue
    ld  a, l
    add c
    ld  l, a
    ld  a, h
    adc 0
    ld  h, a
    ld  [hl], b
    ; wVqDest[c*2] = de
    ld  a, c
    add a
    ld  hl, wVqDest
    add l
    ld  l, a
    ld  a, h
    adc 0
    ld  h, a
    ld  a, e
    ld  [hl+], a
    ld  a, d
    ld  [hl], a
    ret

FlushVramQueue::
    ld  a, [wVqCount]
    and a
    ret z
    ld  b, a
    ld  c, 0
.loop:
    ; de = wVqDest[c*2]
    ld  a, c
    add a
    ld  hl, wVqDest
    add l
    ld  l, a
    ld  a, h
    adc 0
    ld  h, a
    ld  a, [hl+]
    ld  e, a
    ld  a, [hl]
    ld  d, a
    ; a = wVqValue[c]
    ld  hl, wVqValue
    ld  a, l
    add c
    ld  l, a
    ld  a, h
    adc 0
    ld  h, a
    ld  a, [hl]
    ld  [de], a
    inc c
    dec b
    jr  nz, .loop
    xor a
    ld  [wVqCount], a
    ret

; --------------------------------------------------------------------- random
; Rand -- an 8-bit xorshift.  Returns a and clobbers nothing else, because
; every caller is inside a loop that keeps its index in bc.
Rand::
    push hl
    ld  a, [wRandState]
    ld  [wRandTmp], a
    rlca
    rlca
    rlca
    ld  hl, wRandTmp
    xor [hl]
    ld  [hl], a
    ld  a, [wRandState]
    rrca
    ld  hl, wRandTmp
    xor [hl]
    inc a
    ld  [wRandState], a
    pop hl
    ret

SECTION "rand ram", WRAM0
wRandState:: db
wRandTmp::   db

SECTION "hram", HRAM
hOamDma:: ds 8
hBootA::  db
