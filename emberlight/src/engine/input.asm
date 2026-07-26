; ============================================================================
;  input.asm  --  joypad polling, held and newly-pressed masks
; ============================================================================

SECTION "input", ROM0

ReadJoypad::
    ld  a, [wJoyHeld]
    ld  [wJoyPrev], a

    ld  a, P1F_GET_DPAD
    ld  [rJOYP], a
    ld  a, [rJOYP]
    ld  a, [rJOYP]              ; the port needs a moment to settle
    cpl
    and $0F
    swap a
    ld  b, a

    ld  a, P1F_GET_BTN
    ld  [rJOYP], a
    ld  a, [rJOYP]
    ld  a, [rJOYP]
    cpl
    and $0F
    or  b
    ld  [wJoyHeld], a

    ld  a, P1F_GET_NONE
    ld  [rJOYP], a

    ; newly pressed = held & ~previous
    ld  a, [wJoyPrev]
    cpl
    ld  b, a
    ld  a, [wJoyHeld]
    and b
    ld  [wJoyPressed], a
    ret

; WaitButton -- block until A or START is newly pressed.
WaitButton::
.loop:
    call WaitFrame
    call FxStep
    ld  a, [wJoyPressed]
    and PADF_A | PADF_START
    jr  z, .loop
    ret

; WaitAnyKey -- as above, plus B, for "press anything to move on".
WaitAnyKey::
.loop:
    call WaitFrame
    call FxStep
    ld  a, [wJoyPressed]
    and PADF_A | PADF_START | PADF_B
    jr  z, .loop
    ret
