# 32bit master (ESP-IDF v5.5.1, esp32s3). Build with ../compile.sh master.
# No MIDI in this firmware, so no JP1 setting.
cmake_minimum_required(VERSION 3.16)

# Board: -D CODEC_CLOCK_MASTER=1 for the ES1 board (Y2 clocks the ES8388, codec = I2S master, ESP32-S3 =
# slave), 0 for the S3 board (ESP32-S3 makes MCLK on GPIO21). compile.sh / flash.sh pass it from BOARD.
if(NOT DEFINED CODEC_CLOCK_MASTER)
    set(CODEC_CLOCK_MASTER 0)
endif()
if(NOT CODEC_CLOCK_MASTER MATCHES "^[01]$")
    message(FATAL_ERROR "CODEC_CLOCK_MASTER must be 0 or 1, got '${CODEC_CLOCK_MASTER}'")
endif()

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
idf_build_set_property(MINIMAL_BUILD ON)
project(master)
