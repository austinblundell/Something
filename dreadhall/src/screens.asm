; =============================================================================
;  screens.asm -- title, death and escape screens
; =============================================================================

; HL = destination in the map, DE = 0-terminated string (charmapped to tiles)
SECTION "ScreenCode", ROM0

DrawText::
    ld a, [de]
    and a
    ret z
    ld [hl+], a
    inc de
    jr DrawText

; -----------------------------------------------------------------------------
DrawTitle::
    ld hl, $9800
    ld bc, $800
    ld a, T_HUD_PANEL
    call MemSet

    ; logo, 19 tiles wide, starting on row 2
    ld a, T_LOGO
    ld hl, $9800 + 2 * 32
    ld b, LOGO_TH
.lrow:
    push hl
    ld c, LOGO_TW
.lcol:
    ld [hl+], a
    inc a
    dec c
    jr nz, .lcol
    pop hl
    ld de, 32
    add hl, de
    dec b
    jr nz, .lrow

    ld hl, $9800 + 7 * 32 + 2
    ld de, StrTagline
    call DrawText
    ld hl, $9800 + 12 * 32 + 0
    ld de, StrCtl1
    call DrawText
    ld hl, $9800 + 13 * 32 + 0
    ld de, StrCtl2
    call DrawText
    ld hl, $9800 + 14 * 32 + 0
    ld de, StrCtl3
    call DrawText
    ret

TitleUpdate::
    ; blink the prompt; we are called just after halt, so VRAM is writable
    ld a, [wFrameCounter]
    and $20
    ld de, StrPressBlank
    jr z, :+
    ld de, StrPress
:   ld hl, $9800 + 10 * 32 + 4
    call DrawText

    ld a, [wPadNew]
    and PADF_START
    ret z
    call EnterPlay
    ret

; -----------------------------------------------------------------------------
DrawEndScreen::
    ld hl, $9800
    ld bc, $800
    ld a, T_HUD_PANEL
    call MemSet

    ld a, [wGameState]
    cp ST_WIN
    jr z, .win
    ld hl, $9800 + 5 * 32 + 6
    ld de, StrDied
    call DrawText
    ld hl, $9800 + 7 * 32 + 1
    ld de, StrDiedSub
    call DrawText
    jr .stats
.win:
    ld hl, $9800 + 5 * 32 + 4
    ld de, StrEscaped
    call DrawText
    ld hl, $9800 + 7 * 32 + 3
    ld de, StrEscapedSub
    call DrawText

.stats:
    ld hl, $9800 + 10 * 32 + 4
    ld de, StrKills
    call DrawText
    ld a, [wKills]
    ld hl, $9800 + 10 * 32 + 12
    call PutDigits2
    ret

EndUpdate::
    ld a, [wEndTimer]
    and a
    jr z, .ready
    dec a
    ld [wEndTimer], a
    ret
.ready:
    ; blink the prompt
    ld a, [wFrameCounter]
    and $20
    ld de, StrPressBlank
    jr z, :+
    ld de, StrPress
:   ld hl, $9800 + 14 * 32 + 4
    call DrawText

    ld a, [wPadNew]
    and PADF_START
    ret z
    call EnterTitle
    ret

; -----------------------------------------------------------------------------
StrTagline:     db "SOMETHING IS AWAKE", 0
StrPress:       db "PRESS START", 0
StrPressBlank:  db "           ", 0
StrCtl1:        db "DPAD  MOVE AND TURN", 0
StrCtl2:        db "B    HOLD TO STRAFE", 0
StrCtl3:        db "A            SHOOT", 0
StrDied:        db "YOU DIED", 0
StrDiedSub:     db "THE DARK KEEPS YOU", 0
StrEscaped:     db "YOU ESCAPED", 0
StrEscapedSub:  db "DAYLIGHT AT LAST", 0
StrKills:       db "KILLS", 0
