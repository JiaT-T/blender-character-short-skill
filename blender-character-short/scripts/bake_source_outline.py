"""Bake/verify source-GLB outlines in an existing matched probe scene.

This path requires exact GLB vertex ordering/attributes. It does not manufacture
PMX smooth normals or establish website depth/stencil/AA equivalence.
"""
import argparse,sys,json,hashlib,time
from pathlib import Path
import bpy,numpy as np
sys.path.insert(0,str(Path(__file__).parent))
from render_source_probe import read_glb
from glb_morphs import read_position_target
import source_outline

def entries(scene,glb,tint):
    raw,chunks,doc,read=read_glb(glb);found=[];bindings=[];binary=next(v for k,v in chunks if k==0x004e4942)
    for obj in list(scene.objects):
        if obj.type!='MESH' or 'source_mesh_index' not in obj:continue
        mi=int(obj['source_mesh_index']);mati=int(obj['source_material_index']);candidates=[p for p in doc['meshes'][mi]['primitives'] if p.get('material')==mati]
        if len(candidates)!=1:raise ValueError('Ambiguous source primitive: '+obj.name)
        attrs={k:read(i) for k,i in candidates[0]['attributes'].items()};rest=np.array([v.co[:] for v in obj.data.vertices]);expected=attrs['POSITION'][:,[0,2,1]]*np.array([1,-1,1])
        source_outline.require_finite('source/imported basis '+obj.name,rest,expected)
        if rest.shape!=expected.shape or np.abs(rest-expected).max()>1e-5:raise ValueError('Source vertex ordering/positions differ: '+obj.name)
        targets=candidates[0].get('targets',[])
        if targets:
            attrs['_MORPH_TARGET_NAMES']=doc['meshes'][mi].get('extras',{}).get('targetNames')
            attrs['_MORPH_UNSUPPORTED_SEMANTICS']=sorted({key for target in targets for key in target if key!='POSITION'})
            attrs['_MORPH_POSITION_DELTAS']=[read_position_target(doc,binary,target['POSITION'],read)[:,[0,2,1]]*np.array([1,-1,1]) if 'POSITION' in target else np.zeros_like(rest) for target in targets]
        for oi in doc['materials'][mati].get('extras',{}).get('passes',[]):
            rawmat=doc['materials'][oi]
            if rawmat.get('extras',{}).get('family')!='outline':continue
            cfg=source_outline.parameters(rawmat,tint);label=f'Source outline m{mi} p{oi}'
            found.append((obj,attrs,cfg,label));bindings.append({'object':obj.name,'mesh_index':mi,'base_material_index':mati,'outline_material_index':oi,'label':label,'parameters':cfg})
    if not found:raise ValueError('No explicit outline passes found')
    return found,bindings,hashlib.sha256(raw).hexdigest()

def verify(scene,items,frames):
    records=[]
    for frame in frames:
        scene.frame_set(frame);bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get()
        for source,attrs,cfg,label in items:
            expected,_,_,metrics=source_outline.compute_vertices(scene,source,attrs,cfg);obj=scene.objects.get(label)
            if obj is None:raise ValueError('Missing cached outline '+label)
            ev=obj.evaluated_get(dg);me=ev.to_mesh()
            try:
                actual=np.array([v.co[:] for v in me.vertices]);actual=(np.column_stack([actual,np.ones(len(actual))])@np.array(obj.matrix_world).T)[:,:3];source_outline.require_finite('expected/cached outline '+label,expected,actual);err=float(np.max(np.abs(expected-actual)))
            finally:ev.to_mesh_clear()
            records.append({'frame':frame,'outline':label,'max_world_error':err})
            if err>3e-6:raise ValueError(f'Stale or incorrect outline cache at {frame} {label}: {err}; rebake after camera/pose/parameter changes')
    return records

def main():
    p=argparse.ArgumentParser();p.add_argument('--scene',required=True);p.add_argument('--glb',required=True);p.add_argument('--output');p.add_argument('--report',required=True);p.add_argument('--start',type=int,required=True);p.add_argument('--end',type=int,required=True);p.add_argument('--tint',type=float,nargs=3,required=True);p.add_argument('--verify-only',action='store_true');p.add_argument('--remove-legacy-outline',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);started=time.time()
    if a.end<a.start:raise ValueError('Empty frame range')
    if not a.verify_only and (not a.output or Path(a.output).exists()):raise ValueError('Supply a new, unused --output blend path')
    bpy.ops.wm.open_mainfile(filepath=str(Path(a.scene).resolve()));scene=bpy.context.scene;items,bindings,sha=entries(scene,a.glb,a.tint);frames=list(range(a.start,a.end+1));report={'source_glb_sha256':sha,'bindings':bindings,'range':[a.start,a.end],'tint_provenance':'caller-supplied; runtime equivalence must be evidenced separately','mode':'verify' if a.verify_only else 'bake'}
    if not a.verify_only:
        for obj in list(scene.objects):
            if obj.get('source_outline_cache') or (a.remove_legacy_outline and obj.name=='Source outline projected hull'):bpy.data.objects.remove(obj,do_unlink=True)
        _,report['bake']=source_outline.bake(scene,items,frames);scene['outline_source_glb']=str(Path(a.glb).resolve());scene['outline_source_sha256']=sha;scene['outline_global_tint']=json.dumps(a.tint)
        for name in ['SourceOutlineMask','HX_BloomWeight']:
            if not scene.view_layers[0].aovs.get(name):scene.view_layers[0].aovs.add().name=name;scene.view_layers[0].aovs[name].type='VALUE'
    report['verification']=verify(scene,items,frames)
    if not a.verify_only:
        # Saved probe must never retain output-node paths into a historical run.
        scene.use_nodes=True;scene.node_tree.nodes.clear();rl=scene.node_tree.nodes.new('CompositorNodeRLayers');co=scene.node_tree.nodes.new('CompositorNodeComposite');scene.node_tree.links.new(rl.outputs['Image'],co.inputs[0]);scene.render.filepath=str(Path(a.output).with_suffix('.png'));scene.frame_set(a.start);Path(a.output).parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(Path(a.output).resolve()))
    report['elapsed_seconds']=time.time()-started;Path(a.report).parent.mkdir(parents=True,exist_ok=True);Path(a.report).write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8');print('SOURCE_OUTLINE_OK',report['mode'],len(items),len(frames),report['elapsed_seconds'])

if __name__=='__main__':main()
