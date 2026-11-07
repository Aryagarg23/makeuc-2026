# Telling Instagram reels from DMs (and TikTok / Shorts) from encrypted metadata on a Tailscale exit node

Date of research: 2026-11-07. Scope: what the classifier in `pipeline/gvs_pipeline/{flows,classify}.py` can and cannot rely on.

Tags used throughout: **[S]** = sourced fact (URL given), **[W]** = weak source (third party / unverified), **[I]** = my inference, **[?]** = not found, do not rely on it.

Search tooling note: several primary pages were only reachable as summaries (WebFetch returns a model summary, not raw text). Where a number came from a summary I say so. Nothing below is quoted from memory.

## Summary

1. No public source maps `video-*` / `scontent-*` / `fna.fbcdn.net` hostnames to "reel" vs "photo" vs "DM media" **[?]**. The only hostname facts I could source are weak (passive-DNS listings). Hostname alone will not separate reels from DM media; `cdninstagram.com` is shared, which the current design already assumes.
2. DM *text* rides on a long-lived MQTT-over-TLS connection, with media sends going through the normal HTTP API **[S]** (instagrapi / instagram_mqtt docs). DM text is tiny, so it stays under the 50 kB floor. The risky DM traffic is media (photos, videos) and DM video playback, which I could find nothing on **[?]**.
3. Instagram on iOS and Android has been on QUIC/HTTP3 since Meta's 2020 rollout **[S]**, and Meta's newer in-house mobile stack (launched to Instagram) has its own DNS resolution and caching, connection pooling and QUIC **[S]**. So expect: UDP/443, multiplexed streams, per-connection features coarse, DNS answers possibly absent.
4. Instagram preloads the *next* reel in memory (adjacent preload) and previously used disk prefetch **[S]** (Android Developers blog). That is confirmed for the Reels tab. Whether reel video prefetches while you sit in the home feed or DMs is **[?]**.
5. SNI is probably still visible for Meta in 2026. Meta servers support ECH but do not publish ECH configs in DNS **[S]**, 99.99 % of 1.1 M active ECH deployments are Cloudflare **[S]**, and Apple has no system-wide ECH default **[S]** (forum thread). Inference: Instagram iOS traffic still exposes SNI **[I]**. Verify with the capture plan.
6. Literature supports classifying in-app *activity* and video *streaming* from coarse timing/size features, but nothing I found targets reels-vs-DMs. Best analogue: Pathmaperuma et al. got 90 %+ on 92 in-app activities (Facebook, Instagram, Messenger, ...) with 0.2-0.5 s windows using per-direction packet size and inter-arrival statistics **[S]**, but note Instagram activities were confused with Facebook ones, and this was a lab setup with frame-level data.
7. Biggest practical risk (see end): reels and DM media share hosts, protocol and the single multiplexed QUIC connection, and the 10 s / one-vector-per-domain design averages them together.

## 1. Hostnames and roles

| Host | Role | Evidence |
|---|---|---|
| `i.instagram.com` | Private/mobile API host (feed, DM inbox, thread fetch, etc.) | Netify lists it as an Instagram hostname on Meta CDN **[W]** https://www.netify.ai/resources/hostnames/i.instagram.com . Role "mobile API" is my reading of the instagrapi / instagram-private-api ecosystem **[I]**; I did not get a page that states it. |
| `graph.instagram.com` | API host | Netify lists it as Instagram **[W]** https://www.netify.ai/resources/hostnames/graph.instagram.com . Role not stated by the source. |
| `scontent*.cdninstagram.com` (many `scontent-<pop>-N` names, plus `scontent.cdninstagram.com`, `scontent-fallback`) and `static.cdninstagram.com` | Media CDN | Netify lists 280+ hostnames under cdninstagram.com and does not assign roles **[W]** https://www.netify.ai/resources/domains/cdninstagram.com . A Grokipedia page claims images, feed videos, Stories and Reels all come from these subdomains **[W]** https://grokipedia.com/page/Facebook_and_Instagram_CDN_Domains (encyclopedia-style, secondary, treat as unverified). |
| `*.fbcdn.net` (e.g. `instagram-p3-shv-01-otp1.fbcdn.net`) | Another CDN domain Instagram also uses | Netify reverse-DNS example **[W]** https://www.netify.ai/resources/ips/185.60.218.52 . |
| `video-*.cdninstagram.com`, `instagram.*.fna.fbcdn.net` | Commonly assumed video hosts | **[?]** I found no source confirming either name or role. Do not hard-code them. |
| MQTT realtime for DMs (MQTToT), IRIS inbox sync, typing/seen, reactions | DM text, realtime events | instagrapi realtime docs: realtime client opens Instagram's MQTToT connection; it can publish text, reactions, seen, typing over MQTT; "use the regular Direct methods for media sends" **[S]** https://github.com/subzeroid/instagrapi/blob/f5e2c2a0ff52b009767de64d9d3e6f2ab4941dad/docs/usage-guide/realtime.md . instagram_mqtt README describes MQTToT (zipped thrift payload in CONNECT) **[S]** https://github.com/nerixyz/instagram_mqtt . A hybrid client design doc says the MQTT path supports only text, media goes via Web API **[S]** https://github.com/supreme-gg-gg/instagram-cli/blob/660bc14e7e49f23edc703abfe8a24bc4ab28ed0b/docs/hybrid-client-design.md |
| `edge-chat.instagram.com` | WebSocket carrying the same realtime protocol for the **web** client | A gist for backing up DMs from the web version references `edge-chat.instagram.com` **[W]** https://gist.github.com/baptx/1e61eef2e1ec200b6e7b32409f79c07f ; a StackOverflow answer says Instagram uses MQTT for DMs and a websocket in browsers **[W]** https://stackoverflow.com/questions/68413708 . Whether the **iOS app** uses this host: **[?]**. |
| `edge-mqtt.facebook.com`, `edge-mqtt-fallback.facebook.com` | Facebook-family MQTT edge hosts | Appear in Netify and FullHunt listings **[W]** https://www.netify.ai/resources/hostnames/edge-mqtt-fallback.facebook.com . That Instagram's app uses them: **[?]** from my sources. |
| `mqtt-mini.facebook.com` | FBNS push notifications (separate device-auth MQTT connection) | **[S]** instagrapi realtime docs (same URL as above). |
| `rupload.facebook.com` | Resumable video upload host for the **official Graph API** content publishing flow | **[S]** https://developers.facebook.com/documentation/instagram-platform/content-publishing . This is the documented developer API; the app's own uploads may differ **[I]**. |
| `gateway.instagram.com` | **[?]** No source found for its role. |
| "Facebook MNS" | **[?]** No official doc found. The closest is an Instagram app log, hosted on Scribd (third party, unverified), with `mns` entries doing DNS cache refresh and fallback to the system `getaddrinfo()` **[W]** https://www.scribd.com/document/888550591/Log . Meta does say it built an in-house mobile network stack (below), but the talk page does not call it MNS. |

Reels vs photos vs DM media on the CDN: **[?]** no primary source. Are DM videos served from the same hosts as reels: **[?]** no source; **[I]** it is very likely they share `cdninstagram.com` (same CDN domain, same media pipeline), which is why the shared-domain logic exists. Treat "same hosts" as the working assumption and test it (Capture plan C3).

## 2. Protocols

**QUIC / HTTP3 on Instagram iOS.** Meta's engineering post states QUIC is deployed on Instagram for iOS and Android, first tested on a small share then scaled, with metrics comparable to or better than the Facebook app; Facebook-app video saw up to 22 % better mean time between rebuffering, 8 % fewer video errors, 20 % fewer stalls; more than 75 % of Meta internet traffic used QUIC/HTTP3 as of that post **[S]** https://engineering.fb.com/2020/10/21/networking-traffic/how-facebook-is-bringing-quic-to-billions/ (per a page summary; the post does not break out Instagram share). The same post notes static content was still downloaded over TCP during testing, and lists true 0-RTT as future work **[S]**. mvfst is Meta's C++ IETF QUIC implementation, the foundation for Proxygen HTTP/3 **[S]** same post.

**Newer in-house mobile stack.** A Mobile @Scale talk page says Meta built its own mobile network stack in C on open-source libraries including ngtcp2 and nghttp3 (QUIC/HTTP3), with connection pooling, DNS resolution and caching, TCP and QUIC Happy Eyeballs; it has launched to Instagram; Meta's apps do not rely on the platform networking APIs **[S]** https://atscaleconference.com/?p=570422 (page summary). Consequences:
- Multiplexing: HTTP/2 and HTTP/3 carry multiple streams per connection **[S]** (Meta QUIC post). Connection pooling implies API, media and DM-media requests can share connections to the same origin **[I]**. Per-connection features would then be coarse, and your per-registrable-domain grouping is the right granularity, not per-5-tuple.
- DNS: the stack does its own DNS resolution and caching **[S]** (talk page). Whether it uses DoH or its own DNS server: **[?]**. The only hint is the unverified log that falls back to system `getaddrinfo()` **[W]**. Inference: lookups may be infrequent (cached) and may go via the OS resolver at times, so you cannot count on seeing a DNS answer per session **[I]**.
- TCP fallback / Happy Eyeballs exists in the stack **[S]**, and Meta's 2026 Live ingest post says the client picks TCP or QUIC per stream by whichever handshake wins and keeps it for the session, with TCP fallback when UDP/443 is blocked **[S]** https://engineering.fb.com/2026/10/12/video-engineering/shipping-media-over-quic-at-meta-scale-for-instagram-live-ingest/ (that post covers Live *ingest*, not reels playback; it does not say what viewers use).
- Pinning across app sections: **[?]** no source. Pooling suggests yes **[I]**.

**ECH / SNI in 2026.**
- RFC 9849 (ECH) and RFC 9848 (DNS bootstrap) were published March 2026 **[S]** https://isc.sans.edu/diary.html?date=2026-03-09 .
- 1.1 M active ECH deployments, 99.99 % Cloudflare; about one in five Firefox clients does ECH daily **[S]** Hajda et al., "The Fragile Privacy of Encrypted Client Hello", IFIP Networking 2026, https://dl.ifip.org/db/conf/networking/networking2026/1571261276.pdf (read from the PDF text).
- Same paper's client table: Firefox and Chrome yes, Safari (iOS, macOS) "experimental, disabled by default" **[S]**.
- Meta: a poster reports Meta as a second large ECH deployment whose servers support ECH but whose config is not exposed in DNS **[S]** https://www.inet.haw-hamburg.de/publications/mgsw-ptcve-25.html (summary). A client cannot normally use ECH without the config from DNS HTTPS records **[I]** (from how ECH bootstraps, RFC 9848), so Meta's choice not to publish it implies ordinary clients are not using ECH to Meta **[I]**.
- iOS: Apple exposes `sec_protocol_options_set_enable_encrypted_client_hello` but a developer forum thread says there is no system-wide switch to enable ECH for URLSession / CFNetwork / WebKit **[S]** https://developer.apple.com/forums/thread/842112 . Meta's app uses its own stack, not URLSession **[S]** above, so Apple's setting is moot for it.
- Does Meta use its own SNI-hiding scheme? **[?]** Nothing found. Not asserted either way.
- Conclusion: SNI very likely still visible for Instagram traffic in your capture **[I]**. Cheap to verify: Capture plan step 0.

## 3. Prefetching

- Instagram Reels uses an "adjacent preload" strategy: the Reel after the current one is kept ready in memory, in both swipe directions. Meta previously combined warmup with disk prefetch. Android Developers blog, March 2026 **[S]** https://android-developers.googleblog.com/2026/03/instagram-and-facebook-deliver-instant.html . Caveats: the post is about Android Media3; it gives no counts and no iOS statement. The post also says playback preloading pauses when I/O or CPU is under load.
- Whether reels prefetch from the home feed, from the Reels tab entry, or while in DMs: **[?]**. The pipeline README already lists this as a risk.
- Inference: during a reels session expect a download burst for the next reel while the current one is still playing, so bursts will not align with what is on screen **[I]**. Prefetch from Reels is indeed reel-like traffic that is *during* reel use, so that is fine; the harmful case is reel-shaped bursts in DMs or feed, untested.

## 4. Published classification work (what it shows, what it does not)

| Work | Finding | Relevance |
|---|---|---|
| Schuster, Shmatikov, Tromer, "Beauty and the Burst", USENIX Security 2017 | DASH segmentation makes bursts whose sizes depend on content; CNNs on burst sizes identify titles from YouTube, Netflix, Amazon, Vimeo **[S]** https://www.usenix.org/conference/usenixsecurity17/technical-sessions/presentation/schuster . From the full text: steady-state example fetching one segment every 5 s after a ~50 s initial buffering burst; samples of 60-90 s per stream; YouTube classifier ~99 % accuracy; classifier on a different network 98 % **[S]** (PDF copy https://users.wpi.edu/~kmus/ECE579M_files/ReadingMaterials/beautyburst[1827].pdf , text extracted by me). | Establishes ON/OFF burst structure of adaptive video. Time-to-decision is tens of seconds to minutes for *title* ID, a different problem. Long-form DASH, not vertical short video **[I]**. |
| "I Know What You Saw Last Minute", arXiv 1602.00490 | SVM on encrypted YouTube HAS; >95 % title accuracy, 10,000 streams over 100 titles **[S]** https://arxiv.org/abs/1602.00490 (abstract) | Title ID, not service ID. |
| Casas et al. style flow/buffer-state work, arXiv 1803.00303 | Random forests from IP packet arrival features with a small generic feature set identify YouTube flows and playback buffer state in real time, no DPI **[S]** https://arxiv.org/abs/1803.00303 (abstract; no feature list or window in the abstract) | Supports "video flow vs other" from timing/size only. |
| Pathmaperuma et al., Sensors 2022 (PMC9570541) | 92 in-app activities over 8 apps (Facebook 22, Instagram 20, Messenger 10, YouTube 9, WhatsApp 9, ...), 65,189 samples at 0.5 s windows; 48 features = 12 stats each for frame length and inter-arrival time, per direction; DNN; validation accuracy 93 % (0.5 s), 95 % (0.2 s), 91 % (0.05 s), 90 % (0.02 s); unknown-activity detection 79 % average; reject if top probability < 0.97; Instagram activities were often confused with Facebook ones **[S]** https://pmc.ncbi.nlm.nih.gov/articles/PMC9570541 (summary). | Closest to your task. Shows sub-second windows are feasible with richer per-direction features, **but** frame-level lab captures of known activities, not a mixed live stream, and no reels-vs-DM split is reported in what I read **[?]**. |
| AppScanner (Taylor et al., EuroS&P 2016) | 110 Google Play apps re-identified with >99 % accuracy; 2017 extension reports up to 96 % six months later **[S]** https://www.cs.ox.ac.uk/publications/publication11116-abstract.html (search-result summary). The package returns a label only above a confidence threshold (default 0.9) **[S]** https://pypi.org/project/appscanner . | App-level, not in-app action. Confidence-threshold-or-nothing matches your "winner must beat runner-up" design. |
| FlowPrint (van Ede et al., NDSS 2020) | Unsupervised app fingerprints from temporal correlation of destination features; 89.2 % app recognition on Android and iOS **[S]** https://research.utwente.nl/en/publications/flowprint-semi-supervised-mobile-app-fingerprinting-on-encrypted-/ (search summary) | Argues for using *which destinations co-occur in time* as a feature, relevant if reels and DMs open different host sets. |
| TripletViNet, arXiv 2407.10644 | Cross-platform video-traffic identification from content-specific VBR patterns **[S]** https://arxiv.org/pdf/2407.10644 (search summary) | Same-video-across-platforms; not a short-video service classifier. |
| Zaragoza instant-messaging study | Covers Instagram among nine messaging platforms; F1 from 0.62 (X) to 0.98 (WhatsApp); no Instagram-specific score visible in what I got **[S/?]** https://zaguan.unizar.es/record/170444 (snippet only; full text returned 403) | Messaging side; message type/direction inferable. |

Not found: any paper separating TikTok vs Reels vs Shorts vs DMs from flow shape. State this honestly in any write-up.

## 5. Feature suggestions for the 6-feature design

Everything here is **[I]** unless a source is named. The sourced parts only show that these feature families work in neighbouring problems.

Current: log bytes, log packets, mean size/1500, frac > 1200 B, downstream fraction, burstiness CV (per domain per 10 s).

Why that likely confuses reels and DM media: both are mostly large downstream packets on the same QUIC connection, and a 10 s window averages a 1-2 s photo burst with idle gaps into something between "reel" and "idle".

Proposed additions, in order of expected value:
1. **Sustained-rate duty cycle**: fraction of 1 s bins in the window with downstream bytes above, say, 100 kB/s. A reel plays continuously (high duty), a DM photo or video-open is one burst then silence. Sourced rationale: adaptive video shows ON/OFF segment fetching and a startup burst **[S]** Beauty and the Burst text above; short vertical videos may be fetched as one file rather than segments **[?]**, so test.
2. **Max single-burst bytes and number of bursts** (gap threshold 200-500 ms): DM photo = 1 burst; reels = several, each roughly one video's worth.
3. **Inter-burst gap median / CV** and **ON-OFF cycle durations**. Source support: burst-size sequences identify video **[S]**; for short video, the periodic structure will be swipe-driven, not a fixed 5 s cadence.
4. **Uplink packet rate and uplink/downlink ratio per burst**: reels scrolling sends small API/ACK uplink, DMs with typing send small MQTT publishes; DM media *sends* are uplink-heavy (rupload-style) **[S]** upload host exists. Pathmaperuma used per-direction statistics **[S]**.
5. **Concurrent distinct hosts / flows active in the window** (FlowPrint-style co-occurrence **[S]**). The MQTT connection is long-lived and low-rate, so its presence does not discriminate by itself, but a *new* media-host appearing does.
6. **Packet-size histogram** (a few bins, not just fraction > 1200) and **inter-arrival percentiles**, per direction. These are the families that gave 90 %+ in Pathmaperuma **[S]**.
7. **Cross-window state**: a 3-window (30 s) hold or hysteresis; reels sessions last tens of seconds to minutes, DM media opens last seconds. Also keep the last N windows' duty cycle.

Window length:
- 10 s windows with one summary vector is fine for service-level grouping but too coarse and too slow for reels vs DM media, and the 50 kB floor drops quiet DM windows (good) but also quiet reels (bad) **[I]**.
- Suggested: compute features on 1 s bins, decide every 1-2 s over a trailing 3-5 s window, require 2 consecutive agreeing decisions before stimulating. **[I]**. Basis for feasibility: Pathmaperuma reached 90 %+ at 0.2-0.5 s with ML on rich features **[S]**; Beauty and the Burst needed 60-90 s but for a harder task **[S]**. So 1-3 s decisions are plausible for "sustained video vs not" but unproven for "reel vs DM video" **[I]**. Treat as a hypothesis to test on your captures; report accuracy per window length.
- The startup burst is the most informative moment (Beauty and the Burst notes initial buffering at higher rate **[S]**). For short video the equivalent is the first 1-2 s after a swipe **[I]**.

## 6. iOS and tailnet confounders

- **Tailscale DNS and exit nodes.** Tailscale docs: with an exit node, DNS queries for all domains go to the exit node regardless of nameserver settings, unless "Use with exit node" is enabled per nameserver; public global nameservers (Cloudflare, Google) are queried over DoH automatically **[S]** https://tailscale.com/kb/1054/dns . Inference: the exit node resolves, so tshark on the exit node can see the client's DNS query, but if the exit node's upstream resolver is DoH, the *answer* is encrypted after leaving the node. Whether tshark sees the plaintext answer depends on where the capture point sits relative to the resolver **[I]**. Check by capturing on the tailnet interface and the WAN interface.
- **Exit-node routing scope.** Exit nodes capture all traffic not directed to a subnet router or app connector (default routes 0.0.0.0/0 and ::/0) **[S]** https://tailscale.com/kb/1103/exit-nodes . The page does not mention UDP/QUIC specifically; I would verify QUIC appears on the exit node **[I]**.
- **iOS 15-era report** that Tailscale overrides local DNS with exit nodes **[W]** https://forum.tailscale.com/t/ios-15-tailscale-overrides-local-dns-when-using-exit-nodes/1125 ; a recent iOS 18.4 / Tailscale 1.81 DNS failure with "Use Tailscale DNS" **[W]** https://forum.netgate.com/post/1213663 . Anecdotal.
- **iCloud Private Relay / Limit IP Address Tracking.** Apple says Private Relay protects Safari browsing and encrypts DNS records, can be disabled per network ("Limit IP Address Tracking"), and that third-party VPN or filtering apps can conflict **[S]** https://support.apple.com/en-us/102602 and https://support.apple.com/en-us/102022 . Apple's pages do not say it covers third-party apps like Instagram or what happens alongside a VPN profile **[?]**. Secondary sources say it does not cover all app traffic and turns off with a traditional VPN **[W]** https://andreafortuna.org/2026/06/19/apple-private-relay-dfir/ . Inference: it is unlikely to hit Instagram app traffic, but turn it off for the capture network to remove the variable **[I]**.
- **iOS DNS caching.** No source found **[?]**. Combined with Meta's own DNS cache **[S]**, expect no DNS answer when you reconnect to an already-resolved host **[I]**. This is why SNI and the HostMap's `p.dst` learning matter, and why a flow whose server IP was learned before capture started will be unnamed.
- **Connection reuse from before the exit node was enabled.** A long-lived QUIC or TCP connection started before the exit node was selected will break or migrate when the route changes (new source address). QUIC connection migration or a fresh handshake is expected **[I]**. Force app restart after enabling the exit node.
- **Other apps on the phone** share the tunnel; iMessage/iCloud, Photos upload and others add large flows to unrelated domains. Your per-registrable-domain grouping handles most of that, but large `icloud.com` / `apple.com` windows will be ignored only because they are not enrolled.

## Capture plan

Do each as its own capture file, one activity only, `tshark` column order of `packets.py:COLUMNS`. Name files so labels are recoverable. Keep notes of start/stop times and every action.

Setup (once):
- 0. **Check what's visible.** Enable the exit node, turn off iCloud Private Relay and Limit IP Address Tracking for that network, force-quit Instagram, then launch it and open the app. In the capture, check: (a) do you see TLS ClientHello with SNI to `*.instagram.com` / `*.cdninstagram.com`? (b) any QUIC Initial packets, and does tshark decode SNI from them (needs a recent tshark with QUIC decryption of Initial)? (c) any DNS answers for those names? (d) what UDP/443 vs TCP/443 split? Save the answers; they decide whether `HostMap` has any names to learn.
- Capture both the tailnet interface and the exit node's WAN interface for the first run, so you can see whether DNS and QUIC differ.

Exemplars (each: Wi-Fi only, screen on, other apps closed, notifications off, app **force-quit and relaunched** right after the exit node is enabled so DNS and handshakes happen inside the capture, then 10 s idle on the home screen to isolate login chatter):
- C1. **Reels only, 2-3 min**, Reels tab, swipe at natural pace, no likes, comments or DMs. Repeat a second 2 min where you watch 3 reels to the end each (long dwell).
- C2. **DMs text only, 2 min**, open a thread, send and receive 10+ short messages with a friend or second account, type for a while, check typing indicators.
- C3. **DMs with photos, 2 min**, send and open 5 photos, scroll back through old photos in a thread.
- C4. **DMs with video, 2 min**, send two short videos, open received videos, play a video from DM history; also forward a reel to a friend and open a reel someone sent you (this is the one most likely to resemble reels).
- C5. **Home feed scroll, 2 min**, with video posts in view, no tapping into reels.
- C6. **Stories, 2 min**.
- C7. **Mixed realistic 5 min**: reels 60 s, DMs 60 s, feed 60 s, reels 60 s, DM photo 60 s, with a spoken or written timeline of transitions (use a stopwatch, note switch times to within a second). This is the test set; do not enroll from it.
- C8. **Idle app 2 min** (app open on a profile, no scrolling), to see background chatter and the MQTT keepalive.
- C9. **Transitions**: 20 times, from DMs open a reel shared in the thread, then back out. Note times.
- C10. **TikTok 2 min** and **YouTube Shorts 2 min** (each in its own app or tab, same protocol), plus **Safari YouTube long video 2 min** for DASH contrast.
- Repeat C1 and C2 on a second day or network to test drift (CDN names `scontent-<pop>-N` rotate).

For each capture also save `tshark -z conv,tcp -z conv,udp` and the list of SNI values with byte counts, so you can see which hosts carry which activity before looking at features.

## Suggested classifier changes

Ordered by dependency on what the captures show:

1. **Before any code change, run C0-C4 and print, per capture, bytes by SNI and by registrable domain.** If reels and DMs media land on the same SNI and on the same connection, the domain route can only ever give you "Instagram", and the whole decision is shape. [I]
2. **Add a duty-cycle feature and a burst-count / max-burst feature** to the feature vector, with a version bump of `N_FEATURES`; existing saved buckets must be re-enrolled. Tied to **[S]** ON/OFF burst structure of adaptive video (Beauty and the Burst) and **[S]** per-direction size/IAT statistics (Pathmaperuma).
3. **Shorter decision granularity**: compute on 1 s bins and decide on a trailing 3-5 s window with two-in-a-row agreement; keep the 10 s window only for logging. Tied to **[S]** sub-second feasibility in Pathmaperuma, with the warning that it is lab data.
4. **Do not treat the 50 kB floor as per-10 s fixed.** A 3 s window at reel rate easily exceeds it; scale the floor by window length or you will never fire on short windows. [I]
5. **Keep abstaining**: the "beat the runner-up at 0.90 and be close in absolute terms" rule matches AppScanner's confidence-threshold-or-nothing and Pathmaperuma's 0.97 unknown threshold **[S]**. Keep it. Add a third bucket "ig_other" (feed, stories, idle, MQTT, API) with weight 0, so ambiguous windows have somewhere safe to go instead of being forced to reels or DMs. [I]
6. **Use the SNI-or-DNS name as a time-window feature, not only a group key**: the set of media hostnames active in the last 30 s (FlowPrint-style co-occurrence **[S]**). If reels use a host set DM media never touches (to be seen in captures), this is cheaper and stronger than shapes.
7. **Hold-off after a reel-like burst while in DMs**: only fire on shared-domain windows after N consecutive windows, to ride out prefetch **[I]** (prefetch of the next reel is sourced **[S]**; prefetch outside Reels is **[?]**).
8. **When the name is missing** (iOS/Meta DNS caching, QUIC SNI not decoded), the fallback `shape` branch with threshold 0.80 will fire on any large flow, including iCloud photo uploads and YouTube. Require a minimum duty cycle and an uplink/downlink ratio gate before the unnamed shape route can stimulate. [I]
9. **Hard-code nothing about `video-*` hostnames** until a capture shows them.

## Open questions

1. Do the Instagram iOS app's media requests show SNI at all in 2026, and does tshark decode QUIC Initial SNI on your build?
2. Do reel video and DM video share a hostname and a connection? (No source; Capture C4 answers it.)
3. Does the app prefetch reel video while in the feed or DMs? (Only Reels-tab adjacent preload is sourced, Android.)
4. Does Instagram iOS use `edge-chat.instagram.com`, `edge-mqtt.facebook.com` or `gateway.instagram.com` for the MQTT connection? Only web-client and unrelated listings were found.
5. Does Meta's stack use DoH or its own resolver, and how long are DNS results cached? Unsourced.
6. Are reels fetched as segmented DASH/HLS (periodic bursts) or as whole files? Determines how much the ON/OFF features help.
7. Does Tailscale's exit-node resolver on your node use DoH upstream, hiding DNS answers from tshark?
8. What does Private Relay do to Instagram app traffic on iOS? Apple's pages are silent.
9. What accuracy do richer features reach on your own captures, and at what window length? Nothing public answers this for reels vs DMs.

## Biggest risk

Reels and DM media probably use the same CDN domain, the same QUIC multiplexed connection and the same app-level connection pool, so name- and connection-level evidence cannot separate them, and your 10 s one-vector-per-domain summary blurs a DM photo or DM-opened video into something reel-like. Only the burst structure over time can, and no published work shows that works for this pair.
