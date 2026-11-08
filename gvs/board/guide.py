import sys, base64, html; sys.path.insert(0,'.')
from layout import parts, bridges, jumpers, ext
HN={'T':'top pair, inner hole','U':'top pair, outer hole','V':'bottom pair, inner hole','W':'bottom pair, outer hole'}
def nm(h):
    s,c,r=h
    return f'S{s} col {c} {HN[r]}' if r in HN else f'S{s} {r}{c}'
def code(h): return f'<b>{nm(h)}</b>'
img=lambda p: ('data:image/webp;base64,' if p.endswith('webp') else 'data:image/png;base64,')+base64.b64encode(open(p,'rb').read()).decode()
steps=[]
G=lambda g,t: steps.append((g,t))
IMG={}
SECNAME={1:'Section 1 (top) — boost converter + relay 1',2:'Section 2 (middle) — XIAO + current sink',3:'Section 3 (bottom) — LM358 + relay 2'}
G('0 · Before you solder', 'Hold the board like the pictures: copper bus columns near the LEFT, XIAO in the middle section, USB pointing right.')
G('0 · Before you solder', 'Hole names: <b>S2 B10</b> = section 2, row B, column 10. Header holes are called <b>top/bottom pair, inner/outer</b> (inner = the one next to row A or E).')
G('0 · Before you solder', 'Beep test: col 4 (HV bus) to col 6 (GND bus) must <b>NOT</b> beep.')
BN={}; n={1:0,2:0,3:0}
for i,p in enumerate(bridges):
    sc=p[0][0]; n[sc]+=1; BN[i]=f'{sc}.{n[sc]}'
order={'rflat':0,'diode':1,'ind':2,'rstand':3,'film':4,'ecap':5,'npnv':6,'dip':7}
def part_text(nme,l,legs,k):
    if k=='rflat': return f'<b>{l}</b> resistor, lying flat: {code(legs[0][0])} and {code(legs[1][0])}.'
    if k=='rstand': return f'<b>{l}</b> resistor, standing up: body over {code(legs[0][0])}, top lead bent down into {code(legs[1][0])}.'
    if k=='diode':
        d={p:h for h,p in legs}; return f'<b>1N5819 diode</b>: stripe end in {code(d["K"])}, other end in {code(d["A"])}.'
    if k=='ind': return f'<b>1mH inductor</b> (green), either way round: {code(legs[0][0])} and {code(legs[1][0])}.'
    if k=='film': return f'<b>{l}</b> capacitor (red box), either way round: {code(legs[0][0])} and {code(legs[1][0])}.'
    if k=='ecap':
        d={p:h for h,p in legs}; return f'<b>{l}</b> electrolytic: <b>long leg (+)</b> in {code(d["+"])}, <b>stripe leg (−)</b> in {code(d["-"])}.'
    if k=='npnv':
        d={p:h for h,p in legs}; return f'<b>2N3904 ({nme})</b>: E in {code(d["E"])}, B in {code(d["B"])}, C in {code(d["C"])}. Flat face toward the LEFT.'
    if k=='dip':
        d={p:h for h,p in legs}; return f'<b>LM358</b>: pin 1 in {code(d["1"])}, pin 8 in {code(d["8"])}; notch/dot toward row E (down).'
for sec in (1,2,3):
    g=SECNAME[sec]; IMG[g]=sec
    for i,path in enumerate(bridges):
        if path[0][0]!=sec: continue
        G(g, f'<span class="tag">{BN[i]}</span> Back bridge: ' + ' → '.join(code(h) for h in path) + '.')
    pl=sorted([p for p in parts if p[3] in order and p[2][0][0][0]==sec], key=lambda p:order[p[3]])
    for p in pl: G(g, part_text(*p))
    for i,(a1,b1,lab) in enumerate(jumpers):
        if min(a1[0],b1[0])!=sec and not (a1[0]==sec and b1[0]==sec): 
            if not (a1[0]==sec and b1[0]!=sec and min(a1[0],b1[0])==sec): continue
        if a1[0]!=sec and b1[0]!=sec: continue
        if a1[0]!=b1[0] and sec!=min(a1[0],b1[0]): continue
        G(g, f'<span class="tag j">J{i+1}</span> Insulated wire <b>{html.escape(lab)}</b>: {code(a1)} → {code(b1)}.')
    for h,lab in ext:
        if h[0]==sec: G(g, f'<span class="tag o">off</span> <b>{html.escape(lab)}</b> wire into {code(h)}.')
G(SECNAME[1],'Battery: add a second wire on the XIAO BAT+ pad (already has the battery) and bring it to <b>S1 D18</b>.')
G(SECNAME[3],'Run the long wires (J11 battery, J12 GND) along the back so they don\'t block the USB-C port.')
G('4 · Relays, electrodes, kill switch', 'Relays sit in col 20, rows B/C/D. Read the labels by the pins: this layout assumes <b>S, +, −</b> top to bottom. If yours read <b>−, +, S</b>, swap that relay\'s S wire and GND wire.')
G('4 · Relays, electrodes, kill switch', 'Relay screw terminals: NO and NC wires go to the holes shown in section 2. <b>Relay 1 COM → kill switch → left electrode</b>. <b>Relay 2 COM → right electrode</b>.')
G('4 · Relays, electrodes, kill switch', 'Firmware: <code>RELAY_ACTIVE_LOW = false</code> (red module: jumper on H).')
for t in ['Beep <b>HV (col 4) ↔ GND (col 6)</b>: must NOT beep.',
          'Beep <b>BAT (S1 D18) ↔ GND</b>: must NOT beep.',
          'Beep <b>XIAO 5V pin ↔ BAT</b> and <b>5V ↔ GND</b>: must NOT beep.',
          'Beep <b>XIAO GND pin ↔ col 6</b>: MUST beep.',
          'Look over the back with a light: no solder blob touching a neighbouring pad, especially next to the header pairs.']:
    G('6 · Beep checks before power', t)
for t in ['Battery charged, USB to laptop, firmware flashed with <code>BOOST_PCT = 0</code>.',
          'Meter on HV ↔ GND: about 3.5–3.9 V (battery passing through).',
          'Tune the boost: <code>/boost?pct=5</code>, then +5% at a time until about 24 V on a full battery. Never above 28 V. Put the number in <code>BOOST_PCT</code>, reflash, then <code>/boost?pct=0</code>.',
          'Test 1: 2.2k resistor across the two electrode leads. <code>/pulse?ma=1&mode=dc&ms=3000</code> → about 2.2 V across the resistor (1 mA).',
          'Test 2: idle and reboot read 0 V across the resistor; <code>pol=1</code> flips the sign; the kill switch cuts it; <code>mode=sine&hz=0.5</code> → relays click, meter swings ±.',
          'Only after all of that: unplug USB, electrodes behind the ears, sit down, start at 0.5 mA.']:
    G('7 · First power-up', t)
groups=[]; 
for g,t in steps:
    if not groups or groups[-1][0]!=g: groups.append((g,[]))
    groups[-1][1].append(t)
body=[]; idx=0
for g,items in groups:
    body.append(f'<section><h2>{html.escape(g)}</h2>')
    if g in IMG:
        sc=IMG[g]; body.append(f'<p class="note">Front (parts):</p><img class="sec" alt="Section {sc} front" src="{img(f"S{sc}_front.webp")}"><p class="note">Back (solder side, flipped over sideways; tags match the steps):</p><img class="sec" alt="Section {sc} back" src="{img(f"S{sc}_back.webp")}">')
    body.append('<ul>')
    for t in items:
        body.append(f'<li><label><input type="checkbox" data-i="{idx}"><span>{t}</span></label></li>'); idx+=1
    body.append('</ul></section>')
total=idx
page=f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GVS perfboard build guide</title>
<style>
:root{{--bg:#faf9f6;--fg:#1f1e1c;--mut:#6b6a65;--line:#e4e1d8;--acc:#1d4f91;--ok:#2f7d32}}
@media (prefers-color-scheme:dark){{:root{{--bg:#191917;--fg:#ecebe6;--mut:#a3a19a;--line:#33322e;--acc:#7fb0f0;--ok:#7bc47f}}}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 -apple-system,system-ui,Segoe UI,Roboto,sans-serif}}
header{{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 16px;z-index:2}}
h1{{font-size:20px;margin:0}} .prog{{color:var(--mut);font-size:14px;margin-top:4px}} .bar{{height:6px;background:var(--line);border-radius:3px;margin-top:6px}} .bar i{{display:block;height:100%;width:0;background:var(--ok);border-radius:3px}}
main{{max-width:820px;margin:0 auto;padding:8px 16px 60px}}
h2{{font-size:17px;margin:26px 0 8px}} ul{{list-style:none;padding:0;margin:0}}
li{{border-bottom:1px solid var(--line)}} label{{display:flex;gap:12px;padding:10px 2px;cursor:pointer}}
input{{width:22px;height:22px;flex:none;margin-top:2px;accent-color:var(--ok)}}
input:checked+span{{color:var(--mut);text-decoration:line-through}}
img.sec{{width:100%;border-radius:8px;border:1px solid var(--line);margin:4px 0 10px}} .tag{{display:inline-block;min-width:34px;text-align:center;font-weight:700;font-size:13px;background:var(--fg);color:var(--bg);border-radius:5px;padding:0 5px;margin-right:4px}} .tag.j{{background:#7BC043;color:#10240a}} .tag.o{{background:#D85A30;color:#fff}} .imgs img{{width:100%;border-radius:8px;border:1px solid var(--line);margin:6px 0 14px}} .note{{color:var(--mut);font-size:14px}}
code{{font-size:13px;background:var(--line);padding:1px 4px;border-radius:4px}} details{{margin-top:10px}} summary{{cursor:pointer;font-weight:600}}
button{{font:inherit;padding:6px 12px;border:1px solid var(--line);background:transparent;color:var(--fg);border-radius:6px;margin-top:8px}}
</style></head><body>
<header><h1>GVS perfboard build guide</h1><div class="prog" id="prog"></div><div class="bar"><i id="bar"></i></div></header>
<main>
<p class="note">Particle FeatherWing Tripler · col 4 = HV bus · col 6 = GND bus · gold pairs = header pins (bussed between sections; only the XIAO and the listed jumpers touch them). Layout checked hole-by-hole against the circuit and simulated in ngspice (0 mA idle, 1 / 2 mA exact, 19.5 V max boost, shorted-transistor fault caught).</p>
<details><summary>Whole board with every wire (tap to open)</summary><img class="sec" alt="Whole board" src="{img('full_front.webp')}"></details><p class="note">Work one section at a time: back bridges first, then parts lowest to tallest, then insulated wires. Pinch the pictures to zoom; turn your phone sideways.</p>
{''.join(body)}
<button id="reset">Clear all ticks</button>
</main>
<script>
const KEY='gvs-build-v6', boxes=[...document.querySelectorAll('input[type=checkbox]')];
function load(){{try{{return JSON.parse(localStorage.getItem(KEY)||'[]')}}catch(e){{return []}}}}
function save(v){{try{{localStorage.setItem(KEY,JSON.stringify(v))}}catch(e){{}}}}
function upd(){{const n=boxes.filter(b=>b.checked).length;document.getElementById('prog').textContent=n+' / {total} steps done';document.getElementById('bar').style.width=(100*n/{total})+'%'}}
const s=load(); boxes.forEach(b=>{{b.checked=s.includes(+b.dataset.i);b.addEventListener('change',()=>{{save(boxes.filter(x=>x.checked).map(x=>+x.dataset.i));upd()}})}});
document.getElementById('reset').addEventListener('click',()=>{{boxes.forEach(b=>b.checked=false);save([]);upd()}});
upd();
</script></body></html>'''
open('build_guide.html','w').write(page)
print(total, len(page)//1024,'KB')
