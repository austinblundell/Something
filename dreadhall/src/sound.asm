; =============================================================================
;  sound.asm -- one-shot effects driven entirely by the hardware envelopes,
;  so nothing has to be serviced per frame.
; =============================================================================

SECTION "SoundCode", ROM0

SoundInit::
    ld a, $80
    ldh [rNR52], a             ; master enable
    ld a, $77
    ldh [rNR50], a             ; full volume, both outputs
    ld a, $FF
    ldh [rNR51], a             ; every channel to both outputs
    ret

; sharp noise crack
SfxShoot::
    xor a
    ldh [rNR41], a
    ld a, $F2                  ; volume 15, decaying
    ldh [rNR42], a
    ld a, $21
    ldh [rNR43], a
    ld a, $80
    ldh [rNR44], a
    ret

; dry click when out of ammo
SfxDry::
    xor a
    ldh [rNR41], a
    ld a, $51
    ldh [rNR42], a
    ld a, $55
    ldh [rNR43], a
    ld a, $80
    ldh [rNR44], a
    ret

; enemy takes a hit: short falling blip
SfxHit::
    ld a, $54                  ; sweep down
    ldh [rNR10], a
    ld a, $81
    ldh [rNR11], a
    ld a, $A3
    ldh [rNR12], a
    ld a, $00
    ldh [rNR13], a
    ld a, $87
    ldh [rNR14], a
    ret

; enemy dies: longer, lower
SfxKill::
    ld a, $76
    ldh [rNR10], a
    ld a, $40
    ldh [rNR11], a
    ld a, $C4
    ldh [rNR12], a
    ld a, $80
    ldh [rNR13], a
    ld a, $85
    ldh [rNR14], a
    ret

; player struck
SfxHurt::
    xor a
    ldh [rNR41], a
    ld a, $D4
    ldh [rNR42], a
    ld a, $67
    ldh [rNR43], a
    ld a, $80
    ldh [rNR44], a
    ret

; pickup chime
SfxPickup::
    ld a, $80
    ldh [rNR21], a
    ld a, $A4
    ldh [rNR22], a
    ld a, $C0
    ldh [rNR23], a
    ld a, $86
    ldh [rNR24], a
    ret
