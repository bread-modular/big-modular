#include "cal.h"

#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#include "audio.h"
#include "board.h"
#include "console.h"

#define NI AUDIO_IN_CHANNELS
#define NO AUDIO_OUT_CHANNELS

// Saved measurements (settings page, board.h): raw codes, so the coefficients
// are derived again whenever a part is measured anew.
#define SETTINGS_MAGIC   0x38583643u   // "C6X8"
#define SETTINGS_VERSION 1u

typedef struct {
  uint32_t magic, version;
  uint8_t in_valid, out_valid;      // bit per channel
  uint8_t out_in[NO];               // input each output was measured through (0..5)
  uint8_t pad[2];
  int32_t in_zero[NI];              // ADC code with the input at 0 V (unpatched)
  int32_t out_zero[NO];             // ADC code at out_in with the output at DAC code 0
  int32_t out_loop[NO];             // loop gain, ADC code / DAC code, Q30
  int32_t ref;                      // `cal ref` correction of the DAC / ADC split, Q30
  uint32_t crc;                     // of the fields before it
} settings_t;

_Static_assert(sizeof(settings_t) <= BOARD_SETTINGS_BYTES, "settings page");

static settings_t set;
static bool saved_ok = true;

// Levels (millivolts at the jack, nominal full scale before the calibration)
#define LOOP_MV       4000         // `cal out` / `looptest` steps: +-4 V
#define CAL_IN_OUT_MV 2000         // every output during `cal in`
#define SETTLE_MS     150
#define MEASURE_MS    250
#define IN_WINDOWS    8            // `cal in`: 100 ms windows, the last 4 must agree
#define IN_WINDOW_MS  100
#define IN_LIMIT_MV   200          // more is not an input offset (patched?)
#define IN_NOISE_MV   10           // peak to peak per window
#define IN_STABLE_UV  500          // window means within 0.5 mV

typedef enum { RUN_IDLE, RUN_IN, RUN_OUT, RUN_LOOPTEST } run_t;
static run_t run = RUN_IDLE;
static int step;                   // RUN_OUT / RUN_LOOPTEST: 0 = all at 0, then 1 + 2 * o + (0: +, 1: -)
static bool measuring;
static uint32_t at;
static int32_t meas[1 + 2 * NO][NI];          // input means per step (raw codes)
static int32_t win_mean[IN_WINDOWS][NI], win_pp[IN_WINDOWS][NI];

static inline int32_t iabs32(int32_t v) {
  return v < 0 ? -v : v;
}

// Nominal conversions (before the calibration)
static int32_t in_mv_to_code(int32_t mv) {
  return (int32_t) (((int64_t) mv * AUDIO_FS_CODE) / AUDIO_IN_FS_MV);
}

static int32_t in_code_to_uv(int32_t code) {
  return (int32_t) (((int64_t) code * AUDIO_IN_FS_MV * 1000) / AUDIO_FS_CODE);
}

static int32_t out_mv_to_code(int32_t mv) {
  return (int32_t) (((int64_t) mv * AUDIO_FS_CODE) / AUDIO_OUT_FS_MV);
}

static double sqrt_d(double x) {   // no libm: Newton from 1 (x is near 1)
  double r = x > 1.0 ? x : 1.0;
  for (int i = 0; i < 40; i++) r = 0.5 * (r + x / r);
  return r;
}

static int32_t to_q30(double v) {
  return (int32_t) (v * (double) AUDIO_Q30 + (v < 0 ? -0.5 : 0.5));
}

static double from_q30(int32_t v) {
  return (double) v / (double) AUDIO_Q30;
}

//--------------------------------------------------------------------+
// Coefficients
//--------------------------------------------------------------------+

// Output whose loop sets input i's share of the gain: OUT i+1 when it was
// measured through IN i+1, else the first output measured through it; -1 none.
static int primary_out(int i) {
  if (i < NO && (set.out_valid >> i & 1) && set.out_in[i] == i) return i;
  for (int o = 0; o < NO; o++) {
    if ((set.out_valid >> o & 1) && set.out_in[o] == i) return o;
  }
  return -1;
}

// Loop gain in jack volts per jack volt (nominal scales): e_out * e_in.
static double loop_of(int o) {
  return from_q30(set.out_loop[o]) * AUDIO_IN_FS_MV / AUDIO_OUT_FS_MV;
}

// e_in / e_out: actual gain / nominal gain of each side.
static void split(double e_in[NI], double e_out[NO]) {
  double const r = set.ref ? from_q30(set.ref) : 1.0;
  for (int i = 0; i < NI; i++) {
    int const p = primary_out(i);
    e_in[i] = p < 0 ? 1.0 : sqrt_d(loop_of(p)) / r;
  }
  for (int o = 0; o < NO; o++) {
    e_out[o] = (set.out_valid >> o & 1) ? loop_of(o) / e_in[set.out_in[o]] : 1.0;
  }
}

static void apply(void) {
  double e_in[NI], e_out[NO];
  split(e_in, e_out);
  audio_coef_t k;
  for (int i = 0; i < NI; i++) {
    k.in_zero[i] = (set.in_valid >> i & 1) ? set.in_zero[i] : 0;
    k.in_gain[i] = to_q30((double) AUDIO_IN_FS_MV / AUDIO_FS_MV / e_in[i]);
  }
  for (int o = 0; o < NO; o++) {
    double const g = (double) AUDIO_FS_MV / AUDIO_OUT_FS_MV / e_out[o];
    k.out_gain[o] = to_q30(g);
    if (set.out_valid >> o & 1) {
      int const i = set.out_in[o];
      // The output's level at DAC code 0, as a calibrated sample, cancelled.
      double const v0 = (double) (set.out_zero[o] - k.in_zero[i]) * from_q30(k.in_gain[i]);
      k.out_zero[o] = (int32_t) (-v0 * g + (v0 < 0 ? 0.5 : -0.5));
    } else {
      k.out_zero[o] = 0;
    }
  }
  audio_set_coef(&k);
}

static void defaults(void) {
  memset(&set, 0, sizeof(set));
  set.magic = SETTINGS_MAGIC;
  set.version = SETTINGS_VERSION;
  set.ref = AUDIO_Q30;
}

static bool save(void) {
  set.crc = board_crc32(&set, offsetof(settings_t, crc));
  if (!memcmp(&set, board_settings(), sizeof(set))) return true;
  // Flash writes stall the bus: TDM stops and restarts around them.
  audio_restart(0);
  bool const ok = board_settings_write(&set, sizeof(set));
  audio_restart(0);
  saved_ok = ok;
  return ok;
}

void cal_init(void) {
  settings_t const *const s = board_settings();
  if (s->magic == SETTINGS_MAGIC && s->version == SETTINGS_VERSION &&
      s->crc == board_crc32(s, offsetof(settings_t, crc))) {
    set = *s;
  } else {
    defaults();
  }
  apply();
}

bool cal_erase(void) {
  defaults();
  apply();
  audio_restart(0);
  bool const ok = board_settings_write(NULL, 0);
  audio_restart(0);
  saved_ok = ok;
  return ok;
}

bool cal_busy(void) {
  return run != RUN_IDLE;
}

//--------------------------------------------------------------------+
// Measurements
//--------------------------------------------------------------------+

// Output sources for a step: everything at 0, output `o` at `mv` (raw DAC codes
// for `cal out`, calibrated samples for `looptest`).
static void drive(int o, int32_t mv) {
  for (int c = 0; c < NO; c++) {
    int32_t const v = c == o ? mv : 0;
    if (run == RUN_LOOPTEST) {
      audio_gen_set(c, GEN_DC, audio_mv_to_sample(v));
    } else {
      audio_gen_set(c, GEN_RAW, out_mv_to_code(v));
    }
  }
}

static void release_outputs(void) {
  for (int c = 0; c < NO; c++) audio_gen_set(c, GEN_USB, 0);
}

static void step_drive(void) {
  if (step == 0) {
    drive(-1, 0);
  } else {
    int const o = (step - 1) / 2;
    drive(o, (step - 1) & 1 ? -LOOP_MV : LOOP_MV);
  }
}

static void start(run_t r) {
  run = r;
  step = 0;
  measuring = false;
  at = board_millis() + SETTLE_MS;
  if (r == RUN_IN) {
    for (int c = 0; c < NO; c++) audio_gen_set(c, GEN_RAW, out_mv_to_code(CAL_IN_OUT_MV));
    at = board_millis() + 3 * SETTLE_MS;
  } else {
    step_drive();
  }
}

void cal_start_inputs(void) {
  console_printf("cal in: IN 1-6 at 0 V (unpatched), every OUT at +2 V meanwhile, about 1.3 s\r\n");
  start(RUN_IN);
}

void cal_start_outputs(void) {
  console_printf("cal out: every OUT stepped to -4 / +4 V in turn, about 7 s\r\n");
  start(RUN_OUT);
}

void cal_start_looptest(void) {
  console_printf("looptest: every OUT stepped to -4 / +4 V in turn (calibrated), about 7 s\r\n");
  start(RUN_LOOPTEST);
}

static void print_mv3(int32_t uv) {   // microvolts as +x.xxx V
  int32_t const mv = (uv + (uv < 0 ? -500 : 500)) / 1000;
  console_printf("%c%ld.%03ld", mv < 0 ? '-' : '+', (long) iabs32(mv) / 1000, (long) iabs32(mv) % 1000);
}

static void print_ratio(double g) {   // +x.xxxx
  int32_t const v = (int32_t) (g * 10000.0 + (g < 0 ? -0.5 : 0.5));
  console_printf("%c%ld.%04ld", v < 0 ? '-' : '+', (long) iabs32(v) / 10000, (long) iabs32(v) % 10000);
}

static void finish_inputs(void) {
  release_outputs();
  run = RUN_IDLE;
  int32_t const lim = in_mv_to_code(IN_LIMIT_MV), noise = in_mv_to_code(IN_NOISE_MV);
  int32_t const stable = (int32_t) (((int64_t) IN_STABLE_UV * AUDIO_FS_CODE) / (AUDIO_IN_FS_MV * 1000));
  uint8_t ok = 0;
  console_printf("cal in:");
  for (int i = 0; i < NI; i++) {
    int32_t lo = INT32_MAX, hi = INT32_MIN, pp = 0;
    int64_t sum = 0;
    for (int w = IN_WINDOWS - 4; w < IN_WINDOWS; w++) {
      if (win_mean[w][i] < lo) lo = win_mean[w][i];
      if (win_mean[w][i] > hi) hi = win_mean[w][i];
      if (win_pp[w][i] > pp) pp = win_pp[w][i];
      sum += win_mean[w][i];
    }
    int32_t const mean = (int32_t) (sum / 4);
    console_printf(" IN%d ", i + 1);
    print_mv3(in_code_to_uv(mean));
    if (iabs32(mean) > lim) {
      console_printf(" (patched? kept old)");
    } else if (pp > noise || hi - lo > stable) {
      console_printf(" (not steady, kept old)");
    } else {
      set.in_zero[i] = mean;
      ok |= (uint8_t) (1u << i);
    }
  }
  console_printf(" V\r\n");
  if (!ok) {
    console_printf("cal in: nothing measured\r\n");
    return;
  }
  set.in_valid |= ok;
  apply();
  console_printf(save() ? "cal in: saved\r\n" : "cal in: NOT saved, flash write failed\r\n");
}

// Patched pairs from the steps: the input that follows output o; -1 none.
static int follower(int o, double *gain) {
  int const hi = 1 + 2 * o, lo = hi + 1;
  int best = -1;
  int32_t best_d = 0;
  for (int i = 0; i < NI; i++) {
    int32_t const d = meas[hi][i] - meas[lo][i];
    if (iabs32(d) > iabs32(best_d)) {
      best_d = d;
      best = i;
    }
  }
  int32_t const span = run == RUN_LOOPTEST ? 2 * audio_mv_to_sample(LOOP_MV) : 2 * out_mv_to_code(LOOP_MV);
  *gain = (double) best_d / (double) span;
  return *gain > 0.5 ? best : -1;
}

static void finish_outputs(void) {
  release_outputs();
  run = RUN_IDLE;
  int32_t const span = 2 * out_mv_to_code(LOOP_MV);
  uint8_t ok = 0;
  for (int o = 0; o < NO; o++) {
    double g;
    int const i = follower(o, &g);
    console_printf("  OUT%d", o + 1);
    if (i < 0) {
      console_printf(" -> no input follows it (unpatched), kept old\r\n");
      continue;
    }
    // Every other input must stay put.
    double worst = 0;
    for (int k = 0; k < NI; k++) {
      if (k == i) continue;
      double const x = (double) (meas[1 + 2 * o][k] - meas[2 + 2 * o][k]) / (double) span;
      if ((x < 0 ? -x : x) > worst) worst = x < 0 ? -x : x;
    }
    // Linearity: the 0 V step against the middle of the +-4 V steps.
    int32_t const mid = (meas[1 + 2 * o][i] + meas[2 + 2 * o][i]) / 2;
    int32_t const bow = mid - meas[0][i];
    console_printf(" -> IN%d loop ", i + 1);
    print_ratio(g * AUDIO_IN_FS_MV / AUDIO_OUT_FS_MV);
    console_printf(", at 0 ");
    print_mv3(in_code_to_uv(meas[0][i] - ((set.in_valid >> i & 1) ? set.in_zero[i] : 0)));
    console_printf(" V, others ");
    print_ratio(worst);
    if (worst > 0.01 || iabs32(bow) > in_mv_to_code(5)) {
      console_printf(", NOT used (%s)\r\n", worst > 0.01 ? "crosstalk" : "not linear");
      continue;
    }
    set.out_in[o] = (uint8_t) i;
    set.out_zero[o] = meas[0][i];
    set.out_loop[o] = to_q30(g);
    ok |= (uint8_t) (1u << o);
    console_printf("\r\n");
  }
  if (!ok) {
    console_printf("cal out: nothing measured\r\n");
    return;
  }
  set.out_valid |= ok;
  apply();
  if (set.in_valid != (1u << NI) - 1u) {
    console_printf("cal out: inputs without `cal in`: their offset is in the outputs' offsets\r\n");
  }
  console_printf(save() ? "cal out: saved\r\n" : "cal out: NOT saved, flash write failed\r\n");
}

static void finish_looptest(void) {
  release_outputs();
  run = RUN_IDLE;
  bool pass = true;
  int pairs = 0;
  int32_t const span = 2 * audio_mv_to_sample(LOOP_MV);
  console_printf("looptest (calibrated: OUT n at +-4.000 V, every IN read in volts):\r\n");
  for (int o = 0; o < NO; o++) {
    double g;
    int const i = follower(o, &g);
    console_printf("  OUT%d", o + 1);
    if (i < 0) {
      console_printf(" -> nothing\r\n");
      continue;
    }
    pairs++;
    double worst = 0;
    for (int k = 0; k < NI; k++) {
      if (k == i) continue;
      double const x = (double) (audio_in_sample(k, meas[1 + 2 * o][k]) - audio_in_sample(k, meas[2 + 2 * o][k])) / span;
      if ((x < 0 ? -x : x) > worst) worst = x < 0 ? -x : x;
    }
    // Calibrated readings (meas holds raw codes)
    int32_t const sp = audio_in_sample(i, meas[1 + 2 * o][i]), sm = audio_in_sample(i, meas[2 + 2 * o][i]);
    int32_t const s0 = audio_in_sample(i, meas[0][i]);
    double const gain = (double) (sp - sm) / span;
    int32_t const off_uv = (int32_t) (((int64_t) s0 * AUDIO_FS_MV * 1000) / AUDIO_FS_CODE);
    bool const cal = (set.out_valid >> o & 1) && set.out_in[o] == i;
    double const gtol = cal ? 0.002 : 0.05;
    int32_t const otol = cal ? 2000 : 100000;
    bool const ok = gain > 1 - gtol && gain < 1 + gtol && iabs32(off_uv) <= otol && worst < 0.001;
    if (!ok) pass = false;
    console_printf(" -> IN%d gain ", i + 1);
    print_ratio(gain);
    console_printf(", at 0 V ");
    print_mv3(off_uv);
    console_printf(" V, +4 V ");
    print_mv3((int32_t) (((int64_t) sp * AUDIO_FS_MV * 1000) / AUDIO_FS_CODE));
    console_printf(", -4 V ");
    print_mv3((int32_t) (((int64_t) sm * AUDIO_FS_MV * 1000) / AUDIO_FS_CODE));
    console_printf(", others ");
    print_ratio(worst);
    console_printf("%s%s\r\n", cal ? "" : " (not calibrated)", ok ? "" : "  <- FAIL");
  }
  console_printf(!pairs ? "looptest: no OUT is patched to an IN\r\n"
                 : pass ? "looptest: PASS (calibrated pairs: gain 1 +-0.002, 0 V +-2 mV; others < 0.001)\r\n"
                        : "looptest: FAIL\r\n");
}

void cal_task(void) {
  if (run == RUN_IDLE) return;
  uint32_t const now = board_millis();
  if ((int32_t) (now - at) < 0) return;
  audio_meter_t m;
  audio_take_meter(&m);
  if (audio_get_state() != AUDIO_RUNNING || (measuring && m.frames < AUDIO_RATE / 1000 * IN_WINDOW_MS / 2)) {
    release_outputs();
    run = RUN_IDLE;
    console_printf("cal: stopped, the audio restarted; nothing changed\r\n");
    return;
  }
  if (!measuring) {   // settled: measure from now
    measuring = true;
    at = now + (run == RUN_IN ? IN_WINDOW_MS : MEASURE_MS);
    return;
  }
  if (run == RUN_IN) {
    for (int i = 0; i < NI; i++) {
      win_mean[step][i] = m.in_mean[i];
      win_pp[step][i] = m.in_max[i] - m.in_min[i];
    }
    at = now + IN_WINDOW_MS;
    if (++step == IN_WINDOWS) finish_inputs();
    return;
  }
  for (int i = 0; i < NI; i++) meas[step][i] = m.in_mean[i];
  measuring = false;
  at = now + SETTLE_MS;
  if (++step < 1 + 2 * NO) {
    step_drive();
  } else if (run == RUN_OUT) {
    finish_outputs();
  } else {
    finish_looptest();
  }
}

bool cal_ref(int o, int32_t mv) {
  if (o < 1 || o > NO || audio_gen_mode(o - 1) != GEN_DC) {
    console_printf("cal ref: set the output with `dc <n> <volts>` first, measure it, then `cal ref <n> <volts measured>`\r\n");
    return false;
  }
  if (!(set.out_valid >> (o - 1) & 1)) {
    console_printf("cal ref: OUT%d has no `cal out` measurement yet\r\n", o);
    return false;
  }
  int32_t const want = audio_sample_to_mv(audio_gen_value(o - 1));
  if (iabs32(want) < 1000) {
    console_printf("cal ref: use a level of at least 1 V\r\n");
    return false;
  }
  double const r = from_q30(set.ref) * (double) mv / (double) want;
  if (r < 0.9 || r > 1.1) {
    console_printf("cal ref: %ld mV measured for %ld mV is more than 10 %% off, not used\r\n", (long) mv, (long) want);
    return false;
  }
  set.ref = to_q30(r);
  apply();
  bool const ok = save();
  console_printf(ok ? "cal ref: saved, every output and input scaled\r\n" : "cal ref: NOT saved, flash write failed\r\n");
  return ok;
}

//--------------------------------------------------------------------+
// Reports
//--------------------------------------------------------------------+

void cal_print_summary(void) {
  console_printf("Cal:   IN offsets %d of %d, OUT loops %d of %d, reference %s%s\r\n",
                 __builtin_popcount(set.in_valid), NI, __builtin_popcount(set.out_valid), NO,
                 set.ref != AUDIO_Q30 ? "from a meter (`cal ref`)" : "split evenly (no `cal ref`)",
                 saved_ok ? "" : ", NOT saved");
}

void cal_print(void) {
  double e_in[NI], e_out[NO];
  split(e_in, e_out);
  audio_coef_t k;
  audio_get_coef(&k);
  console_printf("calibration (full scale +-%d.%03d V in and out):\r\n", AUDIO_FS_MV / 1000, AUDIO_FS_MV % 1000);
  for (int i = 0; i < NI; i++) {
    console_printf("  IN%d   offset ", i + 1);
    print_mv3(in_code_to_uv(k.in_zero[i]));
    console_printf(" V%s, gain ", (set.in_valid >> i & 1) ? "" : " (no `cal in`)");
    print_ratio(e_in[i]);
    console_printf(" of nominal\r\n");
  }
  for (int o = 0; o < NO; o++) {
    console_printf("  OUT%d  ", o + 1);
    if (!(set.out_valid >> o & 1)) {
      console_printf("not measured (`cal out` with it patched to an IN)\r\n");
      continue;
    }
    // Offset at DAC code 0 (corrected now), in volts
    int32_t const v0 = audio_in_sample(set.out_in[o], set.out_zero[o]);
    console_printf("offset ");
    print_mv3((int32_t) (((int64_t) v0 * AUDIO_FS_MV * 1000) / AUDIO_FS_CODE));
    console_printf(" V, gain ");
    print_ratio(e_out[o]);
    console_printf(" of nominal, measured through IN%d, loop ", set.out_in[o] + 1);
    print_ratio(loop_of(o));
    console_printf("\r\n");
  }
  if (set.ref != AUDIO_Q30) {
    console_printf("  reference: outputs x");
    print_ratio(from_q30(set.ref));
    console_printf(" against the even split (`cal ref`)\r\n");
  }
}
