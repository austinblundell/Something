; ============================================================================
;  text.asm  --  dialogue box and typewriter printing
;
;  VRAM writes all happen immediately after WaitFrame returns.  The VBlank
;  handler finishes well before the end of the blanking period, so there are
;  a few hundred safe cycles left -- enough for a row of map or a glyph -- and
;  no LCD blanking or tearing.
;
;  Strings are pre-wrapped to TEXT_WIDTH by tools/story.py, so this only has
;  to honour the control codes it is handed.
; ============================================================================

SECTION "text", ROM0

EnsureScriptBank::
    ld  a, [wScriptBank]
    call SetRomBank
    ret

; ----------------------------------------------------------------------------
; OpenBox -- unroll the dialogue frame downward, one row per frame.
; ----------------------------------------------------------------------------
OpenBox::
    ld  a, [wBoxOpen]
    and a
    ret nz
    ld  a, 1
    ld  [wBoxOpen], a

    ; MapAddr consumes b and c, so the row counter lives in WRAM rather than
    ; being juggled across three calls.
    xor a
    ld  [wBoxRow], a
.row:
    call WaitFrame
    call FxStep
    ld  a, [wBoxRow]
    add BOX_ROW
    ld  b, a
    ld  c, 0
    call MapAddr                ; hl = start of this map row

    ; Pick the three tiles that make up this row: left, middle, right.
    ld  a, [wBoxRow]
    and a
    jr  nz, .notTop
    ld  d, TILE_BOX_TL
    ld  e, TILE_BOX_T
    ld  b, TILE_BOX_TR
    jr  .emit
.notTop:
    cp  BOX_HEIGHT - 1
    jr  nz, .middle
    ld  d, TILE_BOX_BL
    ld  e, TILE_BOX_B
    ld  b, TILE_BOX_BR
    jr  .emit
.middle:
    ld  d, TILE_BOX_L
    ld  e, TILE_BLANK
    ld  b, TILE_BOX_R
.emit:
    ld  a, d
    ld  [hl+], a
    ld  a, SCRN_COLS - 2
.mid:
    ld  [hl], e
    inc hl
    dec a
    jr  nz, .mid
    ld  a, b
    ld  [hl], a

    ; Colour: the whole box sits on BG palette 7, the parchment.
    ld  a, [wIsCGB]
    and a
    jr  z, .noAttr
    ld  a, 1
    ld  [rVBK], a
    ld  a, [wBoxRow]
    add BOX_ROW
    ld  b, a
    ld  c, 0
    call MapAddr
    ld  a, SCRN_COLS
.attr:
    ld  [hl], 7
    inc hl
    dec a
    jr  nz, .attr
    xor a
    ld  [rVBK], a
.noAttr:

    ld  a, [wBoxRow]
    inc a
    ld  [wBoxRow], a
    cp  BOX_HEIGHT
    jr  c, .row

    call ResetTextCursor
    ret

ResetTextCursor::
    xor a
    ld  [wTextCol], a
    ld  [wTextLine], a
    ret

; ----------------------------------------------------------------------------
; CloseBox -- put the picture back underneath.
; ----------------------------------------------------------------------------
CloseBox::
    ld  a, [wBoxOpen]
    and a
    ret z
    xor a
    ld  [wBoxOpen], a

    ; FxStep clobbers c, so the row counter is kept in WRAM.
    xor a
    ld  [wBoxRow], a
.row:
    call WaitFrame
    call FxStep
    ld  a, [wBoxRow]
    ld  c, a
    call RestorePicRow
    ld  a, [wBoxRow]
    inc a
    ld  [wBoxRow], a
    cp  BOX_HEIGHT
    jr  c, .row
    call EnsureScriptBank
    ret

; RestorePicRow -- c = row within the box; repaint it from the loaded picture.
RestorePicRow:
    ld  a, [wHasPic]
    and a
    jr  nz, .fromPicture

    ; No picture loaded (title card): blank the row instead.
    ld  a, c
    add BOX_ROW
    ld  b, a
    ld  c, 1
    ld  a, TILE_BLANK
    call FillBgMapRows
    ret

.fromPicture:
    ld  a, [wPicBank]
    call SetRomBank
    ; hl = picture map + (BOX_ROW + c) * SCRN_COLS
    ld  a, [wPicDesc + 4]
    ld  l, a
    ld  a, [wPicDesc + 5]
    ld  h, a
    ld  a, c
    add BOX_ROW
    ld  b, a
    call AddRowOffset
    ; de = map address for that row
    push hl
    ld  a, c
    add BOX_ROW
    ld  b, a
    ld  c, 0
    call MapAddr
    ld  d, h
    ld  e, l
    pop hl
    push de
    ld  c, SCRN_COLS
    call MemCopySmall
    pop de

    ld  a, [wIsCGB]
    and a
    jr  z, .done
    ld  a, [wPicDesc + 6]
    ld  l, a
    ld  a, [wPicDesc + 7]
    ld  h, a
    or  l
    jr  z, .done
    ld  a, [wPicDesc + 6]
    ld  l, a
    ld  a, [wPicDesc + 7]
    ld  h, a
    ld  a, [wBoxRestoreRow]
    ld  b, a
    call AddRowOffset
    ld  a, 1
    ld  [rVBK], a
    ld  c, SCRN_COLS
    call MemCopySmall
    xor a
    ld  [rVBK], a
.done:
    ret

; AddRowOffset -- hl += b * SCRN_COLS, and remember b for the attribute pass.
AddRowOffset:
    ld  a, b
    ld  [wBoxRestoreRow], a
    ld  a, b
    and a
    ret z
    ld  de, SCRN_COLS
.loop:
    add hl, de
    dec b
    jr  nz, .loop
    ret

; ----------------------------------------------------------------------------
; PrintString -- hl = string in the script bank.  Opens the box if needed.
; ----------------------------------------------------------------------------
PrintString::
    ld  a, l
    ld  [wTextPtr], a
    ld  a, h
    ld  [wTextPtr + 1], a
    call OpenBox
    call ClearTextArea

.next:
    call EnsureScriptBank
    ld  a, [wTextPtr]
    ld  l, a
    ld  a, [wTextPtr + 1]
    ld  h, a
    ld  a, [hl+]
    ld  b, a
    ld  a, l
    ld  [wTextPtr], a
    ld  a, h
    ld  [wTextPtr + 1], a
    ld  a, b

    and a
    jr  z, .finish              ; TX_END
    cp  TX_LINE
    jr  z, .newline
    cp  TX_PAGE
    jr  z, .page
    cp  TX_PAUSE
    jr  z, .pause
    cp  TX_SPEED
    jr  z, .speed
    cp  TX_SHAKE
    jr  z, .shake
    cp  TX_SFX
    jr  z, .sfxCode

    call PutGlyph
    ld  a, [wTextSpeed]
    and a
    jr  z, .next
    ld  [wTextDelay], a
.delay:
    call WaitFrame
    call FxStep
    ; Holding B fast-forwards, the way every good text game lets you.
    ld  a, [wJoyHeld]
    and PADF_B
    jr  nz, .next
    ld  a, [wTextDelay]
    dec a
    ld  [wTextDelay], a
    jr  nz, .delay
    jr  .next

.newline:
    ld  a, [wTextLine]
    inc a
    ld  [wTextLine], a
    xor a
    ld  [wTextCol], a
    jr  .next

.page:
    call ShowMoreArrow
    call WaitButton
    call HideMoreArrow
    call ClearTextArea
    jr  .next

.pause:
    call FetchTextByte
    ld  b, a
    call WaitFrames
    jp  .next

.speed:
    call FetchTextByte
    ld  [wTextSpeed], a
    jp  .next

.shake:
    call FetchTextByte
    ld  [wShakeTimer], a
    jp  .next

.sfxCode:
    call FetchTextByte
    call PlaySfx
    jp  .next

.finish:
    call ShowMoreArrow
    call WaitButton
    call HideMoreArrow
    ret

; FetchTextByte -- read the next byte of the string and advance the pointer.
FetchTextByte:
    call EnsureScriptBank
    ld  a, [wTextPtr]
    ld  l, a
    ld  a, [wTextPtr + 1]
    ld  h, a
    ld  a, [hl+]
    ld  b, a
    ld  a, l
    ld  [wTextPtr], a
    ld  a, h
    ld  [wTextPtr + 1], a
    ld  a, b
    ret

; PutGlyph -- a = ASCII character; place it at the cursor and advance.
PutGlyph:
    sub FONT_FIRST_CHAR
    add TILE_FONT_BASE
    ld  d, a                    ; d = tile
    ld  a, [wTextLine]
    add TEXT_ROW
    ld  b, a
    ld  a, [wTextCol]
    add TEXT_COL
    ld  c, a
    push de
    call MapAddr
    pop de
    ld  [hl], d
    ld  a, [wTextCol]
    inc a
    ld  [wTextCol], a
    ret

; ClearTextArea -- wipe the three text lines, leaving the frame alone.
ClearTextArea::
    call WaitFrame
    ld  b, TEXT_ROW
    ld  c, TEXT_LINES
    ld  a, TILE_BLANK
    call FillBgMapRowsInset
    call ResetTextCursor
    ret

; FillBgMapRowsInset -- like FillBgMapRows but skips the frame columns.
; a = tile, b = first row, c = row count.  MapAddr eats b, hence the push.
FillBgMapRowsInset:
    ld  d, a
    ld  e, c
.row:
    push bc
    push de
    ld  c, TEXT_COL
    call MapAddr
    pop de
    ld  a, TEXT_WIDTH
.col:
    ld  [hl], d
    inc hl
    dec a
    jr  nz, .col
    pop bc
    inc b
    dec e
    jr  nz, .row
    ret

ShowMoreArrow::
    call WaitFrame
    ld  b, BOX_ROW + BOX_HEIGHT - 1
    ld  c, SCRN_COLS - 2
    call MapAddr
    ld  [hl], TILE_BOX_ARROW
    ret

HideMoreArrow::
    call WaitFrame
    ld  b, BOX_ROW + BOX_HEIGHT - 1
    ld  c, SCRN_COLS - 2
    call MapAddr
    ld  [hl], TILE_BOX_B
    ret

; ----------------------------------------------------------------------------
; PrintCentered -- hl = string; draw it centred on the map with no box.
; Used for chapter cards, where the words are the whole image.
; ----------------------------------------------------------------------------
PrintCentered::
    ld  a, l
    ld  [wTextPtr], a
    ld  a, h
    ld  [wTextPtr + 1], a
    ld  a, [wCardRow]
    ld  [wTextLine], a
.line:
    ; Measure this line so it can be centred.
    call EnsureScriptBank
    ld  a, [wTextPtr]
    ld  l, a
    ld  a, [wTextPtr + 1]
    ld  h, a
    ld  c, 0
.measure:
    ld  a, [hl+]
    and a
    jr  z, .haveLen
    cp  TX_LINE
    jr  z, .haveLen
    inc c
    jr  .measure
.haveLen:
    ld  a, SCRN_COLS
    sub c
    srl a
    ld  [wTextCol], a

    call WaitFrame
.emit:
    call FetchTextByte
    and a
    jr  z, .done
    cp  TX_LINE
    jr  z, .nextLine
    push af
    ld  a, [wTextLine]
    ld  b, a
    ld  a, [wTextCol]
    ld  c, a
    call MapAddr
    pop af
    sub FONT_FIRST_CHAR
    add TILE_FONT_BASE
    ld  [hl], a
    ld  a, [wTextCol]
    inc a
    ld  [wTextCol], a
    jr  .emit
.nextLine:
    ld  a, [wTextLine]
    inc a
    inc a
    ld  [wTextLine], a
    jr  .line
.done:
    ret

SECTION "text ram", WRAM0
wHasPic::         db
wBoxRestoreRow::  db
wCardRow::        db
wBoxRow::         db
wTextDelay::      db
