; =============================================================================
;  render.asm -- raycaster and tilemap column builder
;
;  One DDA ray per tile column. The grid walk is branch-duplicated so the axis
;  that was crossed is implied by which hit label we land on, keeping the inner
;  loop down to ~37 cycles with no per-step bookkeeping.
; =============================================================================

SECTION "RenderCode", ROM0

MatBaseTab:
    db MAT_BASE + 0 * MAT_STRIDE
    db MAT_BASE + 1 * MAT_STRIDE
    db MAT_BASE + 2 * MAT_STRIDE
    db MAT_BASE + 3 * MAT_STRIDE
    db MAT_BASE + 4 * MAT_STRIDE
    db MAT_BASE + 5 * MAT_STRIDE

; -----------------------------------------------------------------------------
RenderView::
    xor a
    ldh [hCol], a
.colLoop:
    ; ray angle = player angle + this column's fixed offset
    ld hl, ColAngle
    ldh a, [hCol]
    add l
    ld l, a
    jr nc, :+
    inc h
:   ld a, [hl]
    ld hl, wPlayerAng
    add [hl]
    ldh [hRayAng], a

    call CastRay
    call BuildColumn

    ldh a, [hCol]
    inc a
    ldh [hCol], a
    cp VIEW_COLS
    jr c, .colLoop
    ret

; -----------------------------------------------------------------------------
; CastRay: walks the grid for the angle in hRayAng.
; Leaves the perpendicular distance in wColDist[col], the wall half height in
; wColH2[col] and the shaded material in wColMat[col].
; -----------------------------------------------------------------------------
CastRay:
    ; ---- X axis setup ----
    ldh a, [hRayAng]
    call CosLookup             ; BC = cos(angle) = ray dir X
    bit 7, b
    jr nz, .xneg
    ld a, 1
    ldh [hStepX], a
    ld a, [wPlayerX]           ; distance to the boundary ahead is 1 - frac
    cpl
    inc a
    jr .xdone
.xneg:
    ld a, -1
    ldh [hStepX], a
    ld a, [wPlayerX]
.xdone:
    ldh [hTmp], a

    ldh a, [hRayAng]
    add 64                     ; 1/|cos(a)| == RecipTab[a + 64]
    ld l, a
    ld h, 0
    add hl, hl
    ld de, RecipTab
    add hl, de
    ld a, [hl+]
    ld c, a
    ld b, [hl]
    ld a, c
    ldh [hDdXl], a
    ld a, b
    ldh [hDdXh], a
    ldh a, [hTmp]
    and a
    jr nz, .mulx
    ld h, b                    ; frac was exactly 0: a whole cell to the boundary
    ld l, c
    jr .stx
.mulx:
    call MulFrac
.stx:
    ld a, l
    ldh [hSdXl], a
    ld a, h
    ldh [hSdXh], a

    ; ---- Y axis setup ----
    ldh a, [hRayAng]
    call SinLookup             ; BC = sin(angle) = ray dir Y
    bit 7, b
    jr nz, .yneg
    ld a, 32                   ; one map row forward
    ldh [hStepYl], a
    xor a
    ldh [hStepYh], a
    ld a, [wPlayerY]
    cpl
    inc a
    jr .ydone
.yneg:
    ld a, -32
    ldh [hStepYl], a
    ld a, $FF
    ldh [hStepYh], a
    ld a, [wPlayerY]
.ydone:
    ldh [hTmp], a

    ldh a, [hRayAng]
    ld l, a
    ld h, 0
    add hl, hl
    ld de, RecipTab
    add hl, de
    ld a, [hl+]
    ld c, a
    ld b, [hl]
    ld a, c
    ldh [hDdYl], a
    ld a, b
    ldh [hDdYh], a
    ldh a, [hTmp]
    and a
    jr nz, .muly
    ld h, b
    ld l, c
    jr .sty
.muly:
    call MulFrac
.sty:
    ld a, l
    ldh [hSdYl], a
    ld a, h
    ldh [hSdYh], a

    ; ---- map pointer: LevelMap + mapY*32 + mapX ----
    ld a, [wPlayerY + 1]
    and 31
    ld l, a
    ld h, 0
    add hl, hl
    add hl, hl
    add hl, hl
    add hl, hl
    add hl, hl                 ; *32, low 5 bits clear
    ld a, [wPlayerX + 1]
    and 31
    or l
    ld l, a
    ld de, LevelMap
    add hl, de

    ; ---- DDA: HL = map pointer, DE = sideDistX, BC = sideDistY ----
    ldh a, [hSdXl]
    ld e, a
    ldh a, [hSdXh]
    ld d, a
    ldh a, [hSdYl]
    ld c, a
    ldh a, [hSdYh]
    ld b, a
    ld a, 48
    ldh [hCount], a

.loop:
    ld a, e
    sub c
    ld a, d
    sbc b
    jr nc, .stepY

.stepX:
    ldh a, [hDdXl]
    add e
    ld e, a
    ldh a, [hDdXh]
    adc d
    ld d, a
    ldh a, [hStepX]
    add l
    ld l, a
    ld a, [hl]
    and a
    jr nz, .hitX
    ldh a, [hCount]
    dec a
    ldh [hCount], a
    jr nz, .loop
    jr .miss

.stepY:
    ldh a, [hDdYl]
    add c
    ld c, a
    ldh a, [hDdYh]
    adc b
    ld b, a
    ldh a, [hStepYl]
    add l
    ld l, a
    ldh a, [hStepYh]
    adc h
    ld h, a
    ld a, [hl]
    and a
    jr nz, .hitY
    ldh a, [hCount]
    dec a
    ldh [hCount], a
    jr nz, .loop
    jr .miss

    ; distance is the side distance from *before* the last step, so subtract
    ; the delta back off; the label we reach tells us which axis was crossed.
.hitX:
    ldh [hTmp2], a
    ldh a, [hDdXl]
    ld c, a
    ldh a, [hDdXh]
    ld b, a
    ld a, e
    sub c
    ld l, a
    ld a, d
    sbc b
    ld h, a
    xor a                      ; side 0: no extra shading
    jr .finish

.hitY:
    ldh [hTmp2], a
    ldh a, [hDdYl]
    ld e, a
    ldh a, [hDdYh]
    ld d, a
    ld a, c
    sub e
    ld l, a
    ld a, b
    sbc d
    ld h, a
    ld a, 1                    ; side 1: one shade darker
    jr .finish

.miss:
    ld a, 1
    ldh [hTmp2], a
    ld hl, $0FF0
    xor a

.finish:
    ldh [hTmp], a              ; side
    ; store the perpendicular distance for sprite occlusion
    push hl
    ld hl, wColDist
    ldh a, [hCol]
    add a
    add l
    ld l, a
    jr nc, :+
    inc h
:   pop de
    ld a, e
    ld [hl+], a
    ld [hl], d
    ld h, d
    ld l, e

    ; ---- distance -> table index (1/16 cell units, clamped at 16 cells) ----
    ld a, h
    cp $10
    jr c, .near
    ld a, $FF
    jr .haveIdx
.near:
    ld a, l
    swap a
    and $0F
    ld c, a
    ld a, h
    swap a
    and $F0
    or c
.haveIdx:
    ld c, a                    ; C = distance index

    ; ---- wall half height (per column table folds in the fisheye correction) --
    ld hl, ColTab
    ldh a, [hCol]
    add l
    ld l, a
    jr nc, :+
    inc h
:   ld a, [hl]
    add HIGH(HeightTabs)
    ld h, a
    ld l, c
    ld a, [hl]
    ld hl, wColH2
    ld b, a
    ldh a, [hCol]
    add l
    ld l, a
    jr nc, :+
    inc h
:   ld [hl], b

    ; ---- shade: distance band, one darker for Y-facing walls and for metal ----
    ld h, HIGH(ShadeTab)
    ld l, c
    ld a, [hl]
    ld b, a
    ldh a, [hTmp]
    add b
    ld b, a
    ldh a, [hTmp2]
    dec a                      ; wall type 1 -> +0, type 2 -> +1
    add b
    cp NUM_MAT
    jr c, :+
    ld a, NUM_MAT - 1
:   ld b, a
    ld hl, wColMat
    ldh a, [hCol]
    add l
    ld l, a
    jr nc, :+
    inc h
:   ld [hl], b
    ret

; -----------------------------------------------------------------------------
; BuildColumn: writes the 14 tiles of the current column into wMapBuf.
;
;   ceiling rows  : A     (A = top >> 3)
;   top cap       : 1     (only when top & 7 is non-zero)
;   wall body     : 12-2A (or 14-2A when the wall starts on a tile boundary)
;   bottom cap    : 1
;   floor rows    : A
;
; The horizon sits on a tile boundary, so the top and bottom edges of a wall can
; never share a tile -- which is exactly why the static tile set is enough.
; -----------------------------------------------------------------------------
BuildColumn:
    ; material -> tile block base
    ld hl, wColMat
    ldh a, [hCol]
    add l
    ld l, a
    jr nc, :+
    inc h
:   ld a, [hl]
    ld hl, MatBaseTab
    add l
    ld l, a
    ld a, [hl]
    ldh [hMatBase], a

    ; top = HORIZON - h2
    ld hl, wColH2
    ldh a, [hCol]
    add l
    ld l, a
    jr nc, :+
    inc h
:   ld a, HORIZON
    sub [hl]
    ld b, a
    and 7
    ld c, a                    ; C = pixel offset inside the tile
    ld a, b
    rrca
    rrca
    rrca
    and $1F
    ld b, a                    ; B = whole ceiling tile rows

    ; destination: current back buffer + col, stepping a full row each write
    ld a, [wRenderPtr]
    ld l, a
    ld a, [wRenderPtr + 1]
    ld h, a
    ldh a, [hCol]
    add l
    ld l, a
    jr nc, :+
    inc h
:   ld de, VIEW_COLS

    ; ---- ceiling ----
    ld a, b
    and a
    jr z, .noCeil
    push bc
    ld a, T_CEIL
    call FillCol
    pop bc
.noCeil:

    ld a, c
    and a
    jr z, .flush               ; wall starts exactly on a tile boundary

    ; ---- top cap ----
    ldh a, [hMatBase]
    add c
    ld [hl], a
    add hl, de

    ; ---- body: 12 - 2*ceilRows ----
    ld a, 12
    sub b
    sub b
    jr z, .noBody
    jr c, .noBody
    push bc
    ld b, a
    ldh a, [hMatBase]
    call FillCol
    pop bc
.noBody:

    ; ---- bottom cap: mirror of the top offset ----
    ld a, 8
    sub c
    add 7                      ; bottom caps live at matBase + 7 + k
    ld c, a
    ldh a, [hMatBase]
    add c
    ld [hl], a
    add hl, de
    jr .floor

.flush:
    ; ---- body only: 14 - 2*ceilRows ----
    ld a, 14
    sub b
    sub b
    jr z, .floor
    jr c, .floor
    push bc
    ld b, a
    ldh a, [hMatBase]
    call FillCol
    pop bc

.floor:
    ld a, b
    and a
    ret z
    ld a, T_FLOOR
    ; fall through

; A = tile, B = count, HL = dest, DE = stride
FillCol:
    ld [hl], a
    add hl, de
    dec b
    jr nz, FillCol
    ret
