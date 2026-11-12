"""Explicit scene-only material/light refinement. Does not open, save or render files."""
from __future__ import annotations
import math


def _number(value, low, high, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label}: expected finite number in [{low}, {high}]')
    return float(value)


def _name(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError('Expected a nonempty explicit name')
    return value


def _vector(value, length, label, low=-1e6, high=1e6):
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f'{label}: expected {length} numbers')
    return [_number(v, low, high, label) for v in value]


def _keys(obj, allowed, required=()):
    if not isinstance(obj, dict) or set(obj) - set(allowed) or set(required) - set(obj):
        raise ValueError('Unknown or missing configuration fields')


def validate_config(cfg):
    """Validate JSON values without importing Blender."""
    _keys(cfg, {'schema','objects','collection','materials','lights','add_lights'}, {'schema','objects','collection'})
    if cfg['schema'] != 1 or isinstance(cfg['schema'], bool):
        raise ValueError('Scene refinement schema 1 required')
    _name(cfg['collection'])
    if not isinstance(cfg['objects'], list) or not cfg['objects'] or len(set(cfg['objects'])) != len(cfg['objects']):
        raise ValueError('Explicit unique scene objects required')
    for name in cfg['objects']: _name(name)
    for group in ('materials','lights','add_lights'):
        rows = cfg.get(group, [])
        if not isinstance(rows, list): raise ValueError(f'{group} must be an array')
        names = []
        for row in rows:
            if not isinstance(row, dict): raise ValueError('Expected row object')
            names.append(_name(row.get('name')))
        if len(set(names)) != len(names): raise ValueError(f'Duplicate {group} name')
    for mat in cfg.get('materials', []):
        _keys(mat, {'name','inputs','quiet','contact'}, {'name'})
        for op in mat.get('inputs', []):
            _keys(op, {'node','socket','value'}, {'node','socket','value'})
            _name(op['node']); _name(op['socket'])
            value=op['value']
            if isinstance(value,list):
                if len(value) not in (3,4): raise ValueError('Input vectors must have 3 or 4 components')
                _vector(value,len(value),'input')
            else: _number(value,-1e6,1e6,'input')
        for kind in ('quiet','contact'):
            for op in mat.get(kind, []):
                common={'name','source_node','source_socket','target_node','target_socket'}
                extra={'factor','color'} if kind=='quiet' else {'distance','strength','minimum','samples'}
                _keys(op, common|extra, common|extra)
                for key in common: _name(op[key])
                if kind=='quiet':
                    _number(op['factor'],0,1,'factor'); _vector(op['color'],4,'color',0,1)
                else:
                    _number(op['distance'],0.000001,10000,'distance')
                    _number(op['strength'],0,1,'strength'); _number(op['minimum'],0,1,'minimum')
                    if type(op['samples']) is not int or not 1<=op['samples']<=128: raise ValueError('AO samples must be 1..128')
    for op in cfg.get('lights', []):
        _keys(op, {'name','energy','size','color'}, {'name','energy'})
        _number(op['energy'],0,1e6,'energy')
        if 'size' in op: _number(op['size'],0.000001,10000,'size')
        if 'color' in op: _vector(op['color'],3,'light color',0,1)
    for op in cfg.get('add_lights', []):
        _keys(op, {'name','location','target','energy','size','color'}, {'name','location','target','energy','size','color'})
        _vector(op['location'],3,'location'); _vector(op['target'],3,'target')
        if op['location']==op['target']: raise ValueError('Light direction has zero length')
        _number(op['energy'],0,1e6,'energy'); _number(op['size'],0.000001,10000,'size'); _vector(op['color'],3,'color',0,1)
    if set(x['name'] for x in cfg.get('lights',[])) & set(x['name'] for x in cfg.get('add_lights',[])):
        raise ValueError('Existing and new light names overlap')
    return cfg


def _local_plain(data):
    if data.library or data.override_library or getattr(data, "animation_data", None):
        raise ValueError(f'Linked, overridden or animated datablock is not editable: {data.name}')


def _socket(sockets, name):
    matches=[s for s in sockets if s.name==name]
    if len(matches)!=1: raise ValueError(f'Missing or ambiguous socket: {name}')
    return matches[0]


def _edge(tree, op):
    source=tree.nodes.get(op['source_node']); target=tree.nodes.get(op['target_node'])
    if source is None or target is None: raise ValueError('Missing exact source/target node')
    src=_socket(source.outputs,op['source_socket']); dst=_socket(target.inputs,op['target_socket'])
    if len(dst.links)!=1 or dst.links[0].from_socket!=src:
        raise ValueError('Expected source-to-target connection differs')
    if src.type!='RGBA' or dst.type!='RGBA': raise ValueError('Color sockets required')
    return src,dst


def _prepare(scene, cfg):
    """Resolve all targets without mutations."""
    import bpy
    from mathutils import Vector
    validate_config(cfg)
    objects=[]
    for name in cfg['objects']:
        obj=scene.objects.get(name)
        if obj is None or obj.type not in ('MESH','EMPTY','ARMATURE'): raise ValueError(f'Scene object not found or unsupported: {name}')
        _local_plain(obj)
        if obj.data is not None: _local_plain(obj.data)
        objects.append(obj)
    allowed=set(objects)
    collection=bpy.data.collections.get(cfg['collection'])
    if collection is None or set(collection.all_objects)!=allowed:
        raise ValueError('Receiver collection must contain exactly the declared scene objects')
    _local_plain(collection)
    plans=[]; write_targets=set(); reserved=set()
    for row in cfg.get('materials',[]):
        mat=bpy.data.materials.get(row['name'])
        if mat is None or not mat.use_nodes or mat.node_tree is None: raise ValueError('Node material not found')
        _local_plain(mat); _local_plain(mat.node_tree)
        owners={o for o in bpy.data.objects if any(s.material==mat for s in o.material_slots)}
        if not owners or not owners<=allowed: raise ValueError(f'Material shared outside scene allowlist: {mat.name}')
        tree=mat.node_tree
        for op in row.get('inputs',[]):
            node=tree.nodes.get(op['node'])
            if node is None: raise ValueError('Exact input node not found')
            socket=_socket(node.inputs,op['socket'])
            if socket.is_linked or not hasattr(socket,'default_value'): raise ValueError('Input must be an unlinked value socket')
            if socket.type not in ('VALUE','RGBA','VECTOR'): raise ValueError('Only numeric/color/vector inputs can change')
            value=op['value']
            if socket.type=='VALUE' and isinstance(value,list): raise ValueError('Scalar input required')
            if socket.type in ('RGBA','VECTOR') and (not isinstance(value,list) or len(value)!=(4 if socket.type=='RGBA' else 3)):
                raise ValueError('Input vector length differs')
            prop=socket.bl_rna.properties.get('default_value')
            vals=value if isinstance(value,list) else [value]
            if prop and any(v<prop.hard_min or v>prop.hard_max for v in vals): raise ValueError('Input value outside RNA range')
            key=(tree.as_pointer(),node.name,op['socket'])
            if key in write_targets: raise ValueError('Duplicate target socket')
            write_targets.add(key); plans.append(('input',mat,op,socket))
        for kind in ('quiet','contact'):
            for op in row.get(kind,[]):
                src,dst=_edge(tree,op)
                key=(tree.as_pointer(),dst.node.name,dst.name)
                if key in write_targets: raise ValueError('Duplicate target socket')
                write_targets.add(key)
                names=[op['name']] if kind=='quiet' else [op['name']+suffix for suffix in (' AO',' Range',' Mix')]
                for name in names:
                    if len(name.encode('utf-8')) > 63: raise ValueError('New node name exceeds Blender name limit')
                    if tree.nodes.get(name) or (tree.as_pointer(),name) in reserved: raise ValueError('New node name already exists')
                    reserved.add((tree.as_pointer(),name))
                plans.append((kind,mat,op,(src,dst)))
    light_plans=[]
    for row in cfg.get('lights',[]):
        light=scene.objects.get(row['name'])
        if light is None or light.type!='LIGHT': raise ValueError('Scene light not found')
        _local_plain(light); _local_plain(light.data)
        if light.data.users!=1: raise ValueError('Shared light datablock refused')
        if light.light_linking.receiver_collection!=collection: raise ValueError('Existing light must already target exact scene collection')
        if 'size' in row and light.data.type!='AREA': raise ValueError('Size tuning requires area light')
        light_plans.append((light,row))
    for row in cfg.get('add_lights',[]):
        if len(row['name'].encode('utf-8')) > 63: raise ValueError('New light name exceeds Blender name limit')
        if bpy.data.objects.get(row['name']) or bpy.data.lights.get(row['name']): raise ValueError('New light name already exists')
    return collection, plans, light_plans


def validate(scene, cfg):
    """Preflight only; return exact mutable datablock ownership for the caller's guard."""
    collection, plans, light_plans = _prepare(scene, cfg)
    return {'materials': sorted({mat.name for _,mat,_,_ in plans}),
            'lights': sorted(light.name for light,_ in light_plans)}


def apply(scene, cfg):
    """Apply preflighted edits; caller owns backup, protection guard and reopen."""
    import bpy
    from mathutils import Vector
    collection, plans, light_plans = _prepare(scene, cfg)
    changes=[]
    for kind,mat,op,target in plans:
        tree=mat.node_tree
        if kind=='input':
            old=list(target.default_value) if target.type in ('RGBA','VECTOR') else target.default_value
            target.default_value=op['value']; changes.append({'kind':kind,'material':mat.name,**op,'before':old})
        elif kind=='quiet':
            src,dst=target; node=tree.nodes.new('ShaderNodeMixRGB'); node.name=op['name']; node.label='Scene pattern contrast'; node.blend_type='MIX'
            node.inputs[0].default_value=op['factor']; node.inputs[2].default_value=op['color']
            tree.links.new(src,node.inputs[1]); tree.links.new(node.outputs[0],dst)
            changes.append({'kind':kind,'material':mat.name,**op})
        else:
            src,dst=target; ao=tree.nodes.new('ShaderNodeAmbientOcclusion'); ao.name=op['name']+' AO'; ao.samples=op['samples']; ao.inputs['Distance'].default_value=op['distance']
            remap=tree.nodes.new('ShaderNodeMapRange'); remap.name=op['name']+' Range'; remap.clamp=True
            remap.inputs['From Min'].default_value=0; remap.inputs['From Max'].default_value=1
            remap.inputs['To Min'].default_value=op['minimum']; remap.inputs['To Max'].default_value=1
            mix=tree.nodes.new('ShaderNodeMixRGB'); mix.name=op['name']+' Mix'; mix.blend_type='MULTIPLY'; mix.inputs[0].default_value=op['strength']
            tree.links.new(ao.outputs['AO'],remap.inputs['Value']); tree.links.new(src,mix.inputs[1]); tree.links.new(remap.outputs['Result'],mix.inputs[2]); tree.links.new(mix.outputs[0],dst)
            changes.append({'kind':kind,'material':mat.name,**op})
    for light,row in light_plans:
        old={k:(list(light.data.color) if k=='color' else getattr(light.data,k)) for k in row if k!='name'}
        for key,value in row.items():
            if key!='name': setattr(light.data,key,value)
        changes.append({'kind':'light','before':old,**row})
    for row in cfg.get('add_lights',[]):
        data=bpy.data.lights.new(row['name'],'AREA'); obj=bpy.data.objects.new(row['name'],data); scene.collection.objects.link(obj)
        obj.location=row['location']; obj.rotation_euler=(Vector(row['target'])-obj.location).to_track_quat('-Z','Y').to_euler()
        data.shape='DISK'; data.energy=row['energy']; data.size=row['size']; data.color=row['color']; obj.light_linking.receiver_collection=collection
        changes.append({'kind':'add_light','receiver_collection':collection.name,**row})
    return {'changes':changes,'scene_objects':sorted(cfg['objects']),'receiver_collection':collection.name,'static_only':True,'character_modified':False}
