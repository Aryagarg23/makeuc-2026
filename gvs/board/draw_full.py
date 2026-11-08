import sys, math, cairosvg; sys.path.insert(0,'/home/claude/perf')
from layout import parts, bridges, jumpers, ext, R, TOPCOLS, BOTCOLS
P=50; X0=420; Y0=270
ROWOFF={'U':-2,'T':-1,'A':0,'B':1,'C':2,'D':3,'E':4,'V':5,'W':6}
RLAB={'U':'top pair · outer','T':'top pair · inner','A':'A','B':'B','C':'C','D':'D','E':'E','V':'bottom pair · inner','W':'bottom pair · outer'}
INK='#2C2C2A'; HOLE='#8f8c84'; RED='#E24B4A'; BLU='#4d9be6'; ORG='#D85A30'; JG='#7BC043'; GOLD='#E8B04B'
TITLE={1:'S1 · TOP section — boost converter + relay 1',2:'S2 · MIDDLE section — XIAO + current sink',3:'S3 · BOTTOM section — LM358 + relay 2'}
# numbering shared with the checklist
BNUM={}; n={1:0,2:0,3:0}
for i,p in enumerate(bridges):
    s=p[0][0]; n[s]+=1; BNUM[i]=f'{s}.{n[s]}'
JNUM={i:f'J{i+1}' for i in range(len(jumpers))}
def nm(h):
    s,c,r=h; return f'S{s} {r}{c}' if r in R else f'S{s} col {c} {"top" if r in "UT" else "bot"} {"outer" if r in "UW" else "inner"}'
SH=560
SECS=(1,2,3)
def svg(sec,mirror):
    o=[]; a=o.append
    W,H=2350,260+3*SH+200
    def xy(h):
        s,c,r=h; c2=21-c if mirror else c
        return X0+(c2-1)*P, Y0+(s-1)*SH+(ROWOFF[r]+2)*P
    def T(x,y,s,sz=14,anc='start',w=400,fill=INK): a(f'<text x="{x}" y="{y}" font-size="{sz}" font-weight="{w}" text-anchor="{anc}" fill="{fill}" font-family="Helvetica,Arial,sans-serif">{s}</text>')
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><rect width="{W}" height="{H}" fill="#fff"/>')
    T(24,40,'Whole board — every part, bridge and wire',26,'start',700)
    T(24,68,('FRONT (parts side). Copper bus columns on the LEFT, USB of the XIAO points RIGHT.' if not mirror else 'BACK (solder side) — board flipped over sideways, so col 1 is now on the RIGHT. White = bare-wire bridge.'),15,'start',400,'#5F5E5A')
    for sec in SECS:
        bx1,_=xy((sec,1,'U')); bx2,_=xy((sec,20,'U')); xl,xr=min(bx1,bx2),max(bx1,bx2)
        _,yt=xy((sec,1,'U')); _,yb=xy((sec,1,'W'))
        a(f'<rect x="{xl-32}" y="{yt-30}" width="{xr-xl+64}" height="{yb-yt+60}" rx="12" fill="#1f1f1d"/>')
        # header pairs
        for cols,(r1,r2) in ((TOPCOLS,('U','T')),(BOTCOLS,('V','W'))):
            for c in cols:
                (x,y1),(_,y2)=xy((sec,c,r1)),xy((sec,c,r2))
                a(f'<rect x="{x-14}" y="{y1-14}" width="28" height="{y2-y1+28}" rx="14" fill="#3a2f18" stroke="{GOLD}" stroke-width="2"/>')
                for yy in (y1,y2): a(f'<circle cx="{x}" cy="{yy}" r="7" fill="none" stroke="{GOLD}" stroke-width="1.6"/>')
        for c in range(1,21):
            for r in (R+'TUVW' if c in (4,6) else R):
                x,y=xy((sec,c,r)); col=RED if c==4 else BLU if c==6 else HOLE
                a(f'<circle cx="{x}" cy="{y}" r="8" fill="none" stroke="{col}" stroke-width="{3 if c in (4,6) else 1.8}"/>')
        # column numbers top+bottom, row labels both sides
        for c in range(1,21):
            x,_=xy((sec,c,'A')); col=RED if c==4 else BLU if c==6 else INK
            T(x,yt-40,str(c),17,'middle',700,col); T(x,yb+56,str(c),17,'middle',700,col)
        x4,_=xy((sec,4,'A')); x6,_=xy((sec,6,'A'))
        T(x4,yb+76,'HV',12,'middle',700,RED); T(x6,yb+76,'GND',12,'middle',700,BLU)
        for r in 'UTABCDEVW':
            _,y=xy((sec,1,r)); big=r in R
            T(xl-44,y+5,RLAB[r] if not big else r,18 if big else 11,'end',700 if big else 400,INK if big else '#9a7a2c')
            T(xr+44,y+5,RLAB[r] if not big else r,18 if big else 11,'start',700 if big else 400,INK if big else '#9a7a2c')

        T(24,yt-40,f'S{sec}',30,'start',700,'#5F5E5A')
    # bridges (front: dashed hint, back: white)
    for i,path in enumerate(bridges):
        if path[0][0] not in SECS: continue
        pts=[xy(h) for h in path]; ps=' '.join(f'{x},{y}' for x,y in pts)
        if mirror:
            a(f'<polyline points="{ps}" fill="none" stroke="#F1EFE8" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>')
        else:
            a(f'<polyline points="{ps}" fill="none" stroke="#77756e" stroke-width="3" stroke-dasharray="5 5" stroke-linecap="round"/>')
    used=set()
    for _,_,legs,_ in parts:
        for h,_ in legs: used.add(h)
    for h,_ in ext: used.add(h)
    for a1,b1,_ in jumpers: used|={a1,b1}
    for h in used:
        if h[0] in SECS: x,y=xy(h); a(f'<circle cx="{x}" cy="{y}" r="6" fill="#F2C94C"/>')
    if mirror:
        for i,path in enumerate(bridges):
            if path[0][0] not in SECS: continue
            pts=[xy(h) for h in path]
            # tag at first point, nudged
            x,y=pts[0]; 
            a(f'<rect x="{x-21}" y="{y-34}" width="42" height="20" rx="5" fill="#fff" stroke="{INK}"/>'); T(x,y-19,BNUM[i],13,'middle',700,INK)
    if not mirror:
        for nme,l,legs,k in parts:
            if legs[0][0][0] not in SECS: continue
            pts=[xy(h) for h,_ in legs]
            if k in ('rflat','ind','diode'):
                (x1,y1),(x2,y2)=pts; mx,my=(x1+x2)/2,(y1+y2)/2; ang=math.degrees(math.atan2(y2-y1,x2-x1))
                a(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#bdbab0" stroke-width="3"/>')
                g=f'<g transform="translate({mx} {my}) rotate({ang:.1f})">'
                if k=='rflat': a(g+'<rect x="-28" y="-10" width="56" height="20" rx="8" fill="#D9C49A"/></g>')
                elif k=='ind': a(g+'<rect x="-30" y="-13" width="60" height="26" rx="11" fill="#639922"/></g>')
                else:
                    a(g+'<rect x="-30" y="-11" width="60" height="22" rx="4" fill="#111" stroke="#888"/></g>')
                    kx,ky=pts[0]; sx=mx+(kx-mx)*0.4
                    a(f'<g transform="translate({sx} {my}) rotate({ang:.1f})"><rect x="-4" y="-11" width="8" height="22" fill="#ddd"/></g>')
                T(mx,my+5,l,13,'middle',700,'#3a2a10' if k=='rflat' else '#fff')
            elif k=='rstand':
                (x1,y1),(x2,y2)=pts
                a(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#bdbab0" stroke-width="3"/>')
                a(f'<circle cx="{x1}" cy="{y1}" r="19" fill="#D9C49A" stroke="#712B13" stroke-width="2.5"/>')
                T(x1,y1+5,l,12,'middle',700,'#3a2a10')
            elif k=='ecap':
                (xp,yp),(xm,ym)=pts; mx,my=(xp+xm)/2,(yp+ym)/2
                a(f'<circle cx="{mx}" cy="{my}" r="21" fill="#111" stroke="#999" stroke-width="2"/>')
                T(mx,my+5,l,12,'middle',700,'#fff')
                dx,dy=xp-mx,yp-my; L=math.hypot(dx,dy) or 1
                T(xp+dx/L*16,yp+dy/L*16+6,'+',20,'middle',700,'#F2C94C')
            elif k=='film':
                (x1,y1),(x2,y2)=pts; mx,my=(x1+x2)/2,(y1+y2)/2
                if abs(y2-y1)>abs(x2-x1): a(f'<rect x="{mx-15}" y="{my-22}" width="30" height="44" rx="4" fill="#C0392B"/>')
                else: a(f'<rect x="{mx-30}" y="{my-14}" width="60" height="28" rx="4" fill="#C0392B"/>')
                T(mx,my+5,l,13,'middle',700,'#fff')
            elif k=='npnv':
                (xe,ye),(xb,yb_),(xc,yc)=pts
                a(f'<path d="M{xe-14} {ye-20} L{xe-14} {yc+20} Q{xe+26} {yc+20} {xe+26} {yb_} Q{xe+26} {ye-20} {xe-14} {ye-20} Z" fill="#111" stroke="#aaa" stroke-width="2"/>')
                a(f'<line x1="{xe-14}" y1="{ye-20}" x2="{xe-14}" y2="{yc+20}" stroke="#F2C94C" stroke-width="4"/>')
                for (x,y),t in zip(pts,'EBC'): T(x+13,y+6,t,15,'start',700,'#F2C94C')
                T(xe-22,yb_+5,'flat',11,'end',700,'#F2C94C')
            elif k=='dip':
                xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
                x1,x2,y1,y2=min(xs)-18,max(xs)+18,min(ys)-18,max(ys)+18
                a(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" rx="4" fill="#111" stroke="#888" stroke-width="2"/>')
                a(f'<path d="M{(x1+x2)/2-14} {y2} A14 14 0 0 1 {(x1+x2)/2+14} {y2}" fill="#666"/>')
                T((x1+x2)/2,(y1+y2)/2-6,'LM358',16,'middle',700,'#fff'); T((x1+x2)/2,(y1+y2)/2+14,'notch ↓ row E',11,'middle',400,'#bbb')
                for (x,y),(h,p) in zip(pts,legs): T(x+(-14 if x==min(xs) else 14),y+6,p,15,'end' if x==min(xs) else 'start',700,'#F2C94C')
            elif k=='relay':
                xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
                x1=max(xs)+75; x2=x1+190; y1=min(ys)-34; y2=max(ys)+34
                a(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" rx="8" fill="#1d4f91" stroke="#9cc3f0" stroke-width="2"/>')
                T(x1+48,y1+28,l,17,'start',700,'#fff'); T(x1+48,y1+50,'module hangs off',12,'start',400,'#dbe8fb'); T(x1+48,y1+66,'the right edge',12,'start',400,'#dbe8fb')
                for (x,y),(h,p) in zip(pts,legs): a(f'<line x1="{x}" y1="{y}" x2="{x1+8}" y2="{y}" stroke="#F2C94C" stroke-width="3"/>'); T(x1+16,y+6,p,17,'start',700,'#F2C94C')
            elif k=='xiao':
                xs=[xy(h)[0] for h,_ in legs]; ys=[xy(h)[1] for h,_ in legs]
                x1,x2,y1,y2=min(xs)-22,max(xs)+22,min(ys)-18,max(ys)+18
                a(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" rx="10" fill="#2d6a4f" opacity="0.6" stroke="#95d5b2" stroke-width="2.5"/>')
                a(f'<rect x="{x2-8}" y="{(y1+y2)/2-24}" width="38" height="48" rx="5" fill="#bbb"/>'); T(x2+36,(y1+y2)/2+5,'USB-C →',14,'start',700,'#95d5b2')
                T((x1+x2)/2,(y1+y2)/2-4,'XIAO ESP32-C3',20,'middle',700,'#fff'); T((x1+x2)/2,(y1+y2)/2+20,'chip side up · USB right',13,'middle',400,'#e0f2e9')
                for (h,p) in legs:
                    x,y=xy(h); a(f'<circle cx="{x}" cy="{y}" r="6" fill="#F2C94C"/>')
                    T(x,y+(28 if h[2]=='T' else -16),p,13,'middle',700,'#F2C94C')
        # jumpers
        xlist=[]; xc=[0]
        for i,(a1,b1,lab) in enumerate(jumpers):
            ins=[h for h in (a1,b1) if h[0] in SECS]
            if not ins: continue
            tag=f'{JNUM[i]} {lab}'
            if len(ins)==2:
                (x1,y1),(x2,y2)=xy(a1),xy(b1)
                cx,cy=(x1+x2)/2,min(y1,y2)-45 if abs(x2-x1)>P else (y1+y2)/2
                if a1[0]!=b1[0]: cx,cy=max(x1,x2)+90,(y1+y2)/2
                if (a1[2] in 'EVW' or b1[2] in 'EVW') and abs(x2-x1)<4*P and abs(y2-y1)<=P: cy=max(y1,y2)+30
                if abs(x2-x1)<=P and abs(y2-y1)<=P: cx+=40
                a(f'<path d="M{x1} {y1} Q{cx} {cy} {x2} {y2}" fill="none" stroke="{JG}" stroke-width="6" stroke-linecap="round" opacity="0.95"/>')
                tx,ty=(x1+2*cx+x2)/4,(y1+2*cy+y2)/4
                if a1[0]!=b1[0]:
                    tt=[0.3,0.55,0.8][xc[0]%3]; xc[0]+=1
                    tx=(1-tt)**2*x1+2*(1-tt)*tt*cx+tt*tt*x2; ty=(1-tt)**2*y1+2*(1-tt)*tt*cy+tt*tt*y2
                a(f'<rect x="{tx-len(tag)*4.3-6}" y="{ty-14}" width="{len(tag)*8.6+12}" height="21" rx="5" fill="{JG}"/>'); T(tx,ty+2,tag,13,'middle',700,'#10240a')
            else:
                h=ins[0]; other=b1 if h==a1 else a1
                x,y=xy(h); ex,ey=x+(-26 if h[2] in 'EVW' else 22), y+(26 if h[2] in 'EVW' else -26)
                a(f'<line x1="{x}" y1="{y}" x2="{ex}" y2="{ey}" stroke="{JG}" stroke-width="6" stroke-linecap="round"/>')
                a(f'<rect x="{ex-4}" y="{ey-12}" width="{len(JNUM[i])*9+10}" height="21" rx="5" fill="{JG}"/>'); T(ex+1,ey+4,JNUM[i],13,'start',700,'#10240a')
                xlist.append(f'{JNUM[i]} ({lab}): {nm(h)} here → {nm(other)}')
    offboard(a,T,xy,mirror)
    ly=H-36
    if not mirror: T(24,ly-20,'Grey dashed lines are bare-wire bridges on the BACK. Green = insulated wire you route (long ones on the back). Orange = flying wires to the relays, electrodes and battery.',15,'start',700,INK); T(24,ly,'Red col 4 = HV bus · Blue col 6 = GND bus · Gold pairs = header holes · Yellow dot = a leg goes here · Grey dashed = bridge on the back · Green = insulated jumper (J#) ',14,'start',400,INK)
    else: T(24,ly,'Tags (1.4 = section 1, bridge 4) match the checklist. Only join the holes on each white line — neighbouring lines must not touch.',14,'start',400,INK)
    a('</svg>'); return ''.join(o)

def offboard(a,T,xy,mirror):
    if mirror: return
    # relay terminal blocks (screw side), drawn right of each relay box
    term={}
    for sec,name in ((1,'Relay 1'),(3,'Relay 2')):
        x20,yB=xy((sec,20,'B')); _,yD=xy((sec,20,'D'))
        bx=x20+75+190
        a(f'<rect x="{bx}" y="{yB-34}" width="70" height="{yD-yB+68}" rx="6" fill="#2a5aa0" stroke="#9cc3f0" stroke-width="2"/>')
        for k,(lab,yy) in enumerate((('NO',yB),('COM',(yB+yD)/2),('NC',yD))):
            a(f'<circle cx="{bx+56}" cy="{yy}" r="9" fill="#ddd" stroke="#555"/>'); T(bx+6,yy+5,lab,13,'start',700,'#fff')
            term[(name,lab)]=(bx+56,yy)
    ORG2='#D85A30'; PUR='#8e44ad'
    def wire(p,q,col,lab=None,bend=0):
        (x1,y1),(x2,y2)=p,q
        cx=(x1+x2)/2+bend; cy=(y1+y2)/2
        a(f'<path d="M{x1} {y1} C{x1-60 if bend<0 else x1+60} {y1} {cx} {cy} {x2+40} {y2} L{x2} {y2}" fill="none" stroke="{col}" stroke-width="4" stroke-dasharray="10 6" stroke-linecap="round" opacity="0.9"/>')
    for h,lab in ext:
        if not lab.startswith('Relay'): continue
        rname,kind=lab.rsplit(' ',1); p=xy(h); q=term[(rname,kind)]
        col=ORG2 if rname=='Relay 1' else PUR
        x1,y1=p
        # route out to the left/bottom edge first so wires stay readable
        if h[1]<=2:
            mid=(p[0]-120,p[1])
            a(f'<path d="M{x1} {y1} L{mid[0]} {mid[1]} Q{mid[0]-80} {q[1] if rname=="Relay 2" else q[1]} {q[0]-300} {q[1]-(70 if kind=="NO" else 0)} " fill="none" stroke="none"/>')
        pts=[p]
        _,ygap=xy((2,1,'W')); ygap+=60
        if h[1]<=2:
            pts += [(x1-110,y1),(x1-110,(xy((1,1,'U'))[1]-80) if rname=='Relay 1' else (xy((3,1,'W'))[1]+90))]
        else:
            pts += [(x1, ygap+ (0 if h[1]==8 else 18)), (xy((1,1,'A'))[0]-140-(0 if h[1]==8 else 25), ygap+(0 if h[1]==8 else 18)),
                    (xy((1,1,'A'))[0]-140-(0 if h[1]==8 else 25), (xy((1,1,'U'))[1]-110) if rname=='Relay 1' else (xy((3,1,'W'))[1]+120))]
        xr=q[0]+100+(0 if kind=='NO' else 25)
        pts += [(xr,pts[-1][1]),(xr,q[1]),q]
        ps=' '.join(f'{x},{y}' for x,y in pts)
        a(f'<polyline points="{ps}" fill="none" stroke="{col}" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>')
        T(x1-14 if h[1]<=2 else x1+10, y1-12, f'{rname} {kind}',13,'end' if h[1]<=2 else 'start',700,col)
    # COM -> electrodes
    for rname,col,el,ks in (('Relay 1','#D85A30','LEFT electrode (behind left ear)',True),('Relay 2','#8e44ad','RIGHT electrode (behind right ear)',False)):
        x,y=term[(rname,'COM')]
        if ks:
            a(f'<line x1="{x}" y1="{y}" x2="{x+90}" y2="{y}" stroke="{col}" stroke-width="4"/>')
            a(f'<rect x="{x+90}" y="{y-20}" width="90" height="40" rx="6" fill="#fff" stroke="#c0392b" stroke-width="3"/>'); T(x+135,y+5,'KILL SW',13,'middle',700,'#c0392b')
            a(f'<line x1="{x+180}" y1="{y}" x2="{x+215}" y2="{y}" stroke="{col}" stroke-width="4"/>'); x0=x+215
        else:
            a(f'<line x1="{x}" y1="{y}" x2="{x+215}" y2="{y}" stroke="{col}" stroke-width="4"/>'); x0=x+215
        a(f'<circle cx="{x0+16}" cy="{y}" r="16" fill="#ccc" stroke="#555" stroke-width="2"/>')
        T(x0-60,y+40,el,13,'start',700,col)
    # battery
    xb,yb=xy((1,19,'C'))
    _,y2=xy((2,18,'W'))
    bx,by=xb+60,y2+20
    a(f'<rect x="{bx}" y="{by}" width="150" height="70" rx="8" fill="#c9c9c9" stroke="#777" stroke-width="2"/>'); T(bx+75,by+30,'LiPo 3.7 V',15,'middle',700,INK); T(bx+75,by+52,'on XIAO BAT pads',12,'middle',400,INK)
    a(f'<polyline points="{xb},{yb} {xb+30},{yb+30} {xb+30},{by+20} {bx},{by+20}" fill="none" stroke="#111" stroke-width="5" stroke-linejoin="round"/>')
    T(bx+160,by+30,'black wire: XIAO BAT+ pad',13,'start',700,'#111')
    T(bx+160,by+50,'→ S1 C19 (battery +)',13,'start',400,'#111')
import cairosvg
cairosvg.svg2png(bytestring=svg(0,False).encode(),write_to='/home/claude/perf/full_front.png',output_width=2580)
print('ok')
