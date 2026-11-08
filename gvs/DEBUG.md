# Debug: tingle but no sway (2026-11-07)

The first on-head session ran 1.0–1.5 mA (`bench_log.md`). The skin sensation grew and turned into pain, but there was never any lean. This page compares my circuit against the published builds and lists checks in order, cheapest first.

## My circuit vs published GVS stimulators

| | Mine (`HANDOFF.md`) | Liu et al. 2025, HardwareX ([PMC12019011](https://pmc.ncbi.nlm.nih.gov/articles/PMC12019011/)) | Hobby builds ([xsimulator thread](https://www.xsimulator.net/community/threads/solid-state-motion-simulator-gvs.16213/)) |
|---|---|---|---|
| Topology | LM358 + 2N3904 sink, one direction; two relays swap which electrode is on top | Enhanced Howland current source, truly bipolar | Current limiter + H-bridge |
| Supply | DIY boost, measured 17–19 V under load at 1–2 mA | MT3608 boost; needs at least 20.4 V, run at 24.6 V | 2×9 V, later 24 V |
| In series with the head | 2.2 kΩ top + 1.1 kΩ sense = 3.3 kΩ | sense resistor only | varies |
| Current reading | voltage on the sink emitter: commanded current plus base current | INA219 sensor, true current | multimeter, with electrodes shorted |
| Electrodes | TENS pads with 2 mm sockets; on 2026-11-07 one had a wire pushed into its carbon layer | MSGST-37 ECG electrodes, NuPrep exfoliation | M8 washers, then TENS pads |
| Head + electrode resistance | not measured yet | 0.8–3 kΩ (their calibration loads: 1481, 2663, 3850 Ω) | — |
| Effect seen | tingle, then pain; no lean up to 1.5 mA | tilt perceived; just-noticeable difference 0.74 ± 0.38 mA | head "pulled like a magnet" at 2.5–4 mA; **only noticed standing, not seated** |

**How much head resistance the board can drive.** This is arithmetic from my measured supply, not a measurement on a head:

| Current | Supply under load | Largest head + electrode resistance that still gets the full current |
|---|---|---|
| 1.0 mA | 18.8 V | (18.8 − 0.2) / 1.0 mA − 3.3 kΩ = **15 kΩ** |
| 1.5 mA | 17.5 V | **8.2 kΩ** |
| 2.0 mA | 17.0 V | **5.1 kΩ** |

Good contact (0.8–5 kΩ) is inside all three. A damaged or dry pad is not, and then **the board still reports the commanded current**. When the head side can't take the current, the op-amp drives more base current into Q2, and the emitter, which is what the board measures, stays on target. So the board's reading never shows lost compliance.

## Likely causes, most likely first

1. **Electrode connection.** A bare wire in a 2 mm socket, or one poking into the carbon layer, touches only a few points. The current crowds into small spots, which gives pain at currents that should only tingle, and the head resistance goes up. Both match the session. *Fix:* fresh pads, 2 mm male pins, skin prep (Liu used NuPrep; alcohol at minimum). Saline sponge or conductive-foam electrodes "greatly improved" tingling in [Powell's driving-sim build](https://willpowell.uk/files/Enhancing_the_Realism_of_Driving_Simulators_using_Galvanic_Vestibular_Stimulation_Motion_Cueing.pdf).
2. **Less current is reaching you than the board says** (lost compliance; see above). *Check:* the meter test in the next section.
3. **Posture.** The thresholds in the literature are mostly measured **standing with feet together and eyes closed**: [Trier 2026](https://pmc.ncbi.nlm.nih.gov/articles/PMC12975849/), and Liu's tilt task. The xsimulator builder felt the pull standing up but not seated in his rig. Sitting with back support hides most of the sway. *Fix:* see the protocol section.
4. **Placement:** pads off the mastoid bone, too low on the neck, or bridged by gel. *Fix:* `pictures/electrode_placement.png`.
4b. **Electrode size.**
   - Truong et al. 2024, a simulation of GVS current flow ([PLOS ONE 19:e0309007](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0309007)), reports that **smaller electrodes (3 cm²) deliver a higher electric field to the vestibular regions than large ones (35 cm²)**, because less current is lost across the scalp. They also find that only about 15–40% of the injected current enters the skull at all, depending on placement.
   - The trade-off is current density at the skin: 2 mA over 3 cm² is 0.67 mA/cm², more sting, but still under the LOTES-2023 2 mA/cm² limit (`../research/gvs.md`).
   - *Fix:* electrodes about 2–2.5 cm across (3–5 cm²), round, centred on the mastoid, with gel or saline, and both sides the same size.
5. **A high threshold.** Liu reports 0.74 ± 0.38 mA; Nguyen 2022 (in `research/gvs.md`) reports 0.98 ± 0.29 mA seated. Possible, but only worth concluding after 1–4 are ruled out.

## Meter-only checks (no soldering)

| # | Check | Setup | Pass |
|---|---|---|---|
| A | Pads and wires | Fresh pads stuck gel to gel; meter on Ω between the two electrode wires; wiggle each pin | under about 1 kΩ, and steady when wiggled |
| B | Head + electrode resistance | Pads on; meter DC V across the two pad wires during a 1.0 mA, 3 s DC pulse | 1–5 V (= 1–5 kΩ). Above 10 V means poor contact. |
| C | **True current, independent of the board's reading** | Meter DC V across the **2.2 kΩ top resistor**: middle section, standing between col 4 row B (HV) and col 2 row B (TOP, bridged to B1/C1). Red on the col 4 leg, black on the col 2 leg, during the same 1.0 mA pulse | 2.2 V (= 1.0 mA). Lower means the board is overstating the current. |
| D | Supply headroom | Meter on HV (col 4) to GND during the pulse | stays above head volts + 3.3 V × mA + 0.2 V |

C is the measurement the board itself can't make. If C reads low while the board says 1.0 mA, cause 2 is confirmed.

## Session protocol changes

- **Standing**, feet together, eyes closed, **with a spotter** behind you and a bed or wall within reach. This is how the threshold studies are run. Keep pulses short: 3 s DC at most.
- If standing isn't possible: seated on a stool with no back, feet off the floor, arms straight out in front. Watch for arm or torso drift, not just "feeling" it.
- Restart at 0.5 mA after any change of electrodes, then step up 0.25 mA. Pain, burning, flashes of light or a headache still end the session.

## Hardware changes worth making

1. **A true load-current reading.** Add a divider from TOP to a free ADC1 pin, so firmware can compute (HV − V_TOP) / 2.2 kΩ, or one from BOTTOM, to see Q2 saturating. Firmware could then fault on "compliance lost" and on open electrodes, which today read as normal.
   - The only free ADC1 pin is **D0 = GPIO2, which is an ESP32-C3 boot strapping pin**. Check its required level at reset in the C3 datasheet before adding a divider to ground there. Not verified here.
   - Alternative: an INA219 on I2C, as Liu did. But D4/D5, the default I2C pins, already drive the relays.
2. **More headroom**, only if B shows you need it. Lowering the 2.2 kΩ top resistor raises the resistance the board can drive. It also raises the fault current if Q2 shorts: 24 V / (R_top + 1.1 kΩ) is 7.3 mA today and would be 11 mA with 1 kΩ. Keep the 2.2 kΩ unless B reads above about 8 V at 1.5 mA.
3. The boost tops out at about 21–23 V open and 17 V at 2 mA, because `BOOST_MAX_PCT` is 45%. Raising that cap is a separate firmware and heat decision. Don't change it until A–D are done.

## Not verified

- Checks A–D haven't been run on a head.
- The GPIO2 strapping constraint is from memory, not the datasheet.
- The resistance limits in the first section are calculated, not measured.
