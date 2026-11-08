# Builds a SPICE netlist straight from the perfboard layout's connectivity and runs it in ngspice.
import sys, subprocess, re; sys.path.insert(0,'/home/claude/perf')
import check
from check import f, parts, ext
names={}
def N(h):
    r=f(h)
    if r==f('GND'): return '0'
    if r==f('HV'): return 'hv'
    if r not in names: names[r]=f'n{len(names)}'
    return names[r]
leg={}
for n,l,legs,k in parts:
    for i,(h,p) in enumerate(legs): leg[(n,p or str(i))]=N(h)
X={lab:N(h) for h,lab in ext}
for n,l,legs,k in parts:
    if n=='XIAO':
        for h,p in legs: X['XIAO '+p]=N(h)
X['XIAO BAT+']=X['battery + (black wire)']
assert X['XIAO GND']=='0', 'XIAO GND not on circuit ground!'
val={'R100k_d':'100k','R8k2':'8.2k','Rbleed':'10k','Rpd':'10k','R330':'330','R10k_in':'10k','R100k_d3':'100k',
     'R1k_fb':'1k','R1k_b':'1k','Rs':'1k','R100':'100','R100k_s':'100k','R100k_g':'100k','R2k2':'2.2k'}
def netlist(duty_boost, duty_stim, head_ohm, bat=3.9, tstop='400m', pol=0, q2short=False):
    L=['* auto-generated from perfboard layout',
       '.model Q2N3904 NPN(IS=6.734f XTI=3 EG=1.11 VAF=74.03 BF=416.4 NE=1.259 ISE=6.734f IKF=66.78m XTB=1.5 BR=.7371 NC=2 RC=1 CJC=3.638p MJC=.3085 VJC=.75 CJE=4.493p MJE=.2593 VJE=.75 TR=239.5n TF=301.2p ITF=.4 VTF=4 XTF=2 RB=10)',
       '.model D5819 D(IS=3.1u RS=0.05 N=1.0 CJO=110p M=0.5 BV=40 IBV=1m)',
       '.subckt LM358 inp inm vcc out',
       'G1 0 n1 inp inm 1m', 'R1 n1 0 100Meg', 'C1 n1 0 159p',
       'Bo o 0 V = max(min(V(n1), V(vcc)-1.5), 0.02)', 'Ro o out 50', 'Rq vcc 0 100k', '.ends']
    for n,(a,b) in [(k,(leg[(k,'0')],leg[(k,'1')])) for k in val]: L.append(f'R{n} {a} {b} {val[n]}')
    L.append(f"Cc47 {leg[('C47','+')]} {leg[('C47','-')]} 47u IC=0")
    L.append(f"Cc104 {leg[('C104','0')]} {leg[('C104','1')]} 100n")
    L.append(f"Cc1u {leg[('C1u','+')]} {leg[('C1u','-')]} 1u")
    L.append(f"Cc103 {leg[('C103','0')]} {leg[('C103','1')]} 10n")
    L.append(f"Dd1 {leg[('D1N5819','A')]} {leg[('D1N5819','K')]} D5819")
    L.append(f"Ll1 {leg[('L1','1')]} lx 1m"); L.append(f"Rdcr lx {leg[('L1','0')]} 25")
    for q in ('Q1','Q2'): L.append(f"Q{q} {leg[(q,'C')]} {leg[(q,'B')]} {leg[(q,'E')]} Q2N3904")
    if q2short: L.append(f"Rshort {leg[('Q2','C')]} {leg[('Q2','E')]} 1")
    L.append(f"XU1 {leg[('U1','3')]} {leg[('U1','2')]} {leg[('U1','8')]} {leg[('U1','1')]} LM358")
    # pins 5,6,7 (unused half) are tied off on the board; not simulated
    L.append(f"Vbat bat 0 {bat}"); L.append(f"Rbat bat {X['XIAO BAT+']} 0.2")
    T=50e-6
    def pwm(name,node,duty):
        if duty<=0: L.append(f'V{name} {node}x 0 0')
        else: L.append(f'V{name} {node}x 0 PULSE(0 3.3 0 20n 20n {duty*T-40e-9:.3e} {T})')
        L.append(f'R{name}o {node}x {node} 40')
    pwm('d10',X['XIAO D10'],duty_boost); pwm('d3',X['XIAO D3'],duty_stim)
    # relays: polarity 0 -> relay1 COM=NO(TOP), relay2 COM=NC(BOTTOM). Head (dummy resistor) between the COMs.
    top,bot=X['Relay 1 NO'],X['Relay 1 NC']
    if pol==0: L.append(f'Rhead {top} {bot} {head_ohm}')
    L += ['.options method=gear reltol=1e-3', f'.tran 1u {tstop} uic',
          '.control','run',
          f"meas tran vhv avg v(hv) from={float(tstop[:-1])*0.8e-3} to={float(tstop[:-1])*1e-3}",
          f"meas tran ihead avg i(Vmeas) from={float(tstop[:-1])*0.8e-3} to={float(tstop[:-1])*1e-3}" if False else '',
          f"meas tran vtop avg v({top}) from={float(tstop[:-1])*0.8e-3} to={float(tstop[:-1])*1e-3}",
          f"meas tran vbot avg v({bot}) from={float(tstop[:-1])*0.8e-3} to={float(tstop[:-1])*1e-3}",
          f"meas tran vsense avg v({leg[('Q2','E')]}) from={float(tstop[:-1])*0.8e-3} to={float(tstop[:-1])*1e-3}",
          f"meas tran vd1 avg v({X['XIAO D1']}) from={float(tstop[:-1])*0.8e-3} to={float(tstop[:-1])*1e-3}",
          f"meas tran vd2 avg v({X['XIAO D2']}) from={float(tstop[:-1])*0.8e-3} to={float(tstop[:-1])*1e-3}",
          f"meas tran vset avg v({leg[('U1','3')]}) from={float(tstop[:-1])*0.8e-3} to={float(tstop[:-1])*1e-3}",
          f"meas tran ibat avg i(Vbat) from={float(tstop[:-1])*0.8e-3} to={float(tstop[:-1])*1e-3}",
          f"meas tran icmax max i(Vbat) from={float(tstop[:-1])*0.8e-3} to={float(tstop[:-1])*1e-3}",
          'quit','.endc','.end']
    return '\n'.join(x for x in L if x)
def run(**kw):
    import os,uuid; fn=f'/tmp/c_{uuid.uuid4().hex}.cir'
    open(fn,'w').write(netlist(**kw))
    out=subprocess.run(['ngspice','-b',fn],capture_output=True,text=True,timeout=900).stdout
    r={}
    for m in re.finditer(r'^(\w+)\s+=\s+([-\d.e+]+)',out,re.M): r[m.group(1)]=float(m.group(2))
    if not r: print(out[-2000:])
    return r
