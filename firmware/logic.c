#include "logic.h"
#include <string.h>
static bool elapsed(uint32_t now,uint32_t then,uint32_t ms){return (uint32_t)(now-then)>=ms;}
static bool window(uint16_t v,uint16_t lo,uint16_t hi){return v>=lo && v<=hi;}
void controller_init(controller_t *c){memset(c,0,sizeof(*c));c->phase=WAIT_PD;}
uint8_t rail_hysteresis(controller_t *c,const inputs_t *in){
    const uint16_t nominal[3]={12000,12000,5000};
    for(uint8_t i=0;i<3;i++){
        uint8_t bit=(uint8_t)(1u<<i);
        if(!window(in->rail[i],nominal[i]*95ul/100,nominal[i]*105ul/100)){
            c->faults|=bit;c->restore_since[i]=in->now;
        }else if(window(in->rail[i],nominal[i]*96ul/100,nominal[i]*104ul/100)){
            if(elapsed(in->now,c->restore_since[i],100))c->faults&=(uint8_t)~bit;
        }else c->restore_since[i]=in->now;
    }
    return c->faults;
}
static void latch(controller_t *c,uint8_t fault){
    if(!c->first_fault)c->first_fault=fault;
    c->general_fault=!fault;c->phase=LATCHED;c->permit=false;c->bipolar=false;
}
void controller_step(controller_t *c,const inputs_t *in,bool qualified){
    /* Explicit status or measured voltage proves absence; unknown I2C is a
       general diagnostic fault, not a fabricated claim of missing PD. */
    bool voltage9=window(in->vbus,8550,9450);
    bool actual_missing=!voltage9 || (in->pd_valid && !in->pd_active);
    bool status9=in->pd_valid && in->pd_active && voltage9;
    bool authorized=status9 && in->pg_low && in->current_50ma>=60;
    bool reset_edge=in->reset && !c->last_reset;
    c->last_reset=in->reset;
    if(reset_edge){controller_init(c);c->last_reset=true;c->since=in->now;}
    c->missing9=actual_missing;
    if(actual_missing){
        c->permit=false;c->bipolar=false;
        if(c->phase!=LATCHED){c->phase=WAIT_PD;c->since=in->now;}
        c->leds=((in->now/1000u)&1u)?0:7;return; /* 0.5 Hz, shared phase */
    }
    if(!qualified){c->permit=false;c->bipolar=false;c->leds=((in->now/125u)&1u)?0:7;return;}
    if(!authorized){
        c->permit=false;c->bipolar=false;
        if(c->phase==RUNNING || c->phase==BI_START || c->phase==BUCK_START)latch(c,0);
        else {c->phase=WAIT_PD;c->since=in->now;}
        c->leds=((in->now/125u)&1u)?0:7;return;
    }
    switch(c->phase){
    case WAIT_PD: c->since=in->now;c->phase=QUALIFY;break;
    case QUALIFY:
        if(elapsed(in->now,c->since,100)){c->permit=true;c->phase=BUCK_START;c->since=in->now;c->mid_since=in->now;}
        break;
    case BUCK_START:
        /* RUN may still be open; no slow missing-PD pattern for that case. */
        if(!window(in->mid,5050,5380) || !window(in->vprot,7800,10000))c->mid_since=in->now;
        if(elapsed(in->now,c->mid_since,100) && !in->flt_low){c->bipolar=true;c->phase=BI_START;c->since=in->now;}
        else if(elapsed(in->now,c->since,750))latch(c,0);
        break;
    case BI_START:
        if(!window(in->mid,4950,5400) || in->flt_low){latch(c,0);break;}
        if(elapsed(in->now,c->since,250)){
            c->faults=0;
            for(uint8_t i=0;i<3;i++)c->restore_since[i]=in->now;
            if(rail_hysteresis(c,in))latch(c,c->faults);else c->phase=RUNNING;
        }
        break;
    case RUNNING:
        /* Sample and preserve first affected rail BEFORE global disable. */
        if(rail_hysteresis(c,in))latch(c,c->faults);
        else if(in->flt_low || !window(in->mid,4950,5400) || !window(in->vprot,7800,10000))latch(c,0);
        break;
    case LATCHED: c->permit=false;c->bipolar=false;break;
    }
    if(c->phase==RUNNING)c->leds=7;
    else if(c->phase==LATCHED)c->leds=((in->now/125u)&1u)?0:(c->first_fault?c->first_fault:7);
    else c->leds=0;
}
