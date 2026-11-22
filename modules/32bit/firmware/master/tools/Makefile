# Host tools for the master firmware.
#   make                 builds ms_render (WAV in -> the firmware chain -> WAV out)
#   make web             regenerates ../web/demo.js (the page's demo mode) from the
#                        parameter table
#   make demo            a synthetic kick + mix loop through the factory settings,
#                        WAVs and plots in ../../../research/master/ (ignored)
#   make glue            the glue compressor alone on test signals: glue.md and
#                        glue.png in ../../../research/master/glue/; OLD=<ms_render
#                        of another firmware version> draws that one beside it
CC ?= cc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Wno-unused-parameter -Werror
INC := -I../main/include
OUT ?= ../../../research/master

SRCS := ms_render.c ../main/src/ms_dsp.c ../main/src/ms_params.c

ms_render: $(SRCS) $(wildcard ../main/include/*.h)
	$(CC) $(CFLAGS) $(INC) -o $@ $(SRCS) -lm

gen_web_demo: gen_web_demo.c ../main/src/ms_proto.c ../main/src/ms_params.c ../main/src/ms_dsp.c $(wildcard ../main/include/*.h) ../VERSION
	$(CC) $(CFLAGS) $(INC) -DFIRMWARE_VERSION='"$(shell cat ../VERSION)"' -o $@ gen_web_demo.c ../main/src/ms_proto.c ../main/src/ms_params.c ../main/src/ms_dsp.c -lm

web: gen_web_demo
	./gen_web_demo > ../web/demo.js

# Fails if ../web/demo.js is not what the parameter table gives now.
check-web: gen_web_demo
	./gen_web_demo | cmp -s - ../web/demo.js || { echo "web/demo.js is stale: run 'make web' in tools/"; exit 1; }

demo: ms_render
	python3 -B demo.py --render ./ms_render --out $(OUT)

glue: ms_render
	python3 -B glue_check.py --render ./ms_render --out $(OUT)/glue $(if $(OLD),--old $(OLD))

clean:
	rm -f ms_render gen_web_demo

.PHONY: web check-web demo glue clean
