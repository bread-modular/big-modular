// USB-AUDIO firmware: CH32V307 USB 2.0 High-Speed UAC2 interface (2 in / 2 out,
// 24-bit, 48 / 96 / 192 kHz) for the CS4270 codec on the carrier, plus a CDC
// console. The codec is the clock master; both I2S ports run as slaves and the
// host follows the codec clock through the explicit feedback endpoint.
#include "audio.h"
#include "board.h"
#include "console.h"
#include "tusb.h"

int main(void) {
  board_init();
  audio_init();

  tusb_rhport_init_t const dev_init = {.role = TUSB_ROLE_DEVICE, .speed = TUSB_SPEED_HIGH};
  tusb_init(0, &dev_init);

  // Self-powered: hold the D+ pull-up off while no host drives VBUS (PA9).
  bool vbus = board_vbus_present();
  if (!vbus) tud_disconnect();

  while (1) {
    tud_task();
    audio_task();
    console_task();
    board_boot_task(tud_mounted());

    bool const now = board_vbus_present();
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
