#include "ultrasonic.h"
#include "hardware/gpio.h"
#include "pico/stdlib.h"
#include <string.h>

// Number of readings kept for median filtering.
#define US_MEDIAN_N  3

typedef struct {
    uint8_t  trig;
    uint8_t  echo;
    bool     active;
    uint16_t distance_mm;
    uint8_t  valid;
    // Median-filter ring buffer: stores the last US_MEDIAN_N raw measurements.
    // invalid readings are stored as 0xFFFF.
    uint16_t ring[US_MEDIAN_N];
    uint8_t  ring_idx;
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
    u->ring_idx    = 0;
    for (uint8_t i = 0; i < US_MEDIAN_N; i++) u->ring[i] = 0xFFFFu;

    gpio_init(trig_gpio);
    gpio_set_dir(trig_gpio, GPIO_OUT);
    gpio_put(trig_gpio, 0);

    gpio_init(echo_gpio);
    gpio_set_dir(echo_gpio, GPIO_IN);
    gpio_pull_up(echo_gpio);  // support open-drain echo variants that rely on pull-up
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

    // Send trigger pulse — 50 µs (5× the minimum) for 3.3 V variants that
    // may need more headroom than the spec 10 µs minimum.
    gpio_put(u->trig, 1);
    sleep_us(50);
    gpio_put(u->trig, 0);
    sleep_us(10);   // settle before watching echo

    // Wait up to 30 ms for echo to go HIGH (break, not return, so we always
    // reach the measurement — this lets us see non-zero echo_us even if the
    // wait times out, which helps diagnose whether the pin ever goes HIGH).
    uint32_t t_start = time_us_32();
    while (!gpio_get(u->echo)) {
        if ((time_us_32() - t_start) > 30000) break;
    }

    // Measure how long echo stays HIGH (0 µs if it never went HIGH at all)
    uint32_t echo_start = time_us_32();
    while (gpio_get(u->echo)) {
        if ((time_us_32() - echo_start) > 38000) break;
    }
    uint32_t echo_us = time_us_32() - echo_start;

    // Store raw result in the median ring buffer.
    // 0xFFFF = invalid (coupling spike, timeout, or out-of-range).
    uint32_t dist_mm = echo_us * 10u / 58u;
    uint16_t raw = (echo_us >= 150u && dist_mm < ULTRASONIC_MAX_MM)
                   ? (uint16_t)dist_mm : 0xFFFFu;
    u->ring[u->ring_idx] = raw;
    u->ring_idx = (u->ring_idx + 1u) % US_MEDIAN_N;

    // Median of ring buffer: simple insertion sort on a 3-element copy.
    uint16_t s[US_MEDIAN_N];
    for (uint8_t i = 0; i < US_MEDIAN_N; i++) s[i] = u->ring[i];
    for (uint8_t i = 1; i < US_MEDIAN_N; i++) {
        uint16_t key = s[i];
        int8_t   j   = (int8_t)i - 1;
        while (j >= 0 && s[j] > key) { s[j + 1] = s[j]; j--; }
        s[j + 1] = key;
    }
    uint16_t median = s[US_MEDIAN_N / 2];  // middle element

    if (median == 0xFFFFu) {
        u->distance_mm = 0;
        u->valid       = 0;
    } else {
        u->distance_mm = median;
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
