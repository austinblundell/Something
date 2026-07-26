; =============================================================================
;  player.asm -- movement, collision and the weapon
; =============================================================================

SECTION "PlayerCode", ROM0

PlayerUpdate::
    ; ---- hurt flash decay ----
    ld a, [wHurtFlash]
    and a
    jr z, .noFlash
    dec a
    ld [wHurtFlash], a
    ld a, %11100100
    ld b, a
    ld a, [wHurtFlash]
    and 4
    jr z, :+
    ld b, %00011011            ; invert for one frame in two
:   ld a, b
    ldh [rBGP], a
    jr .flashDone
.noFlash:
    ld a, %11100100
    ldh [rBGP], a
.flashDone:

    ; ---- turning (ramps up while held so fine aiming stays possible) ----
    ld a, [wPad]
    and PADF_B
    jr nz, .noTurn             ; B converts left/right into strafing

    ld a, [wPad]
    and PADF_LEFT | PADF_RIGHT
    jr nz, .turning
    xor a
    ld [wTurnVel], a
    jr .noTurn
.turning:
    ld a, [wTurnVel]
    cp TURN_MAX
    jr nc, :+
    inc a
    ld [wTurnVel], a
:   ld b, a
    ld a, [wPad]
    and PADF_LEFT
    jr z, .turnRight
    ld a, [wPlayerAng]
    sub b
    ld [wPlayerAng], a
    jr .noTurn
.turnRight:
    ld a, [wPlayerAng]
    add b
    ld [wPlayerAng], a
.noTurn:

    ; ---- forward / back ----
    ld a, [wPad]
    and PADF_UP | PADF_DOWN
    jr z, .noWalk

    ld a, [wPlayerAng]
    call CosLookup             ; BC = dirX
    ld de, MOVE_SPEED
    call MulSigned
    ld a, l
    ld [wDX], a
    ld a, h
    ld [wDX + 1], a

    ld a, [wPlayerAng]
    call SinLookup             ; BC = dirY
    ld de, MOVE_SPEED
    call MulSigned
    ld a, l
    ld [wDY], a
    ld a, h
    ld [wDY + 1], a

    ld a, [wPad]
    and PADF_DOWN
    call nz, NegateDelta
    call MoveTry

    ; head bob drives the gun sprite, not the camera: scrolling the background
    ; would drag the status bar with it.
    ld a, [wBobPhase]
    inc a
    ld [wBobPhase], a
    jr .walkDone
.noWalk:
    ld a, [wBobPhase]
    and $F8
    ld [wBobPhase], a
.walkDone:

    ; ---- strafing (B + left/right) ----
    ld a, [wPad]
    and PADF_B
    jr z, .noStrafe
    ld a, [wPad]
    and PADF_LEFT | PADF_RIGHT
    jr z, .noStrafe

    ; right vector is the forward vector turned 90 degrees: (-sin, cos)
    ld a, [wPlayerAng]
    call SinLookup
    ld de, STRAFE_SPEED
    call MulSigned
    xor a                      ; negate: strafe X uses -sin
    sub l
    ld [wDX], a
    sbc a, a
    sub h
    ld [wDX + 1], a

    ld a, [wPlayerAng]
    call CosLookup
    ld de, STRAFE_SPEED
    call MulSigned
    ld a, l
    ld [wDY], a
    ld a, h
    ld [wDY + 1], a

    ld a, [wPad]
    and PADF_LEFT
    call nz, NegateDelta
    call MoveTry
.noStrafe:

    ; ---- reached the exit? ----
    ld a, [wPlayerX + 1]
    cp EXIT_X
    jr nz, .noExit
    ld a, [wPlayerY + 1]
    cp EXIT_Y
    jr nz, .noExit
    ld a, ST_WIN
    call EnterEnd
.noExit:
    ret

; -----------------------------------------------------------------------------
NegateDelta:
    ld a, [wDX]
    cpl
    ld c, a
    ld a, [wDX + 1]
    cpl
    ld b, a
    inc bc
    ld a, c
    ld [wDX], a
    ld a, b
    ld [wDX + 1], a
    ld a, [wDY]
    cpl
    ld c, a
    ld a, [wDY + 1]
    cpl
    ld b, a
    inc bc
    ld a, c
    ld [wDY], a
    ld a, b
    ld [wDY + 1], a
    ret

; -----------------------------------------------------------------------------
; MoveTry: applies wDX / wDY to the player one axis at a time so that running
; into a wall at an angle slides along it instead of stopping dead.
; -----------------------------------------------------------------------------
MoveTry::
    ; ---- X ----
    ld a, [wPlayerX]
    ld l, a
    ld a, [wPlayerX + 1]
    ld h, a
    ld a, [wDX]
    ld e, a
    ld a, [wDX + 1]
    ld d, a
    add hl, de
    ld a, l
    ld [wNewX], a
    ld a, h
    ld [wNewX + 1], a
    bit 7, d
    jr nz, .xn
    ld de, PLAYER_R
    jr .xp
.xn:
    ld de, -PLAYER_R
.xp:
    add hl, de
    ld c, h
    ld a, [wPlayerY + 1]
    ld b, a
    call MapAt
    and a
    jr nz, .noX
    ld a, [wNewX]
    ld [wPlayerX], a
    ld a, [wNewX + 1]
    ld [wPlayerX + 1], a
.noX:

    ; ---- Y ----
    ld a, [wPlayerY]
    ld l, a
    ld a, [wPlayerY + 1]
    ld h, a
    ld a, [wDY]
    ld e, a
    ld a, [wDY + 1]
    ld d, a
    add hl, de
    ld a, l
    ld [wNewY], a
    ld a, h
    ld [wNewY + 1], a
    bit 7, d
    jr nz, .yn
    ld de, PLAYER_R
    jr .yp
.yn:
    ld de, -PLAYER_R
.yp:
    add hl, de
    ld b, h
    ld a, [wPlayerX + 1]
    ld c, a
    call MapAt
    and a
    ret nz
    ld a, [wNewY]
    ld [wPlayerY], a
    ld a, [wNewY + 1]
    ld [wPlayerY + 1], a
    ret

; -----------------------------------------------------------------------------
; MapAt: B = cell Y, C = cell X -> A = map value. Clobbers HL, DE.
MapAt::
    ld a, b
    and 31
    ld l, a
    ld h, 0
    add hl, hl
    add hl, hl
    add hl, hl
    add hl, hl
    add hl, hl
    ld a, c
    and 31
    or l
    ld l, a
    ld de, LevelMap
    add hl, de
    ld a, [hl]
    ret

; =============================================================================
;  weapon
; =============================================================================
WeaponUpdate::
    ld a, [wGunState]
    and a
    jr z, .idle
    dec a
    ld [wGunState], a
    ret
.idle:
    ld a, [wPadNew]
    and PADF_A
    ret z
    ld a, [wAmmo]
    and a
    jr z, .dry
    dec a
    ld [wAmmo], a
    ld a, 10
    ld [wGunState], a
    call SfxShoot
    call HudBuild
    call FireHitscan
    ret
.dry:
    call SfxDry
    ret

; -----------------------------------------------------------------------------
; FireHitscan: the shot goes straight down the middle of the screen, so a hit is
; simply "is the crosshair inside this enemy's billboard, and is the billboard
; in front of the wall in that column".
; -----------------------------------------------------------------------------
FireHitscan:
    ld a, $FF
    ld [wHitBest], a
    ld a, $FF
    ld [wHitDistH], a

    ld c, 0
.loop:
    ld a, c
    ld b, a
    ld hl, wEsVis
    add l
    ld l, a
    jr nc, :+
    inc h
:   ld a, [hl]
    and a
    jr z, .next

    ; horizontal overlap with the crosshair at x = 80
    ld hl, wEsX
    ld a, b
    add l
    ld l, a
    jr nc, :+
    inc h
:   ld a, [hl]
    ld d, a                    ; screen centre X
    ld hl, wEsW
    ld a, b
    add l
    ld l, a
    jr nc, :+
    inc h
:   ld a, [hl]
    ld e, a                    ; half width

    ld a, d
    sub 80
    jr nc, :+
    cpl
    inc a
:   cp e
    jr nc, .next               ; crosshair outside the silhouette

    ; keep the nearest candidate
    ld hl, wEsZ + 1
    ld a, b
    add a
    add l
    ld l, a
    jr nc, :+
    inc h
:   ld a, [hl]
    ld hl, wHitDistH
    cp [hl]
    jr nc, .next
    ld [hl], a
    ld a, b
    ld [wHitBest], a

.next:
    inc c
    ld a, c
    ld hl, wEnemyCount
    cp [hl]
    jr c, .loop

    ld a, [wHitBest]
    cp $FF
    ret z
    call DamageEnemy
    ret

; =============================================================================
SECTION "PlayerVars", WRAM0
wDX::     dw
wDY::     dw
wNewX::   dw
wNewY::   dw
wHitBest::  db
wHitDistH:: db
