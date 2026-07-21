cmake_minimum_required(VERSION 3.13)

# Pull in Pico SDK (must be before project()).
# pico_sdk_import.cmake must be copied from $PICO_SDK_PATH/external/pico_sdk_import.cmake
# or PICO_SDK_PATH must be set in the environment / passed to cmake.
include(pico_sdk_import.cmake)

project(redwing_firmware C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(redwing
    src/main.c
    src/usb_comm.c
    src/port_manager.c
    src/devices/motor.c
    src/devices/servo.c
    src/devices/encoder.c
    src/devices/ultrasonic.c
    src/devices/pio_pwm.c
    src/devices/vl53l0x.c
    src/devices/pca9685.c
    src/devices/gobilda_serial.c
    src/devices/ir_distance.c
    src/devices/bno085.c
    src/devices/bno055.c
    src/devices/mpu6050.c
)

# Generate C header from PIO assembly
pico_generate_pio_header(redwing ${CMAKE_CURRENT_LIST_DIR}/src/devices/pio_pwm.pio)

target_include_directories(redwing PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/src
)

# USB serial (CDC) — no UART stdio
pico_enable_stdio_usb(redwing 1)
pico_enable_stdio_uart(redwing 0)

target_link_libraries(redwing
    pico_stdlib
    hardware_pwm
    hardware_pio
    hardware_gpio
    hardware_i2c
    hardware_uart
    hardware_timer
    hardware_adc
    pico_multicore
)

# Set USB VID/PID and product string
target_compile_definitions(redwing PRIVATE
    USBD_VID=0x2E8A          # Raspberry Pi VID
    USBD_PID=0x000A          # Custom PID for Redwing
    USBD_MANUFACTURER_STRING="Rivers Engineering"
    USBD_PRODUCT_STRING="Redwing"
)

# Generate UF2, ELF and BIN output
pico_add_extra_outputs(redwing)
