#include "ir_distance.h"
#include "hardware/adc.h"
#include "hardware/gpio.h"
#include <math.h>

// Sharp GP2Y0A21YK0F distance formula: D_cm = 27.86 × V^(-1.15)
// Signal connected directly to ADC (no voltage divider — max output ≈ 3.1V at 5V VCC).
//   V = raw × 3.3 / 4095
// Valid output range: 10–80 cm. Below 10 cm the response curve is non-monotonic.

// Per-channel EMA state (-1 = uninitialized). Three channels: ADC0/1/2 → S5/S6/S7.
// EMA alpha ≈ 0.3:  ema = (3 * raw + 7 * ema) / 10
// Smooths the ~39 ms sensor update cycle without feeling sluggish.
static int32_t _ema[3] = {-1, -1, -1};

void ir_distance_adc_init(uint8_t gpio) {
    adc_init();
    adc_gpio_init(gpio);
    // Reset EMA state for this channel so a new sensor gets a clean start.
    if (gpio >= 26 && gpio <= 28) _ema[gpio - 26] = -1;
}

uint16_t ir_distance_read_mm(uint8_t adc_channel, bool *valid) {
    adc_select_input(adc_channel);

    // 16-sample burst average — reduces quantisation and ADC thermal noise.
    uint32_t sum = 0;
    for (int i = 0; i < 16; i++) sum += adc_read();
    int32_t raw = (int32_t)(sum / 16);

    // EMA across state-update calls — smooths cycle-to-cycle variation.
    if (_ema[adc_channel] < 0) {
        _ema[adc_channel] = raw;          // seed on first call
    } else {
        _ema[adc_channel] = (3 * raw + 7 * _ema[adc_channel]) / 10;
    }
    raw = _ema[adc_channel];

    if (raw < 10) {
        *valid = false;
        return 0;
    }

    float v       = (float)raw * (3.3f / 4095.0f);
    float dist_cm = 27.86f * powf(v, -1.15f);

    if (dist_cm < 10.0f || dist_cm > 80.0f) {
        *valid = false;
        return 0;
    }

    *valid = true;
    return (uint16_t)(dist_cm * 10.0f);
}
