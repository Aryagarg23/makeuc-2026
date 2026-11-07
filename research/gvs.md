# GVS: what the literature says, and what to change before it touches a head

Written 2026-11-07 for the makeuc-2026 rig (ESP32-C3 command controller in `esp32/gvs_controller`, analog front end not yet described). Companion to `research/conditioning.md`, which covers the learning side.

Tags: **[S]** = the number or claim is in the cited source (I read the abstract or the passage; where I only saw a summary, it says so). **[I]** = my inference, arithmetic or engineering choice. I did not invent any citation; where I could not find a source for a number, the text says so.

## Summary

1. **A 0.5 to 2 s pulse will not make you nauseous.** Every study that produced GVS nausea ran low-frequency stimulation for minutes: ±2 mA sinusoids at 0.08 to 0.18 Hz for about 9 to 21 min gave nausea in 33 to 58% of people [S: Klingberg 2015; Javaid 2019; McCarthy 2023]. Bouts of about 30 s did not [S: McCarthy 2026]. A brief pulse gives a tilt, sway or spin sensation that starts within about 1 to 2 s, plus skin tingling. Both stop within seconds of the current ending [S: Fitzpatrick & Day 2004; Marchand 2025; Nguyen 2022]. That is the stimulus you actually have. It is a disorienting jolt, not nausea.
2. **Nausea also could not be paired with a content event if you got it.** It takes minutes to build. Subjective recovery takes 15 to 30 min, and sensitivity stays raised for at least 2 h [S: Golding & Stott 1997]. Nausea is therefore a session-level state, not a cue you can attach to a single event.
3. **Recommended event stimulus [I, built on S]:** a zero-mean sine burst across the mastoids (binaural bipolar), 1 Hz, 2 full cycles (2.0 s), with a 250 ms cosine taper at each end. Start at 0.5 mA peak and titrate up in 0.25 mA steps. Peak current is software-capped at 2.0 mA for the first sessions, and a hardware fault ceiling of 5 mA or less holds even if the firmware fails.
4. **The current firmware cannot produce that safely as-is.** It drives a single unipolar 0 to 3.3 V command. If your front end treats mid-scale as 0 mA, which is how the published open-source GVS current source works (Liu 2025), then the firmware's "off" state (duty 0) commands **full negative current**. If the front end treats 0 V as 0 mA, you can only make one-polarity DC. Both cases need the change in the "Firmware change spec" section: two PWM channels feeding a differential input, plus a hardware enable.
5. **Hard rules:** battery power only for everything galvanically connected to the electrodes. That includes the ESP32, so no USB to a charging Mac while electrodes are on. Use a voltage-to-current converter, not a voltage source. Put a series current limit in hardware. Both electrodes go on the head (mastoids). Sit down with back support, have a second person present, use intact skin with gel, and do a bench test on a dummy load before any on-head use [S: LOTES-2023; Liu 2025; Kollmansperger 2024].

---

## 1. Electrodes, placement, skin prep, impedance

**Placement.**
- Binaural bipolar: anode on one mastoid process, cathode on the other. This is the standard montage and gives roll-plane (side-to-side) tilt/sway toward the anode [S: Fitzpatrick & Day 2004, https://doi.org/10.1152/japplphysiol.00008.2004; Marchand 2025 review, https://doi.org/10.1007/s00221-025-07079-8].
- Monaural montages put one mastoid electrode with a return on C7, the forehead, the vertex or the forearm. Their lateral component is about half as large [S: Marchand 2025]. Copolar montages with a distal forehead or shoulder electrode give pitch sensations, but with "substantial side effects, particularly for skin tingling" [S: Austin, Willett & Clark 2026, https://doi.org/10.1007/s00221-026-07255-4].
- Use binaural bipolar. It gives the strongest motion sensation per mA [S: Austin 2026, "Motion sensations were the most prevalent and intense with Binaural"], keeps both electrodes on the head, and keeps current away from the chest [I].

**Electrode type and size** (what published GVS work actually used):
- 35 mm adhesive hydrogel Ag/AgCl electrodes on the mastoids, extra conductive cream underneath, held with an elastic headband or gauze. This was the sGVS nausea protocol [S: McCarthy 2023, https://doi.org/10.1007/s00221-023-06722-6].
- 50 mm square Ag/AgCl electrodes, gauze-wrapped [S: McCarthy 2026, https://doi.org/10.1007/s00221-026-07411-w].
- MSGST-37 ECG electrodes after NuPrep exfoliation [S: Liu 2025, https://doi.org/10.1016/j.ohx.2025.e00647].
- 35 cm² (5 × 7 cm) conductive rubber with gel, giving 57.14 µA/cm² at 2 mA [S: Nguyen, Kang & Oh 2022, https://doi.org/10.3389/fneur.2022.955088].
- 40 × 60 mm conductive rubber with gel and a headband [S: Kollmansperger 2024, https://doi.org/10.3389/fneur.2024.1502204].

The practical choice is 35 to 50 mm hydrogel Ag/AgCl ECG electrodes, which are cheap and match the nausea and HCI studies. Fresh electrodes every session [I].

**Skin prep and gel.** Clean with alcohol, exfoliate lightly (NuPrep), wipe the residue off, then apply the electrode with gel [S: Liu 2025; Austin 2026 used alcohol swabs plus NuPrep]. Liu notes prep "helps reduce the impedance of the skin and minimizes the sensation of tingling" [S]. Use only intact, healthy skin, never over a rash, cut or irritation [S: LOTES-2023 warnings, https://doi.org/10.1016/j.brs.2023.05.008]. Hair under the electrode raises impedance, so place it on the bare mastoid skin behind the ear [I].

**Electrode plus skin impedance (mastoid to mastoid):**
- "around 0.8 kΩ to 3 kΩ" (offset-calibration guidance). The open-source module was designed for 0 to 5 kΩ and tested on 1481, 2663 and 3850 Ω dummy loads [S: Liu 2025].
- Below 10 kΩ for all participants [S: Allred, Gopinath & Clark 2025, https://doi.org/10.1038/s44172-025-00417-2].
- Below 12 kΩ between all pairs, accepted as the pass criterion [S: Austin 2026].
- Impedance falls during the first part of DC stimulation [S: Liu 2025, citing tDCS work].

Design for 0.5 to 10 kΩ. Expect 1 to 5 kΩ after prep. Refuse to stimulate above 10 kΩ [I].

## 2. Currents: thresholds, effects, maximums, waveform type

**Where each effect appears (healthy adults):**
- Motion perception (dizziness, spinning, fall tendency) from DC, seated: **0.98 ± 0.29 mA**. Females 0.75 mA, males 1.0 mA (medians) [S: Nguyen 2022, 25 subjects, 3 s DC steps].
- Skin tingling (cutaneous threshold): **0.9 ± 0.29 mA**, mostly at the cathode [S: Nguyen 2022].
- Nystagmus (oculomotor threshold): **1.61 ± 0.35 mA** [S: Nguyen 2022].
- Tilt-direction discrimination with 2 s raised-sine DC pulses: **0.74 ± 0.38 mA** (range tested 0.2 to 1.8 mA) [S: Liu 2025, n = 12].
- Sinusoidal sway sensitivity: thresholds were mapped with 0.1 to 0.7 mA sines while standing [S: Trier 2026, https://doi.org/10.1007/s00221-026-07250-9]. Subjects could tell amplitude steps of a median 0.03 mA around ±0.6 mA [S: Temple 2024, https://doi.org/10.1007/s00221-024-06908-6].
- The "commonly used" experimental level is about 1 mA, and "when the small current flows for 1 or 2 s, it causes a person to sway if they are standing or perceive illusory movements if they are not" [S: Fitzpatrick & Day 2004].
- Postural time course: the body leans toward the anode, stabilises within 1 to 2 s, and returns after the current stops [S: Marchand 2025]. In Nguyen 2022, rotation and falling sensations "persisted for several seconds even after cessation of the stimulation" [S].
- Response scales sublinearly with current (power law, exponent 0.55), so doubling the current gives about 73% more response, not 100% [S: Marchand 2025 citing Day et al. 2010].
- Nausea: see section 3. It is about duration, not amplitude. Nausea was not observed at 0.6 mA or 1.5 mA across 255 sessions [S: Utz 2011, https://doi.org/10.3109/02699052.2011.607789].
- Skin effects scale with current. Across 0.5 to 4 mA (12 s, 0.5 Hz sine), tingling severity rose with current. Metallic taste and visual flashes appeared in some subjects, more at 3 mA and above with forehead/temple montages [S: Austin 2026]. Metallic taste was also reported during ±2 mA sGVS [S: McCarthy 2026]. The sGVS nausea studies report an "initial burning or tingling sensation" that "would usually abate within approximately two minutes" [S: McCarthy 2023].
- Pain: I found no source giving a mastoid pain threshold in mA. Austin 2026 had 3 subjects report severe tingling somewhere in 0.5 to 4 mA. Treat "moderate and rising" tingling as the stop signal (section 7).

**Maximums used and safety limits:**
- GVS studies have used up to 5 mA (Watson 1998, MacDougall 2002) and up to 7 mA (Zink 1998). The review calls such levels possibly "unnecessary" [S: Marchand 2025].
- Pseudorandom GVS at 3.5 or 5 mA peak was used for 10.5 min intermittent and 20 min continuous [S: Dilda 2011, https://doi.org/10.3357/asem.3051.2011].
- One study capped waveforms at 5 mA "to produce current waveforms that would be tolerated" [S: Allred 2025]. Another ran a 0.5 to 4 mA ladder [S: Austin 2026].
- tDCS evidence base: "≤40 min, ≤4 milliamperes, ≤7.2 Coulombs" across more than 33,200 sessions with no serious adverse effect or irreversible injury. Animal brain injury needed current densities more than 10× conventional tDCS (6.3 to 13 A/m²) [S: Bikson 2016, https://doi.org/10.1016/j.brs.2016.06.004, abstract]. Liu 2025 adopts ±4 mA from the Antal et al. tES guidelines [S].
- Limited-output device standard (LOTES-2023) [S: https://doi.org/10.1016/j.brs.2023.05.008]:
  - for DC or sustained current over 1 s, the limited-output scope requires average current ≤ 4 mA (absolute); meeting that waives the per-phase charge and phase-duration limits
  - peak ≤ 30 mA
  - ≤ 2 mA/cm² of electrolyte-skin contact area
  - ≤ 60 min per session
  - ≤ 6000 mC per session
  - ≤ 100 µA DC when inactive or failed
  - battery only, isolated from earth ground, not usable while charging
  - must not become unsafe with open- or short-circuited electrodes
  - any equipment physically connected to it (for example a USB host) counts as part of the device
- Current density examples: 2 mA over the 35 cm² rubber pad is 0.057 mA/cm² [S: Nguyen 2022]. Over a hydrogel contact of about 7 cm² (a guess for a 35 to 40 mm ECG electrode; I found no measured gel area) it is about 0.29 mA/cm². Both are under the 2 mA/cm² LOTES limit [I, arithmetic].

**DC vs AC vs noisy, for safety:**
- DC and low-frequency sine are both used safely at 1 to 2 mA in the literature above [S].
- The differences are electrochemical and in sensation:
  - Net DC drives irreversible electrode reactions, and charge-balanced waveforms reverse them [S: general principle in Merrill, Bikson & Jefferys 2005, https://doi.org/10.1016/j.jneumeth.2004.10.020].
  - The mobile nGVS stimulator "employs AC coupling to prevent the application of DC currents, eliminating the possibility of charge accumulation" [S: Kollmansperger 2024].
  - tDCS skin burns are documented as case reports (for example Palm & Feichtner 2020, https://pubmed.ncbi.nlm.nih.gov/32364552/; Frank 2010 anodal lesions, https://doi.org/10.1016/j.brs.2009.04.002; Lu & Lam 2019 cathodal lesions, https://doi.org/10.1111/ner.12892) [S: titles only, not read].
- Noisy GVS (±1 mA, 0.5 to 30 Hz) is usually subthreshold and is the gentlest. It is used therapeutically and to reduce cybersickness (±1.75 mA) [S: Kollmansperger 2024; Weech 2020, https://doi.org/10.1007/s00221-019-05718-5]. It is the wrong tool for an aversive jolt [I].
- Choose integer-cycle sine bursts: zero net charge per event, and abrupt onsets avoided [I].

## 3. Which waveform makes nausea, how fast, and how long it lasts

**What produced nausea:**

| Protocol | Nausea | Source |
|---|---|---|
| Bipolar binaural sine ±2 mA, 100 cycles at 0.08, 0.13 or 0.18 Hz (≈21, 13, 9 min), seated | 21 of 36 (58%). "At low frequencies of sGVS (≤0.2 Hz), some subjects report nausea" | [S: Klingberg 2015, https://doi.org/10.1007/s00221-015-4313-x] |
| ±2 mA, 0.08 Hz, 21 min | 10 of 30 (33%) | [S: Javaid 2019, https://doi.org/10.1113/EP087385] |
| ±2 mA, 0.08 Hz, 100 cycles (~21 min), semi-recumbent | 7/20 and 6/13 (35%, 46%), ratings 2 to 10 on 0 to 10. One subject vomited about 10 min in | [S: McCarthy 2023] |
| Same, supine in MRI, head fixed | 2/17 nauseous (5/10), 2 more "on the brink". Authors note ~30 s bouts in prior imaging "did not induce nausea" | [S: McCarthy 2026] |
| Pseudorandom bipolar, 3.5 or 5 mA, 10.5 min intermittent | 78.3% none or mild, 13.3% moderate, 8.3% severe (stopped) | [S: Dilda 2011] |
| Same, 20 min continuous | 16.7% severe, all in the 5 mA group | [S: Dilda 2011] |
| 1 mA, 38 min | no significant motion sickness. Low-level sickness only after 76 min | [S: Pasquier 2019, https://doi.org/10.3389/fnsys.2019.00014] |
| 0.6 and 1.5 mA sessions (255 sessions) | "neither seizures nor vertigo or nausea were observed" | [S: Utz 2011] |

- Low-frequency sines (0.2 to 2 Hz, ±2 mA) produced "strong postural illusions of 'rocking in a boat' or 'swaying in a hammock'" in all subjects [S: James 2010, https://doi.org/10.1007/s00221-009-2131-8].
- Nausea did not track how strong the sway felt [S: McCarthy 2023, "the occurrence and the amount of nausea ... did not correlate with the participants' perceived sway"].

**Onset latency.** The only per-subject time I found is the vomiting at about 10 min into ±2 mA, 0.08 Hz sGVS [S: McCarthy 2023]. Every nausea-positive protocol ran at least about 9 min of continuous stimulation [S, table]. I found no paper reporting a median time-to-nausea for GVS.

**Can a 0.5 to 2 s DC pulse produce nausea?**
- No study supports it. The shortest bouts with reported nausea outcomes were about 30 s and produced none [S: McCarthy 2026].
- One 0.08 Hz sGVS cycle lasts 12.5 s, so a 2 s pulse is under a fifth of one cycle of the nauseogenic stimulus [I, arithmetic].
- The sourced sensation from 1 to 2 s is sway or illusory motion [S: Fitzpatrick & Day 2004], with after-sensations lasting several seconds [S: Nguyen 2022].
- Quantified as well as the literature allows [I]:
  - nausea-producing exposure ≈ 9 to 21 min continuous at ±2 mA
  - your proposed 30 stims/hour × 2 s = 60 s/hour, intermittent, at ≤2 mA
  - that is 9 to 21 times less exposure even before counting the 5 s gaps and habituation

**How long nausea lasts once induced.** Data come from motion sickness in general, not GVS specifically. After a provocative motion challenge, most people reported subjective recovery by 15 to 30 min. Objective sensitisation to further motion lasted at least 2 h [S: Golding & Stott 1997, https://doi.org/10.3233/ves-1997-7601]. In sGVS, one subject reported "a lingering sense of nausea" through later stimulation blocks separated by 4 min rests [S: McCarthy 2023].

**What this means for the rig [I]:**
- The per-event stimulus is a vestibular jolt (tilt or rocking) plus tingling. That is what gets paired with content.
- If nausea did develop, it would build over many minutes, outlast the content by 15 to 30 min, and attach to the whole session rather than to an event. This matches the "weak, short US" concern in `research/conditioning.md`.
- The one human result where motion-sickness nausea conditioned after a single pairing used a novel taste as the cue [S: Klosterhalfen 2000, https://doi.org/10.1097/00006842-200009000-00011].
- **Habituation:** sway responses habituate within a session [S: Balter 2004, https://doi.org/10.1080/00016480310015245]. Sway illusions dissipated over 21 min of sGVS in 11 of 20 subjects [S: McCarthy 2023]. GVS-induced postural impairment recovered over 70 to 80 min of cumulative exposure across weeks [S: Dilda 2014, https://doi.org/10.1371/journal.pone.0112131]. Expect the jolt to weaken with repeated pairings.

## 4. Safety

**Contraindications and exclusions.** GVS papers exclude people with:
- vestibular or neurological disorders, recent neck, back or lower-body injury, or alcohol or balance-affecting drugs in the prior 24 h [S: Trier 2026]
- psychiatric disorders [S: Pasquier 2019]
- MRI contraindications, for the imaging work [S: McCarthy 2026]

LOTES-2023 warnings [S]:
- consult a physician if under active care or with a pre-existing neurological or neuropsychiatric condition
- only intact, clean, healthy skin, never over wounds, rash or inflamed skin
- not while intoxicated
- consult your perinatal team if pregnant

LOTES-2023 also argues that blanket exclusions for implants, epilepsy and pregnancy are precedent rather than evidence of risk [S]. A small series found no tDCS interference with pacemakers [S: Roncero 2020, https://doi.org/10.1016/j.brs.2019.08.010, abstract].

Rule for a self-experimenter without supervision or medical screening [I]: do not use it if any of these apply:
- epilepsy, seizure history or unexplained fainting
- a pacemaker, ICD or any implanted electronic device, or metal in the head
- a heart condition
- migraine, especially vestibular migraine (no GVS source found; included because motion-sickness provocation is a known trigger concern, an inference)
- any vestibular disorder (Ménière's, BPPV, vestibular neuritis)
- pregnancy
- skin lesions at the mastoids
- strong motion-sickness susceptibility
- a recent concussion

**Current density and charge.** Keep ≤ 2 mA/cm² [S: LOTES]. At ≤ 2 mA through 35 to 50 mm electrodes you are about 0.1 to 0.3 mA/cm² [I]. Absolute charge at 30 bursts/hour × 2 s × 2 mA peak (mean |I| of a sine = 2/π × peak ≈ 1.27 mA) is about 75 mC per hour, far under 6000 mC per session [I, arithmetic; limit S: LOTES]. Burns in tDCS come from poor contact (dried sponge, small effective area, damaged skin) rather than from total charge [I; the case reports above are titles I did not open]. That is why the stop rule includes rising sensation, which LOTES-2023 also uses: "if you experience significantly increasing levels of discomfort, stop" [S].

**Battery power and isolation [S: LOTES-2023]:**
- Run on battery only, isolated from earth ground, never stimulating while connected to a charger.
- Anything physically connected counts as part of the device. For this rig that means the ESP32 USB cable to a Mac on its charger is a mains-referenced path into the electrode circuit.
- Plan [I]:
  - (a) the ESP32 and front end on their own battery, controlled over WiFi
  - or (b) a USB isolator, with the laptop also unplugged from mains
  - (a) is better. Note that the firmware's HTTP endpoint currently has no authentication (README).

**Current limiting in hardware.** Use a current source, not a voltage source, so current stays set as impedance changes [S: Liu 2025]. The firmware is a "software safety layer ... not a substitute for hardware current limiting" (esp32/README.md). Layers are specified in section 5.

**Never across the chest.**
- LOTES-2023 notes that "across the chest" warnings are ambiguous and that extracephalic montages have been used. It still lets manufacturers direct users to avoid chest paths, and requires a risk analysis for any electrode below the neck [S].
- For this build, both electrodes go on the mastoids. No return electrode on an arm, hand or shoulder, and no lead routing that could put one on the body [I].

**Supervision and posture:**
- Every sourced protocol had subjects seated or semi-recumbent [S: Nguyen 2022 seated; Liu 2025 seated; McCarthy 2023 semi-recumbent].
- Standing GVS produces real sway [S: Fitzpatrick & Day 2004]. Pseudorandom GVS raised crash landings from 2.3% to 9% in a Shuttle landing simulator [S: Moore 2011, https://doi.org/10.3357/asem.2942.2011].
- Rules [I]:
  - sit in a chair with back and arm support
  - a second person within reach of the E-stop
  - no standing for 2 to 5 min after the last stim
  - no driving, cycling or ladders that session
  - stop for the day on any nausea (motion-sickness sensitisation lasts at least 2 h [S: Golding & Stott 1997])

## 5. Circuit: microcontroller to bipolar constant current

**ESP32-C3 has no DAC.** The datasheet lists an LED PWM controller (up to 6 channels) and two 12-bit SAR ADCs, with no DAC in the peripheral list [S: Espressif ESP32-C3 datasheet, https://documentation.espressif.com/api/resource/doc/file/aYwvqd1B/FILE/esp32-c3_datasheet_en.pdf; "no DAC" is my reading of the peripheral list, I]. The PWM-plus-RC-filter approach is therefore correct, and the filter sets the effective DAC bandwidth [S: TI SPRAA88, "Using PWM Output as a Digital-to-Analog Converter", https://www.ti.com/lit/SPRAA88].

**Reference designs:**
- **Liu et al. 2025, HardwareX**: an open-source enhanced Howland current source (EHCS) for GVS.
  - Parts: LT1013 op-amps, single 3.7 V Li-ion cell boosted to 24.6 V (MT3608), ISL60002 reference, current set by (V_DAC − V_ref).
  - Output range: linear ±4 mA. Load design range 0 to 5 kΩ.
  - Compliance arithmetic: 4 mA × 5 kΩ = 20 V, + 0.4 V sense, + more than 3 V op-amp headroom, so 20.4 V minimum and 24.6 V chosen.
  - Measured error: 0.41 to 4.70%, with a 0.04 mA offset trimmed in software.
  - Monitoring: INA219 current monitor for a programmable over-current cutoff.
  - Resistors: below 1% tolerance needed, because Howland accuracy depends on matching.
  - Files: https://github.com/DigitalNatureGroup/Howland-VCCS-for-GVS-experiment-prototype, https://doi.org/10.5281/zenodo.14545604 (CERN-OHL-W).
  - [S: https://doi.org/10.1016/j.ohx.2025.e00647]
  - Key detail for you: V_ref is set at half the DAC range, so **mid-scale input = 0 mA** [S].
- **Chen, Kuo & Blouin 2022**: an Arduino (Simulink) controller at about 200 Hz driving a separate isolated current stimulator over a ±10 V command [S: https://doi.org/10.1016/j.jneumeth.2022.109709, abstract]. This is the "MCU + commercial isolated stimulator" pattern. The sGVS nausea work used a WPI Linear Stimulus Isolator driven by PowerLab [S: McCarthy 2023]. Nguyen 2022 used a battery-driven neuroConn DC-Stimulator Plus [S].
- **Kollmansperger 2024** (mobile nGVS, built with neuroConn) [S]:
  - firmware-limited ±17 V plus Zener hardware clamp at ±18 V
  - output power limited by restricted DC/DC pulse width
  - AC coupling
  - a relay that diverts unwanted current outside stimulation
  - under-voltage battery cutoff
  - 2 s fade in and out
  - 30 min maximum continuous stimulation
- **milovanpms/gvs (GitHub)**: improved Howland plus a push-pull output stage, "hardware-limited to 5mA", RC fade filter, ±9 V rails. Its own badge says untested, and the limiter mechanism is not described in the README [S: https://github.com/milovanpms/gvs, README only]. Use it as an idea source, not as a validated design.

**Compliance voltage [I, arithmetic].** V_needed = I_peak × (R_head + R_series + R_sense) + op-amp headroom. At 2 mA with a 5 kΩ head, a 2.2 kΩ series limiter and a 100 Ω sense resistor: 2 mA × 7.3 kΩ = 14.6 V, plus about 3 V headroom, so about 18 V across the load path. A Liu-style 24 V single-supply bridge (load between two driven outputs) or ±12 V rails both cover this. At 10 kΩ the same 2 mA needs about 27 V and will clip, which is safe (less current) but distorts the waveform. Hence the 10 kΩ refuse rule.

**Hardware current limit independent of firmware [I unless tagged]:**
1. **Series resistor (required).** Size it so a fault with the output stuck at the rail, driving into a short, cannot exceed 5 mA: R_s ≥ V_swing / 5 mA. With ±12 V rails (about ±10.5 V swing) that is ≥ 2.1 kΩ, so use 2.2 kΩ. With a 24 V bridge (about ±21 V across the load) it is ≥ 4.2 kΩ, so use 4.7 kΩ and recheck compliance. Put it inside the Howland feedback loop's load path so it costs compliance but not accuracy. The 5 mA ceiling matches the highest GVS levels routinely tolerated [S: Allred 2025 cap; Dilda 2011] and sits above LOTES's 4 mA average [S].
2. **Low supply voltage.** Total available voltage divided by minimum path resistance bounds the current whatever the firmware does. Do not use a 48 V or larger boost [I].
3. **Current-regulating diodes, optional second layer.** A 1N5314 regulates at 4.70 mA nominal (4.23 to 5.17 mA), 100 V peak operating voltage, ≤ 2.9 V limiting voltage [S: distributor listing of the Central Semiconductor 1N5283–1N5314 datasheet, https://my.centralsemi.com/datasheets/1N5283-5314.PDF; values not checked against the original PDF]. A CRD regulates in one direction only, so a bipolar output needs two in anti-series. Their reverse-direction behaviour is not something I verified: bench-test the short-circuit current in both polarities (section 7) before trusting it.
4. **Polyfuse: no.** The smallest common PTC (Bourns MF-R005) holds 50 mA and trips at 100 mA [S: https://www.digikey.ca/en/products/detail/bourns-inc/MF-R005-0/1232764]. That is 10 to 20 times above anything you should allow through a head, so it protects the battery, not you [I].
5. **Output disconnect + E-stop in hardware.** Use a normally-open relay or solid-state (PhotoMOS) switch in series with one electrode lead. Its drive passes through a normally-closed mushroom E-stop, so pressing the button opens the electrode circuit even if the MCU hangs. This is the same idea as Kollmansperger's diversion relay [S] and LOTES's "no unsafe state with open/short" requirement [S]. Use a silent solid-state switch so a relay click cannot become an auditory cue that predicts the stim [I].
6. **Current monitor.** Put a sense resistor in the load path and read it with an ADC (the ESP32-C3 has one) or an INA219-style chip, and abort on mismatch [S: Liu 2025 used an INA219 for a user-set cutoff].

**Filtering the 20 kHz PWM [I, arithmetic; principle S: TI SPRAA88].**
- First-order RC ripple ≈ V × D(1−D) × T_pwm / τ, worst case at D = 0.5. With 3.3 V, T = 50 µs and τ = RC = 10 ms (10 kΩ, 1 µF; f_c = 16 Hz): ripple ≈ 4.1 mV p-p, which is 0.12% of full scale.
- A second identical RC stage, buffered, cuts the 20 kHz residue by about 2π × 20 kHz × 10 ms ≈ 1250× more.
- Effect on a 1 Hz sine: about 7° total phase lag and under 0.5% amplitude loss across two poles.
- Step settling: about 50 to 70 ms. That is shorter than the 250 ms taper, so the edges stay smooth.
- Spec: two buffered RC poles of 10 kΩ / 1 µF on each PWM line, then the Howland differential input.
- The PWM high level is the 3.3 V rail, so current scales with rail noise and drift. Calibrate the mA-per-duty factor on the bench (section 7).

**Bipolar from a unipolar MCU [I].** There are three options:
- (a) **Two PWM channels into the Howland's differential input**, I_L = (V+ − V−)/(k·R0) [S: Liu 2025 eq. 6]. Positive half-cycles go on PWM-A, negative on PWM-B. Both at 0 means 0 mA, and with pull-downs both float to 0 during reset.
- (b) One PWM at mid-scale offset. Rejected, because duty 0 (the firmware's off and reset state) means full negative current.
- (c) A unipolar magnitude plus an H-bridge or relay for polarity. Rejected, because of the switching transients and a second failure mode.

Use (a). Scale so that 100% differential duty equals 2.5 mA. With k = 1 (matched 10 kΩ ratio resistors) that gives R0 = 3.3 V / 2.5 mA = 1.32 kΩ, use 1.33 kΩ 0.1%. Even a firmware bug at full duty then cannot command more than 2.5 mA, below the 5 mA resistor ceiling.

## 6. Key numbers

| Quantity | Value | Source |
|---|---|---|
| Motion perception threshold, DC 3 s, seated | 0.98 ± 0.29 mA | Nguyen 2022 |
| Cutaneous (tingling) threshold | 0.90 ± 0.29 mA | Nguyen 2022 |
| Nystagmus threshold | 1.61 ± 0.35 mA | Nguyen 2022 |
| Tilt-direction JND, 2 s raised-sine pulse | 0.74 ± 0.38 mA | Liu 2025 |
| "Commonly used" GVS current; 1–2 s → sway / illusory motion | ~1 mA | Fitzpatrick & Day 2004 |
| Body tilt settles after onset | 1–2 s | Marchand 2025 |
| After-sensation following DC offset | "several seconds" | Nguyen 2022 |
| sGVS that causes nausea | ±2 mA, 0.08–0.18 Hz, 9–21 min | Klingberg 2015; Javaid 2019; McCarthy 2023 |
| Nausea incidence, sGVS seated | 33–58% | Javaid 2019; Klingberg 2015 |
| Short sGVS bouts (~30 s) | no nausea | McCarthy 2026 |
| Earliest per-subject GVS nausea time found | ~10 min (vomited) | McCarthy 2023 |
| Pseudorandom 3.5/5 mA, 10.5 min: none/mild, moderate, severe | 78.3%, 13.3%, 8.3% | Dilda 2011 |
| Subjective recovery from motion-sickness nausea | 15–30 min; sensitised ≥ 2 h | Golding & Stott 1997 |
| GVS currents used in literature (max) | 4–5 mA routine high end; 7 mA once | Austin 2026; Dilda 2011; Allred 2025; Marchand 2025 |
| tDCS no-serious-AE envelope | ≤ 4 mA, ≤ 40 min, ≤ 7.2 C | Bikson 2016 |
| LOTES: sustained-current average / peak | ≤ 4 mA / ≤ 30 mA | LOTES-2023 |
| LOTES: current density | ≤ 2 mA/cm² | LOTES-2023 |
| LOTES: session time / charge | ≤ 60 min / ≤ 6000 mC | LOTES-2023 |
| LOTES: idle or fault DC | ≤ 100 µA | LOTES-2023 |
| Mastoid-to-mastoid impedance | 0.8–3 kΩ typical; < 10–12 kΩ accepted | Liu 2025; Allred 2025; Austin 2026 |
| Open-source GVS compliance design point | 4 mA into 5 kΩ → ≥ 20.4 V, built at 24.6 V | Liu 2025 |
| Adverse effects at 0.6 / 1.5 mA, 255 sessions | itching 10.2%, tingling 10.7%; no seizures, vertigo, nausea | Utz 2011 |
| Smallest common polyfuse hold current | 50 mA | Bourns MF-R005 listing |
| Recommended event burst | 1 Hz sine, 2 cycles, 250 ms taper, 0.5 → ≤ 2.0 mA peak | [I] from above |
| Recommended hardware fault ceiling | ≤ 5 mA into a short | [I] |

## 7. Firmware change spec (do not implement here; spec only)

Every item below is [I] unless tagged, and is tied to the section above that motivates it.

**F1. Output stage: two PWM channels plus an enable (section 5).**
- `PIN_PWM_A = 4` (positive current) and `PIN_PWM_B` = a free GPIO for negative current (GPIO1 is a candidate; check it is not tied to anything on your board). Both run LEDC at 20 kHz, 10-bit, each with an external 10 kΩ pull-down.
- At any instant at most one channel is nonzero. Both are 0 at boot, on E-stop, on disarm and between stims.
- `PIN_EN` = another free GPIO driving the solid-state disconnect through the hardware E-stop. Default low with a pull-down. Asserted on `arm`, deasserted on disarm, arm expiry, E-stop, fault and boot.
- Assert EN, wait 20 ms, then start the waveform, so the switch never makes or breaks while current flows.

**F2. Waveform: replace the DC trapezoid with an integer-cycle sine burst (sections 2–3).**
- `I(t) = A · w(t) · sin(2π f t)`, for t in [0, n/f].
- f is clamped to [0.5, 2.0] Hz, default 1.0. n is clamped to [1, 4] cycles, default 2. Reject (`bad_args`) any request where n/f > 4000 ms. The duration is n/f, so 500–4000 ms, and the 50 ms minimum goes away.
- w(t) is a cosine (Tukey) taper, 250 ms up and 250 ms down, flat between. The envelope is symmetric and there is an integer number of cycles, so the burst integrates to zero net charge.
- Recompute every loop pass (about 1 kHz), well above the 1 Hz content.
- Drop the DC mode for now. Named omission: no DC-step "tilt" stimulus.
- Ramps: Liu 2025 uses ramps to avoid "tingling and burning sensations" [S]. Kollmansperger 2024 uses 2 s fades [S]. 250 ms is a compromise that keeps the burst at 2 s.

**F3. Units in mA, ceilings in mA (sections 2, 5).**
- Protocol becomes `{"cmd":"stim","bucket":"x","peak_ma":0.0..,"freq_hz":1.0,"cycles":2}`. The current `intensity` field is kept and maps to `peak_ma = intensity × max_peak_ma`, for compatibility with the pipeline.
- Compiled `MAX_PEAK_MA_CEILING = 2.5`. Config `max_peak_ma` defaults to **1.0** and can only lower or match the ceiling. Raise it in 0.25 mA steps only after on-head sessions show it is tolerated, never above 2.0 for the first week.
- Config `ma_full_scale` holds the bench-calibrated mA at 100% differential duty. Duty = peak_ma / ma_full_scale. Refuse to run (`reason:"uncalibrated"`) if it is absent.
- Report `peak_ma`, `freq_hz`, `cycles`, `ms` and the duty in the reply and the CSV log.

**F4. Caps (sections 3–4).**

| Cap | Now | Spec | Why |
|---|---|---|---|
| Duration | 50–2000 ms DC | 500–4000 ms, integer cycles | one 0.5 Hz cycle = 2 s; ~30 s bouts did not cause nausea [S: McCarthy 2026], so 4 s is far from the nauseogenic regime |
| Ramp | 200 ms linear | 250 ms cosine taper | smoother edges, less tingling [S: Liu 2025] |
| Cooldown | 5 s | **10 s** | after-sensations last "several seconds" [S: Nguyen 2022]; lets each event resolve before the next [I] |
| Per hour | 30 | **keep 30** | 30 × 2 s = 60 s/h, 9–21× below the exposure that produced nausea [S table; I arithmetic] |
| Session | arm 600 s, re-armable forever | add **60 min cumulative armed time per power cycle**, then refuse until reboot | LOTES ≤ 60 min/session [S] |
| Charge | none | log cumulative absolute charge (mC) per hour in `status` | LOTES 6000 mC/session [S]; will read ~75 mC/h at 30 × 2 mA bursts [I] |

**F5. Current readback abort (section 5).** If the front end exposes a sense voltage, read it with the ESP32-C3 ADC. Abort the stim, deassert EN and latch `fault` if either of these holds for more than 20 ms:
- |I_meas − I_cmd| > 0.3 mA
- |I_meas| > max_peak_ma + 0.2 mA

The fault latch requires a reboot to clear. Report `fault` and `last_fault` in `status`. [S for the pattern: Liu 2025 INA219 cutoff.]

**F6. Impedance gate (section 1).** Add a `{"cmd":"check"}` that, while armed, delivers a single 0.1 mA, 1 Hz, 1-cycle sine and computes |V|/|I| from the readback. Refuse stims if the result is above 10 kΩ or below 300 Ω (a short or a gel bridge between the leads). This needs the voltage across the electrodes to be measurable. If your front end cannot provide it, drop F6 and use the multimeter step in section 9.

**F7. E-stop fail-safe wiring (section 4).** Invert the logic: a normally-closed switch to GND, so pin LOW = OK and HIGH = stop. A broken wire (pulled up by INPUT_PULLUP) then trips the stop. Today a broken wire reads as not tripped (README).

**F8. Network control (section 4).**
- When running untethered on battery over WiFi, require a `token` field matching `/config.json` `auth_token` on every HTTP command. Reject otherwise.
- Prefer a phone hotspot to shared venue WiFi.
- Keep `server.handleClient()` from delaying `tick()`: the README notes stalls with a slow client.

**F9. Keep as-is:** output 0 first thing in `setup()`, arm requirement, 600 s arm expiry, E-stop every loop pass, trial logging before the waveform starts.

## 8. Bench test (first power-on, no human)

Equipment: battery-powered rig (no USB to a charging laptop), a DMM with µA/mA range, a scope if you have one, and 1% resistors of 1.0 kΩ, 2.7 kΩ, 4.7 kΩ and 10 kΩ. These bracket the 0.8–3 kΩ typical and the < 10 kΩ acceptance range [S: Liu 2025 used 1481/2663/3850 Ω and recommends 0.8–3 kΩ for calibration; Allred 2025 < 10 kΩ].

Each step is [I] unless tagged.

1. **Idle and reset.** Put 2.7 kΩ across the electrode leads and the DMM in series (µA range). Power on, reset the ESP32 several times and hold BOOT to enter the bootloader.
   - Pass: |I| ≤ 10 µA at all times. LOTES maximum is 100 µA idle or fault [S].
   - On the scope across the load: no spike above 0.1 mA × 2.7 kΩ = 0.27 V during reset or boot.
2. **Calibration.** Arm. Command a full-differential-duty test (a debug-only command, or temporarily 1 cycle at 0.5 Hz) and record the peak current both ways. Set `ma_full_scale`. Liu found and trimmed a 0.04 mA offset, so expect one [S].
3. **Accuracy and linearity.** At each of 1.0 / 2.7 / 4.7 kΩ, command 0.25, 0.5, 1.0, 1.5 and 2.0 mA peak, 1 Hz, 2 cycles. Measure peak current as V_load / R on the scope.
   - Pass: within ±10% or ±50 µA, whichever is larger. Liu achieved 0.4–4.7% [S]. Both polarities should be symmetric within 5%.
4. **Compliance.** At 10 kΩ, command 2.0 mA. Record whether it clips; clipping here is acceptable. At 4.7 kΩ, 2.0 mA must not clip.
5. **Charge balance.** On the scope, use the mean over the full burst at 2.7 kΩ, 2.0 mA.
   - Pass: |mean| ≤ 2% of peak (≤ 40 µA). The DMM in DC mode should average to about 0 over the burst.
6. **Ripple.** At 1.0 mA DC-equivalent hold, if you add a hold debug mode, or at a sine peak, check the 20 kHz component across the load.
   - Pass: ≤ 1% of peak (≤ 10 µA at 1 mA). Expected about 0.1% per section 5.
7. **Hardware ceiling, the most important test.** Disconnect the PWM and enable lines from the ESP32. Force the worst case by hand: PWM-A input tied to 3.3 V, PWM-B to GND, EN forced on, load = **0 Ω** (DMM mA range directly across the leads). Repeat with the polarity swapped.
   - Pass: |I| ≤ 5.0 mA in both polarities.
   - If you added CRDs, this also verifies their anti-series behaviour.
8. **Open circuit.** Remove the load and command 2.0 mA, then reconnect a 2.7 kΩ load mid-burst.
   - Pass: on reconnect, the current transient does not exceed the commanded peak by more than 20%, and nothing gets hot. LOTES requires no unsafe state with open or short electrodes [S].
9. **E-stop.** Mid-burst at 2.0 mA into 2.7 kΩ, press the hardware E-stop.
   - Pass: current is ≤ 10 µA within 10 ms on the scope, and firmware reports `estop`. Repeat by cutting the E-stop wire, which must also stop once F7 is done.
10. **Readback abort (if F5 is built).** Swap the load to 10 kΩ mid-burst so the output clips.
    - Pass: the firmware latches `fault` and EN drops.
11. **Isolation check.** With the stimulator on battery, measure resistance from each electrode lead to the laptop chassis or USB shield, if anything is connected.
    - Pass: open circuit (more than 10 MΩ on the DMM). Otherwise, disconnect.

Do not proceed to a head until steps 1, 3, 5, 7 and 9 pass and are written down.

## 9. On-head procedure (first session)

Each step is [I] unless tagged.

**Before:**
- Run the contraindication list in section 4. Have a second person present who knows where the E-stop is and how to pull the leads.
- No food in the previous hour. A bin within reach.
- Sit in a chair with back and arm support, feet flat, not standing.

**Prep:**
- Alcohol wipe, light NuPrep exfoliation, wipe clean, 35–50 mm Ag/AgCl gel electrode on each mastoid, headband over the electrodes [S: Liu 2025; McCarthy 2023].
- Inspect the skin first. Never use it over irritated skin [S: LOTES].

**Impedance check:**
- With F6: run `check`.
- Without F6: one 0.1 mA, 1-cycle 1 Hz burst while measuring the peak voltage across the leads with the scope. R = V / 0.1 mA.
- Proceed only if R is 0.5–10 kΩ. Re-prep if it is over 10 kΩ [S for the threshold: Allred 2025; Austin 2026].

**Ladder:**
- Start at **0.5 mA** peak, 1 Hz, 2 cycles. Step **+0.25 mA** to a maximum of **2.0 mA** [S: Nguyen 2022 started at 0.5 mA and stepped 0.25 mA; Austin 2026 started at 0.5 mA with 0.5 mA steps].
- One burst per step, at least 60 s between steps. Nguyen used 5 min, so 60 s is a hackathon compromise [I].
- After each burst, rate these 0–3 (none, slight, moderate, severe; Austin 2026's scale [S]): motion sensation, tingling, metallic taste, visual flashes, headache, nausea.
- The expected order is tingling and motion at about 0.75–1.25 mA [S: Nguyen 2022; Liu 2025].
- The **working level** is the lowest step with clearly noticeable motion sensation and tingling no worse than slight. Set `max_peak_ma` to that level plus 0.25 mA and stop climbing.

**Stop immediately and end the session if any of these occur:**
- tingling or burning rated moderate, or rising from one burst to the next at the same current [S: LOTES-2023 precaution]
- any pain
- visual flashes
- any nausea (≥ 1/10)
- headache
- motion sensation that lasts more than about 10 s after the burst ends, when several seconds is the expected range [S: Nguyen 2022]
- anything unexpected

**After:**
- Stay seated 5 min.
- Peel the electrodes and inspect the skin. Mild redness should be gone within 24 h; do not re-stimulate until it is [S: LOTES-2023].
- Log the working level, impedance and every rating.
- First session total: ≤ 20 min on the head, ≤ 15 bursts.
- If any nausea appeared, no more GVS that day, because sensitisation lasts at least 2 h [S: Golding & Stott 1997].

## Open questions and what I left out

- **Your analog front end is unknown.** Everything in sections 5, 7 and 8 assumes a Howland-type differential V-to-I converter. If you built something else (a single-ended op-amp with a sense resistor, a transistor sink, a voltage source with a series resistor), the mid-scale and duty-0 hazard and the compliance math need redoing. Send the schematic or a photo. A voltage source with only a series resistor would also need its own analysis.
- **Whether a 2 s rocking burst is aversive enough to punish scrolling** is untested. I found no study using GVS as an aversive stimulus for seconds-scale pairing. Habituation over repeated pairings is documented (section 3). See `research/conditioning.md`.
- **DC tilt vs sine rocking: which is more unpleasant?** No source compares them for aversiveness. I chose the sine for charge balance, not because it is known to be worse to feel.
- **Nausea-mode (session-level ±2 mA, 0.08 Hz, up to 21 min) is deliberately left out.** It is the only sourced way to make GVS nauseating. It affects only about a third to a half of people, cannot be tied to events, and needs a separate supervised protocol with vomiting provisions. The F4 caps would block it on purpose.
- **Sources I could not read in full:** Utz et al. 2010 "Electrified minds" safety section (the PDF copy was blocked); Antal 2017 tES guidelines; Dlugaiczyk 2019 review (no safety numbers extracted); the tDCS burn case reports (titles only); and the original Central Semiconductor 1N5314 PDF (values from a distributor listing).
- **Numbers with no source:** the mastoid pain threshold, hydrogel contact area for a 35 mm ECG electrode, the median time-to-nausea for GVS, and the migraine contraindication.
- **CRD anti-series behaviour** in reverse bias is not verified. Bench step 7 is the check.
- **Relay or switch click as an unintended cue:** solved by keeping the switch closed while armed and using a solid-state part. Confirm it is silent.
- **ESP32-C3 GPIO choice for PWM-B and EN:** check that GPIO1 and the other candidate are free on your specific board.
