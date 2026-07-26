ROM     := build/gbhorizon.gb
SRC     := src/main.asm
GENDIR  := src/gen
GENSTAMP:= $(GENDIR)/.stamp

.PHONY: all clean shot

all: $(ROM)

$(GENSTAMP): tools/gen_assets.py
	@mkdir -p $(GENDIR)
	python3 tools/gen_assets.py
	@touch $(GENSTAMP)

build/main.o: $(SRC) src/hardware.inc $(GENSTAMP)
	@mkdir -p build
	rgbasm -o $@ $(SRC)

$(ROM): build/main.o
	@mkdir -p build
	rgblink -o $@ -m build/main.map -n build/main.sym build/main.o
	rgbfix -v -p 0xFF -t "GB HORIZON" -i GBHZ -l 0x33 $(ROM)

clean:
	rm -rf build $(GENDIR)
