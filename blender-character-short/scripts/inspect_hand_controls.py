"""Read wrist descendants and actual skin influence without modifying a scene."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--blend',required=True,type=Path)
    p.add_argument('--character',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--min-weight',type=float,default=.01)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if not math.isfinite(a.min_weight) or not 0<=a.min_weight<1:
        raise ValueError('min-weight must be finite and in [0,1)')
    if a.output.exists():raise FileExistsError('Preserve earlier inventory: '+str(a.output))
    source=a.blend.resolve();digest=hashlib.sha256(source.read_bytes()).hexdigest()
    cfg=json.loads(a.character.read_text('utf-8'))
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene=bpy.context.scene;arms=[o for o in scene.objects if o.type=='ARMATURE']
    if len(arms)!=1:raise ValueError('Expected exactly one character armature')
    arm=arms[0];wrists={}
    for side in ['left','right']:
        name=cfg['bones'][side+'_wrist']
        if name not in arm.data.bones:raise ValueError('Missing configured wrist: '+name)
        wrists[side]=arm.data.bones[name]
    meshes=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==arm for m in o.modifiers)]
    if not meshes:raise ValueError('No meshes use the configured character armature')
    stats={}
    for obj in meshes:
        groups={g.index:g.name for g in obj.vertex_groups}
        for vertex in obj.data.vertices:
            for assignment in vertex.groups:
                if assignment.weight<=a.min_weight:continue
                name=groups[assignment.group]
                row=stats.setdefault(name,{'weighted_vertices':0,'weight_sum':0.,'maximum_weight':0.,'meshes':set()})
                row['weighted_vertices']+=1;row['weight_sum']+=assignment.weight
                row['maximum_weight']=max(row['maximum_weight'],assignment.weight);row['meshes'].add(obj.name)
    hands={}
    for side,wrist in wrists.items():
        rows=[]
        for bone in arm.data.bones:
            if wrist not in bone.parent_recursive:continue
            weight=stats.get(bone.name,{'weighted_vertices':0,'weight_sum':0.,'maximum_weight':0.,'meshes':set()})
            pose=arm.pose.bones[bone.name]
            rows.append({'bone':bone.name,'parent':bone.parent.name if bone.parent else None,'deform':bone.use_deform,
                         'head_rest_armature':list(bone.head_local),'tail_rest_armature':list(bone.tail_local),
                         'rest_matrix':list(map(list,bone.matrix_local)),
                         'constraints':[{'type':c.type,'influence':c.influence} for c in pose.constraints],
                         'skin':{**weight,'meshes':sorted(weight['meshes'])}})
        hands[side]={'wrist':wrist.name,'descendant_bones':rows,
                     'weighted_deforming_descendants':sum(r['deform'] and r['skin']['weighted_vertices']>0 for r in rows)}
    if hashlib.sha256(source.read_bytes()).hexdigest()!=digest:raise RuntimeError('Source scene bytes changed')
    report={'status':'readonly-inventory-complete','blend':str(source),'scene_sha256':digest,'armature':arm.name,
            'weight_threshold_exclusive':a.min_weight,'hands':hands,'source_scene_bytes_unchanged':True,
            'scope':'Counts original mesh assignments above threshold under configured wrists. This is not evaluated deformation, automatic rig mapping, a curl axis, fingertip contact, or natural grasp acceptance. Zero counted assignments do not imply a bone cannot affect a constrained/indirect control.'}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print('HAND_CONTROL_INVENTORY',[(s,r['weighted_deforming_descendants']) for s,r in hands.items()],flush=True)


if __name__=='__main__':main()
