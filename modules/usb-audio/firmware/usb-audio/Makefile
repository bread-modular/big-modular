# USB-AUDIO firmware (CH32V307RCT6): UAC2 2 in / 2 out + CDC console.
# Built through ../compile.sh (opt/ch32v307-tools), which passes the pinned
# CROSS_COMPILE, TINYUSB_PATH and WCH_SDK_PATH.

TARGET ?= usb-audio
BUILD ?= .build
CROSS_COMPILE ?= riscv-none-elf-
TINYUSB_PATH ?= $(error TINYUSB_PATH not set: build with ../compile.sh)
WCH_SDK_PATH ?= $(error WCH_SDK_PATH not set: build with ../compile.sh)

CC = $(CROSS_COMPILE)gcc
OBJCOPY = $(CROSS_COMPILE)objcopy
SIZE = $(CROSS_COMPILE)size

SDK = $(WCH_SDK_PATH)/EVT/EXAM/SRC
BSP = $(TINYUSB_PATH)/hw/bsp/ch32v30x

VERSION := $(shell cat VERSION)
GIT_REV := $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)

SRC_C = \
  src/main.c src/board.c src/codec.c src/i2s.c src/audio.c src/console.c src/usb_descriptors.c src/mem.c \
  $(BSP)/system_ch32v30x.c \
  $(SDK)/Core/core_riscv.c \
  $(SDK)/Peripheral/src/ch32v30x_gpio.c \
  $(SDK)/Peripheral/src/ch32v30x_rcc.c \
  $(SDK)/Peripheral/src/ch32v30x_misc.c \
  $(SDK)/Peripheral/src/ch32v30x_spi.c \
  $(SDK)/Peripheral/src/ch32v30x_dma.c \
  $(SDK)/Peripheral/src/ch32v30x_i2c.c \
  $(SDK)/Peripheral/src/ch32v30x_flash.c \
  $(TINYUSB_PATH)/src/tusb.c \
  $(TINYUSB_PATH)/src/common/tusb_fifo.c \
  $(TINYUSB_PATH)/src/device/usbd.c \
  $(TINYUSB_PATH)/src/class/audio/audio_device.c \
  $(TINYUSB_PATH)/src/class/cdc/cdc_device.c \
  src/dcd_ch32_usbhs.c
SRC_S = $(SDK)/Startup/startup_ch32v30x_D8C.S
# The BSP script moved up past the 16 KiB DFU bootloader (../bootloader).
LD_FILE = $(BUILD)/usb-audio.ld

INC = -Isrc -I../bootloader/src -I$(BSP) -I$(TINYUSB_PATH)/src/portable/wch -I$(SDK)/Core -I$(SDK)/Peripheral/inc -I$(TINYUSB_PATH)/src

ARCH = -march=rv32imac_zicsr_zifencei -mabi=ilp32 -msmall-data-limit=8 -mno-save-restore
DEFS = -DCH32V30x_D8C -DCFG_TUSB_MCU=OPT_MCU_CH32V307 -DCFG_TUD_WCH_USBIP_USBHS=1 \
       -DFW_VERSION=\"$(VERSION)\" -DFW_GIT=\"$(GIT_REV)\"
CFLAGS = $(ARCH) $(DEFS) $(INC) -Os -g -std=gnu11 -ffunction-sections -fdata-sections \
         -fsigned-char -fmessage-length=0 -Wall -Wno-strict-prototypes -Wno-unused-parameter
# __FLASH_SIZE: the 240 KiB application area less 1 KiB, its last 256 bytes are
# the settings page (src/board.h).
LDFLAGS = $(ARCH) -T $(LD_FILE) -nostartfiles --specs=nano.specs --specs=nosys.specs \
          -Wl,--gc-sections -Wl,--wrap=dcd_event_handler -Wl,-Map=$(BUILD)/$(TARGET).map \
          -Wl,--defsym=__FLASH_SIZE=239K -Wl,--defsym=__RAM_SIZE=64K -Wl,--defsym=__STACK_SIZE=2048

OBJ = $(addprefix $(BUILD)/obj/,$(notdir $(SRC_C:.c=.o)) $(notdir $(SRC_S:.S=.o)))
vpath %.c $(sort $(dir $(SRC_C)))
vpath %.S $(sort $(dir $(SRC_S)))

all: $(BUILD)/$(TARGET).bin $(BUILD)/$(TARGET).hex
	$(SIZE) $(BUILD)/$(TARGET).elf

$(BUILD)/obj/%.o: %.c src/*.h ../bootloader/src/boot.h VERSION | $(BUILD)/obj
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/obj/%.o: %.S | $(BUILD)/obj
	$(CC) $(ARCH) $(DEFS) $(INC) -x assembler-with-cpp -c $< -o $@

$(LD_FILE): $(BSP)/linker/ch32v30x.ld Makefile | $(BUILD)/obj
	sed 's/ORIGIN = 0x00000000/ORIGIN = 0x00004000/' $< > $@
	grep -q 'ORIGIN = 0x00004000' $@

$(BUILD)/$(TARGET).elf: $(OBJ) $(LD_FILE)
	$(CC) $(LDFLAGS) $(OBJ) -o $@

$(BUILD)/$(TARGET).bin: $(BUILD)/$(TARGET).elf
	$(OBJCOPY) -O binary $< $@

$(BUILD)/$(TARGET).hex: $(BUILD)/$(TARGET).elf
	$(OBJCOPY) -O ihex $< $@

# Bootloader (padded to its 16 KiB slot) + application, written from 0x0000
# through the WCH ROM bootloader (../flash.sh --full).
BOOTLOADER_BIN ?= ../bootloader/.build/bootloader.bin

full: $(BUILD)/$(TARGET)-full.bin

$(BUILD)/$(TARGET)-full.bin: $(BOOTLOADER_BIN) $(BUILD)/$(TARGET).bin
	test "$$(wc -c < $(BOOTLOADER_BIN))" -le 16384
	dd if=$(BOOTLOADER_BIN) of=$@ bs=16384 count=1 conv=sync 2>/dev/null
	cat $(BUILD)/$(TARGET).bin >> $@

$(BUILD)/obj:
	mkdir -p $@

clean:
	rm -rf $(BUILD)

.PHONY: all clean full
