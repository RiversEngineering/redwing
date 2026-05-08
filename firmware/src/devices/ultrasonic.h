#pragma once
#include <stdint.h>
#include <stdbool.h>

#define ULTRASONIC_MAX          8
#define ULTRASONIC_MAX_MM       4000
#define ULTRASONIC_COOLDOWN_MS  60   // HC-SR04 minimum inter-trigger interval

// Register an HC-SR04 sensor on a two-pin port.
// slot: 0-7 internal index.
void ultrasonic_init(uint8_t slot, uint8_t trig_gpio, uint8_t echo_gpio);

// Unregister a slot.
void ultrasonic_deinit(uint8_t slot);

// Called periodically (~every 3 frames at 50 Hz) to fire one sensor.
// Serialises triggers: only one sensor fires per call.
void ultrasonic_update(void);

// Retrieve the last reading for a slot.
// distance_mm: result; valid: 1 if within range, 0 otherwise.
void ultrasonic_read(uint8_t slot, uint16_t *distance_mm, uint8_t *valid);
