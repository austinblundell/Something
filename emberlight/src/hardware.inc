; ============================================================================
;  hardware.inc  --  Game Boy / Game Boy Color hardware definitions
;  Hand-written for EMBERLIGHT.  Only what the engine actually uses.
; ============================================================================

IF !DEF(HARDWARE_INC)
DEF HARDWARE_INC EQU 1

; ---------------------------------------------------------------- memory map
DEF _VRAM        EQU $8000
DEF _VRAM8000    EQU $8000
DEF _VRAM8800    EQU $8800
DEF _VRAM9000    EQU $9000
DEF _SCRN0       EQU $9800
DEF _SCRN1       EQU $9C00
DEF _SRAM        EQU $A000
DEF _RAM         EQU $C000
DEF _OAMRAM      EQU $FE00
DEF _HRAM        EQU $FF80

; ------------------------------------------------------------------ MBC5
DEF rRAMG        EQU $0000   ; RAM enable   ($0A = on)
DEF rROMB0       EQU $2000   ; ROM bank low 8 bits
DEF rROMB1       EQU $3000   ; ROM bank bit 8
DEF rRAMB        EQU $4000   ; SRAM bank

; ------------------------------------------------------------------ I/O regs
DEF rP1          EQU $FF00
DEF rJOYP        EQU $FF00
DEF rSB          EQU $FF01
DEF rSC          EQU $FF02
DEF rDIV         EQU $FF04
DEF rTIMA        EQU $FF05
DEF rTMA         EQU $FF06
DEF rTAC         EQU $FF07
DEF rIF          EQU $FF0F

DEF rNR10        EQU $FF10
DEF rNR11        EQU $FF11
DEF rNR12        EQU $FF12
DEF rNR13        EQU $FF13
DEF rNR14        EQU $FF14
DEF rNR21        EQU $FF16
DEF rNR22        EQU $FF17
DEF rNR23        EQU $FF18
DEF rNR24        EQU $FF19
DEF rNR30        EQU $FF1A
DEF rNR31        EQU $FF1B
DEF rNR32        EQU $FF1C
DEF rNR33        EQU $FF1D
DEF rNR34        EQU $FF1E
DEF rNR41        EQU $FF20
DEF rNR42        EQU $FF21
DEF rNR43        EQU $FF22
DEF rNR44        EQU $FF23
DEF rNR50        EQU $FF24
DEF rNR51        EQU $FF25
DEF rNR52        EQU $FF26
DEF _AUD3WAVERAM EQU $FF30

DEF rLCDC        EQU $FF40
DEF rSTAT        EQU $FF41
DEF rSCY         EQU $FF42
DEF rSCX         EQU $FF43
DEF rLY          EQU $FF44
DEF rLYC         EQU $FF45
DEF rDMA         EQU $FF46
DEF rBGP         EQU $FF47
DEF rOBP0        EQU $FF48
DEF rOBP1        EQU $FF49
DEF rWY          EQU $FF4A
DEF rWX          EQU $FF4B
DEF rKEY1        EQU $FF4D
DEF rVBK         EQU $FF4F
DEF rHDMA1       EQU $FF51
DEF rHDMA2       EQU $FF52
DEF rHDMA3       EQU $FF53
DEF rHDMA4       EQU $FF54
DEF rHDMA5       EQU $FF55
DEF rRP          EQU $FF56
DEF rBCPS        EQU $FF68
DEF rBCPD        EQU $FF69
DEF rOCPS        EQU $FF6A
DEF rOCPD        EQU $FF6B
DEF rOPRI        EQU $FF6C
DEF rSVBK        EQU $FF70
DEF rIE          EQU $FFFF

; ------------------------------------------------------------------ LCDC bits
DEF LCDCF_OFF        EQU %00000000
DEF LCDCF_ON         EQU %10000000
DEF LCDCF_WIN9800    EQU %00000000
DEF LCDCF_WIN9C00    EQU %01000000
DEF LCDCF_WINOFF     EQU %00000000
DEF LCDCF_WINON      EQU %00100000
DEF LCDCF_BG8800     EQU %00000000
DEF LCDCF_BG8000     EQU %00010000
DEF LCDCF_BG9800     EQU %00000000
DEF LCDCF_BG9C00     EQU %00001000
DEF LCDCF_OBJ8       EQU %00000000
DEF LCDCF_OBJ16      EQU %00000100
DEF LCDCF_OBJOFF     EQU %00000000
DEF LCDCF_OBJON      EQU %00000010
DEF LCDCF_BGOFF      EQU %00000000
DEF LCDCF_BGON       EQU %00000001

; ------------------------------------------------------------------ STAT bits
DEF STATF_LYC        EQU %01000000
DEF STATF_MODE10     EQU %00100000
DEF STATF_MODE01     EQU %00010000
DEF STATF_MODE00     EQU %00001000
DEF STATF_BUSY       EQU %00000010

; ------------------------------------------------------------------ IE / IF
DEF IEF_HILO         EQU %00010000
DEF IEF_SERIAL       EQU %00001000
DEF IEF_TIMER        EQU %00000100
DEF IEF_STAT         EQU %00000010
DEF IEF_VBLANK       EQU %00000001

; ------------------------------------------------------------------ joypad
DEF P1F_5            EQU %00100000   ; select d-pad
DEF P1F_4            EQU %00010000   ; select buttons
DEF P1F_GET_BTN      EQU %00010000
DEF P1F_GET_DPAD     EQU %00100000
DEF P1F_GET_NONE     EQU %00110000

DEF PADF_DOWN        EQU %10000000
DEF PADF_UP          EQU %01000000
DEF PADF_LEFT        EQU %00100000
DEF PADF_RIGHT       EQU %00010000
DEF PADF_START       EQU %00001000
DEF PADF_SELECT      EQU %00000100
DEF PADF_B           EQU %00000010
DEF PADF_A           EQU %00000001

DEF PADB_DOWN        EQU 7
DEF PADB_UP          EQU 6
DEF PADB_LEFT        EQU 5
DEF PADB_RIGHT       EQU 4
DEF PADB_START       EQU 3
DEF PADB_SELECT      EQU 2
DEF PADB_B           EQU 1
DEF PADB_A           EQU 0

; ------------------------------------------------------------------ OAM flags
DEF OAMF_PRI         EQU %10000000
DEF OAMF_YFLIP       EQU %01000000
DEF OAMF_XFLIP       EQU %00100000
DEF OAMF_PAL0        EQU %00000000
DEF OAMF_PAL1        EQU %00010000
DEF OAMF_BANK0       EQU %00000000
DEF OAMF_BANK1       EQU %00001000

; --------------------------------------------------------------- CGB helpers
; Pack a 15-bit BGR555 colour from 0-31 components.
MACRO rgb555
    DEF _C = (\1 & 31) | ((\2 & 31) << 5) | ((\3 & 31) << 10)
    dw _C
ENDM

ENDC
