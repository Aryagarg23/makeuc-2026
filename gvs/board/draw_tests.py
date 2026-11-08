import sys,re,cairosvg; sys.path.insert(0,'.')
import importlib.util
spec=importlib.util.spec_from_file_location('df','draw_full.py')
src=open('draw_full.py').read().split("import cairosvg\ncairosvg.svg2png")[0]
ns={}; exec(src,ns)
base=ns['svg'](0,False)
P,X0,Y0,SH=50,420,270,560
RO={'U':-2,'T':-1,'A':0,'B':1,'C':2,'D':3,'E':4,'V':5,'W':6}
def xy(s,c,r): return X0+(c-1)*P, Y0+(s-1)*SH+(RO[r]+2)*P
RED,GRN,BLU='#E0322F','#1E9E3E','#1F6FD1'
tests=[ # (kind, a, b, a_label, b_label, expect)
 ('read',(2,4,'A'),(2,6,'A'),'HV bus (col 4)','GND bus (col 6)','Ω mode: about 9 kΩ (0 = short!)'),
 ('no',(1,19,'D'),(1,6,'C'),'S1 D19 (battery net)','GND bus','NO beep'),
 ('no',(2,18,'W'),(2,6,'W'),'XIAO 5V pin','GND bus','NO beep'),
 ('no',(2,18,'W'),(2,4,'W'),'XIAO 5V pin','HV bus','NO beep'),
 ('no',(2,15,'W'),(1,19,'D'),'XIAO D10 pin','S1 D19 (battery net)','NO beep'),
 ('no',(2,8,'E'),(2,6,'E'),'S2 E8 (relay NC wire)','GND bus','NO beep'),
 ('yes',(2,17,'W'),(2,6,'V'),'XIAO GND pin','GND bus','BEEP'),
 ('yes',(3,8,'E'),(3,4,'E'),'S3 E8 (LM358 pin 8)','HV bus','BEEP'),
 ('yes',(3,12,'B'),(3,6,'A'),'S3 B12 (LM358 pin 4)','GND bus','BEEP'),
 ('yes',(1,20,'D'),(1,6,'E'),'Relay 1 − pin','GND bus','BEEP'),
 ('yes',(3,20,'D'),(3,6,'C'),'Relay 2 − pin','GND bus','BEEP'),
 ('yes',(1,20,'C'),(3,20,'C'),'Relay 1 + pin','Relay 2 + pin','BEEP'),
 ('yes',(1,20,'B'),(2,14,'T'),'Relay 1 S pin','XIAO D4 pin','BEEP'),
 ('yes',(3,20,'B'),(2,13,'T'),'Relay 2 S pin','XIAO D5 pin','BEEP'),
 ('yes',(2,15,'W'),(1,17,'C'),'XIAO D10 pin','S1 C17','BEEP'),
 ('yes',(2,16,'T'),(1,10,'A'),'XIAO D2 pin','S1 A10','BEEP'),
 ('yes',(2,17,'T'),(2,7,'D'),'XIAO D1 pin','S2 D7','BEEP'),
 ('yes',(2,15,'T'),(3,15,'A'),'XIAO D3 pin','S3 A15','BEEP'),
 ('read',(1,19,'D'),(1,4,'D'),'S1 D19 (RED probe)','HV bus (BLACK probe)','Diode mode: 0.2–0.4 V; swapped: OL'),
 ('read',(2,10,'B'),(2,6,'B'),'S2 B10 (sense)','GND bus','Ω mode: about 1.1 kΩ'),
 ('read',(2,1,'B'),(2,4,'B'),'S2 B1 (relay NO wire)','HV bus','Ω mode: about 2.2 kΩ'),
]
COL={'no':RED,'yes':GRN,'read':BLU}
o=[]; a=o.append
# fade the drawing a little so markers pop
a('<rect x="0" y="0" width="2350" height="2140" fill="#fff" opacity="0.35"/>')
offs={}
for i,(k,p,q,la,lb,ex) in enumerate(tests,1):
    for tag,h in (('a',p),('b',q)):
        x,y=xy(*h); n=offs.get(h,0); offs[h]=n+1
        dx,dy=[(0,0),(26,-26),(-26,-26),(26,26)][n%4]
        if n: a(f'<line x1="{x}" y1="{y}" x2="{x+dx}" y2="{y+dy}" stroke="{COL[k]}" stroke-width="3"/>')
        a(f'<circle cx="{x+dx}" cy="{y+dy}" r="17" fill="{COL[k]}" stroke="#fff" stroke-width="3"/>')
        a(f'<text x="{x+dx}" y="{y+dy+6}" font-size="{16 if i<10 else 14}" font-weight="700" text-anchor="middle" fill="#fff" font-family="Helvetica,Arial,sans-serif">{i}</text>')
# table on the right
tx=1850; ty=150
W2=2350+780
def T(x,y,s,sz=17,w=400,fill='#2C2C2A',anc='start'): a(f'<text x="{x}" y="{y}" font-size="{sz}" font-weight="{w}" fill="{fill}" text-anchor="{anc}" font-family="Helvetica,Arial,sans-serif">{s}</text>')
tx=2380
T(tx,ty,'Meter checks — touch one probe on each matching number',22,700)
T(tx,ty+30,'Battery wire to S1 D19 NOT added yet.  Red = must NOT beep · Green = must beep · Blue = read the value',14,400,'#5F5E5A')
y=ty+80
for i,(k,p,q,la,lb,ex) in enumerate(tests,1):
    a(f'<circle cx="{tx+16}" cy="{y-6}" r="15" fill="{COL[k]}"/>'); T(tx+16,y,str(i),15,700,'#fff','middle')
    T(tx+42,y,f'{la}  +  {lb}',17,700)
    T(tx+42,y+22,ex,15,700,COL[k])
    y+=58
T(tx,y+10,'Off the board (relays resting):',17,700)
T(tx,y+34,'• each relay COM to its NC terminal: BEEP · COM to NO: no beep',15)
T(tx,y+56,'• kill switch OFF: left electrode to relay 1 COM: no beep',15)
T(tx,y+78,'XIAO pins can read a little odd because the battery is on it — fine.',14,400,'#5F5E5A')
svg=base.replace('</svg>',''.join(o)+'</svg>')
svg=re.sub(r'width="2350" height="(\d+)" viewBox="0 0 2350 (\d+)"',lambda m:f'width="{W2}" height="{m.group(1)}" viewBox="0 0 {W2} {m.group(2)}"',svg,count=1)
svg=svg.replace('<rect width="2350"',f'<rect width="{W2}"',1)
svg=svg.replace('Whole board — every part, bridge and wire','Test points — every pair to check')
cairosvg.svg2png(bytestring=svg.encode(),write_to='test_points.png',output_width=3200)
print('ok')
