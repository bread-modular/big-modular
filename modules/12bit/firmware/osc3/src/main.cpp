// ============================================================================
// 12bit osc3 firmware (STM32G071C8T6 U3): three-oscillator mixer.
//
//   PA1 ADC_IN1    P1 knob (RV1) -> oscillator 1 frequency
//   PA6 ADC_IN6    P2 knob (RV2) -> oscillator 2 frequency
//   PA7 ADC_IN7    P3 knob (RV3) -> oscillator 3 frequency
//   PA4 DAC1_OUT1  OUT 1: mix of the three
//   PA5 DAC1_OUT2  OUT 2: the same mix
//   PB4            MODE button (internal pull-up): next waveform
//   PB5            MODE LED (R7 -> D1): flashes the waveform number
//
// MIDI (PB7) and CV (PA0) are not used yet, so JP1 does not matter.
//
// Clock: HSI16 -> PLL 64 MHz, no crystal. TIM6 48 kHz sample tick, SysTick
// 1 ms.
// ============================================================================

#include "stm32g0xx.h"
#include "osc3_logic.h"

#define ADC_CH_P1 1   // PA1
#define ADC_CH_P2 6   // PA6
#define ADC_CH_P3 7   // PA7

static const uint32_t SYSCLK_HZ = 64000000;

static volatile uint32_t g_millis = 0;

// ---- shared with the sample interrupt -----------------------------------------
static volatile uint32_t phaseInc[3];
static volatile uint8_t waveSel = osc3::SINE;
static int16_t sineTable[osc3::SINE_SIZE];

extern "C" {

void SysTick_Handler(void) { g_millis++; }

void TIM6_DAC_LPTIM1_IRQHandler(void) {
    static uint32_t phase[3];
    TIM6->SR = 0;
    const osc3::Wave w = (osc3::Wave)waveSel;
    int32_t s[3];
    for (int i = 0; i < 3; i++) {
        phase[i] += phaseInc[i];
        s[i] = osc3::wave(w, phase[i], sineTable);
    }
    const uint32_t v = osc3::mixToDac(s[0], s[1], s[2]);
    DAC1->DHR12RD = v | (v << 16);   // both channels in one write
}

}  // extern "C"

// ---- hardware setup ------------------------------------------------------------

static void clockInit() {
    FLASH->ACR = (FLASH->ACR & ~FLASH_ACR_LATENCY) | FLASH_ACR_LATENCY_1 | FLASH_ACR_PRFTEN | FLASH_ACR_ICEN;
    while ((FLASH->ACR & FLASH_ACR_LATENCY) != FLASH_ACR_LATENCY_1) {}
    // HSI16 / M 1 x N 8 = 128 MHz VCO, / R 2 = 64 MHz
    RCC->PLLCFGR = RCC_PLLCFGR_PLLSRC_HSI | (8u << RCC_PLLCFGR_PLLN_Pos) | (1u << RCC_PLLCFGR_PLLR_Pos) |
                   RCC_PLLCFGR_PLLREN;
    RCC->CR |= RCC_CR_PLLON;
    while (!(RCC->CR & RCC_CR_PLLRDY)) {}
    RCC->CFGR = (RCC->CFGR & ~RCC_CFGR_SW) | RCC_CFGR_SW_1;
    while ((RCC->CFGR & RCC_CFGR_SWS) != RCC_CFGR_SWS_1) {}
    SystemCoreClock = SYSCLK_HZ;
    SysTick_Config(SYSCLK_HZ / 1000);
    NVIC_SetPriority(SysTick_IRQn, 3);
}

static void setMode(GPIO_TypeDef *port, uint32_t n, uint32_t mode) {
    port->MODER = (port->MODER & ~(3u << (2 * n))) | (mode << (2 * n));
}

static void gpioInit() {
    RCC->IOPENR |= RCC_IOPENR_GPIOAEN | RCC_IOPENR_GPIOBEN;
    setMode(GPIOA, 1, 3);   // P1, analog
    setMode(GPIOA, 6, 3);   // P2, analog
    setMode(GPIOA, 7, 3);   // P3, analog
    setMode(GPIOA, 4, 3);   // DAC1_OUT1
    setMode(GPIOA, 5, 3);   // DAC1_OUT2
    setMode(GPIOB, 4, 0);   // MODE, input with pull-up
    GPIOB->PUPDR = (GPIOB->PUPDR & ~(3u << 8)) | (1u << 8);
    GPIOB->BRR = 1u << 5;
    setMode(GPIOB, 5, 1);   // LED, output
}

static void dacInit() {
    RCC->APBENR1 |= RCC_APBENR1_DAC1EN;
    DAC1->MCR = 0;          // both channels: buffer on, to the pin
    DAC1->DHR12RD = (uint32_t)osc3::DAC_MID | ((uint32_t)osc3::DAC_MID << 16);
    DAC1->CR = DAC_CR_EN1 | DAC_CR_EN2;
}

static void delayUs(uint32_t us) {
    volatile uint32_t n = us * (SYSCLK_HZ / 4000000);   // >= 4 cycles per pass
    while (n--) {}
}

static void adcInit() {
    RCC->APBENR2 |= RCC_APBENR2_ADCEN;
    ADC1->CFGR2 = (2u << ADC_CFGR2_CKMODE_Pos)       // PCLK / 4 = 16 MHz
                | ADC_CFGR2_OVSE | (3u << ADC_CFGR2_OVSR_Pos) | (4u << ADC_CFGR2_OVSS_Pos);  // 16x, >> 4
    ADC1->CR = ADC_CR_ADVREGEN;
    delayUs(30);
    ADC1->CR |= ADC_CR_ADCAL;
    while (ADC1->CR & ADC_CR_ADCAL) {}
    ADC1->SMPR = 5u << ADC_SMPR_SMP1_Pos;            // 39.5 cycles (10n on each wiper)
    ADC1->CFGR1 = ADC_CFGR1_OVRMOD;                  // 12 bit, single, ascending scan
    ADC1->ISR = ADC_ISR_CCRDY;
    ADC1->CHSELR = (1u << ADC_CH_P1) | (1u << ADC_CH_P2) | (1u << ADC_CH_P3);
    for (uint32_t i = 0; i < 100000 && !(ADC1->ISR & ADC_ISR_CCRDY); i++) {}
    ADC1->ISR = ADC_ISR_ADRDY;
    ADC1->CR |= ADC_CR_ADEN;
    while (!(ADC1->ISR & ADC_ISR_ADRDY)) {}
}

static uint16_t adcNext() {
    while (!(ADC1->ISR & ADC_ISR_EOC)) {}
    return (uint16_t)ADC1->DR;                       // 12 bit
}

// One ascending scan: PA1 (P1), PA6 (P2), PA7 (P3).
static void readKnobs(uint16_t *knob) {
    ADC1->CR |= ADC_CR_ADSTART;
    for (int i = 0; i < 3; i++) knob[i] = adcNext();
    while (!(ADC1->ISR & ADC_ISR_EOS)) {}
    ADC1->ISR = ADC_ISR_EOS | ADC_ISR_EOC;
}

static void sampleTimerInit() {
    RCC->APBENR1 |= RCC_APBENR1_TIM6EN;
    TIM6->PSC = 0;
    TIM6->ARR = SYSCLK_HZ / osc3::SAMPLE_RATE_HZ - 1;
    TIM6->DIER = TIM_DIER_UIE;
    TIM6->CR1 = TIM_CR1_CEN;
    NVIC_SetPriority(TIM6_DAC_LPTIM1_IRQn, 0);
    NVIC_EnableIRQ(TIM6_DAC_LPTIM1_IRQn);
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

// Flashes the LED (waveform + 1) times after a change: 1 sine .. 4 square.
static uint32_t ledStart = 0;
static uint8_t ledFlashes = 0;

static void ledUpdate() {
    const uint32_t t = g_millis - ledStart;
    const bool on = t < ledFlashes * 300u && (t % 300u) < 150u;
    if (on) GPIOB->BSRR = 1u << 5;
    else GPIOB->BRR = 1u << 5;
}

int main() {
    clockInit();
    gpioInit();
    osc3::fillSine(sineTable);
    dacInit();
    adcInit();

    osc3::KnobFilter filter[3];
    uint16_t knob[3];
    readKnobs(knob);
    for (int i = 0; i < 3; i++) phaseInc[i] = osc3::phaseInc(osc3::knobHz(filter[i].update(knob[i])));
    sampleTimerInit();

    ledStart = g_millis;
    ledFlashes = waveSel + 1;

    uint32_t lastScan = g_millis;
    for (;;) {
        if (g_millis != lastScan) {   // 1 kHz knob scan, so the filter time is fixed (~16 ms)
            lastScan = g_millis;
            readKnobs(knob);
            for (int i = 0; i < 3; i++) {
                phaseInc[i] = osc3::phaseInc(osc3::knobHz(filter[i].update(knob[i])));
            }
        }
        if (modePressed()) {
            waveSel = (uint8_t)((waveSel + 1) % osc3::WAVE_COUNT);
            ledStart = g_millis;
            ledFlashes = waveSel + 1;
        }
        ledUpdate();
    }
}
