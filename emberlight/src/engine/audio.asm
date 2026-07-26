; ============================================================================
;  audio.asm  --  a small two-channel sequencer plus one-shot effects
;
;  Tracks are byte streams: [note, length] pairs, note 0 = rest, $FF = loop.
;  MusicStep is called once a frame from the wait loops, so music keeps
;  playing under dialogue and fades.
; ============================================================================

DEF NOTE_REST   EQU 0
DEF TRACK_LOOP  EQU $FF

SECTION "audio", ROM0

AudioInit::
    ld  a, $80
    ld  [rNR52], a              ; master enable
    ld  a, $77
    ld  [rNR50], a              ; full volume both sides
    ld  a, $FF
    ld  [rNR51], a              ; everything to both ears
    xor a
    ld  [wMusicId], a
    ld  [wMusicTimer], a
    ld  [wMusicTimer2], a
    ret

AudioStop::
    xor a
    ld  [wMusicId], a
    ld  [rNR12], a
    ld  [rNR22], a
    ld  a, $80
    ld  [rNR14], a
    ld  [rNR24], a
    ret

; ----------------------------------------------------------------------------
; PlayMusic -- a = track id (1..N), 0 stops.
; ----------------------------------------------------------------------------
PlayMusic::
    and a
    jr  nz, .start
    call AudioStop
    ret
.start:
    ld  b, a
    ld  a, [wMusicId]
    cp  b
    ret z                       ; already playing
    ld  a, b
    ld  [wMusicId], a
    dec a
    add a                       ; index a table of two pointers per track
    add a
    ld  hl, MusicTable
    add l
    ld  l, a
    ld  a, h
    adc 0
    ld  h, a
    ld  a, [hl+]
    ld  [wMusicPtr], a
    ld  a, [hl+]
    ld  [wMusicPtr + 1], a
    ld  a, [hl+]
    ld  [wMusicPtr2], a
    ld  a, [hl]
    ld  [wMusicPtr2 + 1], a
    ld  a, l
    ld  [wMusicHome], a         ; remember where to loop back to
    ld  a, h
    ld  [wMusicHome + 1], a
    xor a
    ld  [wMusicTimer], a
    ld  [wMusicTimer2], a
    ret

; ----------------------------------------------------------------------------
; MusicStep -- one frame of both voices.
; ----------------------------------------------------------------------------
MusicStep::
    ld  a, [wMusicId]
    and a
    ret z

    ; --- voice 1: the melody, on the first pulse channel -------------------
    ld  a, [wMusicTimer]
    and a
    jr  z, .advance1
    dec a
    ld  [wMusicTimer], a
    jr  .voice2
.advance1:
    ld  a, [wMusicPtr]
    ld  l, a
    ld  a, [wMusicPtr + 1]
    ld  h, a
    ld  a, [hl]
    cp  TRACK_LOOP
    jr  nz, .note1
    call MusicRewind1
    ld  a, [wMusicPtr]
    ld  l, a
    ld  a, [wMusicPtr + 1]
    ld  h, a
    ld  a, [hl]
.note1:
    inc hl
    ld  b, a                    ; note index
    ld  a, [hl+]
    ld  [wMusicTimer], a        ; length in frames
    ld  a, l
    ld  [wMusicPtr], a
    ld  a, h
    ld  [wMusicPtr + 1], a
    ld  a, b
    and a
    jr  z, .voice2              ; rest: let the previous note ring out
    call Ch1Note

.voice2:
    ld  a, [wMusicTimer2]
    and a
    jr  z, .advance2
    dec a
    ld  [wMusicTimer2], a
    ret
.advance2:
    ld  a, [wMusicPtr2]
    ld  l, a
    ld  a, [wMusicPtr2 + 1]
    ld  h, a
    ld  a, [hl]
    cp  TRACK_LOOP
    jr  nz, .note2
    call MusicRewind2
    ld  a, [wMusicPtr2]
    ld  l, a
    ld  a, [wMusicPtr2 + 1]
    ld  h, a
    ld  a, [hl]
.note2:
    inc hl
    ld  b, a
    ld  a, [hl+]
    ld  [wMusicTimer2], a
    ld  a, l
    ld  [wMusicPtr2], a
    ld  a, h
    ld  [wMusicPtr2 + 1], a
    ld  a, b
    and a
    ret z
    call Ch2Note
    ret

MusicRewind1:
    ld  a, [wMusicHome]
    ld  l, a
    ld  a, [wMusicHome + 1]
    ld  h, a
    dec hl
    dec hl
    dec hl                      ; back to the start of this track's entry
    ld  a, [hl+]
    ld  [wMusicPtr], a
    ld  a, [hl]
    ld  [wMusicPtr + 1], a
    ret

MusicRewind2:
    ld  a, [wMusicHome]
    ld  l, a
    ld  a, [wMusicHome + 1]
    ld  h, a
    dec hl
    ld  a, [hl+]
    ld  [wMusicPtr2], a
    ld  a, [hl]
    ld  [wMusicPtr2 + 1], a
    ret

; Ch1Note / Ch2Note -- b = note index into NoteTable.
Ch1Note:
    call NotePeriod
    ld  a, $80                  ; 50% duty
    ld  [rNR11], a
    ld  a, $71                  ; soft attack, slow decay -- a bell, not a beep
    ld  [rNR12], a
    ld  a, e
    ld  [rNR13], a
    ld  a, d
    or  $80                     ; trigger
    ld  [rNR14], a
    ret

Ch2Note:
    call NotePeriod
    ld  a, $40                  ; 25% duty, thinner: this is the under-voice
    ld  [rNR21], a
    ld  a, $52
    ld  [rNR22], a
    ld  a, e
    ld  [rNR23], a
    ld  a, d
    or  $80
    ld  [rNR24], a
    ret

; NotePeriod -- b = note index -> de = 11-bit period, d already frequency-high.
NotePeriod:
    ld  hl, NoteTable
    ld  a, b
    dec a
    add a
    add l
    ld  l, a
    ld  a, h
    adc 0
    ld  h, a
    ld  a, [hl+]
    ld  e, a
    ld  a, [hl]
    and 7
    ld  d, a
    ret

; ----------------------------------------------------------------------------
; PlaySfx -- a = effect id.
; ----------------------------------------------------------------------------
PlaySfx::
    and a
    ret z
    cp  SFX_BLIP
    jr  z, .blip
    cp  SFX_THUNDER
    jr  z, .thunder
    cp  SFX_CHIME
    jr  z, .chime
    cp  SFX_WAVE
    jr  z, .wave
    ret

.blip:
    ld  a, $80
    ld  [rNR41], a
    ld  a, $51
    ld  [rNR42], a
    ld  a, $55
    ld  [rNR43], a
    ld  a, $80
    ld  [rNR44], a
    ret

.thunder:
    ld  a, $00
    ld  [rNR41], a
    ld  a, $F4                  ; loud, long decay
    ld  [rNR42], a
    ld  a, $7F                  ; lowest, roughest noise
    ld  [rNR43], a
    ld  a, $80
    ld  [rNR44], a
    ret

.chime:
    ld  b, 49                   ; C6
    call Ch1Note
    ret

.wave:
    ld  a, $20
    ld  [rNR41], a
    ld  a, $63
    ld  [rNR42], a
    ld  a, $6E
    ld  [rNR43], a
    ld  a, $C0
    ld  [rNR44], a
    ret

; ----------------------------------------------------------------------------
;  music data
;
;  Two slow voices in D natural minor.  The melody hangs on unresolved
;  intervals and the under-voice moves half as often, which is what makes it
;  sound like weather rather than a tune.
; ----------------------------------------------------------------------------
; Note indices: 1 = C3, chromatic upward.  Handy names for the notes used.
DEF D4  EQU 15
DEF E4  EQU 17
DEF F4  EQU 18
DEF G4  EQU 20
DEF A4  EQU 22
DEF AS4 EQU 23
DEF C5  EQU 25
DEF D5  EQU 27
DEF E5  EQU 29
DEF F5  EQU 30
DEF G5  EQU 32
DEF A5  EQU 34
DEF D3  EQU 3
DEF F3  EQU 6
DEF G3  EQU 8
DEF A3  EQU 10
DEF AS3 EQU 11
DEF C4  EQU 13

MusicTable:
    dw MusA1, MusA2             ; 1 -- the tower at night
    dw MusB1, MusB2             ; 2 -- the storm
    dw MusC1, MusC2             ; 3 -- memory / dawn

; --- 1: the tower at night ---------------------------------------------------
MusA1:
    db D5, 40, F5, 40, A5, 60, G5, 40
    db F5, 40, E5, 60, D5, 80
    db NOTE_REST, 30
    db C5, 40, D5, 40, F5, 60, E5, 40
    db D5, 60, A4, 90
    db NOTE_REST, 40
    db TRACK_LOOP
MusA2:
    db D3, 120, A3, 120
    db F3, 120, C4, 120
    db G3, 120, D3, 120
    db A3, 120, A3, 120
    db TRACK_LOOP

; --- 2: the storm -----------------------------------------------------------
MusB1:
    db D5, 20, D5, 20, E5, 20, F5, 20
    db D5, 20, D5, 20, C5, 20, D5, 20
    db AS4, 20, AS4, 20, C5, 20, D5, 20
    db A4, 30, A4, 30, G4, 40
    db TRACK_LOOP
MusB2:
    db D3, 40, D3, 40, AS3, 40, AS3, 40
    db G3, 40, G3, 40, A3, 40, A3, 40
    db TRACK_LOOP

; --- 3: memory / dawn -------------------------------------------------------
MusC1:
    db A4, 60, C5, 60, D5, 90, C5, 50
    db A4, 60, G4, 90
    db F4, 60, G4, 60, A4, 120
    db NOTE_REST, 50
    db TRACK_LOOP
MusC2:
    db F3, 150, C4, 150
    db D3, 150, A3, 150
    db TRACK_LOOP

; Standard Game Boy note periods, C3 upward.
NoteTable:
    dw   44, 156, 262, 363, 457, 547, 631, 710, 785, 856, 923, 986
    dw 1046,1102,1155,1205,1253,1297,1339,1379,1417,1452,1486,1517
    dw 1546,1575,1602,1627,1650,1673,1694,1714,1732,1750,1767,1783
    dw 1798,1812,1825,1837,1849,1860,1871,1881,1890,1899,1907,1915
    dw 1923,1930,1936,1943,1949,1954,1959,1964,1969,1974,1978,1982

SECTION "audio ram", WRAM0
wMusicPtr2::   dw
wMusicTimer2:: db
wMusicHome::   dw
