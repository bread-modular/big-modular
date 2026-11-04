#include "board.h"

#include <stdio.h>
#include <string.h>

#include "boot.h"
#include "i2s.h"
#include "tusb.h"

static volatile uint32_t ticks_ms;

__attribute__((interrupt)) void SysTick_Handler(void) {
  SysTick->SR = 0;
  ticks_ms++;
}

// Audio worker, pended by the USBHS capture and the I2S DMA handlers: USB
// transfer processing (re-arms the iso endpoints) and the I2S halves, one at
// a time with the USB work in between.
__attribute__((interrupt)) void SW_Handler(void) {
  do {
    tud_int_handler(0);
  } while (i2s_service());
}

__attribute__((interrupt)) void HardFault_Handler(void) {
  NVIC_SystemReset();
}

uint32_t board_millis(void) {
  return ticks_ms;
}

void board_delay_ms(uint32_t ms) {
  uint32_t start = ticks_ms;
  while ((uint32_t) (ticks_ms - start) < ms) {
  }
}

// SysTick counts HCLK and reloads every millisecond.
void board_delay_us(uint32_t us) {
  uint32_t const per_us = SystemCoreClock / 1000000u;
  uint32_t const period = (uint32_t) SysTick->CMP + 1u;
  uint32_t last = (uint32_t) SysTick->CNT;
  uint32_t elapsed = 0, target = us * per_us;
  while (elapsed < target) {
    uint32_t now = (uint32_t) SysTick->CNT;
    elapsed += (now >= last) ? (now - last) : (now + period - last);
    last = now;
  }
}

bool board_vbus_present(void) {
  return GPIO_ReadInputDataBit(GPIOA, GPIO_Pin_9) == Bit_SET;
}

void board_codec_reset(bool asserted) {
  GPIO_WriteBit(GPIOB, GPIO_Pin_14, asserted ? Bit_RESET : Bit_SET);
}

void board_serial(char *out, size_t len) {
  // 96-bit unique ID (ESIG UNIID1..3)
  uint32_t const *uid = (uint32_t const *) 0x1FFFF7E8;
  snprintf(out, len, "%08lX%08lX%08lX", (unsigned long) uid[0], (unsigned long) uid[1], (unsigned long) uid[2]);
}

void board_reset(void) {
  NVIC_SystemReset();
}

void board_reset_to_dfu(void) {
  RCC_APB1PeriphClockCmd(RCC_APB1Periph_PWR | RCC_APB1Periph_BKP, ENABLE);
  PWR->CTLR |= PWR_CTLR_DBP;
  BKP->DATAR1 = BOOT_DFU_MAGIC;
  tud_disconnect();
  board_delay_ms(20);
  NVIC_SystemReset();
}

// Rewrites the DFU bootloader (flash 0x0000 up to BOOT_APP_BASE) and reads it
// back, so a bootloader fix needs no BOOT / RESET either. The application keeps
// running from its own sectors; a reset before this returns true would leave no
// bootloader (recovery: BOOT + RESET, ../flash.sh --full). Flash erase, program
// and read-back need a flash clock <= 60 MHz, so HCLK is halved meanwhile (WCH
// FLASH example, note b). The flash controller takes the 0x08000000 alias.
bool board_write_bootloader(uint8_t const *img, uint32_t len) {
  static uint32_t page[64];
  if (len < 8 || len > BOOT_APP_BASE) return false;
  uint32_t const span = (len + 255u) & ~255u;
  RCC->CFGR0 = (RCC->CFGR0 & ~RCC_HPRE) | RCC_HPRE_DIV2;
  bool ok = FLASH_ROM_ERASE(FLASH_BASE, BOOT_APP_BASE) == FLASH_COMPLETE;
  for (uint32_t off = 0; ok && off < span; off += 256u) {
    uint32_t const n = len - off < 256u ? len - off : 256u;
    for (uint32_t i = 0; i < 64; i++) page[i] = 0xE339E339u;   // erased value
    memcpy(page, img + off, n);
    ok = FLASH_ROM_WRITE(FLASH_BASE + off, page, 256u) == FLASH_COMPLETE &&
         memcmp((void const *) (FLASH_BASE + off), page, 256u) == 0;
    IWDG->CTLR = 0xAAAA;
  }
  RCC->CFGR0 = (RCC->CFGR0 & ~RCC_HPRE) | RCC_HPRE_DIV1;
  return ok;
}

// A new image (BKP DATAR2 = BOOT_TRIAL_TAG | attempts) is confirmed after 3 s
// configured by the host. Without that within BOOT_TRIAL_MS of VBUS it resets,
// so the bootloader counts a failed start; crashes and watchdog resets count too.
void board_boot_task(bool configured) {
  static bool checked, trial;
  static uint32_t vbus_since, configured_since;
  IWDG->CTLR = 0xAAAA;
  uint32_t const now = ticks_ms;
  if (!checked) {
    checked = true;
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_PWR | RCC_APB1Periph_BKP, ENABLE);
    trial = (BKP->DATAR2 & BOOT_TRIAL_MASK) == BOOT_TRIAL_TAG;
    vbus_since = configured_since = now;
  }
  if (!trial) return;
  if (!configured) configured_since = now;
  if (!board_vbus_present()) vbus_since = now;
  if (now - configured_since >= 3000u) {
    PWR->CTLR |= PWR_CTLR_DBP;
    BKP->DATAR2 = 0;
    PWR->CTLR &= ~PWR_CTLR_DBP;
    trial = false;
  } else if (now - vbus_since >= BOOT_TRIAL_MS) {
    NVIC_SystemReset();
  }
}

void board_init(void) {
  __disable_irq();
  SystemCoreClockUpdate();

  // The startup enables 4-level nesting (preemption bits [7:6]). The USBHS
  // interrupt only captures transfer status (dcd_ch32_usbhs.c) and preempts
  // everything; all other handlers share the level below it (nesting two deep).
  NVIC_SetPriority(USBHS_IRQn, 0x00);
  NVIC_SetPriority(Software_IRQn, 0x40);
  NVIC_SetPriority(DMA1_Channel4_IRQn, 0x40);
  NVIC_SetPriority(DMA2_Channel2_IRQn, 0x40);
  NVIC_SetPriority(SysTicK_IRQn, 0x40);
  NVIC_EnableIRQ(SysTicK_IRQn);
  SysTick->CTLR = 0;
  SysTick->SR = 0;
  SysTick->CNT = 0;
  SysTick->CMP = SystemCoreClock / 1000 - 1;
  SysTick->CTLR = 0xF;   // enable, interrupt, HCLK, auto-reload

  // USBHS PHY PLL from the 8 MHz HSE (as the WCH EVT / TinyUSB BSP)
  RCC_USBCLK48MConfig(RCC_USBCLK48MCLKSource_USBPHY);
  RCC_USBHSPLLCLKConfig(RCC_HSBHSPLLCLKSource_HSE);
  RCC_USBHSConfig(RCC_USBPLL_Div2);
  RCC_USBHSPLLCKREFCLKConfig(RCC_USBHSPLLCKREFCLK_4M);
  RCC_USBHSPHYPLLALIVEcmd(ENABLE);
  RCC_AHBPeriphClockCmd(RCC_AHBPeriph_USBHS, ENABLE);

  RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOB | RCC_APB2Periph_AFIO, ENABLE);

  GPIO_InitTypeDef gpio = {0};
  // Codec RST: low (held in reset) until the codec driver releases it.
  GPIO_ResetBits(GPIOB, GPIO_Pin_14);
  gpio.GPIO_Pin = GPIO_Pin_14;
  gpio.GPIO_Mode = GPIO_Mode_Out_PP;
  gpio.GPIO_Speed = GPIO_Speed_2MHz;
  GPIO_Init(GPIOB, &gpio);

  // VBUS sense
  gpio.GPIO_Pin = GPIO_Pin_9;
  gpio.GPIO_Mode = GPIO_Mode_IN_FLOATING;
  GPIO_Init(GPIOA, &gpio);

  __enable_irq();
}
