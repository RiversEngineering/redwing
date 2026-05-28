#pragma once
#include <stdint.h>
#include <stdbool.h>

/**
 * Lightweight VL53L0X ToF sensor driver for RP2040.
 *
 * Requires i2c0 to be initialised at 400 kHz on GP4 (SDA) / GP5 (SCL)
 * before calling vl53l0x_init().  All functions are safe to call even
 * if the sensor was never detected — they return 0 / false gracefully.
 *
 * Typical usage:
 *   bool ok = vl53l0x_init();            // call once at startup
 *   // ... in main loop:
 *   bool valid;
 *   uint16_t mm = vl53l0x_read_mm(&valid); // non-blocking, cached
 */

/** Probe, initialise the sensor, and start continuous back-to-back ranging.
 *  Returns true on success, false if the sensor is absent or init fails. */
bool vl53l0x_init(void);

/** Return the most recent distance reading in millimetres (non-blocking).
 *  Sets *valid to false when out of range or sensor absent.
 *  Returns the cached value from the previous interrupt if no new data
 *  is ready yet — suitable for calling at the 50 Hz state-send rate. */
uint16_t vl53l0x_read_mm(bool *valid);

/** Stop continuous ranging (e.g. before re-init). */
void vl53l0x_stop(void);
