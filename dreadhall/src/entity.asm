; =============================================================================
;  entity.asm -- enemies, pickups, billboard projection and OAM assembly
; =============================================================================

; size class table: tile, columns, OAM rows, artwork height in px
SECTION "EntityCode", ROM0

EnemySizes:
    db E0_S0_TILE, E0_S0_COLS, 2, 32
    db E0_S1_TILE, E0_S1_COLS, 2, 24
    db E0_S2_TILE, E0_S2_COLS, 1, 16
    db E0_S3_TILE, E0_S3_COLS, 1, 8
EnemySizesHurt:
    db E1_S0_TILE, E1_S0_COLS, 2, 32
    db E1_S1_TILE, E1_S1_COLS, 1, 16

; -----------------------------------------------------------------------------
InitLevel::
    ld a, START_X
    ld [wPlayerX + 1], a
    ld a, START_Y
    ld [wPlayerY + 1], a
    ld a, $80                  ; stand in the middle of the cell
    ld [wPlayerX], a
    ld [wPlayerY], a
    ld a, START_ANG            ; face down the longest clear run from spawn
    ld [wPlayerAng], a
    xor a
    ld [wKills], a
    ld [wTurnVel], a
    ld [wGunState], a
    ld [wHurtFlash], a
    ld [wBobPhase], a
    ld a, MAX_HP
    ld [wPlayerHp], a
    ld a, START_AMMO
    ld [wAmmo], a

    ; ---- enemies ----
    ld hl, EnemySpawns
    ld de, wEnemies
    ld c, NUM_ENEMY
.espawn:
    ld a, $80
    ld [de], a
    inc de
    ld a, [hl+]                ; cell X
    ld [de], a
    inc de
    ld a, $80
    ld [de], a
    inc de
    ld a, [hl+]                ; cell Y
    ld [de], a
    inc de
    ld a, ENEMY_HP
    ld [de], a
    inc de
    ld a, EST_IDLE
    ld [de], a
    inc de
    xor a
    ld [de], a
    inc de
    ld [de], a
    inc de
    dec c
    jr nz, .espawn
    ld a, NUM_ENEMY
    ld [wEnemyCount], a
    ld [wEnemiesLeft], a

    ; ---- pickups ----
    ld hl, PickupSpawns
    ld de, wPickups
    ld c, NUM_PICKUP
.pspawn:
    ld a, [hl+]
    ld [de], a
    inc de
    ld a, [hl+]
    ld [de], a
    inc de
    ld a, [hl+]
    ld [de], a
    inc de
    ld a, 1
    ld [de], a
    inc de
    dec c
    jr nz, .pspawn
    ld a, NUM_PICKUP
    ld [wPickupCount], a
    ret

; -----------------------------------------------------------------------------
; A = index -> HL = &wEnemies[A]
EnemyPtr:
    ld l, a
    ld h, 0
    add hl, hl
    add hl, hl
    add hl, hl
    ld de, wEnemies
    add hl, de
    ret

LoadEntBase:
    ld a, [wEntBase]
    ld l, a
    ld a, [wEntBase + 1]
    ld h, a
    ret

; A = |A| for a signed byte
AbsA:
    bit 7, a
    ret z
    cpl
    inc a
    ret

; HL = |HL|
Abs16:
    bit 7, h
    ret z
    xor a
    sub l
    ld l, a
    sbc a, a
    sub h
    ld h, a
    ret

; =============================================================================
EnemiesUpdate::
    xor a
    ld [wEntIdx], a
.loop:
    ld a, [wEntIdx]
    ld hl, wEnemyCount
    cp [hl]
    ret nc

    ld a, [wEntIdx]
    call EnemyPtr
    ld a, l
    ld [wEntBase], a
    ld a, h
    ld [wEntBase + 1], a

    ld de, E_ST
    add hl, de
    ld a, [hl]
    cp EST_DEAD
    jr z, .next
    cp EST_DYING
    jr z, .timed
    cp EST_HURT
    jr z, .timed
    call EnemyThink
    jr .next

.timed:
    ld b, a                    ; remember which timed state we are in
    inc hl                     ; -> E_TM
    ld a, [hl]
    dec a
    ld [hl], a
    jr nz, .next
    dec hl
    ld a, b
    cp EST_DYING
    jr nz, .backToChase
    ld [hl], EST_DEAD
    jr .next
.backToChase:
    ld [hl], EST_CHASE

.next:
    ld a, [wEntIdx]
    inc a
    ld [wEntIdx], a
    jr .loop

; -----------------------------------------------------------------------------
EnemyThink:
    ; delta to the player
    call LoadEntBase
    ld a, [hl+]
    ld b, a
    ld a, [hl+]
    ld c, a                    ; BC = enemy X
    ld a, [hl+]
    ld d, a
    ld a, [hl]
    ld e, a                    ; DE = enemy Y

    ld a, [wPlayerX]
    sub b
    ld [wEDX], a
    ld a, [wPlayerX + 1]
    sbc c
    ld [wEDX + 1], a
    ld a, [wPlayerY]
    sub d
    ld [wEDY], a
    ld a, [wPlayerY + 1]
    sbc e
    ld [wEDY + 1], a

    ; give up on anything more than a dozen cells away
    ld a, [wEDX + 1]
    call AbsA
    ld b, a
    ld a, [wEDY + 1]
    call AbsA
    add b
    cp 13
    ret nc

    call LoadEntBase
    ld de, E_ST
    add hl, de
    ld a, [hl]
    cp EST_IDLE
    jr nz, :+
    ld [hl], EST_CHASE
:

    ; within swinging range on both axes?
    ld a, [wEDX]
    ld l, a
    ld a, [wEDX + 1]
    ld h, a
    call Abs16
    ld a, h
    and a
    jr nz, .chase
    ld a, l
    cp $C0
    jr nc, .chase
    ld a, [wEDY]
    ld l, a
    ld a, [wEDY + 1]
    ld h, a
    call Abs16
    ld a, h
    and a
    jr nz, .chase
    ld a, l
    cp $C0
    jr nc, .chase

    ; adjacent: attack on a cooldown
    call LoadEntBase
    ld de, E_TM
    add hl, de
    ld a, [hl]
    and a
    jr z, .swing
    dec a
    ld [hl], a
    ret
.swing:
    ld [hl], 45
    call HurtPlayer
    ret

.chase:
    ld a, [wEDX + 1]
    bit 7, a
    jr nz, .xneg
    or a
    jr nz, .xpos
    ld a, [wEDX]
    cp $30
    jr c, .xskip
.xpos:
    ld bc, ENEMY_SPEED
    jr .xmove
.xneg:
    ld bc, -ENEMY_SPEED
.xmove:
    call EnemyMoveX
.xskip:

    ld a, [wEDY + 1]
    bit 7, a
    jr nz, .yneg
    or a
    jr nz, .ypos
    ld a, [wEDY]
    cp $30
    ret c
.ypos:
    ld bc, ENEMY_SPEED
    jr .ymove
.yneg:
    ld bc, -ENEMY_SPEED
.ymove:
    jp EnemyMoveY

; -----------------------------------------------------------------------------
; BC = signed delta. Each axis is tested on its own so enemies slide along
; walls rather than sticking to corners.
EnemyMoveX:
    call LoadEntBase
    ld a, [hl+]
    ld e, a
    ld a, [hl]
    ld d, a
    ld h, d
    ld l, e
    add hl, bc
    ld a, l
    ld [wNewX], a
    ld a, h
    ld [wNewX + 1], a
    bit 7, b
    jr nz, .n
    ld de, PLAYER_R
    jr .p
.n:
    ld de, -PLAYER_R
.p:
    add hl, de
    ld c, h                    ; probe cell X
    call LoadEntBase
    inc hl
    inc hl
    inc hl
    ld a, [hl]
    ld b, a                    ; enemy cell Y
    call MapAt
    and a
    ret nz
    call LoadEntBase
    ld a, [wNewX]
    ld [hl+], a
    ld a, [wNewX + 1]
    ld [hl], a
    ret

EnemyMoveY:
    call LoadEntBase
    inc hl
    inc hl
    ld a, [hl+]
    ld e, a
    ld a, [hl]
    ld d, a
    ld h, d
    ld l, e
    add hl, bc
    ld a, l
    ld [wNewY], a
    ld a, h
    ld [wNewY + 1], a
    bit 7, b
    jr nz, .n
    ld de, PLAYER_R
    jr .p
.n:
    ld de, -PLAYER_R
.p:
    add hl, de
    ld b, h                    ; probe cell Y
    call LoadEntBase
    inc hl
    ld a, [hl]
    ld c, a                    ; enemy cell X
    call MapAt
    and a
    ret nz
    call LoadEntBase
    inc hl
    inc hl
    ld a, [wNewY]
    ld [hl+], a
    ld a, [wNewY + 1]
    ld [hl], a
    ret

; -----------------------------------------------------------------------------
HurtPlayer::
    ld a, [wPlayerHp]
    sub ENEMY_DMG
    jr nc, :+
    xor a
:   ld [wPlayerHp], a
    ld a, 14
    ld [wHurtFlash], a
    call SfxHurt
    call HudBuild
    ld a, [wPlayerHp]
    and a
    ret nz
    ld a, ST_DEAD
    jp EnterEnd

; -----------------------------------------------------------------------------
; DamageEnemy: A = enemy index
DamageEnemy::
    call EnemyPtr
    ld de, E_HP
    add hl, de
    ld a, [hl]
    sub GUN_DAMAGE
    ld [hl], a
    jr z, .kill
    jr c, .kill
    inc hl
    ld [hl], EST_HURT
    inc hl
    ld [hl], 8
    jp SfxHit
.kill:
    xor a
    ld [hl], a
    inc hl
    ld [hl], EST_DYING
    inc hl
    ld [hl], 50
    ld a, [wKills]
    inc a
    ld [wKills], a
    ld a, [wEnemiesLeft]
    and a
    jr z, :+
    dec a
    ld [wEnemiesLeft], a
:   call SfxKill
    jp HudBuild

; =============================================================================
PickupsUpdate::
    xor a
    ld [wEntIdx], a
.loop:
    ld a, [wEntIdx]
    ld hl, wPickupCount
    cp [hl]
    ret nc

    call PickupPtr
    push hl
    ld de, P_A
    add hl, de
    ld a, [hl]
    pop hl
    and a
    jr z, .next

    ld a, [hl+]
    ld b, a                    ; cell X
    ld a, [hl]
    ld c, a                    ; cell Y
    ld a, [wPlayerX + 1]
    cp b
    jr nz, .next
    ld a, [wPlayerY + 1]
    cp c
    jr nz, .next

    call PickupPtr
    ld de, P_K
    add hl, de
    ld a, [hl]
    inc hl
    ld [hl], 0                 ; consume
    and a
    jr nz, .med
    ld a, [wAmmo]
    add 20
    cp MAX_AMMO
    jr c, :+
    ld a, MAX_AMMO
:   ld [wAmmo], a
    jr .got
.med:
    ld a, [wPlayerHp]
    add 40
    cp MAX_HP
    jr c, :+
    ld a, MAX_HP
:   ld [wPlayerHp], a
.got:
    call SfxPickup
    call HudBuild

.next:
    ld a, [wEntIdx]
    inc a
    ld [wEntIdx], a
    jr .loop

; A = index -> HL = &wPickups[A]
PickupPtr:
    ld a, [wEntIdx]
    add a
    add a
    ld l, a
    ld h, 0
    ld de, wPickups
    add hl, de
    ret

; =============================================================================
;  billboard projection
; =============================================================================
; ProjectPoint: world position in wPtX / wPtY.
; Carry set = not visible. Otherwise wScrX (signed 16) holds the screen centre
; and wZIdx the distance table index.
; -----------------------------------------------------------------------------
ProjectPoint:
    ld a, [wPtX]
    ld b, a
    ld a, [wPtX + 1]
    ld c, a
    ld a, [wPlayerX]
    ld d, a
    ld a, [wPlayerX + 1]
    ld e, a
    ld a, b
    sub d
    ld [wRelX], a
    ld a, c
    sbc e
    ld [wRelX + 1], a

    ld a, [wPtY]
    ld b, a
    ld a, [wPtY + 1]
    ld c, a
    ld a, [wPlayerY]
    ld d, a
    ld a, [wPlayerY + 1]
    ld e, a
    ld a, b
    sub d
    ld [wRelY], a
    ld a, c
    sbc e
    ld [wRelY + 1], a

    ; camZ = relX*cos + relY*sin  (distance along the view direction)
    ld a, [wRelX]
    ld c, a
    ld a, [wRelX + 1]
    ld b, a
    ld a, [wPCos]
    ld e, a
    ld a, [wPCos + 1]
    ld d, a
    call MulSigned
    push hl
    ld a, [wRelY]
    ld c, a
    ld a, [wRelY + 1]
    ld b, a
    ld a, [wPSin]
    ld e, a
    ld a, [wPSin + 1]
    ld d, a
    call MulSigned
    pop de
    add hl, de
    ld a, l
    ld [wCamZ], a
    ld a, h
    ld [wCamZ + 1], a

    bit 7, h
    jp nz, .reject
    ld a, h
    and a
    jr nz, .zok
    ld a, l
    cp $30
    jp c, .reject
.zok:

    ; camX = relY*cos - relX*sin   (offset to the player's right)
    ld a, [wRelY]
    ld c, a
    ld a, [wRelY + 1]
    ld b, a
    ld a, [wPCos]
    ld e, a
    ld a, [wPCos + 1]
    ld d, a
    call MulSigned
    push hl
    ld a, [wRelX]
    ld c, a
    ld a, [wRelX + 1]
    ld b, a
    ld a, [wPSin]
    ld e, a
    ld a, [wPSin + 1]
    ld d, a
    call MulSigned
    ld b, h
    ld c, l
    pop hl
    ld a, l
    sub c
    ld l, a
    ld a, h
    sbc b
    ld h, a
    ld a, l
    ld [wCamX], a
    ld a, h
    ld [wCamX + 1], a

    ; |camX| < camZ keeps the sprite inside a 90 degree cone; it is also what
    ; bounds the projection multiply below.
    call Abs16
    ld a, [wCamZ]
    ld e, a
    ld a, [wCamZ + 1]
    ld d, a
    ld a, l
    sub e
    ld a, h
    sbc d
    jp nc, .reject

    ; distance index, 1/16 cell units clamped at 16 cells
    ld a, [wCamZ + 1]
    cp $10
    jr c, .near
    ld a, $FF
    jr .haveIdx
.near:
    ld a, [wCamZ]
    swap a
    and $0F
    ld e, a
    ld a, [wCamZ + 1]
    swap a
    and $F0
    or e
.haveIdx:
    ld [wZIdx], a

    ; t = camX / camZ, as (|camX| * recip) >> 8 split into a 16x8 product plus
    ; a fractional one so the whole 8.8 reciprocal is used.
    ld l, a
    ld h, 0
    add hl, hl
    ld de, RecipDist
    add hl, de
    ld a, [hl+]
    ld e, a
    ld d, [hl]

    ld a, [wCamX]
    ld c, a
    ld a, [wCamX + 1]
    ld b, a
    ld [wSignT], a
    bit 7, b
    jr z, .cxpos
    xor a
    sub c
    ld c, a
    sbc a, a
    sub b
    ld b, a
.cxpos:
    push de
    ld a, d
    call Mul16x8               ; |camX| * high(recip)
    pop de
    push hl
    ld a, e
    call MulFrac               ; (|camX| * low(recip)) >> 8
    pop de
    add hl, de

    ld a, [wSignT]
    bit 7, a
    jr z, .tpos
    xor a
    sub l
    ld l, a
    sbc a, a
    sub h
    ld h, a
.tpos:
    ld b, h
    ld c, l
    ld de, 139                 ; projection plane distance
    call MulSigned
    ld a, l
    add 80
    ld l, a
    ld a, h
    adc 0
    ld h, a
    ld a, l
    ld [wScrX], a
    ld a, h
    ld [wScrX + 1], a

    ; occlusion against the wall standing in that screen column
    bit 7, h
    ld a, 0
    jr nz, .haveCol
    ld a, h
    and a
    ld a, VIEW_COLS - 1
    jr nz, .haveCol
    ld a, l
    rrca
    rrca
    rrca
    and $1F
    cp VIEW_COLS
    jr c, .haveCol
    ld a, VIEW_COLS - 1
.haveCol:
    add a
    ld l, a
    ld h, 0
    ld de, wColDist
    add hl, de
    ld a, [hl+]
    ld e, a
    ld d, [hl]
    ld a, [wCamZ]
    ld c, a
    ld a, [wCamZ + 1]
    ld b, a
    ld a, e
    sub c
    ld a, d
    sbc b
    jr c, .reject
    and a                      ; clear carry: visible
    ret
.reject:
    scf
    ret

; A = multiplier, BC = value -> HL = A*BC (low 16 bits). Clobbers A, D.
Mul16x8:
    ld d, a
    ld hl, 0
    and a
    ret z
.loop:
    srl d
    jr nc, :+
    add hl, bc
:   sla c
    rl b
    ld a, d
    and a
    jr nz, .loop
    ret

; =============================================================================
;  OAM assembly
; =============================================================================
BuildOam::
    ; Sprites 0..15 are reserved for the weapon. On DMG, when more than ten
    ; sprites land on a scanline the PPU keeps the ones earliest in OAM, so the
    ; gun has to come first or a close enemy erases it.
    ld a, ENEMY_OAM_BASE
    ld [wOamPtr], a

    ld a, [wPlayerAng]
    call CosLookup
    ld a, c
    ld [wPCos], a
    ld a, b
    ld [wPCos + 1], a
    ld a, [wPlayerAng]
    call SinLookup
    ld a, c
    ld [wPSin], a
    ld a, b
    ld [wPSin + 1], a

    ; ---- enemies ----
    xor a
    ld [wEntIdx], a
.eloop:
    ld a, [wEntIdx]
    ld hl, wEnemyCount
    cp [hl]
    jp nc, .edone

    ld hl, wEsVis
    ld a, [wEntIdx]
    add l
    ld l, a
    jr nc, :+
    inc h
:   ld [hl], 0

    ld a, [wEntIdx]
    call EnemyPtr
    push hl
    ld de, E_ST
    add hl, de
    ld a, [hl]
    pop hl
    cp EST_DEAD
    jp z, .enext
    ld [wEntState], a

    ld a, [hl+]
    ld [wPtX], a
    ld a, [hl+]
    ld [wPtX + 1], a
    ld a, [hl+]
    ld [wPtY], a
    ld a, [hl]
    ld [wPtY + 1], a

    call ProjectPoint
    jp c, .enext

    ld a, HIGH(HeightTabs) + 9  ; centre column table: no fisheye correction
    ld h, a
    ld a, [wZIdx]
    ld l, a
    ld a, [hl]
    ld [wSprH2], a

    ld hl, EnemySizes
    ld de, 4
    ld a, [wEntState]
    cp EST_DYING
    jr nz, .alive
    ld hl, EnemySizesHurt
    ld a, [wSprH2]
    cp 14
    jr nc, .haveSize
    add hl, de
    jr .haveSize
.alive:
    ld a, [wSprH2]
    cp 14
    jr nc, .haveSize
    add hl, de
    cp 10
    jr nc, .haveSize
    add hl, de
    cp 6
    jr nc, .haveSize
    add hl, de
.haveSize:
    ld a, [hl+]
    ld [wSprTile], a
    ld a, [hl+]
    ld [wSprCols], a
    ld a, [hl+]
    ld [wSprRows], a
    ld a, [hl]
    ld [wSprArtH], a

    ; remember the silhouette so the hitscan can test against it
    ld a, [wSprCols]
    add a
    add a                      ; cols*4 = half width
    ld b, a
    ld hl, wEsW
    ld a, [wEntIdx]
    add l
    ld l, a
    jr nc, :+
    inc h
:   ld [hl], b
    ld hl, wEsX
    ld a, [wEntIdx]
    add l
    ld l, a
    jr nc, :+
    inc h
:   ld a, [wScrX + 1]
    and a
    ld a, [wScrX]
    jr z, :+
    ld a, $FF                  ; off to one side; never under the crosshair
:   ld [hl], a
    ld hl, wEsZ
    ld a, [wEntIdx]
    add a
    add l
    ld l, a
    jr nc, :+
    inc h
:   ld a, [wCamZ]
    ld [hl+], a
    ld a, [wCamZ + 1]
    ld [hl], a
    ld hl, wEsVis
    ld a, [wEntIdx]
    add l
    ld l, a
    jr nc, :+
    inc h
:   ld [hl], 1

    call EmitBillboard

.enext:
    ld a, [wEntIdx]
    inc a
    ld [wEntIdx], a
    jp .eloop
.edone:

    ; ---- pickups ----
    xor a
    ld [wEntIdx], a
.ploop:
    ld a, [wEntIdx]
    ld hl, wPickupCount
    cp [hl]
    jr nc, .pdone

    call PickupPtr
    push hl
    ld de, P_A
    add hl, de
    ld a, [hl]
    pop hl
    and a
    jr z, .pnext

    ld a, [hl+]
    ld [wPtX + 1], a
    ld a, [hl+]
    ld [wPtY + 1], a
    ld a, [hl]
    ld [wPickKind], a
    ld a, $80
    ld [wPtX], a
    ld [wPtY], a

    call ProjectPoint
    jr c, .pnext

    ld a, HIGH(HeightTabs) + 9
    ld h, a
    ld a, [wZIdx]
    ld l, a
    ld a, [hl]
    srl a                      ; a crate is about half a cell tall
    ld [wSprH2], a
    cp 4
    jr c, .pnext

    ld a, [wPickKind]
    and a
    ld a, O_PICKUP * 2
    jr z, :+
    ld a, O_MED * 2
:   ld [wSprTile], a
    ld a, 2
    ld [wSprCols], a
    ld a, 1
    ld [wSprRows], a
    ld a, 16
    ld [wSprArtH], a
    call EmitBillboard

.pnext:
    ld a, [wEntIdx]
    inc a
    ld [wEntIdx], a
    jr .ploop
.pdone:
    ld a, [wOamPtr]
    ld b, a
    ld c, 40
    call ClearOamRange
    ret

; -----------------------------------------------------------------------------
; EmitBillboard: lays out wSprCols x wSprRows 8x16 sprites with the artwork's
; feet on the floor line for its distance.
; -----------------------------------------------------------------------------
EmitBillboard:
    ; top = HORIZON + h2 - artH
    ld a, [wSprH2]
    add HORIZON
    ld b, a
    ld a, [wSprArtH]
    ld c, a
    ld a, b
    sub c
    ld [wSprTop], a

    ; left = scrX - cols*4  (16 bit: scrX can legitimately be off screen)
    ld a, [wSprCols]
    add a
    add a
    ld c, a
    ld b, 0
    ld a, [wScrX]
    ld l, a
    ld a, [wScrX + 1]
    ld h, a
    ld a, l
    sub c
    ld l, a
    ld a, h
    sbc b
    ld h, a
    ld a, l
    ld [wSprLeft], a
    ld a, h
    ld [wSprLeft + 1], a

    xor a
    ld [wSprCol], a
.colLoop:
    ld a, [wSprCol]
    ld hl, wSprCols
    cp [hl]
    ret nc

    ; px = left + col*8
    ld a, [wSprCol]
    add a
    add a
    add a
    ld c, a
    ld b, 0
    ld a, [wSprLeft]
    ld l, a
    ld a, [wSprLeft + 1]
    ld h, a
    add hl, bc
    ; visible only when -8 < px < 160
    bit 7, h
    jr nz, .colNext            ; fully to the left
    ld a, h
    and a
    jr nz, .colNext            ; fully to the right
    ld a, l
    cp 160
    jr nc, .colNext
    ld a, l
    add 8                      ; OAM X origin
    ld [wSprX], a

    xor a
    ld [wSprRow], a
.rowLoop:
    ld a, [wSprRow]
    ld hl, wSprRows
    cp [hl]
    jr nc, .colNext

    ; y = top + row*16 + 16
    ld a, [wSprRow]
    swap a
    ld b, a
    ld a, [wSprTop]
    add b
    add 16
    ld [wSprY], a

    ; tile = base + (col*rows + row)*2
    ld a, [wSprCol]
    ld b, a
    ld a, [wSprRows]
    ld c, a
    xor a
.tmul:
    dec b
    bit 7, b
    jr nz, .tmulDone
    add c
    jr .tmul
.tmulDone:
    ld hl, wSprRow
    add [hl]
    add a
    ld hl, wSprTile
    add [hl]
    ld d, a

    ld a, [wSprY]
    ld b, a
    ld a, [wSprX]
    ld c, a
    ld e, 0
    call AddSprite

    ld a, [wSprRow]
    inc a
    ld [wSprRow], a
    jr .rowLoop

.colNext:
    ld a, [wSprCol]
    inc a
    ld [wSprCol], a
    jp .colLoop

; -----------------------------------------------------------------------------
; AddSprite: B = y, C = x, D = tile, E = attributes
AddSprite::
    ld a, [wOamPtr]
    cp 40
    ret nc
    push af
    add a
    add a
    ld l, a
    ld h, HIGH(wShadowOam)
    ld a, b
    ld [hl+], a
    ld a, c
    ld [hl+], a
    ld a, d
    ld [hl+], a
    ld a, e
    ld [hl], a
    pop af
    inc a
    ld [wOamPtr], a
    ret

; -----------------------------------------------------------------------------
BuildGunOam::
    xor a
    ld [wOamPtr], a
    ; walking sway: applied to the weapon rather than the scroll registers,
    ; which would drag the status bar around with it
    ld a, [wBobPhase]
    and $18
    swap a
    and 3
    ld [wBobY], a

    ld a, [wGunState]
    and a
    ld b, 0
    jr z, :+
    ld b, 5                    ; recoil kick
:   ld a, b
    ld [wGunRecoil], a

    ; crosshair -- OBP1 ($10) maps colour 1 to white for the rim
    ld b, 52 + 16
    ld c, 76 + 8
    ld d, O_CROSS * 2
    ld e, $10
    call AddSprite

    ; muzzle flash during the first frames of the shot
    ld a, [wGunState]
    cp 6
    jr c, .noFlash
    xor a
    ld [wSprCol], a
.flashCol:
    ld a, [wSprCol]
    cp FLASH_COLS
    jr nc, .noFlash
    add a
    add a
    add a
    add 68 + 8
    ld c, a
    ld b, 48 + 16              ; just above the muzzle
    ld a, [wSprCol]
    add a
    add O_FLASH * 2
    ld d, a
    ld e, $10
    call AddSprite
    ld a, [wSprCol]
    inc a
    ld [wSprCol], a
    jr .flashCol
.noFlash:

    ; the weapon: GUN_COLS x GUN_ROWS 8x16 sprites
    xor a
    ld [wSprCol], a
.gcol:
    ld a, [wSprCol]
    cp GUN_COLS
    jr nc, .gdone
    xor a
    ld [wSprRow], a
.grow:
    ld a, [wSprRow]
    cp GUN_ROWS
    jr nc, .gnext

    ; tile first: the index maths needs B as scratch, and B holds Y below
    ld a, [wSprCol]
    ld b, a
    add a
    add b                      ; col * 3
    add a                      ; col * GUN_ROWS * 2
    ld b, a
    ld a, [wSprRow]
    add a
    add b
    add O_GUN * 2
    ld [wSprTile], a

    ld a, [wSprCol]
    add a
    add a
    add a
    add 56 + 8
    ld c, a                    ; OAM X

    ld a, [wSprRow]
    swap a
    ld b, a
    ld a, (VIEW_H - 48) + 16   ; sit the artwork on the bottom of the viewport
    add b
    ld b, a
    ld a, [wGunRecoil]
    add b
    ld b, a
    ld a, [wBobY]
    add b
    ld b, a                    ; OAM Y

    ld a, [wSprTile]
    ld d, a
    ld e, $10
    call AddSprite

    ld a, [wSprRow]
    inc a
    ld [wSprRow], a
    jr .grow
.gnext:
    ld a, [wSprCol]
    inc a
    ld [wSprCol], a
    jr .gcol
.gdone:

    ; blank any unused weapon slots
    ld a, [wOamPtr]
    ld b, a
    ld c, ENEMY_OAM_BASE
    ; fall through

; ClearOamRange: B = first sprite index, C = one past the last
ClearOamRange::
    ld a, b
    cp c
    ret nc
    add a
    add a
    ld l, a
    ld h, HIGH(wShadowOam)
    ld a, c
    add a
    add a
    ld e, a
.loop:
    xor a
    ld [hl+], a
    inc l
    inc l
    inc l
    ld a, l
    cp e
    jr c, .loop
    ret

; =============================================================================
SECTION "EntityVars", WRAM0
wEntIdx::   db
wEntBase::  dw
wEntState:: db
wEDX::      dw
wEDY::      dw
wPtX::      dw
wPtY::      dw
wRelX::     dw
wRelY::     dw
wCamX::     dw
wCamZ::     dw
wPCos::     dw
wPSin::     dw
wZIdx::     db
wScrX::     dw
wSignT::    db
wSprTile::  db
wSprCols::  db
wSprRows::  db
wSprArtH::  db
wSprH2::    db
wSprTop::   db
wSprLeft::  dw
wSprX::     db
wSprY::     db
wSprCol::   db
wSprRow::   db
wPickKind:: db
wBobY::     db
wEsVis::    ds MAX_ENEMIES
wEsX::      ds MAX_ENEMIES
wEsW::      ds MAX_ENEMIES
wEsZ::      ds MAX_ENEMIES * 2
