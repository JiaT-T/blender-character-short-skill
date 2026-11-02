"""Opt-in Eevee matte bands for explicit static scene surfaces only."""
import math
import bpy


def apply_matte_style(scene, config, stage_materials, story_materials):
    if config is None:
        return None
    if not isinstance(config, dict) or set(config) - {'mix', 'stage', 'story'}:
        raise ValueError('matte_style accepts only mix, stage and story')
    mix = config.get('mix', .35)
    if isinstance(mix, bool) or not isinstance(mix, (int, float)) or not math.isfinite(mix) or not 0 <= mix <= 1:
        raise ValueError('matte_style mix must be finite within0..1')
    selected = []
    for namespace, mapping in [('stage', stage_materials), ('story', story_materials)]:
        names = config.get(namespace, [])
        if not isinstance(names, list) or any(not isinstance(n, str) or not n for n in names) or len(set(names)) != len(names):
            raise ValueError('matte_style surface selections require distinct names')
        for name in names:
            if name not in mapping:
                raise ValueError('Unknown matte_style '+namespace+' surface: '+name)
            selected.append((namespace, name, mapping[name]))
    if not selected or len({m for _, _, m in selected}) != len(selected):
        raise ValueError('Select at least one distinct scene material')
    protected = {m for o in scene.objects if o.type == 'MESH' and any(x.type == 'ARMATURE' for x in o.modifiers) for m in o.data.materials if m}
    prepared = []
    # Validate the entire selection before adding or relinking any node.
    for namespace, name, material in selected:
        if material in protected or not material.use_nodes:
            raise ValueError('Matte style requires an unshared static scene shader')
        nt = material.node_tree
        if (material.animation_data and material.animation_data.action) or (nt.animation_data and nt.animation_data.action):
            raise ValueError('Do not style animated scene materials')
        outputs = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output]
        if len(outputs) != 1 or len(outputs[0].inputs['Surface'].links) != 1:
            raise ValueError('Matte style requires one linked surface output')
        shader = outputs[0].inputs['Surface'].links[0].from_node
        if shader.type != 'BSDF_PRINCIPLED':
            raise ValueError('Matte style requires a direct Principled surface')
        for socket, expected in [('Alpha', 1), ('Transmission Weight', 0), ('Emission Strength', 0)]:
            value = shader.inputs[socket]
            if value.is_linked or value.default_value != expected:
                raise ValueError('Do not style transparent, transmitting or luminous surfaces')
        if shader.inputs['Base Color'].is_linked:
            raise ValueError('Matte style requires an explicit flat base color')
        color = tuple(shader.inputs['Base Color'].default_value)
        if not all(math.isfinite(v) and v >= 0 for v in color):
            raise ValueError('Invalid matte surface base color')
        prepared.append((namespace, name, material, shader, outputs[0], color))
    records = []
    for namespace, name, material, shader, output, color in prepared:
        if mix:
            nt = material.node_tree
            diffuse = nt.nodes.new('ShaderNodeBsdfDiffuse');diffuse.inputs['Color'].default_value = (1,1,1,1)
            rgb = nt.nodes.new('ShaderNodeShaderToRGB');nt.links.new(diffuse.outputs[0],rgb.inputs[0])
            bw = nt.nodes.new('ShaderNodeRGBToBW');nt.links.new(rgb.outputs[0],bw.inputs[0])
            ramp = nt.nodes.new('ShaderNodeValToRGB');ramp.name = 'Scene matte / three light bands';ramp.color_ramp.interpolation = 'CONSTANT'
            ramp.color_ramp.elements[0].position = 0;ramp.color_ramp.elements[0].color = (.52,.52,.52,1)
            ramp.color_ramp.elements[1].position = .45;ramp.color_ramp.elements[1].color = (1,1,1,1)
            mid = ramp.color_ramp.elements.new(.15);mid.color = (.78,.78,.78,1);nt.links.new(bw.outputs[0],ramp.inputs[0])
            multiply = nt.nodes.new('ShaderNodeMixRGB');multiply.blend_type = 'MULTIPLY';multiply.inputs[0].default_value = 1;multiply.inputs[1].default_value = color;nt.links.new(ramp.outputs[0],multiply.inputs[2])
            surface = nt.nodes.new('ShaderNodeEmission');nt.links.new(multiply.outputs[0],surface.inputs[0]);surface.inputs[1].default_value = 1
            for link in list(output.inputs['Surface'].links):nt.links.remove(link)
            blend = nt.nodes.new('ShaderNodeMixShader');blend.name = 'Scene matte / original volume mix';blend.inputs[0].default_value = mix;nt.links.new(shader.outputs[0],blend.inputs[1]);nt.links.new(surface.outputs[0],blend.inputs[2]);nt.links.new(blend.outputs[0],output.inputs['Surface'])
        records.append({'namespace':namespace,'key':name,'material':material.name,'mix':mix,'base_color':list(color)})
    return {'mode':'opt-in Eevee three-band matte mix','materials':records,'limitations':'Static opaque flat scene surfaces only; original physical weight1-mix retains some volume/shadow. Requires sampled and temporal review. Not character shader or source-render equivalence.'}
