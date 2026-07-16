#pragma once
#include <stdint.h>
#include <stdbool.h>

#define ENCODER_MAX  8   // one per port slot

// Register a quadrature encoder on pin_a and pin_b.
// slot: 0-7 internal index (call once per encoder port).
void encoder_init(uint8_t slot, uint8_t pin_a, uint8_t pin_b);

// Remove an encoder from a slot (used on CONFIGURE to different type).
void encoder_deinit(uint8_t slot);

// Reset tick count for the given slot to zero.
void encoder_reset(uint8_t slot);

// Set whether count and velocity are negated before being returned.
// Use when the encoder is physically mounted such that positive motor direction
// produces a decreasing count.  Does not affect the raw IRQ accumulator.
void encoder_set_inverted(uint8_t slot, bool inverted);

// Read current tick count.
int32_t encoder_get_count(uint8_t slot);

// Read velocity in ticks/s × 10 (updated by the velocity daemon at 100 Hz).
int32_t encoder_get_velocity(uint8_t slot);

// Called by the 100 Hz PID/velocity timer to update running velocity averages.
void encoder_update_velocity(void);
