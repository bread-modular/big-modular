// ============================================================================
// 12bit humtest firmware (STM32G071C8T6 U3): bench test for noise at the
// outputs. No sound: both DACs hold mid-scale (0 V at the jacks) and the MODE
// button steps through what the MCU is doing, so the step where a hum changes
// names its source. The LED flashes the step number, then stays off.
//
//   step  clock    knob scan        48 kHz sample interrupt  MIDI receiver
//   1     64 MHz   1 kHz bursts     on                       on    (the first clapsnare, idle)
//   2     16 MHz   1 kHz bursts     on                       on    (HSI16, PLL off)
//   3     64 MHz   off              on                       on
//   4     64 MHz   off              off                      on
//   5     1 MHz    off (ADC off)    off                      off   (HSI16 / 16, PLL off)
//   6     64 MHz   48 kHz, TIM6     on                       on    (clapsnare now, idle)
//   7     64 MHz   1 kHz bursts     on                       on    (step 1 with the DAC output buffers off)
//
// First board, 2026-11-18: hum loudest in 1, about half in 2, none in 3..5, so
// it is the 1 kHz burst scan (208 us of software-started conversions, then
// idle). Step 6 is the fix: TIM6 starts one four-channel scan per sample and
// DMA stores it, read every millisecond as in clapsnare.
//
// Step 7 (2026-11-19; user: hum still there, a bit duller) asks which way the hum of step 1 gets
// into the outputs, before the S3 board is ordered: with the buffers off the
// DAC pins are the resistor strings on VREF+ alone. Hum still there (duller:
// 11.7k + 1k into 4.7n is a 2.7 kHz low-pass) = it rides on the reference,
// which S3 takes off the MCU supply. Hum gone = it comes through the buffers'
// supply (VDD/VDDA), which S3 does not change.
//
//   PA4 / PA5      DAC1_OUT1 / OUT2, mid-scale, never changed
//   PA0 PA1 PA6 PA7  CV + P1..P3, the clapsnare ADC scan (values not used)
//   PB7 USART1_RX  MIDI, set up as the clapsnare `p` build, bytes dropped
//   PB4            MODE button (internal pull-up): next step
//   PB5            MODE LED (R7 -> D1)
//
// SysTick 1 ms runs in every step (button + LED). g_step holds the step and
// g_scanCount / g_sampleCount count the 1 kHz scans or reads and the sample
// interrupts, for a read over SWD; writing 1..7 to g_stepRequest selects a
// step.
// ============================================================================

#include "stm32g0xx.h"

#define ADC_CH_CV 0   // PA0
#define ADC_CH_P1 1   // PA1
#define ADC_CH_P2 6   // PA6
#define ADC_CH_P3 7   // PA7

#define ADC_CHANNELS 4
#define ADC_SCANS 16   // averaged per reading (step 6)

static const uint32_t SAMPLE_RATE_HZ = 48000;
static const uint32_t DAC_MID = 2048;
static const uint32_t FLASH_MS = 150;     // LED on / off time of one flash

enum Scan : uint8_t {
    SCAN_OFF,
    SCAN_BURST,   // every millisecond: one software-started scan, 16x oversampled
    SCAN_TIMED,   // every sample: one scan started by TIM6, DMA ring
};

struct Step {
    uint32_t hz;      // 64 MHz (PLL), 16 MHz (HSI16) or 1 MHz (HSI16 / 16)
    Scan scan;        // knob + CV scan
    bool sampleIrq;   // 48 kHz TIM6 interrupt writing the DACs
    bool midi;        // USART1 receiver
    bool dacBuffer;   // DAC output buffers (off: the pins are the 11.7k resistor strings)
};

static const Step STEPS[] = {
    {64000000, SCAN_BURST, true, true, true},
    {16000000, SCAN_BURST, true, true, true},
    {64000000, SCAN_OFF, true, true, true},
    {64000000, SCAN_OFF, false, true, true},
    {1000000, SCAN_OFF, false, false, true},
    {64000000, SCAN_TIMED, true, true, true},
    {64000000, SCAN_BURST, true, true, false},
};
static const uint8_t STEP_COUNT = sizeof(STEPS) / sizeof(STEPS[0]);

static volatile uint32_t g_millis = 0;

volatile uint8_t g_step = 1;          // 1 .. STEP_COUNT
volatile uint8_t g_stepRequest = 0;   // write 1 .. STEP_COUNT over SWD
volatile uint32_t g_scanCount = 0;
volatile uint32_t g_sampleCount = 0;

// Step 6 scans in a ring, written by DMA: CV, P1, P2, P3; g_adc is their mean.
static volatile uint16_t adcBuf[ADC_SCANS * ADC_CHANNELS];
volatile uint16_t g_adc[ADC_CHANNELS];

extern "C" {

void SysTick_Handler(void) { g_millis++; }

void TIM6_DAC_LPTIM1_IRQHandler(void) {
    TIM6->SR = 0;
    DAC1->DHR12RD = DAC_MID | (DAC_MID << 16);   // both channels in one write
    g_sampleCount++;
}

void USART1_IRQHandler(void) {
    uint32_t isr = USART1->ISR;
    if (isr & (USART_ISR_ORE | USART_ISR_FE | USART_ISR_NE)) {
        USART1->ICR = USART_ICR_ORECF | USART_ICR_FECF | USART_ICR_NECF;
    }
    if (isr & USART_ISR_RXNE_RXFNE) (void)USART1->RDR;
}

}  // extern "C"

// ---- hardware setup ------------------------------------------------------------

// Every change goes through HSI16: SYSCLK = PLL 64 MHz, HSI16 or HSI16 / 16.
// The flash stays at 2 wait states, valid at each of them.
static void setClock(uint32_t hz) {
    FLASH->ACR = (FLASH->ACR & ~FLASH_ACR_LATENCY) | FLASH_ACR_LATENCY_1 | FLASH_ACR_PRFTEN | FLASH_ACR_ICEN;
    while ((FLASH->ACR & FLASH_ACR_LATENCY) != FLASH_ACR_LATENCY_1) {}
    RCC->CR &= ~RCC_CR_HSIDIV;
    RCC->CFGR &= ~RCC_CFGR_SW;
    while (RCC->CFGR & RCC_CFGR_SWS) {}
    RCC->CR &= ~RCC_CR_PLLON;
    while (RCC->CR & RCC_CR_PLLRDY) {}
    if (hz == 64000000) {
        // HSI16 / M 1 x N 8 = 128 MHz VCO, / R 2 = 64 MHz
        RCC->PLLCFGR = RCC_PLLCFGR_PLLSRC_HSI | (8u << RCC_PLLCFGR_PLLN_Pos) | (1u << RCC_PLLCFGR_PLLR_Pos) |
                       RCC_PLLCFGR_PLLREN;
        RCC->CR |= RCC_CR_PLLON;
        while (!(RCC->CR & RCC_CR_PLLRDY)) {}
        RCC->CFGR = (RCC->CFGR & ~RCC_CFGR_SW) | RCC_CFGR_SW_1;
        while ((RCC->CFGR & RCC_CFGR_SWS) != RCC_CFGR_SWS_1) {}
    } else if (hz == 1000000) {
        RCC->CR |= RCC_CR_HSIDIV_2;   // / 16
    }
    SystemCoreClock = hz;
    SysTick_Config(hz / 1000);
    NVIC_SetPriority(SysTick_IRQn, 3);
}

static void setMode(GPIO_TypeDef *port, uint32_t n, uint32_t mode) {
    port->MODER = (port->MODER & ~(3u << (2 * n))) | (mode << (2 * n));
}

static void setAf(GPIO_TypeDef *port, uint32_t n, uint32_t af) {
    port->AFR[n >> 3] = (port->AFR[n >> 3] & ~(15u << (4 * (n & 7)))) | (af << (4 * (n & 7)));
    setMode(port, n, 2);
}

static void gpioInit() {
    RCC->IOPENR |= RCC_IOPENR_GPIOAEN | RCC_IOPENR_GPIOBEN;
    setMode(GPIOA, 0, 3);   // CV, analog
    setMode(GPIOA, 1, 3);   // P1, analog
    setMode(GPIOA, 6, 3);   // P2, analog
    setMode(GPIOA, 7, 3);   // P3, analog
    setMode(GPIOA, 4, 3);   // DAC1_OUT1
    setMode(GPIOA, 5, 3);   // DAC1_OUT2
    setMode(GPIOB, 4, 0);   // MODE, input with pull-up
    GPIOB->PUPDR = (GPIOB->PUPDR & ~(3u << 8)) | (1u << 8);
    GPIOB->BRR = 1u << 5;
    setMode(GPIOB, 5, 1);   // LED, output
    setAf(GPIOB, 7, 0);     // USART1_RX
}

// Both channels to their pins, mid-scale, with or without the output buffer
// (MCR can only be written with the channels off).
static void dacSet(bool buffer) {
    static const uint32_t unbuffered = (2u << DAC_MCR_MODE1_Pos) | (2u << DAC_MCR_MODE2_Pos);
    if (DAC1->CR && DAC1->MCR == (buffer ? 0 : unbuffered)) return;
    DAC1->CR = 0;
    DAC1->MCR = buffer ? 0 : unbuffered;
    DAC1->DHR12RD = DAC_MID | (DAC_MID << 16);
    DAC1->CR = DAC_CR_EN1 | DAC_CR_EN2;
}

static void dacInit() {
    RCC->APBENR1 |= RCC_APBENR1_DAC1EN;
    dacSet(true);
}

static void delayLoop(uint32_t passes) {
    volatile uint32_t n = passes;
    while (n--) {}
}

static void adcOff() {
    RCC->APBENR2 |= RCC_APBENR2_ADCEN;
    RCC->AHBENR |= RCC_AHBENR_DMA1EN;
    if (ADC1->CR & ADC_CR_ADSTART) {
        ADC1->CR |= ADC_CR_ADSTP;
        while (ADC1->CR & ADC_CR_ADSTP) {}
    }
    if (ADC1->CR & ADC_CR_ADEN) {
        ADC1->CR |= ADC_CR_ADDIS;
        while (ADC1->CR & ADC_CR_ADEN) {}
    }
    ADC1->CFGR1 = 0;   // DMAEN off: a calibration with it set leaves a DMA request pending
    DMA1_Channel1->CCR = 0;
}

// SCAN_BURST: the first clapsnare ADC set-up, with a 16 MHz ADC clock at 64
// and at 16 MHz, so one scan takes the same 208 us at both. SCAN_TIMED: the
// clapsnare set-up, armed for one scan per TIM6 update.
static void adcOn(uint32_t hz, Scan scan) {
    adcOff();
    ADC1->CFGR2 = (hz == 64000000 ? 2u : 3u) << ADC_CFGR2_CKMODE_Pos;   // PCLK / 4 or PCLK / 1
    if (scan != SCAN_TIMED) {
        ADC1->CFGR2 |= ADC_CFGR2_OVSE | (3u << ADC_CFGR2_OVSR_Pos) | (4u << ADC_CFGR2_OVSS_Pos);  // 16x, >> 4
    }
    ADC1->CR = ADC_CR_ADVREGEN;
    delayLoop(480);                                  // >= 30 us at 64 MHz
    ADC1->CR |= ADC_CR_ADCAL;
    while (ADC1->CR & ADC_CR_ADCAL) {}
    ADC1->SMPR = 5u << ADC_SMPR_SMP1_Pos;            // 39.5 cycles (10n on each wiper)
    ADC1->CFGR1 = ADC_CFGR1_OVRMOD;                  // 12 bit, single, ascending scan
    if (scan == SCAN_TIMED) {
        // one scan per TIM6_TRGO (TRG5) rising edge, DMA ring
        ADC1->CFGR1 |= ADC_CFGR1_EXTEN_0 | (5u << ADC_CFGR1_EXTSEL_Pos) | ADC_CFGR1_DMAEN | ADC_CFGR1_DMACFG;
    }
    ADC1->ISR = ADC_ISR_CCRDY;
    ADC1->CHSELR = (1u << ADC_CH_CV) | (1u << ADC_CH_P1) | (1u << ADC_CH_P2) | (1u << ADC_CH_P3);
    for (uint32_t i = 0; i < 100000 && !(ADC1->ISR & ADC_ISR_CCRDY); i++) {}
    ADC1->ISR = ADC_ISR_ADRDY;
    ADC1->CR |= ADC_CR_ADEN;
    while (!(ADC1->ISR & ADC_ISR_ADRDY)) {}
    if (scan == SCAN_TIMED) {
        DMAMUX1_Channel0->CCR = 5;                   // DMA1 channel 1 <- ADC
        DMA1_Channel1->CPAR = (uint32_t)&ADC1->DR;
        DMA1_Channel1->CMAR = (uint32_t)adcBuf;
        DMA1_Channel1->CNDTR = ADC_SCANS * ADC_CHANNELS;
        DMA1_Channel1->CCR = DMA_CCR_MINC | DMA_CCR_CIRC | DMA_CCR_MSIZE_0 | DMA_CCR_PSIZE_0 | DMA_CCR_EN;
        ADC1->ISR = ADC_ISR_OVR;
        ADC1->CR |= ADC_CR_ADSTART;
    }
}

// One ascending scan: PA0 (CV), PA1 (P1), PA6 (P2), PA7 (P3); values dropped.
static void scanKnobs() {
    ADC1->CR |= ADC_CR_ADSTART;
    for (int i = 0; i < 4; i++) {
        while (!(ADC1->ISR & ADC_ISR_EOC)) {}
        (void)ADC1->DR;
    }
    while (!(ADC1->ISR & ADC_ISR_EOS)) {}
    ADC1->ISR = ADC_ISR_EOS | ADC_ISR_EOC;
    g_scanCount++;
}

// The clapsnare 1 kHz read: the mean of the last ADC_SCANS timed scans.
static void readKnobs() {
    uint32_t sum[ADC_CHANNELS] = {0, 0, 0, 0};
    for (int i = 0; i < ADC_SCANS * ADC_CHANNELS; i++) sum[i % ADC_CHANNELS] += adcBuf[i];
    for (int i = 0; i < ADC_CHANNELS; i++) g_adc[i] = (uint16_t)(sum[i] / ADC_SCANS);
    g_scanCount++;
}

static void sampleTimerOff() {
    RCC->APBENR1 |= RCC_APBENR1_TIM6EN;
    NVIC_DisableIRQ(TIM6_DAC_LPTIM1_IRQn);
    TIM6->CR1 = 0;
    TIM6->DIER = 0;
    TIM6->SR = 0;
    NVIC_ClearPendingIRQ(TIM6_DAC_LPTIM1_IRQn);
}

static void sampleTimerOn(uint32_t hz) {
    TIM6->PSC = 0;
    TIM6->ARR = hz / SAMPLE_RATE_HZ - 1;
    TIM6->CNT = 0;
    TIM6->CR2 = TIM_CR2_MMS_1;       // TRGO on update: starts the SCAN_TIMED scan
    TIM6->DIER = TIM_DIER_UIE;
    TIM6->CR1 = TIM_CR1_CEN;
    NVIC_SetPriority(TIM6_DAC_LPTIM1_IRQn, 0);
    NVIC_EnableIRQ(TIM6_DAC_LPTIM1_IRQn);
}

static void midiOff() {
    RCC->APBENR2 |= RCC_APBENR2_USART1EN;
    NVIC_DisableIRQ(USART1_IRQn);
    USART1->CR1 = 0;
    NVIC_ClearPendingIRQ(USART1_IRQn);
}

static void midiOn(uint32_t hz) {
    USART1->BRR = hz / 31250;
    USART1->CR2 = USART_CR2_RXINV;   // JP1 = P, as the clapsnare `p` build
    USART1->CR1 = USART_CR1_RE | USART_CR1_RXNEIE_RXFNEIE | USART_CR1_UE;
    NVIC_SetPriority(USART1_IRQn, 1);
    NVIC_EnableIRQ(USART1_IRQn);
}

static void applyStep(uint8_t n) {
    const Step &s = STEPS[n - 1];
    sampleTimerOff();
    midiOff();
    adcOff();
    setClock(s.hz);
    dacSet(s.dacBuffer);
    if (s.hz != 1000000) adcOn(s.hz, s.scan);   // enabled and idle when the scan is off
    if (s.midi) midiOn(s.hz);
    if (s.sampleIrq) sampleTimerOn(s.hz);
    g_step = n;
}

// ---- MODE button + LED ------------------------------------------------------------

static bool modePressed() {
    static bool stable = false;
    static bool last = false;
    static uint32_t since = 0;
    const bool now = !(GPIOB->IDR & (1u << 4));
    if (now != last) {
        last = now;
        since = g_millis;
    }
    if (now != stable && g_millis - since >= 20) {
        stable = now;
        return stable;   // press edge only
    }
    return false;
}

// Flashes the step number once after a change, then stays off.
static uint32_t ledStart = 0;

static void ledUpdate() {
    const uint32_t t = g_millis - ledStart;
    const bool on = t < g_step * 2 * FLASH_MS && (t % (2 * FLASH_MS)) < FLASH_MS;
    if (on) GPIOB->BSRR = 1u << 5;
    else GPIOB->BRR = 1u << 5;
}

int main() {
    gpioInit();
    dacInit();
    applyStep(1);
    ledStart = g_millis;

    uint32_t lastScan = g_millis;
    for (;;) {
        if (g_millis != lastScan) {   // 1 kHz, as the clapsnare knob read
            lastScan = g_millis;
            const Scan scan = STEPS[g_step - 1].scan;
            if (scan == SCAN_BURST) scanKnobs();
            else if (scan == SCAN_TIMED) readKnobs();
        }
        uint8_t next = 0;
        if (modePressed()) next = (uint8_t)(g_step % STEP_COUNT + 1);
        const uint8_t request = g_stepRequest;
        if (request) {
            g_stepRequest = 0;
            if (request <= STEP_COUNT) next = request;
        }
        if (next) {
            applyStep(next);
            lastScan = ledStart = g_millis;
        }
        ledUpdate();
    }
}
