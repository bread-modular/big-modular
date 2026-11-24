# Host tests for the master DSP, parameters and USB protocol (main/src/ms_*.c).
# `make` builds and runs them under AddressSanitizer / UBSan.
CC ?= cc
CFLAGS ?= -O1 -g -std=c11 -Wall -Wextra -Wno-unused-parameter -Werror -fsanitize=address,undefined
INC := -I../main/include

SRCS := test_ms.c ../main/src/ms_dsp.c ../main/src/ms_params.c ../main/src/ms_proto.c ../main/src/ms_ctl.c

run: test_ms
	./test_ms
	$(MAKE) -C ../tools check-web

test_ms: $(SRCS) $(wildcard ../main/include/*.h)
	$(CC) $(CFLAGS) $(INC) -o $@ $(SRCS) -lm

clean:
	rm -f test_ms

.PHONY: run clean
