#pragma once
#include <stdint.h>

// Initialise sign-magnitude motor on a two-pin port.
// dir_gpio: direction pin (HIGH = forward), pwm_gpio: speed PWM pin.
void motor_sm_init(uint8_t dir_gpio, uint8_t pwm_gpio);

// Set SM motor power.  value: -10000 to +10000 (= -100.00% to +100.00%).
void motor_sm_set(uint8_t dir_gpio, uint8_t pwm_gpio, int16_t value);

// Initialise locked anti-phase motor on a single PWM pin.
void motor_lap_init(uint8_t pwm_gpio);

// Set LAP motor power.  value: -10000 to +10000.
void motor_lap_set(uint8_t pwm_gpio, int16_t value);

// Stop a motor (either type) — drives PWM to neutral.
void motor_stop(uint8_t port_type, uint8_t pin_a, uint8_t pin_b);
