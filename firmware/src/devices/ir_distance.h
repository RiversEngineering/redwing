#pragma once
#include <stdint.h>
#include <stdbool.h>

// Sharp GP2Y0A21YK0F (10–80 cm) IR distance sensor.
// Requires a 10kΩ/10kΩ voltage divider on the output to stay within the RP2040's 3.3V ADC limit.
// Only valid on ADC-capable GPIOs: GP26 (ADC0/S5), GP27 (ADC1/S6), GP28 (ADC2/S7).

void     ir_distance_adc_init(uint8_t gpio);
uint16_t ir_distance_read_mm(uint8_t adc_channel, bool *valid);
