#include "ultrasonic.h"
#include "hardware/gpio.h"
#include "pico/stdlib.h"
#include <string.h>

typedef struct {
    uint8_t  trig;
    uint8_t  echo;
    bool     active;
    uint16_t distance_mm;
    uint8_t  valid;
} UltrasonicState;

static UltrasonicState us[ULTRASONIC_MAX];

// Round-robin index: one sensor is triggered per update() call
static uint8_t rr_idx = 0;

void ultrasonic_init(uint8_t slot, uint8_t trig_gpio, uint8_t echo_gpio) {
    if (slot >= ULTRASONIC_MAX) return;
    UltrasonicState *u = &us[slot];
    u->trig        = trig_gpio;
    u->echo        = echo_gpio;
    u->distance_mm = 0;
    u->valid       = 0;
    u->active      = true;

    gpio_init(trig_gpio);
    gpio_set_dir(trig_gpio, GPIO_OUT);
    gpio_put(trig_gpio, 0);

    gpio_init(echo_gpio);
    gpio_set_dir(echo_gpio, GPIO_IN);
}

void ultrasonic_deinit(uint8_t slot) {
    if (slot >= ULTRASONIC_MAX) return;
    us[slot].active = false;
}

// Fire one sensor and busy-wait for the echo (max ~25 ms timeout).
// This is intentionally blocking — called at ~17 Hz per sensor so it's safe.
static void trigger_and_read(uint8_t slot) {
    UltrasonicState *u = &us[slot];
    if (!u->active) return;

    // Send 10 µs trigger pulse
    gpio_put(u->trig, 1);
    sleep_us(10);
    gpio_put(u->trig, 0);

    // Wait for echo to go high (max 5 ms before echo starts)
    uint32_t t_start = time_us_32();
    while (!gpio_get(u->echo)) {
        if ((time_us_32() - t_start) > 5000) {
            u->valid = 0;
            return;
        }
    }

    // Measure pulse width (max 38 ms for no-object)
    uint32_t echo_start = time_us_32();
    while (gpio_get(u->echo)) {
        if ((time_us_32() - echo_start) > 38000) break;
    }
    uint32_t echo_us = time_us_32() - echo_start;

    // Convert: distance_mm = echo_us * 10 / 58
    uint32_t dist_mm = echo_us * 10u / 58u;
    if (dist_mm > ULTRASONIC_MAX_MM) {
        u->distance_mm = 0;
        u->valid       = 0;
    } else {
        u->distance_mm = (uint16_t)dist_mm;
        u->valid       = 1;
    }
}

void ultrasonic_update(void) {
    // Advance round-robin to the next active slot
    for (uint8_t i = 0; i < ULTRASONIC_MAX; i++) {
        rr_idx = (rr_idx + 1) % ULTRASONIC_MAX;
        if (us[rr_idx].active) {
            trigger_and_read(rr_idx);
            return;
        }
    }
}

void ultrasonic_read(uint8_t slot, uint16_t *distance_mm, uint8_t *valid) {
    if (slot >= ULTRASONIC_MAX || !us[slot].active) {
        *distance_mm = 0;
        *valid       = 0;
        return;
    }
    *distance_mm = us[slot].distance_mm;
    *valid       = us[slot].valid;
}
