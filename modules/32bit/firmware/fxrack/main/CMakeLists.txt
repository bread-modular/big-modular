# MIDI_RX_INVERT is checked in the project CMakeLists.txt.
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/../VERSION" FIRMWARE_VERSION)
string(STRIP "${FIRMWARE_VERSION}" FIRMWARE_VERSION)

idf_component_register(
    SRCS
        "main.c"
        "src/bm_audio.c"
        "src/bm_button.c"
        "src/bm_cv.c"
        "src/bm_es8388.c"
        "src/bm_led.c"
        "src/bm_midi.c"
        "src/lib/bm_buffer.c"
        "src/lib/bm_param.c"
        "src/lib/bm_motion_recorder.c"
        "src/lib/bm_utils.c"
        "src/audio/bm_comb_filter.c"
        "src/audio/bm_hall_reverb.c"
        "src/apps/bm_app_fxrack.c"
    REQUIRES
        esp_driver_gpio
        esp_driver_i2c
        esp_driver_i2s
        esp_driver_ledc
        esp_driver_uart
        esp_adc
        esp_psram
        esp_timer
    INCLUDE_DIRS
        "include"
)

target_compile_definitions(${COMPONENT_LIB} PRIVATE
    MIDI_RX_INVERT=${MIDI_RX_INVERT}
    FIRMWARE_NAME="fxrack"
    FIRMWARE_VERSION="${FIRMWARE_VERSION}"
)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Wno-unused-parameter)
