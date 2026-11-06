"""Sample permitted local BVH to skeleton-only GLB and native world witnesses.

Run inside Blender with its bundled io_anim_bvh enabled. No network, source
geometry or character retargeting. Caller provides source rights and calibration.
"""
from pathlib import Path
import argparse, datetime, hashlib, json, math, struct, sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from bvh_source_plan import load_plan,probe_bvh

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--plan',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.output.exists():raise ValueError('Choose a new BVH conversion directory')
    plan=load_plan(args.plan,args.source);probe=probe_bvh(args.source,plan)
    import bpy
    from mathutils import Matrix
    if not bpy.app.background:raise ValueError('Use an isolated background Blender process; do not clear an interactive scene')
    if not bpy.context.preferences.addons.get('io_anim_bvh'):raise ValueError('Enable the bundled BVH importer before using this source adapter')
    for ob in list(bpy.data.objects):bpy.data.objects.remove(ob,do_unlink=True)
    result=bpy.ops.import_anim.bvh(filepath=str(args.source.resolve()),global_scale=plan['scale'],
        frame_start=1,use_fps_scale=False,update_scene_fps=True,update_scene_duration=True,
        rotate_mode='QUATERNION',axis_forward=plan['axes']['forward'],axis_up=plan['axes']['up'])
    if 'FINISHED' not in result:raise RuntimeError('Bundled BVH importer did not finish')
    arm=bpy.context.object;bones=list(arm.data.bones)
    if arm.type!='ARMATURE' or len(bones)!=probe['bones']:raise ValueError('Imported BVH skeleton differs from probe')
    root=next(b for b in bones if b.parent is None);pelvis=plan['reference']['pelvis']
    if pelvis not in arm.data.bones:raise ValueError('Reviewed source pelvis bone missing')
    scene=bpy.context.scene;frames=list(range(plan['frames'][0],plan['frames'][1]+1,plan['frames'][2]))
    scene.frame_start=1;scene.frame_end=probe['raw_frames']
    indexes={b.name:i for i,b in enumerate(bones)}
    scene.frame_set(frames[0]);bpy.context.view_layer.update()
    C=Matrix(((1,0,0,0),(0,0,1,0),(0,-1,0,0),(0,0,0,1)))
    if plan['reference']['mode']=='first-frame':
        reference={b.name:C@arm.matrix_world@arm.pose.bones[b.name].matrix for b in bones}
        calibration='First sampled captured pose defines source calibration; source BVH bind offsets may not form an anatomical T-pose.'
    elif plan['reference']['mode']=='bind-rebased':
        offset=(arm.matrix_world@arm.pose.bones[pelvis].matrix).translation-(arm.matrix_world@arm.data.bones[pelvis].matrix_local).translation
        reference={b.name:C@Matrix.Translation(offset)@arm.matrix_world@b.matrix_local for b in bones}
        calibration='Anatomical BVH bind reference translated to first captured pelvis position; captured root displacements retained.'
    else:
        first_pelvis=(arm.matrix_world@arm.pose.bones[pelvis].matrix).translation.copy()
        scene.frame_set(plan['reference']['frame']);bpy.context.view_layer.update()
        calibration_pelvis=(arm.matrix_world@arm.pose.bones[pelvis].matrix).translation.copy()
        offset=first_pelvis-calibration_pelvis;offset.z=0
        reference={b.name:C@Matrix.Translation(offset)@arm.matrix_world@arm.pose.bones[b.name].matrix for b in bones}
        calibration=('Reviewed captured calibration frame '+str(plan['reference']['frame'])+
            ' horizontally translated to the first sampled pelvis. Captured reference height/orientation retained; cropped first-pose lean and vertical offset are not reset. Sampled source motion remains unchanged.')
    def trs(matrix):
        loc,rot,scale=matrix.decompose()
        if any(not math.isfinite(v) or abs(v)>1e5 for row in matrix for v in row) or max(abs(v-1) for v in scale)>1e-5:raise ValueError('Finite unit-scale rigid source matrices required')
        return list(loc),[rot.x,rot.y,rot.z,rot.w]
    nodes=[]
    for b in bones:
        local=reference[b.parent.name].inverted()@reference[b.name] if b.parent else reference[b.name]
        loc,rot=trs(local);node={'name':b.name,'translation':loc,'rotation':rot,'scale':[1,1,1]}
        if b.children:node['children']=[indexes[c.name] for c in b.children]
        nodes.append(node)
    samples={b.name:{'translation':[],'rotation':[]} for b in bones};witness=[]
    for frame in frames:
        scene.frame_set(frame);bpy.context.view_layer.update()
        worlds={b.name:C@arm.matrix_world@arm.pose.bones[b.name].matrix for b in bones}
        for b in bones:
            local=worlds[b.parent.name].inverted()@worlds[b.name] if b.parent else worlds[b.name]
            loc,rot=trs(local);previous=samples[b.name]['rotation']
            if previous and sum(a*c for a,c in zip(previous[-1],rot))<0:rot=[-v for v in rot]
            samples[b.name]['translation'].append(loc);samples[b.name]['rotation'].append(rot)
        witness.append({'source_frame':frame,'worlds':[[list(row) for row in worlds[b.name]] for b in bones]})
    binary=bytearray();views=[];accessors=[]
    def accessor(values,width,kind):
        while len(binary)%4:binary.append(0)
        offset=len(binary);flat=[v for row in values for v in row] if width>1 else values
        binary.extend(struct.pack('<'+'f'*len(flat),*flat));views.append({'buffer':0,'byteOffset':offset,'byteLength':len(flat)*4})
        entry={'bufferView':len(views)-1,'componentType':5126,'count':len(values),'type':kind}
        if width==1:entry.update(min=[min(values)],max=[max(values)])
        accessors.append(entry);return len(accessors)-1
    times=[i/plan['fps'] for i in range(len(frames))];time_accessor=accessor(times,1,'SCALAR');samplers=[];channels=[]
    for b in bones:
        for path,width,kind in [('translation',3,'VEC3'),('rotation',4,'VEC4')]:
            samplers.append({'input':time_accessor,'output':accessor(samples[b.name][path],width,kind),'interpolation':'LINEAR'})
            channels.append({'sampler':len(samplers)-1,'target':{'node':indexes[b.name],'path':path}})
    document={'asset':{'version':'2.0','generator':'Bounded source-only BVH sampler'},'scene':0,
        'scenes':[{'nodes':[indexes[root.name]]}],'nodes':nodes,
        'animations':[{'name':args.source.stem,'samplers':samplers,'channels':channels}],
        'buffers':[{'byteLength':len(binary)}],'bufferViews':views,'accessors':accessors}
    encoded=json.dumps(document,separators=(',',':')).encode();encoded+=b' '*((-len(encoded))%4);binary.extend(b'\0'*((-len(binary))%4))
    total=12+8+len(encoded)+8+len(binary)
    payload=struct.pack('<4sII',b'glTF',2,total)+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
    args.output.mkdir(parents=True,exist_ok=False);target=args.output/'motion.glb';target.write_bytes(payload)
    rights={**plan['rights'],'source_sha256':hashlib.sha256(payload).hexdigest()}
    rights['modifications']+='; '+calibration+'; sampled source frames '+str(plan['frames'])+' at intended '+str(plan['fps'])+'fps (rounded BVH timing tolerance <=1e-6sec/frame); no geometry.'
    (args.output/'source-provenance.json').write_text(json.dumps(rights,indent=2,ensure_ascii=False),encoding='utf-8')
    report={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':str(args.source.resolve()),
        'source_sha256':plan['source_sha256'],'plan_sha256':hashlib.sha256(args.plan.read_bytes()).hexdigest(),
        'writer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'plan_reader_sha256':hashlib.sha256(Path(__file__).with_name('bvh_source_plan.py').read_bytes()).hexdigest(),
        'blender':bpy.app.version_string,'probe':probe,'frames':len(frames),'fps':plan['fps'],
        'node_names':[b.name for b in bones],'reference_mode':plan['reference']['mode'],'calibration':calibration,
        'reference_world_witness':[[list(row) for row in reference[b.name]] for b in bones],
        'motion_glb_sha256':hashlib.sha256(payload).hexdigest(),'world_witness':witness,
        'normal_speed_continuous_viewing':False,'scope':'Source native-transform witness only. Reopen, independent GLB decode comparison, retargeting, skin and visual acceptance are separate.'}
    (args.output/'native-witness.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    scene.frame_set(frames[0]);bpy.ops.wm.save_as_mainfile(filepath=str(args.output/'source-scene.blend'),check_existing=False)
    print(json.dumps({k:v for k,v in report.items() if k!='world_witness'}))

if __name__=='__main__':main()
