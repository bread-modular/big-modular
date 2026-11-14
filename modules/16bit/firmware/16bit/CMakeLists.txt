# Generated Cmake Pico project file

cmake_minimum_required(VERSION 3.13)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Initialise pico_sdk from installed location
# (note this can come from environment, CMake cache etc)

# SDK and toolchain paths are provided by opt/rp2350-tools/compile.sh via
# -DPICO_SDK_PATH and -DPICO_TOOLCHAIN_PATH (reused from ~/.breadmodular, or
# installed there by opt/rp2350-tools/setup.sh).

# 16bit board script will set the flash size to 16MB in the runtime
set(PICO_BOARD 16bit)
set(PICO_BOARD_HEADER_DIRS ${CMAKE_CURRENT_LIST_DIR}/includes/boards)
# This configures the firmware flash size to 2MB
# So, it won't override the 14MB filesystem when flashing the firmware
set(PICO_FLASH_SIZE_BYTES 2097152)

# Pull in Raspberry Pi Pico SDK (must be before project)
include(pico_sdk_import.cmake)

project(16bit C CXX ASM)

# Initialise the Raspberry Pi Pico SDK
pico_sdk_init()

# ---------------------------------------------------------------------------
# App selection at compile time (one app per firmware, like the 32bit module)
# The firmware compiles a SINGLE app into the binary; ../package.sh builds
# one firmware per app. Default to polysynth if not specified.
# ---------------------------------------------------------------------------
if(NOT DEFINED APP_NAME)
    set(APP_NAME "polysynth")
endif()

set(VALID_APPS "noop" "sampler" "polysynth" "fxrack" "elab" "monosynth" "lyra4")
if(NOT APP_NAME IN_LIST VALID_APPS)
    message(FATAL_ERROR "Invalid APP_NAME: ${APP_NAME}. Valid options are: ${VALID_APPS}")
endif()

# JP1 MIDI input setting (Big Modular 16bit carrier), set by ../jumper.sh:
#   1 = JP1 1-2, protected NPN front end: GPIO5 RX inverted
#   0 = JP1 2-3, direct input (as Bread Modular)
if(NOT DEFINED MIDI_RX_INVERT OR NOT MIDI_RX_INVERT MATCHES "^[01]$")
    message(FATAL_ERROR "MIDI_RX_INVERT must be 0 or 1 (JP1 setting): build through ../compile.sh p|d")
endif()

# BM_APP_<NAME>=1 compile definition + FIRMWARE_NAME used by main.cpp
set(APP_DEFINE "BM_APP_${APP_NAME}")
string(TOUPPER "${APP_DEFINE}" APP_DEFINE)

# Add executable. Default name is the project name, version 0.1

add_executable(16bit
    main.cpp
)
pico_generate_pio_header(16bit ${CMAKE_CURRENT_LIST_DIR}/i2s.pio)

# Firmware version (Bread Modular 16bit VERSION the sources were taken from)
file(READ "${CMAKE_CURRENT_LIST_DIR}/VERSION" PROJECT_VERSION)
string(STRIP "${PROJECT_VERSION}" PROJECT_VERSION)

pico_set_program_name(16bit "16bit")
pico_set_program_version(16bit "${PROJECT_VERSION}")
# Shown by `picotool info` (file or board), so a UF2 / a board tells which app
# and JP1 build it is (../flash.sh prints it before loading, ../flash.sh info).
if(MIDI_RX_INVERT)
    set(JP1_SETTING "p")
else()
    set(JP1_SETTING "d")
endif()
pico_set_program_description(16bit "${APP_NAME} app, JP1=${JP1_SETTING}")

# Modify the below lines to enable/disable output over UART/USB
pico_enable_stdio_uart(16bit 0)
pico_enable_stdio_usb(16bit 1)

# Configure USB device descriptors
target_compile_definitions(16bit PRIVATE
    USBD_VID=0x2E8A
    USBD_PID=0x000A
    USBD_MANUFACTURER="Bread Modular"
    USBD_PRODUCT="16bit"
    ${APP_DEFINE}=1
    FIRMWARE_NAME="${APP_NAME}"
    MIDI_RX_INVERT=${MIDI_RX_INVERT}
)

# Add external libraries
add_library(lfs STATIC
    ${CMAKE_CURRENT_LIST_DIR}/lib/lfs/lfs.c
    ${CMAKE_CURRENT_LIST_DIR}/lib/lfs/lfs_util.c
)

# Add the standard library to the build
target_link_libraries(16bit
        pico_stdlib
        hardware_pio
        pico_multicore
        hardware_adc
        lfs
        )

# Add the standard include files to the build
target_include_directories(16bit PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}
        ${CMAKE_CURRENT_LIST_DIR}/includes
        ${CMAKE_CURRENT_LIST_DIR}/lib/lfs
)

# The polysynth runs from RAM: its voices + the ladder executing from flash
# overrun the audio core (XIP cache misses). Its wavetables stay in flash
# (.flashdata, wavetable_data.h) and are copied to RAM one table at a time.
# lyra4 (oscillators, delay, two ladders every sample) runs from RAM too.
if(APP_NAME STREQUAL "polysynth" OR APP_NAME STREQUAL "lyra4")
    pico_set_binary_type(16bit copy_to_ram)
endif()

pico_add_extra_outputs(16bit)
