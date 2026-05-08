#pragma once
#include <stdint.h>

// ─── Packet framing ──────────────────────────────────────────────────────────
#define PROTO_SYNC      0xAA
#define PROTO_MAX_LEN   192   // max payload bytes (17 ports × ~10 bytes + header)

// ─── Pi → RP2040 command types ───────────────────────────────────────────────
#define CMD_CONFIGURE       0x01
#define CMD_SET_MOTOR       0x02
#define CMD_SET_SERVO       0x03
#define CMD_SET_VELOCITY    0x04
#define CMD_SET_PID         0x05
#define CMD_RESET_ENC       0x06
#define CMD_SET_GPIO        0x07
#define CMD_SET_RATE        0x08
#define CMD_STOP_ALL        0x09
#define CMD_SET_SERVO_RANGE 0x0A
#define CMD_ATTACH_ENC      0x0B
#define CMD_CONFIG_DONE     0x0C  // finalize port config, validate, lock
#define CMD_UART_TX         0x0D  // send bytes out UART0 (D7: GP12 TX / GP13 RX)
#define CMD_RESET           0x0E  // stop all motors, unlock config, reset all ports
#define CMD_HEARTBEAT       0x0F  // keepalive — resets the watchdog timer; no reply

// ─── RP2040 → Pi response types ──────────────────────────────────────────────
#define RESP_STATE    0x81
#define RESP_ERROR    0x82
#define RESP_ACK      0x83
#define RESP_UART_RX  0x84  // bytes received on UART0 (D7: GP12 TX / GP13 RX)

// ─── Port type enum ──────────────────────────────────────────────────────────
#define PORT_UNCONFIGURED   0x00
#define PORT_MOTOR_SM       0x01
#define PORT_MOTOR_LAP      0x02
#define PORT_MOTOR_SERVO    0x03
#define PORT_SERVO          0x04
#define PORT_ENCODER        0x05
#define PORT_ULTRASONIC     0x06
#define PORT_I2C            0x07
#define PORT_GPIO_IN        0x08
#define PORT_GPIO_OUT       0x09
#define PORT_UART           0x0A  // UART0 bus (claims D7: GP12=TX + GP13=RX)

// ─── Error codes ─────────────────────────────────────────────────────────────
#define ERR_UNKNOWN_CMD     0x01
#define ERR_BAD_PORT        0x02
#define ERR_BAD_TYPE        0x03
#define ERR_BAD_CRC         0x04
#define ERR_BAD_LEN         0x05
#define ERR_WRONG_PORT_TYPE 0x06
#define ERR_PORT_CONFLICT   0x07  // PWM slice conflict between two ports
#define ERR_CONFIG_LOCKED   0x08  // CMD_CONFIGURE received after CMD_CONFIG_DONE

// ─── Port count and ID layout ─────────────────────────────────────────────────
// Single-pin ports:  S0–S7  → IDs 0–7
// Dual-pin ports:    D0–D7  → IDs 8–15
// Dedicated I2C:     I2C    → ID  16  (always PORT_I2C, not reconfigurable)
#define PORT_COUNT_SINGLE  8
#define PORT_COUNT_DUAL    8
#define PORT_ID_DUAL_BASE  8
#define PORT_ID_I2C        16
#define PORT_COUNT_TOTAL   17   // 8 single + 8 dual + 1 dedicated I2C

// ─── Port classification helpers ─────────────────────────────────────────────
#define IS_VALID_PORT(id)  ((id) < PORT_COUNT_TOTAL)
#define IS_DUAL_PORT(id)   ((id) >= PORT_ID_DUAL_BASE && (id) < (PORT_ID_DUAL_BASE + PORT_COUNT_DUAL))
#define IS_SINGLE_PORT(id) ((id) < PORT_COUNT_SINGLE)
#define IS_I2C_PORT(id)    ((id) == PORT_ID_I2C)

// ─── GPIO pin map ─────────────────────────────────────────────────────────────
//
// TO CHANGE PIN ASSIGNMENTS: edit only these two arrays plus I2C_*_GPIO.
//   SINGLE_GPIO[n]    = GPIO pin for single-pin port Sn
//   DUAL_GPIO[n][0/1] = GPIO pins A / B for dual-pin port Dn
//
// PWM partition (zero motor-servo conflicts):
//   Servos (50 Hz) use slices 0–3: all single-pin ports
//   Motors (20 kHz) use slices 4–7: all dual-port B pins
//
// Special functions:
//   I2C port (GP4/GP5) — dedicated I2C0 SDA/SCL; always PORT_I2C, not reconfigurable
//   D7 (GP12/GP13)     — also UART0 TX/RX; both pins reserved when PORT_UART configured
//   Analog-capable: GP26 (D5 pin A), GP27 (D6 pin A), GP28 (D4 pin B)

static const uint8_t SINGLE_GPIO[PORT_COUNT_SINGLE] = {
    0,   // S0 = GP0  (PWM slice 0A)
    1,   // S1 = GP1  (PWM slice 0B)
    2,   // S2 = GP2  (PWM slice 1A)
    3,   // S3 = GP3  (PWM slice 1B)
    6,   // S4 = GP6  (PWM slice 3A)
    7,   // S5 = GP7  (PWM slice 3B)
    20,  // S6 = GP20 (PWM slice 2A)
    21,  // S7 = GP21 (PWM slice 2B)
};

// [n][0] = pin A (direction / UART TX),  [n][1] = pin B (speed PWM / UART RX)
// All B pins are on slices 4–7 so motors never conflict with single-port servos.
static const uint8_t DUAL_GPIO[PORT_COUNT_DUAL][2] = {
    {16,  8},  // D0: A=GP16 (slice 0A), B=GP8  (slice 4A)
    {17,  9},  // D1: A=GP17 (slice 0B), B=GP9  (slice 4B)
    {18, 10},  // D2: A=GP18 (slice 1A), B=GP10 (slice 5A)
    {19, 11},  // D3: A=GP19 (slice 1B), B=GP11 (slice 5B)
    {22, 28},  // D4: A=GP22 (slice 3A), B=GP28 (slice 6A, ADC2)
    {26, 14},  // D5: A=GP26 (slice 5A, ADC0), B=GP14 (slice 7A)
    {27, 15},  // D6: A=GP27 (slice 5B, ADC1), B=GP15 (slice 7B)
    {12, 13},  // D7: A=GP12 (UART0 TX, slice 6A), B=GP13 (UART0 RX, slice 6B)
};

#define I2C_SDA_GPIO  4   // dedicated I2C port — GP4 = I2C0 SDA
#define I2C_SCL_GPIO  5   // dedicated I2C port — GP5 = I2C0 SCL

// ─── Pin lookup helpers ───────────────────────────────────────────────────────

#define NO_PIN 255u   // sentinel: port has no B pin

static inline uint8_t port_pin_a(uint8_t id) {
    if (IS_I2C_PORT(id))  return I2C_SDA_GPIO;
    if (IS_DUAL_PORT(id)) return DUAL_GPIO[id - PORT_ID_DUAL_BASE][0];
    return SINGLE_GPIO[id];
}

// Returns B pin GPIO, or NO_PIN for single-pin ports.
static inline uint8_t port_pin_b(uint8_t id) {
    if (IS_I2C_PORT(id))  return I2C_SCL_GPIO;
    if (IS_DUAL_PORT(id)) return DUAL_GPIO[id - PORT_ID_DUAL_BASE][1];
    return NO_PIN;
}

// Slot index into encoder/ultrasonic device arrays (dual ports only → 0–7)
#define DUAL_SLOT(port_id) ((uint8_t)((port_id) - PORT_ID_DUAL_BASE))

// ─── Command payload structs (packed, little-endian) ─────────────────────────
#pragma pack(push, 1)

typedef struct { uint8_t port_id; uint8_t port_type; }                CmdConfigure;
typedef struct { uint8_t port_id; uint8_t port_type; uint32_t baud; } CmdConfigureUart;
typedef struct { uint8_t port_id; int16_t value; }                    CmdSetMotor;
typedef struct { uint8_t port_id; uint16_t angle; }                   CmdSetServo;
typedef struct { uint8_t port_id; int32_t velocity; }                 CmdSetVelocity;
typedef struct { uint8_t port_id; float kp; float ki; float kd; }     CmdSetPid;
typedef struct { uint8_t port_id; }                                    CmdResetEnc;
typedef struct { uint8_t port_id; uint8_t state; }                    CmdSetGpio;
typedef struct { uint16_t rate; }                                      CmdSetRate;
typedef struct { uint8_t port_id; uint16_t min_us; uint16_t max_us; } CmdSetServoRange;
typedef struct { uint8_t motor_port; uint8_t encoder_port; }          CmdAttachEnc;
// CMD_UART_TX: variable-length; first byte is data length, rest is data
typedef struct { uint8_t len; }                                        CmdUartTx;

#pragma pack(pop)
