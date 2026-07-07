#pragma once
#include <stdint.h>
#include <stdbool.h>

// Detect and initialize the PCA9685 at the given I²C address.
// Puts the device into sleep mode, writes prescale, then wakes it with
// auto-increment enabled.  All channels are set to FULL_OFF on success.
// Returns true if the device responds and init succeeds.
bool pca9685_init(uint8_t addr, uint8_t prescale);

// Set a channel's ON/OFF tick counts (0–4095).  Call with on=0 and
// off = pulse_us / period_us * 4096 for normal PWM operation.
bool pca9685_set_channel(uint8_t addr, uint8_t channel, uint16_t on, uint16_t off);

// Disable a channel (FULL_OFF — output stays LOW regardless of count).
bool pca9685_channel_off(uint8_t addr, uint8_t channel);
