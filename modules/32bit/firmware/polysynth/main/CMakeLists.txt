# MIDI_RX_INVERT is checked in the project CMakeLists.txt.
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/../VERSION" FIRMWARE_VERSION)
string(STRIP "${FIRMWARE_VERSION}" FIRMWARE_VERSION)

idf_component_register(
    SRCS
        "main.c"
        "src/ps_dsp.c"
        "src/bm_audio.c"
        "src/bm_button.c"
        "src/bm_cv.c"
        "src/bm_es8388.c"
        "src/bm_led.c"
        "src/bm_midi.c"
        "${CMAKE_CURRENT_BINARY_DIR}/ps_wavetables.c"
    REQUIRES
        esp_driver_gpio
        esp_driver_i2c
        esp_driver_i2s
        esp_driver_ledc
        esp_driver_uart
        esp_adc
        esp_timer
        nvs_flash
    INCLUDE_DIRS
        "include"
)

# Wavetables are generated at build time (tools/gen_wavetables.py, pure Python).
idf_build_get_property(python PYTHON)
set(WT_GEN "${CMAKE_CURRENT_SOURCE_DIR}/../tools/gen_wavetables.py")
add_custom_command(
    OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/ps_wavetables.c"
    COMMAND ${python} "${WT_GEN}" "${CMAKE_CURRENT_BINARY_DIR}/ps_wavetables.c"
    DEPENDS "${WT_GEN}"
    COMMENT "Generating polysynth wavetables"
    VERBATIM)
add_custom_target(ps_wavetables DEPENDS "${CMAKE_CURRENT_BINARY_DIR}/ps_wavetables.c")
add_dependencies(${COMPONENT_LIB} ps_wavetables)

target_compile_definitions(${COMPONENT_LIB} PRIVATE
    MIDI_RX_INVERT=${MIDI_RX_INVERT}
    FIRMWARE_NAME="polysynth"
    FIRMWARE_VERSION="${FIRMWARE_VERSION}"
)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Wno-unused-parameter)
