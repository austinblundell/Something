; ============================================================================
;  explore.asm  --  cursor-driven examination of a full-screen picture
;
;  EMBERLIGHT is cinematic rather than tile-based, so the interactive beats
;  reuse the cutscene art directly: a reticle moves over the painting and A
;  examines whatever is under it.  Hotspot tables live in the script bank.
;
;  Table layout:
;    db  count
;    per entry, 7 bytes:
;      db x, y, w, h        -- hit rectangle in pixels
;      dw text              -- what the keeper notices
;      db flags             -- bit 7: examining this ends the segment
;                              bit 0..2: global variable to set to 1
; ============================================================================

DEF SPOT_SIZE   EQU 7
DEF SPOTF_EXIT  EQU %10000000
DEF SPOTF_SETV  EQU %01000000

SECTION "explore", ROM0

; ----------------------------------------------------------------------------
; ExploreRun -- hl = hotspot table in the script bank.
; ----------------------------------------------------------------------------
ExploreRun::
    ld  a, l
    ld  [wSpotTable], a
    ld  a, h
    ld  [wSpotTable + 1], a
    ld  a, 72
    ld  [wCurX], a
    ld  a, 56
    ld  [wCurY], a
    xor a
    ld  [wExploreExit], a
    ld  a, 1
    ld  [wExploreActive], a

.loop:
    call WaitFrame
    call FxStep
    call ExploreMoveCursor

    ld  a, [wJoyPressed]
    and PADF_A
    jr  z, .loop

    call ExploreHitTest
    ld  a, [wSpotFound]
    and a
    jr  z, .loop

    ; Something is there: read the entry and say what she sees.
    call EnsureScriptBank
    ld  a, [wSpotEntry]
    ld  l, a
    ld  a, [wSpotEntry + 1]
    ld  h, a
    ld  de, 4
    add hl, de
    ld  a, [hl+]
    ld  e, a
    ld  a, [hl+]
    ld  d, a
    ld  a, [hl]                 ; flags
    ld  [wSpotFlags], a

    xor a
    ld  [wExploreActive], a     ; hide the reticle while she speaks
    call ResetOam
    ld  h, d
    ld  l, e
    call PrintString
    call CloseBox
    ld  a, 1
    ld  [wExploreActive], a

    ld  a, [wSpotFlags]
    and SPOTF_SETV
    jr  z, .noVar
    ld  a, [wSpotFlags]
    and 7
    ld  c, a
    ld  b, 0
    ld  hl, wVars
    add hl, bc
    ld  [hl], 1
.noVar:
    ld  a, [wSpotFlags]
    and SPOTF_EXIT
    jr  z, .loop

    xor a
    ld  [wExploreActive], a
    call ResetOam
    ret

; ----------------------------------------------------------------------------
; ExploreMoveCursor -- d-pad nudges the reticle, two pixels a frame.
; ----------------------------------------------------------------------------
ExploreMoveCursor:
    ld  a, [wJoyHeld]
    ld  b, a

    bit PADB_LEFT, b
    jr  z, .notLeft
    ld  a, [wCurX]
    sub 2
    jr  c, .notLeft
    ld  [wCurX], a
.notLeft:
    bit PADB_RIGHT, b
    jr  z, .notRight
    ld  a, [wCurX]
    add 2
    cp  146
    jr  nc, .notRight
    ld  [wCurX], a
.notRight:
    bit PADB_UP, b
    jr  z, .notUp
    ld  a, [wCurY]
    sub 2
    jr  c, .notUp
    ld  [wCurY], a
.notUp:
    bit PADB_DOWN, b
    jr  z, .notDown
    ld  a, [wCurY]
    add 2
    cp  114
    jr  nc, .notDown
    ld  [wCurY], a
.notDown:
    ret

; ----------------------------------------------------------------------------
; ExploreDrawCursor -- four corner brackets, breathing outward and back.
; ----------------------------------------------------------------------------
ExploreDrawCursor::
    ld  a, [wExploreActive]
    and a
    ret z

    ; A slow one-pixel breath, so the reticle reads as alive rather than as
    ; part of the painting.
    ld  a, [wFrameCounter]
    and $10
    jr  z, .tight
    ld  a, 1
    jr  .havePulse
.tight:
    xor a
.havePulse:
    ld  [wCurPulse], a

    ; Four 8x8 corners boxing exactly the 16x16 the hit test uses, so what
    ; the player aims at is what gets examined.
    ld  c, 0
.corner:
    ld  a, c
    ld  [wCurCorner], a

    ld  a, [wCurY]
    add 16
    ld  b, a                    ; OAM Y for the top row
    ld  a, [wCurX]
    add 8
    ld  e, a                    ; OAM X for the left column

    ld  a, [wCurCorner]
    and 1
    jr  z, .leftCol
    ld  a, e
    add 8
    ld  e, a
    ld  a, [wCurPulse]
    add e
    ld  e, a                    ; right column pushes outward on the pulse
    jr  .haveX
.leftCol:
    ld  a, e
    ld  d, a
    ld  a, [wCurPulse]
    ld  e, a
    ld  a, d
    sub e
    ld  e, a
.haveX:
    ld  a, [wCurCorner]
    and 2
    jr  z, .topRow
    ld  a, b
    add 8
    ld  b, a
    ld  a, [wCurPulse]
    add b
    ld  b, a
    jr  .haveY
.topRow:
    ld  a, [wCurPulse]
    ld  d, a
    ld  a, b
    sub d
    ld  b, a
.haveY:
    ld  a, [wCurCorner]
    add TILE_RETICLE_TL
    ld  d, a
    ld  a, e
    ld  c, a
    ld  e, 0
    call OamPut

    ld  a, [wCurCorner]
    inc a
    ld  c, a
    cp  4
    jr  c, .corner
    ret

; ----------------------------------------------------------------------------
; ExploreHitTest -- is the reticle centre inside any hotspot?
; Sets wSpotFound and wSpotEntry.
; ----------------------------------------------------------------------------
ExploreHitTest:
    xor a
    ld  [wSpotFound], a
    call EnsureScriptBank

    ld  a, [wCurX]
    add 8
    ld  [wCurCx], a
    ld  a, [wCurY]
    add 8
    ld  [wCurCy], a

    ld  a, [wSpotTable]
    ld  l, a
    ld  a, [wSpotTable + 1]
    ld  h, a
    ld  a, [hl+]
    and a
    ret z
    ld  b, a                    ; entry count

.entry:
    ; hl points at this entry's x; keep the anchor so the four field reads
    ; below never have to track where hl drifted to.
    ld  a, l
    ld  [wSpotEntry], a
    ld  a, h
    ld  [wSpotEntry + 1], a

    ld  a, [hl+]                ; x
    ld  d, a
    ld  a, [hl+]                ; y
    ld  e, a
    ld  a, [hl+]                ; w
    ld  c, a
    ld  a, [hl]                 ; h
    ld  [wSpotH], a

    ld  a, [wCurCx]
    cp  d
    jr  c, .miss                ; centre is left of the spot
    ld  a, d
    add c
    ld  c, a                    ; c = x + w
    ld  a, [wCurCx]
    cp  c
    jr  nc, .miss               ; centre is right of the spot

    ld  a, [wCurCy]
    cp  e
    jr  c, .miss                ; centre is above
    ld  a, [wSpotH]
    add e
    ld  c, a                    ; c = y + h
    ld  a, [wCurCy]
    cp  c
    jr  nc, .miss               ; centre is below

    ld  a, 1
    ld  [wSpotFound], a
    ret

.miss:
    ld  a, [wSpotEntry]
    ld  l, a
    ld  a, [wSpotEntry + 1]
    ld  h, a
    ld  de, SPOT_SIZE
    add hl, de
    dec b
    jr  nz, .entry
    ret

SECTION "explore ram", WRAM0
wExploreActive:: db
wCurPulse::      db
wCurCx::         db
wCurCy::         db
wSpotFound::     db
wSpotEntry::     dw
wSpotFlags::     db
wSpotH::         db
wCurCorner::     db
