# Pitch video: scene list

**Opening, built:** `edl.opening.json` → `out/opening.mp4`. Scene 1 → window-cloning glitch (`transition.py`) →
scene 2 in the DedSec look with a glitched voice (`dedsec.py beats.scene2.json`; the hyperpop version, `hyperpop.py`, is retired).
Next comes you to camera, in normal mode (footage still to shoot).

**Scene 1:** `edl.scene1.json` → `out/scene1.mp4`, 44.6 s.
- The settlement headline card, then 7 high-impact beats from the All-In clip, in the CYBER look.
- Mood readouts by shot, her name title on her first close-up, and Fallé underneath.
- The creator mark (the ingot logo) appears once, on the headline card. There's no "+- II" text tag, because the logo already reads + − II.
- Beats:
  1. the settlement question
  2. "two of the biggest disasters…", her laugh, the interviewer bewildered, the crowd laughing
  3. "disagree with every single premise"
  4. "billion dollar settlement says otherwise"
  5. "are you done with your ten-minute question?"
  6. "um okay"
  7. "couldn't be more proud of the agreement"
- The table below continues from there. Its old row 2 is now this opening.

This is spliced from real clips, not AI-generated. Each scene gets a **look** and a **voice**, used only where they fit.

**Looks**
- **KIDS:** soft, bloomed, oversaturated, VHS fuzz, 4:3 picture with a round vignette.
- **DEDSEC:** RGB split, scanlines, glitch tears, pixelated eyes.
- **CLEAN:** no effect.

**Voices**
- **YOU:** your serious, YC-style voice.
- **TTS:** robot narrator (macOS Zarvox / Trinoids, crushed).
- **MEME:** your voice pitched way up.
- **ECHO:** repeats and fades.

The tools are in `video/fx.py` and `video/build.py` (see `video/README.md`). Running time is about 2:15.

| # | Time | Look | Picture | Voice and words |
|---|---|---|---|---|
| 1 | 0:00–0:10 | DEDSEC | Black, then a glitching title: *"what if you could edit your reflexes?"* Quick cuts of people scrolling, eyes pixelated. | **TTS:** "In a future where people can control their subconscious response to what they see… what does that world look like?" |
| 2 | 0:10–0:25 | DEDSEC | Headline card: **"Meta to pay up to $18B to settle states' claims it designed apps to addict kids"**, sourced *Reuters / AP, Aug 26 2026*. Then the All-In Summit clip (CYBER look), with lower third **"Meta President Dina Powell McCormick, All-In Summit 2026"** and *via @scrolling2death / All-In* in the corner. Keep her lines "I totally disagree with… every single premise" and "couldn't be more proud of the agreement." | **YOU:** "Meta just agreed to pay twelve billion dollars, up to eighteen, to settle claims it built Instagram to hook kids. Asked about it on stage, this was the answer." *(Let her clip play. See note A.)* |
| 3 | 0:25–0:35 | DEDSEC, fast | Paper titles and cut-out people flashing at 4–6 frames each: infinite scroll, variable rewards, autoplay. | **TTS:** "The feed runs on patterns you never agreed to: variable rewards, infinite scroll, autoplay." |
| 4 | 0:35–0:45 | KIDS | Screen-time apps and grayscale mode, bright and toylike. | **YOU:** "Solutions exist. But the solutions…" **MEME + ECHO:** "…don't go NUCLEAR. *nuclear… nuclear…*" |
| 5 | 0:45–0:55 | CLEAN | You, to camera. | **YOU:** "A screen-time blocker can be uninstalled. Conditioning lives in your nervous system." *(See note B.)* |
| 6 | 0:55–1:10 | CLEAN, with a DEDSEC flash on "blacklist" | Screen recording: the packet watcher, then Instagram turned on in the blacklist, then the board's status going *live*. | **YOU:** "Pick what you want to quit. Instagram goes on the blacklist. Every time your devices pull reels, you get a jolt. Over time, you stop wanting it." |
| 7 | 1:10–1:25 | CLEAN | TRIBE brain map (`research/tribe_v2/test12_mean.png`, or a brain movie rendered from your recordings). | **YOU:** "Next: Meta's own brain-encoding model, TRIBE v2, scores what you actually watch. The goal is to read and steer your responses to media the way interpretability reads a model: keep the load that teaches you, punish the junk." |
| 8 | 1:25–1:45 | KIDS | Your friend steering you from the phone page, and you tilting. Show the LED matrix bar. | **MEME:** "There's also a fun mode." **YOU (normal):** "That's my friend, driving me with my own sense of balance." |
| 9 | 1:45–2:00 | CLEAN cards | Citation cards, the wiring diagram (`gvs/pictures/full_front.png`), then the software map (`video/assets/software_map.png`). | **YOU:** "How it works. A current source modelled on published GVS hardware, aversive conditioning from the learning literature, and a lot of safety: two milliamp cap, auto-off in one second if the link drops, thirty minutes an hour, and never wired to a charging laptop." |
| 10 | 2:00–2:15 | CLEAN, with a DEDSEC sting on the last card | Results cards. | **YOU:** "Results. I've been nauseous since 3:30 a.m. Four friends have felt it with me. Three of them drove me around like an RC car." **TTS:** "Edit your reflexes." |

## Notes

**A: Meta.**
- **Settlement (scene 2 card):** Reuters, AP, BBC and PBS, Aug 26 2026. Meta agreed to pay about $12B over 10 years, up to $17–18B, to settle nearly every US state's claims it designed Facebook and Instagram to addict kids. Meta denied wrongdoing. Say "settlement" and "agreed to pay," not "fine."
- **The clip** (https://www.instagram.com/reels/Ddjchg-ugUO/, reposted by @scrolling2death; file `clips/powell_cspan.mp4`) is from **Dina Powell McCormick's appearance at the All-In Summit (2026)**, after the settlement. The source for the speaker is the reposter's caption plus All-In Summit coverage; nobody was identified from their face.
  - The interviewer raises Meta having "just paid the largest settlement." Her answers in the burned-in captions: "I totally disagree with basic[ally] every single premise in your question" and "I couldn't be actually more proud of the agreement."
  - "Laughs off accountability" is the reposter's headline (burned into the top of the video). Crop it out and let her own words carry the beat.
  - Lower third: "Meta President Dina Powell McCormick, All-In Summit 2026", credited "via @scrolling2death / All-In".
  - (An earlier draft pointed at a C-SPAN clip from Mar 25 2026. That was a different video.)
- **Getting the footage:** download it yourself from C-SPAN, or screen-record the reel. The C-SPAN original is the better source.
- **Eye pixelation:** that's a style choice. It doesn't hide who she is, since the card names her.

**B: "Can't be uninstalled."** The learning research (`research/conditioning.md` §4) says conditioned aversion fades once the stimulus stops (extinction), and relapse is common.
- Your original line: "Pavlovian conditioning on the brain cannot [be uninstalled]".
- Honest punch: "a blocker is an app; conditioning is in you," or "conditioning is a lot harder to uninstall."

**C: "Nauseous on demand."** The firmware's short pulses give tilt and tingle. The nausea you report is your own experience, so say it as "I've been nauseous since 3:30 a.m.," not as a guaranteed effect. The research says real GVS nausea takes minutes of slow rocking (`research/gvs.md` §3).

**D: Dashboard (scene 6).** There's no packet-watcher dashboard yet, and you've said it's planned. Until it exists, record `pipeline` output in a terminal next to the steering page, or build the dashboard before filming.

**E: Citations (scene 9):**
- **Hardware:** Liu, Suzuki, Fushimi, Ochiai (2025), *Design and evaluation of a voltage-controlled current source for galvanic vestibular stimulation research*, HardwareX 22:e00647.
- **Conditioning:**
  - Garcia & Koelling (1966), *Relation of cue to consequence in avoidance learning*, Psychonomic Science 4:123–124. This is the "belongingness" paper: nausea pairs with taste.
  - Azrin, Holz & Hake (1963), *Fixed-ratio punishment*, J. Exp. Anal. Behav. 6:141–148. Punishment timing and schedule.
- **Safety:** Bikson et al. (2016), *Safety of transcranial direct current stimulation: evidence based update 2016*, Brain Stimulation 9:641–661.

**F: Results (scene 10)** are your numbers: nausea since 3:30, 4 friends, 3 drivers. Only put on screen what happened.

**G: Style references** are for the feel only. Don't use Teletubbies or Watch Dogs characters, logos, music or UI art. The look comes from the filters.

## Shots to collect

1. You to camera, scenes 2, 5, 6 and 9 voiceover (or record VO separately).
2. The friend steering you from a phone, plus the LED matrix close-up (scene 8).
3. A screen recording of the packet watcher or terminal plus the steering page (scene 6).
4. Scrolling b-roll: hands on a phone in the dark (scenes 1 and 3).
5. Screen-time apps (scene 4).
6. Optional news footage (scene 2), sourced.
