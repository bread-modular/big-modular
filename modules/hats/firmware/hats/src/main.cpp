// ============================================================================
// HATS S4 firmware (STM32G071C8T6 U2): Bread Modular NOISE + HIHAT on one
// MCU, plus the PWM CUTOFF vactrol and the shared 4-bar REC recorder.
//
//   PA4 DAC1_OUT1  white noise (BM NOISE, -> R6 / U4A, blue high-pass)
//   PA5 DAC1_OUT2  velocity (BM HIHAT)
//   PA2 / PA3      gate / open hat (BM HIHAT: notes > 60 open)
//   PA1 ADC_IN1    NOISE TONE knob (RV1)
//   PA6 ADC_IN6    CUTOFF knob (RV3)
//   PB0 TIM3_CH3   CUTOFF vactrol LED PWM (R51 -> U11), 31.25 kHz, dithered
//   PB4 / PB5      REC button (pull-up) / REC LED (R48 -> D6)
//   PB7 USART1_RX  MIDI 31250 baud, all channels; RXINV for JP1 = P
//
//   REC (shared CvRecorder): lane 1 CUTOFF, lane 2 NOISE TONE, 4 bars on
//   MIDI clock. MIDI CC 74 x 8 adds to NOISE TONE (BM).
//
// Clock: HSI16 -> PLL 64 MHz, no crystal. Timers: TIM6 100 kHz noise tick
// (one BM delay unit), TIM3 PWM + dither, SysTick 1 ms.
// ============================================================================

#include "stm32g0xx.h"
#include "Arduino.h"
#include "CvRecorder.h"
#include "hats_logic.h"

// JP1 on the HATS carrier picks the MIDI input path (set by ../jumper.sh):
//   P (protected) = NPN front end (Q1), which inverts the UART data -> 1
//   D (direct)    = jack tip straight to PB7, as Bread Modular     -> 0
#ifndef MIDI_RX_INVERT
#error "MIDI_RX_INVERT must be set: build with ../compile.sh p|d"
#endif

#define GATE_PIN       PIN_PA(2)
#define OPEN_HAT_PIN   PIN_PA(3)
#define REC_BUTTON_PIN PIN_PB(4)
#define REC_LED_PIN    PIN_PB(5)

#define ADC_CH_TONE    1   // PA1
#define ADC_CH_CUTOFF  6   // PA6

static const uint32_t SYSCLK_HZ = 64000000;

volatile uint32_t g_millis = 0;

// ---- shared with the interrupts ---------------------------------------------
static volatile uint32_t noiseHold = hats::noiseHoldTicks(0);  // ticks per sample
static volatile uint8_t swingMix = 0;
static volatile uint32_t cutoffDuty = 0;                       // PWM_FULL units

static volatile uint8_t rxBuf[64];
static volatile uint8_t rxHead = 0;
static uint8_t rxTail = 0;

// ---- state -------------------------------------------------------------------
static hats::WhiteNoise noise;
static hats::PwmDither dither;
static hats::MidiParser midi;
static hats::HihatOut hihat;
static CvRecorder recorder(REC_BUTTON_PIN, REC_LED_PIN);

static uint8_t cc74 = 0;
static uint16_t liveCutoff = 0;   // knobs, 0..1023 (recorder input)
static uint16_t liveTone = 0;
static uint16_t playCutoff = 0;   // recorded take (PLAYBACK)
static uint16_t playTone = 0;

// Knob value -> cutoff PWM duty, filled at boot from the LDR model.
static uint16_t cutoffTable[1024];

extern "C" {

void SysTick_Handler(void) { g_millis++; }

// One BM delay unit: count up to the TONE hold, then output a noise sample.
// A shorter hold (TONE turned down) applies at once instead of after the
// pending one, which can last over a second at full TONE.
void TIM6_DAC_LPTIM1_IRQHandler(void) {
    static uint32_t elapsed = 0;
    TIM6->SR = 0;
    if (++elapsed >= noiseHold) {
        elapsed = 0;
        DAC1->DHR12R1 = hats::dac12(hats::boostSwing(noise.next(), swingMix));
    }
}

// Every PWM period: next dithered compare value for the cutoff vactrol.
void TIM3_IRQHandler(void) {
    TIM3->SR = 0;
    TIM3->CCR3 = dither.next(cutoffDuty);
}

void USART1_IRQHandler(void) {
    uint32_t isr = USART1->ISR;
    if (isr & (USART_ISR_ORE | USART_ISR_FE | USART_ISR_NE)) {
        USART1->ICR = USART_ICR_ORECF | USART_ICR_FECF | USART_ICR_NECF;
    }
    if (isr & USART_ISR_RXNE_RXFNE) {
        uint8_t b = (uint8_t)USART1->RDR;
        uint8_t next = (uint8_t)((rxHead + 1) & 63);
        if (next != rxTail) {
            rxBuf[rxHead] = b;
            rxHead = next;
        }
    }
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

static void setAf(GPIO_TypeDef *port, uint32_t n, uint32_t af) {
    port->AFR[n >> 3] = (port->AFR[n >> 3] & ~(15u << (4 * (n & 7)))) | (af << (4 * (n & 7)));
    setMode(port, n, 2);
}

static void gpioInit() {
    RCC->IOPENR |= RCC_IOPENR_GPIOAEN | RCC_IOPENR_GPIOBEN;
    pinMode(GATE_PIN, OUTPUT);
    pinMode(OPEN_HAT_PIN, OUTPUT);
    digitalWrite(GATE_PIN, LOW);
    digitalWrite(OPEN_HAT_PIN, LOW);
    setMode(GPIOA, 1, 3);   // NOISE TONE, analog
    setMode(GPIOA, 6, 3);   // CUTOFF, analog
    setMode(GPIOA, 4, 3);   // DAC1_OUT1
    setMode(GPIOA, 5, 3);   // DAC1_OUT2
    setAf(GPIOB, 0, 1);     // TIM3_CH3
    setAf(GPIOB, 7, 0);     // USART1_RX
}

static void dacInit() {
    RCC->APBENR1 |= RCC_APBENR1_DAC1EN;
    DAC1->MCR = 0;          // both channels: buffer on, to the pin
    DAC1->DHR12R1 = hats::dac12(128);
    DAC1->DHR12R2 = hats::dac12(hihat.velocity);
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
    ADC1->CHSELR = (1u << ADC_CH_TONE) | (1u << ADC_CH_CUTOFF);
    for (uint32_t i = 0; i < 100000 && !(ADC1->ISR & ADC_ISR_CCRDY); i++) {}
    ADC1->ISR = ADC_ISR_ADRDY;
    ADC1->CR |= ADC_CR_ADEN;
    while (!(ADC1->ISR & ADC_ISR_ADRDY)) {}
}

static uint16_t adcNext() {
    while (!(ADC1->ISR & ADC_ISR_EOC)) {}
    return (uint16_t)(ADC1->DR >> 2);                // 12 -> 10 bit, as BM analogRead
}

// One scan: PA1 (TONE) then PA6 (CUTOFF).
static void readKnobs() {
    ADC1->CR |= ADC_CR_ADSTART;
    liveTone = adcNext();
    liveCutoff = adcNext();
    while (!(ADC1->ISR & ADC_ISR_EOS)) {}
    ADC1->ISR = ADC_ISR_EOS | ADC_ISR_EOC;
}

static void noiseTimerInit() {
    RCC->APBENR1 |= RCC_APBENR1_TIM6EN;
    TIM6->PSC = 0;
    TIM6->ARR = SYSCLK_HZ / hats::NOISE_TICK_HZ - 1;
    TIM6->DIER = TIM_DIER_UIE;
    TIM6->CR1 = TIM_CR1_CEN;
    NVIC_SetPriority(TIM6_DAC_LPTIM1_IRQn, 0);
    NVIC_EnableIRQ(TIM6_DAC_LPTIM1_IRQn);
}

static void cutoffPwmInit() {
    for (uint16_t k = 0; k < 1024; k++) {
        uint32_t d = hats::cutoffDuty(k);
        cutoffTable[k] = d >= hats::PWM_FULL ? 0xFFFF : (uint16_t)d;
    }
    RCC->APBENR1 |= RCC_APBENR1_TIM3EN;
    TIM3->PSC = 0;
    TIM3->ARR = hats::PWM_PERIOD - 1;
    TIM3->CCR3 = 0;
    TIM3->CCMR2 = (6u << TIM_CCMR2_OC3M_Pos) | TIM_CCMR2_OC3PE;   // PWM mode 1, preload
    TIM3->CCER = TIM_CCER_CC3E;
    TIM3->DIER = TIM_DIER_UIE;
    TIM3->EGR = TIM_EGR_UG;
    TIM3->SR = 0;
    TIM3->CR1 = TIM_CR1_ARPE | TIM_CR1_CEN;
    NVIC_SetPriority(TIM3_IRQn, 2);
    NVIC_EnableIRQ(TIM3_IRQn);
}

static void midiInit() {
    RCC->APBENR2 |= RCC_APBENR2_USART1EN;
    USART1->BRR = SYSCLK_HZ / 31250;
#if MIDI_RX_INVERT
    // JP1 = P: the NPN input stage inverts the MIDI UART data.
    USART1->CR2 = USART_CR2_RXINV;
#endif
    USART1->CR1 = USART_CR1_RE | USART_CR1_RXNEIE_RXFNEIE | USART_CR1_UE;
    NVIC_SetPriority(USART1_IRQn, 1);
    NVIC_EnableIRQ(USART1_IRQn);
}

// ---- recorder glue (as modules/acid) -------------------------------------------

static void applyRecorded(uint16_t cut, uint16_t tone) {
    playCutoff = cut;
    playTone = tone;
}

static void handleClock() {
    if (recorder.isRecording()) {
        applyRecorded(liveCutoff, liveTone);   // the take starts where it was played
    }
    recorder.onClock(liveCutoff, liveTone, applyRecorded);
}

static void handleMidi() {
    while (rxTail != rxHead) {
        uint8_t b = rxBuf[rxTail];
        rxTail = (uint8_t)((rxTail + 1) & 63);
        hats::MidiParser::Event ev = midi.feed(b);
        switch (ev.kind) {
            case hats::MidiParser::NOTE_ON:
                hihat.noteOn(ev.data1, ev.data2);
                break;
            case hats::MidiParser::NOTE_OFF:
                hihat.noteOff(ev.data2);
                break;
            case hats::MidiParser::CONTROL_CHANGE:
                if (ev.data1 == 74) cc74 = ev.data2;   // BM NOISE: CC 74 = tone
                continue;
            case hats::MidiParser::CLOCK:
                handleClock();
                continue;
            case hats::MidiParser::START:
                recorder.onStart();
                continue;
            default:
                continue;
        }
        digitalWrite(GATE_PIN, hihat.gate ? HIGH : LOW);
        digitalWrite(OPEN_HAT_PIN, hihat.open ? HIGH : LOW);
        DAC1->DHR12R2 = hats::dac12(hihat.velocity);
    }
}

int main() {
    clockInit();
    gpioInit();
    dacInit();
    adcInit();
    cutoffPwmInit();
    recorder.begin();
    readKnobs();
    noiseTimerInit();
    midiInit();

    for (;;) {
        handleMidi();
        readKnobs();
        recorder.update();

        // PLAYBACK: the recorded take (shifted by the knobs after its first
        // pass, inside CvRecorder) sets CUTOFF and TONE; otherwise the knobs.
        const bool playing = recorder.isPlayingBack();
        const uint16_t tone = hats::noiseTone(playing ? playTone : liveTone, cc74);
        const uint16_t cut = playing ? playCutoff : liveCutoff;

        noiseHold = hats::noiseHoldTicks(tone);
        swingMix = (uint8_t)(tone >> 2);
        uint16_t duty = cutoffTable[cut > 1023 ? 1023 : cut];
        cutoffDuty = duty == 0xFFFF ? hats::PWM_FULL : duty;
    }
}
