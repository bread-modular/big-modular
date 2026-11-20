// PCM3168A (carrier U3) over I2C2. The I2C address tells which carrier this is
// and whether the clock link is in use (S3 carrier: ADR0 high, ADR1 = LINK_N):
//   0x47  S3, CLK IN open: this unit is the clock master
//   0x45  S3, CLK IN connected: clock slave, SCKI / BCK / LRCK come from the link
//   0x44  S2 carrier (no clock link): clock master
// Master: ADC = TDM clock master from SCKI (Y1, 24.576 MHz); the DAC is a slave
// on the same BCK / LRCK (BCKDA, LRCKDA tied to BCKAD, LRCKAD on the carrier).
// Slave: the ADC must stay a slave (the link receiver U13 drives BCK / LRCK).
#ifndef CODEC_H_
#define CODEC_H_

#include <stdbool.h>
#include <stdint.h>

// PCM3168A registers (TI SBAS452A section 9.5)
#define PCM_RESET       0x40   // MRST SRST - - - - SRDA[1:0]
#define PCM_DAC_CTL1    0x41   // PSMDA MSDA[2:0] FMTDA[3:0]
#define PCM_DAC_CTL2    0x42   // OPEDA[3:0] FLT[3:0]
#define PCM_DAC_PHASE   0x43   // REVDA[8:1]
#define PCM_DAC_MUTE    0x44   // MUTDA[8:1]
#define PCM_DAC_ZERO    0x45   // ZERO[8:1], read only
#define PCM_DAC_CTL3    0x46   // ATMDDA ATSPDA DEMP[1:0] AZRO[2:0] ZREV
#define PCM_DAC_ATT0    0x47   // ATDA0 (master) .. 0x4F ATDA8, 0xFF = 0 dB
#define PCM_ADC_SRATE   0x50   // SRAD[1:0]
#define PCM_ADC_CTL1    0x51   // - MSAD[2:0] - FMTAD[2:0]
#define PCM_ADC_CTL2    0x52   // - PSVAD[2:0] - BYP[2:0]
#define PCM_ADC_INPUT   0x53   // SEAD[6:1]
#define PCM_ADC_PHASE   0x54   // REVAD[6:1]
#define PCM_ADC_MUTE    0x55   // MUTAD[6:1]
#define PCM_ADC_OVF     0x56   // OVF[6:1], read clears
#define PCM_ADC_CTL3    0x57   // ATMDAD ATSPAD - - - - - OVFP
#define PCM_ADC_ATT0    0x58   // ATAD0 (master) .. 0x5E ATAD6, 0xD7 = 0 dB
#define PCM_REG_FIRST   0x40
#define PCM_REG_LAST    0x5E

typedef enum {
  CODEC_OFF = 0,       // not started / held in reset
  CODEC_NO_ACK,        // no I2C answer at 0x47 / 0x45 / 0x44 (codec missing, unpowered, not soldered,
                       // or a clock slave whose master sends no SCKI)
  CODEC_BAD_REGS,      // answered, but the reset defaults / written values do not read back
  CODEC_READY,         // configured, ADC still slave: BCK / LRCK not started yet
  CODEC_RUNNING,       // ADC master: BCK / LRCK running
} codec_state_t;

// Reset and configure for `rate` (48000; 96000 later with SPI1), leaving the ADC
// a slave so BCK / LRCK stay low (50k pull-downs in the codec): CODEC_READY.
// Every start goes through the reset, so the TDM slaves see the first BCK edge.
codec_state_t codec_prepare(uint32_t rate);
// ADC to master mode: BCK / LRCK start. CODEC_READY -> CODEC_RUNNING.
bool codec_run(void);
void codec_stop(void);

codec_state_t codec_state(void);
// 7-bit I2C address the codec answered at in the last codec_prepare(), 0 if none.
uint8_t codec_address(void);
// CLK IN connected (address 0x45): never call codec_run().
bool codec_linked(void);
// One register read at the current address: false when the codec no longer
// answers there (reset, or the clock link was plugged / unplugged: ADR1 moved).
bool codec_alive(void);
bool codec_read(uint8_t reg, uint8_t *val);
bool codec_write(uint8_t reg, uint8_t val);
const char *codec_state_name(codec_state_t s);
// Register that failed the CODEC_BAD_REGS check, and what it read.
void codec_bad_reg(uint8_t *reg, uint8_t *got, uint8_t *want);

#endif
