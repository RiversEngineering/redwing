#include "gobilda_serial.h"
#include "hardware/gpio.h"
#include "pico/time.h"

// ─── Pre-computed packet bytes ─────────────────────────────────────────────
// Dynamixel/Feetech v1 protocol, 76800 baud 8N1.  Checksums are pre-verified.

static const uint8_t UNLOCK[] = {0xFF, 0xFF, 0x01, 0x04, 0x03, 0x34, 0x00, 0xC3};

// Continuous rotation mode configuration (51 bytes)
static const uint8_t CFG_CONT[] = {
    0xFF, 0xFF, 0x01, 0x2F, 0x03, 0x06, 0x32, 0x14, 0x00, 0x05, 0x00,
    0x0A, 0x00, 0x0A, 0x00, 0x1E, 0x00, 0x00, 0x00, 0x03, 0xFF, 0x01,
    0x00, 0x00, 0x00, 0x41, 0x03, 0xC5, 0x01, 0xF4, 0x01, 0xFF, 0x00,
    0x00, 0x02, 0x06, 0x0E, 0x05, 0xAA, 0x03, 0xE8, 0x00, 0x14, 0x00,
    0x00, 0x00, 0x00, 0x03, 0xE8, 0x00, 0x99
};

// Positional control mode configuration (51 bytes)
static const uint8_t CFG_POS[] = {
    0xFF, 0xFF, 0x01, 0x2F, 0x03, 0x06, 0x02, 0x1E, 0x00, 0x05, 0x00,
    0x0F, 0x00, 0x2D, 0x00, 0x00, 0x00, 0x00, 0x0F, 0x03, 0xFC, 0x00,
    0x00, 0x00, 0x00, 0x41, 0x03, 0xC5, 0x00, 0x00, 0x01, 0xFF, 0x01,
    0x00, 0x02, 0x09, 0xC4, 0x01, 0xF4, 0x03, 0xE8, 0x00, 0x01, 0x00,
    0x00, 0x00, 0x00, 0x03, 0xE8, 0x00, 0xB2
};

static const uint8_t LOCK[]   = {0xFF, 0xFF, 0x01, 0x04, 0x03, 0x34, 0x01, 0xC2};
static const uint8_t REBOOT[] = {0xFF, 0xFF, 0x01, 0x02, 0x0D, 0xEF};

// ─── Bit-bang half-duplex UART TX ─────────────────────────────────────────
// 76800 baud → 13.02 µs/bit.  busy_wait_us_32(13) gives 13 µs (0.15% error —
// well within UART receiver tolerance).  gpio_put() overhead (~40 ns) is
// negligible at this bit rate.

#define BIT_US 13u

static void tx_byte(uint8_t pin, uint8_t byte) {
    gpio_put(pin, 0);                   // start bit
    busy_wait_us_32(BIT_US);
    for (int i = 0; i < 8; i++) {      // 8 data bits, LSB first
        gpio_put(pin, (byte >> i) & 1u);
        busy_wait_us_32(BIT_US);
    }
    gpio_put(pin, 1);                   // stop bit
    busy_wait_us_32(BIT_US);
}

static void tx(uint8_t pin, const uint8_t *data, uint8_t len) {
    for (uint8_t i = 0; i < len; i++) {
        tx_byte(pin, data[i]);
    }
}

// ─── Public API ────────────────────────────────────────────────────────────

void gobilda_set_mode(uint8_t gpio_pin, uint8_t mode) {
    // Take pin offline from PWM → GPIO output, idle HIGH (UART idle state)
    gpio_set_function(gpio_pin, GPIO_FUNC_SIO);
    gpio_set_dir(gpio_pin, GPIO_OUT);
    gpio_put(gpio_pin, 1);
    busy_wait_us_32(10000);     // 10 ms: let servo see a stable idle before packets

    // Step 1: unlock EEPROM
    tx(gpio_pin, UNLOCK, sizeof(UNLOCK));
    busy_wait_us_32(10000);     // 10 ms

    // Step 2: write mode configuration
    if (mode == 1) {
        tx(gpio_pin, CFG_CONT, sizeof(CFG_CONT));
    } else {
        tx(gpio_pin, CFG_POS, sizeof(CFG_POS));
    }
    busy_wait_us_32(80000);     // 80 ms: EEPROM write time

    // Step 3: lock EEPROM
    tx(gpio_pin, LOCK, sizeof(LOCK));
    busy_wait_us_32(10000);     // 10 ms

    // Step 4: reboot servo — caller restores PWM immediately after return
    tx(gpio_pin, REBOOT, sizeof(REBOOT));
    gpio_put(gpio_pin, 1);      // hold idle HIGH; caller reconnects PWM
}
