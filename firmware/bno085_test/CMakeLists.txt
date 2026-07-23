cmake_minimum_required(VERSION 3.13)

# PICO_SDK_PATH can be set via environment variable or -DPICO_SDK_PATH= on the cmake command.
if(DEFINED ENV{PICO_SDK_PATH} AND NOT DEFINED PICO_SDK_PATH)
    set(PICO_SDK_PATH $ENV{PICO_SDK_PATH})
endif()

include(${PICO_SDK_PATH}/external/pico_sdk_import.cmake)

project(bno085_test C CXX ASM)
set(CMAKE_C_STANDARD 11)

pico_sdk_init()

add_executable(bno085_test bno085_test.c)
target_link_libraries(bno085_test pico_stdlib hardware_i2c)
pico_add_extra_outputs(bno085_test)
pico_enable_stdio_usb(bno085_test 1)
pico_enable_stdio_uart(bno085_test 0)
