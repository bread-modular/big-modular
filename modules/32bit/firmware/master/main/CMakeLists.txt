# Re-run CMake when VERSION changes, or the build keeps the old version string.
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/../VERSION")
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/../VERSION" FIRMWARE_VERSION)
string(STRIP "${FIRMWARE_VERSION}" FIRMWARE_VERSION)

idf_component_register(
    SRCS
        "main.c"
        "src/bm_audio.c"
        "src/bm_es8388.c"
        "src/bm_led.c"
        "src/ms_dsp.c"
        "src/ms_params.c"
        "src/ms_proto.c"
    REQUIRES
        esp_driver_gpio
        esp_driver_i2c
        esp_driver_i2s
        esp_driver_ledc
        esp_driver_usb_serial_jtag
        esp_timer
        nvs_flash
        vfs
    INCLUDE_DIRS
        "include"
)

target_compile_definitions(${COMPONENT_LIB} PRIVATE
    FIRMWARE_NAME="master"
    FIRMWARE_VERSION="${FIRMWARE_VERSION}"
)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Wno-unused-parameter)
