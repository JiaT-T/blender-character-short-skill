"""Import static set pieces, normalize their size and bind the story palette."""
import math
import bpy
from mathutils import Matrix, Euler, Vector
from scene_asset_inputs import collect_scene_asset_inputs, inspect_static_glb


def add_scene_assets(scene, story_path, height, ground, materials):
    entries = collect_scene_asset_inputs(story_path)
    if not entries:
        return None
    records = []
    for entry in entries:
        prefix = 'Scene asset / ' + entry['name']
        if any(o.name == prefix or o.name.startswith(prefix + ' / ') for o in bpy.data.objects):
            raise ValueError('Scene asset namespace already exists: ' + prefix)
        source_materials = inspect_static_glb(entry['path'])['materials']
        if any(name in bpy.data.materials for name in source_materials):
            raise ValueError('Scene asset source material names collide with existing data; namespace them in the reviewed asset')
        before = set(bpy.data.objects)
        old_materials = set(bpy.data.materials)
        original_camera = scene.camera
        bpy.ops.import_scene.gltf(filepath=entry['path'], import_pack_images=False)
        imported = set(bpy.data.objects) - before
        scene.camera = original_camera
        if not imported or any(o.type not in {'MESH', 'EMPTY'} or o.animation_data for o in imported):
            raise ValueError('Imported scene asset must contain only static meshes and empties')
        meshes = [o for o in imported if o.type == 'MESH']
        if not meshes or any(o.data.shape_keys or o.modifiers or o.constraints for o in imported if o.type == 'MESH'):
            raise ValueError('Unsupported imported mesh rig/modifier/constraint')
        bpy.context.view_layer.update()
        points = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
        if not points or any(not math.isfinite(c) for point in points for c in point):
            raise ValueError('Scene asset contains empty or nonfinite geometry')
        low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
        high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
        if high.z - low.z <= 1e-8:
            raise ValueError('Scene asset requires a nonzero vertical extent')
        anchor = Vector(((low.x + high.x) / 2, (low.y + high.y) / 2, low.z))
        scale = entry['height'] * height / (high.z - low.z)
        position = Vector((entry['position'][0] * height, entry['position'][1] * height,
                           ground + entry['position'][2] * height))
        rotation = Euler(tuple(math.radians(v) for v in entry['rotation']), 'XYZ').to_matrix().to_4x4()
        transform = Matrix.Translation(position) @ rotation @ Matrix.Scale(scale, 4) @ Matrix.Translation(-anchor)
        root = bpy.data.objects.new(prefix, None)
        scene.collection.objects.link(root)
        root.matrix_world = transform
        root['narrative_role'] = entry['purpose']
        roots = [o for o in imported if o.parent not in imported]
        for o in roots:
            world = o.matrix_world.copy()
            o.parent = root
            o.matrix_parent_inverse = Matrix.Identity(4)
            o.matrix_basis = world
        for o in sorted(imported, key=lambda x: x.name):
            source_name = o.name
            o['scene_asset_source_name'] = source_name
            o.name = prefix + ' / ' + source_name
            o['narrative_role'] = entry['purpose']
            if o.type == 'MESH':
                # Slot names refer to the file's own palette; never edit an imported
                # shader in place or share it with the character's shader.
                for index, slot in enumerate(o.material_slots):
                    source_material = slot.material
                    if source_material is None or source_material.name not in entry['materials']:
                        raise ValueError('Imported material name differs from preflight')
                    o.data.materials[index] = materials[entry['materials'][source_material.name]]
        for material in set(bpy.data.materials) - old_materials:
            if material.users == 0:
                bpy.data.materials.remove(material)
        bpy.context.view_layer.update()
        records.append({**entry, 'normalization': 'bottom-center of imported world-space mesh bounds; uniform height scale; then XYZ rotation and story position',
                        'source_bounds': [list(low), list(high)], 'uniform_scale': scale,
                        'root': root.name, 'objects': sorted(o.name for o in imported),
                        'source_object_names': {o.name:o['scene_asset_source_name'] for o in imported},
                        'mesh_count': len(meshes), 'palette': entry['materials']})
    return {'status': 'static-GLB-imported-story-palette-bound', 'assets': records,
            'limits': 'Static self-contained triangle GLB only. No animation, rigs, cameras, lights, textures or physics. Source/license strings are declarations requiring independent review.'}
