#include "pico/stdlib.h"
#include "pico/time.h"
#include "hardware/gpio.h"
#include "protocol.h"
#include "crc8.h"
#include "usb_comm.h"
#include "port_manager.h"
#include "devices/encoder.h"
#include "devices/ultrasonic.h"
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
                uint32_t baud = UART_DEFAULT_BAUD;
                if (len >= sizeof(CmdConfigureUart)) {
                    baud = ((const CmdConfigureUart *)payload)->baud;
                }
                ok = port_configure_uart(baud);
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
            // Payload: [len:u8][data...]
            if (len < 1) goto bad_len;
            uint8_t data_len = payload[0];
            if (len < (uint8_t)(1 + data_len)) goto bad_len;
            port_uart_tx(payload + 1, data_len);
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
    uint8_t  uart_rx_buf[64];

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

        // ── 2. Forward any UART RX bytes to the Pi ──
        uint8_t n = port_uart_rx(uart_rx_buf);
        if (n > 0) {
            usb_comm_send(RESP_UART_RX, uart_rx_buf, n);
        }

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
