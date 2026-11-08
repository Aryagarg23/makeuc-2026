# Bench log

Each run uses a 2.2 kΩ dummy load across the electrode leads, with nobody attached. Pulses are driven over USB serial by `tools/bench.py`. The board's reading is the firmware's own current readback; the meter reading is DC volts across the 2.2k, so true mA = V / 2.2.

## 2026-11-07

**Power.** With the battery feed wire on S1 col 19, the HV rail reads 3.85–3.89 V at idle on the board's own voltage reading.

**Boost sweep, open leads.** HV at each duty setting, on the board's own reading:

| Duty | 5% | 10% | 15% | 20% | 25% | 30% | 35% | 40% | 45% |
|---|---|---|---|---|---|---|---|---|---|
| HV (V) | 5.9 | 7.9 | 10.0 | 12.1 | 14.1 | 16.0 | 17.7 | 19.4 | 21.1 |

- 45% is the firmware ceiling (`BOOST_MAX_PCT`) and is now `BOOST_PCT`.
- During 3 s pulses with the leads open, HV peaked at 23–26.5 V. The cutoff is 28 V.
- Once the boost stops, HV bleeds back to about 3.9 V within about 1 s.

**Relays, open leads, 0.5 Hz sine.** The relay state went -1 → 0 → 1 → (-1) → 0 → -1: it alternated, and passed through released at each flip.

**Current into 2.2k, DC, 3 s:**

| Commanded | Meter | True current | Board's reading, before calibration | HV during pulse |
|---|---|---|---|---|
| 0.5 mA | 1.07 V | 0.486 mA | 0.69–0.72 | 21 V |
| 1.0 mA | 2.2 V | 1.00 mA | 1.13–1.14 | 19.5 V |
| 2.0 mA | 4.308 V | 1.958 mA | 1.92–2.03 | 17.0 V |

- With 0 mA commanded, the board read 0.25–0.28 mA, though no current was flowing. Taken together with the rows above, the uncorrected board reading follows **raw = 0.27 + 0.88 × true** in mA, so the error was in the measurement, not the output.
- The firmware now reports `meas_ma` with that correction. The overcurrent trip (2.3 mA) still uses the uncorrected reading, which runs at or above the true current up to about 2.25 mA.
- The meter reading at 0 mA commanded was not recorded.
