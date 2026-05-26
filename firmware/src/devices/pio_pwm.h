#pragma once
#include <stdint.h>
#include <stdbool.h>

// Period countdown for the PIO PWM loop.
// Period = 3 + 3*(PIO_PWM_WRAP+1) = 6252 cycles @125 MHz → ~20 kHz.
//
// Duty level mapping (argument to pio_pwm_set_level):
//   0              → full ON  (100 %)
//   PIO_PWM_WRAP   → ~0.05 % ON
//   PIO_PWM_WRAP+1 → full OFF (0 %)
#define PIO_PWM_WRAP 2082u

// Returns true for the four D-port B-pins that use PIO PWM instead of hardware
// PWM to eliminate slice conflicts with S-port servos and D1/D6 motor conflict:
//   GP10 = D2-B  (hw slice 5A = same channel as S5/GP26)
//   GP11 = D3-B  (hw slice 5B = same channel as S6/GP27)
//   GP13 = D7-B  (hw slice 6B = same slice   as S7/GP28)
//   GP25 = D6-B  (hw slice 4B = same channel as D1-B/GP9)
bool pio_pwm_pin(uint8_t gpio);

// Initialise (or reinitialise) PIO PWM on one GPIO.
// Allocates a PIO SM on first call; reuses the same SM on subsequent calls.
void pio_pwm_init(uint8_t gpio);

// Push a new duty threshold (non-blocking; drop silently if TX FIFO is full).
void pio_pwm_set_level(uint8_t gpio, uint16_t level);

// Disable the SM and return the pin to plain GPIO (SIO) control.
// Called when the port is reconfigured away from motor type.
void pio_pwm_stop(uint8_t gpio);
