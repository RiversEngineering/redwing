#include "servo.h"
#include "hardware/pwm.h"
#include "hardware/gpio.h"
#include "pico/stdlib.h"

// For 50 Hz servo PWM with a 20 ms period:
// SYS_CLK = 125 MHz.  Use clkdiv=64, wrap=39062  → 125e6/64/39063 ≈ 50.00 Hz.
// One count = 64/125e6 = 0.512 µs, so counts_per_us = 125000000 / 64 / 1000000
//           = 1.953125 → use integer: level = pulse_us * 125000000 / 64 / 1000000
//           = pulse_us * 125 / 64   (simplified, done in 32-bit)
#define SERVO_CLK_DIV   64
#define SERVO_WRAP      39062   // (125000000 / 64 / 50) - 1

// Convert microseconds to PWM wrap counts
static uint16_t us_to_level(uint16_t us) {
    // level = us * (SYS_CLK / clkdiv / 1e6)
    //       = us * 125000000 / 64 / 1000000
    //       = us * 1953125 / 1000000  → avoid overflow: us * 125 / 64
    return (uint16_t)((uint32_t)us * 125u / 64u);
}

void servo_init(uint8_t gpio, uint16_t min_us, uint16_t max_us) {
    (void)min_us; (void)max_us;  // stored in port_manager, not here
    gpio_set_function(gpio, GPIO_FUNC_PWM);
    uint slice = pwm_gpio_to_slice_num(gpio);
    pwm_config cfg = pwm_get_default_config();
    pwm_config_set_clkdiv_int(&cfg, SERVO_CLK_DIV);
    pwm_config_set_wrap(&cfg, SERVO_WRAP);
    pwm_init(slice, &cfg, true);
    // Default to 1500 µs (midpoint)
    pwm_set_gpio_level(gpio, us_to_level(1500));
}

void servo_set(uint8_t gpio, uint16_t angle_cd, uint16_t min_us, uint16_t max_us) {
    // angle_cd: 0-18000 centidegrees → pulse min_us..max_us
    if (angle_cd > 18000) angle_cd = 18000;
    uint32_t range_us  = max_us - min_us;
    uint32_t pulse_us  = min_us + (uint32_t)angle_cd * range_us / 18000;
    pwm_set_gpio_level(gpio, us_to_level((uint16_t)pulse_us));
}

void servo_set_raw_us(uint8_t gpio, uint16_t pulse_us, uint16_t min_us, uint16_t max_us) {
    if (pulse_us < min_us) pulse_us = min_us;
    if (pulse_us > max_us) pulse_us = max_us;
    pwm_set_gpio_level(gpio, us_to_level(pulse_us));
}
