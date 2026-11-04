// Flash map and backup registers shared with the application (usb-audio/src/board.c):
//   0x00000000  this DFU bootloader (16 KiB)
//   0x00004000  application (240 KiB), linked there
// BKP DATAR1: the application asks for DFU by writing BOOT_DFU_MAGIC and
//   resetting (console `dfu`); the bootloader clears it.
// BKP DATAR2: start attempts of a freshly downloaded application,
//   BOOT_TRIAL_TAG | count. The application clears it once the host has
//   configured it; a crash, a watchdog reset or no host configuration within
//   BOOT_TRIAL_MS (with VBUS) is a failed attempt. After BOOT_TRIAL_MAX
//   failed attempts the bootloader blanks the application and stays in DFU.
// The bootloader starts the independent watchdog (BOOT_IWDG_RELOAD on the
// 40 kHz LSI / 64, ~4 s) before it jumps; the application feeds it.
#ifndef BOOT_H_
#define BOOT_H_

#define BOOT_APP_BASE      0x00004000u
#define BOOT_APP_END       0x00040000u
#define BOOT_DFU_MAGIC     0xD0F1u
#define BOOT_TRIAL_TAG     0xA500u
#define BOOT_TRIAL_MASK    0xFF00u
#define BOOT_TRIAL_MAX     3u
#define BOOT_TRIAL_MS      15000u
#define BOOT_IWDG_RELOAD   2500u

#endif
