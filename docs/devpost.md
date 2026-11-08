## Inspiration

I wanted to see if I could make myself hate opening an app.

In August 2026 Meta agreed to pay up to $18 billion to settle claims that Facebook and Instagram were designed to addict kids. The usual advice is "get off your phone" or "buy a screen lock app". Those methods are nothing beyond performative. An app can be uninstalled. Pavlovian conditioning cannot.

## What it does

HVAC stands for Human Vestibular Aversion Conditioner. I pick what I want it to catch. When I do that thing, the headband makes me feel like I'm tipping over, and it keeps doing it for as long as the app stays open.

It watches the network traffic of every device I own over Tailscale, so it doesn't matter whether Reels opens on my phone or on my laptop. A dashboard on the Arduino UNO Q lets me set each app to Nauseate, Never or Auto.

There's also a fun mode. My friends join the UNO Q's hotspot and steer my head left and right from their phones. I'm the remote-controlled car.

**DANGER. This device passes current through your head and can cause permanent damage.** It is a hackathon prototype, not a medical device. The full safety notes are in the repo.

## How I built it

**Hardware.** An electrode behind each ear. A XIAO ESP32-C3 on perfboard with a battery, a boost converter, a current sink (an LM358 and a 2N3904), two relays that reverse the direction of the current, and a physical kill switch. The firmware caps the current at 2.0 mA, a pulse at 3 seconds, and a pulse every 5 seconds. I tested the circuit on a dummy load before I wore it.

**Software.** The Arduino UNO Q captures packets with tshark. A pure-Python classifier labels each flow from DNS and TLS, and checks the last three seconds of traffic once a second. To teach it what to catch, I record two minutes of whatever I want punished. Reels and DMs use the same servers, so the classifier looks at the shape of the traffic. Two matches in a row and the band fires. Ten seconds later, if the traffic still matches, it fires again. TRIBE v2 runs once on a screen recording when I enroll a category, and its predicted brain response can lower the weight of a match. Commands go to the headband over Bluetooth.

## Challenges

- The PWM that sets the current failed to attach at 12 and 11 bits on the ESP32-C3. Every pulse would have commanded 0 mA and still reported success. It now runs at 10 bits and faults at boot if it fails to attach.
- My first time wearing it, I felt tingling that turned into pain, with no balance effect. A bare wire pushed into the electrode pad was the likely cause. The fix is fresh pads, 2 mm pins, and checking the resistance before I start.
- The board reports the commanded current even when the head can't take that much, so I worked out how much resistance the supply can drive and how to measure the true current.
- Reels and DMs share servers, so a domain name alone can't tell them apart.
- The battery went flat overnight because the board kept a hotspot up. WiFi now stays off unless it's needed.

## Accomplishments that I'm proud of

It works end to end. I use something I enrolled, the traffic matches, and the headband fires.

I have been nauseous since 3:30 a.m. My friend who tested it was nauseous too.

## What I learned

- A bad electrode contact can ruin everything: mine gave pain instead of a balance effect.
- In the research, nausea takes minutes of slow current, and a short burst gives a tilt. So the headband repeats the burst for as long as an app stays open.

## What's next

I'd love to fine-tune TRIBE v2 on my own brain responses. Could I condition myself to like germane cognitive load? Could I make myself dislike reels, cringe?

What would the world look like if people could choose how they respond to things before they're even aware they're responding?

## Links

- The hackathon writeup, with the wiring diagram and the software map: https://aryagarg23.com/writing/hvac
- Field notes from its future, with a simulation you can play with: https://aryagarg23.com/futures/hvac
