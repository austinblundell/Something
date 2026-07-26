; =============================================================================
; GB HORIZON -- a pseudo-3D racer for the Game Boy
;
; The road is a single straight perspective image baked into the background
; map.  Every scanline of the road band gets its own SCX (bends the road into
; curves) and its own BGP (palette banding scrolls the asphalt toward the
; camera).  No tile data is rewritten while racing, which leaves the whole
; frame budget for physics, eleven opponents and the HUD.
; =============================================================================

INCLUDE "src/hardware.inc"
INCLUDE "src/gen/consts.inc"

DEF CH_HASH        EQU 35 - 32   ; glyph offsets into FontMap
DEF CH_STAR        EQU 42 - 32
DEF CH_ZERO        EQU 48 - 32
DEF CH_LT          EQU 60 - 32
DEF CH_GT          EQU 62 - 32

DEF PLAYER_X_LIM   EQU 64        ; steering clamp, keeps SCX out of wrap range
DEF OFFROAD_X      EQU 50        ; |playerX| past this and the tyres are on grass
DEF NUM_ENEMIES    EQU 11
DEF EN_SIZE        EQU 4
DEF EN_RZL         EQU 0
DEF EN_RZH         EQU 1
DEF EN_LAT         EQU 2
DEF EN_SPD         EQU 3

DEF Z_NEAR         EQU 3048      ; depth of the bottom scanline
DEF Z_FAR          EQU 14628     ; depth of the horizon
DEF Z_RECYCLE_HI   EQU 20000
DEF Z_RECYCLE_LO   EQU 800
DEF Z_WRAP         EQU 18000

DEF PLAYER_OAM_Y   EQU 141
DEF LOOKAHEAD_HI   EQU 8         ; trackPos high-byte units == one segment

DEF SIZE_BIG_Y     EQU 112       ; scanline thresholds for opponent sprite size
DEF SIZE_MED_Y     EQU 84

; -----------------------------------------------------------------------------
SECTION "Header", ROM0[$0100]
    nop
    jp Start
    ds $150 - @, 0

; -----------------------------------------------------------------------------
SECTION "Main", ROM0

Start:
    di
    ld sp, $DFFF

    call LcdOff
    call ClearOam
    call LoadTiles
    call InstallDma

    ld a, %11100100
    ldh [rOBP0], a
    xor a
    ldh [rSCY], a
    ld [wCarSel], a
    ld [wKeys], a

    jp TitleInit

; =============================================================================
; Car select
; =============================================================================
TitleInit:
    call LcdOff
    call ClearOam

    ; blank background, sky palette
    ld hl, _SCRN0
    ld de, 32 * 32
    ld a, TILE_BLANK
    call FillBytes

    ld a, PAL_SKY
    ldh [rBGP], a
    xor a
    ldh [rSCX], a

    ld hl, StrTitle
    ld de, _SCRN0 + 1 * 32 + 5
    call PrintString
    ld hl, StrPressA
    ld de, _SCRN0 + 15 * 32 + 3
    call PrintString

    call DrawCarPanel

    ld a, LCDCF_ON | LCDCF_BG8800 | LCDCF_BG9800 | LCDCF_BGON
    ldh [rLCDC], a

TitleLoop:
    call WaitVBlank
    ld a, [wDirty]
    or a
    call nz, DrawCarPanel
    call ReadInput

    ld a, [wKeysNew]
    bit 0, a                       ; A -> race
    jp nz, RaceInit
    bit 3, a                       ; START -> race
    jp nz, RaceInit

    ld a, [wKeysNew]
    bit 5, a                       ; LEFT
    jr z, .noleft
    ld a, [wCarSel]
    or a
    jr z, .noleft
    dec a
    ld [wCarSel], a
    ld a, 1
    ld [wDirty], a
.noleft
    ld a, [wKeysNew]
    bit 4, a                       ; RIGHT
    jr z, .noright
    ld a, [wCarSel]
    cp 2
    jr z, .noright
    inc a
    ld [wCarSel], a
    ld a, 1
    ld [wDirty], a
.noright
    jr TitleLoop

; Redraw everything that depends on the current selection.  Small enough to
; land inside one vertical blank.
DrawCarPanel:
    xor a
    ld [wDirty], a

    ; selection arrows
    ld a, [wCarSel]
    ld b, a
    ld a, TILE_BLANK
    ld [_SCRN0 + 3 * 32 + 1], a
    ld [_SCRN0 + 3 * 32 + 18], a
    ld a, b
    or a
    jr z, .noleftarrow
    ld a, [FontMap + CH_LT]
    ld [_SCRN0 + 3 * 32 + 1], a
.noleftarrow
    ld a, b
    cp 2
    jr z, .norightarrow
    ld a, [FontMap + CH_GT]
    ld [_SCRN0 + 3 * 32 + 18], a
.norightarrow

    ; name
    ld a, [wCarSel]
    ld hl, CarNames
    call IndexWord
    ld de, _SCRN0 + 3 * 32 + 5
    call PrintString

    ; picture: SHOW_W x SHOW_H tiles from the showcase bank (tiles 128+)
    ld a, [wCarSel]
    ld hl, ShowMapPtrs
    call IndexWord
    ld de, _SCRN0 + 5 * 32 + 6
    ld c, SHOW_H
.row
    ld b, SHOW_W
.col
    ld a, [hl+]
    add 128                        ; showcase tiles live at $8800
    ld [de], a
    inc de
    dec b
    jr nz, .col
    ld a, e
    add 32 - SHOW_W
    ld e, a
    jr nc, .nocarry
    inc d
.nocarry
    dec c
    jr nz, .row

    ; three stat bars
    ld a, [wCarSel]
    add a
    add a                          ; * 4 bytes per stat record
    ld c, a
    ld b, 0
    ld hl, CarStatBars
    add hl, bc
    push hl

    ld hl, StrSpd
    ld de, _SCRN0 + 11 * 32 + 4
    call PrintString
    ld hl, StrAcc
    ld de, _SCRN0 + 12 * 32 + 4
    call PrintString
    ld hl, StrGrp
    ld de, _SCRN0 + 13 * 32 + 4
    call PrintString

    pop hl
    ld de, _SCRN0 + 11 * 32 + 8
    ld c, 3
.bars
    ld a, [hl+]
    push bc
    push hl
    push de
    call DrawBar
    pop de
    pop hl
    pop bc
    ld a, e
    add 32
    ld e, a
    jr nc, .nc2
    inc d
.nc2
    dec c
    jr nz, .bars
    ret

; a = filled count (0..8), de = destination
DrawBar:
    ld b, a
    ld c, 8
.loop
    ld a, b
    or a
    jr z, .empty
    dec b
    ld a, [FontMap + CH_HASH]
    jr .put
.empty
    ld a, [FontMap + CH_STAR]
.put
    ld [de], a
    inc de
    dec c
    jr nz, .loop
    ret

; a = index, hl = table of words -> hl = entry
IndexWord:
    add a
    ld c, a
    ld b, 0
    add hl, bc
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    ret

; =============================================================================
; Race
; =============================================================================
RaceInit:
    call LcdOff
    call ClearOam

    ; sky band
    ld hl, _SCRN0
    ld de, ROW_FIRST * 32
    ld a, TILE_SKY
    call FillBytes
    ; road band
    ld hl, RoadMap
    ld de, _SCRN0 + ROW_FIRST * 32
    ld bc, ROAD_ROWS * 32
    call CopyBytes
    ; off-screen rows
    ld hl, _SCRN0 + 18 * 32
    ld de, 14 * 32
    ld a, TILE_SKY
    call FillBytes

    ld hl, StrSpdHud
    ld de, _SCRN0 + 1 * 32 + 1
    call PrintString

    call InitRace

    xor a
    ldh [rSCX], a
    ld a, PAL_SKY
    ldh [rBGP], a

    ld a, LCDCF_ON | LCDCF_BG8800 | LCDCF_BG9800 | LCDCF_BGON | LCDCF_OBJ16 | LCDCF_OBJON
    ldh [rLCDC], a

MainLoop:
    call WaitVBlank

    ; --- vertical blank ------------------------------------------------------
    xor a
    ldh [rSCX], a
    ld a, PAL_SKY
    ldh [rBGP], a
    call hDma                      ; last frame's sprites
    call UpdateHud                 ; touches VRAM, must stay in blanking

    ; --- rest of the frame is WRAM only --------------------------------------
    call ReadInput
    call UpdateDrive
    call BuildScxTable
    call BuildBgpTable
    call BuildOam

    ldh a, [rLY]
    ldh [hDebugLy], a              ; how close we ran to the deadline

    call RoadRaster
    jr MainLoop

InitRace:
    xor a
    ldh [hCamZLo], a
    ldh [hCamZHi], a
    ld [wTrackPos], a
    ld [wTrackPos + 1], a
    ld [wCurve], a
    ld [wCurveTarget], a
    ld [wPlayerX], a
    ld [wSpeed], a
    ld [wDriftAcc], a
    ld a, $FF
    ld [wLastSpeedDisp], a
    ld [wLastArrow], a
    ld a, $A5
    ld [wRandom], a

    ; per-car handling
    ld a, [wCarSel]
    add a
    add a
    ld c, a
    ld b, 0
    ld hl, CarStats
    add hl, bc
    ld a, [hl+]
    ld [wMaxSpeed], a
    ld a, [hl+]
    ld [wAccel], a
    ld a, [hl]
    ld [wSteer], a

    ; the distant stretch of road never bands
    ld hl, BgpTable
    ld b, BAND_START
    ld a, PAL_FAR
.far
    ld [hl+], a
    dec b
    jr nz, .far

    ; opponents, spread down the road
    ld hl, wEnemies
    ld de, EnemySeed
    ld c, NUM_ENEMIES
.spawn
    ld a, [de]                     ; rz high byte
    inc de
    ld b, a
    ld a, [de]                     ; lateral
    inc de
    push af
    ld a, b
    add a                          ; rz = seed * 512 + 2600
    ld [hl], 0
    inc hl
    ld [hl], a
    inc hl
    pop af
    ld [hl+], a
    ld a, [de]                     ; speed
    inc de
    ld [hl+], a
    dec c
    jr nz, .spawn
    ret

; -----------------------------------------------------------------------------
; Player physics and track curvature.
UpdateDrive:
    ; --- throttle / brake ----------------------------------------------------
    ld a, [wKeys]
    bit 1, a                       ; B brakes
    jr z, .nobrake
    ld a, [wSpeed]
    sub 3
    jr nc, .setspeed
    xor a
    jr .setspeed
.nobrake
    ld a, [wSpeed]
    ld b, a
    ld a, [wMaxSpeed]
    cp b
    jr z, .speeddone
    jr c, .decel
    ld a, [wAccel]
    add b
    jr .setspeed
.decel
    ld a, b
    dec a
.setspeed
    ld [wSpeed], a
.speeddone

    ; --- steering ------------------------------------------------------------
    ld a, [wKeys]
    ld b, a
    ld a, [wPlayerX]
    ld c, a
    bit 5, b                       ; LEFT
    jr z, .noleft
    ld a, [wSteer]
    ld d, a
    ld a, c
    sub d
    ld c, a
.noleft
    bit 4, b                       ; RIGHT
    jr z, .noright
    ld a, [wSteer]
    ld d, a
    ld a, c
    add d
    ld c, a
.noright

    ; --- the turn pushes you to the outside ----------------------------------
    ; Accumulated sub-pixel, so a gentle bend still nudges you a little rather
    ; than nothing at all.
    ld a, [wCurve]
    sra a
    sra a                          ; curve / 4, sign preserved
    ld b, a
    ld a, [wDriftAcc]
    add b
    ld [wDriftAcc], a
    bit 7, a
    jr nz, .driftneg
    cp 16
    jr c, .driftdone
    sub 16
    ld [wDriftAcc], a
    dec c                          ; right-hand bend pushes you left
    jr .driftdone
.driftneg
    cp 241                         ; > -15: not a whole pixel yet
    jr nc, .driftdone
    add 16
    ld [wDriftAcc], a
    inc c
.driftdone

    ; clamp to +/- PLAYER_X_LIM
    ld a, c
    bit 7, a
    jr nz, .negclamp
    cp PLAYER_X_LIM + 1
    jr c, .xdone
    ld a, PLAYER_X_LIM
    jr .xdone
.negclamp
    cp 256 - PLAYER_X_LIM
    jr nc, .xdone
    ld a, 256 - PLAYER_X_LIM
.xdone
    ld [wPlayerX], a

    ; --- grass costs you speed ----------------------------------------------
    call AbsA
    cp OFFROAD_X + 1
    jr c, .onroad
    ld a, [wSpeed]
    sub 4
    jr nc, .offset
    xor a
.offset
    ld [wSpeed], a
.onroad

    ; --- advance the world ---------------------------------------------------
    ld a, [wSpeed]
    ld c, a
    ldh a, [hCamZLo]
    add c
    ldh [hCamZLo], a
    ldh a, [hCamZHi]
    adc 0
    ldh [hCamZHi], a

    ld a, [wSpeed]
    srl a
    srl a
    ld c, a
    ld a, [wTrackPos]
    add c
    ld [wTrackPos], a
    ld a, [wTrackPos + 1]
    adc 0
    ld [wTrackPos + 1], a

    ; --- curvature for the segment under the car -----------------------------
    ld a, [wTrackPos + 1]
    call SegCurve
    ld [wCurveTarget], a

    ; ease wCurve toward the target (signed compare)
    ld a, [wCurve]
    ld b, a
    add $80
    ld c, a
    ld a, [wCurveTarget]
    add $80
    cp c
    ret z
    jr c, .down
    inc b
    jr .store
.down
    dec b
.store
    ld a, b
    ld [wCurve], a
    ret

; a = trackPos high byte -> a = curvature of that segment
SegCurve:
    srl a
    srl a
    srl a
    and 31
    ld c, a
    ld b, 0
    ld hl, TrackData
    add hl, bc
    ld a, [hl]
    ret

; a -> |a|
AbsA:
    bit 7, a
    ret z
    cpl
    inc a
    ret

; -----------------------------------------------------------------------------
; Move the opponents and recycle any that leave the visible stretch.
Rand:
    ld a, [wRandom]
    sla a
    jr nc, .skip
    xor $1D
.skip
    ld [wRandom], a
    ret

; -----------------------------------------------------------------------------
; Build the sprite list: player first, then every visible opponent.
; Builds the sprite list AND runs opponent physics in the same walk.
BuildOam:
    ld hl, ShadowOam

    ; --- player, four 8x16 columns centred on screen x = 80 ------------------
    ld a, PLAYER_OAM_Y
    ld [hl+], a
    ld a, 72
    ld [hl+], a
    ld a, SPR_PLAYER0
    ld [hl+], a
    xor a
    ld [hl+], a

    ld a, PLAYER_OAM_Y
    ld [hl+], a
    ld a, 80
    ld [hl+], a
    ld a, SPR_PLAYER1
    ld [hl+], a
    xor a
    ld [hl+], a

    ld a, PLAYER_OAM_Y
    ld [hl+], a
    ld a, 88
    ld [hl+], a
    ld a, SPR_PLAYER2
    ld [hl+], a
    xor a
    ld [hl+], a

    ld a, PLAYER_OAM_Y
    ld [hl+], a
    ld a, 96
    ld [hl+], a
    ld a, SPR_PLAYER3
    ld [hl+], a
    xor a
    ld [hl+], a

    ld a, l
    ld [wOamPtr], a

    ; --- opponents: advance and draw in one pass ----------------------------
    ld de, wEnemies
    ld a, NUM_ENEMIES
    ld [wEnIdx], a
.enemy
    ld a, [de]
    ld l, a
    inc de
    ld a, [de]
    ld h, a                        ; hl = rz, de -> rz high byte
    inc de
    ld a, [de]
    ld [wEnLatCur], a              ; lane
    inc de
    ld a, [de]                     ; opponent speed
    ld [wEnSpdCur], a

    ; rz += opponentSpeed - playerSpeed
    ld c, a
    ld a, [wSpeed]
    ld b, a
    ld a, c
    sub b
    ld c, a
    ld b, 0
    bit 7, a
    jr z, .poshi
    dec b
.poshi
    add hl, bc

    ; too far ahead -> pull it back behind the camera
    ld a, h
    cp HIGH(Z_RECYCLE_HI)
    jr c, .checklow
    ld bc, -Z_WRAP
    add hl, bc
    jr .relane
.checklow
    ; overtaken -> send it back up the road
    cp HIGH(Z_RECYCLE_LO)
    jr nc, .touching
    ld bc, Z_WRAP
    add hl, bc
.relane
    call Rand
    and 15                         ; drop it into one of the 16 lanes
    ld [wEnLatCur], a
    jr .writeback

    ; close enough to touch?  you cannot out-accelerate a car you are on top of
.touching
    cp 10                          ; rz >= 2560
    jr c, .writeback
    cp 17                          ; rz <  4352
    jr nc, .writeback
    ld a, [wEnLatCur]              ; lane -> road units
    add a
    add a
    add a
    sub 60
    ld b, a
    ld a, [wPlayerX]
    sub b
    call AbsA
    cp 13
    jr nc, .writeback
    ld a, [wEnSpdCur]
    ld b, a
    ld a, [wSpeed]
    cp b
    jr c, .writeback
    ld a, b
    ld [wSpeed], a

.writeback
    ; de still points at the speed byte; rewind and store rz + lane
    dec de
    dec de
    dec de
    ld a, l
    ld [de], a
    inc de
    ld a, h
    ld [de], a
    inc de
    ld a, [wEnLatCur]
    ld [de], a
    inc de
    inc de                         ; -> next record

    ; visible?  Z_NEAR <= rz <= Z_FAR
    ld a, h
    cp HIGH(Z_NEAR)
    jp c, .next
    cp HIGH(Z_FAR) + 1
    jp nc, .next

    ; scanline = YFromRz[rz >> 7]
    add hl, hl                     ; high byte is now rz >> 7
    ld a, h
    and 127
    ld c, a
    ld b, 0
    ld hl, YFromRz
    add hl, bc
    ld a, [hl]
    or a
    jr z, .next                    ; beyond the horizon
    cp 255
    jr z, .next                    ; nearer than the bottom scanline
    cp ROAD_TOP + 14
    jr c, .next                    ; too near the vanishing point to read
    ld [wScanline], a
    sub ROAD_TOP
    ld [wLineIdx], a

    ; road centre at that scanline = 128 - SCX(line)
    ld l, a
    ld h, 0
    ld bc, ScxTable
    add hl, bc
    ld a, [hl]
    ld b, a
    ld a, 128
    sub b
    ld [wScrCentre], a

    ; lateral pixels come straight out of LaneTable[line][lane]
    ld a, [wLineIdx]
    ld l, a
    ld h, 0
    add hl, hl
    add hl, hl
    add hl, hl
    add hl, hl                     ; line * 16
    ld a, [wEnLatCur]              ; lane 0..15
    ld c, a
    ld b, 0
    add hl, bc
    ld bc, LaneTable
    add hl, bc
    ld a, [hl]                     ; signed offset from the road centre
    ld b, a
    ld a, [wScrCentre]
    add b
    ld [wScrX], a

    ; sprite size follows distance
    ld a, [wScanline]
    cp SIZE_BIG_Y
    jr nc, .big
    cp SIZE_MED_Y
    jr nc, .med
    ld b, SPR_FAR
    jr .onecol
.med
    ld b, SPR_MED
.onecol
    ld a, [wScrX]
    add 4                          ; 8 wide, centred
    ld c, a
    call EmitSprite
    jr .next
.big
    ld a, [wScrX]
    ld c, a                        ; 16 wide, centred
    ld b, SPR_BIG0
    call EmitSprite
    ld a, [wScrX]
    add 8
    ld c, a
    ld b, SPR_BIG1
    call EmitSprite
.next
    ld hl, wEnIdx
    dec [hl]
    jp nz, .enemy

    ; hide whatever is left over -- Y = 0 is enough, no need to wipe all four
    ld a, [wOamPtr]
    ld l, a
    ld h, HIGH(ShadowOam)
    xor a
.clear
    ld [hl], a
    inc l
    inc l
    inc l
    inc l
    ld b, a
    ld a, l
    cp 160
    ld a, b
    jr c, .clear
    ret

; b = tile, c = OAM x, wScanline = road scanline the wheels sit on
EmitSprite:
    ld a, c
    or a
    ret z                          ; x = 0 is hidden anyway
    cp 168
    ret nc
    ld a, [wOamPtr]
    ld l, a
    ld h, HIGH(ShadowOam)
    ld a, [wScanline]
    inc a                          ; graphics are bottom-aligned in 8x16
    ld [hl+], a
    ld a, c
    ld [hl+], a
    ld a, b
    ld [hl+], a
    xor a
    ld [hl+], a
    ld a, l
    ld [wOamPtr], a
    ret


; -----------------------------------------------------------------------------
; HUD: speed readout and the upcoming-turn arrow.  VRAM writes only.
UpdateHud:
    ; --- speed ---------------------------------------------------------------
    ld a, [wSpeed]
    add a                          ; display as km/h-ish
    ld b, a
    ld a, [wLastSpeedDisp]
    cp b
    jr z, .arrow
    ld a, b
    ld [wLastSpeedDisp], a
    call DrawSpeed
.arrow
    ; --- upcoming turn -------------------------------------------------------
    ld a, [wTrackPos + 1]
    add LOOKAHEAD_HI
    call SegCurve
    ld b, 0                        ; 0 = none
    bit 7, a
    jr nz, .negcurve
    cp 32
    jr c, .haveArrow
    ld b, 2                        ; right
    jr .haveArrow
.negcurve
    call AbsA
    cp 32
    jr c, .haveArrow
    ld b, 1                        ; left
.haveArrow
    ld a, [wLastArrow]
    cp b
    ret z
    ld a, b
    ld [wLastArrow], a
    jp DrawArrow

; a = value 0..255, print three digits at row 1 col 5
DrawSpeed:
    ld hl, _SCRN0 + 1 * 32 + 5
    ld b, 0
.hundreds
    cp 100
    jr c, .tens
    sub 100
    inc b
    jr .hundreds
.tens
    push af
    ld a, b
    call PutDigit
    pop af
    ld b, 0
.tensloop
    cp 10
    jr c, .units
    sub 10
    inc b
    jr .tensloop
.units
    push af
    ld a, b
    call PutDigit
    pop af
PutDigit:
    push bc
    ld c, a
    ld b, 0
    push hl
    ld hl, FontMap + CH_ZERO
    add hl, bc
    ld a, [hl]
    pop hl
    ld [hl+], a
    pop bc
    ret

; b = 0 none / 1 left / 2 right
DrawArrow:
    ld a, b
    or a
    jr nz, .draw
    ld a, TILE_SKY                 ; blend back into the sky band
    ld [_SCRN0 + 2 * 32 + 9], a
    ld [_SCRN0 + 2 * 32 + 10], a
    ld [_SCRN0 + 3 * 32 + 9], a
    ld [_SCRN0 + 3 * 32 + 10], a
    ret
.draw
    dec a
    add a
    add a
    ld c, a
    ld b, 0
    ld hl, ArrowMaps
    add hl, bc
    ld a, [hl+]
    ld [_SCRN0 + 2 * 32 + 9], a
    ld a, [hl+]
    ld [_SCRN0 + 2 * 32 + 10], a
    ld a, [hl+]
    ld [_SCRN0 + 3 * 32 + 9], a
    ld a, [hl]
    ld [_SCRN0 + 3 * 32 + 10], a
    ret

; -----------------------------------------------------------------------------
; Per-scanline road driver.  Parks the CPU from line 47 to the bottom.
RoadRaster:
    ld hl, ScxTable
    ld de, BgpTable
    ld b, ROAD_LINES
.waitLine
    ldh a, [rLY]
    cp ROAD_TOP - 1
    jr nz, .waitLine
.wait0
    ldh a, [rSTAT]
    and 3
    jr nz, .wait0
.write
    ld a, [hl+]
    ldh [rSCX], a
    ld a, [de]
    ldh [rBGP], a
    inc de
    dec b
    ret z
.wait3
    ldh a, [rSTAT]
    and 3
    cp 3
    jr nz, .wait3
.wait0b
    ldh a, [rSTAT]
    and 3
    jr nz, .wait0b
    jr .write

; -----------------------------------------------------------------------------
; Fill ScxTable.
;
; The road's horizontal offset at each scanline is curve * shape(y), with
; shape() rising quadratically from 0 at the bottom to 128 at the horizon.
; Rather than multiply per line, walk bottom-to-top and add the curve into a
; 16-bit accumulator once per unit of shape() -- 128 adds, emitted unrolled.
MACRO STORE_SCX
    ldh a, [hRoadBase]
    sub h
    ld [de], a
    dec de
ENDM

BuildScxTable:
    ld a, [wPlayerX]
    add SCX_BASE
    ldh [hRoadBase], a

    ld a, [wCurve]
    ld c, a
    ld b, 0
    bit 7, a
    jr z, .positive
    dec b
.positive
    ld hl, 0
    ld de, ScxTable + ROAD_LINES - 1
INCLUDE "src/gen/scxbuild.inc"
    ret

; -----------------------------------------------------------------------------
; Fill BgpTable.  A band is 256 world units, so the band a
; scanline belongs to is bit 0 of the high byte of (camZ + z(y)).
BuildBgpTable:
    ld hl, BgpTable + BAND_START
    ld de, ZTable + BAND_START * 2
    ldh a, [hCamZLo]
    ld b, a
    ldh a, [hCamZHi]
    ld c, a
.loop
    ld a, [de]
    inc de
    add b
    ld a, [de]
    inc de
    adc c
    rra                            ; band = bit 0 of the high byte
    ld a, PAL_A
    jr nc, .store
    ld a, PAL_B
.store
    ld [hl+], a                    ; this scanline
    ld [hl+], a                    ; and its partner
    inc de                         ; bands never resolve below two scanlines,
    inc de                         ; so one lookup covers both
    ld a, l
    cp LOW(BgpTable) + ROAD_LINES
    jr c, .loop
    ret

; =============================================================================
; Utilities
; =============================================================================
WaitVBlank:
.wait
    ldh a, [rLY]
    cp 144
    jr nz, .wait
    ret

LcdOff:
    ldh a, [rLCDC]
    and LCDCF_ON
    ret z
.wait
    ldh a, [rLY]
    cp 145
    jr nz, .wait
    xor a
    ldh [rLCDC], a
    ret

ReadInput:
    ld a, P1F_GET_DPAD
    ldh [rJOYP], a
    ldh a, [rJOYP]
    ldh a, [rJOYP]
    cpl
    and $0F
    swap a
    ld b, a
    ld a, P1F_GET_BTN
    ldh [rJOYP], a
    ldh a, [rJOYP]
    ldh a, [rJOYP]
    ldh a, [rJOYP]
    ldh a, [rJOYP]
    cpl
    and $0F
    or b
    ld b, a
    ld a, P1F_GET_NONE
    ldh [rJOYP], a
    ld a, [wKeys]
    xor b
    and b
    ld [wKeysNew], a
    ld a, b
    ld [wKeys], a
    ret

ClearOam:
    ld hl, ShadowOam
    ld de, 160
    xor a
    call FillBytes
    ld hl, _OAMRAM
    ld de, 160
    xor a
    jp FillBytes

; hl = dest, de = count, a = value
FillBytes:
    ld b, a
.loop
    ld a, b
    ld [hl+], a
    dec de
    ld a, d
    or e
    jr nz, .loop
    ret

; hl = src, de = dest, bc = count
CopyBytes:
    ld a, [hl+]
    ld [de], a
    inc de
    dec bc
    ld a, b
    or c
    jr nz, CopyBytes
    ret

; hl = null-terminated string, de = tilemap destination
PrintString:
.loop
    ld a, [hl+]
    or a
    ret z
    push hl
    sub 32
    ld c, a
    ld b, 0
    ld hl, FontMap
    add hl, bc
    ld a, [hl]
    ld [de], a
    inc de
    pop hl
    jr .loop

LoadTiles:
    ld hl, BgTiles
    ld de, _VRAM9000
    ld bc, BgTilesEnd - BgTiles
    call CopyBytes
    ld hl, ShowTiles
    ld de, _VRAM8800
    ld bc, ShowTilesEnd - ShowTiles
    call CopyBytes
    ld hl, ObTiles
    ld de, _VRAM8000
    ld bc, ObTilesEnd - ObTiles
    jp CopyBytes

InstallDma:
    ld hl, DmaRoutine
    ld de, hDma
    ld bc, DmaRoutineEnd - DmaRoutine
    jp CopyBytes

DmaRoutine:
    ld a, HIGH(ShadowOam)
    ldh [rDMA], a
    ld a, 40
.wait
    dec a
    jr nz, .wait
    ret
DmaRoutineEnd:

; =============================================================================
SECTION "Data", ROM0

TrackData:
    db   0,   0,  40,  64,  32,   0, -48, -72
    db -40,   0,   0,  36,  64,  80,  40,   0
    db -32, -64, -32,   0,  48,  72,  48,   0
    db -40, -80, -56, -20,   0,  24,   0,   0

; maxSpeed, accel, steer, pad
CarStats:
    db  88, 3, 4, 0
    db 112, 3, 3, 0
    db  76, 2, 5, 0

; bar lengths shown on the select screen: speed, accel, grip, pad
CarStatBars:
    db 5, 6, 7, 0
    db 8, 7, 5, 0
    db 4, 4, 8, 0

CarNames:
    dw StrCar0, StrCar1, StrCar2
StrCar0: db "HATCH GT", 0
StrCar1: db "SPORTSTER", 0
StrCar2: db "BRUTE 4X4", 0

ShowMapPtrs:
    dw ShowMap0, ShowMap1, ShowMap2

StrTitle:   db "GB HORIZON", 0
StrPressA:  db "PRESS A TO RACE", 0
StrSpd:     db "SPD", 0
StrAcc:     db "ACC", 0
StrGrp:     db "GRP", 0
StrSpdHud:  db "SPD", 0

; rzSeed (x512), lane 0..15, speed
EnemySeed:
    db  7,  2, 58
    db 10,  9, 62
    db 13,  5, 55
    db 16, 13, 66
    db 19,  1, 60
    db 22,  8, 57
    db 25,  4, 64
    db 28, 12, 59
    db 31,  6, 61
    db 34, 10, 56
    db 37,  3, 63

INCLUDE "src/gen/tables.inc"
INCLUDE "src/gen/roadmap.inc"
INCLUDE "src/gen/fontmap.inc"
INCLUDE "src/gen/arrows.inc"
INCLUDE "src/gen/showmaps.inc"
INCLUDE "src/gen/bgtiles.inc"
INCLUDE "src/gen/obtiles.inc"
INCLUDE "src/gen/showtiles.inc"

; =============================================================================
SECTION "Line Table", WRAM0, ALIGN[8]
ScxTable:       ds ROAD_LINES          ; per-scanline scroll (the curve)
BgpTable:       ds ROAD_LINES          ; per-scanline palette (the motion)

SECTION "Shadow OAM", WRAM0, ALIGN[8]
ShadowOam:      ds 160

SECTION "Vars", WRAM0
wSpeed:         ds 1
wPlayerX:       ds 1                   ; signed, screen pixels
wCurve:         ds 1                   ; signed, horizon offset * 2
wCurveTarget:   ds 1
wTrackPos:      ds 2
wMaxSpeed:      ds 1
wAccel:         ds 1
wSteer:         ds 1
wCarSel:        ds 1
wDirty:         ds 1
wKeys:          ds 1
wKeysNew:       ds 1
wRandom:        ds 1
wLastSpeedDisp: ds 1
wLastArrow:     ds 1
wDriftAcc:      ds 1
wScrX:          ds 1
wScrCentre:     ds 1
wScanline:      ds 1
wLineIdx:       ds 1
wEnIdx:         ds 1
wEnLatCur:      ds 1
wEnSpdCur:      ds 1
wOamPtr:        ds 1
wEnemies:       ds NUM_ENEMIES * EN_SIZE

SECTION "HRAM", HRAM
hRoadBase:      ds 1
hCamZLo:        ds 1
hCamZHi:        ds 1
hDebugLy:       ds 1
hDma:           ds 16
