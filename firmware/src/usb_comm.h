#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

// Maximum number of bytes in a single outbound packet (framed)
#define USB_TX_BUF_SIZE 256

// Initialise USB serial and internal state
void usb_comm_init(void);

// Send a pre-built payload as a framed packet.
// type:    response type byte (e.g. RESP_STATE)
// payload: raw payload bytes
// len:     payload length
void usb_comm_send(uint8_t type, const uint8_t *payload, uint8_t len);

// Try to read one complete, CRC-verified packet from USB.
// Returns true when a packet is ready; fills *out_type and copies payload into
// out_payload (up to PROTO_MAX_LEN bytes).  out_len receives payload length.
bool usb_comm_recv(uint8_t *out_type, uint8_t *out_payload, uint8_t *out_len);

// Send a one-byte ACK for the given command type
void usb_comm_send_ack(uint8_t cmd_type);

// Send an error packet: code + null-terminated message string
void usb_comm_send_error(uint8_t code, const char *msg);
