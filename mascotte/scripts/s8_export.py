import bpy, os, sys
S=os.path.dirname(os.path.abspath(bpy.data.filepath)); sys.path.insert(0,S)
import s6_anim as A
ao,keys=A.ao,A.keys; sc=bpy.context.scene; ao.animation_data_create(); keys.animation_data_create()
MK=list(A.P().m)
for n,T,fn in A.ANIMS:
    N=int(T*A.FPS); act=bpy.data.actions.new(n); ka=bpy.data.actions.new(n+'_face'); ao.animation_data.action=act; keys.animation_data.action=ka; prev={}
    for f in range(N+1):
        u=(f/N if n in A.ONCE else (f%N)/N); p,L,_=A.pose_at(fn,u,T); A.apply(ao,p,L,prev)
        if f%2==0 or f==N:
            for pb in ao.pose.bones:
                pb.keyframe_insert('rotation_quaternion',frame=f)
            ao.pose.bones['hips'].keyframe_insert('location',frame=f)
            for s in 'LR': ao.pose.bones[f'eye.{s}'].keyframe_insert('location',frame=f)
            for b in('goggles','card'): ao.pose.bones[b].keyframe_insert('location',frame=f)
        for k in MK: keys.key_blocks[k].keyframe_insert('value',frame=f)
    for ad,a in((ao.animation_data,act),(keys.animation_data,ka)):
        ad.action=None; tr=ad.nla_tracks.new(); tr.name=n; st=tr.strips.new(n,0,a); st.action_frame_start=0; st.action_frame_end=N; tr.mute=False
    print('clip',n,N)
for pb in ao.pose.bones: pb.rotation_quaternion=(1,0,0,0); pb.location=(0,0,0)
for k in MK: keys.key_blocks[k].value=0
sc.frame_start=0; sc.frame_end=400; sc.frame_set(0)
for name,s in(('fox_base.png',1536),('fox_normal.png',1024)):
    im=bpy.data.images[name]; im.scale(s,s)
out=S+'/neo.glb'
bpy.ops.export_scene.gltf(filepath=out,export_format='GLB',export_animations=True,export_animation_mode='NLA_TRACKS',export_merge_animation='NLA_TRACK',export_nla_strips=True,export_force_sampling=True,export_frame_step=2,export_optimize_animation_size=True,export_morph=True,export_morph_normal=False,export_skins=True,export_influence_nb=4,export_image_format='JPEG',export_jpeg_quality=80,export_tangents=False,export_yup=True,export_apply=False,export_def_bones=False,export_vertex_color='MATERIAL')
print('size',os.path.getsize(out)/1e6)
bpy.ops.file.pack_all(); bpy.ops.wm.save_as_mainfile(filepath=S+'/neo.blend',copy=True,compress=True); print('blend',os.path.getsize(S+'/neo.blend')/1e6)
