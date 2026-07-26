; =============================================================================
;  hud.asm -- the four row status bar under the 3D view
;
;  The bar lives in tile rows 14..17 of *both* background maps, since the view
;  above it flips between them every frame. It is rebuilt into wHudBuf only
;  when a value actually changes, and pushed to VRAM by the vblank handler.
; =============================================================================

SECTION "HudCode", ROM0

HudTemplate:
    ; row 14 -- rule separating the viewport from the status bar
    REPT 20
    db T_HUD_TOP
    ENDR
    ; row 15 -- health bar and the ammo label
    db "HP"
    db T_BARL
    REPT 8
    db T_BARFULL
    ENDR
    db T_BARR
    db T_HUD_PANEL, T_HUD_PANEL
    db "AMMO"
    db T_HUD_PANEL, T_HUD_PANEL
    ; row 16 -- counters
    db "KILLS"
    db T_HUD_PANEL
    db "00"
    REPT 7
    db T_HUD_PANEL
    ENDR
    db "00"
    db T_HUD_PANEL, T_HUD_PANEL, T_HUD_PANEL
    ; row 17
    REPT 20
    db T_HUD_PANEL
    ENDR

; -----------------------------------------------------------------------------
HudBuild::
    ld hl, HudTemplate
    ld de, wHudBuf
    ld bc, 80
    call MemCopy

    ; ---- health bar: 8 tiles x 4 units ----
    ld a, [wPlayerHp]
    srl a
    srl a                      ; 0..32 units
    ld b, a
    ld hl, wHudBuf + 20 + 3
    ld c, 8
.bar:
    ld a, b
    cp 4
    jr c, .partial
    sub 4
    ld b, a
    ld a, T_BARFULL
    jr .store
.partial:
    ld b, 0
    add T_BAR0
.store:
    ld [hl+], a
    dec c
    jr nz, .bar

    ; ---- counters ----
    ld a, [wKills]
    ld hl, wHudBuf + 40 + 6
    call PutDigits2
    ld a, [wAmmo]
    ld hl, wHudBuf + 40 + 15
    call PutDigits2

    ld a, 1
    ld [wHudDirty], a
    ret

; A = value (0..99), HL = destination for two tiles
PutDigits2::
    ld b, 0
.tens:
    cp 10
    jr c, .ones
    sub 10
    inc b
    jr .tens
.ones:
    ld c, a
    ld a, b
    add T_DIGIT0
    ld [hl+], a
    ld a, c
    add T_DIGIT0
    ld [hl], a
    ret

; -----------------------------------------------------------------------------
; HudUpload: push the bar into both maps. Unrolled so both copies fit inside a
; single vblank (~870 cycles).
HudUpload::
    ld hl, wHudBuf
    ld de, $9800 + 14 * 32
    call HudRows
    ld hl, wHudBuf
    ld de, $9C00 + 14 * 32
    ; fall through

HudRows:
    ld c, 4
.row:
  REPT 20
    ld a, [hl+]
    ld [de], a
    inc de
  ENDR
    ld a, e
    add 12
    ld e, a
    jr nc, :+
    inc d
:   dec c
    jr nz, .row
    ret
