// Compiled safety ceilings and pure helpers. Config can only tighten these.
#pragma once
#include <stdint.h>

static const uint32_t PWM_FREQ_HZ = 20000;
static const uint8_t  PWM_BITS = 10;
static const uint32_t PWM_MAX_COUNTS = 1023;

static const float    MAX_DUTY_CEILING = 0.6f;   // compiled; config may only lower
static const float    DEFAULT_MAX_DUTY = 0.4f;
static const uint32_t MIN_MS = 50, MAX_MS = 2000;
static const uint32_t RAMP_MS = 200;
static const uint32_t COOLDOWN_MS = 5000;
static const int      MAX_STIMS_PER_HOUR = 30;
static const uint32_t HOUR_MS = 3600000UL;
static const uint32_t ARM_TIMEOUT_MS = 600000UL;

static inline float clampIntensity(float x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }
static inline uint32_t clampMs(long v) {
  return v < (long)MIN_MS ? MIN_MS : (v > (long)MAX_MS ? MAX_MS : (uint32_t)v);
}
static inline uint32_t dutyCounts(float intensity, float maxDuty) {
  if (maxDuty > MAX_DUTY_CEILING) maxDuty = MAX_DUTY_CEILING;
  return (uint32_t)(intensity * maxDuty * PWM_MAX_COUNTS + 0.5f);
}
// Trapezoid: linear ramp up and down of RAMP_MS inside the duration
// (shortened to dur/2 when dur < 2*RAMP_MS so the peak is never exceeded).
static inline uint32_t rampDuty(uint32_t t, uint32_t dur, uint32_t peak) {
  uint32_t r = RAMP_MS; if (r > dur / 2) r = dur / 2;
  if (r == 0) return peak;
  uint32_t edge = t < dur - t ? t : dur - t;
  if (edge >= r) return peak;
  return (uint32_t)((uint64_t)peak * edge / r);
}
