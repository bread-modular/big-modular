CC ?= cc
AVR_CC ?= avr-gcc
OUT ?= ../research/electrical-v1/firmware-build
CFLAGS = -std=c11 -Wall -Wextra -Werror -Os
.PHONY: host-test target
host-test:
	mkdir -p $(OUT)
	$(CC) $(CFLAGS) logic.c test_logic.c -o $(OUT)/test_logic
	$(OUT)/test_logic
target:
	command -v $(AVR_CC)
	mkdir -p $(OUT)
	$(AVR_CC) $(CFLAGS) -mmcu=attiny1616 -DF_CPU=3333333UL logic.c main.c -o $(OUT)/diagnostics.elf
	avr-objcopy -O ihex -R .eeprom $(OUT)/diagnostics.elf $(OUT)/diagnostics.hex
