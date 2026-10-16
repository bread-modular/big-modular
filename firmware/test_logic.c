#include "logic.h"
#include <assert.h>
#include <stdio.h>
static inputs_t healthy(void){inputs_t in={0};in.vbus=9000;in.vprot=9000;in.mid=5216;in.rail[0]=in.rail[1]=12000;in.rail[2]=5000;in.pd_valid=in.pd_active=in.pg_low=true;in.current_50ma=60;return in;}
static void start(controller_t*c,inputs_t*i){controller_init(c);for(i->now=0;i->now<=500;i->now+=10)controller_step(c,i,true);assert(c->phase==RUNNING&&c->permit&&c->bipolar&&c->leds==7);}
int main(void){
    controller_t c;inputs_t i=healthy();start(&c,&i);
    for(int rail=0;rail<3;rail++){
        i=healthy();start(&c,&i);i.rail[rail]=0;controller_step(&c,&i,true);
        assert(c.phase==LATCHED&&!c.permit&&!c.bipolar&&c.first_fault==(1<<rail));
        i.rail[0]=i.rail[1]=i.rail[2]=0;i.now+=125;controller_step(&c,&i,true);assert(c.first_fault==(1<<rail));
        i.vbus=5000;controller_step(&c,&i,true);assert(c.missing9&&c.leds==7);
    }
    i=healthy();controller_init(&c);i.vbus=5000;
    for(i.now=0;i.now<5000;i.now+=10){controller_step(&c,&i,true);assert(!c.permit&&!c.bipolar);assert(c.leds==(((i.now/1000)&1)?0:7));}
    i=healthy();controller_init(&c);for(i.now=0;i.now<1000;i.now+=10)controller_step(&c,&i,false);assert(!c.permit&&!c.bipolar&&!c.missing9);
    i=healthy();controller_init(&c);i.pd_valid=false;controller_step(&c,&i,true);assert(!c.permit&&!c.missing9);
    i=healthy();controller_init(&c);i.current_50ma=30;for(i.now=0;i.now<500;i.now+=10)controller_step(&c,&i,true);assert(!c.permit&&!c.missing9);
    i=healthy();start(&c,&i);i.flt_low=true;controller_step(&c,&i,true);assert(c.general_fault&&!c.missing9&&!c.permit);
    i=healthy();controller_init(&c);i.vprot=0;i.mid=0;for(i.now=0;i.now<1000;i.now+=10)controller_step(&c,&i,true);assert(c.phase==LATCHED&&!c.missing9&&!c.bipolar);
    i=healthy();start(&c,&i);i.rail[2]=4000;controller_step(&c,&i,true);i=healthy();i.reset=true;controller_step(&c,&i,true);assert(c.first_fault==0&&!c.permit);
    /* Independent rail hysteresis: 5% trip, 4% +100ms restore, no chatter. */
    controller_init(&c);i=healthy();i.now=0;i.rail[0]=11300;assert(rail_hysteresis(&c,&i)==1);
    i.rail[0]=11480;i.now=200;assert(rail_hysteresis(&c,&i)==1);
    i.rail[0]=12000;i.now=299;assert(rail_hysteresis(&c,&i)==1);i.now=300;assert(rail_hysteresis(&c,&i)==0);
    /* Wrap-safe qualifier. */
    controller_init(&c);i=healthy();i.now=0xfffffff0u;controller_step(&c,&i,true);i.now=84;controller_step(&c,&i,true);assert(c.permit);
    puts("PASS: startup, independent faults, first-fault retention, PD override, unknown/current/RUN/FLT semantics, hysteresis, reset, wrap, default deny");
}
