# Host tests for the fxrack DSP and app (main/src/audio, lib, apps). `make` builds
# and runs them under AddressSanitizer (catches delay-buffer overruns).
CC ?= cc
CFLAGS ?= -O1 -g -std=c11 -Wall -Wextra -Wno-unused-parameter -Werror -fsanitize=address,undefined
INC := -I../main/include -Istubs

SRCS := test_fx_dsp.c \
	../main/src/lib/bm_buffer.c \
	../main/src/lib/bm_param.c \
	../main/src/lib/bm_utils.c \
	../main/src/lib/bm_motion_recorder.c \
	../main/src/audio/bm_comb_filter.c \
	../main/src/audio/bm_all_pass_filter.c \
	../main/src/audio/bm_classic_reverb.c \
	../main/src/audio/bm_hall_reverb.c \
	../main/src/apps/bm_app_fxrack.c \
	stubs/esp_heap_caps.c

run: test_fx_dsp
	./test_fx_dsp

test_fx_dsp: $(SRCS) $(wildcard ../main/include/*.h ../main/include/*/*.h)
	$(CC) $(CFLAGS) $(INC) -o $@ $(SRCS) -lm

clean:
	rm -f test_fx_dsp

.PHONY: run clean
