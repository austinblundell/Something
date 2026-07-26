; =============================================================================
;  DREADHALL  --  a first person shooter for the original Game Boy
;
;  The 3D view is a 20 x 14 tile raycast viewport (160 x 112 px) sitting above
;  a 4 tile status bar. One ray per tile column. Wall columns are assembled out
;  of a static tile set (ceiling / top cap / body / bottom cap / floor), so a
;  whole frame is just 280 tilemap bytes -- cheap enough to double buffer
;  between the two background maps and flip with a single LCDC write, which
;  gives a rock steady tear-free 30 fps.
; =============================================================================

INCLUDE "hardware.inc"
INCLUDE "gen/consts.inc"

; ---- tuning ---------------------------------------------------------------
DEF PLAYER_R     EQU $50      ; collision radius (0.31 cells)
DEF MOVE_SPEED   EQU 30       ; 8.8 units per frame, scaled by |dir|
DEF STRAFE_SPEED EQU 22
DEF TURN_MAX     EQU 4        ; angle units / frame at full turn
DEF MAX_HP       EQU 128
DEF START_AMMO   EQU 50
DEF MAX_AMMO     EQU 99
DEF ENEMY_SPEED  EQU 11
DEF ENEMY_HP     EQU 3
DEF ENEMY_DMG    EQU 9
DEF GUN_DAMAGE   EQU 1

DEF MAX_ENEMIES  EQU 8
DEF ENEMY_OAM_BASE EQU 22   ; sprites 0..21 belong to the weapon
DEF MAX_PICKUPS  EQU 8

; enemy record
DEF E_XL EQU 0
DEF E_XH EQU 1
DEF E_YL EQU 2
DEF E_YH EQU 3
DEF E_HP EQU 4
DEF E_ST EQU 5
DEF E_TM EQU 6
DEF E_AN EQU 7
DEF E_SZ EQU 8

DEF EST_DEAD  EQU 0
DEF EST_IDLE  EQU 1
DEF EST_CHASE EQU 2
DEF EST_HURT  EQU 3
DEF EST_DYING EQU 4

; pickup record
DEF P_X EQU 0
DEF P_Y EQU 1
DEF P_K EQU 2
DEF P_A EQU 3
DEF P_SZ EQU 4

; game states
DEF ST_TITLE EQU 0
DEF ST_PLAY  EQU 1
DEF ST_DEAD  EQU 2
DEF ST_WIN   EQU 3

; =============================================================================
SECTION "Vectors", ROM0[$00]
    ds $40 - @, 0
SECTION "VBlankVec", ROM0[$40]
    jp VBlankISR
SECTION "OtherVecs", ROM0[$48]
    reti
    ds $50 - @, 0
    reti
    ds $58 - @, 0
    reti
    ds $60 - @, 0
    reti

SECTION "Header", ROM0[$100]
    nop
    jp Start
    ds $150 - @, 0            ; logo + metadata written by rgbfix

; =============================================================================
SECTION "Main", ROM0[$150]

Start:
    di
    ld sp, $DFFF
    ; map ROM bank 1 at $4000 and leave it there for good
    ld a, 1
    ld [$2000], a
    xor a
    ld [$3000], a
    call LcdOff

    ; ---- clear VRAM ----
    ld hl, $8000
    ld bc, $2000
    xor a
    call MemSet

    ; ---- clear WRAM working area + OAM shadow ----
    ld hl, $C000
    ld bc, $1000
    xor a
    call MemSet

    ; ---- tiles ----
    ; BG uses the $8800 addressing mode: indices 0..127 live at $9000 and
    ; 128..255 at $8800, which keeps sprites ($8000..$87FF) in their own space.
    ld hl, BgTiles
    ld de, $9000
    ld bc, 128 * 16
    call MemCopy
    ld hl, BgTiles + 128 * 16
    ld de, $8800
    ld bc, (BG_TILE_COUNT - 128) * 16
    call MemCopy
    ld hl, ObjTiles
    ld de, $8000
    ld bc, OBJ_TILE_COUNT * 16
    call MemCopy

    call CopyDmaRoutine

    ; ---- palettes ----
    ld a, %11100100
    ldh [rBGP], a
    ld a, %11100100
    ldh [rOBP0], a
    ld a, %11010000            ; sprite palette: unused index 1 -> white
    ldh [rOBP1], a

    xor a
    ldh [rSCY], a
    ldh [rSCX], a
    ldh [rNR52], a
    ld [wFrameReady], a
    ld [wUploadRow], a
    ld [wHudDirty], a

    call SoundInit

    ld a, IEF_VBLANK
    ldh [rIE], a
    xor a
    ldh [rIF], a

    call EnterTitle
    ei

; -----------------------------------------------------------------------------
MainLoop:
    call ReadJoypad

    ld a, [wGameState]
    cp ST_PLAY
    jr z, .play
    cp ST_TITLE
    jr z, .title
    jr .endscreen

.title:
    call WaitVBlank            ; update runs at the top of vblank so it can
    call TitleUpdate           ; touch VRAM directly
    jr MainLoop

.endscreen:
    call WaitVBlank
    call EndUpdate
    jr MainLoop

.play:
    call PlayerUpdate          ; may end the level by reaching the exit
    ld a, [wGameState]
    cp ST_PLAY
    jp nz, MainLoop
    call EnemiesUpdate         ; may kill the player
    ld a, [wGameState]
    cp ST_PLAY
    jp nz, MainLoop
    call PickupsUpdate

    call RenderView            ; raycast + build the tilemap back buffer
    call BuildOam              ; enemy/pickup billboards + hit-test data
    call WeaponUpdate          ; firing tests against what BuildOam just saw
    call BuildGunOam           ; weapon and crosshair drawn over everything

    ; Wait only for the *previous* upload to drain, then hand this buffer over
    ; and start the next one immediately. Render and upload overlap, so the
    ; frame period is max(render, upload) rather than their sum.
.waitPrev:
    ld a, [wFrameReady]
    and a
    jr z, .handoff
    halt
    jr .waitPrev
.handoff:
    di
    ld a, [wRenderPtr]
    ld [wUploadPtr], a
    ld a, [wRenderPtr + 1]
    ld [wUploadPtr + 1], a
    ld a, [wBufSel]
    xor 1
    ld [wBufSel], a
    call SetRenderPtr
    ld a, 1
    ld [wFrameReady], a
    ei
    jp MainLoop

; =============================================================================
; VBlank: OAM DMA on flip frames, then push one half of the tilemap back buffer.
; =============================================================================
VBlankISR:
    push af
    push bc
    push de
    push hl

    ld a, [wHudDirty]
    and a
    jr z, .view
    ; A HUD refresh replaces the view upload for one vblank; it happens only
    ; when a counter actually changes, so the hitch is invisible.
    xor a
    ld [wHudDirty], a
    call HudUpload
    jr .done

.view:
    ld a, [wFrameReady]
    and a
    jr z, .done

    call UploadChunk

    ld a, [wUploadRow]
    add 7
    ld [wUploadRow], a
    cp VIEW_ROWS
    jr c, .done

    ; whole frame is in the back map: show it, and start filling the other one
    xor a
    ld [wUploadRow], a
    ld [wFrameReady], a
    ld a, [wBackMap]
    ld b, a
    ld a, [wFrontMap]
    ld [wBackMap], a
    ld a, b
    ld [wFrontMap], a
    cp $98
    ld a, LCDCF_ON | LCDCF_BGON | LCDCF_OBJON | LCDCF_OBJ16
    jr z, .noBit
    or LCDCF_BG9C00
.noBit:
    ldh [rLCDC], a
    call RunDma               ; keep sprites in step with the map they belong to

.done:
    ld a, [wFrameCounter]
    inc a
    ld [wFrameCounter], a
    pop hl
    pop de
    pop bc
    pop af
    reti

; -----------------------------------------------------------------------------
; Push 7 rows (140 bytes) of wMapBuf into the back map.
; Stack-pointer reads plus `inc l` writes: 9 cycles per 2 bytes, ~660 total,
; which fits comfortably inside vblank alongside the DMA.
; -----------------------------------------------------------------------------
UploadChunk:
    ld a, [wUploadRow]
    ld l, a
    ld h, 0
    ; src = wMapBuf + row*20
    ld d, h
    ld e, l
    add hl, hl                ; *2
    add hl, hl                ; *4
    add hl, de                ; *5
    add hl, hl                ; *10
    add hl, hl                ; *20
    ld a, [wUploadPtr]
    ld e, a
    ld a, [wUploadPtr + 1]
    ld d, a
    add hl, de
    ld [wSrcSave], sp
    ld sp, hl

    ; dst = backmap + row*32
    ld a, [wUploadRow]
    ld l, a
    ld h, 0
    add hl, hl
    add hl, hl
    add hl, hl
    add hl, hl
    add hl, hl                ; *32
    ld a, [wBackMap]
    ld d, a
    ld e, 0
    add hl, de

    ld bc, 12                 ; 32 - 20: step to the next row
REPT 7
  REPT 10
    pop de
    ld [hl], e
    inc l
    ld [hl], d
    inc l
  ENDR
    add hl, bc
ENDR

    ld a, [wSrcSave]
    ld l, a
    ld a, [wSrcSave + 1]
    ld h, a
    ld sp, hl
    ret

; =============================================================================
; helpers
; =============================================================================

LcdOff:
    ldh a, [rLCDC]
    and LCDCF_ON
    ret z
.wait:
    ldh a, [rLY]
    cp 144
    jr c, .wait
    xor a
    ldh [rLCDC], a
    ret

; Turn the LCD on with the current front map selected.
LcdOn:
    ld a, [wFrontMap]
    cp $98
    ld a, LCDCF_ON | LCDCF_BGON | LCDCF_OBJON | LCDCF_OBJ16
    jr z, .go
    or LCDCF_BG9C00
.go:
    ldh [rLCDC], a
    ret

WaitVBlank:
    halt
    ret

; hl = dest, bc = count, a = value
MemSet:
    ld d, a
.loop:
    ld a, d
    ld [hl+], a
    dec bc
    ld a, b
    or c
    jr nz, .loop
    ret

; hl = src, de = dest, bc = count
MemCopy:
    ld a, [hl+]
    ld [de], a
    inc de
    dec bc
    ld a, b
    or c
    jr nz, MemCopy
    ret

; -----------------------------------------------------------------------------
ReadJoypad:
    ld a, $20                 ; d-pad
    ldh [rP1], a
    ldh a, [rP1]
    ldh a, [rP1]
    cpl
    and $0F
    swap a
    ld b, a
    ld a, $10                 ; buttons
    ldh [rP1], a
    ldh a, [rP1]
    ldh a, [rP1]
    ldh a, [rP1]
    ldh a, [rP1]
    cpl
    and $0F
    or b
    ld b, a
    ld a, [wPad]
    cpl
    and b
    ld [wPadNew], a
    ld a, b
    ld [wPad], a
    ld a, $30
    ldh [rP1], a
    ret

; -----------------------------------------------------------------------------
; OAM DMA has to run from HRAM: everything except HRAM is inaccessible while it
; is in flight.
CopyDmaRoutine:
    ld hl, DmaSrc
    ld de, RunDma
    ld bc, DmaEnd - DmaSrc
    call MemCopy
    ret

DmaSrc:
    ld a, HIGH(wShadowOam)
    ldh [rDMA], a
    ld a, 40
.wait:
    dec a
    jr nz, .wait
    ret
DmaEnd:

; =============================================================================
; multiply helpers
; =============================================================================

; MulFrac: HL = (A * BC) >> 8   with A read as an 8-bit fraction (A/256).
; Accumulates into the 24-bit register triple E:HL, then keeps the top 16 bits.
; Clobbers A, D, E.
MulFrac::
    ld d, a
    ld hl, 0
    ld e, 0
REPT 8
    add hl, hl
    rl e
    sla d
    jr nc, .skip\@
    add hl, bc
    jr nc, .skip\@
    inc e
.skip\@:
ENDR
    ld l, h
    ld h, e
    ret

; MulSigned: HL = (BC * DE) >> 8, both signed, |DE| must be <= 255.
; Clobbers A, BC, DE.
MulSigned::
    xor a
    ld [wMulSign], a
    bit 7, b
    jr z, .bpos
    ; BC = -BC
    xor a
    sub c
    ld c, a
    sbc a, a
    sub b
    ld b, a
    ld a, 1
    ld [wMulSign], a
.bpos:
    bit 7, d
    jr z, .dpos
    xor a
    sub e
    ld e, a
    ld a, [wMulSign]
    xor 1
    ld [wMulSign], a
.dpos:
    ld a, e
    call MulFrac
    ld a, [wMulSign]
    and a
    ret z
    ; HL = -HL
    xor a
    sub l
    ld l, a
    sbc a, a
    sub h
    ld h, a
    ret

; SinLookup: A = angle -> BC = sin (s8.8, magnitude <= 255)
SinLookup::
    ld l, a
    ld h, 0
    add hl, hl
    ld de, SinTab
    add hl, de
    ld a, [hl+]
    ld c, a
    ld b, [hl]
    ret

; CosLookup: A = angle -> BC = cos
CosLookup::
    add 64
    ld l, a
    ld h, 0
    add hl, hl
    ld de, SinTab
    add hl, de
    ld a, [hl+]
    ld c, a
    ld b, [hl]
    ret

; =============================================================================
; state entry
; =============================================================================

EnterTitle:
    call LcdOff
    ld a, ST_TITLE
    ld [wGameState], a
    xor a
    ld [wFrameReady], a
    ld [wUploadRow], a
    ld [wHudDirty], a
    ld a, $98
    ld [wFrontMap], a
    ld a, $9C
    ld [wBackMap], a
    call ClearOam
    call RunDmaSafe
    call DrawTitle
    call LcdOn
    ret

EnterPlay:
    call LcdOff
    ld a, ST_PLAY
    ld [wGameState], a
    ld a, $98
    ld [wFrontMap], a
    ld a, $9C
    ld [wBackMap], a
    xor a
    ld [wUploadRow], a
    ld [wFrameReady], a
    ld [wHudDirty], a
    ld [wBufSel], a
    call SetRenderPtr

    call InitLevel
    call ClearBothMaps
    call HudBuild
    call HudUpload            ; safe: LCD is off
    call ClearOam
    call RunDmaSafe
    call LcdOn
    ret

; a = ST_DEAD or ST_WIN
EnterEnd:
    ld [wGameState], a
    call LcdOff
    xor a
    ld [wFrameReady], a
    ld [wUploadRow], a
    ld [wHudDirty], a
    ld a, $98
    ld [wFrontMap], a
    ld a, $9C
    ld [wBackMap], a
    call ClearOam
    call RunDmaSafe
    call DrawEndScreen
    ld a, 90
    ld [wEndTimer], a
    call LcdOn
    ret

; wRenderPtr = whichever map buffer this frame should be drawn into
SetRenderPtr::
    ld a, [wBufSel]
    and a
    ld hl, wMapBufA
    jr z, :+
    ld hl, wMapBufB
:   ld a, l
    ld [wRenderPtr], a
    ld a, h
    ld [wRenderPtr + 1], a
    ret

RunDmaSafe:
    call RunDma
    ret

ClearOam:
    ld hl, wShadowOam
    ld bc, 160
    xor a
    call MemSet
    ret

ClearBothMaps:
    ld hl, $9800
    ld bc, $800
    ld a, T_HUD_PANEL
    call MemSet
    ret

; =============================================================================
INCLUDE "render.asm"
INCLUDE "player.asm"
INCLUDE "entity.asm"
INCLUDE "hud.asm"
INCLUDE "screens.asm"
INCLUDE "sound.asm"

; =============================================================================
SECTION "Tables", ROM0, ALIGN[8]
INCLUDE "gen/tables.inc"

; both of these are addressed as HIGH(base)+k : index, so they must each be
; page aligned
SECTION "ShadeTable", ROM0, ALIGN[8]
INCLUDE "gen/shade.inc"

SECTION "HeightTables", ROM0, ALIGN[8]
INCLUDE "gen/height.inc"

SECTION "LevelData", ROMX, BANK[1], ALIGN[10]
INCLUDE "gen/map.inc"

; Tile and level data live in bank 1. The bank register is set once at boot and
; never touched again, so $4000-$7FFF is permanently mapped and the raycaster
; can read the level map straight out of it.
SECTION "Tiles", ROMX, BANK[1]
INCLUDE "gen/tiles.inc"

; =============================================================================
SECTION "ShadowOam", WRAM0[$C000]
wShadowOam:: ds 160

SECTION "MapBuffer", WRAM0
; Two tilemap buffers: the renderer fills one while vblank drains the other,
; so a slow frame never costs a wasted upload slot.
wMapBufA::     ds VIEW_COLS * VIEW_ROWS
wMapBufB::     ds VIEW_COLS * VIEW_ROWS

SECTION "Vars", WRAM0
wGameState::   db
wFrameCounter::db
wPad::         db
wPadNew::      db
wFrontMap::    db
wBackMap::     db
wUploadRow::   db
wFrameReady::  db
wHudDirty::    db
wSrcSave::     dw
wMulSign::     db
wBufSel::      db
wRenderPtr::   dw
wUploadPtr::   dw
wEndTimer::    db

wPlayerX::     dw
wPlayerY::     dw
wPlayerAng::   db
wPlayerHp::    db
wAmmo::        db
wKills::       db
wTurnVel::     db
wBobPhase::    db
wHurtFlash::   db

wGunState::    db            ; 0 idle, else countdown of the fire animation
wGunRecoil::   db

wColH2::       ds VIEW_COLS
wColMat::      ds VIEW_COLS
wColDist::     ds VIEW_COLS * 2

wEnemies::     ds MAX_ENEMIES * E_SZ
wEnemyCount::  db
wEnemiesLeft:: db
wPickups::     ds MAX_PICKUPS * P_SZ
wPickupCount:: db

wOamPtr::      db
wHudBuf::      ds 20 * 4

SECTION "HramVars", HRAM
RunDma::       ds 16

hSdXl::  db
hSdXh::  db
hSdYl::  db
hSdYh::  db
hDdXl::  db
hDdXh::  db
hDdYl::  db
hDdYh::  db
hStepX:: db
hStepYl::db
hStepYh::db
hCount:: db
hCol::   db
hRayAng::db
hMatBase::db
hTmp::   db
hTmp2::  db
