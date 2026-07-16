#include "encoder.h"
#include "hardware/gpio.h"
#include "pico/stdlib.h"
#include "pico/critical_section.h"
#include <string.h>

// ─── Velocity averaging ───────────────────────────────────────────────────────
// We keep a ring buffer of tick-count snapshots over the last 100 ms.
// At 100 Hz the timer fires every 10 ms → 10 samples span 100 ms.
#define VEL_SAMPLES     10

typedef struct {
    uint8_t  pin_a;
    uint8_t  pin_b;
    bool     active;
    bool     inverted;               // when true, count and velocity are negated on read
    volatile int32_t count;          // raw tick count (ISR-written)
    int32_t  snap[VEL_SAMPLES];      // circular snapshot buffer
    uint8_t  snap_idx;
    int32_t  velocity_x10;           // ticks/s × 10, refreshed each timer tick
} EncoderState;

static EncoderState enc[ENCODER_MAX];

// Critical section to protect 32-bit count reads on a 32-bit MCU
// (not strictly needed on RP2040 since 32-bit reads are atomic, but kept for
// correctness if the compiler ever splits the access)
static critical_section_t enc_cs;
static bool cs_inited = false;

// Lookup table: gpio → slot index (-1 = unregistered)
static int8_t gpio_to_slot[30];  // GP0-GP29

// ─── Quadrature decode via state machine ─────────────────────────────────────
// We use a 4-state Gray-code table: (prev_a<<1)|prev_b -> (cur_a<<1)|cur_b
static const int8_t QEM[16] = {
    // rows = old state 0-3, cols = new state 0-3
     0, -1,  1,  0,   // old = 0b00
     1,  0,  0, -1,   // old = 0b01
    -1,  0,  0,  1,   // old = 0b10
     0,  1, -1,  0,   // old = 0b11
};

static uint8_t enc_state[ENCODER_MAX];  // last 2-bit AB state per slot

static void encoder_irq_handler(uint gpio, uint32_t events) {
    (void)events;
    int8_t slot = gpio_to_slot[gpio];
    if (slot < 0) return;
    EncoderState *e = &enc[(uint8_t)slot];
    if (!e->active) return;

    uint8_t a = gpio_get(e->pin_a);
    uint8_t b = gpio_get(e->pin_b);
    uint8_t new_state = (a << 1) | b;
    uint8_t old_state = enc_state[(uint8_t)slot];
    enc_state[(uint8_t)slot] = new_state;

    int8_t delta = QEM[(old_state << 2) | new_state];
    e->count += delta;
}

void encoder_init(uint8_t slot, uint8_t pin_a, uint8_t pin_b) {
    if (slot >= ENCODER_MAX) return;

    if (!cs_inited) {
        critical_section_init(&enc_cs);
        memset(gpio_to_slot, -1, sizeof(gpio_to_slot));
        cs_inited = true;
    }

    EncoderState *e = &enc[slot];
    e->pin_a        = pin_a;
    e->pin_b        = pin_b;
    e->count        = 0;
    e->velocity_x10 = 0;
    e->snap_idx     = 0;
    e->inverted     = false;
    memset(e->snap, 0, sizeof(e->snap));
    enc_state[slot] = 0;
    e->active       = true;

    gpio_to_slot[pin_a] = (int8_t)slot;
    gpio_to_slot[pin_b] = (int8_t)slot;

    gpio_init(pin_a);
    gpio_set_dir(pin_a, GPIO_IN);
    gpio_pull_up(pin_a);

    gpio_init(pin_b);
    gpio_set_dir(pin_b, GPIO_IN);
    gpio_pull_up(pin_b);

    // Initial state capture before enabling IRQs
    enc_state[slot] = (gpio_get(pin_a) << 1) | gpio_get(pin_b);

    gpio_set_irq_enabled_with_callback(pin_a,
        GPIO_IRQ_EDGE_RISE | GPIO_IRQ_EDGE_FALL, true, encoder_irq_handler);
    gpio_set_irq_enabled(pin_b,
        GPIO_IRQ_EDGE_RISE | GPIO_IRQ_EDGE_FALL, true);
}

void encoder_deinit(uint8_t slot) {
    if (slot >= ENCODER_MAX) return;
    EncoderState *e = &enc[slot];
    if (!e->active) return;

    gpio_set_irq_enabled(e->pin_a, GPIO_IRQ_EDGE_RISE | GPIO_IRQ_EDGE_FALL, false);
    gpio_set_irq_enabled(e->pin_b, GPIO_IRQ_EDGE_RISE | GPIO_IRQ_EDGE_FALL, false);
    gpio_to_slot[e->pin_a] = -1;
    gpio_to_slot[e->pin_b] = -1;
    e->active = false;
}

void encoder_reset(uint8_t slot) {
    if (slot >= ENCODER_MAX) return;
    // Disable IRQ briefly to safely zero the count
    EncoderState *e = &enc[slot];
    gpio_set_irq_enabled(e->pin_a, GPIO_IRQ_EDGE_RISE | GPIO_IRQ_EDGE_FALL, false);
    gpio_set_irq_enabled(e->pin_b, GPIO_IRQ_EDGE_RISE | GPIO_IRQ_EDGE_FALL, false);
    e->count = 0;
    memset(e->snap, 0, sizeof(e->snap));
    e->velocity_x10 = 0;
    e->snap_idx = 0;
    gpio_set_irq_enabled(e->pin_a, GPIO_IRQ_EDGE_RISE | GPIO_IRQ_EDGE_FALL, true);
    gpio_set_irq_enabled(e->pin_b, GPIO_IRQ_EDGE_RISE | GPIO_IRQ_EDGE_FALL, true);
}

int32_t encoder_get_count(uint8_t slot) {
    if (slot >= ENCODER_MAX || !enc[slot].active) return 0;
    int32_t v = enc[slot].count;   // 32-bit read is atomic on Cortex-M0+
    return enc[slot].inverted ? -v : v;
}

int32_t encoder_get_velocity(uint8_t slot) {
    if (slot >= ENCODER_MAX || !enc[slot].active) return 0;
    int32_t v = enc[slot].velocity_x10;
    return enc[slot].inverted ? -v : v;
}

void encoder_set_inverted(uint8_t slot, bool inverted) {
    if (slot >= ENCODER_MAX) return;
    enc[slot].inverted = inverted;
}

// Called at 100 Hz — computes velocity over the last 100 ms window
void encoder_update_velocity(void) {
    for (uint8_t s = 0; s < ENCODER_MAX; s++) {
        EncoderState *e = &enc[s];
        if (!e->active) continue;

        int32_t current = e->count;
        uint8_t oldest_idx = (e->snap_idx + 1) % VEL_SAMPLES;
        int32_t oldest  = e->snap[oldest_idx];

        // delta ticks over 100 ms → ticks/s = delta * 10; reported × 10 → * 100
        int32_t delta = current - oldest;
        e->velocity_x10 = delta * 100;  // ticks/s × 10

        e->snap[e->snap_idx] = current;
        e->snap_idx = (e->snap_idx + 1) % VEL_SAMPLES;
    }
}
