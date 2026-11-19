// USB-AUDIO-MAX firmware ("Bread Modular 6x8"): CH32V307 USB 2.0 High-Speed
// UAC2 interface, 6 in / 8 out, 24-bit, 48 kHz, for the PCM3168A on the
// carrier (TDM), with per-channel DC calibration and a CDC console. The codec
// is the clock master; the host follows it through the explicit feedback
// endpoint. The DFU bootloader (../bootloader) takes updates over the same
// USB-C without the BOOT / RESET buttons.
#include "audio.h"
#include "board.h"
#include "cal.h"
#include "console.h"
#include "tusb.h"

int main(void) {
  board_init();
  audio_init();
  cal_init();

  tusb_rhport_init_t const dev_init = {.role = TUSB_ROLE_DEVICE, .speed = TUSB_SPEED_HIGH};
  tusb_init(0, &dev_init);

  // Self-powered: hold the D+ pull-up off while no host drives VBUS (PA9),
  // debounced: a single low read used to drop the link (the host saw an unplug).
  bool vbus = board_vbus_task();
  if (!vbus) tud_disconnect();

  while (1) {
    tud_task();
    audio_task();
    cal_task();
    console_task();
    board_boot_task(tud_mounted());

    bool const now = board_vbus_task();
    if (now != vbus) {
      vbus = now;
      if (vbus) {
        tud_connect();
      } else {
        tud_disconnect();
      }
    }
  }
}
