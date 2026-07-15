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
#define CMD_UART_TX         0x0D  // send bytes out UART; payload: [port_id:u8][len:u8][data...]
#define CMD_RESET           0x0E  // stop all motors, unlock config, reset all ports
#define CMD_HEARTBEAT       0x0F  // keepalive — resets the watchdog timer; no reply
#define CMD_MEASURE_PULSE   0x10  // measure pulse width on a single-pin port; payload: [port_id:u8]
#define CMD_PCA_INIT        0x11  // detect + init PCA9685; payload: [prescale:u8] → ACK or ERROR
#define CMD_PCA_SET_CH      0x12  // set channel; payload: [ch:u8][on:u16le][off:u16le] (no ACK)
#define CMD_PCA_CH_OFF      0x13  // full-off channel; payload: [ch:u8] (no ACK)
#define CMD_SET_POSITION    0x14  // position PID; payload: [port_id:u8][target:i32le][speed_limit:u16le]

// ─── RP2040 → Pi response types ──────────────────────────────────────────────
#define RESP_STATE         0x81
#define RESP_ERROR         0x82
#define RESP_ACK           0x83
#define RESP_UART_RX       0x84  // bytes received on UART; payload: [port_id:u8][data...]
#define RESP_MEASURE_PULSE 0x85  // pulse width result; payload: [pulse_us:u32 LE]

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
#define PORT_UART           0x0A  // UART bus: D7=UART0 (GP12=TX/GP13=RX) or D6=UART1 (GP20=TX/GP21=RX)
#define PORT_VL53L0X        0x0B  // VL53L0X ToF sensor on I²C port (auto-detected at startup)

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
// PWM partition:
//   S ports (50 Hz servos / motors): S0–S7 all servo-capable.
//     S0–S4 use hardware PWM (slices 0A,0B,1A,1B,3A).
//     S5–S7 (GP26/27/28, also ADC0–2) use hardware PWM (slices 5A,5B,6A) — safe
//     because the D-port B-pins that formerly shared those slices now use PIO PWM.
//   D ports (20 kHz SM motors): B-pins use either hardware PWM or PIO PWM:
//     D0-B (GP8,  slice 4A) — hardware PWM
//     D1-B (GP9,  slice 4B) — hardware PWM
//     D2-B (GP10, slice 5A) — PIO PWM  (would conflict with S5 on slice 5A)
//     D3-B (GP11, slice 5B) — PIO PWM  (would conflict with S6 on slice 5B)
//     D4-B through D7-B     — all use PIO PWM (eliminates all slice conflicts)
//
// Special functions:
//   I2C port (GP4/GP5)  — dedicated I2C0 SDA/SCL; always PORT_I2C, not reconfigurable
//   D7 (GP12/GP13)      — also UART0 TX/RX; both pins reserved when PORT_UART configured
//   D6 (GP20/GP21)      — also UART1 TX/RX
//   ADC-capable singles: S5=GP26 (ADC0), S6=GP27 (ADC1), S7=GP28 (ADC2)

static const uint8_t SINGLE_GPIO[PORT_COUNT_SINGLE] = {
    0,   // S0 = GP0  (PWM slice 0A — servo-capable)
    1,   // S1 = GP1  (PWM slice 0B — servo-capable)
    2,   // S2 = GP2  (PWM slice 1A — servo-capable)
    3,   // S3 = GP3  (PWM slice 1B — servo-capable)
    6,   // S4 = GP6  (PWM slice 3A — servo-capable)
    26,  // S5 = GP26 (ADC0, PWM slice 5A — servo-capable; D2-B moved to PIO)
    27,  // S6 = GP27 (ADC1, PWM slice 5B — servo-capable; D3-B moved to PIO)
    28,  // S7 = GP28 (ADC2, PWM slice 6A — servo-capable; D7-B moved to PIO)
};

// [n][0] = pin A (direction / UART TX),  [n][1] = pin B (speed PWM / UART RX)
// All dual-port B-pins use PIO PWM (see pio_pwm.h) so no combination of
// motor and servo ports can produce a hardware PWM slice conflict.
static const uint8_t DUAL_GPIO[PORT_COUNT_DUAL][2] = {
    {16,  8},  // D0: A=GP16, B=GP8  (slice 4A)
    {17,  9},  // D1: A=GP17, B=GP9  (slice 4B)
    {18, 10},  // D2: A=GP18, B=GP10 (slice 5A — PIO)
    {19, 11},  // D3: A=GP19, B=GP11 (slice 5B — PIO)
    {22, 15},  // D4: A=GP22, B=GP15 (slice 7B)
    { 7, 14},  // D5: A=GP7,  B=GP14 (slice 7A)  ← GP7 replaces GP20 (freed for D6)
    {20, 21},  // D6: A=GP20 (UART1 TX, slice 2A), B=GP21 (UART1 RX, slice 2B)
    {12, 13},  // D7: A=GP12 (UART0 TX, slice 6A), B=GP13 (UART0 RX, slice 6B — PIO)
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
// CMD_UART_TX: [port_id:u8][len:u8][data...]
typedef struct { uint8_t port_id; uint8_t len; }                       CmdUartTx;
typedef struct { uint8_t port_id; }                                    CmdMeasurePulse;
typedef struct { uint8_t prescale; }                                   CmdPcaInit;
typedef struct { uint8_t ch; uint16_t on; uint16_t off; }             CmdPcaSetCh;
typedef struct { uint8_t ch; }                                         CmdPcaChOff;
typedef struct { uint8_t port_id; int32_t target; uint16_t speed_limit; } CmdSetPosition;

#pragma pack(pop)
