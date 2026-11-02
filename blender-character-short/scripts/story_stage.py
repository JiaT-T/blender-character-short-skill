"""Data-authored narrative set pieces; no character-specific geometry or names."""
import math
import bpy
from mathutils import Matrix, Vector


def vector(value, label, positive=False):
    if len(value) != 3 or not all(math.isfinite(float(v)) for v in value):
        raise ValueError(label + ' requires three finite values')
    if positive and min(value) <= 0:
        raise ValueError(label + ' must be positive')
    return tuple(float(v) for v in value)


def add_story_objects(scene, cfg, height, ground, frame, material_sink=None):
    """Optional set.materials and set.objects, in normalized world coordinates.

    Material emission keys remain ordinary saved Blender animation. Objects
    use actual mesh dimensions before bevel, so bevel width is scale-stable.
    """
    items = cfg.get('objects', [])
    parents = {item['name']: item['parent'] for item in items if item.get('parent') is not None}
    if parents:
        declared = [item['name'] for item in items]
        if len(set(declared)) != len(declared):
            raise ValueError('Duplicate story object in parent graph')
        if any(name in scene.objects for name in declared):
            raise ValueError('Parented story object names must be distinct from existing scene objects')
        for name, parent in parents.items():
            if not isinstance(parent, str) or not parent or (parent not in declared and parent not in scene.objects):
                raise ValueError('Parent references a missing scene/story object: ' + str(parent))
        for name in parents:
            active = set()
            cursor = name
            while cursor in parents:
                if cursor in active:
                    raise ValueError('Story object parent graph contains a cycle')
                active.add(cursor)
                cursor = parents[cursor]
    definitions = cfg.get('materials', {})
    materials = {}
    for name, definition in definitions.items():
        color = vector(definition['color'], 'Material color')
        if min(color) < 0:
            raise ValueError('Material color must be nonnegative')
        rough = float(definition.get('roughness', .7))
        emission = float(definition.get('emission', 0))
        if not math.isfinite(emission) or emission < 0 or not 0 <= rough <= 1:
            raise ValueError('Invalid material roughness or emission')
        mat = bpy.data.materials.new('Story set / ' + name)
        mat.diffuse_color = (*color, 1)
        mat.use_nodes = True
        shader = mat.node_tree.nodes.get('Principled BSDF')
        shader.inputs['Base Color'].default_value = (*color, 1)
        shader.inputs['Roughness'].default_value = rough
        shader.inputs['Metallic'].default_value = definition.get('metallic', 0)
        emission_color = vector(definition.get('emission_color', color), 'Emission color')
        if min(emission_color) < 0:
            raise ValueError('Emission color must be nonnegative')
        shader.inputs['Emission Color'].default_value = (*emission_color, 1)
        shader.inputs['Emission Strength'].default_value = emission
        for key in definition.get('emission_keys', []):
            value = float(key['value'])
            if not math.isfinite(value) or value < 0:
                raise ValueError('Emission keys must be finite and nonnegative')
            socket = shader.inputs['Emission Strength']
            socket.default_value = value
            socket.keyframe_insert('default_value', frame=frame(key['t']))
        if mat.node_tree.animation_data and mat.node_tree.animation_data.action:
            for curve in mat.node_tree.animation_data.action.fcurves:
                for key in curve.keyframe_points:
                    key.interpolation = 'LINEAR'
        materials[name] = mat
    if material_sink is not None:
        material_sink.update(materials)
    records = []
    names = set()
    created = {}
    for item in items:
        name = item['name']
        if name in names:
            raise ValueError('Duplicate story-set object: ' + name)
        names.add(name)
        shape = item.get('shape', 'box')
        size = vector(item['size'], 'Object size', positive=True)
        position = vector(item['position'], 'Object position')
        material = materials.get(item['material'])
        if material is None:
            raise ValueError('Unknown story-set material: ' + item['material'])
        bevel = float(item.get('bevel', 0))
        if not math.isfinite(bevel) or bevel < 0 or bevel > min(size) / 2:
            raise ValueError('Object bevel must fit its dimensions')
        if shape == 'box':
            bpy.ops.mesh.primitive_cube_add(size=1)
        elif shape == 'cylinder':
            bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=.5, depth=1)
        else:
            raise ValueError('Unsupported story-set shape: ' + shape)
        obj = bpy.context.object
        obj.name = name
        for vertex in obj.data.vertices:
            vertex.co = Vector((vertex.co[i] * size[i] * height for i in range(3)))
        obj.location = (position[0] * height, position[1] * height,
                        (0 if name in parents else ground) + position[2] * height)
        obj.rotation_euler = tuple(math.radians(v) for v in
                                   vector(item.get('rotation', [0, 0, 0]), 'Rotation'))
        obj.data.materials.append(material)
        if bevel:
            modifier = obj.modifiers.new('Manufactured soft edge', 'BEVEL')
            modifier.width = bevel * height
            modifier.segments = 3
        obj['narrative_role'] = item.get('purpose', '')
        created[name] = obj
        records.append({'name': name, 'shape': shape, 'position': position,
                        'size': size, 'material': item['material'],
                        'purpose': item.get('purpose', '')})
    for name, parent_name in parents.items():
        parent = created[parent_name] if parent_name in created else scene.objects[parent_name]
        obj = created[name]
        obj.parent = parent
        obj.parent_type = 'OBJECT'
        obj.matrix_parent_inverse = Matrix.Identity(4)
        record = next(row for row in records if row['name'] == name)
        record.update(parent=parent_name, coordinate_space='parent-local normalized height, before inherited scale')
    if parents:
        bpy.context.view_layer.update()
    return {'objects': records, 'materials': list(materials)}
