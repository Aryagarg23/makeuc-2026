# Perfboard layout v3 for the Particle FeatherWing Tripler, XIAO mounted in S3's header rows.
# Holes: (section, col, row). Build rows 'A'..'E'. Header rows: 'U' top-outer, 'T' top-inner (next to A),
# 'V' bottom-inner (next to E), 'W' bottom-outer. Col 4 = HV bus, col 6 = GND bus (full board).
# Top header pairs (cols 3,5,7..18): T/U of S1, S2, S3 all joined per column. Bottom pairs (cols 7..18): V/W joined per column.
R='ABCDE'
TOPCOLS=[3,5]+list(range(7,19)); BOTCOLS=list(range(7,19))
def H(s,c,r): return (s,c,r)
parts=[]; bridges=[]; jumpers=[]; ext=[]
def P(name,label,legs,kind): parts.append((name,label,legs,kind))
def B(*holes): bridges.append(list(holes))
# ---------------- XIAO in S3, USB pointing RIGHT (off the col-20 edge), components facing up ----------------
top=['D6','D5','D4','D3','D2','D1','D0']      # cols 12..18 in S3 row T (top-inner)
bot=['D7','D8','D9','D10','3V3','GND','5V']    # cols 12..18 in S3 row W (bottom-outer)
P('XIAO','XIAO',[(H(3,12+i,'T'),p) for i,p in enumerate(top)]+[(H(3,12+i,'W'),p) for i,p in enumerate(bot)],'xiao')
# ---------------- Section 1: boost (v6 = as actually soldered, from photo) ----------------
s=1
P('R100k_d','100k',[(H(s,5,'A'),''),(H(s,9,'A'),'')],'rflat')
B(H(s,5,'A'),H(s,4,'A'))
P('R8k2','8.2k',[(H(s,8,'B'),''),(H(s,11,'A'),'')],'rflat')      # soldered diagonally
B(H(s,9,'A'),H(s,10,'A'),H(s,11,'A'))
jumpers.append((H(s,10,'A'),H(s,16,'T'),'D2'))
P('C47','47µF',[(H(s,5,'B'),'+'),(H(s,6,'B'),'-')],'ecap')
B(H(s,5,'B'),H(s,4,'B'))
B(*[H(s,c,'B') for c in range(6,14)])
P('Rbleed','10k',[(H(s,4,'W'),''),(H(s,6,'D'),'')],'rflat')   # as soldered: HV bus -> GND bus
P('D1N5819','1N5819',[(H(s,8,'D'),'K'),(H(s,12,'D'),'A')],'diode')
B(H(s,8,'D'),H(s,7,'D')); jumpers.append((H(s,7,'D'),H(s,4,'D'),'diode→HV'))
P('Q1','2N3904',[(H(s,13,'B'),'E'),(H(s,13,'C'),'B'),(H(s,13,'D'),'C')],'npnv')
P('Rpd','10k',[(H(s,12,'C'),''),(H(s,8,'C'),'')],'rflat')
B(H(s,8,'C'),H(s,8,'B'))
B(H(s,12,'C'),H(s,13,'C'),H(s,14,'C'))
P('R330','330Ω',[(H(s,14,'C'),''),(H(s,18,'C'),'')],'rflat')
B(H(s,18,'C'),H(s,17,'C')); jumpers.append((H(s,17,'C'),H(s,15,'V'),'D10'))
B(H(s,12,'D'),H(s,13,'D'),H(s,14,'D'))
P('L1','1mH',[(H(s,14,'D'),''),(H(s,18,'D'),'')],'ind')
B(H(s,18,'D'),H(s,19,'D'))
ext += [(H(s,19,'C'),'battery + (black wire)')]
# ---------------- Section 2: LM358 + input network ----------------
s=2
P('U1','LM358',[(H(s,9,'B'),'5'),(H(s,9,'C'),'6'),(H(s,9,'D'),'7'),(H(s,9,'E'),'8'),
                (H(s,12,'B'),'4'),(H(s,12,'C'),'3'),(H(s,12,'D'),'2'),(H(s,12,'E'),'1')],'dip')
B(*[H(s,c,'B') for c in range(6,15)])
B(H(s,9,'C'),H(s,9,'D'))
B(H(s,9,'E'),H(s,8,'E')); jumpers.append((H(s,8,'E'),H(s,4,'E'),'pin 8 → HV'))
P('C104','104',[(H(s,4,'D'),''),(H(s,6,'D'),'')],'film')
B(H(s,12,'C'),H(s,13,'C'),H(s,14,'C'),H(s,15,'C'))
P('C1u','1µF',[(H(s,13,'C'),'+'),(H(s,13,'B'),'-')],'ecap')
P('R10k_in','10k',[(H(s,15,'C'),''),(H(s,15,'A'),'')],'rstand')
B(H(s,14,'A'),H(s,15,'A'),H(s,15,'T'))             # D3 node -> header col 15 (= XIAO D3)
P('R100k_d3','100k',[(H(s,14,'A'),''),(H(s,14,'B'),'')],'rstand')
B(H(s,12,'D'),H(s,13,'D'),H(s,14,'D'))
B(H(s,12,'E'),H(s,13,'E'),H(s,14,'E'))
P('C103','103',[(H(s,13,'D'),''),(H(s,13,'E'),'')],'film')
P('R1k_fb','1k',[(H(s,14,'D'),''),(H(s,16,'D'),'')],'rstand')
P('R1k_b','1k',[(H(s,14,'E'),''),(H(s,16,'E'),'')],'rstand')
B(H(s,16,'D'),H(s,17,'D')); B(H(s,16,'E'),H(s,17,'E'))
jumpers.append((H(2,17,'D'),H(3,10,'B'),'to SENSE'))
jumpers.append((H(2,17,'E'),H(3,8,'D'),'to base'))
jumpers.append((H(2,17,'W'),H(2,6,'W'),'XIAO GND'))   # bottom header col 17 = XIAO GND
# ---------------- Section 3 (left half; XIAO covers cols 11-19) ----------------
s=3
P('Q2','2N3904',[(H(s,9,'C'),'E'),(H(s,9,'D'),'B'),(H(s,9,'E'),'C')],'npnv')
B(H(s,9,'C'),H(s,10,'C'),H(s,10,'B'),H(s,10,'A'))  # SENSE
B(H(s,9,'B'),H(s,9,'C'))
P('Rs','1k',[(H(s,8,'A'),''),(H(s,10,'A'),'')],'rstand')
B(H(s,7,'A'),H(s,8,'A'))
P('R100','100Ω',[(H(s,6,'A'),''),(H(s,7,'A'),'')],'rstand')
P('R100k_s','100k',[(H(s,7,'B'),''),(H(s,9,'B'),'')],'rstand')
B(H(s,7,'B'),H(s,7,'C'),H(s,7,'D'))
P('R100k_g','100k',[(H(s,7,'C'),''),(H(s,6,'C'),'')],'rstand')
jumpers.append((H(s,7,'D'),H(s,17,'U'),'D1'))
B(H(s,8,'D'),H(s,9,'D'))                            # base
B(H(s,8,'E'),H(s,9,'E'),H(s,10,'E'))                # BOTTOM
ext += [(H(s,8,'E'),'Relay 1 NC'),(H(s,10,'E'),'Relay 2 NC')]
P('R2k2','2.2k',[(H(s,2,'B'),''),(H(s,4,'B'),'')],'rstand')
B(H(s,2,'B'),H(s,1,'B'),H(s,1,'C'))                 # TOP
ext += [(H(s,1,'B'),'Relay 1 NO'),(H(s,1,'C'),'Relay 2 NO')]

# ---- user request: XIAO + current sink in the CENTER section, LM358 network in the BOTTOM section ----
_sw={1:1,2:3,3:2}
def _m(h): return (_sw[h[0]],h[1],h[2])
parts=[(n,l,[(_m(h),p) for h,p in legs],k) for n,l,legs,k in parts]
bridges=[[_m(h) for h in path] for path in bridges]
jumpers=[(_m(a),_m(b),lab) for a,b,lab in jumpers]
ext=[(_m(h),lab) for h,lab in ext]
def P(name,label,legs,kind): parts.append((name,label,legs,kind))
def B(*holes): bridges.append(list(holes))
# ---------------- Relay modules (as soldered): header pins in column 20, rows B/C/D, module off the RIGHT edge ----------------
# assumed pin order top->bottom: S, +, -   (swap the S and - jumpers if your module reads -, +, S)
P('K1','Relay 1',[(H(1,20,'B'),'S'),(H(1,20,'C'),'+'),(H(1,20,'D'),'-')],'relay')
B(H(1,20,'B'),H(1,20,'A')); jumpers.append((H(1,20,'A'),H(1,14,'U'),'D4'))
B(H(1,20,'C'),H(1,19,'C')); B(H(1,19,'C'),H(1,19,'D'))                      # + -> BAT strip
B(H(1,20,'D'),H(1,20,'E')); jumpers.append((H(1,20,'E'),H(1,17,'W'),'GND'))   # bottom header col 17 = XIAO GND
P('K2','Relay 2',[(H(3,20,'B'),'S'),(H(3,20,'C'),'+'),(H(3,20,'D'),'-')],'relay')
B(H(3,20,'B'),H(3,20,'A')); jumpers.append((H(3,20,'A'),H(3,13,'U'),'D5'))
B(H(3,20,'C'),H(3,19,'C')); jumpers.append((H(3,19,'C'),H(1,19,'D'),'BAT'))
B(H(3,20,'D'),H(3,20,'E')); jumpers.append((H(3,20,'E'),H(3,17,'V'),'GND'))
