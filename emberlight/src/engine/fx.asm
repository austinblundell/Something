; ============================================================================
;  fx.asm  --  weather, embers, water shimmer, screen shake
;
;  FxStep runs once per frame from every wait loop in the engine, so effects
;  keep running while dialogue is on screen.  Particles live in shadow OAM;
;  the water shimmer is a per-scanline SCX table driven by the STAT interrupt,
;  which is what gives the reflections their wobble.
; ============================================================================

SECTION "fx", ROM0

; ----------------------------------------------------------------------------
; FxSet -- a = effect id.  Seeds the particle field and arms the interrupts.
; ----------------------------------------------------------------------------
FxSet::
    ld  [wFxMode], a
    xor a
    ld  [wWaterOn], a
    ld  a, [wFxMode]
    cp  FX_WATER
    jr  nz, .notWater
    ld  a, 1
    ld  [wWaterOn], a
    call BuildWaterTable
    ld  a, STATF_MODE00
    ld  [rSTAT], a
    ld  a, IEF_VBLANK | IEF_STAT
    ld  [rIE], a
    ret
.notWater:
    ld  a, IEF_VBLANK
    ld  [rIE], a
    ld  a, [wFxMode]
    and a
    jr  nz, .seed
    call ResetOam
    ret
.seed:
    ld  c, 0
.loop:
    call Rand
    and $7F
    add 8
    ld  hl, wPartX
    ld  b, 0
    add hl, bc
    ld  [hl], a
    call Rand
    and $7F
    add 16
    ld  hl, wPartY
    add hl, bc
    ld  [hl], a
    call Rand
    and 3
    inc a
    ld  hl, wPartV
    add hl, bc
    ld  [hl], a
    call Rand
    ld  hl, wPartT
    add hl, bc
    ld  [hl], a
    inc c
    ld  a, c
    cp  FX_PARTICLES
    jr  c, .loop
    ret

; ----------------------------------------------------------------------------
; FxStep -- one frame of every active effect.
; ----------------------------------------------------------------------------
FxStep::
    call ResetOam
    call ExploreDrawCursor
    ld  a, [wFxMode]
    and a
    jr  z, .noParticles
    cp  FX_WATER
    jr  z, .water
    call StepParticles
    jr  .shake
.water:
    ld  a, [wWaterPhase]
    inc a
    ld  [wWaterPhase], a
    call BuildWaterTable
    jr  .shake
.noParticles:
.shake:
    call StepShake
    call MusicStep
    ret

; ----------------------------------------------------------------------------
; StepParticles -- advance and emit the 16 particle sprites.
; ----------------------------------------------------------------------------
StepParticles:
    ld  c, 0
.loop:
    ; --- load this particle -----------------------------------------------
    ld  b, 0
    ld  hl, wPartX
    add hl, bc
    ld  d, [hl]                 ; d = x
    ld  hl, wPartY
    add hl, bc
    ld  e, [hl]                 ; e = y
    ld  hl, wPartV
    add hl, bc
    ld  a, [hl]
    ld  [wFxSpeed], a

    ld  a, [wFxMode]
    cp  FX_EMBERS
    jr  z, .embers
    cp  FX_SNOW
    jr  z, .snow
    cp  FX_GLINT
    jr  z, .glint

    ; --- rain --------------------------------------------------------------
    ld  a, [wFxMode]
    cp  FX_RAIN_HEAVY
    ld  a, [wFxSpeed]
    jr  nz, .rainSpeed
    add 3
.rainSpeed:
    add 3
    ld  b, a                    ; b = fall speed
    ld  a, e
    add b
    ld  e, a
    ld  a, d
    inc a
    inc a
    ld  d, a
    ld  a, e
    cp  152
    jr  c, .store
    call RecycleTop
    jr  .store

.embers:
    ; Sparks drift up and weave; they die near the top of the frame.
    ld  a, e
    sub 1
    ld  e, a
    ld  b, 0
    ld  hl, wPartT
    add hl, bc
    ld  a, [hl]
    inc a
    ld  [hl], a
    and 8
    jr  z, .emberLeft
    inc d
    jr  .emberDone
.emberLeft:
    dec d
.emberDone:
    ld  a, e
    cp  20
    jr  nc, .store
    call RecycleBottom
    jr  .store

.snow:
    ld  a, [wFxSpeed]
    srl a
    inc a
    ld  b, a
    ld  a, e
    add b
    ld  e, a
    ld  b, 0
    ld  hl, wPartT
    add hl, bc
    ld  a, [hl]
    inc a
    ld  [hl], a
    and 16
    jr  z, .snowLeft
    inc d
    jr  .snowDone
.snowLeft:
    dec d
.snowDone:
    ld  a, e
    cp  152
    jr  c, .store
    call RecycleTop
    jr  .store

.glint:
    ; Highlights sliding across open water, low in the frame.
    ld  a, d
    inc a
    ld  d, a
    cp  168
    jr  c, .store
    ld  d, 0
    call Rand
    and $1F
    add 108
    ld  e, a

.store:
    ld  b, 0
    ld  hl, wPartX
    add hl, bc
    ld  [hl], d
    ld  b, 0
    ld  hl, wPartY
    add hl, bc
    ld  [hl], e

    push bc
    call EmitParticle
    pop bc
    inc c
    ld  a, c
    cp  FX_PARTICLES
    jp  c, .loop
    ret

RecycleTop:
    call Rand
    and $9F                     ; keep it inside the visible width
    ld  d, a
    call Rand
    and 7
    ld  e, a
    ret

RecycleBottom:
    call Rand
    and $3F
    add 56
    ld  d, a
    call Rand
    and 15
    add 104
    ld  e, a
    ret

; EmitParticle -- c = index; reads position back out and pushes one sprite.
EmitParticle:
    ld  b, 0
    ld  hl, wPartX
    add hl, bc
    ld  a, [hl]
    ld  [wFxTmpX], a
    ld  hl, wPartY
    add hl, bc
    ld  a, [hl]
    ld  [wFxTmpY], a

    ld  e, 0                    ; object palette 0: cold highlights
    ld  a, [wFxMode]
    cp  FX_EMBERS
    ld  d, TILE_SPARK
    jr  nz, .notEmber
    ld  e, OAMF_PAL1            ; embers burn warm
    jr  .haveTile
.notEmber:
    cp  FX_SNOW
    ld  d, TILE_DOT
    jr  z, .haveTile
    cp  FX_GLINT
    ld  d, TILE_GLINT
    jr  z, .haveTile
    cp  FX_RAIN_HEAVY
    ld  d, TILE_RAIN_LONG
    jr  z, .haveTile
    ld  d, TILE_RAIN_SHORT
.haveTile:
    ld  a, [wFxTmpY]
    add 16                      ; OAM Y is offset by 16
    ld  b, a
    push de
    ld  a, [wFxTmpX]
    add 8                       ; OAM X is offset by 8
    ld  c, a
    pop de
    call OamPut
    ret

; ----------------------------------------------------------------------------
; StepShake -- rattle the whole background for a few frames.
; ----------------------------------------------------------------------------
StepShake:
    ld  a, [wShakeTimer]
    and a
    jr  z, .steady
    dec a
    ld  [wShakeTimer], a
    call Rand
    and 3
    ld  b, a
    ld  a, [wPanBase]
    add b
    dec a
    ld  [wSCXShadow], a
    call Rand
    and 1
    ld  [wSCYShadow], a
    ret
.steady:
    ld  a, [wPanBase]
    ld  [wSCXShadow], a
    xor a
    ld  [wSCYShadow], a
    ret

; ----------------------------------------------------------------------------
; BuildWaterTable -- one SCX value per scanline, sinusoidal below the horizon.
; ----------------------------------------------------------------------------
BuildWaterTable:
    ld  hl, wWaterTable
    ld  c, 0                    ; scanline
.line:
    ld  a, c
    ld  b, a
    ld  a, [wWaterHorizon]
    cp  b
    jr  z, .wobble
    jr  c, .wobble
    ; above the waterline: no displacement
    ld  a, [wPanBase]
    ld  [hl+], a
    jr  .next
.wobble:
    ; phase = (line >> 1) + wWaterPhase, wrapped to the 16-entry table
    ld  a, c
    srl a
    ld  b, a
    ld  a, [wWaterPhase]
    srl a
    add b
    and 15
    ld  de, WaterSine
    add e
    ld  e, a
    ld  a, d
    adc 0
    ld  d, a
    ld  a, [de]
    ld  b, a
    ld  a, [wPanBase]
    add b
    ld  [hl+], a
.next:
    inc c
    ld  a, c
    cp  154
    jr  c, .line
    ret

WaterSine:
    db 0, 1, 1, 2, 2, 2, 1, 1, 0, $FF, $FF, $FE, $FE, $FE, $FF, $FF

SECTION "fx ram", WRAM0
wFxSpeed::     db
wFxTmpX::      db
wFxTmpY::      db
wWaterHorizon::db
