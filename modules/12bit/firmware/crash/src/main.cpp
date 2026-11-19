// ============================================================================
// 12bit crash firmware (STM32G071C8T6 U3): synthesized crash cymbal (TR-808 /
// TR-909 style) + TR-808 cowbell, every setting at the same level (the one
// of ../clapsnare), with a resonant FILTER.
//
//   PB7 USART1_RX  MIDI 31250 baud, all channels; RXINV for JP1 = P.
//                  Note-on fires the voice, velocity = level (the clapsnare
//                  curve), note ignored;
//                  note-off releases it (the gate length = the ring length).
//   PA1 ADC_IN1    P1 knob (RV1): MORPH, crash -> both layered -> cowbell
//   PA6 ADC_IN6    P2 knob (RV2): TONE, fully left = the classic sounds, then
//                  both are tuned up
//   PA7 ADC_IN7    P3 knob (RV3): FILTER, resonant low-pass; fully left = off
//   PA0 ADC_IN0    CV in: added to FILTER, 5 V = the whole knob travel,
//                  bipolar (after the recorder, so it is never recorded)
//   PA4 DAC1_OUT1  OUT 1
//   PA5 DAC1_OUT2  OUT 2: the same signal
//   PB4            MODE button (internal pull-up): 4-bar knob recorder on
//                  MIDI clock (click = record, loops after 4 bars, click = live;
//                  hold + turn a knob while looping = overdub that knob)
//   PB5            MODE LED (R7 -> D1): the recorder only: blinks while
//                  recording or overdubbing, solid while looping, off in live
//
// Clock: HSI16 -> PLL 64 MHz, no crystal. TIM6 48 kHz sample tick, SysTick
// 1 ms.
//
// Knob + CV ADC as ../clapsnare: TIM6 starts one four-channel scan per sample
// and DMA stores it, and the scan only runs while the voice sounds or a take
// is recorded (a note-on with the scan off first reads the knobs, 0.33 ms).
// Between the hits the ADC is idle (no 1 kHz buzz at the outputs).
// ============================================================================

#include "stm32g0xx.h"
#include "crash_logic.h"

// JP1 on the 12bit carrier picks the MIDI input path (set by ../jumper.sh):
//   P (protected) = NPN front end (Q1), which inverts the UART data -> 1
//   D (direct)    = jack tip straight to PB7, as Bread Modular     -> 0
#ifndef MIDI_RX_INVERT
#error "MIDI_RX_INVERT must be set: build with ../compile.sh crash p|d"
#endif

#define ADC_CH_CV 0   // PA0
#define ADC_CH_P1 1   // PA1
#define ADC_CH_P2 6   // PA6
#define ADC_CH_P3 7   // PA7

#define ADC_CHANNELS 4
#define ADC_SCANS 16   // averaged per reading

static const uint32_t SYSCLK_HZ = 64000000;
static const uint32_t REC_BLINK_MS = 150;   // as the shared CvRecorder

static volatile uint32_t g_millis = 0;

// ---- shared with the interrupts ------------------------------------------------
static crash::Tables tables;               // filled at boot, read-only after
static crash::Voice voice;                 // rendered in the sample interrupt
static volatile uint8_t trigVelocity = 0;  // != 0: fire on the next sample
static volatile uint8_t releasePending = 0;   // note-off: release on the next sample

static volatile uint8_t rxBuf[64];
static volatile uint8_t rxHead = 0;
static uint8_t rxTail = 0;

// Worst sample-interrupt run time in timer counts (1 / 64 MHz) of the 1333
// per sample; read it over SWD to check the CPU headroom.
volatile uint16_t g_sampleIsrMaxTicks = 0;

// Scans in a ring, written by DMA: CV, P1, P2, P3 (ascending channel order).
static volatile uint16_t adcBuf[ADC_SCANS * ADC_CHANNELS];

// ADC overruns recovered by a restart of the scan (never expected).
volatile uint16_t g_adcOverruns = 0;

// Smoothed CV ADC code (0 V = crash::CV_ZERO), for a read over SWD.
volatile uint16_t g_cvAdc = 0;

// 1 while the knob scan runs, and how often a note-on or a recording started
// it, for a read over SWD.
volatile uint8_t g_scanning = 0;
volatile uint16_t g_scanWakes = 0;

// ---- state -------------------------------------------------------------------------
static crash::MidiParser midi;
static crash::MotionRecorder recorder;
static uint16_t live[3];   // smoothed knobs: MORPH, TONE, FILTER
static uint16_t play[3];   // recorder output
static crash::KnobFilter smooth[3];   // ADC jitter
static crash::KnobFilter glide[3];    // recorder steps
static crash::KnobFilter cvSmooth;    // ~4 ms (rate set in main)

extern "C" {

void SysTick_Handler(void) { g_millis++; }

void TIM6_DAC_LPTIM1_IRQHandler(void) {
    TIM6->SR = 0;
    const uint8_t vel = trigVelocity;
    if (vel) {
        trigVelocity = 0;
        voice.trigger(vel);
    }
    if (releasePending) {
        releasePending = 0;
        voice.release();
    }
    const uint32_t v = crash::toDac(voice.render());
    DAC1->DHR12RD = v | (v << 16);   // both channels in one write
    const uint16_t ticks = (uint16_t)TIM6->CNT;
    if (ticks > g_sampleIsrMaxTicks) g_sampleIsrMaxTicks = ticks;
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

static void dacInit() {
    RCC->APBENR1 |= RCC_APBENR1_DAC1EN;
    DAC1->MCR = 0;          // both channels: buffer on, to the pin
    DAC1->DHR12RD = (uint32_t)crash::DAC_MID | ((uint32_t)crash::DAC_MID << 16);
    DAC1->CR = DAC_CR_EN1 | DAC_CR_EN2;
}

static void delayUs(uint32_t us) {
    volatile uint32_t n = us * (SYSCLK_HZ / 4000000);   // >= 4 cycles per pass
    while (n--) {}
}

// Arms the stopped ADC: every TIM6 update then converts PA0, PA1, PA6, PA7
// once (4 x 3.25 us of the 20.8 us sample period) into adcBuf, from its start.
static void adcStart() {
    DMA1_Channel1->CCR = 0;
    DMA1_Channel1->CPAR = (uint32_t)&ADC1->DR;
    DMA1_Channel1->CMAR = (uint32_t)adcBuf;
    DMA1_Channel1->CNDTR = ADC_SCANS * ADC_CHANNELS;
    DMA1->IFCR = DMA_IFCR_CTCIF1;
    DMA1_Channel1->CCR = DMA_CCR_MINC | DMA_CCR_CIRC | DMA_CCR_MSIZE_0 | DMA_CCR_PSIZE_0 | DMA_CCR_EN;
    ADC1->ISR = ADC_ISR_OVR;
    ADC1->CFGR1 |= ADC_CFGR1_DMAEN;
    ADC1->CR |= ADC_CR_ADSTART;
}

// Stops the conversions; the ADC stays enabled and idle. DMAEN off and a read
// of DR drop a pending DMA request, which would shift the next ring by one.
static void adcStop() {
    if (ADC1->CR & ADC_CR_ADSTART) {
        ADC1->CR |= ADC_CR_ADSTP;
        while (ADC1->CR & ADC_CR_ADSTP) {}
    }
    ADC1->CFGR1 &= ~ADC_CFGR1_DMAEN;
    (void)ADC1->DR;
    DMA1_Channel1->CCR = 0;
}

static void adcInit() {
    RCC->APBENR2 |= RCC_APBENR2_ADCEN;
    RCC->AHBENR |= RCC_AHBENR_DMA1EN;
    ADC1->CFGR2 = 2u << ADC_CFGR2_CKMODE_Pos;        // PCLK / 4 = 16 MHz, no oversampling
    ADC1->CR = ADC_CR_ADVREGEN;
    delayUs(30);
    ADC1->CR |= ADC_CR_ADCAL;
    while (ADC1->CR & ADC_CR_ADCAL) {}
    ADC1->SMPR = 5u << ADC_SMPR_SMP1_Pos;            // 39.5 cycles (10n on each wiper)
    // 12 bit, one ascending scan per TIM6_TRGO (TRG5) rising edge, DMA ring
    // (DMAEN in adcStart: a calibration with it set leaves a request pending)
    ADC1->CFGR1 = ADC_CFGR1_OVRMOD | ADC_CFGR1_EXTEN_0 | (5u << ADC_CFGR1_EXTSEL_Pos) | ADC_CFGR1_DMACFG;
    ADC1->ISR = ADC_ISR_CCRDY;
    ADC1->CHSELR = (1u << ADC_CH_CV) | (1u << ADC_CH_P1) | (1u << ADC_CH_P2) | (1u << ADC_CH_P3);
    for (uint32_t i = 0; i < 100000 && !(ADC1->ISR & ADC_ISR_CCRDY); i++) {}
    DMAMUX1_Channel0->CCR = 5;                       // DMA1 channel 1 <- ADC
    ADC1->ISR = ADC_ISR_ADRDY;
    ADC1->CR |= ADC_CR_ADEN;
    while (!(ADC1->ISR & ADC_ISR_ADRDY)) {}
}

// The mean of the last ADC_SCANS scans. An overrun stops the DMA requests and
// would shift the channel order in the ring: restart the scan from PA0.
static void readKnobs(uint16_t *knob, uint16_t *cv) {
    if (ADC1->ISR & ADC_ISR_OVR) {
        adcStop();
        adcStart();
        g_adcOverruns++;
    }
    uint32_t sum[ADC_CHANNELS] = {0, 0, 0, 0};
    for (int i = 0; i < ADC_SCANS * ADC_CHANNELS; i++) sum[i % ADC_CHANNELS] += adcBuf[i];
    *cv = (uint16_t)(sum[0] / ADC_SCANS);
    for (int i = 0; i < 3; i++) knob[i] = (uint16_t)(sum[i + 1] / ADC_SCANS);
}

static void sampleTimerInit() {
    RCC->APBENR1 |= RCC_APBENR1_TIM6EN;
    TIM6->PSC = 0;
    TIM6->ARR = SYSCLK_HZ / crash::SAMPLE_RATE_HZ - 1;
    TIM6->CR2 = TIM_CR2_MMS_1;       // TRGO on update: starts the ADC scan
    TIM6->CR1 = TIM_CR1_CEN;
}

static void sampleIrqInit() {
    TIM6->SR = 0;
    TIM6->DIER = TIM_DIER_UIE;
    NVIC_SetPriority(TIM6_DAC_LPTIM1_IRQn, 0);
    NVIC_EnableIRQ(TIM6_DAC_LPTIM1_IRQn);
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

// Knobs (or the recorded take) + CV on FILTER -> synthesis parameters, when
// they moved (table look-ups and a few divisions: only here, never per
// sample). snap: no glide, for the first reading after the scan was off.
static void updateParams(uint16_t cv, bool snap) {
    static uint16_t applied[3];
    static bool first = true;
    const bool playing = recorder.state == crash::MotionRecorder::PLAYBACK;
    uint16_t k[3];
    bool changed = first;
    for (int i = 0; i < 3; i++) {
        const uint16_t target = playing ? play[i] : live[i];
        k[i] = snap ? glide[i].set(target) : glide[i].update(target);
        if (i == 2) k[i] = crash::applyCv(k[i], cv);
        if (k[i] != applied[i]) changed = true;
    }
    if (!changed) return;
    first = false;
    const crash::Params next = crash::makeParams(tables, k[0], k[1], k[2]);
    __disable_irq();
    voice.p = next;
    __enable_irq();
    for (int i = 0; i < 3; i++) applied[i] = k[i];
}

// ---- knob scan gate -----------------------------------------------------------------

// The 1 kHz knob read while the scan runs. snap: jump to the reading.
static void knobUpdate(bool snap) {
    uint16_t knob[3];
    uint16_t cv;
    readKnobs(knob, &cv);
    for (int i = 0; i < 3; i++) live[i] = snap ? smooth[i].set(knob[i]) : smooth[i].update(knob[i]);
    g_cvAdc = snap ? cvSmooth.set(cv) : cvSmooth.update(cv);
    updateParams(g_cvAdc, snap);
}

// Starts the scan and waits for a full ring of fresh scans (0.33 ms; the
// bound covers a stopped TIM6), so the next hit plays the knobs as they are.
static void scanWake() {
    adcStart();
    for (uint32_t i = 0; i < 20000 && !(DMA1->ISR & DMA_ISR_TCIF1); i++) {}
    knobUpdate(true);
    g_scanning = 1;
    g_scanWakes++;
}

static void scanSleep() {
    adcStop();
    g_scanning = 0;
}

// ---- MIDI ---------------------------------------------------------------------------

static void handleMidi() {
    while (rxTail != rxHead) {
        uint8_t b = rxBuf[rxTail];
        rxTail = (uint8_t)((rxTail + 1) & 63);
        crash::MidiParser::Event ev = midi.feed(b);
        switch (ev.kind) {
            case crash::MidiParser::NOTE_ON:
                if (!g_scanning) scanWake();   // the knobs as they are now
                releasePending = 0;            // an earlier note-off must not cut this hit
                trigVelocity = ev.data2;       // the note itself is ignored
                break;
            case crash::MidiParser::NOTE_OFF:
                releasePending = 1;            // any note-off, as the 8bit crash
                break;
            case crash::MidiParser::CLOCK:
                recorder.onClock(live, play);
                break;
            case crash::MidiParser::START:
                recorder.onStart();
                break;
            default:
                break;
        }
    }
}

// ---- MODE button + LED ------------------------------------------------------------

// Debounced MODE edges to the recorder: press, and release (overdub hold).
static void modeUpdate() {
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
        if (stable) recorder.press();
        else recorder.release();
    }
}

// The recorder only (no flash on a note): RECORDING and overdub blink,
// PLAYBACK solid, LIVE off.
static void ledUpdate() {
    bool on;
    switch (recorder.state) {
        case crash::MotionRecorder::RECORDING:
            on = (g_millis / REC_BLINK_MS) & 1;
            break;
        case crash::MotionRecorder::PLAYBACK:
            on = !recorder.overdubbing() || ((g_millis / REC_BLINK_MS) & 1);
            break;
        default:
            on = false;
            break;
    }
    if (on) GPIOB->BSRR = 1u << 5;
    else GPIOB->BRR = 1u << 5;
}

int main() {
    clockInit();
    gpioInit();
    dacInit();
    sampleTimerInit();
    tables.fill();                     // soft floats, ~0.1 s
    // S3 boards: the +3V0 reference (VREF+) comes up ~13 ms after the MCU
    // supply; let it settle before the ADC calibration and the first knob read.
    delayUs(20000);
    adcInit();
    cvSmooth.rate = 2;                 // ~4 ms: the CV may be an envelope or a sequencer step
    scanWake();
    for (int i = 0; i < 3; i++) play[i] = live[i];
    sampleIrqInit();
    midiInit();

    uint32_t lastScan = g_millis;
    for (;;) {
        handleMidi();
        modeUpdate();
        // The scan runs while the voice sounds (the CV and a recorded take
        // keep moving the sound), while a take is recorded and while MODE is held
        // for an overdub.
        const bool need = voice.active || trigVelocity || recorder.state == crash::MotionRecorder::RECORDING ||
                          recorder.holding;
        if (need && !g_scanning) {
            scanWake();
            lastScan = g_millis;
        } else if (!need && g_scanning) {
            scanSleep();
        }
        if (g_scanning && g_millis != lastScan) {   // 1 kHz knob read, so the filter times are fixed (~16 ms)
            lastScan = g_millis;
            knobUpdate(false);
        }
        ledUpdate();
    }
}
