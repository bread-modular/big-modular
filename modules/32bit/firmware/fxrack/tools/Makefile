# Host render of the fxrack reverbs (old BM classic vs hall) for listening and
# analysis: `make` builds render_reverb, `make render` writes WAVs, plots and a
# metrics table to ../../../research/fxrack-reverb/ (ignored).
CC ?= cc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Wno-unused-parameter -Werror
INC := -I../main/include -I../tests/stubs
OUT ?= ../../../research/fxrack-reverb

SRCS := render_reverb.c \
	../main/src/lib/bm_buffer.c \
	../main/src/lib/bm_param.c \
	../main/src/lib/bm_utils.c \
	../main/src/audio/bm_comb_filter.c \
	../main/src/audio/bm_all_pass_filter.c \
	../main/src/audio/bm_classic_reverb.c \
	../main/src/audio/bm_hall_reverb.c \
	../tests/stubs/esp_heap_caps.c

render_reverb: $(SRCS) $(wildcard ../main/include/*/*.h)
	$(CC) $(CFLAGS) $(INC) -o $@ $(SRCS) -lm

render: render_reverb
	python3 -B reverb_sim.py --render ./render_reverb --out $(OUT)

clean:
	rm -f render_reverb

.PHONY: render clean
