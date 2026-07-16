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
    // Velocity PID state
    bool     pid_enabled;
    int32_t  pid_target;     // velocity target, ticks/s × 10
    float    pid_kp;
    float    pid_ki;
    float    pid_kd;
    float    pid_integral;
    float    pid_last_error;   // velocity PID: previous error for d-on-error
    float    pid_integral_max; // 0 = uncapped; > 0 = clamp accumulator to ±this value
    // Position PID state (mutually exclusive with velocity PID)
    bool     pos_pid_enabled;
    int32_t  pos_target;      // target encoder tick count
    uint16_t pos_speed_limit; // max motor output 0–10000; 0 = full (10000)
    int32_t  pid_last_count;  // position PID: previous encoder count for d-on-measurement
    float    pid_d_alpha;     // EMA alpha for derivative low-pass filter (1.0 = no filter)
    float    pid_d_prev;      // EMA state: previous filtered derivative value
    // Position PID options
    float    pos_deadband;      // ticks; |error| ≤ this → zero output, integral frozen (0 = off)
    float    pos_output_floor;  // %; minimum output magnitude when outside deadband (0 = off)
    float    pos_ramp_rate;       // ticks/s; internal setpoint ramps at this rate (0 = instant)
    float    pos_approach_factor; // 0 = off; >0: caps ramp step to |remaining| × factor near target
    float    pos_ramp_setpoint;   // internal: current interpolated setpoint for ramp

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

// ─── UART port IDs ───────────────────────────────────────────────────────────
#define UART0_PORT_ID  15u   // D7: GP12=TX, GP13=RX (UART0)
#define UART1_PORT_ID  14u   // D6: GP20=TX, GP21=RX (UART1)

// ─── API ─────────────────────────────────────────────────────────────────────

// Initialise the port manager (call once at startup)
void port_manager_init(void);

// Configure a port to a new type.  De-initialises the old type first.
// Returns false on error (bad port id, bad type, or config locked).
bool port_configure(uint8_t port_id, uint8_t port_type);

// Configure D6 (UART1, GP24/GP25) or D7 (UART0, GP12/GP13) as a UART bus.
// port_id must be 14 (D6) or 15 (D7).
// Returns false if config is locked or port_id is invalid.
bool port_configure_uart(uint8_t port_id, uint32_t baud);

// Validate PWM slice conflicts across all configured ports and lock the config.
// Sends RESP_ERROR internally on conflict; returns false in that case.
// Returns true (and sends nothing) if already locked.
bool port_config_done(void);

// Send bytes out the UART on port_id (14=D6/UART1, 15=D7/UART0).  No-op if not configured.
void port_uart_tx(uint8_t port_id, const uint8_t *data, uint8_t len);

// Read available RX bytes from the UART on port_id into buf (max 64 bytes).
// Returns number of bytes read, or 0 if not configured or no bytes waiting.
uint8_t port_uart_rx(uint8_t port_id, uint8_t *buf);

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

// Set position PID target (absolute encoder tick count).
// speed_limit caps the motor output (0–10000); 0 means no cap (full 10000).
// Clears velocity PID; mutually exclusive with port_set_velocity.
void port_set_position(uint8_t port_id, int32_t target, uint16_t speed_limit, bool keep_integral);

// Set position PID options. All options persist until changed.
//   deadband:     ticks; within ±deadband, output is zeroed and integral frozen. 0 = off.
//   output_floor: %; minimum motor output when outside deadband (overcomes stiction). 0 = off.
//   ramp_rate:    ticks/s; max rate the internal setpoint moves toward the target. 0 = instant.
//   d_alpha:      EMA alpha for derivative filter; 1.0 = no filter, lower = more smoothing.
void port_set_pos_options(uint8_t port_id, float deadband, float output_floor, float ramp_rate, float d_alpha, float approach_factor);

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
