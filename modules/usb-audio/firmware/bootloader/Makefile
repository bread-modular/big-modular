# USB-AUDIO DFU bootloader (CH32V307RCT6): flash 0x0000-0x3FFF, the
# application starts at 0x4000 (see src/main.c). Built through ../compile.sh.

TARGET ?= bootloader
BUILD ?= .build
CROSS_COMPILE ?= riscv-none-elf-
TINYUSB_PATH ?= $(error TINYUSB_PATH not set: build with ../compile.sh)
WCH_SDK_PATH ?= $(error WCH_SDK_PATH not set: build with ../compile.sh)

CC = $(CROSS_COMPILE)gcc
OBJCOPY = $(CROSS_COMPILE)objcopy
SIZE = $(CROSS_COMPILE)size

SDK = $(WCH_SDK_PATH)/EVT/EXAM/SRC
BSP = $(TINYUSB_PATH)/hw/bsp/ch32v30x
# 96 MHz from the 8 MHz HSE, as WCH's USBHS IAP: flash erase / program wants
# HCLK < 100 MHz (the application runs at 144 MHz).
SYSTEM_C = $(WCH_SDK_PATH)/EVT/EXAM/IAP/USB_UART/CHV30x_IAP/User/system_ch32v30x.c

VERSION := $(shell cat VERSION)

SRC_C = \
  src/main.c src/usb_descriptors.c \
  $(SYSTEM_C) \
  $(SDK)/Core/core_riscv.c \
  $(SDK)/Peripheral/src/ch32v30x_rcc.c \
  $(SDK)/Peripheral/src/ch32v30x_flash.c \
  $(TINYUSB_PATH)/src/tusb.c \
  $(TINYUSB_PATH)/src/common/tusb_fifo.c \
  $(TINYUSB_PATH)/src/device/usbd.c \
  $(TINYUSB_PATH)/src/class/dfu/dfu_device.c \
  $(TINYUSB_PATH)/src/portable/wch/dcd_ch32_usbhs.c
SRC_S = $(SDK)/Startup/startup_ch32v30x_D8C.S
# The BSP script; __FLASH_SIZE cuts it to the 16 KiB bootloader slot.
LD_FILE = $(BSP)/linker/ch32v30x.ld

INC = -Isrc -I$(BSP) -I$(SDK)/Core -I$(SDK)/Peripheral/inc -I$(TINYUSB_PATH)/src

ARCH = -march=rv32imac_zicsr_zifencei -mabi=ilp32 -msmall-data-limit=8 -mno-save-restore
DEFS = -DCH32V30x_D8C -DCFG_TUSB_MCU=OPT_MCU_CH32V307 -DCFG_TUD_WCH_USBIP_USBHS=1 -DFW_VERSION=\"$(VERSION)\"
CFLAGS = $(ARCH) $(DEFS) $(INC) -Os -g -std=gnu11 -ffunction-sections -fdata-sections \
         -fsigned-char -fmessage-length=0 -Wall -Wno-strict-prototypes -Wno-unused-parameter
LDFLAGS = $(ARCH) -T $(LD_FILE) -nostartfiles --specs=nano.specs --specs=nosys.specs \
          -Wl,--gc-sections -Wl,-Map=$(BUILD)/$(TARGET).map -Wl,--wrap=SystemInit \
          -Wl,--defsym=__FLASH_SIZE=16K -Wl,--defsym=__RAM_SIZE=64K -Wl,--defsym=__STACK_SIZE=2048

OBJ = $(addprefix $(BUILD)/obj/,$(notdir $(SRC_C:.c=.o)) $(notdir $(SRC_S:.S=.o)))
# SYSTEM_C has an explicit rule: its directory also holds the IAP example's main.c.
vpath %.c $(sort $(dir $(filter-out $(SYSTEM_C),$(SRC_C))))
vpath %.S $(sort $(dir $(SRC_S)))

all: $(BUILD)/$(TARGET).bin $(BUILD)/$(TARGET).hex
	$(SIZE) $(BUILD)/$(TARGET).elf

$(BUILD)/obj/%.o: %.c src/*.h VERSION | $(BUILD)/obj
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/obj/system_ch32v30x.o: $(SYSTEM_C) | $(BUILD)/obj
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/obj/%.o: %.S | $(BUILD)/obj
	$(CC) $(ARCH) $(DEFS) $(INC) -x assembler-with-cpp -c $< -o $@

$(BUILD)/$(TARGET).elf: $(OBJ) $(LD_FILE)
	$(CC) $(LDFLAGS) $(OBJ) -o $@

$(BUILD)/$(TARGET).bin: $(BUILD)/$(TARGET).elf
	$(OBJCOPY) -O binary $< $@

$(BUILD)/$(TARGET).hex: $(BUILD)/$(TARGET).elf
	$(OBJCOPY) -O ihex $< $@

$(BUILD)/obj:
	mkdir -p $@

clean:
	rm -rf $(BUILD)

.PHONY: all clean
