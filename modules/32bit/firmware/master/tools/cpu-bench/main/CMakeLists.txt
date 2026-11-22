idf_component_register(
    SRCS
        "bench.c"
        "../../../main/src/ms_dsp.c"
        "../../../main/src/ms_params.c"
    REQUIRES
        esp_timer
    INCLUDE_DIRS
        "../../../main/include"
)

if(MS_BENCH_AUDIO)
    target_compile_definitions(${COMPONENT_LIB} PRIVATE MS_BENCH_AUDIO=1)
endif()
