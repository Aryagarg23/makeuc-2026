import sys; import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layout import *
par={}
def f(x):
    par.setdefault(x,x)
    while par[x]!=x: par[x]=par[par[x]]; x=par[x]
    return x
def u(a,b): par[f(a)]=f(b)
for s in (1,2,3):
    for r in list(R)+['T','U','V','W']:
        u((s,4,r),'HV'); u((s,6,r),'GND')
for c in TOPCOLS:
    for s in (1,2,3):
        for r in 'TU': u((s,c,r),('TOPHDR',c))
for c in BOTCOLS:
    for s in (1,2,3):
        for r in 'VW': u((s,c,r),('BOTHDR',c))
for path in bridges:
    for a,b in zip(path,path[1:]): u(a,b)
for a,b,_ in jumpers: u(a,b)
use={}; errs=[]
def occ(h,who):
    if h in use: errs.append(f'DOUBLE USE {h} {use[h]} {who}')
    use[h]=who
for n,l,legs,k in parts:
    for h,p in legs: occ(h,f'{n}.{p}')
for a,b,lab in jumpers: occ(a,'J:'+lab); occ(b,'J:'+lab)
for h,lab in ext: occ(h,'X:'+lab)
# holes under the XIAO body (S3 cols 11-19, rows T..W) may not hold anything but XIAO pins
for h,w in use.items():
    if h[0]==2 and 11<=h[1]<=19 and h[2] in 'ABCDEV' : errs.append(f'UNDER XIAO {h} {w}')
# header holes: only XIAO pins / taps on XIAO signal columns allowed
nets={}
for n,l,legs,k in parts:
    for i,(h,p) in enumerate(legs): nets.setdefault(f(h),[]).append(f'{n}.{p or i}')
for h,lab in ext: nets.setdefault(f(h),[]).append('['+lab+']')
if __name__=='__main__':
    print('\n'.join(errs) or 'no placement errors')
    for k,v in nets.items(): print(sorted(v))
