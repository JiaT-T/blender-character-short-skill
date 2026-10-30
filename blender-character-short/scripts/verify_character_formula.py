"""Isolated Blender 4.5 Character formula acceptance probe (extended draft).

Run only in a fresh, background Blender process, never against a production blend:
  blender.exe --background --factory-startup --python-exit-code 1 \
    --python verify_character_formula_extended.py -- \
    --builder path/to/character_material.py \
    --cases path/to/character-formula-cases.json \
    --cases path/to/character-formula-additional-cases.json --output new/output/directory

The script creates synthetic float EXR inputs, invokes the real material builder,
pins Geometry Normal/Incoming consumers to the case's exact unit vectors, and
renders a full-coverage emission plane through an orthographic camera. This tests
the formula graph, texture channel selection and UV mirror, not geometry adapters,
website rasterization, full character appearance, Bloom or color management.

It exports linear 32-bit EXRs for Combined and diagnostic AOVs, reloads them,
compares center pixel AND a flat 4x4 center ROI with independently evaluated CPU
formulas, and writes progressive JSON reports. No production script is edited.
Repeat --cases to run both documents (original seven plus four additional cases).
The supplemental second-gate-on control is added only when its source case exists.
--cpu-only evaluates the independent source formulas without importing Blender or
the production builder. That mode never reports Blender acceptance.
No Blender run was performed when this extended draft was delivered.
"""

import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
import traceback

import numpy as np


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    """Atomic checkpoint inside this probe's newly created output directory."""
    path = Path(path)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                              allow_nan=False), encoding='utf-8')
    tmp.replace(path)


def normalized(value):
    value = np.asarray(value, dtype=np.float64)
    length = float(np.linalg.norm(value))
    if length <= 1e-12:
        raise ValueError('Fixture requests normalization of a zero vector')
    return value / length


def source_linear_color(values):
    """Source lf color-parameter decode; never call the production helper."""
    rgb = np.asarray(values[:3], dtype=np.float64)
    return np.asarray([c / 12.92 if c < .04045 else ((c + .055) / 1.055) ** 2.4
                       for c in rgb], dtype=np.float64)


def fixture_texture(case, binding, uv):
    """CPU LINEAR/CLAMP sampling of declared FLOAT32 data texture inputs.

    All accepted probes sample an exact center or a 1x1 constant, so source
    REPEAT/CLAMP and vertical-origin differences cannot affect these cases.
    No actual Blender texture output is used as a reference.
    """
    shader = case['raw_material']['extras']['shader']
    index = shader['textures'][binding]['index']
    desc = next(t for t in case['texture_fixtures'] if t['index'] == index)
    pixels = np.asarray(desc['pixels_top_to_bottom'], dtype=np.float64).reshape(desc['height'], desc['width'], 4)
    x, y = float(uv[0]) * desc['width'] - .5, float(uv[1]) * desc['height'] - .5
    x0, y0 = math.floor(x), math.floor(y)
    tx, ty = x - x0, y - y0
    def get(ix, iy):
        return pixels[min(max(iy, 0), desc['height']-1), min(max(ix, 0), desc['width']-1)]
    return ((1-tx)*(1-ty)*get(x0, y0) + tx*(1-ty)*get(x0+1, y0)
            + (1-tx)*ty*get(x0, y0+1) + tx*ty*get(x0+1, y0+1))


def cpu_reference(case):
    """Source ah/Wp/Up/Hp/Lp algebra; independent of builder and render output."""
    s = case['source_inputs']
    shader = case['raw_material']['extras']['shader']
    p = shader['floats']
    colors = shader['colors']
    def flag(name):
        return float(p.get(name, 0)) > .1
    def color(name):
        return source_linear_color(colors.get(name, [1, 1, 1, 1]))
    main = np.asarray(s['main_linear_rgba'], dtype=np.float64)
    original = np.asarray(s['mask_original_sample_rgba'], dtype=np.float64)
    n = np.asarray(s['N_view'], dtype=np.float64)
    view = np.asarray(s['V_view'], dtype=np.float64)
    light_view = np.asarray(s['L_view'], dtype=np.float64)
    nov = float(np.clip(np.dot(n, view), 0, 1))
    noh = float(np.clip(np.dot(n, normalized(view + light_view)), 0, 1))
    mirror = False
    face_sample = None
    if s['face_shadow_enabled']:
        light = np.asarray(s['L_world'], dtype=np.float64)
        oy = np.asarray(s['object_y_world'], dtype=np.float64)
        oz = np.asarray(s['object_z_world'], dtype=np.float64)
        mirror = float(np.dot(light, oz)) <= 0.0
        face_sample = np.asarray(s['mask_mirrored_sample_rgba'] if mirror
                                 else s['mask_original_sample_rgba'], dtype=np.float64)
        ny = p['IF_SHADOW_OBJECT_SPACE_NORMAL_MAP_Y'] * (2 * face_sample[3] - 2) + 1
        nz = 2 * face_sample[2] - 1
        # Source normalizes the world normal before discarding its Y component.
        # Do NOT renormalize this normal after projecting to XZ.
        nf = normalized(ny * oy + nz * oz)
        light_xz = normalized(light[[0, 2]])
        h = .5 * float(np.dot(nf[[0, 2]], light_xz)) + .5
    else:
        h = .5 * float(np.dot(n, light_view)) + .5
    alpha_mask = p['IF_MAIN_ALPHA_FOR_SHADOWMASK']
    g = original[1] * (1 - alpha_mask) + main[3] * alpha_mask
    branch = 1 - math.floor(1.5 - g)
    edge = (1.25 * g - .12) * (1 - branch) + (1.2 * g - .1) * branch
    fv = .5 * (h + edge) + 1 - p['_FirstShadow']
    smooth = max(p['_SmoothFactor'], .0001)
    hard = 1 - math.floor(fv)
    soft = 1 - max(0.0, min(1.0, (fv - 1 + smooth) / (2 * smooth)))
    w1 = hard * (1 - p['IF_SMOOTH_SHADOW']) + soft * p['IF_SMOOTH_SHADOW']
    intensity = s['shadowIntensity']
    w1 = intensity * (1 - s['shadowMapLit'] + w1 * s['shadowMapLit'])
    second_value = .5 * (h + g) + 1 - p['_SecondShadow']
    w2 = intensity * (1 - math.floor(second_value))
    allowed = intensity * (1 - math.floor(g + .9))
    no = color('_NoShadowColor')
    first = color('_FirstShadowColor')
    second = color('_SecondShadowColor')
    band1 = no * (1 - w1) + first * w1
    band2 = first * (1 - w2) + second * w2
    band = band1 * (1 - allowed) + band2 * allowed
    base = main[:3] * color('_AlbedoColor') * float(p.get('_AlbedoColorIntensity', 1))
    albedo = base.copy()
    skin_rate = 0.0
    skin_target = None
    if flag('IF_SKIN'):
        # Only the ordinary single-zone, vertexGate=1 fixtures are admitted.
        skin_rate = float(p['_SkinRate']) * float(s.get('skin_vertex_gate', 1))
        ramp = fixture_texture(case, '_SkinRamp', (h, .5))[:3]
        skin_target = base * ramp * color('_SkinColor') * float(p['_SkinIntensity'])
        albedo = base * (1-skin_rate) + skin_target * skin_rate

    # Attenuation lives outside the style-specular gate because Matcap uses it.
    falloff = None
    attenuation = 1.0
    if flag('IF_SPEC_ATTENUATION'):
        falloff = float(np.clip(nov ** p['_SpecAttenuationPow'] / p['_SpecAttenuationSmoothness'], 0, 1))
        attenuation = min(falloff * falloff * (3-2*falloff), 1.0)
    spec_gate = original[2] * float(p.get('_SpecularIntensity', 0))
    lobe = 0.0
    highlight = 0.0
    if spec_gate > 0:
        nh = max(noh, .0001)
        invert = float(p.get('IF_INVERT_SPECULAR', 0))
        lobe = (nh * (1-invert) + (1-nh) * invert) ** p['_SpecularShiness'] + original[0]
        highlight = float(np.clip((lobe - p['_SpecularSmoothFactor'] - 1) / p['_SpecularSmoothFactor'], 0, 1)) * attenuation
        if flag('IF_SPECULAR_SHADOW_INTENSITY'):
            shaded = float(w1 + allowed >= .0001)
            highlight *= 1-shaded + float(p['_SpecularShadowIntensity']) * shaded
    specular = albedo * spec_gate * color('_SpecularColor') * highlight

    rim = np.zeros(3, dtype=np.float64)
    rim_edge_raw = rim_edge = rim_allowed = rim_facing = 0.0
    if flag('IF_RIM') and s.get('front_facing', True):
        rim_edge_raw = float(np.clip((1-nov-p['_RimMin']) / max(p['_RimMax']-p['_RimMin'], .0001), 0, 1))
        rim_edge = rim_edge_raw * rim_edge_raw * (3-2*rim_edge_raw)
        rim_allowed = float(np.dot(n, view) + p['_RimThreshold'] >= 0)
        rim_facing = float(np.clip(np.dot(n, s['rim_direction_view']), 0, 1))
        rim = (rim_edge * p['_RimIntensity'] * color('_RimColor') * rim_allowed
               * s.get('rim_vertex_gate', 1) * rim_facing)

    cap = np.zeros(3, dtype=np.float64)
    cap_mask = cap_shadow = 0.0
    if '_USE_MATCAP' in shader['keywords']:
        # A 1x1 constant deliberately excludes camera UV/YScale from this proof.
        sample = fixture_texture(case, '_MatCapTex', (.5, .5))
        cap_shadow = 1 - p.get('_MapCapShadowStrength', 0) * float(w1 >= .001) * w1
        mask_mix = p['_MatcapMask']
        cap_mask = 1-mask_mix + original[0]*attenuation*mask_mix
        cap = sample[:3] * cap_shadow * cap_mask

    rgb = ((albedo * band + specular + rim + cap) * np.asarray(s['LightColor_linear_rgb'])
           * np.asarray(s['Ambient_linear_rgb']) * color('_GlobalTint'))
    result = dict(H=h, NoV=nov, NoH=noh, firstWeight=float(w1), secondWeight=float(w2),
                  secondAllowed=float(allowed), band=band.tolist(),
                  finalRGB=rgb.tolist(), shadowMaskG=float(g), faceMirror=mirror,
                  maskBranch=float(branch), maskEdge=float(edge), firstValue=float(fv),
                  firstHard=float(hard), firstSoft=float(soft), secondValue=float(second_value),
                  faceMaskSampleUV=None, faceMaskSampleRGBA=None,
                  coverage=1.0, BloomWeight=0.0, BaseAlbedo=base.tolist(),
                  skinRate=skin_rate, skinModifiedAlbedo=albedo.tolist(),
                  skinTarget=None if skin_target is None else skin_target.tolist(),
                  specFalloff=falloff, specAttenuation=attenuation,
                  specularGate=float(spec_gate), specularLobe=float(lobe),
                  specularHighlight=float(highlight), StyleSpecular=specular.tolist(),
                  rimEdgeRaw=rim_edge_raw, rimEdgeCubic=rim_edge,
                  rimAllowed=rim_allowed, rimFacing=rim_facing, RimTerm=rim.tolist(),
                  matcapMask=float(cap_mask), matcapShadow=float(cap_shadow),
                  MatcapTerm=cap.tolist())
    if face_sample is not None:
        result['faceMaskSampleRGBA'] = face_sample.tolist()
        result['faceMaskSampleUV'] = [1-s['uv'][0] if mirror else s['uv'][0], s['uv'][1]]
    return result


def expected_aovs(case, expected):
    """Compute diagnostic targets from the independent CPU result, not Blender."""
    values = {'Image': expected['finalRGB'], 'ProbeFinalLinear': expected['finalRGB'],
              'HalfLambert': expected['H'], 'ShadowBand': expected['band'],
              'ProbeFirstWeight': expected['firstWeight'], 'ProbeSecondWeight': expected['secondWeight'],
              'ProbeSecondAllowed': expected['secondAllowed'], 'ProbeOriginalMaskG': expected['shadowMaskG'],
              'HX_BloomWeight': expected['BloomWeight'], 'ImageAlpha': expected['coverage'],
              'BaseAlbedo': expected['BaseAlbedo'], 'SkinRate': expected['skinRate'],
              'StyleSpecular': expected['StyleSpecular'], 'RimTerm': expected['RimTerm'],
              'MatcapTerm': expected['MatcapTerm'],
              'SourceNormal': (np.asarray(case['blender_adapter']['normal_world'])*.5+.5).tolist()}
    if case['source_inputs']['face_shadow_enabled']:
        values['ProbeFaceB'] = expected['faceMaskSampleRGBA'][2]
        values['ProbeFaceA'] = expected['faceMaskSampleRGBA'][3]
    return values


def check_reference(case, expected):
    supplied = case['expected_float64']
    # Reject unimplemented declarations instead of silently checking an intersection.
    missing = set(supplied) - set(expected)
    if missing:
        raise ValueError('CPU reference omits declared fields: ' + repr(sorted(missing)))
    for key in supplied:
        if supplied[key] is None or expected[key] is None:
            if supplied[key] is not expected[key]:
                raise ValueError(f'Fixture/CPU optional mismatch {case["id"]} {key}')
            continue
        if isinstance(supplied[key], bool):
            if bool(expected[key]) != supplied[key]:
                raise ValueError(f'Fixture/CPU boolean mismatch {case["id"]} {key}')
            continue
        cpu_value = np.asarray(expected[key], dtype=np.float64)
        declared_value = np.asarray(supplied[key], dtype=np.float64)
        if not np.isfinite(cpu_value).all() or not np.isfinite(declared_value).all():
            raise ValueError(f'Non-finite CPU/declaration field {case["id"]} {key}')
        delta = float(np.max(np.abs(cpu_value - declared_value)))
        if delta > 2e-6:
            raise ValueError(f"Fixture/CPU mismatch {case['id']} {key}: {delta}")
    calculated = expected_aovs(case, expected)
    for key, target in case.get('expected_aovs', {}).items():
        if key not in calculated:
            raise ValueError('Unsupported declared expected AOV: ' + key)
        if not np.isfinite(np.asarray(target)).all():
            raise ValueError('Non-finite declared expected AOV: ' + key)
        delta = float(np.max(np.abs(np.asarray(calculated[key])-np.asarray(target))))
        if delta > 2e-6:
            raise ValueError(f'Fixture/CPU AOV mismatch {case["id"]} {key}: {delta}')


def selected_cases(document, add_gate_control):
    cases = copy.deepcopy(document['cases'])
    source = next((c for c in cases if c['id'] == 'second_gate_off'), None)
    if add_gate_control and source is not None:
        control = copy.deepcopy(source)
        control['id'] = 'second_gate_on_control'
        control['title'] = 'Supplemental second-shadow gate-on control'
        control['supplemental'] = True
        change = source['optional_sensitivity_check_not_seventh_primary_case']['change_only']
        rgba = change['mask_original_sample_rgba']
        control['source_inputs']['mask_original_sample_rgba'] = rgba
        control['source_inputs']['mask_mirrored_sample_rgba'] = rgba
        mask_index = control['raw_material']['extras']['shader']['textures']['_MaskTex']['index']
        next(t for t in control['texture_fixtures'] if t['index'] == mask_index)['pixels_top_to_bottom'] = [rgba]
        control['raw_material']['name'] = 'FORMULA_second_gate_on_control'
        control['expected_float64'] = cpu_reference(control)
        control.pop('expected_float32', None)
        control.pop('expected_half_storage_from_float32', None)
        control.pop('optional_sensitivity_check_not_seventh_primary_case', None)
        cases.append(control)
    return cases


def assert_isolated_fixture(case):
    s = case['source_inputs']
    raw = case['raw_material']
    shader = raw['extras']['shader']
    f = shader['floats']
    if raw['extras']['family'] != 'character' or shader.get('cubemap'):
        raise ValueError('Only Character without external cubemap is covered')
    modules = set(case.get('enabled_modules', []))
    supported = {'style_specular', 'spec_attenuation', 'rim', 'skin', 'matcap'}
    if not modules <= supported:
        raise ValueError('Unsupported enabled module: ' + repr(modules-supported))
    allowed_sets = [set(), {'style_specular', 'spec_attenuation'}, {'rim'}, {'skin'}, {'matcap', 'spec_attenuation'}]
    if modules not in allowed_sets:
        raise ValueError('This probe accepts one isolated primary module per additional case')
    expected_kw = {'_SHADOW_OBJECT_SPACE_NORMAL_MAP'} if s['face_shadow_enabled'] else set()
    expected_bindings = {'_MainTex', '_MaskTex'}
    if 'skin' in modules:
        expected_bindings.add('_SkinRamp')
    if 'matcap' in modules:
        expected_kw.add('_USE_MATCAP')
        expected_bindings.add('_MatCapTex')
    if set(shader['keywords']) != expected_kw:
        raise ValueError('Unexpected active shader keyword in formula fixture')
    if set(shader['textures']) != expected_bindings or raw.get('normalTexture'):
        raise ValueError('Formula fixture has an unapproved texture/normal binding')
    module_flags = {'skin': 'IF_SKIN', 'rim': 'IF_RIM', 'spec_attenuation': 'IF_SPEC_ATTENUATION'}
    for module, key in module_flags.items():
        value = float(f.get(key, 0))
        if value != (1.0 if module in modules else 0.0):
            raise ValueError('Enabled module/flag mismatch: ' + key)
    if (float(f.get('_SpecularIntensity', 0)) > 0) != ('style_specular' in modules):
        raise ValueError('Enabled module/intensity mismatch: style_specular')
    for key in ('IF_GI_SKIN', 'IF_MAIN_ALPHA_FOR_SHADOWMASK', '_EmissionIntensity', '_EmissionBloomFactor', '_BloomFactor',
                'IF_INVERT_SPECULAR', 'IF_SPECULAR_SHADOW_INTENSITY',
                'IF_USE_MATCAP_ALPHA', '_MapCapShadowStrength', '_MapCapAlphaUseMask'):
        if float(f.get(key, 0)) != 0:
            raise ValueError(f'Unisolated fixture term: {key}')
    if modules and s['face_shadow_enabled']:
        raise ValueError('Do not combine additional module cases with FaceShadow')
    if s.get('front_facing', True) is not True or s.get('skin_vertex_gate', 1) != 1 or s.get('rim_vertex_gate', 1) != 1:
        raise ValueError('This probe only verifies front faces and unit vertex gates')
    if case.get('required_attributes', []):
        raise ValueError('Vertex attribute fixtures require a separate adapter')
    if raw['extras']['render'].get('blend') is not None or raw['extras']['render'].get('alphaTest', 0):
        raise ValueError('Formula fixture must be opaque with no alpha test')
    for key in ('N_view', 'V_view', 'L_view', 'L_world', 'object_y_world', 'object_z_world'):
        if abs(float(np.dot(s[key], s[key])) - 1) > 1e-10:
            raise ValueError(f'Fixture {key} is not unit length')
    for key, value in case['parameters'].items():
        if f[key] != value:
            raise ValueError(f'Raw shader/fixture parameter mismatch: {key}')
    if s['shadowMapLit'] != 1:
        raise ValueError('Current graph supports the explicitly lit shadow-map diagnostic only')
    if float(f.get('_AlbedoColorIntensity', 1)) != 1 or shader['colors']['_AlbedoColor'] != [1, 1, 1, 1]:
        raise ValueError('This fixture family requires untinted, intensity-one Main')
    if s['main_linear_rgba'][3] != 1:
        raise ValueError('This fixture family requires Main alpha 1')
    # Texture payloads and declared CPU source values must describe the same input.
    for texture in case['texture_fixtures']:
        if texture['storage'] != 'FLOAT32_RGBA' or texture['extras'].get('colorSpace') != 'linear':
            raise ValueError('Fixture requires float32 linear/data image input')
        arr = np.asarray(texture['pixels_top_to_bottom'], dtype=np.float64)
        if arr.size != texture['width']*texture['height']*4 or not np.isfinite(arr).all():
            raise ValueError('Invalid fixture texture payload')
    for binding in shader['textures'].values():
        if binding.get('texCoord', 0) != 0 or binding.get('scale', [1, 1]) != [1, 1] or binding.get('offset', [0, 0]) != [0, 0]:
            raise ValueError('Fixture does not cover arbitrary UV/ST transforms')
    def equal(a, b, label):
        if np.max(np.abs(np.asarray(a, dtype=np.float64)-np.asarray(b, dtype=np.float64))) > 2e-6:
            raise ValueError('Inconsistent fixture input: ' + label)
    equal(fixture_texture(case, '_MainTex', s['uv']), s['main_linear_rgba'], 'Main texture')
    equal(fixture_texture(case, '_MaskTex', s['uv']), s['mask_original_sample_rgba'], 'original Mask texture')
    if s['face_shadow_enabled']:
        equal(fixture_texture(case, '_MaskTex', (1-s['uv'][0], s['uv'][1])), s['mask_mirrored_sample_rgba'], 'mirrored Mask texture')
    for raw_key, input_key in [('_NoShadowColor', 'NoShadow_linear_rgb'), ('_FirstShadowColor', 'FirstShadow_linear_rgb'),
                               ('_SecondShadowColor', 'SecondShadow_linear_rgb'), ('_GlobalTint', 'GlobalTint_linear_rgb')]:
        equal(source_linear_color(shader['colors'][raw_key]), s[input_key], raw_key)
    for module, raw_key, input_key in [('style_specular', '_SpecularColor', 'specular_color_linear_rgb'),
                                      ('rim', '_RimColor', 'rim_color_linear_rgb'), ('skin', '_SkinColor', 'skin_color_linear_rgb')]:
        if module in modules:
            equal(source_linear_color(shader['colors'][raw_key]), s[input_key], raw_key)
    adapter = case['blender_adapter']
    runtime = adapter['runtime']
    def transform(v):
        return [v[0], -v[2], v[1]]
    equal(adapter['normal_world'], transform(s['N_view']), 'pinned normal basis')
    equal(adapter['view_direction_world'], transform(s['V_view']), 'pinned view basis')
    equal(runtime['light_direction'], transform(s['L_view']), 'light basis')
    equal(runtime['light_color'], s['LightColor_linear_rgb'], 'light color')
    equal(runtime['ambient'], s['Ambient_linear_rgb'], 'ambient')
    equal(runtime.get('shadow_intensity', 1), s['shadowIntensity'], 'shadow intensity')
    if s['face_shadow_enabled']:
        equal(runtime['face_object_y'], transform(s['object_y_world']), 'Face Y basis')
        equal(runtime['face_object_z'], transform(s['object_z_world']), 'Face Z basis')
    if 'spec_attenuation' in modules and float(f['_SpecAttenuationSmoothness']) <= 0:
        raise ValueError('Spec attenuation divisor must be positive')
    if 'style_specular' in modules and float(f['_SpecularSmoothFactor']) <= 0:
        raise ValueError('Style specular divisor must be positive')
    if 'rim' in modules:
        equal(runtime['rim_direction'], transform(s['rim_direction_view']), 'rim direction basis')
        if abs(float(np.dot(s['rim_direction_view'], s['rim_direction_view']))-1) > 1e-10:
            raise ValueError('Rim direction must be unit length')
    if 'skin' in modules:
        h = .5*float(np.dot(s['N_view'], s['L_view']))+.5
        equal(fixture_texture(case, '_SkinRamp', (h, .5))[:3], s['skin_ramp_selected_linear_rgb'], 'Skin ramp sample')
    if 'matcap' in modules:
        index = shader['textures']['_MatCapTex']['index']
        desc = next(t for t in case['texture_fixtures'] if t['index'] == index)
        if (desc['width'], desc['height']) != (1, 1):
            raise ValueError('Matcap UV adapter not under test: require a 1x1 constant')
        equal(fixture_texture(case, '_MatCapTex', (.5, .5)), s['matcap_selected_linear_rgba'], 'Matcap constant')


def read_exr(bpy, path):
    im = bpy.data.images.load(str(path), check_existing=False)
    try:
        im.colorspace_settings.name = 'Non-Color'
        im.alpha_mode = 'CHANNEL_PACKED'
        if hasattr(im, 'use_half_precision'):
            im.use_half_precision = False
        width, height = list(im.size)
        channels = int(im.channels)
        if not im.is_float or channels != 4 or width < 1 or height < 1:
            raise ValueError(f'Expected float RGBA EXR: {path}; {width}x{height}x{channels}')
        pixels = np.empty(len(im.pixels), dtype=np.float32)
        im.pixels.foreach_get(pixels)
        pixels = pixels.reshape(height, width, channels)
        if not np.all(np.isfinite(pixels)):
            raise ValueError('Non-finite EXR pixel: ' + str(path))
        return pixels.copy(), {'path': str(path), 'width': width, 'height': height,
                               'channels': channels, 'is_float': bool(im.is_float)}
    finally:
        bpy.data.images.remove(im)


def make_textures(bpy, scene, case, folder, input_tolerance):
    folder.mkdir()
    max_index = max(t['index'] for t in case['texture_fixtures'])
    paths = [None] * (max_index + 1)
    definitions = [None] * (max_index + 1)
    audit = []
    for desc in case['texture_fixtures']:
        width, height = desc['width'], desc['height']
        expected = np.asarray(desc['pixels_top_to_bottom'], dtype=np.float32).reshape(height, width, 4)[::-1].copy()
        im = bpy.data.images.new(case['id'] + '_' + desc['name'], width=width, height=height,
                                 alpha=True, float_buffer=True)
        im.colorspace_settings.name = 'Non-Color'
        im.alpha_mode = 'CHANNEL_PACKED'
        half_property = hasattr(im, 'use_half_precision')
        if half_property:
            im.use_half_precision = False
        im.pixels.foreach_set(expected.ravel())
        im.update()
        path = folder / f"texture_{desc['index']:02d}.exr"
        im.file_format = 'OPEN_EXR'
        im.filepath_raw = str(path)
        # save_render honors the scene's OPEN_EXR / 32 / RGBA settings. Reload
        # comparison below refuses premultiplied, transformed or half-rounded data.
        im.save_render(str(path), scene=scene)
        bpy.data.images.remove(im)
        actual, meta = read_exr(bpy, path)
        error = float(np.max(np.abs(actual - expected)))
        if error > input_tolerance:
            raise ValueError(f'Input texture roundtrip changed {desc["name"]}: max error={error}')
        meta.update(index=desc['index'], name=desc['name'], expected_rgba=expected.tolist(),
                    reloaded_rgba=actual.tolist(), max_abs_error=error,
                    gpu_half_precision_property_available=half_property)
        audit.append(meta)
        paths[desc['index']] = path
        definitions[desc['index']] = {'name': desc['name'], 'extras': desc['extras']}
    return paths, definitions, audit


def linked_output(socket):
    if len(socket.links) != 1:
        raise ValueError('Expected exactly one graph input link: ' + socket.name)
    return socket.links[0].from_socket


def add_aov(nt, name, source, scalar=False):
    node = nt.nodes.new('ShaderNodeOutputAOV')
    node.name = name
    node.aov_name = name
    nt.links.new(source, node.inputs['Value' if scalar else 'Color'])


def extra_diagnostics(mat, case):
    """Tap existing graph links, without recreating its shadow calculations."""
    nt = mat.node_tree
    band = linked_output(nt.nodes['ShadowBand'].inputs['Color']).node
    if band.bl_idname != 'ShaderNodeMixRGB':
        raise ValueError('Builder changed Cel band topology; adapt this explicit probe tap')
    first_mix = linked_output(band.inputs[1]).node
    second_mix = linked_output(band.inputs[2]).node
    if any(n.bl_idname != 'ShaderNodeMixRGB' for n in (first_mix, second_mix)):
        raise ValueError('Builder changed nested Cel band topology')
    add_aov(nt, 'ProbeFirstWeight', linked_output(first_mix.inputs[0]), True)
    add_aov(nt, 'ProbeSecondWeight', linked_output(second_mix.inputs[0]), True)
    add_aov(nt, 'ProbeSecondAllowed', linked_output(band.inputs[0]), True)
    final = nt.nodes['Formula output']
    strength = final.inputs['Strength']
    if strength.is_linked or abs(float(strength.default_value)-1.0) > 1e-7:
        raise ValueError('Builder Formula output must already have unlinked Emission Strength=1')
    add_aov(nt, 'ProbeFinalLinear', linked_output(final.inputs['Color']))
    masks = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeTexImage' and n.label == '_MaskTex']
    original = nt.nodes.get('_MaskTex')
    if original is None or len(masks) != (2 if case['source_inputs']['face_shadow_enabled'] else 1):
        raise ValueError('Builder changed Mask texture node identity/count')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(original.outputs['Color'], sep.inputs[0])
    add_aov(nt, 'ProbeOriginalMaskG', sep.outputs['Y'], True)
    passes = {'ProbeFirstWeight': 'VALUE', 'ProbeSecondWeight': 'VALUE',
              'ProbeSecondAllowed': 'VALUE', 'ProbeFinalLinear': 'COLOR',
              'ProbeOriginalMaskG': 'VALUE'}
    if case['source_inputs']['face_shadow_enabled']:
        face = next(n for n in masks if n != original)
        face_sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(face.outputs['Color'], face_sep.inputs[0])
        add_aov(nt, 'ProbeFaceB', face_sep.outputs['Z'], True)
        add_aov(nt, 'ProbeFaceA', face.outputs['Alpha'], True)
        passes.update(ProbeFaceB='VALUE', ProbeFaceA='VALUE')
    return passes


def pin_vectors(mat, case):
    """Fixture injection into real graph consumers, not production graph edits."""
    nt = mat.node_tree
    geo = nt.nodes['Surface geometry']
    audit = {}
    for output, fixture_key in [('Normal', 'normal_world'), ('Incoming', 'view_direction_world')]:
        value = case['blender_adapter'][fixture_key]
        if abs(float(np.dot(value, value)) - 1) > 1e-10:
            raise ValueError('Pinned graph vector is not unit: ' + output)
        links = list(geo.outputs[output].links)
        node = nt.nodes.new('ShaderNodeCombineXYZ')
        node.name = 'FIXTURE_' + output
        node.label = 'Fixed CPU fixture ' + output
        for i, v in enumerate(value):
            node.inputs[i].default_value = v
        for link in links:
            target = link.to_socket
            nt.links.remove(link)
            nt.links.new(node.outputs[0], target)
        audit[output] = {'value': value, 'replaced_consumer_links': len(links)}
        if not links:
            raise ValueError('Builder exposes no consumers for Geometry.' + output)
    return audit


def create_scene(bpy, case, size, samples):
    from mathutils import Vector
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'OPEN_EXR'
    scene.render.image_settings.color_depth = '32'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.exr_codec = 'ZIP'
    scene.render.dither_intensity = 0
    scene.render.use_compositing = True
    scene.render.use_sequencer = False
    scene.render.use_motion_blur = False
    scene.eevee.taa_render_samples = samples
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.view_settings.use_curve_mapping = False
    scene.frame_set(1)
    world = bpy.data.worlds.new('Formula black world')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0, 0, 0, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0
    scene.world = world
    # One counter-clockwise face, +Z normal, much larger than the camera footprint.
    mesh = bpy.data.meshes.new('Formula XY plane')
    mesh.from_pydata([(-2, -2, 0), (2, -2, 0), (2, 2, 0), (-2, 2, 0)], [], [(0, 1, 2, 3)])
    mesh.update()
    uv = mesh.uv_layers.new(name='UVMap')
    for loop in uv.data:
        loop.uv = case['source_inputs']['uv']
    obj = bpy.data.objects.new('Formula plane', mesh)
    scene.collection.objects.link(obj)
    cd = bpy.data.cameras.new('Formula orthographic camera')
    cam = bpy.data.objects.new(cd.name, cd)
    scene.collection.objects.link(cam)
    cam.location = (0, 0, 3)
    cam.rotation_euler = (Vector((0, 0, 0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cd.type = 'ORTHO'
    cd.ortho_scale = 2
    cd.clip_start = .1
    cd.clip_end = 10
    cd.dof.use_dof = False
    scene.camera = cam
    return scene, obj


def configure_outputs(bpy, scene, folder, extra):
    passes = {'HalfLambert': 'VALUE', 'ShadowBand': 'COLOR', 'BaseAlbedo': 'COLOR',
              'SourceNormal': 'COLOR', 'HX_BloomWeight': 'VALUE', 'SkinRate': 'VALUE',
              'StyleSpecular': 'COLOR', 'RimTerm': 'COLOR', 'MatcapTerm': 'COLOR', **extra}
    layer = scene.view_layers[0]
    layer.name = 'FormulaProbe'
    for name, kind in passes.items():
        av = layer.aovs.add()
        av.name = name
        av.type = kind
    bpy.context.view_layer.update()
    scene.use_nodes = True
    nt = scene.node_tree
    nt.nodes.clear()
    rl = nt.nodes.new('CompositorNodeRLayers')
    rl.layer = layer.name
    co = nt.nodes.new('CompositorNodeComposite')
    nt.links.new(rl.outputs['Image'], co.inputs['Image'])
    out = nt.nodes.new('CompositorNodeOutputFile')
    out.name = 'Linear unprocessed formula passes'
    out.base_path = str(folder)
    out.format.file_format = 'OPEN_EXR'
    out.format.color_depth = '32'
    out.format.color_mode = 'RGBA'
    out.format.exr_codec = 'ZIP'
    out.file_slots.clear()
    names = ['Image', *passes]
    for name in names:
        if name not in rl.outputs:
            raise ValueError('Blender Render Layers missing requested AOV: ' + name)
        out.file_slots.new(name)
        slot = out.file_slots[-1]
        slot.path = name + '_'
        slot.use_node_format = True
        nt.links.new(rl.outputs[name], out.inputs[name])
    return names


def compare_pixels(arr, expected, channels, tolerance):
    height, width = arr.shape[:2]
    x, y = width // 2, height // 2
    center = arr[y, x, channels]
    roi = arr[y-2:y+2, x-2:x+2, :][..., channels]
    expected = np.asarray(expected, dtype=np.float64)
    center_error = float(np.max(np.abs(center - expected)))
    roi_error = float(np.max(np.abs(roi - expected)))
    return {'expected_cpu_float64': expected.tolist(),
            'center_xy_bottom_up': [x, y], 'center_value': np.asarray(center).tolist(),
            'roi_xywh_bottom_up': [x-2, y-2, 4, 4],
            'roi_mean': np.mean(roi, axis=(0, 1)).tolist(),
            'roi_min': np.min(roi, axis=(0, 1)).tolist(),
            'roi_max': np.max(roi, axis=(0, 1)).tolist(),
            'max_abs_center_error': center_error, 'max_abs_roi_error': roi_error,
            'absolute_tolerance': tolerance, 'pass': roi_error <= tolerance,
            'within_strict_float32_tolerance_2e_minus4': roi_error <= 2e-4}


def run_case(bpy, module, case, directory, args):
    directory.mkdir()
    assert_isolated_fixture(case)
    expected = cpu_reference(case)
    check_reference(case, expected)
    report = {'id': case['id'], 'primary': not case.get('supplemental', False),
              'status': 'preparing', 'cpu_reference': expected,
              'supplied_expected_float32': case.get('expected_float32'),
              'supplied_expected_half_storage': case.get('expected_half_storage_from_float32')}
    write_json(directory / 'report.json', report)
    scene, plane = create_scene(bpy, case, args.size, args.samples)
    paths, defs, tex_audit = make_textures(bpy, scene, case, directory / 'textures', args.input_atol)
    runtime = copy.deepcopy(case['blender_adapter']['runtime'])
    mat, material_audit = module.build_character(copy.deepcopy(case['raw_material']), paths, defs,
                                                runtime, attributes=())
    if material_audit.get('gaps'):
        raise ValueError('Unexpected material gap in isolated formula fixture: ' + repr(material_audit['gaps']))
    # Explicitly disable half precision on builder-loaded image datablocks too.
    precision = []
    for node in mat.node_tree.nodes:
        if node.bl_idname == 'ShaderNodeTexImage':
            image = node.image
            available = hasattr(image, 'use_half_precision')
            if available:
                image.use_half_precision = False
            if image.colorspace_settings.name != 'Non-Color' or image.alpha_mode != 'CHANNEL_PACKED':
                raise ValueError('Builder changed fixture colorspace/alpha interpretation')
            precision.append({'node': node.name, 'image': image.filepath,
                              'use_half_precision_property': available,
                              'use_half_precision': bool(image.use_half_precision) if available else None})
    vector_audit = pin_vectors(mat, case)
    extra = extra_diagnostics(mat, case)
    plane.data.materials.append(mat)
    passes = configure_outputs(bpy, scene, directory, extra)
    report.update(status='prepared', runtime=runtime, material=material_audit,
                  texture_roundtrip=tex_audit, texture_gpu_precision=precision,
                  pinned_vectors=vector_audit, passes=passes,
                  scope='Formula graph with exact pinned N/V; geometry adapter is excluded',
                  blender=bpy.app.version_string, engine=scene.render.engine,
                  resolution=[args.size, args.size], samples=args.samples)
    write_json(directory / 'report.json', report)
    if args.save_blends:
        bpy.ops.wm.save_as_mainfile(filepath=str(directory / 'formula-probe.blend'))
    started = time.monotonic()
    bpy.ops.render.render(write_still=False)
    report.update(status='rendered', render_seconds=time.monotonic()-started)
    write_json(directory / 'report.json', report)
    arrays = {}
    file_audit = {}
    for name in passes:
        path = directory / (name + '_0001.exr')
        if not path.is_file():
            raise FileNotFoundError('Compositor did not emit required linear pass: ' + str(path))
        arrays[name], file_audit[name] = read_exr(bpy, path)
        if arrays[name].shape != (args.size, args.size, 4):
            raise ValueError('Unexpected output dimensions: ' + name)
    comparisons = {}
    for name, target in expected_aovs(case, expected).items():
        if name == 'ImageAlpha':
            source_name, channels = 'Image', 3
        else:
            source_name = name
            channels = slice(0, 3) if np.asarray(target).ndim else 0
        if source_name not in arrays:
            raise ValueError('Missing numeric acceptance pass: ' + source_name)
        comparisons[name] = compare_pixels(arrays[source_name], target, channels, args.atol)
    success = all(c['pass'] for c in comparisons.values())
    report.update(status='passed' if success else 'failed_comparison', pass_all=success,
                  comparisons=comparisons, output_files=file_audit,
                  checks='CPU formulas + center pixel + complete 4x4 center ROI; no visual appearance acceptance')
    write_json(directory / 'report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--builder', required=True, type=Path)
    parser.add_argument('--cases', required=True, type=Path, action='append',
                        help='Fixture JSON; repeat this option to run old and additional cases together')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--size', type=int, default=32)
    parser.add_argument('--samples', type=int, default=8)
    parser.add_argument('--atol', type=float, default=1e-3,
                        help='Raw output tolerance allowing internal half-float storage; strict 2e-4 is also reported')
    parser.add_argument('--input-atol', type=float, default=2e-6)
    parser.add_argument('--skip-second-gate-on', action='store_true')
    parser.add_argument('--save-blends', action='store_true')
    parser.add_argument('--cpu-only', action='store_true',
                        help='Verify source-algebra references only; do not import Blender or the builder')
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    args = parser.parse_args(argv)
    if args.size < 8 or args.samples < 1 or args.atol <= 0 or args.input_atol <= 0:
        raise ValueError('Require size >=8, samples >=1 and positive tolerances')
    args.builder = args.builder.resolve(strict=True)
    args.cases = [path.resolve(strict=True) for path in args.cases]
    if len(set(args.cases)) != len(args.cases):
        raise ValueError('Do not provide the same fixture document twice')
    args.output = args.output.resolve()
    documents = [json.loads(path.read_text(encoding='utf-8')) for path in args.cases]
    cases = []
    for document in documents:
        if document.get('schema_version') not in (1, 2):
            raise ValueError('Unsupported fixture schema version')
        if document['primary_case_count'] != len(document['cases']):
            raise ValueError('Fixture primary_case_count does not match its cases')
        cases.extend(selected_cases(document, not args.skip_second_gate_on))
    if len({case['id'] for case in cases}) != len(cases):
        raise ValueError('Duplicate case id across input documents')
    references = []
    for case in cases:
        assert_isolated_fixture(case)
        expected = cpu_reference(case)
        check_reference(case, expected)
        references.append({'id': case['id'], 'enabled_modules': case.get('enabled_modules', []),
                           'cpu_reference': expected, 'expected_aovs': expected_aovs(case, expected)})
    fixture_identity = [{'path': str(path), 'sha256': digest(path)} for path in args.cases]
    if args.cpu_only:
        if args.output.exists() and any(args.output.iterdir()):
            raise FileExistsError('CPU report output must be new/empty: ' + str(args.output))
        args.output.mkdir(parents=True, exist_ok=True)
        report = {'status': 'cpu_reference_passed', 'blender_executed': False,
                  'production_builder_imported': False, 'script_sha256': digest(__file__),
                  'builder_identity_only': {'path': str(args.builder), 'sha256': digest(args.builder)},
                  'fixture_documents': fixture_identity, 'case_count': len(cases),
                  'scope': 'Independent source-algebra consistency only; not Blender or GPU acceptance',
                  'cases': references}
        write_json(args.output / 'cpu-report.json', report)
        print('FORMULA_CPU_REFERENCE_ONLY', len(cases), str(args.output / 'cpu-report.json'), flush=True)
        return
    import bpy
    # No reset of an interactive or loaded user scene is permitted by this draft.
    if not bpy.app.background or bpy.data.filepath:
        raise RuntimeError('Use a fresh background --factory-startup process with no .blend argument')
    if bpy.app.version[:2] != (4, 5):
        raise RuntimeError('This draft targets Blender 4.5; explicit compatibility review required')
    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError('Output must be a new/empty version directory: ' + str(args.output))
    args.output.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location('formula_probe_character_material', args.builder)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    audit = {'status': 'running', 'script': str(Path(__file__).resolve()),
             'script_sha256': digest(__file__), 'builder': str(args.builder),
             'builder_sha256': digest(args.builder), 'fixture_documents': fixture_identity,
             'blender': bpy.app.version_string, 'blender_executed': True,
             'started_unix': time.time(), 'primary_cases': sum(d['primary_case_count'] for d in documents),
             'supplemental_gate_on': any(c.get('supplemental', False) for c in cases),
             'output_tolerance': args.atol, 'input_roundtrip_tolerance': args.input_atol,
             'scene_replacement_scope': 'Only fresh isolated background process',
             'limitations': ['No website GPU comparison', 'No actual character appearance test',
                             'Pinned Normal/Incoming exclude geometry adapter verification',
                             '32-bit file output does not guarantee 32-bit internal Eevee AOV storage'],
             'cases': []}
    write_json(args.output / 'report.json', audit)
    for case_index, case in enumerate(cases):
        infrastructure_error = False
        try:
            result = run_case(bpy, module, case, args.output / case['id'], args)
        except Exception as exc:
            infrastructure_error = True
            folder = args.output / case['id']
            folder.mkdir(exist_ok=True)
            result = {'id': case['id'], 'primary': not case.get('supplemental', False),
                      'status': 'error', 'pass_all': False, 'error': repr(exc),
                      'traceback': traceback.format_exc()}
            write_json(folder / 'error.json', result)
        audit['cases'].append(result)
        write_json(args.output / 'report.json', audit)
        print('FORMULA_CASE', case['id'], result['status'], flush=True)
        # Do not repeat a broken Blender/API/texture setup for every fixture.
        # Numerical comparison failures still allow independent later cases.
        if infrastructure_error:
            audit['not_run_after_infrastructure_error'] = [c['id'] for c in cases[case_index+1:]]
            break
    success = len(audit['cases']) == len(cases) and all(c.get('pass_all', False) for c in audit['cases'])
    audit.update(status='passed' if success else 'failed', pass_all=success,
                 finished_unix=time.time())
    write_json(args.output / 'report.json', audit)
    print('FORMULA_PROBE_REPORT', str(args.output / 'report.json'), audit['status'], flush=True)
    if not success:
        raise RuntimeError('Formula probe did not pass all checks; see report.json')


if __name__ == '__main__':
    main()
