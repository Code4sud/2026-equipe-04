import bpy, os, sys, math
from math import sin,cos,pi,radians as rad
from mathutils import Quaternion as Q, Vector as V, Euler, Matrix
S=os.path.dirname(os.path.abspath(bpy.data.filepath))
ao=bpy.data.objects['Neo']; arm=ao.data; face=bpy.data.objects['Fox_Face']; keys=face.data.shape_keys
FPS=30; bpy.context.scene.render.fps=FPS
bones=sorted(arm.bones,key=lambda b:len(b.parent_recursive)); PAR={b.name:b.parent.name if b.parent else None for b in bones}
RP={b.name:b.head_local.copy() for b in bones}; RT={b.name:b.tail_local.copy() for b in bones}; RQ={b.name:b.matrix_local.to_quaternion() for b in bones}
ID=Q()
E=lambda x=0,y=0,z=0:Euler((rad(x),rad(y),rad(z)),'XYZ').to_quaternion()
mq=lambda q:Q((q.w,q.x,-q.y,-q.z)); mv=lambda v:V((-v[0],v[1],v[2]))
S1=lambda u,n=1,p=0:sin(2*pi*(n*u+p))
def frame(x,th):
    X=V(x).normalized(); T=V(th); T=(T-T.dot(X)*X).normalized(); Y=-T; Z=X.cross(Y)
    return Matrix((X,Y,Z)).transposed().to_quaternion()
def pulse(u,c,w):
    d=abs((u-c+.5)%1-.5); return max(0,1-(d/w))**1 if d<w else 0
def bump(u,c,hold,ramp):
    d=abs((u-c+.5)%1-.5)
    if d<hold: return 1
    if d<hold+ramp:
        t=1-(d-hold)/ramp; return t*t*(3-2*t)
    return 0
def blink(u,T,times,w=.075):
    return min(1,sum(bump(u,c,.012/T,w/T) for c in times))
def steps(u,pts,r=.018):
    # periodic piecewise-constant gaze with soft transitions; pts=[(start,(x,z)),...]
    n=len(pts); out=[0,0]
    for i,(c,v) in enumerate(pts):
        e=pts[(i+1)%n][0]; L=(e-c)%1 or 1; d=(u-c)%1
        k=min(1,d/r)*(1-max(0,(d-L)/r)) if d<L+r else max(0,1-(d-L+1)/r) if False else (min(1,d/r) if d<L else max(0,1-(d-L)/r) if d<L+r else 0)
        k=k*k*(3-2*k); out[0]+=v[0]*k; out[1]+=v[1]*k
    return out
class P:
    def __init__(s): s.L={}; s.hip=V((0,0,0)); s.arm={}; s.eye=(0,0); s.m={k:0 for k in('blink','joy','eyes_smile','mouth_talk','mouth_wide','glint','card_show')}; s.loc={}; s.foot={}; s.card=None
    def r(s,b,q,sym=False):
        if sym:
            s.r(b+'.L',q); s.r(b+'.R',mq(q)); return
        s.L[b]=s.L.get(b,ID)@q
    def both(s,b,ql,qr=None):
        s.r(b+'.L',ql); s.r(b+'.R',mq(qr if qr is not None else ql))
def fingers(p,side,curl,thumb=None,spread=0):
    m=(lambda q:q) if side=='L' else mq
    for i,f in enumerate(('index','middle','pinky')):
        c=curl[i] if isinstance(curl,(tuple,list)) else curl
        p.r(f'{f}1.{side}',m(E(0,c,spread*(1-i)))); p.r(f'{f}2.{side}',m(E(0,c*1.05,0)))
    if thumb is not None:
        p.r(f'thumb1.{side}',m(thumb[0])); p.r(f'thumb2.{side}',m(thumb[1]))
def solve(p):
    Wq={};Wp={};L=dict(p.L)
    def fk(b):
        pa=PAR[b]; q=L.get(b,ID)
        if pa is None: Wq[b]=q; Wp[b]=RP[b].copy(); return
        Wq[b]=Wq[pa]@q; Wp[b]=Wp[pa]+Wq[pa]@(RP[b]-RP[pa])
        if b=='hips': Wp[b]+=p.hip
    def ik(up,lo,end,T,pole):
        fk(up); Sx=Wp[up]; a=(RP[lo]-RP[up]).length; b=(RP[end]-RP[lo]).length; d=T-Sx; D=max(abs(a-b)+1e-3,min(d.length,(a+b)*.995)); dn=d.normalized()
        x=(a*a-b*b+D*D)/(2*D); h=math.sqrt(max(a*a-x*x,0)); pp=pole-Sx; pp=(pp-pp.dot(dn)*dn).normalized()
        El=Sx+dn*x+pp*h; Tt=Sx+dn*D
        q1=(RP[lo]-RP[up]).normalized().rotation_difference((El-Sx).normalized())
        q2=(RP[end]-RP[lo]).normalized().rotation_difference((Tt-El).normalized())
        L[up]=Wq[PAR[up]].inverted()@q1; fk(up); L[lo]=q1.inverted()@q2; fk(lo); return q2
    skip=set()
    for s,(Tf,pole,hq) in p.arm.items(): skip|={f'upperarm.{s}',f'forearm.{s}',f'hand.{s}'}
    for s_ in 'LR': skip|={f'thigh.{s_}',f'shin.{s_}',f'foot.{s_}'}
    pend=[]
    for b in bones:
        n=b.name
        if n in skip or (PAR[n] in Wq)==False and PAR[n] is not None: pend.append(n); continue
        fk(n)
    for s_ in 'LR':
        M_=(lambda v:V(v)) if s_=='L' else mv
        ft=p.foot.get(s_); T_=M_(ft[0]) if ft else RP[f'foot.{s_}'].copy(); po_=M_(ft[1]) if ft else RP[f'shin.{s_}']+V((0,-.5,0)); fq=(ft[2] if s_=='L' else mq(ft[2])) if ft else ID
        q=ik(f'thigh.{s_}',f'shin.{s_}',f'foot.{s_}',T_,po_)
        L[f'foot.{s_}']=q.inverted()@fq; fk(f'foot.{s_}')
    for s,(Tf,pole,hq) in p.arm.items():
        M=(lambda v:V(v)) if s=='L' else mv
        T=M(Tf(Wp,Wq,M) if callable(Tf) else Tf); q=ik(f'upperarm.{s}',f'forearm.{s}',f'hand.{s}',T,M(pole))
        h=hq if s=='L' else mq(hq); L[f'hand.{s}']=q.inverted()@h; fk(f'hand.{s}')
    for n in pend:
        if n not in Wq: fk(n)
    p.cardpos=None
    if p.card:
        grip=(RP['middle1.R']-RP['hand.R'])*1.05+V((0,-.03,-.02))
        p.cardpos=p.card.get('pos') or Wp['hand.R']+Wq['hand.R']@grip
        p.cardpos=V(p.cardpos); L['card']=p.card.get('q',ID)
    return L,Wp
REL=lambda:((.335,-.20,-.205),(.9,.35,.15),frame((.08,-.14,-1),(0,-1,.0)))
def common(p,u,T,tail=1,ears=1,breath=1):
    p.r('chest',E(1.1*breath*S1(u,2),0,0)); p.hip=V((0,0,.003*breath*S1(u,2,.25)))
    for i in range(1,6):
        a=(3+i*1.5)*tail; p.r(f'tail{i}',E(a*.25*S1(u,1,-i*.07),a*.25*S1(u,2,-i*.06),a*S1(u,2,-i*.07)))
    p.both('ear1',E(0,1.8*ears*S1(u,2,.1),0),E(0,1.8*ears*S1(u,2,.3)))
    p.both('ear2',E(0,3*ears*S1(u,2,0),0),E(0,3*ears*S1(u,2,.2)))
    for s in 'LR': fingers(p,s,22)
def sm(t): t=max(0,min(1,t)); return t*t*(3-2*t)
def lerp(a,b,t):
    if isinstance(a,Q): return a.slerp(b,t)
    if callable(a) or callable(b):
        return lambda W,R,M:(lambda x,y:tuple(x[i]+(y[i]-x[i])*t for i in range(3)))(a(W,R,M) if callable(a) else a,b(W,R,M) if callable(b) else b)
    if isinstance(a,(tuple,list,V)): return tuple(a[i]+(b[i]-a[i])*t for i in range(len(a)))
    return a+(b-a)*t
def K(u,pts):
    if u<=pts[0][0]: return pts[0][1]
    for (t0,a),(t1,b) in zip(pts,pts[1:]):
        if u<=t1: return lerp(a,b,sm((u-t0)/(t1-t0))) if t1>t0 else b
    return pts[-1][1]
def AK(u,pts):
    return tuple(K(u,[(q[0],q[i]) for q in pts]) for i in (1,2,3))
def hd(v): return lambda W,R,M:tuple(M(W['head']+R['head']@M(V(v))))
def per(u,c,h,r): return bump(u,c,h,r)
A0=lambda:REL()
PALM=lambda x=.25,y=-.9,z=.15:frame((x,y,z),(1,.1,0))
POLE=(.95,.35,-.5)
THUMB=frame((-.34,-.92,.12),(.05,-.05,1))
HOLD=((.30,-.50,.03),(.9,.1,-.6),frame((-.1,-.72,.68),(-.8,-.45,-.35)))
PACK=((.315,.05,.03),(1,-.2,.25),frame((-.15,.85,-.4),(0,0,1)))
def thumbs(p,s='R'):
    fingers(p,s,72,thumb=(E(0,0,-52),E(0,0,6)))
    m=(lambda q:q) if s=='L' else mq
    for f in('index','middle','pinky'): p.r(f'{f}2.{s}',m(E(0,12,0)))
def openh(p,s,c=-12,sp=6): fingers(p,s,c,thumb=(E(0,0,10),E(0,0,5)),spread=sp)
def pinch(p,s='R'): fingers(p,s,(28,34,40),thumb=(E(0,18,-18),E(0,14,0)))
def face(p,u,T,sm_=.28,bl=(.2,.62)):
    p.m['eyes_smile']=sm_; p.m['blink']=blink(u,T,bl)
def repos(u,T,p):
    common(p,u,T,tail=.8,ears=.8); p.hip=V((.006*S1(u,1),0,.003*S1(u,3,.25)))
    look=K(u,[(.16,0),(.21,1),(.3,1),(.35,0),(.62,0),(.67,-1),(.76,-1),(.81,0)])
    p.r('spine',E(0,.8*S1(u,1),1.2*S1(u,1,.2))); p.r('neck',E(0,0,5*look)); p.r('head',E(-1+1.2*S1(u,2),1.2*S1(u,1,.1),11*look))
    g=K(u,[(.42,0),(.47,1),(.56,1),(.61,0)]); tug=.018*max(0,S1(u,9))*g
    t,po,h=A0(); st=((.185,-.345,.115-tug),(.9,.2,-.5),frame((-.3,-.2,.93),(-.7,-.7,-.2)))
    p.arm['R']=tuple(lerp(a,b,g) for a,b in zip((t,po,h),st)); fingers(p,'R',22*g)
    p.arm['L']=(t,po,h); face(p,u,T,.2,(.08,.39,.44,.72,.93)); p.eye=(.009*look,.001)
def salut(u,T,p):
    common(p,u,T,tail=1.2,ears=1.1)
    st=K(u,[(0,0),(.1,0),(.26,1),(.76,1),(.92,0),(1,0)]); lift=max(0,S1(min(max((u-.1)/.16,0),1)/2))+max(0,S1(min(max((u-.76)/.16,0),1)/2))
    p.hip=V((0,-.055*st,-.012*st+.006*lift))
    p.foot['L']=((.15,-.14-.11*st,-.76+.035*lift),(.135,-.8,-.52),ID)
    w=K(u,[(.14,0),(.32,1),(.72,1),(.9,0)]); sw=S1(u,4.5)*w
    p.r('chest',E(-1,0,3*w)); p.r('head',E(-2*w,3*sw*.4,-5*w+1.5*sw))
    t,po,h=A0(); up=((.43+.03*sw,-.25,.47),(1,.2,-.7),frame((.05+.42*sw,-.12,1),(-1,0,0)))
    p.arm['R']=tuple(lerp(a,b,w) for a,b in zip((t,po,h),up)); openh(p,'R',-12*w,6*w); p.arm['L']=(t,po,h)
    p.m['mouth_wide']=.55*K(u,[(.1,0),(.28,1),(.74,1),(.92,0)]); p.m['eyes_smile']=.2+.35*w; p.m['blink']=blink(u,T,(.55,))
def ecoute(u,T,p):
    common(p,u,T,tail=.6,ears=.9); n=bump(u,.16,.0,.055)+bump(u,.5,.0,.055)+bump(u,.59,.0,.05)+bump(u,.86,.0,.055)
    p.r('neck',E(1,0,0)); p.r('head',E(2+5*n,1.5*S1(u,1),2.5*S1(u,1,.2))); p.r('head',E(0,9,0)); p.r('spine',E(1.5,0,0)); p.r('chest',E(1,1.5,0))
    p.both('ear1',E(0,-4,0),E(0,-1,0)); t,po,h=A0(); p.arm['R']=(t,po,h); p.arm['L']=(t,po,h)
    face(p,u,T,.3,(.1,.42,.72)); p.eye=(0,.002)
def reflexion(u,T,p):
    common(p,u,T,tail=.7,ears=.8); c=K(u,[(0,0),(.46,0),(.56,1),(.92,1),(1,0)]); sw=S1(u,1)
    p.r('neck',E(-3+1*c,0,-2+1*c)); p.r('head',E(-15+6*c+1.4*S1(u,2,.1),-7+4*c+1.2*sw,-11+1*c+2.5*S1(u,1,.2))); p.r('spine',E(-1.2,-1+.8*sw,-3)); p.r('chest',E(-1.2,-1.5,-2))
    p.r('clavicle.R',mq(E(0,-13*(1-c),-3)))
    s=S1(u,18)*(1-c); s2=S1(u,18,.25)*(1-c); tap=max(0,S1(u,24))*c
    a=hd((.385,.13+.006*s,.155+.007*s2)); b=hd((.135,-.335,-.075+.008*tap))
    h=lerp(frame((-.60,.08,.80),(-.72,-.25,-.55)),frame((-.72,-.25,.62),(-.15,-.9,.4)),c); p.arm['R']=(lerp(a,b,c),lerp((1.,.1,.05),(.8,.2,-.75),c),h)
    fc=38+13*s; fingers(p,'R',(fc-22*c-12*tap,fc+18*c,fc+18*c),thumb=(E(0,18,-14),E(0,10,0)))
    t,po,hh=A0(); p.arm['L']=((t[0],t[1]-.02,t[2]+.01),po,hh); p.eye=(.010-.004*c,.0145-.003*c); p.m['eyes_smile']=.38; p.m['blink']=blink(u,T,(.3,.76)); p.m['mouth_talk']=.05
def talking(u,T,p,v):
    common(p,u,T); n1,n2={1:(3,5),2:(2,4),3:(4,3)}[v]; g=S1(u,n1,.05*v); g2=S1(u,n2,.2)
    p.r('head',E(2.6*S1(u,n2+1,.1)-1,1.8*S1(u,2,.2),(5 if v!=2 else -5)*S1(u,2)+2*S1(u,3,.4))); p.r('neck',E(1*S1(u,3),0,2*S1(u,2,.05))); p.r('spine',E(1,1.2*S1(u,1),2*S1(u,1,.15)))
    if v==1:
        p.arm['R']=((.30+.03*g,-.40+.02*g2,.00+.03*g),POLE,PALM()); p.arm['L']=((.31-.02*g,-.38,-.03-.025*g),POLE,PALM(.3))
    elif v==2:
        p.arm['R']=((.27+.05*g,-.42,.05+.04*g2),POLE,PALM(.05,-.9,.25)); t,po,h=A0(); p.arm['L']=((t[0],t[1]-.03,t[2]+.015),po,h)
    else:
        w=.5+.5*g; p.arm['R']=((.33+.08*w,-.36,-.02+.05*w),POLE,PALM(.45,-.8,.15)); p.arm['L']=((.41-.08*w,-.36,.03-.05*w),POLE,PALM(.45,-.8,.15))
    for s in 'RL':
        if s in p.arm and p.arm[s][1] is POLE: openh(p,s,-15+4*g)
    env=1-.95*bump(u,.47,.018,.03)-.95*bump(u,.97,.018,.03); m=max(0,.46+.34*S1(u,23)+.26*S1(u,31,.3)+.14*S1(u,13,.6)); p.m['mouth_talk']=min(.95,m)*env
    p.m['blink']=blink(u,T,(.14,.52,.57,.82)); p.m['eyes_smile']=.24; p.eye=steps(u,[(0,(0,0)),(.24,(.0075,.002)),(.41,(0,0)),(.66,(-.0075,.002)),(.83,(0,0))])
def parle1(u,T,p): talking(u,T,p,1)
def parle2(u,T,p): talking(u,T,p,2)
def parle3(u,T,p): talking(u,T,p,3)
def pas_grave(u,T,p):
    common(p,u,T,ears=1.1); e=K(u,[(0,0),(.2,1),(.34,.72),(.48,1),(.74,1),(1,0)])
    p.both('clavicle',E(0,-11*e,0)); p.r('chest',E(-1.5*e)); p.r('head',E(-2*e,6*e,5*e)); t,po,h=A0()
    for s,x in(('L',.40),('R',.40)):
        p.arm[s]=tuple(lerp(a,b,e) for a,b in zip((t,po,h),((x,-.33,-.03),POLE,PALM(.6,-.75,.08)))); openh(p,s,-14*e,6*e)
    p.m['mouth_wide']=.42*e; p.m['eyes_smile']=.2+.32*e; p.m['blink']=blink(u,T,(.6,))
def pas_mal(u,T,p):
    common(p,u,T,ears=1.1); e=K(u,[(0,0),(.22,1),(.78,1),(1,0)]); b=K(u,[(.05,0),(.2,1),(.42,1),(.62,0)])
    n=bump(u,.48,0,.07)+bump(u,.62,0,.07); p.hip=V((0,.018*b,0)); p.r('spine',E(-4*b)); p.r('chest',E(-3*b)); p.r('head',E(-4*b+6*n,0,3*e))
    t,po,h=A0(); p.arm['R']=tuple(lerp(a,c,e) for a,c in zip((t,po,h),((.27,-.39,.00),(.95,.1,-.55),THUMB)))
    fingers(p,'R',60*e,thumb=(E(0,0,-52*e),E(0,0,6*e))); p.arm['L']=(t,po,h); p.m['eyes_smile']=.2+.2*e; p.m['blink']=blink(u,T,(.34,)); p.m['mouth_wide']=.12*e
GX,GY,GZ=30,-.055,-.185
def detection(u,T,p):
    common(p,u,T,tail=.5,ears=.7); g=K(u,[(0,0),(.17,0),(.31,1),(.81,1),(.94,0),(1,0)]); ha=K(u,[(0,0),(.12,1),(.34,1),(.46,0),(.72,0),(.78,1),(.94,1),(1,0)])
    lean=K(u,[(.25,0),(.4,1),(.76,1),(.9,0)]); scan=S1((u-.36)/.42,1)*lean
    p.r('goggles',E(GX*g)); p.loc['goggles']=(0,GY*g,GZ*g); p.r('spine',E(3*lean)); p.r('chest',E(3*lean)); p.r('head',E(4*lean,0,8*scan)); p.hip=V((0,-.012*lean,-.006*lean))
    t,po,h=A0(); grab=hd((.30,-.20,K(u,[(.1,.27),(.17,.27),(.31,.15),(.78,.15),(.94,.27)])))
    p.arm['R']=(lerp(t,grab,ha),lerp(po,(1,-.1,-.45),ha),lerp(h,frame((-.72,-.25,.65),(-.2,-.9,.3)),ha)); fingers(p,'R',26*ha,thumb=(E(0,15*ha,-10*ha),E(0,8*ha,0)))
    p.arm['L']=(t,po,h); p.m['glint']=K(u,[(.42,0),(.47,1),(.52,0),(.60,0),(.65,1),(.71,0)]); p.m['eyes_smile']=.2; p.m['mouth_talk']=.04
def _cardq(t): return E(-8*t,0,6*t)
def carte_sortir(u,T,p):
    common(p,u,T,tail=1,ears=1); t,po,h=A0(); r=AK(u,[(0,t,po,h),(.2,*PACK),(.36,*PACK),(.68,*HOLD),(1,*HOLD)])
    p.arm['R']=r; p.arm['L']=(t,po,h); s=K(u,[(.3,0),(.42,1)]); p.card={'q':_cardq(1)}; p.m['card_show']=s; pinch(p,'R'); lk=K(u,[(.05,0),(.2,1),(.42,1),(.62,0)])
    p.r('chest',E(0,0,-8*lk)); p.r('head',E(0,0,-14*lk)); p.m['eyes_smile']=.3; p.m['mouth_wide']=K(u,[(.6,0),(.8,.4)]); p.m['blink']=blink(u,T,(.5,)); p.eye=(-.008*lk,0)
def carte_garder(u,T,p):
    common(p,u,T,tail=1.4,ears=1.1); t,po,h=A0(); r=AK(u,[(0,*HOLD),(.32,*PACK),(.5,*PACK),(.82,t,po,h),(1,t,po,h)]); p.arm['R']=r; p.arm['L']=(t,po,h)
    p.card={'q':_cardq(K(u,[(0,1),(.3,.2)]))}; p.m['card_show']=K(u,[(.2,1),(.34,0)]); pinch(p,'R'); lk=K(u,[(.05,0),(.25,1),(.45,1),(.62,0)])
    p.r('chest',E(0,0,-8*lk)); p.r('head',E(-2,0,-13*lk)); n=bump(u,.72,0,.08); p.r('head',E(5*n)); p.m['mouth_wide']=K(u,[(0,.4),(.3,.3),(.65,.65),(1,0)]); p.m['eyes_smile']=K(u,[(0,.3),(.6,.65),(1,.2)]); p.eye=(-.008*lk,0)
_REL=None
def carte_poser(u,T,p):
    common(p,u,T,ears=.9); t,po,h=A0(); DOWN=((.48,-.30,-.20),(1,.2,.1),frame((.15,-.45,-.88),(-.4,-.85,.25))); r=AK(u,[(0,*HOLD),(.32,*DOWN),(.46,*DOWN),(.74,t,po,h),(1,t,po,h)]); p.arm['R']=r; p.arm['L']=(t,po,h)
    down=E(-74,0,12); flat=E(-90,0,12)
    if u>=.4:
        global _REL
        if _REL is None:
            q_=P(); carte_poser(.3999,T,q_); solve(q_); _REL=q_.cardpos.copy()
        f=sm((u-.4)/.2); fl=V((_REL.x-.02,_REL.y,-.935)); f2=f*f
        p.card={'pos':tuple(_REL.lerp(fl,f2)),'q':down.slerp(flat,f)}
    else: p.card={'q':lerp(_cardq(1),down,sm(u/.34))}
    p.m['card_show']=K(u,[(.74,1),(.92,0)]); pinch(p,'R'); p.r('head',E(1,0,-4+8*K(u,[(.45,0),(.7,1)]))); p.m['eyes_smile']=.3; p.m['mouth_wide']=K(u,[(0,.3),(.5,.12),(.8,.28),(1,0)]); p.m['blink']=blink(u,T,(.6,))
def calme(u,T,p):
    common(p,u,T,tail=.15,ears=.15,breath=0); b=S1(u,2,.25); p.hip=V((0,.03,-.50)); p.r('hips',E(-7)); p.r('spine',E(4+.8*b)); p.r('chest',E(4+1.6*b)); p.r('neck',E(3)); p.r('head',E(7+1.2*b,0,1.5*S1(u,1)))
    p.both('clavicle',E(0,-1.5*b,0)); p.r('tail1',E(58,0,18))
    for s in 'LR': p.foot[s]=((.215,-.50,-.76),(.55,-.55,-.15),ID)
    for s in 'LR': p.arm[s]=((.25,-.43+.004*b,-.53+.006*b),(.95,.2,.05),frame((-.15,-.55,-.82),(-.6,-.55,.3)))
    p.m['blink']=.42+.08*S1(u,2,.1); p.m['eyes_smile']=.25
def bras(u,T,p):
    common(p,u,T,tail=1.2,ears=1.1,breath=1.4)
    a=S1(u,2); p.r('spine',E(-2,0,1.5*S1(u,1))); p.r('chest',E(-3.5-.8*a,1*S1(u,1,.25),1.5*S1(u,1))); p.r('neck',E(-2)); p.r('head',E(-5+1.5*a,2.5*S1(u,1,.25),3*S1(u,1,.1)))
    for s,ph in(('L',0),('R',.06)):
        b=S1(u,2,ph); p.arm[s]=((.565+.012*b,-.285,.335+.024*b),(.2,.8,-.9),frame((.86,-.28,.38+.05*b),(-.15,.1,1)))
        fingers(p,s,(9+3*b,7+3*b,9+3*b),thumb=(E(0,0,12),E(0,0,6)),spread=7)
        p.r(f'clavicle.{s}',(lambda q:q if s=='L' else mq(q))(E(0,-5,0)))
    p.m['mouth_wide']=.62+.07*a; p.m['eyes_smile']=.55; p.m['blink']=blink(u,T,(.34,.8)); p.eye=(0,.004)
def encourage(u,T,p):
    common(p,u,T,tail=1.5,ears=1.2)
    b=S1(u,3); bb=max(0,S1(u,3,.05)); p.hip=V((0,0,-.012+.010*b))
    p.r('spine',E(0,1.5,-3)); p.r('chest',E(-1,-1.5,-6+.8*b)); p.r('neck',E(-1,0,3)); p.r('head',E(-3+3.4*S1(u,3,.08),3+1*b,8))
    def tg(Wp,Wq,M): return V((.345,-.43+.012*b,.095+.026*b))
    p.arm['R']=(tg,(.95,.1,-.55),frame((-.34,-.92,.12),(.05,-.05,1)))
    p.r('clavicle.R',mq(E(0,-4,3)))
    fingers(p,'R',94,thumb=(E(0,0,-52),E(0,0,6)))
    for f in('index','middle','pinky'): p.r(f'{f}2.R',mq(E(0,12,0)))
    p.arm['L']=((.355,-.15,-.13+.004*b),(1,.5,.05),frame((-.55,-.25,-.8),(.1,-1,0))); fingers(p,'L',48,thumb=(E(0,18,-10),E(0,14,0)))
    p.m['mouth_wide']=.92+.05*b; p.m['eyes_smile']=.78; p.m['blink']=blink(u,T,(.42,)); p.eye=(-.003,.002)
def rigole(u,T,p):
    common(p,u,T,tail=1.3,ears=.9,breath=0)
    c=S1(u,7); c2=abs(c); env=.75+.25*S1(u,1,.2); h=c*env
    p.hip=V((0,0,-.004+.004*h)); p.r('spine',E(-1+1.3*h)); p.r('chest',E(-2+2.2*h,0,2.4*S1(u,1)))
    p.r('neck',E(-2)); p.r('head',E(-8+2.8*h,3*S1(u,1,.25)+1,-5+4*S1(u,1,.1)))
    for s,sg in(('L',1),('R',-1)):
        p.r(f'clavicle.{s}',(lambda q:q if s=='L' else mq(q))(E(0,-3.5*max(0,h)-1,0)))
    p.arm['L']=((.20,-.395+.004*h,-.015+.012*h),(1,-.1,-.5),frame((-.86,-.22,.17),(.1,-.2,1))); fingers(p,'L',24,thumb=(E(0,0,8),E(0,0,0)))
    t,po,hh=REL(); p.arm['R']=((t[0]+.005,t[1]-.05,t[2]+.04+.012*h),po,hh)
    p.m['joy']=1; p.m['mouth_wide']=max(.5,.68+.2*h)
ANIMS=[('repos',12,repos),('salut',3.4,salut),('ecoute',8,ecoute),('reflexion',8,reflexion),('parle_1',6,parle1),('parle_2',6,parle2),('parle_3',6,parle3),('pas_grave',3.2,pas_grave),('pas_mal',3,pas_mal),('detection',5.6,detection),('carte_sortir',3,carte_sortir),('carte_garder',3,carte_garder),('carte_poser',3.2,carte_poser),('calme',10,calme),('bras_ouverts',4,bras),('encourage',3,encourage),('rigole',3,rigole)]
ONCE={'salut','pas_grave','pas_mal','detection','carte_sortir','carte_garder','carte_poser'}
def pose_at(fn,u,T):
    p=P(); fn(u,T,p); L,Wp=solve(p); return p,L,Wp
def apply(ao,p,L,prev=None):
    for pb in ao.pose.bones:
        n=pb.name; R=RQ[n]; q=R.inverted()@L.get(n,ID)@R
        if prev is not None and n in prev: q.make_compatible(prev[n])
        pb.rotation_mode='QUATERNION'; pb.rotation_quaternion=q
        if prev is not None: prev[n]=q.copy()
        pb.location=(0,0,0)
    pb=ao.pose.bones['hips']; pb.location=RQ['hips'].inverted()@p.hip
    ex,ez=p.eye
    for s,sg in(('L',1),('R',1)):
        pb=ao.pose.bones[f'eye.{s}']; pb.location=RQ[f'eye.{s}'].inverted()@V((ex,0,ez))
    for b,v in p.loc.items(): ao.pose.bones[b].location=RQ[b].inverted()@V(v)
    if p.cardpos is not None: ao.pose.bones['card'].location=RQ['card'].inverted()@(p.cardpos-RP['card'])
    for k,v in p.m.items(): keys.key_blocks[k].value=max(0,min(1,v))
