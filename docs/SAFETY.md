# Safety, disclaimer and how this can go wrong

**Read this before you build, flash or wear anything.**

> **DANGER. This device passes electric current through your head. It can cause permanent damage.**
> It is a hackathon prototype, not a medical device. Nobody has certified, reviewed or approved it. It is provided as is, with no warranty. If you build it or run it, you alone are responsible for what happens to you and to anyone you put it on.

## Do not use it if

Any of these means no:

- epilepsy, a seizure history, or unexplained fainting
- a pacemaker, an ICD or any implanted electronic device, or metal in the head
- a heart condition
- any balance or vestibular disorder (Ménière's, BPPV, vestibular neuritis), migraine, strong motion sickness, or a recent concussion
- pregnancy
- a cut, rash or irritated skin where the electrodes go
- alcohol, or anything that affects balance, in the last 24 hours
- you are under 18 or the person wearing it has not agreed

All but the last item come from the sources in [`research/gvs.md`](../research/gvs.md) section 4 (the last item is mine). It is a self-experimenter's list, not medical advice. Nobody screened the people who tried this build.

## Rules I followed, and you must too

1. **Battery only.** Never wear the electrodes while the laptop is on its charger, while the board is on USB to anything on wall power, or while the board runs from a wall supply. See "The charger path" below.
2. **Dummy load first.** Every test in [TESTING.md](TESTING.md) with a 2.2 kΩ resistor across the electrode leads and nobody attached, before the first test on a person.
3. **Electrodes behind both ears, on the mastoid bone, and nowhere else.** Never one on an arm, hand, shoulder or chest.
4. **Kill switch in your hand.** The design has a physical switch in the left electrode lead. Never run without it. (The first on-head session in [`gvs/bench_log.md`](../gvs/bench_log.md) ran with the switch removed, and the plan was to pull a pad. Don't.)
5. **Sit down, with a second person next to you.** Back support, feet flat, no food in the last hour, a bin within reach. Do not stand, walk, climb stairs, ride or drive while it can fire. It tips your sense of balance, and that is exactly what it is for. The literature measures real sway in standing people, and a shuttle-landing simulator study saw crash landings rise from 2.3% to 9% under random GVS (`research/gvs.md`, Moore 2011).
6. **Start low and go up slowly.** 0.5 mA, then 0.25 mA steps, never above 2.0 mA. At least 60 seconds between steps in a first session. Restart at 0.5 mA after any change to the electrodes.
7. **Stop at the first sign of trouble.** Pain, burning, rising tingling at the same current, flashes of light, a headache, nausea, or a motion sensation that lasts more than about ten seconds after the current ends. Take the electrodes off and don't try again that day. Motion-sickness sensitivity stays raised for at least two hours.
8. **Look at your skin afterwards.** Mild redness should be gone within 24 hours. If it is not, don't stimulate again until it is.

The firmware enforces some of these ([limits it enforces](#what-the-firmware-limits-and-what-they-cannot-do)). It cannot enforce the rest.

## How this can go wrong

### On your body

| What | Why | What I saw or what the sources say |
|---|---|---|
| Burns, blisters and pain at the electrode | Current crowds into the few points that touch the skin: a dry or damaged pad, a bare wire pushed into the pad, a small contact area | **Seen.** On 2026-11-07 a bare wire cut into a pad's carbon layer. Tingle became pain at 1.0 to 1.5 mA, with no balance effect, and the session stopped (`gvs/bench_log.md`, `gvs/DEBUG.md`). |
| Less current than you think | A dry pad, hair under the electrode or a poor contact raise the head's resistance, and the supply runs out of voltage. **The board still reports the commanded current**, because the sink holds its own emitter on target, so its reading never shows the loss | Worked out in `gvs/DEBUG.md`: with 17 V available at 2 mA, the largest head resistance that still gets the full current is about 5 kΩ. Measure across the 2.2 kΩ top resistor to see the true current. |
| Falls and injury | The device tips your sense of balance on purpose | Standing GVS causes real sway. Anything around you becomes dangerous: stairs, roads, kitchens, ladders. |
| Nausea, headache, visual flashes | The vestibular system and the visual system are linked, and brief GVS gives a tilt or spin sensation | Nausea in the studies needs minutes of low-frequency current, but this build repeats a burst for as long as an app stays open, and its fun mode can hold a current for much longer. The builder reports being nauseous after testing, and so was a friend who tried it. Treat that as a warning, not a result. |
| Seizure, or effects on implants | Current through the head | These are exclusions in the literature. Nothing in this build tests for either. |
| Lasting damage | Possible and not ruled out. Nobody has studied this device, so I cannot say it won't happen | The current is small (limit 2.0 mA). That is a limit, not a guarantee. |

### In the circuit

| What | What happens | What protects you, and what doesn't |
|---|---|---|
| **The charger path** | A USB cable from the board to a laptop on its charger ties the electrodes to wall power through the laptop. | The Mac's BLE relay (`gvs/tools/ble_bridge.py`) refuses all current while the Mac is on AC and the board is on USB (`403 refused`). **The UNO Q does not check.** Its page shows a warning while the board reports USB, and that is all. You must keep the board on battery. |
| A transistor shorts (Q2) | The only things left limiting the current are the 2.2 kΩ top resistor and the 1.1 kΩ sense resistor: about 7.3 mA at 24 V (`gvs/DEBUG.md`) | The firmware watches the current readback and trips a latched fault if it exceeds the command by 0.4 mA for 50 ms, but only if the firmware, the sense path and the ADC are all working. The readback can't see a fault in itself. |
| The boost overshoots | The HV rail can reach 23 to 26.5 V with the leads open during a pulse | The firmware cuts the boost and latches a fault above 28 V, three readings in a row. `BOOST_MAX_PCT` is 45 and cannot be exceeded from the commands. A 10 kΩ bleed brings the rail down to about 3.9 V in about a second once the boost stops. If the firmware hangs, a 2 s watchdog resets it. A transistor stuck on, or a broken bleed, isn't covered. |
| A relay sticks or welds | One electrode stays on the high side (TOP, which is HV through 2.2 kΩ) | With the sink off no current flows. With the sink on the current is still set by the sink. A welded relay breaks the polarity logic. The kill switch is the backstop. |
| The relays don't pull in | The 5 V relay coils run from the 3.7 to 4.2 V battery, and a low battery may not close them | Both relays released is a safe state: both electrodes on one node, no current path. |
| A flat or brown-out battery | The board resets mid-session | Seen on 2026-11-08: with no WiFi credentials the firmware kept a hotspot up all night and flattened the 250 mAh cell. That is fixed, but a LiPo that went below about 3.0 V should be checked for swelling and heat while it recharges. |
| LiPo hazards | Fire and venting if punctured, shorted, overcharged or damaged | The cell is soldered straight to the board. Don't leave it charging unattended, don't crush it, and retire a swollen one. |
| PWM not attaching | An early build commanded 0 mA on every pulse and reported success, because the LEDC channel never attached (12 and 11 bit duty both failed on this chip) | Fixed. The board now faults at boot if either PWM fails to attach (`gvs/README.md`). |
| A wiring error on the perfboard | Anything: a wrong jumper, a solder bridge, a swapped relay pin | `gvs/board/check.py`, the continuity checks in [BUILD.md](BUILD.md), and the dummy-load tests exist to catch this. Skip them and you find out on your head. |

### In the software

| What | What happens | What limits it |
|---|---|---|
| The classifier fires on the wrong thing | Reels and DMs share servers. A messaging app can look like a feed. A rule can be set to the wrong app | The pipeline decides from flow shape, needs two matching windows, then rests ten seconds. You can set any app to **Never** on the dashboard, and **Pause** stops everything. No rule can ask for more than the current you set on the command line, and the firmware caps it again. |
| **Anyone on your hotspot can steer you** | Fun mode serves a page on the UNO Q's WiFi hotspot. Whoever opens it can send current | The firmware's caps still hold (2.0 mA, a 1 s dead-man, a budget of 30 minutes of current per hour), and there is a STOP button on the page. Only let people you trust join. The hotspot password is random: `uno_q/fun/start_fun.sh` makes it once into `uno_q/fun/hotspot_pass` (git-ignored) and prints it. Only share it with people you trust, and delete the file to get a new one. |
| Someone reads your traffic | The pipeline sees DNS names, TLS server names and packet sizes for every device on your network | The dashboard is locked with a key whenever it listens off localhost. Only point this at devices and networks you own. |
| A leaked token | The firmware takes commands from anyone who has its token | `secrets.h` and `device.env` are git-ignored. Never commit them. Never leave the default token (`change-me`). |

## What the firmware limits, and what they cannot do

Hard limits in [`gvs/firmware/gvs_controller/gvs_controller.ino`](../gvs/firmware/gvs_controller/gvs_controller.ino):

| Limit | Value |
|---|---|
| Peak current | 2.0 mA (`FW_MAX_MA`); the hardware ceiling is about 3.0 mA at full PWM |
| One pulse | 3000 ms (`MAX_MS`); 5000 ms cooldown between pulses (`COOLDOWN_MS`) |
| Pulses per hour | 30 |
| Live mode | 2.0 mA, slewing at most 4 mA/s, 1 s dead-man, 30 minutes of current per rolling hour |
| Boost | 45% duty cap; cuts off and faults above 28 V |
| Overcurrent | trips if the readback exceeds the command by 0.4 mA for 50 ms |
| Everything else | a latched fault until power cycle; a token on every command; a 2 s watchdog |

They cannot:
- make a bad electrode connection safe
- protect you if a transistor shorts and the firmware isn't running
- stop a person from standing up and walking while it is on
- decide whether you should be using it

## If something goes wrong

1. **Press the kill switch.** Then take both electrodes off your head.
2. Disconnect the battery if you can do it safely.
3. Sit or lie down until the dizziness is gone. Don't get up quickly.
4. Burns, a seizure, chest pain, fainting, or any symptom that does not clear in minutes: get medical help.
5. Write down what happened, with the current, the time and the electrode state, and put it in `gvs/bench_log.md`.

## Where the numbers come from

[`research/gvs.md`](../research/gvs.md) is a sourced write-up: each number is tagged as taken from a paper or as the author's inference. The safety section draws on Liu et al. 2025 (HardwareX), the LOTES-2023 consensus on tDCS-style stimulation, Fitzpatrick & Day 2004, Nguyen et al. 2022 and Golding & Stott 1997. None of this makes the device safe. It is the reason the limits are where they are.
