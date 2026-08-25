#include "port_manager.h"
#include "protocol.h"
#include "usb_comm.h"
#include "devices/motor.h"
#include "devices/servo.h"
#include "devices/encoder.h"
#include "devices/ultrasonic.h"
#include "devices/pio_pwm.h"
#include "devices/vl53l0x.h"
#include "devices/ir_distance.h"
#include "devices/bno085.h"
#include "devices/bno055.h"
#include "devices/mpu6050.h"
#include "hardware/gpio.h"
#include "hardware/pwm.h"
#include "hardware/i2c.h"
#include "hardware/uart.h"
#include "pico/stdlib.h"
#include <string.h>
#include <stdio.h>
#include <math.h>

// S0–S7 at [0–7], D0–D7 at [8–15], dedicated I2C at [16]
PortState ports[PORT_COUNT_TOTAL];

// I²C bus scan results — populated during init, sent with every PORT_I2C state.
static uint8_t _scan_count = 0;
static uint8_t _scan_addrs[8] = {0};

bool config_locked = false;

// UART0_PORT_ID / UART1_PORT_ID defined in port_manager.h
#define UART_DEFAULT_BAUD 115200u
#define UART_RX_BUF_MAX   64u

// Keep legacy alias so references in port_uart_tx/rx still resolve.
#define UART_PORT_ID UART0_PORT_ID

static inline uart_inst_t *uart_inst_for(uint8_t port_id) {
    return (port_id == UART0_PORT_ID) ? uart0 : uart1;
}


// ─── PWM slice helpers ────────────────────────────────────────────────────────

static inline uint8_t gpio_to_pwm_slice(uint8_t gpio) {
    return (gpio >> 1) & 0x7u;
}

static inline bool type_uses_pwm(uint8_t t) {
    return t == PORT_MOTOR_SM    || t == PORT_MOTOR_LAP  ||
           t == PORT_MOTOR_SERVO || t == PORT_SERVO;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

static bool valid_port(uint8_t port_id) {
    return IS_VALID_PORT(port_id);
}

static void port_deinit(uint8_t id) {
    PortState *p = &ports[id];
    switch (p->type) {
        case PORT_MOTOR_SM:
            motor_stop(p->type, p->pin_a, p->pin_b);
            pio_pwm_stop(p->pin_b);  // no-op for non-PIO pins
            break;
        case PORT_MOTOR_LAP:
            motor_stop(p->type, p->pin_a, p->pin_b);
            break;
        case PORT_MOTOR_SERVO:
            motor_stop(p->type, p->pin_a, p->pin_b);
            // Stop the PWM slice and release the pin, same as PORT_SERVO.
            {
                uint slice = pwm_gpio_to_slice_num(p->pin_a);
                pwm_set_enabled(slice, false);
                gpio_init(p->pin_a);
            }
            break;
        case PORT_SERVO: {
            // Stop the PWM slice and release the pin so the next port type
            // can claim it cleanly.  servo_set_raw_us() has already driven
            // the servo to its last commanded position; stopping the slice
            // here lets the servo hold that mechanically before going limp.
            uint slice = pwm_gpio_to_slice_num(p->pin_a);
            pwm_set_enabled(slice, false);
            gpio_init(p->pin_a);   // resets to SIO + input; clears GPIO_FUNC_PWM
            break;
        }
        case PORT_ENCODER:
            encoder_deinit(DUAL_SLOT(id));
            break;
        case PORT_ULTRASONIC:
            ultrasonic_deinit(DUAL_SLOT(id));
            break;
        case PORT_GPIO_IN:
        case PORT_GPIO_OUT:
            gpio_init(p->pin_a);
            break;
        case PORT_UART:
            uart_deinit(uart_inst_for(id));
            gpio_init(p->pin_a);
            gpio_init(p->pin_b);
            break;
        default:
            break;
    }
}

// ─── Init ────────────────────────────────────────────────────────────────────

void port_manager_init(void) {
    memset(ports, 0, sizeof(ports));
    config_locked = false;
    for (uint8_t i = 0; i < PORT_COUNT_TOTAL; i++) {
        ports[i].type         = PORT_UNCONFIGURED;
        ports[i].pin_a        = port_pin_a(i);
        ports[i].pin_b        = port_pin_b(i);   // NO_PIN for single-pin ports
        ports[i].enc_slot     = -1;
        ports[i].servo_min_us = SERVO_MIN_US_DEFAULT;
        ports[i].servo_max_us = SERVO_MAX_US_DEFAULT;
        ports[i].pid_kp           = 1.0f;
        ports[i].pid_ki           = 0.5f;
        ports[i].pid_kd           = 0.1f;
        ports[i].pid_integral_max = 0.0f;
        ports[i].pid_last_count   = 0;
        ports[i].pid_d_alpha      = 1.0f;
    }
    // Initialise I²C0 at 400 kHz on GP4 (SDA) / GP5 (SCL).
    // BNO085 breakout boards include onboard 4.7 kΩ pull-ups suitable for 400 kHz.
    i2c_init(i2c0, 400 * 1000);
    gpio_set_function(I2C_SDA_GPIO, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SCL_GPIO, GPIO_FUNC_I2C);
    gpio_pull_up(I2C_SDA_GPIO);
    gpio_pull_up(I2C_SCL_GPIO);

    // Give sensors time to fully power up. The RP2040 boots in ~10 ms; I²C
    // devices ACK their address almost immediately (just transistor logic) but
    // need more time before their internal registers are stable.  MPU-6050
    // datasheet spec is 30 ms; real-world boards — especially with heavier
    // decoupling capacitance — may need up to 100 ms.
    ports[PORT_ID_I2C].type = PORT_I2C;
    sleep_ms(100);
    for (int attempt = 0; attempt < 3; attempt++) {
        if (vl53l0x_init()) {
            ports[PORT_ID_I2C].type = PORT_VL53L0X;
            break;
        }
        sleep_ms(20);
    }

    // Auto-detect IMU: BNO085 (0x4A) → BNO055 (0x28) → MPU-6050/6500 (0x68).
    // Only one IMU is active; the first that responds wins.
    // Retry each candidate a few times to handle residual power-up transients.
    ports[PORT_ID_IMU].type = PORT_UNCONFIGURED;
    for (int attempt = 0; attempt < 3 && ports[PORT_ID_IMU].type == PORT_UNCONFIGURED; attempt++) {
        if (bno085_init()) {
            ports[PORT_ID_IMU].type = PORT_BNO085;
        } else if (bno055_init()) {
            ports[PORT_ID_IMU].type = PORT_BNO055;
        } else if (mpu6050_init()) {
            ports[PORT_ID_IMU].type = PORT_MPU6050;
        } else if (attempt < 2) {
            sleep_ms(20);
        }
    }

    // Scan the full I²C address space and record responding addresses.
    // Sent in every PORT_I2C state packet so the dashboard can display them.
    _scan_count = 0;
    uint8_t probe_byte;
    for (uint8_t addr = 0x08; addr < 0x78 && _scan_count < 8; addr++) {
        if (i2c_read_blocking(i2c0, addr, &probe_byte, 1, false) >= 0)
            _scan_addrs[_scan_count++] = addr;
    }
}

// ─── Configure ───────────────────────────────────────────────────────────────

bool port_configure(uint8_t id, uint8_t port_type) {
    if (!valid_port(id)) return false;

    if (IS_I2C_PORT(id) || IS_IMU_PORT(id)) {
        usb_comm_send_error(ERR_BAD_PORT, "dedicated port, not configurable");
        return false;
    }

    if (config_locked) {
        usb_comm_send_error(ERR_CONFIG_LOCKED, "configure after start");
        return false;
    }

    // PORT_UART must go through port_configure_uart() so both pins are claimed
    if (port_type == PORT_UART) return false;

    PortState *p = &ports[id];
    port_deinit(id);

    p->type           = port_type;
    p->motor_value    = 0;
    p->pid_enabled    = false;
    p->pos_pid_enabled = false;
    p->pid_integral   = 0.0f;
    p->pid_last_error = 0.0f;
    p->enc_slot       = -1;

    uint8_t a = p->pin_a;
    uint8_t b = p->pin_b;   // NO_PIN if single-pin port

    switch (port_type) {
        case PORT_MOTOR_SM:
            if (b == NO_PIN) return false;   // sign-magnitude needs two pins
            motor_sm_init(a, b);
            break;

        case PORT_MOTOR_LAP:
            motor_lap_init(a);
            break;

        case PORT_MOTOR_SERVO:
            // RC ESC protocol: 1500µs = stop, 1100µs = full reverse, 1900µs = full forward.
            p->servo_min_us = 1100;
            p->servo_max_us = 1900;
            servo_init(a, p->servo_min_us, p->servo_max_us);
            break;

        case PORT_SERVO:
            p->servo_pulse_us = 1500;  // start at midpoint
            servo_init(a, p->servo_min_us, p->servo_max_us);
            break;

        case PORT_ENCODER:
            if (b == NO_PIN) return false;
            encoder_init(DUAL_SLOT(id), a, b);
            p->enc_self_slot = DUAL_SLOT(id);
            break;

        case PORT_ULTRASONIC:
            if (b == NO_PIN) return false;
            ultrasonic_init(DUAL_SLOT(id), a, b);
            p->us_slot = DUAL_SLOT(id);
            break;

        case PORT_I2C:
            // I2C peripheral is managed by the Pi over USB; we just mark the pins reserved.
            break;

        case PORT_GPIO_IN:
            gpio_init(a);
            gpio_set_dir(a, GPIO_IN);
            gpio_pull_up(a);
            break;

        case PORT_GPIO_OUT:
            gpio_init(a);
            gpio_set_drive_strength(a, GPIO_DRIVE_STRENGTH_12MA);
            gpio_set_dir(a, GPIO_OUT);
            gpio_put(a, 0);
            p->gpio_state = 0;
            break;

        case PORT_IR_DISTANCE:
            // Only GP26/27/28 (S5/S6/S7) support ADC.
            if (a < 26) {
                p->type = PORT_UNCONFIGURED;
                return false;
            }
            ir_distance_adc_init(a);
            break;

        case PORT_UNCONFIGURED:
            break;

        default:
            p->type = PORT_UNCONFIGURED;
            return false;
    }
    return true;
}

// ─── UART configuration ───────────────────────────────────────────────────────

bool port_configure_uart(uint8_t port_id, uint32_t baud) {
    if (config_locked) {
        usb_comm_send_error(ERR_CONFIG_LOCKED, "configure after start");
        return false;
    }
    if (port_id != UART0_PORT_ID && port_id != UART1_PORT_ID) {
        usb_comm_send_error(ERR_BAD_PORT, "UART only on D6/D7");
        return false;
    }

    uint32_t actual_baud = (baud > 0) ? baud : UART_DEFAULT_BAUD;
    uint8_t  slot = port_id - PORT_ID_DUAL_BASE;   // 6 for D6, 7 for D7

    port_deinit(port_id);
    uart_init(uart_inst_for(port_id), actual_baud);
    gpio_set_function(DUAL_GPIO[slot][0], GPIO_FUNC_UART);  // TX pin
    gpio_set_function(DUAL_GPIO[slot][1], GPIO_FUNC_UART);  // RX pin

    ports[port_id].type = PORT_UART;
    return true;
}

// ─── Config finalisation and lock ─────────────────────────────────────────────

// PWM frequency groups — ports in different groups cannot share a slice.
// 0 = 50 Hz  (PORT_SERVO, PORT_MOTOR_SERVO)
// 1 = 20 kHz (PORT_MOTOR_LAP, PORT_MOTOR_SM)
static uint8_t pwm_freq_group(uint8_t type) {
    return (type == PORT_MOTOR_LAP || type == PORT_MOTOR_SM) ? 1u : 0u;
}

bool port_config_done(void) {
    if (config_locked) return true;  // idempotent

    // Per-slice: 0xFF = unowned; low nibble = freq group (0/1); high nibble = port index.
    // Use separate arrays for clarity.
    uint8_t slice_freq[8];   // freq group that claimed the slice
    uint8_t slice_owner[8];  // port index that claimed the slice
    memset(slice_freq,  0xFF, sizeof(slice_freq));
    memset(slice_owner, 0xFF, sizeof(slice_owner));

    for (uint8_t i = 0; i < PORT_COUNT_TOTAL; i++) {
        PortState *p = &ports[i];
        uint8_t pwm_gpio;
        uint8_t freq;

        // Determine which GPIO actually carries PWM and its frequency group.
        switch (p->type) {
            case PORT_SERVO:
            case PORT_MOTOR_SERVO:
                pwm_gpio = p->pin_a;
                freq     = 0;   // 50 Hz
                break;
            case PORT_MOTOR_LAP:
                pwm_gpio = p->pin_a;
                freq     = 1;   // 20 kHz
                break;
            case PORT_MOTOR_SM:
                // pin_a is direction GPIO; pin_b carries PWM.
                if (p->pin_b == NO_PIN) continue;
                if (pio_pwm_pin(p->pin_b)) continue;  // PIO-managed: no hw slice conflict
                pwm_gpio = p->pin_b;
                freq     = 1;   // 20 kHz
                break;
            default:
                continue;   // no PWM
        }

        uint8_t slice = gpio_to_pwm_slice(pwm_gpio);
        if (slice_freq[slice] != 0xFF && slice_freq[slice] != freq) {
            char msg[40];
            snprintf(msg, sizeof(msg), "PWM conflict P%u+P%u slice %u",
                     (unsigned)slice_owner[slice], (unsigned)i, (unsigned)slice);
            usb_comm_send_error(ERR_PORT_CONFLICT, msg);
            return false;
        }
        slice_freq[slice]  = freq;
        slice_owner[slice] = i;
    }

    config_locked = true;
    return true;
}

// ─── UART I/O ─────────────────────────────────────────────────────────────────

void port_uart_tx(uint8_t port_id, const uint8_t *data, uint8_t len) {
    if (ports[port_id].type != PORT_UART) return;
    uart_write_blocking(uart_inst_for(port_id), data, len);
}

uint8_t port_uart_rx(uint8_t port_id, uint8_t *buf) {
    if (ports[port_id].type != PORT_UART) return 0;
    uart_inst_t *inst = uart_inst_for(port_id);
    uint8_t n = 0;
    while (n < UART_RX_BUF_MAX && uart_is_readable(inst)) {
        buf[n++] = (uint8_t)uart_getc(inst);
    }
    return n;
}

// ─── Motor / servo control ───────────────────────────────────────────────────

void port_set_motor(uint8_t id, int16_t value) {
    if (!valid_port(id)) return;
    PortState *p = &ports[id];
    p->motor_value = value;
    p->pid_enabled     = false;   // direct power overrides both PID modes
    p->pos_pid_enabled = false;

    uint8_t a = p->pin_a;
    uint8_t b = p->pin_b;

    switch (p->type) {
        case PORT_MOTOR_SM:
            motor_sm_set(a, b, value);
            break;
        case PORT_MOTOR_LAP:
            motor_lap_set(a, value);
            break;
        case PORT_MOTOR_SERVO: {
            uint16_t mid   = (p->servo_min_us + p->servo_max_us) / 2;
            uint16_t range = (p->servo_max_us - p->servo_min_us) / 2;
            int32_t  pulse = (int32_t)mid + ((int32_t)value * (int32_t)range) / 10000;
            servo_set_raw_us(a, (uint16_t)pulse, p->servo_min_us, p->servo_max_us);
            break;
        }
        default: break;
    }
}

void port_set_servo(uint8_t id, uint16_t pulse_us) {
    if (!valid_port(id)) return;
    PortState *p = &ports[id];
    if (p->type != PORT_SERVO) return;
    p->servo_pulse_us = pulse_us;
    servo_set_raw_us(p->pin_a, pulse_us, p->servo_min_us, p->servo_max_us);
}

void port_set_servo_range(uint8_t id, uint16_t min_us, uint16_t max_us) {
    if (!valid_port(id)) return;
    PortState *p = &ports[id];
    p->servo_min_us = min_us;
    p->servo_max_us = max_us;
    if (p->type == PORT_SERVO) {
        servo_set_raw_us(p->pin_a, p->servo_pulse_us, min_us, max_us);
    }
}

// ─── Encoder / PID ───────────────────────────────────────────────────────────

void port_attach_encoder(uint8_t motor_id, uint8_t encoder_id) {
    if (!valid_port(motor_id) || !valid_port(encoder_id)) return;
    PortState *mp = &ports[motor_id];
    PortState *ep = &ports[encoder_id];
    if (ep->type != PORT_ENCODER) return;

    mp->enc_slot      = (int8_t)DUAL_SLOT(encoder_id);
    mp->pid_enabled   = false;
    mp->pid_integral  = 0.0f;
    mp->pid_last_error = 0.0f;
}

void port_set_velocity(uint8_t id, int32_t velocity_x10) {
    if (!valid_port(id)) return;
    PortState *p = &ports[id];
    if (p->enc_slot < 0) return;
    p->pid_target      = velocity_x10;
    p->pid_enabled     = true;
    p->pos_pid_enabled = false;
    p->pid_integral    = 0.0f;
    p->pid_last_error  = 0.0f;
}

void port_set_position(uint8_t id, int32_t target, uint16_t speed_limit, bool keep_integral) {
    if (!valid_port(id)) return;
    PortState *p = &ports[id];
    if (p->enc_slot < 0) return;
    if (!p->pos_pid_enabled) {
        // First enable: seed ramp setpoint and derivative state from current encoder.
        int32_t current      = encoder_get_count((uint8_t)p->enc_slot);
        p->pos_ramp_setpoint = (float)current;
        p->pid_last_count    = current;
        p->pid_d_prev        = 0.0f;
    }
    p->pos_target      = target;
    p->pos_speed_limit = speed_limit;
    p->pos_pid_enabled = true;
    p->pid_enabled     = false;
    if (!keep_integral) {
        p->pid_integral = 0.0f;
    }
}

void port_set_encoder_inverted(uint8_t id, bool inverted) {
    if (!valid_port(id)) return;
    PortState *p = &ports[id];
    if (p->type != PORT_ENCODER) return;
    encoder_set_inverted(p->enc_self_slot, inverted);
}

void port_set_pos_options(uint8_t id, float deadband, float output_floor, float ramp_rate, float d_alpha, float approach_factor) {
    if (!valid_port(id)) return;
    PortState *p = &ports[id];
    p->pos_deadband       = (deadband > 0.0f)                         ? deadband       : 0.0f;
    p->pos_output_floor   = (output_floor > 0.0f)                     ? output_floor   : 0.0f;
    p->pos_ramp_rate      = (ramp_rate > 0.0f)                        ? ramp_rate      : 0.0f;
    p->pid_d_alpha        = (d_alpha > 0.0f && d_alpha <= 1.0f)       ? d_alpha        : 1.0f;
    p->pos_approach_factor = (approach_factor > 0.0f && approach_factor <= 1.0f) ? approach_factor : 0.0f;
}

void port_set_pid(uint8_t id, float kp, float ki, float kd) {
    if (!valid_port(id)) return;
    ports[id].pid_kp = kp;
    ports[id].pid_ki = ki;
    ports[id].pid_kd = kd;
}

void port_reset_encoder(uint8_t id) {
    if (!valid_port(id)) return;
    if (ports[id].type == PORT_ENCODER) {
        encoder_reset(DUAL_SLOT(id));
    }
}

// ─── GPIO ────────────────────────────────────────────────────────────────────

void port_set_gpio(uint8_t id, uint8_t state) {
    if (!valid_port(id)) return;
    PortState *p = &ports[id];
    if (p->type != PORT_GPIO_OUT) return;
    p->gpio_state = state;
    gpio_put(p->pin_a, state);
}

// ─── Stop all ────────────────────────────────────────────────────────────────

void port_stop_all(void) {
    for (uint8_t i = 0; i < PORT_COUNT_TOTAL; i++) {
        PortState *p = &ports[i];
        p->pid_enabled     = false;
        p->pos_pid_enabled = false;
        p->pid_integral    = 0.0f;
        switch (p->type) {
            case PORT_MOTOR_SM:
                motor_sm_set(p->pin_a, p->pin_b, 0);
                p->motor_value = 0;
                break;
            case PORT_MOTOR_LAP:
                motor_lap_set(p->pin_a, 0);
                p->motor_value = 0;
                break;
            case PORT_MOTOR_SERVO:
                servo_set_raw_us(p->pin_a, 1500, p->servo_min_us, p->servo_max_us);
                p->motor_value = 0;
                break;
            default: break;
        }
    }
}

void port_reset(void) {
    // Stop all motor outputs. Servo PWM hardware keeps running so servos hold
    // their last commanded position — no mechanical jerk on program restart.
    port_stop_all();
    config_locked = false;

    for (uint8_t i = 0; i < PORT_COUNT_TOTAL; i++) {
        if (IS_I2C_PORT(i) || IS_IMU_PORT(i)) continue;  // dedicated ports: always reserved
        PortState *p = &ports[i];
        port_deinit(i);   // clean up encoder PIO, ultrasonic, GPIO state
        p->type           = PORT_UNCONFIGURED;
        p->motor_value     = 0;
        p->pid_enabled     = false;
        p->pos_pid_enabled = false;
        p->pid_integral    = 0.0f;
        p->pid_last_error  = 0.0f;
        p->enc_slot        = -1;
    }
}

// ─── PID (called at 100 Hz from repeating timer) ─────────────────────────────

void port_pid_update(void) {
    const float dt = 0.01f;

    for (uint8_t i = 0; i < PORT_COUNT_TOTAL; i++) {
        PortState *p = &ports[i];
        if (p->enc_slot < 0) continue;

        float output = 0.0f;

        if (p->pid_enabled) {
            // Velocity PID — derivative on error
            float measured   = (float)encoder_get_velocity((uint8_t)p->enc_slot) / 10.0f;
            float target     = (float)p->pid_target / 10.0f;
            float error      = target - measured;
            float derivative = (error - p->pid_last_error) / dt;
            p->pid_last_error = error;

            p->pid_integral += error * dt;
            if (p->pid_integral_max > 0.0f) {
                if (p->pid_integral >  p->pid_integral_max) p->pid_integral =  p->pid_integral_max;
                if (p->pid_integral < -p->pid_integral_max) p->pid_integral = -p->pid_integral_max;
            }

            output = p->pid_kp * error + p->pid_ki * p->pid_integral + p->pid_kd * derivative;
            if (output >  100.0f) { output =  100.0f; p->pid_integral -= error * dt; }
            if (output < -100.0f) { output = -100.0f; p->pid_integral -= error * dt; }

        } else if (p->pos_pid_enabled) {
            int32_t current = encoder_get_count((uint8_t)p->enc_slot);

            // Setpoint ramp: move pos_ramp_setpoint toward pos_target at pos_ramp_rate ticks/s.
            if (p->pos_ramp_rate > 0.0f) {
                float step = p->pos_ramp_rate * dt;
                float diff = (float)p->pos_target - p->pos_ramp_setpoint;
                // Approach factor: decelerate the ramp as it nears the final target.
                // step is capped to |remaining| × factor, so the ramp slows proportionally.
                if (p->pos_approach_factor > 0.0f) {
                    float approach_step = fabsf(diff) * p->pos_approach_factor;
                    if (approach_step < step) step = approach_step;
                }
                if (fabsf(diff) <= step) {
                    p->pos_ramp_setpoint = (float)p->pos_target;
                } else {
                    p->pos_ramp_setpoint += (diff > 0.0f) ? step : -step;
                }
            } else {
                p->pos_ramp_setpoint = (float)p->pos_target;
            }

            float error = p->pos_ramp_setpoint - (float)current;

            // Derivative on measurement with EMA low-pass filter.
            float d_raw      = -(float)(current - p->pid_last_count) / dt;
            p->pid_last_count = current;
            float derivative  = p->pid_d_alpha * d_raw + (1.0f - p->pid_d_alpha) * p->pid_d_prev;
            p->pid_d_prev     = derivative;

            float limit = (p->pos_speed_limit > 0) ? (float)p->pos_speed_limit / 100.0f : 100.0f;

            if (p->pos_deadband > 0.0f && fabsf(error) <= p->pos_deadband) {
                // Inside deadband: freeze integral, reset filter state, command zero.
                p->pid_d_prev = 0.0f;
                output = 0.0f;
            } else {
                p->pid_integral += error * dt;
                if (p->pid_integral_max > 0.0f) {
                    if (p->pid_integral >  p->pid_integral_max) p->pid_integral =  p->pid_integral_max;
                    if (p->pid_integral < -p->pid_integral_max) p->pid_integral = -p->pid_integral_max;
                }

                output = p->pid_kp * error + p->pid_ki * p->pid_integral + p->pid_kd * derivative;
                if (output >  limit) { output =  limit; p->pid_integral -= error * dt; }
                if (output < -limit) { output = -limit; p->pid_integral -= error * dt; }

                // Output floor: guarantee minimum output to overcome stiction.
                if (p->pos_output_floor > 0.0f &&
                    fabsf(output) > 0.0f && fabsf(output) < p->pos_output_floor) {
                    output = (output > 0.0f) ? p->pos_output_floor : -p->pos_output_floor;
                }
            }
        } else {
            continue;
        }

        int16_t cmd = (int16_t)(output * 100.0f);
        p->motor_value = cmd;

        switch (p->type) {
            case PORT_MOTOR_SM:
                motor_sm_set(p->pin_a, p->pin_b, cmd);
                break;
            case PORT_MOTOR_LAP:
                motor_lap_set(p->pin_a, cmd);
                break;
            case PORT_MOTOR_SERVO: {
                uint16_t mid   = (p->servo_min_us + p->servo_max_us) / 2;
                uint16_t range = (p->servo_max_us - p->servo_min_us) / 2;
                int32_t  pulse = (int32_t)mid + ((int32_t)cmd * (int32_t)range) / 10000;
                servo_set_raw_us(p->pin_a, (uint16_t)pulse, p->servo_min_us, p->servo_max_us);
                break;
            }
            default: break;
        }
    }
}

// ─── State packet builder ─────────────────────────────────────────────────────

void port_send_state(void) {
    // Re-broadcast the BNO085 init diagnostic every ~5 s while IMU is absent,
    // so the dashboard shows it even if the daemon wasn't connected at boot.
    {
        static uint16_t _imu_diag_ctr = 0;
        if (ports[PORT_ID_IMU].type == PORT_UNCONFIGURED) {
            if (_imu_diag_ctr == 0) {
                const char *d = bno085_get_diag();
                if (d[0] != '\0') usb_comm_send_log(d);
            }
            if (++_imu_diag_ctr >= 250u) _imu_diag_ctr = 0;  // 250 × 20 ms = 5 s at 50 Hz
        }
    }

    uint8_t buf[PROTO_MAX_LEN];
    uint8_t pos = 0;

    uint32_t ts = to_ms_since_boot(get_absolute_time());
    buf[pos++] = (uint8_t)(ts);
    buf[pos++] = (uint8_t)(ts >> 8);
    buf[pos++] = (uint8_t)(ts >> 16);
    buf[pos++] = (uint8_t)(ts >> 24);

    uint8_t count_pos = pos++;
    uint8_t count = 0;

    for (uint8_t i = 0; i < PORT_COUNT_TOTAL; i++) {
        PortState *p = &ports[i];
        if (p->type == PORT_UNCONFIGURED) continue;
        if (pos + 16 > PROTO_MAX_LEN) break;

        buf[pos++] = i;        // port_id
        buf[pos++] = p->type;  // port_type

        switch (p->type) {
            case PORT_MOTOR_SM:
            case PORT_MOTOR_LAP:
            case PORT_MOTOR_SERVO: {
                int16_t v = p->motor_value;
                buf[pos++] = (uint8_t)(v);
                buf[pos++] = (uint8_t)(v >> 8);
                break;
            }
            case PORT_SERVO: {
                uint16_t us = p->servo_pulse_us;
                buf[pos++] = (uint8_t)(us);
                buf[pos++] = (uint8_t)(us >> 8);
                break;
            }
            case PORT_ENCODER: {
                int32_t cnt = encoder_get_count(DUAL_SLOT(i));
                int32_t vel = encoder_get_velocity(DUAL_SLOT(i));
                buf[pos++] = (uint8_t)(cnt);       buf[pos++] = (uint8_t)(cnt >> 8);
                buf[pos++] = (uint8_t)(cnt >> 16); buf[pos++] = (uint8_t)(cnt >> 24);
                buf[pos++] = (uint8_t)(vel);       buf[pos++] = (uint8_t)(vel >> 8);
                buf[pos++] = (uint8_t)(vel >> 16); buf[pos++] = (uint8_t)(vel >> 24);
                break;
            }
            case PORT_ULTRASONIC: {
                uint16_t dist; uint8_t valid;
                ultrasonic_read(DUAL_SLOT(i), &dist, &valid);
                buf[pos++] = (uint8_t)(dist);
                buf[pos++] = (uint8_t)(dist >> 8);
                buf[pos++] = valid;
                break;
            }
            case PORT_I2C:
                // 9 bytes: [count] + [8 addresses, zero-padded]
                buf[pos++] = _scan_count;
                for (int k = 0; k < 8; k++)
                    buf[pos++] = (k < _scan_count) ? _scan_addrs[k] : 0u;
                break;
            case PORT_VL53L0X: {
                bool valid;
                uint16_t dist = vl53l0x_read_mm(&valid);
                buf[pos++] = (uint8_t)(dist);
                buf[pos++] = (uint8_t)(dist >> 8);
                buf[pos++] = valid ? 1u : 0u;
                break;
            }
            case PORT_IR_DISTANCE: {
                bool valid;
                uint16_t dist = ir_distance_read_mm(p->pin_a - 26u, &valid);
                buf[pos++] = (uint8_t)(dist);
                buf[pos++] = (uint8_t)(dist >> 8);
                buf[pos++] = valid ? 1u : 0u;
                break;
            }
            case PORT_BNO085: {
                bno085_poll();
                int16_t qx, qy, qz, qw, ax, ay, az;
                bno085_get_quat(&qx, &qy, &qz, &qw);
                bno085_get_linear_accel(&ax, &ay, &az);
                // 14 bytes: qw, qx, qy, qz, ax, ay, az  (all int16 LE)
                int16_t v7[7] = {qw, qx, qy, qz, ax, ay, az};
                for (int k = 0; k < 7; k++) {
                    buf[pos++] = (uint8_t)(v7[k]);
                    buf[pos++] = (uint8_t)((uint16_t)v7[k] >> 8);
                }
                break;
            }
            case PORT_BNO055: {
                int16_t qw, qx, qy, qz, ax, ay, az;
                if (bno055_read(&qw, &qx, &qy, &qz, &ax, &ay, &az)) {
                    int16_t v7[7] = {qw, qx, qy, qz, ax, ay, az};
                    for (int k = 0; k < 7; k++) {
                        buf[pos++] = (uint8_t)(v7[k]);
                        buf[pos++] = (uint8_t)((uint16_t)v7[k] >> 8);
                    }
                } else {
                    for (int k = 0; k < 14; k++) buf[pos++] = 0;
                }
                break;
            }
            case PORT_MPU6050: {
                int16_t ax, ay, az, gx, gy, gz;
                if (mpu6050_read(&ax, &ay, &az, &gx, &gy, &gz)) {
                    int16_t v6[6] = {ax, ay, az, gx, gy, gz};
                    for (int k = 0; k < 6; k++) {
                        buf[pos++] = (uint8_t)(v6[k]);
                        buf[pos++] = (uint8_t)((uint16_t)v6[k] >> 8);
                    }
                } else {
                    for (int k = 0; k < 12; k++) buf[pos++] = 0;
                }
                break;
            }
            case PORT_GPIO_IN:
                buf[pos++] = gpio_get(p->pin_a) ? 1 : 0;
                break;
            case PORT_GPIO_OUT:
                buf[pos++] = p->gpio_state;
                break;
            default: break;
        }
        count++;
    }

    buf[count_pos] = count;
    usb_comm_send(RESP_STATE, buf, pos);
}
