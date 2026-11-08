import re,cairosvg
src=open('draw_full.py').read().split("import cairosvg\ncairosvg.svg2png")[0]
ns={}; exec(src,ns)
base=ns['svg'](0,False)
P,X0,Y0,SH=50,420,270,560
RO={'U':-2,'T':-1,'A':0,'B':1,'C':2,'D':3,'E':4,'V':5,'W':6}
def xy(s,c,r): return X0+(c-1)*P, Y0+(s-1)*SH+(RO[r]+2)*P
o=[];a=o.append
def T(x,y,s,sz=17,w=400,fill='#2C2C2A',anc='start'): a(f'<text x="{x}" y="{y}" font-size="{sz}" font-weight="{w}" fill="{fill}" text-anchor="{anc}" font-family="Helvetica,Arial,sans-serif">{s}</text>')
a('<rect x="0" y="0" width="2350" height="2140" fill="#fff" opacity="0.55"/>')
# black probe: right stripe (col 6) whole length
x6,yt=xy(1,6,'U'); _,yb=xy(3,6,'W')
a(f'<rect x="{x6-16}" y="{yt-20}" width="32" height="{yb-yt+40}" rx="16" fill="#111" opacity="0.85"/>')
for s in (1,2,3):
    _,ym=xy(s,6,'C'); a(f'<rect x="{x6-60}" y="{ym-16}" width="120" height="32" rx="8" fill="#111"/>'); T(x6,ym+6,'BLACK',16,700,'#fff','middle')
pts=[('2',(2,17,'W'),'#1E9E3E'),('3',(2,18,'W'),'#E0322F'),('4',(1,20,'D'),'#1E9E3E'),('4',(3,20,'D'),'#1E9E3E'),('5',(1,20,'C'),'#E0322F'),('5',(3,20,'C'),'#E0322F')]
for lab,h,col in pts:
    x,y=xy(*h)
    a(f'<circle cx="{x}" cy="{y}" r="24" fill="{col}" stroke="#fff" stroke-width="4"/>'); T(x,y+8,lab,24,700,'#fff','middle')
W2=3000; tx=2380; ty=180
T(tx,ty,'Beep tests — step by step',30,700)
T(tx,ty+36,'Black probe: touch it anywhere on the BLACK stripe',19,700)
T(tx,ty+62,'Red probe: touch the numbered circle',19,700)
steps=[('2','#1E9E3E','XIAO bottom row, 2nd pin from the USB end','BEEP  (it is the XIAO ground)'),
('3','#E0322F','XIAO bottom row, pin right next to the USB end','NO beep  (it is 5V)'),
('4','#1E9E3E','Bottom pin where each relay plugs in (do both)','BEEP  (relay ground)'),
('5','#E0322F','Middle pin where each relay plugs in (do both)','NO beep  (relay power)')]
y=ty+130
for n,col,where,exp in steps:
    a(f'<circle cx="{tx+22}" cy="{y-8}" r="22" fill="{col}"/>'); T(tx+22,y,n,22,700,'#fff','middle')
    T(tx+58,y-6,where,19,700); T(tx+58,y+20,exp,19,700,col); y+=80
T(tx,y+10,'Green circle = should beep.  Red circle = should NOT beep.',17,400,'#5F5E5A')
T(tx,y+36,'If a red one beeps: stop and send a photo.',17,700,'#E0322F')
svg=base.replace('</svg>',''.join(o)+'</svg>')
svg=re.sub(r'width="2350" height="(\d+)" viewBox="0 0 2350 (\d+)"',lambda m:f'width="{W2}" height="{m.group(1)}" viewBox="0 0 {W2} {m.group(2)}"',svg,count=1)
svg=svg.replace('<rect width="2350"',f'<rect width="{W2}"',1).replace('Whole board — every part, bridge and wire','Where to put the probes')
cairosvg.svg2png(bytestring=svg.encode(),write_to='probe_steps.png',output_width=3000)
print('ok')
