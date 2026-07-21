#pragma once
#include <stdint.h>

// Half-duplex serial mode switching for GoBilda dual-mode servos.
// Sends pre-computed Dynamixel/Feetech v1 protocol packets via bit-bang UART
// at 76800 baud on the servo's signal pin (S-port GPIO).
//
// mode: 0 = positional (standard RC servo), 1 = continuous rotation
//
// Blocks for ~120 ms while the servo writes EEPROM.  Caller must restore PWM
// on the GPIO after return and wait ~300 ms for the servo's reboot to complete.
void gobilda_set_mode(uint8_t gpio_pin, uint8_t mode);
