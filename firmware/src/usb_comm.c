#include "usb_comm.h"
#include "protocol.h"
#include "crc8.h"
#include "pico/stdlib.h"
#include "pico/stdio.h"
#include <string.h>

// ─── RX state machine ────────────────────────────────────────────────────────
typedef enum {
    RX_WAIT_SYNC,
    RX_WAIT_TYPE,
    RX_WAIT_LEN,
    RX_WAIT_PAYLOAD,
    RX_WAIT_CRC,
} RxState;

static RxState  rx_state   = RX_WAIT_SYNC;
static uint8_t  rx_type    = 0;
static uint8_t  rx_len     = 0;
static uint8_t  rx_payload[PROTO_MAX_LEN];
static uint8_t  rx_idx     = 0;

// Completed packet staging area — written by the state machine, read by caller
static bool     pkt_ready  = false;
static uint8_t  pkt_type   = 0;
static uint8_t  pkt_payload[PROTO_MAX_LEN];
static uint8_t  pkt_len    = 0;

void usb_comm_init(void) {
    // stdio_init_all() is called in main; nothing extra needed here
    rx_state  = RX_WAIT_SYNC;
    pkt_ready = false;
}

// Feed one byte into the framing state machine
static void rx_feed(uint8_t b) {
    switch (rx_state) {
        case RX_WAIT_SYNC:
            if (b == PROTO_SYNC) rx_state = RX_WAIT_TYPE;
            break;

        case RX_WAIT_TYPE:
            rx_type  = b;
            rx_state = RX_WAIT_LEN;
            break;

        case RX_WAIT_LEN:
            if (b > PROTO_MAX_LEN) {
                // Oversized payload — drop and resync
                rx_state = RX_WAIT_SYNC;
                break;
            }
            rx_len   = b;
            rx_idx   = 0;
            rx_state = (b == 0) ? RX_WAIT_CRC : RX_WAIT_PAYLOAD;
            break;

        case RX_WAIT_PAYLOAD:
            rx_payload[rx_idx++] = b;
            if (rx_idx == rx_len) rx_state = RX_WAIT_CRC;
            break;

        case RX_WAIT_CRC: {
            // CRC covers TYPE + LEN + PAYLOAD
            uint8_t crc_buf[2 + PROTO_MAX_LEN];
            crc_buf[0] = rx_type;
            crc_buf[1] = rx_len;
            memcpy(&crc_buf[2], rx_payload, rx_len);
            uint8_t expected = crc8(crc_buf, 2 + rx_len);

            if (b == expected && !pkt_ready) {
                pkt_type = rx_type;
                pkt_len  = rx_len;
                memcpy(pkt_payload, rx_payload, rx_len);
                pkt_ready = true;
            }
            // Always resync after CRC byte regardless of match
            rx_state = RX_WAIT_SYNC;
            break;
        }
    }
}

bool usb_comm_recv(uint8_t *out_type, uint8_t *out_payload, uint8_t *out_len) {
    // Drain available USB bytes into the state machine
    int c;
    while ((c = getchar_timeout_us(0)) != PICO_ERROR_TIMEOUT) {
        rx_feed((uint8_t)c);
    }

    if (pkt_ready) {
        *out_type = pkt_type;
        *out_len  = pkt_len;
        memcpy(out_payload, pkt_payload, pkt_len);
        pkt_ready = false;
        return true;
    }
    return false;
}

void usb_comm_send(uint8_t type, const uint8_t *payload, uint8_t len) {
    // Build CRC over TYPE + LEN + PAYLOAD
    uint8_t crc_buf[2 + PROTO_MAX_LEN];
    crc_buf[0] = type;
    crc_buf[1] = len;
    if (len) memcpy(&crc_buf[2], payload, len);
    uint8_t crc = crc8(crc_buf, 2 + len);

    // Frame: SYNC TYPE LEN PAYLOAD CRC
    putchar_raw(PROTO_SYNC);
    putchar_raw(type);
    putchar_raw(len);
    for (uint8_t i = 0; i < len; i++) putchar_raw(payload[i]);
    putchar_raw(crc);
}

void usb_comm_send_ack(uint8_t cmd_type) {
    usb_comm_send(RESP_ACK, &cmd_type, 1);
}

void usb_comm_send_error(uint8_t code, const char *msg) {
    uint8_t buf[PROTO_MAX_LEN];
    buf[0] = code;
    size_t msglen = strlen(msg);
    if (msglen > PROTO_MAX_LEN - 2) msglen = PROTO_MAX_LEN - 2;
    memcpy(&buf[1], msg, msglen);
    buf[1 + msglen] = '\0';  // null terminator
    usb_comm_send(RESP_ERROR, buf, (uint8_t)(2 + msglen));
}
