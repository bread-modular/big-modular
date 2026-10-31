# Host tests for the polysynth DSP (main/src/ps_dsp.c). `make` builds and runs.
CC ?= cc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Werror
INC := -I../main/include
PYTHON ?= python3

run: test_ps_dsp
	./test_ps_dsp

ps_wavetables.c: ../tools/gen_wavetables.py
	$(PYTHON) ../tools/gen_wavetables.py $@

test_ps_dsp: test_ps_dsp.c ../main/src/ps_dsp.c ps_wavetables.c ../main/include/ps_dsp.h ../main/include/ps_wavetables.h
	$(CC) $(CFLAGS) $(INC) -o $@ test_ps_dsp.c ../main/src/ps_dsp.c ps_wavetables.c -lm

clean:
	rm -f test_ps_dsp ps_wavetables.c

.PHONY: run clean
