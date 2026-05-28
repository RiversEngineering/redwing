#include "port_manager.h"
#include "protocol.h"
#include "usb_comm.h"
#include "devices/motor.h"
#include "devices/servo.h"
#include "devices/encoder.h"
#include "devices/ultrasonic.h"
#include "devices/pio_pwm.h"
#include "hardware/gpio.h"
#include "hardware/uart.h"
#include "pico/stdlib.h"
#include <string.h>
#include <stdio.h>

// S0–S7 at [0–7], D0–D7 at [8–15], dedicated I2C at [16]
PortState ports[PORT_COUNT_TOTAL];

bool config_locked = false;

// UART0 on D7: GP12 = TX (pin A), GP13 = RX (pin B)
// UART1 on D6: GP24 = TX (pin A), GP25 = RX (pin B)
#define UART0_PORT_ID     15u   // D7
#define UART1_PORT_ID     14u   // D6
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
        case PORT_MOTOR_SERVO:
            motor_stop(p->type, p->pin_a, p->pin_b);
            break;
        case PORT_SERVO:
            break;  // leave at midpoint — safe
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
        ports[i].pid_kp       = 1.0f;
        ports[i].pid_ki       = 0.5f;
        ports[i].pid_kd       = 0.1f;
    }
    // Dedicated I2C port is always reserved — GP4/GP5 are never reconfigurable.
    ports[PORT_ID_I2C].type = PORT_I2C;
}

// ─── Configure ───────────────────────────────────────────────────────────────

bool port_configure(uint8_t id, uint8_t port_type) {
    if (!valid_port(id)) return false;

    if (IS_I2C_PORT(id)) {
        usb_comm_send_error(ERR_BAD_PORT, "I2C port is dedicated");
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
            gpio_set_dir(a, GPIO_OUT);
            gpio_put(a, 0);
            p->gpio_state = 0;
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
    p->pid_enabled = false;   // direct power overrides PID

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
    servo_set_raw_us(p->pin_a, pulse_us, 500, 2500);
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
    p->pid_target  = velocity_x10;
    p->pid_enabled = true;
    p->pid_integral = 0.0f;
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
        p->pid_enabled = false;
        p->pid_integral = 0.0f;
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
        if (IS_I2C_PORT(i)) continue;   // dedicated I2C always stays reserved
        PortState *p = &ports[i];
        port_deinit(i);   // clean up encoder PIO, ultrasonic, GPIO state
        p->type           = PORT_UNCONFIGURED;
        p->motor_value    = 0;
        p->pid_enabled    = false;
        p->pid_integral   = 0.0f;
        p->pid_last_error = 0.0f;
        p->enc_slot       = -1;
    }
}

// ─── PID (called at 100 Hz from repeating timer) ─────────────────────────────

void port_pid_update(void) {
    const float dt = 0.01f;

    for (uint8_t i = 0; i < PORT_COUNT_TOTAL; i++) {
        PortState *p = &ports[i];
        if (!p->pid_enabled || p->enc_slot < 0) continue;

        int32_t measured = encoder_get_velocity((uint8_t)p->enc_slot);
        float error      = (float)(p->pid_target - measured);

        p->pid_integral  += error * dt;
        float derivative  = (error - p->pid_last_error) / dt;
        p->pid_last_error = error;

        float output = p->pid_kp * error
                     + p->pid_ki * p->pid_integral
                     + p->pid_kd * derivative;

        if (output >  10000.0f) { output =  10000.0f; p->pid_integral -= error * dt; }
        if (output < -10000.0f) { output = -10000.0f; p->pid_integral -= error * dt; }

        int16_t cmd = (int16_t)output;
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
                break;
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
