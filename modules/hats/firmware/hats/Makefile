# HATS S4 firmware (STM32G071C8T6), built by ../compile.sh through
# opt/stm32g0-tools/compile.sh, which passes CROSS_COMPILE, CMSIS_G0_PATH,
# CMSIS_CORE_PATH, BUILD, TARGET and DEFINES.

TARGET ?= hats
BUILD ?= .build
CROSS_COMPILE ?= arm-none-eabi-
DEFINES ?=

CC := $(CROSS_COMPILE)gcc
CXX := $(CROSS_COMPILE)g++
OBJCOPY := $(CROSS_COMPILE)objcopy
SIZE := $(CROSS_COMPILE)size

ARCH := -mcpu=cortex-m0plus -mthumb
CPPFLAGS := -DSTM32G071xx $(addprefix -D,$(DEFINES)) -Isrc \
  -I$(CMSIS_G0_PATH)/Include -I$(CMSIS_CORE_PATH)/CMSIS/Core/Include
COMMON := $(ARCH) -Os -g -Wall -Wextra -ffunction-sections -fdata-sections
CFLAGS := $(COMMON) -std=c11
CXXFLAGS := $(COMMON) -std=c++17 -fno-exceptions -fno-rtti -fno-threadsafe-statics
LDFLAGS := $(ARCH) -Tstm32g071x8.ld -Wl,--gc-sections -Wl,-Map=$(BUILD)/$(TARGET).map \
  --specs=nano.specs -Wl,--no-warn-rwx-segments -Wl,--print-memory-usage

OBJS := $(BUILD)/main.o $(BUILD)/system_stm32g0xx.o $(BUILD)/startup_stm32g071xx.o

all: $(BUILD)/$(TARGET).bin $(BUILD)/$(TARGET).hex

$(BUILD):
	mkdir -p $@

$(BUILD)/main.o: src/main.cpp src/*.h | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c $< -o $@

$(BUILD)/system_stm32g0xx.o: $(CMSIS_G0_PATH)/Source/Templates/system_stm32g0xx.c | $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

$(BUILD)/startup_stm32g071xx.o: $(CMSIS_G0_PATH)/Source/Templates/gcc/startup_stm32g071xx.s | $(BUILD)
	$(CC) $(ARCH) -c $< -o $@

$(BUILD)/$(TARGET).elf: $(OBJS) stm32g071x8.ld
	$(CXX) $(OBJS) $(LDFLAGS) -o $@
	$(SIZE) $@

$(BUILD)/$(TARGET).bin: $(BUILD)/$(TARGET).elf
	$(OBJCOPY) -O binary $< $@

$(BUILD)/$(TARGET).hex: $(BUILD)/$(TARGET).elf
	$(OBJCOPY) -O ihex $< $@

clean:
	rm -rf $(BUILD)

.PHONY: all clean
