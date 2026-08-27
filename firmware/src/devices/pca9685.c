#include "pca9685.h"
#include "hardware/i2c.h"
#include "pico/stdlib.h"

// PCA9685 register map
#define MODE1         0x00
#define LED0_ON_L     0x06
#define ALL_LED_ON_L  0xFA
#define PRESCALE      0xFE

// MODE1 bit flags
#define MODE1_SLEEP   0x10
#define MODE1_AI      0x20  // auto-increment register address

static bool write_reg(uint8_t addr, uint8_t reg, uint8_t value) {
    uint8_t buf[2] = {reg, value};
    return i2c_write_blocking(i2c0, addr, buf, 2, false) == 2;
}

bool pca9685_init(uint8_t addr, uint8_t prescale) {
    // Probe: try a register read to confirm the device is present
    uint8_t reg = MODE1;
    uint8_t mode1 = 0;
    if (i2c_write_blocking(i2c0, addr, &reg, 1, true)  != 1) return false;
    if (i2c_read_blocking( i2c0, addr, &mode1, 1, false) != 1) return false;

    // Sleep → write prescale → wake with auto-increment enabled
    if (!write_reg(addr, MODE1, MODE1_SLEEP)) return false;
    sleep_ms(5);
    if (!write_reg(addr, PRESCALE, prescale)) return false;
    sleep_ms(1);
    if (!write_reg(addr, MODE1, MODE1_AI)) return false;
    sleep_ms(5);

    // All channels off: write [ON_L=0, ON_H=0, OFF_L=0, OFF_H=FULL_OFF] to ALL_LED regs
    uint8_t all_off[5] = {ALL_LED_ON_L, 0x00, 0x00, 0x00, 0x10};
    return i2c_write_blocking(i2c0, addr, all_off, 5, false) == 5;
}

bool pca9685_set_channel(uint8_t addr, uint8_t channel, uint16_t on, uint16_t off) {
    uint8_t buf[5] = {
        (uint8_t)(LED0_ON_L + 4u * channel),
        (uint8_t)(on  & 0xFF),
        (uint8_t)(on  >> 8),
        (uint8_t)(off & 0xFF),
        (uint8_t)(off >> 8),
    };
    return i2c_write_blocking(i2c0, addr, buf, 5, false) == 5;
}

bool pca9685_channel_off(uint8_t addr, uint8_t channel) {
    uint8_t buf[5] = {
        (uint8_t)(LED0_ON_L + 4u * channel),
        0x00, 0x00, 0x00, 0x10  // FULL_OFF bit in OFF_H
    };
    return i2c_write_blocking(i2c0, addr, buf, 5, false) == 5;
}

bool pca9685_channel_on(uint8_t addr, uint8_t channel) {
    uint8_t buf[5] = {
        (uint8_t)(LED0_ON_L + 4u * channel),
        0x00, 0x10, 0x00, 0x00  // FULL_ON bit in ON_H
    };
    return i2c_write_blocking(i2c0, addr, buf, 5, false) == 5;
}
