; ============================================================================
;  EMBERLIGHT  --  Keeper of the Last Light
;  A story-driven Game Boy game in RGBDS assembly.
;
;  main.asm  --  vectors, boot, the interrupt handlers and the frame loop.
; ============================================================================

INCLUDE "hardware.inc"
INCLUDE "engine/defs.inc"

; ------------------------------------------------------------------ vectors
SECTION "vblank vector", ROM0[$0040]
    jp VBlankHandler

SECTION "stat vector", ROM0[$0048]
    jp StatHandler

SECTION "timer vector", ROM0[$0050]
    reti

SECTION "serial vector", ROM0[$0058]
    reti

SECTION "joypad vector", ROM0[$0060]
    reti

SECTION "entry", ROM0[$0100]
    nop
    jp Start
    ; $0104-$014F is the cartridge header.  Reserve it explicitly: rgblink
    ; will happily pack data into the gap, and rgbfix then stamps the Nintendo
    ; logo straight over whatever landed there.
    ds $0150 - @, $00

; ---------------------------------------------------------------------- boot
SECTION "boot", ROM0

Start:
    di
    ld  sp, $E000               ; the stack grows down from the top of WRAM
    ; The boot ROM leaves $11 in A on a Game Boy Color.  Park it in HRAM:
    ; the WRAM clear below would eat it anywhere else.
    ldh [hBootA], a

    call LcdOff

    ; --- wipe everything we are about to rely on ---------------------------
    ld  hl, _VRAM
    ld  bc, $2000
    xor a
    call MemFill

    ; Clear WRAM, but stop short of $DF00: the stack lives above that, and
    ; MemFill's own return address is sitting on it right now.
    ld  hl, _RAM
    ld  bc, $1F00
    xor a
    call MemFill

    ld  hl, wShadowOAM
    ld  bc, 160
    ld  a, 0
    call MemFill

    ; Now that WRAM is quiet, record what hardware we woke up on: the boot
    ; ROM leaves $11 in A on a Game Boy Color and $01 on a DMG.  Everything
    ; colour-related keys off this, and so does the picture loader -- on a
    ; DMG it must not write attribute maps, because there is no second VRAM
    ; bank for them to land in.
    ldh a, [hBootA]
    cp  $11
    ld  a, 0
    jr  nz, .notCGB
    inc a
.notCGB:
    ld  [wIsCGB], a
    xor a
    ldh [rVBK], a

    ; MBC5: make bank 1 the default mapped bank.
    ld  a, 1
    ld  [rROMB0], a
    xor a
    ld  [rROMB1], a

    ; The OAM DMA trigger has to run from HRAM, since the bus is otherwise
    ; blocked for the duration of the transfer.
    call InstallOamDma

    ; --- default video state ----------------------------------------------
    xor a
    ld  [rSCX], a
    ld  [rSCY], a
    ld  [wSCXShadow], a
    ld  [wSCYShadow], a
    ld  [rWY], a
    ld  [rWX], a
    ld  a, $E4
    ld  [wBGPShadow], a
    ld  [wPicBGP], a
    ld  a, $E4
    ld  [wOBP0Shadow], a
    ld  [wPicOBP], a
    ld  a, LCDCF_ON | LCDCF_BG8000 | LCDCF_BG9800 | LCDCF_BGON | LCDCF_OBJON | LCDCF_OBJ8
    ld  [wLCDCShadow], a

    ; Fonts, dialogue-box chrome and effect sprites are resident for the whole
    ; game -- only the picture tiles below TILE_FONT_BASE ever get swapped.
    call LoadFontTiles
    call LoadSpriteTiles
    call ClearBgMap

    ; Start fully faded out; every scene brings itself up.
    xor a
    ld  [wFadeLevel], a
    call ApplyFade

    ld  a, IEF_VBLANK
    ld  [rIE], a
    xor a
    ld  [rIF], a
    ei

    call LcdOn

    call GameMain
.hang:
    halt
    jr  .hang


; --------------------------------------------------------------- interrupts
VBlankHandler:
    push af
    push bc
    push de
    push hl

    ld  a, HIGH(wShadowOAM)
    call hOamDma

    ld  a, [wSCXShadow]
    ld  [rSCX], a
    ld  a, [wSCYShadow]
    ld  [rSCY], a
    ld  a, [wBGPShadow]
    ld  [rBGP], a
    ld  a, [wOBP0Shadow]
    ld  [rOBP0], a
    ld  a, [wOBP1Shadow]
    ld  [rOBP1], a

    ; Colour palettes are double-buffered: fades write the shadow, VBlank
    ; pushes it, so a fade never tears across a frame.
    ld  a, [wPalDirty]
    and a
    jr  z, .noPal
    call PushPalettes
    xor a
    ld  [wPalDirty], a
.noPal:

    ; Anything the scene queued for VRAM this frame (text glyphs, animated
    ; tiles) is flushed here, where writing is safe.
    call FlushVramQueue

    call ReadJoypad

    ld  hl, wFrameCounter
    inc [hl]
    ld  a, 1
    ld  [wVBlankDone], a

    pop hl
    pop de
    pop bc
    pop af
    reti


; The STAT handler drives the per-scanline water shimmer.  It runs on Mode 0
; (HBlank) so the SCX write lands between lines rather than mid-line.
StatHandler:
    push af
    push hl
    ld  a, [wWaterOn]
    and a
    jr  z, .done
    ld  a, [rLY]
    ld  hl, wWaterTable
    add l
    ld  l, a
    ld  a, h
    adc 0
    ld  h, a
    ld  a, [hl]
    ld  [rSCX], a
.done:
    pop hl
    pop af
    reti


; -------------------------------------------------------------------- frame
; WaitFrame -- park until the next VBlank has been serviced.
WaitFrame::
    xor a
    ld  [wVBlankDone], a
.wait:
    halt
    ld  a, [wVBlankDone]
    and a
    jr  z, .wait
    ret

; WaitFrames -- b frames, with weather and music still running.
;
; FxStep clobbers every register, so the countdown lives in WRAM.  Nothing
; reachable from FxStep waits, so a single counter is enough.
WaitFrames::
    ld  a, b
    and a
    ret z
    ld  [wWaitCount], a
.loop:
    call WaitFrame
    call FxStep
    ld  a, [wWaitCount]
    dec a
    ld  [wWaitCount], a
    jr  nz, .loop
    ret

SECTION "wait ram", WRAM0
wWaitCount:: db


INCLUDE "engine/util.asm"
INCLUDE "engine/video.asm"
INCLUDE "engine/fade.asm"
INCLUDE "engine/input.asm"
INCLUDE "engine/text.asm"
INCLUDE "engine/fx.asm"
INCLUDE "engine/explore.asm"
INCLUDE "engine/audio.asm"
INCLUDE "engine/vm.asm"
INCLUDE "engine/gfxdata.asm"
