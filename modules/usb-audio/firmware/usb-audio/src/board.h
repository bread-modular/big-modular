// MCU board: clocks, SysTick, pins that are not I2S/I2C, USBHS interrupt.
//
// Pin map (modules/usb-audio/Code.md, MCU board S1):
//   PB6/PB7  USBHS D-/D+          PA9   VBUS sense (10k/20k divider)
//   PB13/PB12/PB15  I2S2 CK/WS/SD (slave RX <- codec SDOUT)
//   PB3/PA15/PB5    I2S3 CK/WS/SD (slave TX -> codec SDIN)
//   PB10/PB11 I2C2 SCL/SDA        PB14  codec RST (10k pull-down on the carrier)
#ifndef BOARD_H_
#define BOARD_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "ch32v30x.h"

void board_init(void);
uint32_t board_millis(void);
void board_delay_ms(uint32_t ms);
void board_delay_us(uint32_t us);
bool board_vbus_present(void);
void board_codec_reset(bool asserted);
void board_serial(char *out, size_t len);
void board_reset(void);
// Reset into the DFU bootloader (../bootloader) for ../flash.sh.
void board_reset_to_dfu(void);
// Rewrite + verify the DFU bootloader from RAM (console `blwrite`). Stop I2S first.
bool board_write_bootloader(uint8_t const *img, uint32_t len);
// Settings page: the last 256 bytes of the application area, which the linker
// script leaves free (Makefile). The DFU bootloader erases only the pages it
// writes, so the page survives firmware updates; ../flash.sh --full erases it.
#define BOARD_SETTINGS_BYTES 256u
void const *board_settings(void);
// Erase the page and write `len` bytes (0: erase only), verified. Stop I2S first.
bool board_settings_write(void const *data, uint32_t len);
uint32_t board_crc32(void const *data, uint32_t len);
// Main loop: feeds the bootloader's watchdog and confirms a newly downloaded
// image once the host has kept it configured (../bootloader/src/boot.h).
void board_boot_task(bool configured);

// Critical section against the I2S DMA and USB processing handlers that keeps
// the USBHS capture interrupt (priority 0, board_init) running: masks the
// priorities >= 0x40 through the PFIC threshold.
static inline uint32_t board_irq_mask(void) {
  uint32_t const prev = PFIC->ITHRESDR;
  PFIC->ITHRESDR = 0x40;
  (void) PFIC->ITHRESDR;
  return prev;
}

static inline void board_irq_restore(uint32_t prev) {
  PFIC->ITHRESDR = prev;
}

#endif
