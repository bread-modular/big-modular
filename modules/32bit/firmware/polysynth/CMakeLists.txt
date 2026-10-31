# 32bit polysynth (ESP-IDF v5.5.1, esp32s3). Build with ../compile.sh p|d.
cmake_minimum_required(VERSION 3.16)

# JP1 MIDI input setting: -D MIDI_RX_INVERT=1 (p, JP1 1-2) or 0 (d, JP1 2-3).
# compile.sh / flash.sh pass it; there is no default on purpose.
if(NOT DEFINED MIDI_RX_INVERT)
    message(FATAL_ERROR "MIDI_RX_INVERT not set: build with ../compile.sh p (JP1 1-2) or d (JP1 2-3)")
endif()
if(NOT MIDI_RX_INVERT MATCHES "^[01]$")
    message(FATAL_ERROR "MIDI_RX_INVERT must be 0 or 1, got '${MIDI_RX_INVERT}'")
endif()

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
idf_build_set_property(MINIMAL_BUILD ON)
project(polysynth)
