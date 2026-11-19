import bpy, os, numpy as np, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
S=os.path.dirname(os.path.abspath(bpy.data.filepath))
lo=bpy.data.objects['Low']; lo.name='Fox_Body'; me=lo.data; me.name='Fox_Body'
# ---------- material
mat=me.materials[0]; nt=mat.node_tree; nt.nodes.clear()
out=nt.nodes.new('ShaderNodeOutputMaterial'); b=nt.nodes.new('ShaderNodeBsdfPrincipled')
b.inputs['Metallic'].default_value=0; b.inputs['Roughness'].default_value=.78
nt.links.new(b.outputs[0],out.inputs[0])
tb=nt.nodes.new('ShaderNodeTexImage'); tb.image=bpy.data.images.load(S+'/fox_base.png'); nt.links.new(tb.outputs[0],b.inputs['Base Color'])
tn=nt.nodes.new('ShaderNodeTexImage'); tn.image=bpy.data.images.load(S+'/fox_normal.png'); tn.image.colorspace_settings.name='Non-Color'
nm=nt.nodes.new('ShaderNodeNormalMap'); nt.links.new(tn.outputs[0],nm.inputs['Color']); nt.links.new(nm.outputs[0],b.inputs['Normal'])
n=len(me.vertices); P=np.zeros(n*3); me.vertices.foreach_get('co',P); P=P.reshape(-1,3); X,Y,Z=P.T
EYE={'L':(.120,.447,.065,.073),'R':(-.120,.447,.065,.073)}
# ---------- bones: name:(head,tail,parent). '.L' is mirrored to '.R'
V=lambda *a:tuple(a)
ear=(X>.15)&(Z>.62)&(Y>-.2); ey=float(np.median(Y[ear]))
C={ 'root':(V(0,-.11,-.95),V(0,-.11,-.855),None),
 'hips':(V(0,-.11,-.25),V(0,-.11,-.10),'root'),'spine':(V(0,-.11,-.10),V(0,-.11,.04),'hips'),
 'chest':(V(0,-.11,.04),V(0,-.11,.20),'spine'),'neck':(V(0,-.11,.22),V(0,-.12,.29),'chest'),
 'head':(V(0,-.12,.29),V(0,-.12,.70),'neck'),
 'goggles':(V(0,-.33,.674),V(0,-.41,.674),'head'),'card':(V(-.80,-.20,.14),V(-.80,-.20,.24),'root')}
Sd={'clavicle':(V(.06,-.11,.12),V(.215,-.105,.095),'chest'),
 'upperarm':(V(.215,-.105,.095),V(.40,-.105,.085),'clavicle'),'forearm':(V(.40,-.105,.085),V(.575,-.105,.08),'upperarm'),
 'hand':(V(.575,-.105,.08),V(.70,-.10,.09),'forearm'),
 'thumb1':(V(.63,-.20,.06),V(.672,-.208,.056),'hand'),'thumb2':(V(.672,-.208,.056),V(.714,-.21,.052),'thumb1'),
 'index1':(V(.71,-.162,.095),V(.75,-.162,.093),'hand'),'index2':(V(.75,-.162,.093),V(.792,-.162,.09),'index1'),
 'middle1':(V(.706,-.10,.10),V(.761,-.10,.098),'hand'),'middle2':(V(.761,-.10,.098),V(.816,-.10,.094),'middle1'),
 'ring1':(V(.706,-.034,.098),V(.748,-.035,.096),'hand'),'ring2':(V(.748,-.035,.096),V(.79,-.036,.092),'ring1'),
 'pinky1':(V(.70,.0,.093),V(.715,.0,.092),'hand'),'pinky2':(V(.715,.0,.092),V(.73,-.002,.09),'pinky1'),
 'thigh':(V(.14,-.11,-.27),V(.145,-.11,-.47),'hips'),'shin':(V(.145,-.11,-.47),V(.15,-.10,-.70),'thigh'),
 'foot':(V(.15,-.10,-.70),V(.16,-.26,-.88),'shin'),'toe':(V(.16,-.26,-.88),V(.16,-.35,-.90),'foot'),
 'ear1':(V(.21,ey,.62),V(.255,ey,.79),'head'),'ear2':(V(.255,ey,.79),V(.30,ey,.94),'ear1'),
 'eye':(V(EYE['L'][0],-.36,EYE['L'][1]),V(EYE['L'][0],-.42,EYE['L'][1]),'head')}
# tail: refine a guessed centre line on the actual tail vertices
T=(Y>.085)&(Z<-.27)&(X<.12); Tp=P[T]
base=np.array([-.03,.06,-.30]); D=np.linalg.norm(Tp-base,axis=1); Dm=np.percentile(D,99.5); G=[base]
for c in (.2,.4,.6,.8): G.append(Tp[np.abs(D-c*Dm)<.05*Dm].mean(0))
G.append(Tp[D>.95*Dm].mean(0)); G=np.array(G)
pts=list(G); print('tail',np.round(pts,3).tolist())
for i in range(5): C[f'tail{i+1}']=(tuple(pts[i]),tuple(pts[i+1]),'hips' if i==0 else f'tail{i}')
B=dict(C)
for k,(h,t,p) in Sd.items():
    B[k+'.L']=(h,t,(p+'.L') if p in Sd else p)
    B[k+'.R']=((-h[0],h[1],h[2]),(-t[0],t[1],t[2]),(p+'.R') if p in Sd else p)
arm=bpy.data.armatures.new('Neo'); ao=bpy.data.objects.new('Neo',arm); bpy.context.collection.objects.link(ao)
bpy.context.view_layer.objects.active=ao; ao.select_set(True); bpy.ops.object.mode_set(mode='EDIT')
for k,(h,t,p) in B.items():
    e=arm.edit_bones.new(k); e.head=h; e.tail=t
for k,(h,t,p) in B.items():
    if p: arm.edit_bones[k].parent=arm.edit_bones[p]
bpy.ops.object.mode_set(mode='OBJECT')
# ---------- weights
def sm(a,b,x):
    t=np.clip((x-a)/(b-a),0,1); return t*t*(3-2*t)
names=list(B); I={k:i for i,k in enumerate(names)}; W=np.zeros((n,len(names)))
def over(m,new):
    global W
    m=np.clip(m,0,1)[:,None]; A=np.zeros_like(W)
    for k,v in new.items(): A[:,I[k]]=v
    W=W*(1-m)+A*m
def segd(Q,a,b):
    a,b=np.array(a),np.array(b); d=b-a; t=np.clip(((Q-a)*d).sum(1)/(d@d),0,1); return np.linalg.norm(Q-(a+t[:,None]*d),axis=1)
def soft(Q,bs,p,side=None,f=lambda x:x):
    D=np.stack([segd(Q,*[np.array(c) for c in B[b][:2]])+.004 for b in bs],1)**-p; D/=D.sum(1,keepdims=True); return {b:D[:,i] for i,b in enumerate(bs)}
a=sm(-.19,-.09,Z); b_=sm(-.03,.07,Z)
W[:,I['hips']]=1-a; W[:,I['spine']]=a*(1-b_); W[:,I['chest']]=a*b_
over(sm(.19,.24,Z)*(1-sm(.11,.15,abs(X)))*(1-sm(-.02,.02,Y)),{'neck':np.ones(n)})
zt=.255+np.clip(Y+.1,0,.3)*.2-.02*(1-sm(-.30,-.26,Y)); over(sm(zt,zt+.035,Z),{'head':np.ones(n)})
for s,sx in (('L',1),('R',-1)):
    x=X*sx; Q=P*[sx,1,1]; g=lambda k:k+'.'+s
    # leg
    m=(1-sm(-.33,-.23,Z))*sm(.0,.03,x)*(Y<.08)
    kn=sm(-.50,-.44,Z); an=1-sm(-.73,-.67,Z); to=an*(1-sm(-.30,-.22,Y))
    over(m,{g('thigh'):kn,g('shin'):(1-kn)*(1-an),g('foot'):an-to,g('toe'):to})
    # arm
    m=sm(.19,.27,x)*sm(-.06,-.01,Z)*(1-sm(.19,.235,Z))*(1-sm(.0,.04,Y))
    c=1-sm(.21,.29,x); e=sm(.37,.43,x); h=sm(.555,.575,x)
    over(m,{g('clavicle'):c,g('upperarm'):(1-c)*(1-e),g('forearm'):(1-c)*e*(1-h),g('hand'):h})
    # hand and fingers
    fs=[g(k) for k in ('hand','thumb1','thumb2','index1','index2','middle1','middle2','ring1','ring2','pinky1','pinky2')]
    over(sm(.555,.575,x)*(np.abs(Z-.08)<.12),{fs[i]:v for i,v in enumerate(soft(Q,[k[:-2]+'.L' for k in fs],6).values())})
    # ear
    m=(x>.15)&(Z>.60)&(Y>-.2); h0,t0=np.array(Sd['ear1'][0]),np.array(Sd['ear2'][1]); ax=t0-h0; t=((Q-h0)*ax).sum(1)/(ax@ax)
    u=sm(.42,.58,t); over(m*sm(.0,.12,t),{g('ear1'):1-u,g('ear2'):u})
    # eye warp
    ex,ez,rx,rz=EYE[s]; r=np.sqrt(((X-ex)/rx)**2+((Z-ez)/rz)**2)
    over((1-sm(.42,.90,r))*(Y<-.25),{g('eye'):np.ones(n)})
t_=[f'tail{i}' for i in range(1,6)]
over(T*sm(.035,.09,Y),soft(P,t_,4))
# prune + normalise, write
for k in names: lo.vertex_groups.new(name=k)
ord_=np.argsort(-W,1)[:,:4]; cnt=0
for i in range(n):
    ids=ord_[i]; v=W[i,ids]; v=np.where(v<.02,0,v); s_=v.sum()
    if s_==0: ids=[I['chest']]; v=np.array([1.]); s_=1
    for j,w in zip(ids,v/s_):
        if w>0: lo.vertex_groups[int(j)].add([i],float(w),'REPLACE')
lo.parent=ao; lo.modifiers.new('Armature','ARMATURE').object=ao
# ---------- face parts (eyelids, open mouth): vertex-coloured, morph-driven
dg=bpy.context.evaluated_depsgraph_get(); tree=BVHTree.FromObject(lo,dg,deform=False)
def Sy(x,z,off=.005):
    h=tree.ray_cast(Vector((x,-1,z)),Vector((0,1,0)),2)
    return (h[0].y if h[0] else -.40)-off
lin=lambda c:tuple(((v/255+.055)/1.055)**2.4 for v in c)
FUR,FUR2,LASH=lin((201,120,44)),lin((170,92,30)),lin((26,17,14)); CREAM=lin((236,226,212))
DARK,TONG,TEETH=lin((58,20,24)),lin((214,100,104)),lin((246,240,232))
_im=bpy.data.images['fox_base.png']; _w,_h=_im.size; _px=np.array(_im.pixels[:]).reshape(_h,_w,4); _uv=me.uv_layers[0].data
def tex(x,z):
    ok,p,_,fi=lo.ray_cast(Vector((x,-1,z)),Vector((0,1,0)))
    if not ok: return np.array(FUR)
    po=me.polygons[fi]; L=list(po.loop_indices); a,b,c=[me.vertices[me.loops[l].vertex_index].co for l in L[:3]]
    v0,v1,v2=b-a,c-a,p-a; d00,d01,d11,d20,d21=v0@v0,v0@v1,v1@v1,v2@v0,v2@v1; D=d00*d11-d01*d01 or 1e-9
    v=(d11*d20-d01*d21)/D; w=(d00*d21-d01*d20)/D; uv=_uv[L[0]].uv*(1-v-w)+_uv[L[1]].uv*v+_uv[L[2]].uv*w
    return _px[int(np.clip(uv.y,0,.9999)*_h),int(np.clip(uv.x,0,.9999)*_w),:3]
def ring(cx,cz,rx,rz,us,sign):
    C=[]
    for u in us:
        a=math.sqrt(max(1-u*u,0))*sign; C.append(np.mean([tex(cx+rx*u*k,cz+rz*a*k) for k in(1.26,1.36,1.46)],0))
    C=np.array(C); return [C[max(0,i-1):i+2].mean(0) for i in range(len(C))]
Vs=[];Fs=[];Cs=[];K={k:[] for k in('blink','joy','eyes_smile','mouth_talk','mouth_wide','glint','card_show')}; Ns=[]; Gs=[]
def grid(rows,bone='head'):  # rows[c][r]=dict(base,keys,col)
    o=len(Vs); nc,nr=len(rows),len(rows[0])
    for c in rows:
        for v in c:
            Vs.append(v['b']); Cs.append(v['c']); Ns.append(v.get('n')); Gs.append(bone)
            for k in K: K[k].append(v.get(k,v['b']))
    for c in range(nc-1):
        for r in range(nr-1):
            a=o+c*nr+r; Fs.append((a,a+nr,a+nr+1,a+1))
NC,NR=17,6
for s,(cx,cz,rx,rz) in EYE.items():
    arch=lambda u:cz-.15*rz+.42*rz*(1-u*u)
    up=[];lw=[]; US=[(-1+2*i/(NC-1))*.998 for i in range(NC)]; A_=np.array(ring(cx,cz,rx,rz,US,1)+ring(cx,cz,rx,rz,US,-1)); A_=A_[(A_[:,0]-A_[:,2]>.22)&(A_[:,0]>.45)]; c_=np.median(A_,0); c_=np.where(c_<=.04045,c_/12.92,((c_+.055)/1.055)**2.4); print('lid colour',s,np.round(c_,3)); c_=np.clip(c_*np.array((1.22,1.02,1.0)),0,1); RU=RL=[c_]*NC
    for i in range(NC):
        u=-1+2*i/(NC-1); u_=u*.998; x=cx+rx*u_; h=rz*math.sqrt(1-u_*u_); zt,zb=cz+h,cz-h; ca=[];cb=[]
        za=max(min(arch(u),zt),zb)
        for j in range(NR):
            v=j/(NR-1); col=LASH if j==NR-1 else tuple(RU[i]*(.82 if j==NR-2 else 1))
            z=zt+(zb-zt)*v; zm=(zt+z)/2; yb=2*Sy(x,zm)-Sy(x,z); zj=zt+(za-zt)*v
            ca.append(dict(b=(x,Sy(x,zt),zt),c=col,blink=(x,Sy(x,z),z),joy=(x,Sy(x,zj),zj)))
            # lower lid, rises from the bottom rim
            z2=zb+(za-zb)*v; zs=zb+(min(za,cz-.12*rz+.30*rz*(1-u*u))-zb)*v
            c2=LASH if j==NR-1 else tuple(RL[i])
            cb.append(dict(b=(x,Sy(x,zb),zb),c=c2,joy=(x,Sy(x,z2),z2),eyes_smile=(x,Sy(x,zs),zs)))
        up.append(ca);lw.append(cb)
    grid(up);grid(lw)
line=lambda x:.307+.012*min(abs(x)/.078,1.1)**2
MC,MR=19,7; col_=[]
def mouthcol(p,v):
    e=abs(p)>.86 or v>.93
    if e: return DARK
    if v<.24 and abs(p)<.8: return TEETH
    if v>.68 and abs(p)<.58: return TONG
    return DARK
rows=[]
for i in range(MC):
    p=-1+2*i/(MC-1); c=[]
    for j in range(MR):
        v=j/(MR-1); x0=p*.018; b=(x0,Sy(x0,line(x0),.006),line(x0))
        d={'b':b,'c':mouthcol(p,v)}
        for k,w,h in(('mouth_talk',.032,.020),('mouth_wide',.066,.034)):
            x=p*w; zt=line(x)-.001; z=zt-h*v*max(1-p*p,0)**.55; d[k]=(x,Sy(x,z,.006),z)
        c.append(d)
    rows.append(c)
grid(rows)
# lens glints: stars collapsed at rest, opened by the 'glint' morph, carried by the goggles
WHITE=(1,1,.94)
for lx in (.141,-.141):
    o_=Vector((lx,-1,.674)); h_=tree.ray_cast(o_,Vector((0,1,0)),2); nn=h_[1].normalized(); nn=nn if nn.y<0 else -nn
    c0=h_[0]+nn*.009; ux=Vector((1,0,0)); uz=nn.cross(ux).normalized(); uz=uz if uz.z>0 else -uz
    col=[]
    for i in range(17):
        a=2*math.pi*i/16; r=.036 if i%4==0 else .007
        tip=c0+ux*(math.cos(a)*r)+uz*(math.sin(a)*r)
        col.append([dict(b=tuple(c0),c=WHITE,n=tuple(nn),glint=tuple(c0)),dict(b=tuple(c0),c=WHITE,n=tuple(nn),glint=tuple(tip))])
    grid(col,'goggles')
# talent card: collapsed at the grip, opened by 'card_show'; stands upright facing the viewer at rest
GOLD=lin((255,209,102)); PAPER=lin((255,248,224)); GX,GY,GZ=-.80,-.20,.14; NY=(0,-1,0)
def rrect(w,h,y,col,r):
    cols=[]; 
    for i in range(13):
        t=-1+2*i/12; x=t*w; ex=max(0,abs(x)-(w-r)); d=r-math.sqrt(max(r*r-ex*ex,0))
        p0=(GX,GY,GZ); a=(GX+x,GY+y,GZ+.105-h+d); b=(GX+x,GY+y,GZ+.105+h-d)
        cols.append([dict(b=p0,c=col,n=NY,card_show=a),dict(b=p0,c=col,n=NY,card_show=b)])
    grid(cols,'card')
rrect(.078,.108,0,GOLD,.016); rrect(.066,.096,-.002,PAPER,.01)
col=[]
for i in range(11):
    a=math.pi/2+2*math.pi*i/10; r=.046 if i%2==0 else .019; p0=(GX,GY,GZ); c_z=GZ+.115
    col.append([dict(b=p0,c=GOLD,n=NY,card_show=(GX,GY-.004,c_z)),dict(b=p0,c=GOLD,n=NY,card_show=(GX+math.cos(a)*r,GY-.004,c_z+math.sin(a)*r))])
grid(col,'card')
fm=bpy.data.meshes.new('Fox_Face'); fm.from_pydata(Vs,[],Fs); fm.update()
fo=bpy.data.objects.new('Fox_Face',fm); bpy.context.collection.objects.link(fo)
ca=fm.color_attributes.new('Col','FLOAT_COLOR','POINT'); 
for i,c in enumerate(Cs): ca.data[i].color=(*c,1)
fo.shape_key_add(name='Basis')
for k,vs in K.items():
    sk=fo.shape_key_add(name=k,from_mix=False); sk.data.foreach_set('co',np.array(vs).ravel())
fm.polygons.foreach_set('use_smooth',[True]*len(fm.polygons))
_N=[]
for v,nv in zip(K['blink'],Ns):
    _N.append(Vector(nv) if nv else Vector((v[0]*.7,-1,(v[2]-.47)*.7+.12)).normalized())
fm.normals_split_custom_set_from_vertices(_N)
fmat=bpy.data.materials.new('Fox_Face'); fmat.use_nodes=True; fn=fmat.node_tree; pb=fn.nodes['Principled BSDF']; pb.inputs['Metallic'].default_value=0; pb.inputs['Roughness'].default_value=.8
ca_=fn.nodes.new('ShaderNodeVertexColor'); ca_.layer_name='Col'; fn.links.new(ca_.outputs[0],pb.inputs['Base Color']); fmat.use_backface_culling=False; fm.materials.append(fmat)
for b_ in sorted(set(Gs)):
    fo.vertex_groups.new(name=b_).add([i for i,g_ in enumerate(Gs) if g_==b_],1,'REPLACE')
fo.parent=ao; fo.modifiers.new('Armature','ARMATURE').object=ao
# ---------- goggles become their own skinned mesh; a dark band replaces them on the head
import bmesh
bm=bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table(); uvl=bm.loops.layers.uv.active
def isgog(f):
    c=f.calc_center_median()
    if not(abs(c.x)<.25 and .54<c.z<.80 and c.y<-.17): return False
    u=sum((l[uvl].uv for l in f.loops),Vector((0,0)))/3; px=_px[int(np.clip(u.y,0,.9999)*_h),int(np.clip(u.x,0,.9999)*_w)]
    return px[0]-px[2]<.30
C_={f.index for f in bm.faces if isgog(f)}
seed=[lo.ray_cast(Vector((x_,-1,.674)),Vector((0,1,0)))[3] for x_ in(.141,-.141)]
G_=set(); st=[i for i in seed if i in C_]
while st:
    i=st.pop()
    if i in G_: continue
    G_.add(i)
    for e in bm.faces[i].edges:
        for f in e.link_faces:
            if f.index in C_ and f.index not in G_: st.append(f.index)
for _ in range(3):
    add=[f.index for f in bm.faces if f.index not in G_ and abs(f.calc_center_median().x)<.255 and sum(1 for e in f.edges for g in e.link_faces if g is not f and g.index in G_)>=2]
    G_|=set(add)
def inb(f):
    c=f.calc_center_median(); return abs(c.x)<.27 and .52<c.z<.82 and c.y<-.10
B_={f.index for f in bm.faces if inb(f)}-G_; seen=set()
for i0 in list(B_):
    if i0 in seen: continue
    comp=[];st=[i0];seen.add(i0);free=False
    while st:
        i=st.pop();comp.append(i)
        for e in bm.faces[i].edges:
            for f in e.link_faces:
                j=f.index
                if j==i or j in G_: continue
                if j in B_:
                    if j not in seen: seen.add(j);st.append(j)
                else: free=True
    if not free: G_|=set(comp); print('enclosed',len(comp))
H_=set()
for f in bm.faces:
    if f.index in G_ or not inb(f): continue
    c=f.calc_center_median()
    for d_ in (Vector((0,-1,0)),Vector((0,-.9,.42)).normalized(),Vector((0,-.9,-.3)).normalized()):
        ok,_,_,hi_=lo.ray_cast(c+d_*.002,d_,distance=.25)
        if ok and hi_ in G_: H_.add(f.index); break
print('hidden faces',len(H_)); print('goggle faces',len(G_))
go=lo.copy(); go.data=me.copy(); go.name='Fox_Goggles'; go.data.name='Fox_Goggles'; bpy.context.collection.objects.link(go)
b2=bmesh.new(); b2.from_mesh(go.data); b2.faces.ensure_lookup_table(); bmesh.ops.delete(b2,geom=[f for f in b2.faces if f.index not in G_],context='FACES'); b2.to_mesh(go.data); b2.free()
go.vertex_groups.clear(); go.vertex_groups.new(name='goggles').add(list(range(len(go.data.vertices))),1,'REPLACE')
inner=[v for v in bm.verts if v.link_faces and all(f.index in G_ for f in v.link_faces)]
for _ in range(40):
    new={v:sum((e.other_vert(v).co for e in v.link_edges),Vector())/len(v.link_edges) for v in inner}
    for v,c in new.items(): v.co=c
ctr=Vector((0,-.05,.55))
for v in inner: v.co+=(ctr-v.co).normalized()*.03
for i in G_|H_: bm.faces[i].material_index=1
bm.to_mesh(me); bm.free()
band=bpy.data.materials.new('Fox_Band'); band.use_nodes=True; pb_=band.node_tree.nodes['Principled BSDF']; pb_.inputs['Base Color'].default_value=(*lin((214,92,26)),1); pb_.inputs['Metallic'].default_value=0; pb_.inputs['Roughness'].default_value=.85; me.materials.append(band)
print('bones',len(names),'face verts',len(Vs),'body',n,'unweighted',int((W.sum(1)<.5).sum()))
bpy.ops.wm.save_as_mainfile(filepath=S+'/rig.blend')
