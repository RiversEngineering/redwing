#include "ir_distance.h"
#include "hardware/adc.h"
#include "hardware/gpio.h"
#include <math.h>

// Sharp GP2Y0A21YK0F distance formula: D_cm = 27.86 × V^(-1.15)
// Signal connected directly to ADC (no voltage divider needed — max output ≈ 3.1V at 5V VCC).
//   V = raw × 3.3 / 4095
// Valid output range: 10–80 cm. Below 10 cm the response curve is non-monotonic.

void ir_distance_adc_init(uint8_t gpio) {
    adc_init();
    adc_gpio_init(gpio);
}

uint16_t ir_distance_read_mm(uint8_t adc_channel, bool *valid) {
    adc_select_input(adc_channel);

    // Average 4 samples to reduce ADC noise.
    uint32_t sum = 0;
    for (int i = 0; i < 4; i++) {
        sum += adc_read();
    }
    uint16_t raw = (uint16_t)(sum / 4);

    if (raw < 10) {
        *valid = false;
        return 0;
    }

    float v_actual = (float)raw * (3.3f / 4095.0f);
    float dist_cm  = 27.86f * powf(v_actual, -1.15f);

    if (dist_cm < 10.0f || dist_cm > 80.0f) {
        *valid = false;
        return 0;
    }

    *valid = true;
    return (uint16_t)(dist_cm * 10.0f);
}
