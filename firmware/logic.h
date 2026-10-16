#ifndef BIG_MODULAR_LOGIC_H
#define BIG_MODULAR_LOGIC_H
#include <stdbool.h>
#include <stdint.h>
typedef enum {WAIT_PD, QUALIFY, BUCK_START, BI_START, RUNNING, LATCHED} phase_t;
typedef struct {
    uint32_t now;
    uint16_t vbus, vprot, mid, rail[3]; /* mV; negative-rail magnitude */
    bool pd_valid, pd_active, pg_low, flt_low, reset;
    uint8_t current_50ma;
} inputs_t;
typedef struct {
    phase_t phase;
    uint32_t since, mid_since, restore_since[3];
    uint8_t faults, first_fault;
    bool general_fault, permit, bipolar, missing9, last_reset;
    uint8_t leds;
} controller_t;
void controller_init(controller_t *c);
void controller_step(controller_t *c, const inputs_t *in, bool power_qualified);
uint8_t rail_hysteresis(controller_t *c, const inputs_t *in);
#endif
