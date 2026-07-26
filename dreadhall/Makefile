# DREADHALL -- Game Boy FPS
NAME    := dreadhall
SRC     := src
BUILD   := build
ASM     := $(SRC)/main.asm
GEN     := $(SRC)/gen/consts.inc $(SRC)/gen/tiles.inc $(SRC)/gen/tables.inc $(SRC)/gen/map.inc $(SRC)/gen/shade.inc $(SRC)/gen/height.inc
DEPS    := $(wildcard $(SRC)/*.asm) $(wildcard $(SRC)/*.inc)

all: $(BUILD)/$(NAME).gb

$(GEN): tools/gen_assets.py
	python3 tools/gen_assets.py

$(BUILD)/$(NAME).o: $(ASM) $(DEPS) $(GEN)
	@mkdir -p $(BUILD)
	rgbasm -i $(SRC)/ -o $@ $(ASM)

$(BUILD)/$(NAME).gb: $(BUILD)/$(NAME).o
	rgblink -m $(BUILD)/$(NAME).map -n $(BUILD)/$(NAME).sym -o $@ $<
	rgbfix -v -p 0xFF -t DREADHALL -i DRDH -m 0x19 $@

clean:
	rm -rf $(BUILD) $(SRC)/gen

.PHONY: all clean
