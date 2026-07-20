#pragma once
#include <stdint.h>

// Default servo pulse range (µs) — widest range; real clamping is done by the daemon
#define SERVO_MIN_US_DEFAULT  500
#define SERVO_MAX_US_DEFAULT  2500
#define SERVO_FREQ_HZ         50

// Initialise RC servo PWM on a GPIO pin.
void servo_init(uint8_t gpio, uint16_t min_us, uint16_t max_us);

// Set servo angle.  angle_cd: centidegrees (0-18000 = 0°-180°).
void servo_set(uint8_t gpio, uint16_t angle_cd, uint16_t min_us, uint16_t max_us);

// Drive servo signal to midpoint (useful for MOTOR_SERVO_SIG mode)
void servo_set_raw_us(uint8_t gpio, uint16_t pulse_us, uint16_t min_us, uint16_t max_us);
