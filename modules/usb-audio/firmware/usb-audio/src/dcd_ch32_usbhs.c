/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 Greg Davill
 * SPDX-FileCopyrightText: Copyright (c) 2023 Denis Krasutski
 * SPDX-FileCopyrightText: Copyright (c) 2022 Ha Thach (tinyusb.org)
 * SPDX-License-Identifier: MIT
 *
 * This file is part of the TinyUSB stack.
 */
/*
 * USB-AUDIO copy of TinyUSB src/portable/wch/dcd_ch32_usbhs.c (commit 8d265ad1),
 * changed so that full-duplex isochronous audio loses no transfers. The
 * controller has one INT_ST / RX_LEN for all endpoints, and the iso OUT, iso IN
 * and feedback transactions of one microframe follow each other within a few
 * microseconds: while dcd_int_handler() was still processing one completion,
 * the next ones overwrote its status (about 10 % of OUT packets lost with both
 * streams running).
 * - USBHS_IRQHandler() only captures: it is entered on ISO_ACT (packet start),
 *   waits for the packet's end and copies INT_ST / RX_LEN / FRAME_NO (and a
 *   SETUP packet) into a queue before releasing the flags.
 * - dcd_int_handler() processes the queue. The capture pends Software_IRQn,
 *   whose handler (the application's) calls tud_int_handler(); the capture
 *   interrupt preempts it. dcd_int_enable()/dcd_int_disable() mask only
 *   Software_IRQn.
 * - With the flags released at once, INT_BUSY no longer holds a non-iso
 *   endpoint off until its completion is processed, so the capture sets it to
 *   NAK (EP0 included) and the processing re-arms it.
 * - Iso OUT packets are taken whatever TOG_OK says (iso has no data toggle).
 * - A zero-length iso OUT packet does not complete the transfer: the audio
 *   class would not arm the next receive after an empty packet.
 */
#include "tusb_option.h"

#if CFG_TUD_ENABLED && defined(TUP_USBIP_WCH_USBHS) && defined(CFG_TUD_WCH_USBIP_USBHS) && \
  (CFG_TUD_WCH_USBIP_USBHS == 1)
  #include "ch32_usbhs_reg.h"

  #include "device/dcd.h"

  // Max number of bi-directional endpoints including EP0
  #define EP_MAX 16

typedef struct {
  uint8_t *buffer;
  uint16_t total_len;
  uint16_t queued_len;
  uint16_t max_size;
  bool     is_iso;
  bool     valid;
} xfer_ctl_t;

  #define XFER_CTL_BASE(_ep, _dir) &xfer_status[_ep][_dir]
static xfer_ctl_t xfer_status[EP_MAX][2];

  #define EP_TX_LEN(ep)      *(volatile uint16_t *)((volatile uint16_t *)&(USBHSD->UEP0_TX_LEN) + (ep) * 2)
  #define EP_TX_CTRL(ep)     *(volatile uint8_t *)((volatile uint8_t *)&(USBHSD->UEP0_TX_CTRL) + (ep) * 4)
  #define EP_RX_CTRL(ep)     *(volatile uint8_t *)((volatile uint8_t *)&(USBHSD->UEP0_RX_CTRL) + (ep) * 4)
  #define EP_RX_MAX_LEN(ep)  *(volatile uint16_t *)((volatile uint16_t *)&(USBHSD->UEP0_MAX_LEN) + (ep) * 2)

  #define EP_TX_DMA_ADDR(ep) *(volatile uint32_t *)((volatile uint32_t *)&(USBHSD->UEP1_TX_DMA) + (ep - 1))
  #define EP_RX_DMA_ADDR(ep) *(volatile uint32_t *)((volatile uint32_t *)&(USBHSD->UEP1_RX_DMA) + (ep - 1))

/* Endpoint Buffer */
TU_ATTR_ALIGNED(4) static uint8_t ep0_buffer[CFG_TUD_ENDPOINT0_SIZE];
static bool ep0_tog;
static bool reset_evt_pending;

/* Captured events, written by USBHS_IRQHandler(), read by dcd_int_handler() */
typedef struct {
  uint32_t setup[2];  // SETUP packet
  uint8_t  flags;     // one of USBHS_BUS_RST_FLAG / TRANSFER / SETUP / SUSPEND
  uint8_t  status;    // INT_ST
  uint16_t len;       // RX_LEN
  uint16_t frame;     // FRAME_NO
  uint32_t t;         // SysTick count
} capture_t;

  #define CAPTURE_DEPTH 16 // power of two
static capture_t capture_q[CAPTURE_DEPTH];
static volatile uint32_t capture_wr, capture_rd;
static uint16_t event_frame;
volatile uint32_t dcd_capture_overflows, dcd_capture_iso_timeouts, dcd_iso_out_empty;
volatile uint32_t dcd_delay_max, dcd_delay_late;

  // Bound of the wait for an iso packet's end (about 4 us at 144 MHz)
  #define ISO_WAIT_LOOPS 200

static void queue_in_packet(uint8_t ep_num, xfer_ctl_t* xfer) {
  uint16_t remaining = xfer->total_len - xfer->queued_len;
  uint16_t tx_len = TU_MIN(remaining, xfer->max_size);

  if (ep_num == 0) {
    memcpy(ep0_buffer, &xfer->buffer[xfer->queued_len], tx_len);
  } else {
    EP_TX_DMA_ADDR(ep_num) = (uint32_t) &xfer->buffer[xfer->queued_len];
  }

  EP_TX_LEN(ep_num) = tx_len;
  xfer->queued_len += tx_len;

  if (ep_num == 0) {
    EP_TX_CTRL(0) = USBHS_EP_T_RES_ACK | (ep0_tog ? USBHS_EP_T_TOG_1 : USBHS_EP_T_TOG_0);
    ep0_tog = !ep0_tog;
  } else if (xfer->is_iso) {
    EP_TX_CTRL(ep_num) = (EP_TX_CTRL(ep_num) & ~(USBHS_EP_T_RES_MASK)) | USBHS_EP_T_RES_NYET;
  } else {
    EP_TX_CTRL(ep_num) = (EP_TX_CTRL(ep_num) & ~(USBHS_EP_T_RES_MASK)) | USBHS_EP_T_RES_ACK;
  }
}

static void queue_out_packet(uint8_t ep_num, xfer_ctl_t* xfer) {
  uint16_t remaining = xfer->total_len - xfer->queued_len;
  uint16_t rx_len = TU_MIN(remaining, xfer->max_size);

  if (ep_num > 0) {
    EP_RX_DMA_ADDR(ep_num) = (uint32_t) &xfer->buffer[xfer->queued_len];
    EP_RX_MAX_LEN(ep_num) = rx_len;
  }

  if (ep_num == 0) {
    EP_RX_CTRL(0) = (EP_RX_CTRL(0) & ~(USBHS_EP_R_RES_MASK)) | USBHS_EP_R_RES_ACK;
  } else if (xfer->is_iso) {
    EP_RX_CTRL(ep_num) = (EP_RX_CTRL(ep_num) & ~(USBHS_EP_R_RES_MASK)) | USBHS_EP_R_RES_NYET;
  } else {
    EP_RX_CTRL(ep_num) = (EP_RX_CTRL(ep_num) & ~(USBHS_EP_R_RES_MASK)) | USBHS_EP_R_RES_ACK;
  }
}

static void update_in(uint8_t rhport, uint8_t ep_num, bool force) {
  xfer_ctl_t* xfer = XFER_CTL_BASE(ep_num, TUSB_DIR_IN);
  if (!xfer->valid) {
    return;
  }

  if (force || (xfer->total_len > xfer->queued_len)) {
    queue_in_packet(ep_num, xfer);
  } else {
    xfer->valid = false;
    if (ep_num == 0) {
      EP_TX_CTRL(0) = USBHS_EP_T_RES_NAK | (ep0_tog ? USBHS_EP_T_TOG_1 : USBHS_EP_T_TOG_0);
    } else {
      EP_TX_CTRL(ep_num) = (EP_TX_CTRL(ep_num) & ~(USBHS_EP_T_RES_MASK)) | USBHS_EP_T_RES_NAK;
    }
    dcd_event_xfer_complete(rhport, ep_num | TUSB_DIR_IN_MASK, xfer->queued_len, XFER_RESULT_SUCCESS, true);
  }
}

static void update_out(uint8_t rhport, uint8_t ep_num, uint16_t rx_len) {
  xfer_ctl_t* xfer = XFER_CTL_BASE(ep_num, TUSB_DIR_OUT);
  if (!xfer->valid) {
    return;
  }

  if (xfer->is_iso && rx_len == 0) {
    dcd_iso_out_empty++;
    return; // no samples: the receive stays armed (NYET) for the next packet
  }

  uint16_t remaining = xfer->total_len - xfer->queued_len;
  uint16_t len = TU_MIN(rx_len, TU_MIN(remaining, xfer->max_size));

  if (ep_num == 0) {
    memcpy(&xfer->buffer[xfer->queued_len], ep0_buffer, len);
  }

  xfer->queued_len += len;

  if ((xfer->queued_len == xfer->total_len) || (len < xfer->max_size)) {
    xfer->valid = false;
    if (ep_num == 0) {
      EP_RX_CTRL(0) = (EP_RX_CTRL(0) & ~(USBHS_EP_R_RES_MASK)) | USBHS_EP_R_RES_NAK;
    }
    dcd_event_xfer_complete(rhport, ep_num, xfer->queued_len, XFER_RESULT_SUCCESS, true);
  }

  if (ep_num != 0) {
    if (xfer->valid) {
      queue_out_packet(ep_num, xfer);
    } else {
      uint8_t rx_res = xfer->is_iso ? USBHS_EP_R_RES_NYET : USBHS_EP_R_RES_NAK;
      EP_RX_CTRL(ep_num) = (EP_RX_CTRL(ep_num) & ~(USBHS_EP_R_RES_MASK)) | rx_res;
    }
  }
}

bool dcd_init(uint8_t rhport, const tusb_rhport_init_t *rh_init) {
  (void)rhport;

  memset(&xfer_status, 0, sizeof(xfer_status));
  ep0_tog = true;
  reset_evt_pending = false;

  USBHSD->HOST_CTRL = 0x00;
  USBHSD->HOST_CTRL = USBHS_PHY_SUSPENDM;

  USBHSD->CONTROL = 0;

  if (rh_init->speed == TUSB_SPEED_HIGH || rh_init->speed == TUSB_SPEED_AUTO) {
    USBHSD->CONTROL = USBHS_DMA_EN | USBHS_INT_BUSY_EN | USBHS_HIGH_SPEED;
  } else if (rh_init->speed == TUSB_SPEED_FULL) {
    USBHSD->CONTROL = USBHS_DMA_EN | USBHS_INT_BUSY_EN | USBHS_FULL_SPEED;
  } else if (rh_init->speed == TUSB_SPEED_LOW) {
    USBHSD->CONTROL = USBHS_DMA_EN | USBHS_INT_BUSY_EN | USBHS_LOW_SPEED;
  } else {
    return false;
  }

  USBHSD->INT_EN = 0;
  USBHSD->INT_EN = USBHS_SETUP_ACT_EN | USBHS_TRANSFER_EN | USBHS_BUS_RST_EN | USBHS_SUSPEND_EN | USBHS_ISO_ACT_EN;

  USBHSD->ENDP_CONFIG = USBHS_EP0_T_EN | USBHS_EP0_R_EN;
  USBHSD->ENDP_TYPE   = 0x00;
  USBHSD->BUF_MODE    = 0x00;

  for (int ep = 0; ep < EP_MAX; ep++) {
    EP_TX_LEN(ep)  = 0;
    EP_TX_CTRL(ep) = USBHS_EP_T_RES_NAK | USBHS_EP_T_TOG_0;
    EP_RX_CTRL(ep) = USBHS_EP_R_RES_NAK | USBHS_EP_R_TOG_0;

    EP_RX_MAX_LEN(ep) = 0;
  }

  USBHSD->UEP0_DMA                      = (uint32_t)ep0_buffer;
  USBHSD->UEP0_MAX_LEN                  = CFG_TUD_ENDPOINT0_SIZE;
  xfer_status[0][TUSB_DIR_OUT].max_size = CFG_TUD_ENDPOINT0_SIZE;
  xfer_status[0][TUSB_DIR_IN].max_size  = CFG_TUD_ENDPOINT0_SIZE;

  USBHSD->DEV_AD = 0;
  dcd_connect(rhport);

  return true;
}

void dcd_int_enable(uint8_t rhport) {
  (void)rhport;
  NVIC_EnableIRQ(Software_IRQn);
  NVIC_EnableIRQ(USBHS_IRQn);
}

// Masks the processing only: the capture has to read every status in time.
void dcd_int_disable(uint8_t rhport) {
  (void)rhport;
  NVIC_DisableIRQ(Software_IRQn);
}

uint16_t dcd_ch32_event_frame(void) {
  return event_frame;
}

void dcd_edpt_close_all(uint8_t rhport) {
  (void)rhport;

  for (size_t ep = 1; ep < EP_MAX; ep++) {
    EP_TX_LEN(ep)  = 0;
    EP_TX_CTRL(ep) = USBHS_EP_T_RES_NAK | USBHS_EP_T_TOG_0;
    EP_RX_CTRL(ep) = USBHS_EP_R_RES_NAK | USBHS_EP_R_TOG_0;

    EP_RX_MAX_LEN(ep) = 0;
  }

  USBHSD->ENDP_CONFIG = USBHS_EP0_T_EN | USBHS_EP0_R_EN;
}

void dcd_set_address(uint8_t rhport, uint8_t dev_addr) {
  (void)dev_addr;

  // Response with zlp status
  dcd_edpt_xfer(rhport, 0x80, NULL, 0, false);
}

void dcd_remote_wakeup(uint8_t rhport) {
  (void)rhport;
}

void dcd_connect(uint8_t rhport) {
  (void)rhport;
  USBHSD->HOST_CTRL |= USBHS_PHY_SUSPENDM;
  USBHSD->CONTROL |= USBHS_DEV_PU_EN;
}

void dcd_disconnect(uint8_t rhport) {
  (void)rhport;
  USBHSD->CONTROL &= ~USBHS_DEV_PU_EN;
  USBHSD->HOST_CTRL &= ~USBHS_PHY_SUSPENDM;
}

void dcd_sof_enable(uint8_t rhport, bool en) {
  (void)rhport;
  if (en) {
    USBHSD->INT_EN |= USBHS_SOF_ACT_EN;
  } else {
    USBHSD->INT_EN &= ~(USBHS_SOF_ACT_EN);
  }
}

void dcd_edpt0_status_complete(uint8_t rhport, const tusb_control_request_t *request) {
  (void)rhport;
  if (request->bmRequestType_bit.recipient == TUSB_REQ_RCPT_DEVICE &&
      request->bmRequestType_bit.type == TUSB_REQ_TYPE_STANDARD && request->bRequest == TUSB_REQ_SET_ADDRESS) {
    USBHSD->DEV_AD = (uint8_t)request->wValue;
  }
}

bool dcd_edpt_open(uint8_t rhport, const tusb_desc_endpoint_t *desc_edpt) {
  (void)rhport;

  const uint8_t    ep_num = tu_edpt_number(desc_edpt->bEndpointAddress);
  const tusb_dir_t dir    = tu_edpt_dir(desc_edpt->bEndpointAddress);

  TU_ASSERT(ep_num < EP_MAX);

  if (ep_num == 0) {
    return true;
  }

  xfer_ctl_t *xfer = XFER_CTL_BASE(ep_num, dir);
  xfer->max_size   = tu_edpt_packet_size(desc_edpt);

  xfer->is_iso = (desc_edpt->bmAttributes.xfer == TUSB_XFER_ISOCHRONOUS);
  if (dir == TUSB_DIR_OUT) {
    USBHSD->ENDP_CONFIG |= (USBHS_EP0_R_EN << ep_num);
    EP_RX_CTRL(ep_num) = USBHS_EP_R_RES_NAK | USBHS_EP_R_TOG_0 |
                         (xfer->is_iso ? 0 : USBHS_EP_R_AUTOTOG);
    if (xfer->is_iso == true) {
      USBHSD->ENDP_TYPE |= (USBHS_EP0_R_TYP << ep_num);
    }
    EP_RX_MAX_LEN(ep_num) = xfer->max_size;
  } else {
    if (xfer->is_iso == true) {
      USBHSD->ENDP_TYPE |= (USBHS_EP0_T_TYP << ep_num);
    }
    USBHSD->ENDP_CONFIG |= (USBHS_EP0_T_EN << ep_num);
    EP_TX_LEN(ep_num)  = 0;
    EP_TX_CTRL(ep_num) = USBHS_EP_T_RES_NAK | USBHS_EP_T_TOG_0 |
                         (xfer->is_iso ? 0 : USBHS_EP_T_AUTOTOG);
  }

  return true;
}

void dcd_edpt_close(uint8_t rhport, uint8_t ep_addr) {
  (void)rhport;

  const uint8_t    ep_num = tu_edpt_number(ep_addr);
  const tusb_dir_t dir    = tu_edpt_dir(ep_addr);

  if (dir == TUSB_DIR_OUT) {
    EP_RX_CTRL(ep_num)    = USBHS_EP_R_RES_NAK | USBHS_EP_R_TOG_0;
    EP_RX_MAX_LEN(ep_num) = 0;
    USBHSD->ENDP_TYPE &= ~(USBHS_EP0_R_TYP << ep_num);
    USBHSD->ENDP_CONFIG &= ~(USBHS_EP0_R_EN << ep_num);
  } else { // TUSB_DIR_IN
    EP_TX_CTRL(ep_num) = USBHS_EP_T_RES_NAK | USBHS_EP_T_TOG_0;
    EP_TX_LEN(ep_num)  = 0;
    USBHSD->ENDP_TYPE &= ~(USBHS_EP0_T_TYP << ep_num);
    USBHSD->ENDP_CONFIG &= ~(USBHS_EP0_T_EN << ep_num);
  }
}

  #if 0
bool dcd_edpt_iso_alloc(uint8_t rhport, uint8_t ep_addr, uint16_t largest_packet_size) {
  (void) rhport;
  (void) ep_addr;
  (void) largest_packet_size;
  return false;
}

bool dcd_edpt_iso_activate(uint8_t rhport, tusb_desc_endpoint_t const * desc_ep) {
  (void) rhport;
  (void) desc_ep;
  return false;
}
  #endif

void dcd_edpt_stall(uint8_t rhport, uint8_t ep_addr) {
  (void)rhport;

  const uint8_t    ep_num = tu_edpt_number(ep_addr);
  const tusb_dir_t dir    = tu_edpt_dir(ep_addr);

  if (dir == TUSB_DIR_OUT) {
    EP_RX_CTRL(ep_num) = USBHS_EP_R_RES_STALL;
  } else {
    EP_TX_LEN(ep_num) = 0;
    EP_TX_CTRL(ep_num) = USBHS_EP_T_RES_STALL;
  }
}

void dcd_edpt_clear_stall(uint8_t rhport, uint8_t ep_addr) {
  (void)rhport;

  const uint8_t    ep_num = tu_edpt_number(ep_addr);
  const tusb_dir_t dir    = tu_edpt_dir(ep_addr);

  if (dir == TUSB_DIR_OUT) {
    xfer_ctl_t *xfer = XFER_CTL_BASE(ep_num, TUSB_DIR_OUT);
    EP_RX_CTRL(ep_num) = USBHS_EP_R_RES_NAK | USBHS_EP_R_TOG_0 |
                         ((ep_num != 0 && !xfer->is_iso) ? USBHS_EP_R_AUTOTOG : 0);
    if (xfer->valid) {
      // A receive is still armed (the class driver considers it submitted and won't re-arm it);
      // re-queue it (ACK/NYET) instead of leaving it NAKing, or the endpoint NAKs forever after
      // clear-halt (usbtest toggle test 29 clears the halt on an armed bulk-OUT pipe).
      queue_out_packet(ep_num, xfer);
    }
  } else {
    xfer_ctl_t *xfer = XFER_CTL_BASE(ep_num, TUSB_DIR_IN);
    EP_TX_CTRL(ep_num) = USBHS_EP_T_RES_NAK | USBHS_EP_T_TOG_0 |
                         ((ep_num != 0 && !xfer->is_iso) ? USBHS_EP_T_AUTOTOG : 0);
  }
}

bool dcd_edpt_xfer(uint8_t rhport, uint8_t ep_addr, uint8_t *buffer, uint16_t total_bytes, bool is_isr) {
  (void)is_isr;
  (void)rhport;
  const uint8_t    ep_num = tu_edpt_number(ep_addr);
  const tusb_dir_t dir    = tu_edpt_dir(ep_addr);

  xfer_ctl_t *xfer     = XFER_CTL_BASE(ep_num, dir);
  xfer->buffer         = buffer;
  xfer->total_len      = total_bytes;
  xfer->queued_len     = 0;
  xfer->valid         = true;

  if (ep_num == 0 && dir == TUSB_DIR_OUT) {
    if (total_bytes == 0) {
      EP_RX_CTRL(0) = (EP_RX_CTRL(0) & ~(USBHS_EP_R_TOG_MASK)) | USBHS_EP_R_TOG_1;
    } else {
      EP_RX_CTRL(0) ^= USBHS_EP_R_TOG_1;
    }
  }

  if (dir == TUSB_DIR_IN) {
    update_in(rhport, ep_num, true);
  } else {
    queue_out_packet(ep_num, xfer);
  }

  return true;
}

static inline __attribute__((always_inline)) capture_t *capture_slot(uint8_t flags) {
  uint32_t const wr = capture_wr;
  if (wr - capture_rd >= CAPTURE_DEPTH) {
    dcd_capture_overflows++;
    return NULL;
  }
  capture_t *c = &capture_q[wr & (CAPTURE_DEPTH - 1)];
  c->flags = flags;
  c->frame = USBHSD->FRAME_NO;
  c->t = (uint32_t) SysTick->CNT;
  return c;
}

// Highest priority: reads each event's status before the next transaction can
// overwrite it, then leaves the processing to the software interrupt. The WCH
// startup enables the hardware prologue/epilogue (HPE), which stacks the
// caller-saved registers, so the vector is a bare call + mret for a short entry
// (nesting stays within the HPE levels: board.c).
__attribute__((used)) void usbhs_capture(void);

__attribute__((naked, used)) void USBHS_IRQHandler(void) {
  __asm volatile("call usbhs_capture\n\t mret");
}

void usbhs_capture(void) {
  uint8_t const done = USBHS_BUS_RST_FLAG | USBHS_TRANSFER_FLAG | USBHS_SETUP_FLAG;
  bool queued = false;

  for (uint32_t n = 0; n < 8; n++) {
    uint8_t flags = USBHSD->INT_FG;
    if ((flags & USBHS_ISO_ACT_FLAG) && !(flags & done)) {
      // An iso packet has started: wait for its end (entry latency is paid
      // while its bytes are on the wire).
      USBHSD->INT_FG = USBHS_ISO_ACT_FLAG;
      if (!(USBHSD->MIS_ST & USBHS_SIE_FREE)) {
        uint32_t i = 0;
        while (!(USBHSD->INT_FG & done) && ++i < ISO_WAIT_LOOPS) {
        }
        if (i >= ISO_WAIT_LOOPS) {
          dcd_capture_iso_timeouts++;
        }
      }
      flags = USBHSD->INT_FG;
    }

    capture_t *c;
    if (flags & USBHS_BUS_RST_FLAG) {
      // Reset invalidates pending completions: drop the ones in the same snapshot.
      c = capture_slot(USBHS_BUS_RST_FLAG);
      USBHSD->INT_FG = flags & done;
    } else if (flags & USBHS_TRANSFER_FLAG) {
      uint8_t const status = USBHSD->INT_ST;
      uint16_t const len = USBHSD->RX_LEN;
      uint8_t const ep_num = status & MASK_UIS_ENDP;
      uint8_t const token = status & MASK_UIS_TOKEN;
      if (token == USBHS_TOKEN_PID_OUT && !(USBHSD->ENDP_TYPE & (USBHS_EP0_R_TYP << ep_num))) {
        EP_RX_CTRL(ep_num) = (EP_RX_CTRL(ep_num) & ~(USBHS_EP_R_RES_MASK)) | USBHS_EP_R_RES_NAK;
      } else if (token == USBHS_TOKEN_PID_IN && !(USBHSD->ENDP_TYPE & (USBHS_EP0_T_TYP << ep_num))) {
        EP_TX_CTRL(ep_num) = (EP_TX_CTRL(ep_num) & ~(USBHS_EP_T_RES_MASK)) | USBHS_EP_T_RES_NAK;
      }
      USBHSD->INT_FG = USBHS_TRANSFER_FLAG;
      c = capture_slot(USBHS_TRANSFER_FLAG);
      if (c) {
        c->status = status;
        c->len = len;
      }
    } else if (flags & USBHS_SETUP_FLAG) {
      // EP0 waits (NAK) for the SETUP to be processed; a new SETUP may overwrite
      // ep0_buffer, so it is copied first.
      EP_RX_CTRL(0) = USBHS_EP_R_RES_NAK;
      EP_TX_CTRL(0) = USBHS_EP_T_RES_NAK;
      c = capture_slot(USBHS_SETUP_FLAG);
      if (c) {
        c->setup[0] = ((uint32_t const *) ep0_buffer)[0];
        c->setup[1] = ((uint32_t const *) ep0_buffer)[1];
      }
      USBHSD->INT_FG = USBHS_SETUP_FLAG;
    } else if (flags & USBHS_SUSPEND_FLAG) {
      USBHSD->INT_FG = USBHS_SUSPEND_FLAG;
      c = capture_slot(USBHS_SUSPEND_FLAG);
    } else if (flags) {
      USBHSD->INT_FG = flags; // ISO_ACT of a packet already captured, FIFO_OV
      continue;
    } else {
      break;
    }

    if (c) {
      capture_wr++;
      queued = true;
    }
  }

  if (queued) {
    NVIC_SetPendingIRQ(Software_IRQn);
  }
}

static void process_capture(uint8_t rhport, capture_t const *c) {
  if (c->flags & USBHS_BUS_RST_FLAG) {
    // The first SOF follows speed negotiation and completes the reset notification.
    reset_evt_pending = true;
    USBHSD->INT_EN |= USBHS_SOF_ACT_EN;
    dcd_event_bus_signal(rhport, DCD_EVENT_BUS_RESET_START, true);

    USBHSD->DEV_AD = 0;
    ep0_tog = true;
    EP_RX_CTRL(0) = USBHS_EP_R_RES_ACK | USBHS_EP_R_TOG_0;
    EP_TX_CTRL(0) = USBHS_EP_T_RES_NAK | USBHS_EP_T_TOG_0;
  } else if (c->flags & USBHS_TRANSFER_FLAG) {
    const uint8_t int_status = c->status;
    const uint8_t token = int_status & MASK_UIS_TOKEN;
    const uint8_t ep_num = int_status & MASK_UIS_ENDP;
    const uint16_t len = c->len;

    if (int_status & USBHS_DEV_UIS_IS_NAK) {
      return; // no data moved
    }
    if (token == USBHS_TOKEN_PID_SOF) {
      if (reset_evt_pending) {
        reset_evt_pending = false;
        tusb_speed_t actual_speed;
        switch (USBHSD->SPEED_TYPE & USBHS_SPEED_TYPE_MASK) {
          case USBHS_SPEED_TYPE_FULL:
            actual_speed = TUSB_SPEED_FULL;
            break;
          case USBHS_SPEED_TYPE_LOW:
            actual_speed = TUSB_SPEED_LOW;
            break;
          default:
            actual_speed = TUSB_SPEED_HIGH;
            break;
        }
        dcd_event_bus_reset(rhport, actual_speed, true);
        USBHSD->INT_EN &= ~USBHS_SOF_ACT_EN;
      } else {
        uint32_t frame_count = c->frame & USBHS_FRAME_NO_NUM_MASK;
        dcd_event_sof(rhport, frame_count, true);
      }
    } else if (token == USBHS_TOKEN_PID_OUT) {
      xfer_ctl_t const *const out = XFER_CTL_BASE(ep_num, TUSB_DIR_OUT);
      if (out->is_iso || (int_status & USBHS_DEV_UIS_TOG_OK)) {
        update_out(rhport, ep_num, len);
        // A continuing EP0 transfer was closed at capture: take its next packet.
        if (ep_num == 0 && out->valid) {
          EP_RX_CTRL(0) = (EP_RX_CTRL(0) & ~(USBHS_EP_R_RES_MASK)) | USBHS_EP_R_RES_ACK;
        }
      } else if (out->valid) {
        // Data toggle mismatch (a host retransmit after a lost ACK): drop the
        // packet and keep the receive armed.
        EP_RX_CTRL(ep_num) = (EP_RX_CTRL(ep_num) & ~(USBHS_EP_R_RES_MASK)) | USBHS_EP_R_RES_ACK;
      }
    } else if (token == USBHS_TOKEN_PID_IN) {
      update_in(rhport, ep_num, false);
    }
  } else if (c->flags & USBHS_SETUP_FLAG) {
    tusb_control_request_t const* setup = (tusb_control_request_t const*) c->setup;
    ep0_tog = true;
    EP_RX_CTRL(0) = (setup->wLength == 0) ? USBHS_EP_R_RES_ACK : USBHS_EP_R_RES_NAK;
    EP_TX_CTRL(0) = USBHS_EP_T_RES_NAK;

    dcd_event_setup_received(0, (uint8_t const *) c->setup, true);
  } else if (c->flags & USBHS_SUSPEND_FLAG) {
    dcd_event_t event = {.rhport = rhport, .event_id = DCD_EVENT_SUSPEND};
    dcd_event_handler(&event, true);
  }
}

// Processes the captured events: called (tud_int_handler) from the
// application's Software_IRQn handler, which the capture pends.
void dcd_int_handler(uint8_t rhport) {
  while (capture_rd != capture_wr) {
    capture_t const *c = &capture_q[capture_rd & (CAPTURE_DEPTH - 1)];
    event_frame = c->frame;
    process_capture(rhport, c);
    uint32_t const period = (uint32_t) SysTick->CMP + 1u;
    uint32_t const d = ((uint32_t) SysTick->CNT + period - c->t) % period;
    if (d > dcd_delay_max) dcd_delay_max = d;
    if (d > period / 10u) dcd_delay_late++;   // 100 us
    capture_rd++;
  }
}
#endif
