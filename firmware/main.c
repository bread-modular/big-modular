/* ATtiny1616-SNR SOIC20 target; target compile and hardware qualification pending.
 * No stage can turn on in this checked-in configuration.
 */
#ifndef F_CPU
#define F_CPU 3333333UL /* factory 20MHz oscillator /6; verify fuses before programming */
#endif
#include <avr/io.h>
#include <avr/cpufunc.h>
#include <avr/wdt.h>
#include <avr/interrupt.h>
#include <util/atomic.h>
#include <util/delay.h>
#include "logic.h"
#ifndef POWER_STAGE_QUALIFIED
#define POWER_STAGE_QUALIFIED 0
#endif
static volatile uint32_t milliseconds;
ISR(TCB0_INT_vect){milliseconds++;TCB0.INTFLAGS=TCB_CAPT_bm;}
#define SDA PIN1_bm
#define SCL PIN2_bm
static void lo(uint8_t m){PORTA.OUTCLR=m;PORTA.DIRSET=m;}
static void release(uint8_t m){PORTA.DIRCLR=m;}
static bool high(uint8_t m){return (PORTA.IN&m)!=0;}
static bool clock_hi(void){release(SCL);for(uint16_t t=0;t<1000;t++){if(high(SCL))return true;_delay_us(2);}return false;}
static void stop(void){lo(SDA);(void)clock_hi();_delay_us(5);release(SDA);_delay_us(5);}
static bool begin(void){release(SDA);if(!clock_hi()||!high(SDA))return false;_delay_us(5);lo(SDA);_delay_us(5);lo(SCL);return true;}
static bool put(uint8_t v){for(uint8_t k=0;k<8;k++){if(v&128)release(SDA);else lo(SDA);_delay_us(3);if(!clock_hi())return false;_delay_us(3);lo(SCL);v<<=1;}release(SDA);if(!clock_hi())return false;_delay_us(3);bool ack=!high(SDA);lo(SCL);return ack;}
static bool get(uint8_t*out){uint8_t v=0;release(SDA);for(uint8_t k=0;k<8;k++){if(!clock_hi())return false;_delay_us(3);v=(uint8_t)((v<<1)|high(SDA));lo(SCL);_delay_us(3);}/* NACK single byte (CH224A, no burst assumption) */release(SDA);if(!clock_hi())return false;_delay_us(3);lo(SCL);*out=v;return true;}
static bool readreg(uint8_t addr,uint8_t reg,uint8_t*out){bool ok=begin()&&put(addr<<1)&&put(reg)&&begin()&&put((addr<<1)|1)&&get(out);stop();return ok;}
static bool writereg(uint8_t addr,uint8_t reg,uint8_t v){bool ok=begin()&&put(addr<<1)&&put(reg)&&put(v);stop();return ok;}
static uint16_t adc(uint8_t channel){ADC0.MUXPOS=channel;_delay_us(100);ADC0.COMMAND=ADC_STCONV_bm;while(!(ADC0.INTFLAGS&ADC_RESRDY_bm)){}ADC0.INTFLAGS=ADC_RESRDY_bm;return ADC0.RES;}
static uint16_t mv(uint8_t ch,uint16_t num,uint16_t den){/* internal reference calibration still required */return (uint32_t)adc(ch)*2500UL*num/(1023UL*den);}
static void outputs(const controller_t*c){
    /* Low permit, Hi-Z deny; data latch pre-cleared before direction changes. */
    PORTB.OUTCLR=PIN2_bm;if(c->permit)PORTB.DIRSET=PIN2_bm;else PORTB.DIRCLR=PIN2_bm;
    if(c->bipolar)PORTB.OUTSET=PIN3_bm;else PORTB.OUTCLR=PIN3_bm;
    PORTC.OUTSET=7;PORTC.OUTCLR=c->leds&7;
}
int main(void){
    controller_t c;controller_init(&c);
    PORTB.OUTCLR=PIN2_bm|PIN3_bm;PORTB.DIRCLR=PIN2_bm;PORTB.DIRSET=PIN3_bm;
    PORTC.OUTSET=7;PORTC.DIRSET=7; /* PC0..2 sink LEDs */
    PORTC.PIN3CTRL=PORT_PULLUPEN_bm;PORTB.PIN0CTRL=PORT_PULLUPEN_bm;PORTA.PIN3CTRL=PORT_PULLUPEN_bm;
    release(SDA|SCL); /* CH224A contains 7..15k pullups, verify bus rise time */
    VREF.CTRLA=VREF_ADC0REFSEL_2V5_gc;VREF.CTRLB=VREF_ADC0REFEN_bm;
    ADC0.CTRLC=ADC_PRESC_DIV16_gc|ADC_REFSEL_INTREF_gc;ADC0.SAMPCTRL=31;ADC0.CTRLA=ADC_ENABLE_bm;
    /* Runtime BOD + watchdog; verify header names and fuse readback with real toolchain. */
    _PROTECTED_WRITE(BOD.CTRLB,BOD_LVL_BODLEVEL2_gc); /* nominal 2.6V */
    _PROTECTED_WRITE(BOD.CTRLA,BOD_ACTIVE_ENABLED_gc|BOD_SLEEP_ENABLED_gc);
    _PROTECTED_WRITE(WDT.CTRLA,WDT_PERIOD_1KCLK_gc);
    TCB0.CCMP=(F_CPU/1000UL)-1;TCB0.CTRLB=TCB_CNTMODE_INT_gc;TCB0.INTCTRL=TCB_CAPT_bm;TCB0.CTRLA=TCB_CLKSEL_CLKDIV1_gc|TCB_ENABLE_bm;sei();
    uint8_t addr=0,st=0,cap=0;
    for(;;){
        inputs_t in={0};ATOMIC_BLOCK(ATOMIC_RESTORESTATE){in.now=milliseconds;}
        if(!addr){if(readreg(0x22,0x09,&st))addr=0x22;else if(readreg(0x23,0x09,&st))addr=0x23;if(addr&&!writereg(addr,0x0a,1))addr=0;}
        in.pd_valid=addr&&readreg(addr,0x09,&st)&&readreg(addr,0x50,&cap);
        if(!in.pd_valid)addr=0;
        in.pd_active=(st&0x08)!=0;in.current_50ma=cap;
        in.pg_low=!(PORTA.IN&PIN3_bm);in.flt_low=!(PORTB.IN&PIN0_bm);in.reset=!(PORTC.IN&PIN3_bm);
        in.rail[0]=mv(4,6,1);in.rail[1]=mv(6,200,33);in.rail[2]=mv(7,3,1);
        in.mid=mv(8,3,1);in.vbus=mv(9,11,1);in.vprot=mv(10,11,1);
        controller_step(&c,&in,POWER_STAGE_QUALIFIED);outputs(&c);wdt_reset();_delay_ms(5);
    }
}
