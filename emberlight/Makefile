# ============================================================================
#  EMBERLIGHT -- Game Boy build
#
#    make          assets, assemble, link, fix -> build/emberlight.gb
#    make assets   regenerate art and script only
#    make shots    run the ROM headlessly and capture screenshots
#    make clean
# ============================================================================

NAME    := emberlight
BUILD   := build
GEN     := assets/gen
SRC     := src

PYTHON  ?= python3
RGBASM  ?= rgbasm
RGBLINK ?= rgblink
RGBFIX  ?= rgbfix

ROM     := $(BUILD)/$(NAME).gb
ROM_DMG := $(BUILD)/$(NAME)-dmg.gb
OBJ     := $(BUILD)/main.o
MAP     := $(BUILD)/$(NAME).map
SYM     := $(BUILD)/$(NAME).sym

# Every engine source is pulled in by main.asm, so one translation unit is
# enough and the whole game links in a single pass.
ASM_DEPS := $(wildcard $(SRC)/*.asm) $(wildcard $(SRC)/*.inc) \
            $(wildcard $(SRC)/engine/*.asm) $(wildcard $(SRC)/engine/*.inc)

TOOL_DEPS := tools/gbart.py tools/gbfont.py tools/scenes.py tools/story.py \
             tools/tileconv.py tools/build_assets.py

ASFLAGS  := -I $(SRC) -I $(SRC)/engine -I $(GEN) -Weverything -Wno-obsolete
LINKFLAGS := -m $(MAP) -n $(SYM)

.PHONY: all assets shots clean preview dmg

all: $(ROM) $(ROM_DMG)

$(GEN)/manifest.inc: $(TOOL_DEPS)
	@mkdir -p $(GEN)
	@echo "  GEN   assets"
	@$(PYTHON) tools/build_assets.py

assets: $(GEN)/manifest.inc

$(OBJ): $(ASM_DEPS) $(GEN)/manifest.inc
	@mkdir -p $(BUILD)
	@echo "  ASM   $(SRC)/main.asm"
	@$(RGBASM) $(ASFLAGS) -o $@ $(SRC)/main.asm

$(ROM): $(OBJ)
	@echo "  LINK  $@"
	@$(RGBLINK) $(LINKFLAGS) -o $@ $<
	@echo "  FIX   $@"
	@$(RGBFIX) -v -p 0xFF -t "EMBERLIGHT" -i EMBL -k EM -m 0x19 -c -l 0x33 $@
	@ls -l $@ | awk '{printf "  DONE  %s (%s bytes)\n", $$9, $$5}'

# The same binary with the Game Boy Color flag cleared.  Useful for testing
# the monochrome path: the boot ROM's hardware signature is what the engine
# keys off, and emulators derive it from this flag.
$(ROM_DMG): $(OBJ)
	@echo "  LINK  $@"
	@$(RGBLINK) -o $@ $<
	@$(RGBFIX) -v -p 0xFF -t "EMBERLIGHT" -i EMBL -k EM -m 0x19 -l 0x33 $@

dmg: $(ROM_DMG)

preview:
	@$(PYTHON) tools/preview.py

shots: $(ROM)
	@$(PYTHON) tools/capture.py

clean:
	rm -rf $(BUILD) $(GEN)
