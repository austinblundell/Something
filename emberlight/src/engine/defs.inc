; ============================================================================
;  defs.inc  --  engine-wide constants and the WRAM map
; ============================================================================

IF !DEF(EMBER_DEFS_INC)
DEF EMBER_DEFS_INC EQU 1

; ---------------------------------------------------------------- VRAM plan
; The background layer can only address 256 tiles at once ($8000 mode), and
; the font plus effect sprites have to stay resident, so a full-screen picture
; gets everything below TILE_FONT_BASE.
DEF TILE_ART_BASE     EQU 0
DEF TILE_ART_MAX      EQU 176
DEF TILE_FONT_BASE    EQU 176     ; ASCII 32..95 -> 176..239
DEF TILE_SPRITE_BASE  EQU 240     ; 240..255

DEF FONT_FIRST_CHAR   EQU 32
DEF TILE_BLANK        EQU TILE_FONT_BASE      ; the space glyph, all paper

; Dialogue-box chrome lives in glyph slots the script never uses.
DEF TILE_BOX_TL       EQU TILE_FONT_BASE + ('#' - 32)
DEF TILE_BOX_T        EQU TILE_FONT_BASE + ('$' - 32)
DEF TILE_BOX_TR       EQU TILE_FONT_BASE + ('%' - 32)
DEF TILE_BOX_L        EQU TILE_FONT_BASE + ('&' - 32)
DEF TILE_BOX_R        EQU TILE_FONT_BASE + ('(' - 32)
DEF TILE_BOX_BL       EQU TILE_FONT_BASE + (')' - 32)
DEF TILE_BOX_B        EQU TILE_FONT_BASE + ('*' - 32)
DEF TILE_BOX_BR       EQU TILE_FONT_BASE + ('+' - 32)
DEF TILE_BOX_ARROW    EQU TILE_FONT_BASE + ('/' - 32)
DEF TILE_BOX_CURSOR   EQU TILE_FONT_BASE + (';' - 32)
DEF TILE_GAUGE_OFF    EQU TILE_FONT_BASE + ('<' - 32)
DEF TILE_GAUGE_ON     EQU TILE_FONT_BASE + ('=' - 32)

; Effect sprites.
DEF TILE_RAIN_LONG    EQU TILE_SPRITE_BASE + 0
DEF TILE_RAIN_SHORT   EQU TILE_SPRITE_BASE + 1
DEF TILE_SPARK        EQU TILE_SPRITE_BASE + 2
DEF TILE_DOT          EQU TILE_SPRITE_BASE + 3
DEF TILE_RETICLE_TL   EQU TILE_SPRITE_BASE + 4
DEF TILE_RETICLE_TR   EQU TILE_SPRITE_BASE + 5
DEF TILE_RETICLE_BL   EQU TILE_SPRITE_BASE + 6
DEF TILE_RETICLE_BR   EQU TILE_SPRITE_BASE + 7
DEF TILE_GLINT        EQU TILE_SPRITE_BASE + 8

; ------------------------------------------------------------------- layout
DEF SCRN_COLS         EQU 20
DEF SCRN_ROWS         EQU 18
DEF MAP_STRIDE        EQU 32

; Dialogue box: five rows at the bottom, three of them text.
DEF BOX_ROW           EQU 13
DEF BOX_HEIGHT        EQU 5
DEF TEXT_ROW          EQU BOX_ROW + 1
DEF TEXT_COL          EQU 1
DEF TEXT_WIDTH        EQU 18
DEF TEXT_LINES        EQU 3

; ------------------------------------------------------------- text control
DEF TX_END            EQU $00    ; end of string
DEF TX_LINE           EQU $01    ; next line
DEF TX_PAGE           EQU $02    ; wait for A, then clear and continue
DEF TX_PAUSE          EQU $03    ; db frames
DEF TX_SPEED          EQU $04    ; db frames-per-character
DEF TX_SHAKE          EQU $05    ; db frames -- rattle the screen mid-line
DEF TX_SFX            EQU $06    ; db id

; --------------------------------------------------------------- VM opcodes
DEF OP_END            EQU $00
DEF OP_PIC            EQU $01    ; db bank : dw descriptor
DEF OP_FADEIN         EQU $02    ; db speed
DEF OP_FADEOUT        EQU $03    ; db speed
DEF OP_TEXT           EQU $04    ; dw string
DEF OP_BOXCLOSE       EQU $05
DEF OP_WAIT           EQU $06    ; db frames
DEF OP_WAITKEY        EQU $07
DEF OP_FX             EQU $08    ; db effect id
DEF OP_SHAKE          EQU $09    ; db frames
DEF OP_FLASH          EQU $0A    ; db count
DEF OP_SFX            EQU $0B    ; db id
DEF OP_MUSIC          EQU $0C    ; db id
DEF OP_CHOICE         EQU $0D    ; dw prompt : dw optA : dw optB
DEF OP_JUMPIF         EQU $0E    ; db var : db value : dw target
DEF OP_JUMP           EQU $0F    ; dw target
DEF OP_SETVAR         EQU $10    ; db var : db value
DEF OP_TITLE          EQU $11
DEF OP_CARD           EQU $12    ; dw string -- centred title card on black
DEF OP_EXPLORE        EQU $13    ; dw hotspot table
DEF OP_PAN            EQU $14    ; db dx : db frames
DEF OP_TEXTSPEED      EQU $15    ; db frames-per-character
DEF OP_BEAT           EQU $16    ; db frames -- silent hold, no box
DEF OP_TENDFLAME      EQU $17    ; the ember mini-sequence
DEF OP_CREDITS        EQU $18    ; dw string -- slow scrolling roll

; ------------------------------------------------------------------ effects
DEF FX_NONE           EQU 0
DEF FX_RAIN           EQU 1
DEF FX_RAIN_HEAVY     EQU 2
DEF FX_EMBERS         EQU 3
DEF FX_WATER          EQU 4      ; per-scanline shimmer below the horizon
DEF FX_GLINT          EQU 5      ; drifting highlights on open water
DEF FX_SNOW           EQU 6

; -------------------------------------------------------------------- audio
DEF SFX_BLIP          EQU 1
DEF SFX_THUNDER       EQU 2
DEF SFX_CHIME         EQU 3
DEF SFX_WAVE          EQU 4

DEF MUS_NIGHT         EQU 1
DEF MUS_STORM         EQU 2
DEF MUS_MEMORY        EQU 3

; ------------------------------------------------------------------ globals
DEF VAR_CHOICE        EQU 0      ; what the keeper decided at the signal
DEF VAR_OIL           EQU 1
DEF VAR_LOG           EQU 2
DEF VAR_COUNT         EQU 8

DEF FADE_MAX          EQU 4      ; 0 = black, 4 = full brightness

; ============================================================================
;  WRAM
; ============================================================================
SECTION "shadow oam", WRAM0, ALIGN[8]
wShadowOAM::          ds 160

SECTION "engine ram", WRAM0

wVBlankDone::         db
wFrameCounter::       db
wIsCGB::              db

wJoyHeld::            db
wJoyPressed::         db
wJoyPrev::            db

wSCXShadow::          db
wSCYShadow::          db
wLCDCShadow::         db
wBGPShadow::          db
wOBP0Shadow::         db
wOBP1Shadow::         db

wPicBGP::             db         ; the current picture's un-faded DMG palette
wPicOBP::             db
wFadeLevel::          db         ; 0..FADE_MAX

wPalDirty::           db
wPalCount::           db         ; how many BG palettes the picture defines
wBGPalBase::          ds 8 * 8   ; target colours, straight from the picture
wBGPalShadow::        ds 8 * 8   ; after fading -- what VBlank pushes
wOBPalBase::          ds 8 * 8
wOBPalShadow::        ds 8 * 8

; A small deferred-write queue so text and animated tiles can be prepared
; anywhere and land in VRAM during VBlank.
DEF VQ_MAX            EQU 24
wVqCount::            db
wVqDest::             ds VQ_MAX * 2
wVqValue::            ds VQ_MAX

wOamNext::            db         ; next free shadow-OAM slot this frame

; --- text ---
wTextPtr::            dw
wTextBank::           db
wTextCol::            db
wTextLine::           db
wTextSpeed::          db
wBoxOpen::            db

; --- effects ---
wFxMode::             db
wFxTimer::            db
wWaterOn::            db
wWaterPhase::         db
wWaterTable::         ds 160     ; one SCX value per scanline
DEF FX_PARTICLES      EQU 16
wPartX::              ds FX_PARTICLES
wPartY::              ds FX_PARTICLES
wPartV::              ds FX_PARTICLES
wPartT::              ds FX_PARTICLES

; --- shake / pan ---
wShakeTimer::         db
wPanBase::            db

; --- VM ---
wScriptPtr::          dw
wScriptBank::         db
wVars::               ds VAR_COUNT
wPicBank::            db
wPicPtr::             dw

; --- explore mode ---
wCurX::               db
wCurY::               db
wCurSpot::            db
wSpotTable::          dw
wSpotDone::           db
wExploreExit::        db

; --- audio ---
wMusicId::            db
wMusicPtr::           dw
wMusicTimer::         db
wMusicCh::            db

ENDC
