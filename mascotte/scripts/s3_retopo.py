import bpy, bmesh, os, time, numpy as np
from mathutils import Vector
S=os.path.dirname(os.path.abspath(__file__))
TARGET=30000
EYES=[(.1085,.526,.062,.064),(-.110,.526,.064,.064)]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.expanduser('~/Downloads/Meshy_AI_Skytrail_Fox_1118154310_texture.glb'))
hi=[x for x in bpy.data.objects if x.type=='MESH'][0]; hi.name='High'
bpy.context.view_layer.objects.active=hi; hi.select_set(True)
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
# High material: non-metal so the diffuse-colour bake is not black
mat=hi.data.materials[0]; nt=mat.node_tree
bs=[n for n in nt.nodes if n.type=='BSDF_PRINCIPLED'][0]
for inp in ('Metallic','Roughness'):
    for l in list(bs.inputs[inp].links): nt.links.remove(l)
bs.inputs['Metallic'].default_value=0; bs.inputs['Roughness'].default_value=.8
# Low: welded copy, decimated
lo=hi.copy(); lo.data=hi.data.copy(); lo.name='Low'; lo.data.name='Low'; bpy.context.collection.objects.link(lo)
for a in list(lo.data.uv_layers): lo.data.uv_layers.remove(a)
lo.data.materials.clear()
t=time.time(); bm=bmesh.new(); bm.from_mesh(lo.data); bmesh.ops.remove_doubles(bm,verts=bm.verts,dist=1e-5)
bm.to_mesh(lo.data); bm.free(); print('weld',time.time()-t,len(lo.data.vertices),len(lo.data.polygons))
bpy.ops.object.select_all(action='DESELECT'); bpy.context.view_layer.objects.active=lo; lo.select_set(True)
m=lo.modifiers.new('d','DECIMATE'); m.ratio=TARGET/len(lo.data.polygons); bpy.ops.object.modifier_apply(modifier='d')
print('dec',time.time()-t,len(lo.data.vertices),len(lo.data.polygons))
# densify eyes (gaze is done by warping them) and re-project on the high-poly
def ine(c,k=1.15):
    return c.y<-.25 and any(((c.x-e[0])/e[2])**2+((c.z-e[1])/e[3])**2<k*k for e in EYES)
bm=bmesh.new(); bm.from_mesh(lo.data)
for it in range(2):
    bm.faces.ensure_lookup_table()
    fs=[f for f in bm.faces if ine(f.calc_center_median())]
    es=list({e for f in fs for e in f.edges}); print('eye faces',len(fs))
    bmesh.ops.subdivide_edges(bm,edges=es,cuts=1,use_grid_fill=True)
    bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>3])
dg=bpy.context.evaluated_depsgraph_get()
n=0
for v in bm.verts:
    if ine(v.co,1.2):
        ok,p,_,_=hi.closest_point_on_mesh(v.co)
        if ok: v.co=p; n+=1
print('reproj',n); bm.to_mesh(lo.data); bm.free()
lo.data.polygons.foreach_set('use_smooth',[True]*len(lo.data.polygons)); lo.data.update()
# UVs
lo.data.uv_layers.new(name='UV')
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=1.15,island_margin=.002,area_weight=.4,scale_to_bounds=False)
bm=bmesh.from_edit_mesh(lo.data); uv=bm.loops.layers.uv.active
seen=set(); isl=[]
for f in bm.faces:
    if f.index in seen: continue
    st=[f]; seen.add(f.index); cur=[]
    while st:
        g=st.pop(); cur.append(g)
        for l in g.loops:
            for o in l.edge.link_loops:
                h=o.face
                if h.index in seen or o is l: continue
                a,b=l[uv].uv,l.link_loop_next[uv].uv; c,d=o[uv].uv,o.link_loop_next[uv].uv
                if ((a-d).length<1e-6 and (b-c).length<1e-6) or ((a-c).length<1e-6 and (b-d).length<1e-6):
                    seen.add(h.index); st.append(h)
    isl.append(cur)
print('islands',len(isl)); k=0
for fs in isl:
    c=sum((f.calc_center_median() for f in fs),Vector())/len(fs)
    s=1
    if c.y<-.22 and .36<c.z<.72 and abs(c.x)<.3: s=2.2
    elif abs(c.x)>.6 and .05<c.z<.25: s=1.3
    if s!=1:
        k+=1; ls=[l for f in fs for l in f.loops]
        m_=sum((l[uv].uv for l in ls),Vector((0,0)))/len(ls)
        for l in ls: l[uv].uv=m_+(l[uv].uv-m_)*s
bmesh.update_edit_mesh(lo.data); print('scaled',k)
bpy.ops.uv.select_all(action='SELECT'); bpy.ops.uv.pack_islands(rotate=True,scale=True,margin=.003)
bpy.ops.object.mode_set(mode='OBJECT')
# Bake
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.samples=4; sc.cycles.device='CPU'
lm=bpy.data.materials.new('Fox'); lm.use_nodes=True; lo.data.materials.append(lm)
tn=lm.node_tree.nodes.new('ShaderNodeTexImage'); lm.node_tree.nodes.active=tn
def bake(name,typ,cs,**kw):
    im=bpy.data.images.new(name,2048,2048,alpha=False,float_buffer=False); im.colorspace_settings.name=cs; tn.image=im
    bpy.ops.object.select_all(action='DESELECT'); hi.select_set(True); lo.select_set(True); bpy.context.view_layer.objects.active=lo
    t=time.time()
    bpy.ops.object.bake(type=typ,use_selected_to_active=True,cage_extrusion=.012,max_ray_distance=.03,margin=8,**kw)
    im.filepath_raw=f'{S}/{name}.png'; im.file_format='PNG'; im.save(); print('baked',name,time.time()-t)
bake('fox_base','DIFFUSE','sRGB',pass_filter={'COLOR'})
bake('fox_normal','NORMAL','Non-Color')
bpy.data.objects.remove(hi)
bpy.ops.outliner.orphans_purge(do_recursive=True)
print('final',len(lo.data.vertices),len(lo.data.polygons))
bpy.ops.wm.save_as_mainfile(filepath=S+'/low.blend')
