#pragma once
#include <stdint.h>
#include <stdbool.h>
#include "protocol.h"

// ─── Per-port runtime state ──────────────────────────────────────────────────

typedef struct {
    uint8_t  type;           // PORT_* enum
    uint8_t  pin_a;          // primary GPIO
    uint8_t  pin_b;          // secondary GPIO, NO_PIN (255) if single-pin port

    // Motor/servo current output value
    int16_t  motor_value;    // -10000 to +10000

    // Servo
    uint16_t servo_pulse_us; // last commanded pulse width in microseconds
    uint16_t servo_min_us;
    uint16_t servo_max_us;

    // Encoder link: which DUAL_SLOT feeds this motor port, or -1 = none
    int8_t   enc_slot;
    // PID state
    bool     pid_enabled;
    int32_t  pid_target;     // velocity target, ticks/s × 10
    float    pid_kp;
    float    pid_ki;
    float    pid_kd;
    float    pid_integral;
    float    pid_last_error;

    // GPIO
    uint8_t  gpio_state;

    // Encoder slot index (when this port IS an encoder)
    uint8_t  enc_self_slot;  // valid when type == PORT_ENCODER

    // Ultrasonic slot index
    uint8_t  us_slot;        // valid when type == PORT_ULTRASONIC
} PortState;

// Indexed 0–16: S0–S7 at [0–7], D0–D7 at [8–15], dedicated I2C at [16].
extern PortState ports[PORT_COUNT_TOTAL];

// True after CMD_CONFIG_DONE is processed; new CMD_CONFIGURE packets are rejected.
extern bool config_locked;

// ─── API ─────────────────────────────────────────────────────────────────────

// Initialise the port manager (call once at startup)
void port_manager_init(void);

// Configure a port to a new type.  De-initialises the old type first.
// Returns false on error (bad port id, bad type, or config locked).
bool port_configure(uint8_t port_id, uint8_t port_type);

// Configure D7 as a UART bus.  Initialises UART0 on GP12 (TX) / GP13 (RX).
// Returns false if config is locked or if D7 is already in use.
bool port_configure_uart(uint32_t baud);

// Validate PWM slice conflicts across all configured ports and lock the config.
// Sends RESP_ERROR internally on conflict; returns false in that case.
// Returns true (and sends nothing) if already locked.
bool port_config_done(void);

// Send bytes out UART0.  No-op if UART not configured.
void port_uart_tx(const uint8_t *data, uint8_t len);

// Read available UART0 RX bytes into buf (max 64).  Returns number of bytes read.
// Returns 0 if UART not configured or no bytes waiting.
uint8_t port_uart_rx(uint8_t *buf);

// Set motor power (-10000 to +10000).  Handles SM, LAP, SERVO_SIG.
void port_set_motor(uint8_t port_id, int16_t value);

// Set servo pulse width in microseconds (clamped to 500–2500).
void port_set_servo(uint8_t port_id, uint16_t pulse_us);

// Set servo pulse range.
void port_set_servo_range(uint8_t port_id, uint16_t min_us, uint16_t max_us);

// Enable PID velocity control by linking an encoder port to a motor port.
void port_attach_encoder(uint8_t motor_port, uint8_t encoder_port);

// Set PID target velocity (ticks/s × 10).
void port_set_velocity(uint8_t port_id, int32_t velocity_x10);

// Set PID gains.
void port_set_pid(uint8_t port_id, float kp, float ki, float kd);

// Reset encoder count for a port.
void port_reset_encoder(uint8_t port_id);

// Set GPIO output state.
void port_set_gpio(uint8_t port_id, uint8_t state);

// Stop all motor outputs, leaving servos at their current angle.
// Called by CMD_STOP_ALL (robot.stop()) and the watchdog on communication timeout.
void port_stop_all(void);

// Stop all motors and reset port configuration state.
// Leaves servo PWM running so physical servo positions are preserved.
// Sets config_locked = false so the new student program can reconfigure.
// Called by CMD_RESET when a new student program starts.
void port_reset(void);

// Run one PID iteration for all motor ports with PID enabled.
// Called at 100 Hz from a repeating timer.
void port_pid_update(void);

// Build and send the STATE packet for all configured ports.
void port_send_state(void);
