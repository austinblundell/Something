; ============================================================================
;  vm.asm  --  the cutscene interpreter
;
;  The whole game is a byte-code stream: load a picture, fade, speak, hold,
;  branch.  Keeping it data rather than code means tools/story.py can own the
;  script, so the prose and the pacing live in one readable place.
; ============================================================================

SECTION "vm", ROM0

GameMain::
    call AudioInit
    ld  a, 2
    ld  [wTextSpeed], a
    ld  a, 100
    ld  [wWaterHorizon], a
    ld  a, 1
    ld  [wRandState], a

    ld  a, BANK(Story)
    ld  hl, Story
    call RunScript
.loop:
    jr  .loop

; ----------------------------------------------------------------------------
; RunScript -- a = bank, hl = script address.
; ----------------------------------------------------------------------------
RunScript::
    ld  [wScriptBank], a
    ld  a, l
    ld  [wScriptPtr], a
    ld  a, h
    ld  [wScriptPtr + 1], a

VmLoop:
    call EnsureScriptBank
    call VmFetch
    and a
    ret z                       ; OP_END
    cp  OP_COUNT
    ret nc                      ; anything unknown ends the script safely

    add a
    ld  hl, VmJumpTable
    add l
    ld  l, a
    ld  a, h
    adc 0
    ld  h, a
    ld  a, [hl+]
    ld  e, a
    ld  a, [hl]
    ld  d, a
    ld  hl, VmLoop
    push hl                     ; the handler's ret comes back here
    push de
    ret

; VmFetch -- next script byte in a.  Clobbers only a and hl: handlers hold
; earlier operands in b/c/d/e while fetching the next one.
VmFetch::
    ld  a, [wScriptPtr]
    ld  l, a
    ld  a, [wScriptPtr + 1]
    ld  h, a
    ld  a, [hl+]
    ld  [wVmByte], a
    ld  a, l
    ld  [wScriptPtr], a
    ld  a, h
    ld  [wScriptPtr + 1], a
    ld  a, [wVmByte]
    ret

; VmFetchWord -- next two script bytes in de (little endian).
VmFetchWord::
    call VmFetch
    ld  e, a
    call VmFetch
    ld  d, a
    ret

; VmWait -- b frames, keeping effects and music alive.
VmWait::
    call WaitFrames
    ret

; ============================================================================
;  handlers
; ============================================================================

VmOpPic:
    call VmFetch
    ld  [wVmArgBank], a
    call VmFetchWord
    ld  h, d
    ld  l, e
    ld  a, [wVmArgBank]
    call LoadPicture
    ld  a, 1
    ld  [wHasPic], a
    xor a
    ld  [wBoxOpen], a
    ld  [wPalMode], a
    call EnsureScriptBank
    ret

VmOpFadeIn:
    call VmFetch
    ld  b, a
    call FadeIn
    ret

VmOpFadeOut:
    call VmFetch
    ld  b, a
    call FadeOut
    ret

VmOpText:
    call VmFetchWord
    ld  h, d
    ld  l, e
    call PrintString
    ret

VmOpBoxClose:
    call CloseBox
    ret

VmOpWait:
    call VmFetch
    ld  b, a
    call VmWait
    ret

VmOpWaitKey:
    call WaitAnyKey
    ret

VmOpFx:
    call VmFetch
    call FxSet
    ret

VmOpShake:
    call VmFetch
    ld  [wShakeTimer], a
    ld  b, a
    call VmWait
    ret

VmOpFlash:
    call VmFetch
    ld  b, a
    call FlashScreen
    ret

VmOpSfx:
    call VmFetch
    call PlaySfx
    ret

VmOpMusic:
    call VmFetch
    call PlayMusic
    ret

VmOpJump:
    call VmFetchWord
    ld  a, e
    ld  [wScriptPtr], a
    ld  a, d
    ld  [wScriptPtr + 1], a
    ret

VmOpJumpIf:
    call VmFetch
    ld  c, a                    ; variable index
    call VmFetch
    ld  [wVmCmp], a             ; value to match
    call VmFetchWord            ; de = target
    ld  b, 0
    ld  hl, wVars
    add hl, bc
    ld  a, [hl]
    ld  hl, wVmCmp
    cp  [hl]
    ret nz
    ld  a, e
    ld  [wScriptPtr], a
    ld  a, d
    ld  [wScriptPtr + 1], a
    ret

VmOpSetVar:
    call VmFetch
    ld  c, a
    call VmFetch
    ld  b, a
    ld  hl, wVars
    ld  a, l
    add c
    ld  l, a
    ld  a, h
    adc 0
    ld  h, a
    ld  [hl], b
    ret

VmOpTextSpeed:
    call VmFetch
    ld  [wTextSpeed], a
    ret

VmOpBeat:
    call VmFetch
    ld  b, a
    call VmWait
    ret

VmOpPan:
    call VmFetch
    ld  c, a                    ; total offset
    call VmFetch
    ld  b, a                    ; frames per step
.loop:
    push bc
    ld  a, [wPanBase]
    inc a
    ld  [wPanBase], a
    call VmWait
    pop bc
    dec c
    jr  nz, .loop
    ret

; ----------------------------------------------------------------------------
; OP_CARD -- a chapter title on black.  The card is built while the screen is
; already dark, so the LCD can be blanked for the map rewrite.
; ----------------------------------------------------------------------------
VmOpCard:
    call VmFetchWord
    push de
    call CloseBox
    ld  b, 2
    call FadeOut
    ; A card is a beat of silence: no weather from the scene we just left.
    ld  a, FX_NONE
    call FxSet
    call ResetOam
    call LcdOff
    ld  hl, _SCRN0
    ld  bc, 32 * 32
    ld  a, TILE_BLANK
    call MemFill
    ld  a, [wIsCGB]
    and a
    jr  z, .noAttr
    ld  a, 1
    ld  [rVBK], a
    ld  hl, _SCRN0
    ld  bc, 32 * 32
    ld  a, 6
    call MemFill
    xor a
    ld  [rVBK], a
.noAttr:
    xor a
    ld  [wHasPic], a
    ld  [wBoxOpen], a
    ld  a, 6
    ld  [wCardRow], a
    ld  a, 1
    ld  [wPalMode], a           ; light lettering on a dark ground
    call InstallUiPalettes
    call LcdOn
    pop de
    ld  h, d
    ld  l, e
    call PrintCentered
    ld  b, 8
    call FadeIn
    ld  b, 110
    call VmWait
    ld  b, 8
    call FadeOut
    ret

; ----------------------------------------------------------------------------
; OP_TITLE -- hold on the title picture with a blinking prompt.
; ----------------------------------------------------------------------------
VmOpTitle:
    ld  b, 10
    call FadeIn
.loop:
    call WaitFrame
    call FxStep
    ld  a, [wFrameCounter]
    and $20
    jr  z, .hide
    ld  a, [wPromptShown]
    and a
    jr  nz, .checkKey
    ld  a, 1
    ld  [wPromptShown], a
    ld  hl, PressStartText
    call DrawPrompt
    jr  .checkKey
.hide:
    ld  a, [wPromptShown]
    and a
    jr  z, .checkKey
    xor a
    ld  [wPromptShown], a
    ld  hl, BlankPromptText
    call DrawPrompt
.checkKey:
    ld  a, [wJoyPressed]
    and PADF_A | PADF_START
    jr  z, .loop

    ld  a, SFX_CHIME
    call PlaySfx
    ld  b, 1
    call FlashScreen
    ld  b, 6
    call FadeOut
    ret

; DrawPrompt -- hl = 11 characters to sit centred on row 15.
DrawPrompt:
    push hl
    call WaitFrame
    pop hl
    ld  b, 15
    ld  c, (SCRN_COLS - 11) / 2
    push hl
    call MapAddr
    pop de
.loop:
    ld  a, [de]
    and a
    ret z
    sub FONT_FIRST_CHAR
    add TILE_FONT_BASE
    ld  [hl+], a
    inc de
    jr  .loop

PressStartText:    db "PRESS START", 0
BlankPromptText:   db "           ", 0

; ----------------------------------------------------------------------------
; OP_EXPLORE -- hand the frame to the reticle.
; ----------------------------------------------------------------------------
VmOpExplore:
    call VmFetchWord
    ld  h, d
    ld  l, e
    call ExploreRun
    call EnsureScriptBank
    ret

; ----------------------------------------------------------------------------
; OP_CHOICE -- prompt, then a two-line menu.  Result lands in VAR_CHOICE.
; ----------------------------------------------------------------------------
VmOpChoice:
    call VmFetchWord
    ld  a, e
    ld  [wChoicePrompt], a
    ld  a, d
    ld  [wChoicePrompt + 1], a
    call VmFetchWord
    ld  a, e
    ld  [wChoiceA], a
    ld  a, d
    ld  [wChoiceA + 1], a
    call VmFetchWord
    ld  a, e
    ld  [wChoiceB], a
    ld  a, d
    ld  [wChoiceB + 1], a

    ld  a, [wChoicePrompt]
    ld  l, a
    ld  a, [wChoicePrompt + 1]
    ld  h, a
    call PrintString
    call ClearTextArea

    xor a
    ld  [wChoiceSel], a
    call DrawChoiceOptions

.loop:
    call WaitFrame
    call FxStep
    ld  a, [wJoyPressed]
    ld  b, a
    and PADF_UP | PADF_DOWN
    jr  z, .noMove
    ld  a, [wChoiceSel]
    xor 1
    ld  [wChoiceSel], a
    ld  a, SFX_BLIP
    call PlaySfx
    call DrawChoiceOptions
.noMove:
    ld  a, [wJoyPressed]
    and PADF_A
    jr  z, .loop

    ld  a, SFX_CHIME
    call PlaySfx
    ld  a, [wChoiceSel]
    inc a                       ; 1 or 2, so 0 can still mean "not asked"
    ld  [wVars + VAR_CHOICE], a
    call CloseBox
    call EnsureScriptBank
    ret

DrawChoiceOptions:
    call EnsureScriptBank
    call WaitFrame
    ld  b, TEXT_ROW
    ld  c, TEXT_LINES
    ld  a, TILE_BLANK
    call FillBgMapRowsInset

    ld  a, [wChoiceA]
    ld  e, a
    ld  a, [wChoiceA + 1]
    ld  d, a
    ld  b, TEXT_ROW
    call DrawChoiceLine
    ld  a, [wChoiceB]
    ld  e, a
    ld  a, [wChoiceB + 1]
    ld  d, a
    ld  b, TEXT_ROW + 1
    call DrawChoiceLine

    ; The cursor sits in the frame column beside the chosen line.
    ld  a, [wChoiceSel]
    add TEXT_ROW
    ld  b, a
    ld  c, TEXT_COL
    call MapAddr
    ld  [hl], TILE_BOX_CURSOR
    ret

; DrawChoiceLine -- de = string, b = map row.
DrawChoiceLine:
    ld  c, TEXT_COL + 1
    push de
    call MapAddr
    pop de
.loop:
    ld  a, [de]
    and a
    ret z
    sub FONT_FIRST_CHAR
    add TILE_FONT_BASE
    ld  [hl+], a
    inc de
    jr  .loop

; ----------------------------------------------------------------------------
; OP_TENDFLAME -- breathe the ember back to life.
;
; Mash A to fill the gauge before it decays away.  The colour palette warms as
; the gauge climbs, so on a Game Boy Color the whole room comes back to life.
; ----------------------------------------------------------------------------
DEF GAUGE_MAX   EQU 18
DEF GAUGE_WIDTH EQU 16

VmOpTendFlame:
    call OpenBox
    ld  hl, TendPromptText
    call DrawTendPrompt
    xor a
    ld  [wGauge], a
    ld  [wGaugeTick], a
    ld  a, FX_EMBERS
    call FxSet
    ld  a, 1
    ld  [wTendActive], a

.loop:
    call WaitFrame
    call FxStep

    ld  a, [wJoyPressed]
    and PADF_A
    jr  z, .noPress
    ld  a, [wGauge]
    add 2
    ld  [wGauge], a
    ld  a, SFX_BLIP
    call PlaySfx
.noPress:

    ; Slow decay: the ember is always trying to go out.
    ld  a, [wGaugeTick]
    inc a
    ld  [wGaugeTick], a
    cp  10
    jr  c, .noDecay
    xor a
    ld  [wGaugeTick], a
    ld  a, [wGauge]
    and a
    jr  z, .noDecay
    dec a
    ld  [wGauge], a
.noDecay:

    call DrawGauge
    ld  a, [wGauge]
    cp  GAUGE_MAX
    jr  c, .loop

    ld  a, SFX_CHIME
    call PlaySfx
    ld  b, 2
    call FlashScreen
    xor a
    ld  [wTendActive], a
    ld  a, 1
    ld  [wVars + VAR_OIL], a
    ld  b, 20
    call VmWait
    call CloseBox
    call EnsureScriptBank
    ret

DrawTendPrompt:
    push hl
    call WaitFrame
    pop hl
    ld  b, TEXT_ROW
    ld  c, TEXT_COL
    push hl
    call MapAddr
    pop de
.loop:
    ld  a, [de]
    and a
    ret z
    sub FONT_FIRST_CHAR
    add TILE_FONT_BASE
    ld  [hl+], a
    inc de
    jr  .loop

DrawGauge:
    ld  b, TEXT_ROW + 2
    ld  c, TEXT_COL
    call MapAddr
    ld  a, [wGauge]
    ld  c, a
    ld  b, GAUGE_WIDTH
.cell:
    ld  a, c
    and a
    jr  z, .empty
    dec c
    ld  a, TILE_GAUGE_ON
    jr  .put
.empty:
    ld  a, TILE_GAUGE_OFF
.put:
    ld  [hl+], a
    dec b
    jr  nz, .cell
    ret

TendPromptText: db "BREATHE.", 0

; ----------------------------------------------------------------------------
;  dispatch table -- order must match the OP_ constants in defs.inc
; ----------------------------------------------------------------------------
VmJumpTable:
    dw VmOpEnd          ; $00 (never reached; OP_END is handled inline)
    dw VmOpPic          ; $01
    dw VmOpFadeIn       ; $02
    dw VmOpFadeOut      ; $03
    dw VmOpText         ; $04
    dw VmOpBoxClose     ; $05
    dw VmOpWait         ; $06
    dw VmOpWaitKey      ; $07
    dw VmOpFx           ; $08
    dw VmOpShake        ; $09
    dw VmOpFlash        ; $0A
    dw VmOpSfx          ; $0B
    dw VmOpMusic        ; $0C
    dw VmOpChoice       ; $0D
    dw VmOpJumpIf       ; $0E
    dw VmOpJump         ; $0F
    dw VmOpSetVar       ; $10
    dw VmOpTitle        ; $11
    dw VmOpCard         ; $12
    dw VmOpExplore      ; $13
    dw VmOpPan          ; $14
    dw VmOpTextSpeed    ; $15
    dw VmOpBeat         ; $16
    dw VmOpTendFlame    ; $17
    dw VmOpCard         ; $18 -- credits reuse the card renderer
DEF OP_COUNT EQU $19

VmOpEnd:
    ret

SECTION "vm ram", WRAM0
wPromptShown::   db
wChoicePrompt::  dw
wChoiceA::       dw
wChoiceB::       dw
wChoiceSel::     db
wGauge::         db
wGaugeTick::     db
wVmCmp::         db
wVmByte::        db
wVmArgBank::     db
wPalMode::       db
wTendActive::    db
