# ============================================================================
#  LEVIATHAN -- title screen
#
#    make          paint the screen -> out/
#    make clean
# ============================================================================

PYTHON ?= python3

TOOLS := tools/gbcanvas.py tools/gbfont.py tools/make_title.py
OUTS  := out/title.png out/title@4x.png out/title.2bpp out/title.tilemap

.PHONY: all clean

all: out/title.png

out/title.png: $(TOOLS)
	@mkdir -p out
	@$(PYTHON) tools/make_title.py

clean:
	rm -rf out __pycache__ tools/__pycache__
