# 32bit master (ESP-IDF v5.5.1, esp32s3). Build with ../compile.sh master.
# No MIDI in this firmware, so no JP1 setting.
cmake_minimum_required(VERSION 3.16)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
idf_build_set_property(MINIMAL_BUILD ON)
project(master)
