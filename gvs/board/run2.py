from sim import run
from concurrent.futures import ProcessPoolExecutor
cases={
 'A max HV: full battery 4.2V, 45%, idle':dict(duty_boost=0.45,duty_stim=0,head_ohm=2200,bat=4.2),
 'B 1 mA into 2.2k dummy (3.9V, 40%)':dict(duty_boost=0.40,duty_stim=1.1/3.3,head_ohm=2200),
 'C 2 mA into 2.2k dummy (3.9V, 45%)':dict(duty_boost=0.45,duty_stim=2.2/3.3,head_ohm=2200),
 'D 2 mA into 4.7k (high skin R), low batt 3.6V, 45%':dict(duty_boost=0.45,duty_stim=2.2/3.3,head_ohm=4700,bat=3.6),
 'E fault: Q2 shorted, PWM 0, 4.2V 45%, 2.2k':dict(duty_boost=0.45,duty_stim=0,head_ohm=2200,bat=4.2,q2short=True),
}
def go(k): return k,run(tstop='300m',**cases[k])
with ProcessPoolExecutor(5) as ex:
    for k,r in ex.map(go,cases):
        ih=(r['vtop']-r['vbot'])/ {'A':2200,'B':2200,'C':2200,'D':4700,'E':2200}[k[0]]*1000
        print(f"{k}\n   HV={r['vhv']:.1f}V  I_head={ih:.3f}mA  SENSE={r['vsense']:.3f}V  D1 adc={r['vd1']:.3f}V (fw reads {r['vd1']*2/1.1:.3f}mA)  D2 adc={r['vd2']:.2f}V  batt draw={-r['ibat']*1000:.0f}mA")
