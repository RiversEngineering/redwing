#include "motor.h"
#include "pio_pwm.h"
#include "hardware/pwm.h"
#include "hardware/gpio.h"
#include "pico/stdlib.h"
#include "../protocol.h"

// PWM frequency target: 20 kHz.
// System clock = 125 MHz.  Divider 1, wrap = 125000000/20000 - 1 = 6249.
#define PWM_FREQ_HZ     20000
#define PWM_WRAP        ((SYS_CLK_HZ / PWM_FREQ_HZ) - 1)  // 6249

static void pwm_gpio_init_20khz(uint8_t gpio) {
    gpio_set_function(gpio, GPIO_FUNC_PWM);
    uint slice = pwm_gpio_to_slice_num(gpio);
    pwm_config cfg = pwm_get_default_config();
    pwm_config_set_clkdiv_int(&cfg, 1);
    pwm_config_set_wrap(&cfg, PWM_WRAP);
    pwm_init(slice, &cfg, true);
    pwm_set_gpio_level(gpio, 0);
}

// Convert -10000..+10000 to a hardware PWM level 0..PWM_WRAP
static uint16_t value_to_hw_level(int16_t value) {
    if (value < -10000) value = -10000;
    if (value >  10000) value =  10000;
    int32_t abs_val = (value < 0) ? -value : value;
    return (uint16_t)((abs_val * (int32_t)PWM_WRAP) / 10000);
}

// Convert -10000..+10000 to a PIO PWM duty threshold.
// PIO convention: output is HIGH from when the countdown y reaches x to y=0.
//   WRAP+1 → y never reaches WRAP+1 → fully OFF (0 %)
//   0      → y reaches 0 on the last tick only → ~0.05 % ON (minimum)
//   WRAP   → y reaches WRAP immediately → ~100 % ON (maximum)
// So larger threshold = more ON time — pass duty directly.
static uint16_t value_to_pio_level(int16_t value) {
    if (value < -10000) value = -10000;
    if (value >  10000) value =  10000;
    int32_t abs_val = (value < 0) ? -value : value;
    if (abs_val == 0) return (uint16_t)(PIO_PWM_WRAP + 1u);  // fully off
    uint32_t duty = ((uint32_t)abs_val * PIO_PWM_WRAP) / 10000;
    return (uint16_t)duty;
}

void motor_sm_init(uint8_t dir_gpio, uint8_t pwm_gpio) {
    gpio_init(dir_gpio);
    gpio_set_dir(dir_gpio, GPIO_OUT);
    gpio_put(dir_gpio, 0);

    if (pio_pwm_pin(pwm_gpio)) {
        pio_pwm_init(pwm_gpio);
    } else {
        pwm_gpio_init_20khz(pwm_gpio);
    }
}

void motor_sm_set(uint8_t dir_gpio, uint8_t pwm_gpio, int16_t value) {
    gpio_put(dir_gpio, value >= 0 ? 1 : 0);

    if (pio_pwm_pin(pwm_gpio)) {
        pio_pwm_set_level(pwm_gpio, value_to_pio_level(value));
    } else {
        pwm_set_gpio_level(pwm_gpio, value_to_hw_level(value));
    }
}

void motor_lap_init(uint8_t pwm_gpio) {
    pwm_gpio_init_20khz(pwm_gpio);
    pwm_set_gpio_level(pwm_gpio, PWM_WRAP / 2);  // 50% = stop
}

void motor_lap_set(uint8_t pwm_gpio, int16_t value) {
    if (value < -10000) value = -10000;
    if (value >  10000) value =  10000;
    int32_t mid   = PWM_WRAP / 2;
    int32_t level = mid + ((int32_t)value * mid) / 10000;
    if (level < 0)        level = 0;
    if (level > PWM_WRAP) level = PWM_WRAP;
    pwm_set_gpio_level(pwm_gpio, (uint16_t)level);
}

void motor_stop(uint8_t port_type, uint8_t pin_a, uint8_t pin_b) {
    if (port_type == PORT_MOTOR_SM) {
        motor_sm_set(pin_a, pin_b, 0);
    } else {
        motor_lap_set(pin_a, 0);
    }
}
