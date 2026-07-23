/*
 * BNO085 Timing Diagnostic
 *
 * Probes 0x4A and 0x4B every 50 ms from the moment I2C is ready.
 * Prints a timestamped result for EVERY probe — both write and read —
 * so we can see exactly when the device first ACKs each type of transaction.
 *
 * GP4 = SDA, GP5 = SCL, I2C0, 100 kHz.
 * Open the USB serial port to see output (any baud — USB CDC ignores it).
 */

#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"

#define SDA_PIN  4
#define SCL_PIN  5
#define LED_PIN 25

#define ADDR_A  0x4Au
#define ADDR_B  0x4Bu

static uint32_t ms(void) { return to_ms_since_boot(get_absolute_time()); }
static const char *s(int r) { return r >= 0 ? "ACK" : "NAK"; }

int main(void) {
    stdio_init_all();

    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);
    gpio_put(LED_PIN, 1);

    // Short wait for USB CDC to enumerate — much less than the previous 3 s.
    // We want to capture data from the first 200 ms onward.
    sleep_ms(200);

    printf("\n\n");
    printf("==============================================\n");
    printf("  BNO085 Timing Diagnostic\n");
    printf("  GP%d=SDA  GP%d=SCL  I2C0  100 kHz\n", SDA_PIN, SCL_PIN);
    printf("  Probing every 50 ms — write AND read\n");
    printf("==============================================\n");
    printf("  Format:  [ms]  W:4A W:4B  R:4A R:4B\n\n");

    i2c_init(i2c0, 100 * 1000);
    gpio_set_function(SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(SCL_PIN, GPIO_FUNC_I2C);
    gpio_pull_up(SDA_PIN);
    gpio_pull_up(SCL_PIN);

    sleep_ms(5);   // brief bus settle after init

    uint8_t dummy = 0;
    uint8_t rbuf;
    bool found = false;

    // Probe every 50 ms for up to 6 s so we see the full boot window.
    uint32_t stop = ms() + 6000u;
    while (ms() < stop) {
        gpio_xor_mask(1u << LED_PIN);

        uint32_t t = ms();
        int wa = i2c_write_blocking(i2c0, ADDR_A, &dummy, 1, false);
        int wb = i2c_write_blocking(i2c0, ADDR_B, &dummy, 1, false);
        int ra = i2c_read_blocking (i2c0, ADDR_A, &rbuf,  1, false);
        int rb = i2c_read_blocking (i2c0, ADDR_B, &rbuf,  1, false);

        printf("[%5lu ms]  W:%s %s  R:%s %s",
               t, s(wa), s(wb), s(ra), s(rb));

        if ((wa >= 0 || wb >= 0 || ra >= 0 || rb >= 0) && !found) {
            printf("  ← FIRST RESPONSE");
            found = true;
        }
        printf("\n");

        sleep_ms(50);
    }

    printf("\nDone. Device %sfound.\n", found ? "" : "NOT ");
    while (true) {
        gpio_xor_mask(1u << LED_PIN);
        sleep_ms(500);
    }
}
