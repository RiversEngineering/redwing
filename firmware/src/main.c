#include "pico/stdlib.h"
#include "pico/time.h"
#include "hardware/gpio.h"
#include "protocol.h"
#include "crc8.h"
#include "usb_comm.h"
#include "port_manager.h"
#include "devices/encoder.h"
#include "devices/ultrasonic.h"
#include "devices/pca9685.h"
#include <string.h>

// ─── Configurable stream rate ─────────────────────────────────────────────────
static uint16_t stream_rate_hz = 50;   // default 50 Hz

// ─── Watchdog ─────────────────────────────────────────────────────────────────
// If no packet is received for WATCHDOG_TIMEOUT_MS milliseconds, all motors are
// stopped (port_stop_all).  Servos hold their last angle.  Config is not cleared.
#define WATCHDOG_TIMEOUT_MS 500u

static uint32_t last_packet_ms   = 0;
static bool     watchdog_triggered = false;

// ─── 100 Hz PID/velocity timer ────────────────────────────────────────────────
// This repeating alarm runs on core 0 alongside the main loop.
// The RP2040 alarm callbacks are lightweight — no blocking allowed.

static volatile bool pid_tick = false;  // flag set by timer, consumed by main loop

static bool pid_timer_cb(struct repeating_timer *t) {
    (void)t;
    encoder_update_velocity();
    pid_tick = true;  // signal main loop to call port_pid_update()
    return true;      // keep repeating
}

// ─── Ultrasonic update counter (every 3 state frames at 50 Hz ≈ 17 Hz) ───────
static uint8_t us_frame_counter = 0;
#define US_FRAME_INTERVAL 3

// ─── Pulse measurement helper ─────────────────────────────────────────────────
// Measures the HIGH pulse width on a GPIO pin.
// Temporarily reconfigures the pin as a floating input, measures, then leaves it
// as a high-impedance input (caller is responsible for any needed restore).
// Returns pulse width in µs, or 0 on timeout.
static uint32_t measure_pulse_us(uint8_t gpio, uint32_t timeout_us) {
    gpio_init(gpio);
    gpio_set_dir(gpio, GPIO_IN);
    gpio_disable_pulls(gpio);

    uint64_t t0 = to_us_since_boot(get_absolute_time());

    // Wait for line to go LOW (idle gap between pulses)
    while (gpio_get(gpio)) {
        if (to_us_since_boot(get_absolute_time()) - t0 > timeout_us) return 0;
    }
    // Wait for rising edge (start of pulse)
    while (!gpio_get(gpio)) {
        if (to_us_since_boot(get_absolute_time()) - t0 > timeout_us) return 0;
    }
    uint64_t rise = to_us_since_boot(get_absolute_time());
    // Wait for falling edge (end of pulse)
    while (gpio_get(gpio)) {
        if (to_us_since_boot(get_absolute_time()) - t0 > timeout_us) return 0;
    }
    return (uint32_t)(to_us_since_boot(get_absolute_time()) - rise);
}

// ─── Command dispatcher ───────────────────────────────────────────────────────

static void handle_command(uint8_t type, const uint8_t *payload, uint8_t len) {
    // Any received packet resets the watchdog timer.
    last_packet_ms    = to_ms_since_boot(get_absolute_time());
    watchdog_triggered = false;

    switch (type) {

        case CMD_CONFIGURE: {
            if (len < sizeof(CmdConfigure)) goto bad_len;
            const CmdConfigure *cmd = (const CmdConfigure *)payload;
            bool ok;
            if (cmd->port_type == PORT_UART) {
                uint32_t baud = 0;  // 0 → port_configure_uart uses its default
                if (len >= sizeof(CmdConfigureUart)) {
                    baud = ((const CmdConfigureUart *)payload)->baud;
                }
                ok = port_configure_uart(cmd->port_id, baud);
            } else {
                ok = port_configure(cmd->port_id, cmd->port_type);
            }
            if (!ok) {
                usb_comm_send_error(ERR_BAD_TYPE, "configure failed");
            } else {
                usb_comm_send_ack(type);
            }
            break;
        }

        case CMD_SET_MOTOR: {
            if (len < sizeof(CmdSetMotor)) goto bad_len;
            const CmdSetMotor *cmd = (const CmdSetMotor *)payload;
            port_set_motor(cmd->port_id, cmd->value);
            usb_comm_send_ack(type);
            break;
        }

        case CMD_SET_SERVO: {
            if (len < sizeof(CmdSetServo)) goto bad_len;
            const CmdSetServo *cmd = (const CmdSetServo *)payload;
            port_set_servo(cmd->port_id, cmd->angle);
            usb_comm_send_ack(type);
            break;
        }

        case CMD_SET_VELOCITY: {
            if (len < sizeof(CmdSetVelocity)) goto bad_len;
            const CmdSetVelocity *cmd = (const CmdSetVelocity *)payload;
            port_set_velocity(cmd->port_id, cmd->velocity);
            usb_comm_send_ack(type);
            break;
        }

        case CMD_SET_PID: {
            if (len < sizeof(CmdSetPid)) goto bad_len;
            const CmdSetPid *cmd = (const CmdSetPid *)payload;
            port_set_pid(cmd->port_id, cmd->kp, cmd->ki, cmd->kd);
            usb_comm_send_ack(type);
            break;
        }

        case CMD_RESET_ENC: {
            if (len < sizeof(CmdResetEnc)) goto bad_len;
            const CmdResetEnc *cmd = (const CmdResetEnc *)payload;
            port_reset_encoder(cmd->port_id);
            usb_comm_send_ack(type);
            break;
        }

        case CMD_SET_GPIO: {
            if (len < sizeof(CmdSetGpio)) goto bad_len;
            const CmdSetGpio *cmd = (const CmdSetGpio *)payload;
            port_set_gpio(cmd->port_id, cmd->state);
            usb_comm_send_ack(type);
            break;
        }

        case CMD_SET_RATE: {
            if (len < sizeof(CmdSetRate)) goto bad_len;
            const CmdSetRate *cmd = (const CmdSetRate *)payload;
            if (cmd->rate == 0 || cmd->rate > 500) {
                usb_comm_send_error(ERR_BAD_LEN, "rate out of range");
            } else {
                stream_rate_hz = cmd->rate;
                usb_comm_send_ack(type);
            }
            break;
        }

        case CMD_STOP_ALL: {
            port_stop_all();
            usb_comm_send_ack(type);
            break;
        }

        case CMD_SET_SERVO_RANGE: {
            if (len < sizeof(CmdSetServoRange)) goto bad_len;
            const CmdSetServoRange *cmd = (const CmdSetServoRange *)payload;
            port_set_servo_range(cmd->port_id, cmd->min_us, cmd->max_us);
            usb_comm_send_ack(type);
            break;
        }

        case CMD_ATTACH_ENC: {
            if (len < sizeof(CmdAttachEnc)) goto bad_len;
            const CmdAttachEnc *cmd = (const CmdAttachEnc *)payload;
            port_attach_encoder(cmd->motor_port, cmd->encoder_port);
            usb_comm_send_ack(type);
            break;
        }

        case CMD_CONFIG_DONE: {
            if (port_config_done()) {
                usb_comm_send_ack(type);
            }
            // on conflict: port_config_done() already sent RESP_ERROR internally
            break;
        }

        case CMD_UART_TX: {
            // Payload: [port_id:u8][len:u8][data...]
            if (len < sizeof(CmdUartTx)) goto bad_len;
            const CmdUartTx *cmd = (const CmdUartTx *)payload;
            uint8_t data_len = cmd->len;
            if (len < (uint8_t)(sizeof(CmdUartTx) + data_len)) goto bad_len;
            port_uart_tx(cmd->port_id, payload + sizeof(CmdUartTx), data_len);
            break;
        }

        case CMD_RESET: {
            port_reset();
            usb_comm_send_ack(type);
            break;
        }

        case CMD_HEARTBEAT: {
            // Watchdog is reset at the top of handle_command.  No reply needed.
            break;
        }

        case CMD_MEASURE_PULSE: {
            if (len < sizeof(CmdMeasurePulse)) goto bad_len;
            const CmdMeasurePulse *cmd = (const CmdMeasurePulse *)payload;
            if (!IS_SINGLE_PORT(cmd->port_id)) {
                usb_comm_send_error(ERR_BAD_PORT, "not a single-pin port");
                break;
            }
            uint8_t gpio = SINGLE_GPIO[cmd->port_id];
            // 150 ms = 7.5 periods of 50 Hz — enough to catch a full pulse cycle.
            uint32_t pulse_us = measure_pulse_us(gpio, 150000);
            if (pulse_us == 0) {
                usb_comm_send_error(ERR_BAD_PORT, "pulse timeout");
            } else {
                uint8_t resp[4] = {
                    (uint8_t)(pulse_us),
                    (uint8_t)(pulse_us >> 8),
                    (uint8_t)(pulse_us >> 16),
                    (uint8_t)(pulse_us >> 24),
                };
                usb_comm_send(RESP_MEASURE_PULSE, resp, 4);
            }
            break;
        }

        case CMD_PCA_INIT: {
            if (len < sizeof(CmdPcaInit)) goto bad_len;
            const CmdPcaInit *cmd = (const CmdPcaInit *)payload;
            if (pca9685_init(0x40, cmd->prescale)) {
                usb_comm_send_ack(type);
            } else {
                usb_comm_send_error(ERR_BAD_TYPE, "PCA9685 not found at 0x40");
            }
            break;
        }

        case CMD_PCA_SET_CH: {
            if (len < sizeof(CmdPcaSetCh)) goto bad_len;
            const CmdPcaSetCh *cmd = (const CmdPcaSetCh *)payload;
            if (cmd->ch > 15) {
                usb_comm_send_error(ERR_BAD_PORT, "PCA9685 ch must be 0-15");
                break;
            }
            pca9685_set_channel(0x40, cmd->ch, cmd->on, cmd->off);
            break;  // fire-and-forget; no ACK
        }

        case CMD_PCA_CH_OFF: {
            if (len < sizeof(CmdPcaChOff)) goto bad_len;
            const CmdPcaChOff *cmd = (const CmdPcaChOff *)payload;
            if (cmd->ch > 15) {
                usb_comm_send_error(ERR_BAD_PORT, "PCA9685 ch must be 0-15");
                break;
            }
            pca9685_channel_off(0x40, cmd->ch);
            break;  // fire-and-forget; no ACK
        }

        default:
            usb_comm_send_error(ERR_UNKNOWN_CMD, "unknown cmd");
            break;
    }
    return;

bad_len:
    usb_comm_send_error(ERR_BAD_LEN, "payload too short");
}

// ─── Entry point ─────────────────────────────────────────────────────────────

int main(void) {
    stdio_init_all();   // activates USB CDC

    usb_comm_init();
    port_manager_init();

    // Start 100 Hz repeating timer for velocity + PID updates
    struct repeating_timer pid_timer;
    add_repeating_timer_ms(-10, pid_timer_cb, NULL, &pid_timer);  // -10 ms = 100 Hz

    // State packet send timing
    absolute_time_t next_state = get_absolute_time();

    uint8_t  cmd_type;
    uint8_t  cmd_payload[PROTO_MAX_LEN];
    uint8_t  cmd_len;
    // uart_rx_buf: 1 byte port_id prefix + up to 64 data bytes
    uint8_t  uart_rx_buf[65];

    last_packet_ms = to_ms_since_boot(get_absolute_time());

    while (true) {
        // ── 1. Receive and dispatch incoming commands ──
        if (usb_comm_recv(&cmd_type, cmd_payload, &cmd_len)) {
            handle_command(cmd_type, cmd_payload, cmd_len);
        }

        // ── Watchdog: stop all motors if no packet received for WATCHDOG_TIMEOUT_MS ──
        {
            uint32_t now_ms = to_ms_since_boot(get_absolute_time());
            if (!watchdog_triggered &&
                (now_ms - last_packet_ms > WATCHDOG_TIMEOUT_MS)) {
                port_stop_all();
                watchdog_triggered = true;
            }
        }

        // ── 2. Forward any UART RX bytes to the Pi (per port, with port_id prefix) ──
        uart_rx_buf[0] = UART0_PORT_ID;
        { uint8_t n = port_uart_rx(UART0_PORT_ID, uart_rx_buf + 1);
          if (n > 0) usb_comm_send(RESP_UART_RX, uart_rx_buf, (uint8_t)(n + 1)); }
        uart_rx_buf[0] = UART1_PORT_ID;
        { uint8_t n = port_uart_rx(UART1_PORT_ID, uart_rx_buf + 1);
          if (n > 0) usb_comm_send(RESP_UART_RX, uart_rx_buf, (uint8_t)(n + 1)); }

        // ── 3. PID tick (flagged by 100 Hz timer ISR) ──
        if (pid_tick) {
            pid_tick = false;
            port_pid_update();
        }

        // ── 5. Send state packet at configured rate ──
        absolute_time_t now = get_absolute_time();
        if (absolute_time_diff_us(next_state, now) >= 0) {
            // Schedule next send (fixed-period, drift-corrected)
            next_state = delayed_by_us(next_state, 1000000u / stream_rate_hz);

            // Update ultrasonic sensors every US_FRAME_INTERVAL frames
            if (++us_frame_counter >= US_FRAME_INTERVAL) {
                us_frame_counter = 0;
                ultrasonic_update();
            }

            port_send_state();
        }
    }

    return 0;  // unreachable
}
