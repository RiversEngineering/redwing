"""RP2040 binary protocol — encoding, decoding, and constants.

Packet format (both directions):
  [0xAA][TYPE:u8][LEN:u8][PAYLOAD:LEN bytes][CRC8:u8]
  CRC8 covers TYPE + LEN + PAYLOAD (polynomial 0x07).
"""

import struct
from dataclasses import dataclass, field
from typing import Any

SYNC = 0xAA

# -------------------------------------------------------------------
# Pi → RP2040 command types
# -------------------------------------------------------------------
CMD_CONFIGURE       = 0x01
CMD_SET_MOTOR       = 0x02
CMD_SET_SERVO       = 0x03
CMD_SET_VELOCITY    = 0x04
CMD_SET_PID         = 0x05
CMD_RESET_ENC       = 0x06
CMD_SET_GPIO        = 0x07
CMD_SET_RATE        = 0x08
CMD_STOP_ALL        = 0x09
CMD_SET_SERVO_RANGE = 0x0A
CMD_ATTACH_ENC      = 0x0B
CMD_CONFIG_DONE     = 0x0C
CMD_UART_TX         = 0x0D
CMD_RESET           = 0x0E
CMD_HEARTBEAT       = 0x0F
CMD_MEASURE_PULSE   = 0x10  # payload: [port_id:u8] — measure pulse on a single-pin port
CMD_PCA_INIT        = 0x11  # payload: [prescale:u8] — detect+init PCA9685; ACK on success, ERROR if absent
CMD_PCA_SET_CH      = 0x12  # payload: [ch:u8][on:u16le][off:u16le] — set channel counts (no ACK)
CMD_PCA_CH_OFF      = 0x13  # payload: [ch:u8] — full-off a channel (no ACK)
CMD_SET_POSITION    = 0x14  # payload: [port_id:u8][target:i32le][speed_limit:u16le]
CMD_SET_POS_OPTIONS = 0x15  # payload: [port_id:u8][deadband:f32][output_floor:f32][ramp_rate:f32][d_alpha:f32][approach_factor:f32]
CMD_INVERT_ENCODER  = 0x16  # payload: [port_id:u8][inverted:u8]

# -------------------------------------------------------------------
# RP2040 → Pi response types
# -------------------------------------------------------------------
RSP_STATE          = 0x81
RSP_ERROR          = 0x82
RSP_ACK            = 0x83
RSP_UART_RX        = 0x84
RSP_MEASURE_PULSE  = 0x85  # payload: [pulse_us:u32 LE]

# -------------------------------------------------------------------
# RP2040 error codes (must match firmware protocol.h)
# -------------------------------------------------------------------
ERR_UNKNOWN_CMD     = 0x01
ERR_BAD_PORT        = 0x02
ERR_BAD_TYPE        = 0x03
ERR_BAD_CRC         = 0x04
ERR_BAD_LEN         = 0x05
ERR_WRONG_PORT_TYPE = 0x06
ERR_PORT_CONFLICT   = 0x07   # PWM slice conflict between two ports
ERR_CONFIG_LOCKED   = 0x08   # CMD_CONFIGURE received after CMD_CONFIG_DONE

# -------------------------------------------------------------------
# Port type enum (must match firmware port_manager.h)
# -------------------------------------------------------------------
PORT_UNCONFIGURED   = 0x00
PORT_MOTOR_SM       = 0x01
PORT_MOTOR_LAP      = 0x02
PORT_MOTOR_SERVO    = 0x03
PORT_SERVO          = 0x04
PORT_ENCODER        = 0x05
PORT_ULTRASONIC     = 0x06
PORT_I2C            = 0x07
PORT_GPIO_IN        = 0x08
PORT_GPIO_OUT       = 0x09
PORT_UART           = 0x0A  # UART bus (D7: GP12=TX, GP13=RX)
PORT_VL53L0X        = 0x0B  # VL53L0X ToF sensor on I²C port (auto-detected)
# 0x0C / 0x0D are daemon-only: firmware sees them as PORT_UART at 115200 baud.
# The daemon parses the Benewake 9-byte frame stream and exposes distance/strength/temperature.
PORT_TFLUNA         = 0x0C  # Benewake TF-Luna (distance + strength + temperature)
PORT_TFMINI         = 0x0D  # Benewake TF-Mini (distance + strength)

PORT_TYPE_NAMES = {
    PORT_UNCONFIGURED: "unconfigured",
    PORT_MOTOR_SM:     "motor_sm",
    PORT_MOTOR_LAP:    "motor_lap",
    PORT_MOTOR_SERVO:  "motor_servo_signal",
    PORT_SERVO:        "servo",
    PORT_ENCODER:      "encoder",
    PORT_ULTRASONIC:   "ultrasonic",
    PORT_I2C:          "i2c",
    PORT_GPIO_IN:      "gpio_in",
    PORT_GPIO_OUT:     "gpio_out",
    PORT_UART:         "uart",
    PORT_VL53L0X:      "vl53l0x",
    PORT_TFLUNA:       "tfluna",
    PORT_TFMINI:       "tfmini",
}

PORT_TYPE_IDS = {v: k for k, v in PORT_TYPE_NAMES.items()}

# Number of state data bytes per port type
PORT_STATE_SIZES = {
    PORT_MOTOR_SM:    2,   # i16 value
    PORT_MOTOR_LAP:   2,   # i16 value
    PORT_MOTOR_SERVO: 2,   # i16 value
    PORT_SERVO:       2,   # u16 angle
    PORT_ENCODER:     8,   # i32 count + i32 velocity
    PORT_ULTRASONIC:  3,   # u16 distance_mm + u8 valid
    PORT_I2C:         0,   # no data
    PORT_GPIO_IN:     1,   # u8 state
    PORT_GPIO_OUT:    1,   # u8 state
    PORT_UART:        0,   # no per-frame state; data flows via RSP_UART_RX packets
    PORT_VL53L0X:     3,   # u16 distance_mm + u8 valid (same layout as ultrasonic)
    PORT_TFLUNA:      0,   # daemon parses RSP_UART_RX; no RP2040 state bytes
    PORT_TFMINI:      0,   # daemon parses RSP_UART_RX; no RP2040 state bytes
}


def _crc8(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) if (crc & 0x80) else (crc << 1)
            crc &= 0xFF
    return crc


def build_packet(msg_type: int, payload: bytes = b"") -> bytes:
    header = bytes([msg_type, len(payload)]) + payload
    return bytes([SYNC]) + header + bytes([_crc8(header)])


# -------------------------------------------------------------------
# Command builders
# -------------------------------------------------------------------

def cmd_configure(port_id: int, port_type: int) -> bytes:
    return build_packet(CMD_CONFIGURE, struct.pack("<BB", port_id, port_type))

def cmd_set_motor(port_id: int, value: int) -> bytes:
    return build_packet(CMD_SET_MOTOR, struct.pack("<Bh", port_id, value))

def cmd_set_servo(port_id: int, pulse_us: int) -> bytes:
    return build_packet(CMD_SET_SERVO, struct.pack("<BH", port_id, pulse_us))

def cmd_set_velocity(port_id: int, velocity_x10: int) -> bytes:
    return build_packet(CMD_SET_VELOCITY, struct.pack("<Bi", port_id, velocity_x10))

def cmd_set_pid(port_id: int, kp: float, ki: float, kd: float, integral_max: float = 0.0) -> bytes:
    if integral_max > 0.0:
        return build_packet(CMD_SET_PID, struct.pack("<Bffff", port_id, kp, ki, kd, float(integral_max)))
    return build_packet(CMD_SET_PID, struct.pack("<Bfff", port_id, kp, ki, kd))

def cmd_reset_encoder(port_id: int) -> bytes:
    return build_packet(CMD_RESET_ENC, struct.pack("<B", port_id))

def cmd_set_gpio(port_id: int, state: int) -> bytes:
    return build_packet(CMD_SET_GPIO, struct.pack("<BB", port_id, state))

def cmd_set_rate(hz: int) -> bytes:
    return build_packet(CMD_SET_RATE, struct.pack("<H", hz))

def cmd_stop_all() -> bytes:
    return build_packet(CMD_STOP_ALL)

def cmd_set_servo_range(port_id: int, min_us: int, max_us: int) -> bytes:
    return build_packet(CMD_SET_SERVO_RANGE, struct.pack("<BHH", port_id, min_us, max_us))

def cmd_attach_encoder(motor_port: int, encoder_port: int) -> bytes:
    return build_packet(CMD_ATTACH_ENC, struct.pack("<BB", motor_port, encoder_port))

def cmd_config_done() -> bytes:
    return build_packet(CMD_CONFIG_DONE)

def cmd_reset() -> bytes:
    return build_packet(CMD_RESET)

def cmd_heartbeat() -> bytes:
    return build_packet(CMD_HEARTBEAT)

def cmd_measure_pulse(port_id: int) -> bytes:
    return build_packet(CMD_MEASURE_PULSE, bytes([port_id]))

def cmd_pca_init(prescale: int) -> bytes:
    return build_packet(CMD_PCA_INIT, bytes([prescale & 0xFF]))

def cmd_pca_set_ch(channel: int, on_count: int, off_count: int) -> bytes:
    return build_packet(CMD_PCA_SET_CH, struct.pack("<BHH", channel, on_count, off_count))

def cmd_pca_ch_off(channel: int) -> bytes:
    return build_packet(CMD_PCA_CH_OFF, bytes([channel & 0xFF]))

def cmd_set_position(port_id: int, target: int, speed_limit: int, keep_integral: bool = False) -> bytes:
    if keep_integral:
        return build_packet(CMD_SET_POSITION, struct.pack("<BiHB", port_id, target, speed_limit, 0x01))
    return build_packet(CMD_SET_POSITION, struct.pack("<BiH", port_id, target, speed_limit))

def cmd_invert_encoder(port_id: int, inverted: bool) -> bytes:
    return build_packet(CMD_INVERT_ENCODER, struct.pack("<BB", port_id, 1 if inverted else 0))

def cmd_set_pos_options(port_id: int, deadband: float = 0.0, output_floor: float = 0.0,
                        ramp_rate: float = 0.0, d_alpha: float = 1.0,
                        approach_factor: float = 0.0) -> bytes:
    return build_packet(CMD_SET_POS_OPTIONS,
                        struct.pack("<Bfffff", port_id, deadband, output_floor, ramp_rate, d_alpha, approach_factor))

def cmd_configure_uart(port_id: int, baud: int = 115200) -> bytes:
    return build_packet(CMD_CONFIGURE, struct.pack("<BBI", port_id, PORT_UART, baud))

def cmd_uart_tx(port_id: int, data: bytes) -> bytes:
    # payload: [port_id:u8][len:u8][data...]
    if len(data) > 255:
        data = data[:255]
    return build_packet(CMD_UART_TX, bytes([port_id, len(data)]) + data)


# -------------------------------------------------------------------
# Packet parser
# -------------------------------------------------------------------

class PacketParser:
    """Stateful parser that reassembles packets from a byte stream."""

    _WAIT_SYNC = 0
    _WAIT_TYPE = 1
    _WAIT_LEN  = 2
    _WAIT_DATA = 3
    _WAIT_CRC  = 4

    def __init__(self):
        self._state = self._WAIT_SYNC
        self._msg_type = 0
        self._length = 0
        self._payload = bytearray()

    def feed(self, data: bytes) -> list[dict]:
        """Feed raw bytes; returns a list of fully-parsed packets."""
        packets = []
        for byte in data:
            pkt = self._process(byte)
            if pkt:
                packets.append(pkt)
        return packets

    def _process(self, byte: int) -> dict | None:
        if self._state == self._WAIT_SYNC:
            if byte == SYNC:
                self._state = self._WAIT_TYPE
        elif self._state == self._WAIT_TYPE:
            self._msg_type = byte
            self._state = self._WAIT_LEN
        elif self._state == self._WAIT_LEN:
            self._length = byte
            self._payload = bytearray()
            self._state = self._WAIT_DATA if byte > 0 else self._WAIT_CRC
        elif self._state == self._WAIT_DATA:
            self._payload.append(byte)
            if len(self._payload) == self._length:
                self._state = self._WAIT_CRC
        elif self._state == self._WAIT_CRC:
            self._state = self._WAIT_SYNC
            header = bytes([self._msg_type, self._length]) + bytes(self._payload)
            if _crc8(header) == byte:
                return self._decode(self._msg_type, bytes(self._payload))
        return None

    def _decode(self, msg_type: int, payload: bytes) -> dict:
        if msg_type == RSP_ACK and len(payload) >= 1:
            return {"type": "ack", "cmd": payload[0]}

        if msg_type == RSP_ERROR and len(payload) >= 1:
            code = payload[0]
            msg = payload[1:].rstrip(b"\x00").decode("ascii", errors="replace")
            return {"type": "error", "code": code, "message": msg}

        if msg_type == RSP_STATE:
            return self._decode_state(payload)

        if msg_type == RSP_UART_RX:
            port_id = payload[0] if len(payload) >= 1 else 15
            return {"type": "uart_rx", "port": port_id, "data": bytes(payload[1:])}

        if msg_type == RSP_MEASURE_PULSE and len(payload) >= 4:
            pulse_us = struct.unpack_from("<I", payload, 0)[0]
            return {"type": "measure_pulse", "pulse_us": pulse_us}

        return {"type": "unknown", "msg_type": msg_type, "payload": payload.hex()}

    def _decode_state(self, payload: bytes) -> dict:
        if len(payload) < 5:
            return {"type": "state", "ts": 0, "ports": {}}

        ts, count = struct.unpack_from("<IB", payload, 0)
        offset = 5
        ports: dict[str, Any] = {}

        for _ in range(count):
            if offset + 2 > len(payload):
                break
            port_id, port_type = payload[offset], payload[offset + 1]
            offset += 2

            size = PORT_STATE_SIZES.get(port_type, 0)
            if offset + size > len(payload):
                break

            pdata = payload[offset : offset + size]
            offset += size

            name = PORT_TYPE_NAMES.get(port_type, "unknown")
            parsed: dict[str, Any] = {"type": name}

            if port_type in (PORT_MOTOR_SM, PORT_MOTOR_LAP, PORT_MOTOR_SERVO):
                parsed["value"] = struct.unpack_from("<h", pdata)[0]
            elif port_type == PORT_SERVO:
                parsed["pulse_us"] = struct.unpack_from("<H", pdata)[0]
            elif port_type == PORT_ENCODER:
                cnt, vel = struct.unpack_from("<ii", pdata)
                parsed["count"] = cnt
                parsed["velocity"] = vel
            elif port_type == PORT_ULTRASONIC:
                dist, valid = struct.unpack_from("<HB", pdata)
                parsed["distance_mm"] = dist
                parsed["valid"] = bool(valid)
            elif port_type == PORT_VL53L0X:
                dist, valid = struct.unpack_from("<HB", pdata)
                parsed["distance_mm"] = dist
                parsed["valid"] = bool(valid)
            elif port_type in (PORT_GPIO_IN, PORT_GPIO_OUT):
                parsed["state"] = pdata[0]

            ports[str(port_id)] = parsed

        return {"type": "state", "ts": ts, "ports": ports}
