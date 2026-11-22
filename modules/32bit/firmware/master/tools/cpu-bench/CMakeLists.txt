# Instruction count of the master chain on the ESP32-S3 (ESP-IDF QEMU, -icount).
# Not a firmware: see run.sh.
cmake_minimum_required(VERSION 3.16)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
idf_build_set_property(MINIMAL_BUILD ON)
project(ms_cpu_bench)
