#pragma once
#include <stdint.h>
#include <stdbool.h>

// Bosch BNO085 — 9-axis fusion IMU using SHTP over I2C.
// I2C address: 0x4A (ADDR=LOW) or 0x4B (ADDR=HIGH).
// Quaternion output: Q14 (divide by 16384 to get float).
// Linear acceleration output: Q8 (divide by 256 to get m/s²).

bool bno085_init(void);

// Drain any pending SHTP input-report packets and cache the latest values.
// Call before each state read to keep data fresh.
void bno085_poll(void);

void bno085_get_quat(int16_t *qx, int16_t *qy, int16_t *qz, int16_t *qw);
void bno085_get_linear_accel(int16_t *ax, int16_t *ay, int16_t *az);
