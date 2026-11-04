// USB-AUDIO DFU bootloader: lets ../flash.sh update the application over the
// panel USB-C without the BOOT / RESET buttons (the WCH ROM bootloader on
// BOOT stays as the recovery path).
//
// Reset -> run the application at BOOT_APP_BASE, unless it asked for DFU
// (console `dfu`), its first sector is blank or a freshly downloaded image
// used up its start attempts (boot.h).
// DFU mode is a DFU 1.1 device 1209:0002 (dfu-util -a 0 -D usb-audio.bin):
// each 4 KiB block is one flash sector from BOOT_APP_BASE up. Block 0 holds
// the application's entry and is written last, at manifestation, so an
// interrupted download leaves a blank entry and the board stays in DFU.
#include <string.h>

#include "boot.h"
#include "ch32v30x.h"
#include "tusb.h"

#define DFU_BLOCK    CFG_TUD_DFU_XFER_BUFSIZE
// DFU on request with an application present: back to it if no download starts.
#define DFU_IDLE_MS  60000u

__attribute__((naked, used)) void USBHS_IRQHandler(void) {
  __asm volatile("li a0, 0\n\t call dcd_int_handler\n\t mret");
}
__attribute__((used)) static void (*const usbhs_isr_keep)(uint8_t) = dcd_int_handler;

static volatile uint32_t ticks_ms;

__attribute__((interrupt)) void SysTick_Handler(void) {
  SysTick->SR = 0;
  ticks_ms++;
}

static uint32_t first_block[DFU_BLOCK / 4];
static uint32_t first_len;
static bool reset_pending;
static uint32_t reset_at, idle_reset_at;
static bool blank_app;   // set before main(): the new image used up its start attempts

// The CPU runs the code flash at 0x00000000; the flash controller (and reads
// that must see it right after an erase / program) use its 0x08000000 alias.
#define FLASH_ALIAS(addr) (FLASH_BASE + (addr))

// Erased CH32V30x flash reads 0xE339E339, not 0xFFFFFFFF.
static bool app_present(void) {
  uint32_t const w = *(volatile uint32_t const *) FLASH_ALIAS(BOOT_APP_BASE);
  return w != 0xE339E339u && w != 0xFFFFFFFFu && w != 0u;
}

static void bkp_open(void) {
  RCC->APB1PCENR |= RCC_PWREN | RCC_BKPEN;
  PWR->CTLR |= PWR_CTLR_DBP;
}

static void bkp_close(void) {
  PWR->CTLR &= ~PWR_CTLR_DBP;
  RCC->APB1PCENR &= ~(RCC_PWREN | RCC_BKPEN);
}

// Application or DFU mode? Counts the start attempts of a new image.
static bool app_wanted(void) {
  bool dfu = !app_present();
  bkp_open();
  if (BKP->DATAR1 == BOOT_DFU_MAGIC) dfu = true;
  BKP->DATAR1 = 0;
  uint16_t const trial = (uint16_t) BKP->DATAR2;
  if (!dfu && (trial & BOOT_TRIAL_MASK) == BOOT_TRIAL_TAG) {
    if ((trial & 0xFFu) >= BOOT_TRIAL_MAX) {
      BKP->DATAR2 = 0;
      blank_app = true;
      dfu = true;
    } else {
      BKP->DATAR2 = (uint16_t) (trial + 1u);
    }
  }
  bkp_close();
  return !dfu;
}

// Started first: that forces the LSI on, which the prescaler / reload update needs.
static void iwdg_start(void) {
  IWDG->CTLR = 0xCCCC;
  IWDG->CTLR = 0x5555;
  IWDG->PSCR = 4;   // LSI / 64
  IWDG->RLDR = BOOT_IWDG_RELOAD;
  for (uint32_t i = 0; i < 100000u && (IWDG->STATR & 3u); i++) {
  }
  IWDG->CTLR = 0xAAAA;
}

void __real_SystemInit(void);

// The WCH startup calls SystemInit in machine mode, then enters main() in user
// mode (mret with MPP = U). The application's startup writes machine CSRs, so
// it is entered from here, before the clocks are touched
// (-Wl,--wrap=SystemInit).
void __wrap_SystemInit(void) {
  if (app_wanted()) {
    iwdg_start();
    __asm volatile("csrci mstatus, 8");   // MIE off until the application's startup sets mtvec
    ((void (*)(void)) BOOT_APP_BASE)();
  }
  __real_SystemInit();
}

// Erase + program whole 256-byte pages (fast mode), pads with the erased value
// and reads every page back. Returns a DFU status.
static uint8_t flash_write(uint32_t addr, uint8_t const *data, uint32_t len) {
  static uint32_t page[64];
  uint32_t const span = (len + 255u) & ~255u;
  if (!len || (addr & 255u) || addr < BOOT_APP_BASE || addr + span > BOOT_APP_END) return DFU_STATUS_ERR_ADDRESS;
  if (FLASH_ROM_ERASE(FLASH_ALIAS(addr), span) != FLASH_COMPLETE) return DFU_STATUS_ERR_ERASE;
  for (uint32_t off = 0; off < span; off += 256u) {
    uint32_t const n = len - off < 256u ? len - off : 256u;
    for (uint32_t i = 0; i < 64; i++) page[i] = 0xE339E339u;
    memcpy(page, data + off, n);
    if (FLASH_ROM_WRITE(FLASH_ALIAS(addr + off), page, 256u) != FLASH_COMPLETE) return DFU_STATUS_ERR_PROG;
    if (memcmp((void const *) FLASH_ALIAS(addr + off), page, 256u)) return DFU_STATUS_ERR_VERIFY;
  }
  return DFU_STATUS_OK;
}

uint32_t tud_dfu_get_timeout_cb(uint8_t alt, uint8_t state) {
  return state == DFU_DNBUSY ? 20 : 0;
}

void tud_dfu_download_cb(uint8_t alt, uint16_t block_num, uint8_t const *data, uint16_t length) {
  uint32_t const addr = BOOT_APP_BASE + (uint32_t) block_num * DFU_BLOCK;
  uint8_t status;
  idle_reset_at = 0;
  if (block_num == 0) {
    // Blank the entry first, keep block 0 for the manifestation.
    first_len = 0;
    if (FLASH_ROM_ERASE(FLASH_ALIAS(BOOT_APP_BASE), DFU_BLOCK) != FLASH_COMPLETE || app_present()) {
      status = DFU_STATUS_ERR_ERASE;
    } else {
      memcpy(first_block, data, length);
      first_len = length;
      status = DFU_STATUS_OK;
    }
  } else if (first_len != DFU_BLOCK) {
    status = DFU_STATUS_ERR_ADDRESS;   // block 0 missing or short
  } else {
    status = flash_write(addr, data, length);
  }
  tud_dfu_finish_flashing(status);
}

void tud_dfu_manifest_cb(uint8_t alt) {
  uint8_t const status = first_len >= 8 ? flash_write(BOOT_APP_BASE, (uint8_t const *) first_block, first_len)
                                        : DFU_STATUS_ERR_FIRMWARE;
  bool const ok = status == DFU_STATUS_OK;
  first_len = 0;
  if (ok) {
    bkp_open();
    BKP->DATAR2 = BOOT_TRIAL_TAG;   // start attempt count 0
    bkp_close();
    // dfu-util polls once more about 1 s after dfuMANIFEST; reset after that.
    reset_pending = true;
    reset_at = ticks_ms + 2000;
  }
  tud_dfu_finish_flashing(status);
}

void tud_dfu_abort_cb(uint8_t alt) {
  first_len = 0;
}

void tud_dfu_detach_cb(void) {
  reset_pending = true;
  reset_at = ticks_ms + 20;
}

int main(void) {
  NVIC_EnableIRQ(SysTicK_IRQn);
  SysTick->CTLR = 0;
  SysTick->SR = 0;
  SysTick->CNT = 0;
  SysTick->CMP = SystemCoreClock / 1000 - 1;
  SysTick->CTLR = 0xF;

  if (blank_app) FLASH_ROM_ERASE(FLASH_ALIAS(BOOT_APP_BASE), DFU_BLOCK);
  if (app_present()) idle_reset_at = DFU_IDLE_MS;

  RCC_USBCLK48MConfig(RCC_USBCLK48MCLKSource_USBPHY);
  RCC_USBHSPLLCLKConfig(RCC_HSBHSPLLCLKSource_HSE);
  RCC_USBHSConfig(RCC_USBPLL_Div2);
  RCC_USBHSPLLCKREFCLKConfig(RCC_USBHSPLLCKREFCLK_4M);
  RCC_USBHSPHYPLLALIVEcmd(ENABLE);
  RCC_AHBPeriphClockCmd(RCC_AHBPeriph_USBHS, ENABLE);

  tusb_rhport_init_t const dev_init = {.role = TUSB_ROLE_DEVICE, .speed = TUSB_SPEED_HIGH};
  tusb_init(0, &dev_init);

  while (1) {
    tud_task();
    IWDG->CTLR = 0xAAAA;   // in case a watchdog is running
    uint32_t const now = ticks_ms;
    if ((reset_pending && (int32_t) (now - reset_at) >= 0) || (idle_reset_at && now >= idle_reset_at)) {
      tud_disconnect();
      for (uint32_t t = ticks_ms; ticks_ms - t < 20;) {
      }
      NVIC_SystemReset();
    }
  }
}
