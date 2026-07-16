#pragma once
#include <stdint.h>
#include <stdbool.h>

// Period countdown for the PIO PWM loop.
// Period = 3 + 3*(PIO_PWM_WRAP+1) = 6252 cycles @125 MHz → ~20 kHz.
//
// Duty level mapping (argument to pio_pwm_set_level):
//   PIO_PWM_WRAP+1 → full OFF (0 %) — y never reaches WRAP+1
//   0              → ~0.05 % ON     — y reaches 0 only on the last tick
//   PIO_PWM_WRAP   → ~100 % ON      — y reaches WRAP immediately, stays HIGH all period
// Higher level = more ON time.  Use value_to_pio_level() to convert motor values.
#define PIO_PWM_WRAP 2082u

// Returns true for all eight dual-port B-pins, which use PIO PWM so that
// no combination of motor and servo/motor ports can produce a hardware PWM
// slice conflict.  GP8,9,10,11,13,14,15,21 = D0-B through D7-B.
bool pio_pwm_pin(uint8_t gpio);

// Initialise (or reinitialise) PIO PWM on one GPIO.
// Allocates a PIO SM on first call; reuses the same SM on subsequent calls.
void pio_pwm_init(uint8_t gpio);

// Push a new duty threshold (non-blocking; drop silently if TX FIFO is full).
void pio_pwm_set_level(uint8_t gpio, uint16_t level);

// Disable the SM and return the pin to plain GPIO (SIO) control.
// Called when the port is reconfigured away from motor type.
void pio_pwm_stop(uint8_t gpio);
