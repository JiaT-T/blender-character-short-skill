"""Read-only identity/preflight for opt-in, self-contained static scene GLBs."""
import hashlib
import json
import math
import struct
from pathlib import Path


def _vector(value, label):
    if not isinstance(value, list) or len(value) != 3 or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in value
    ):
        raise ValueError(label + ' requires three finite numbers')
    return list(value)


def inspect_static_glb(path):
    raw = Path(path).read_bytes()
    if len(raw) < 20 or struct.unpack_from('<4sII', raw) != (b'glTF', 2, len(raw)):
        raise ValueError('Scene asset must be a complete GLB v2')
    offset = 12
    chunks = []
    while offset < len(raw):
        if offset + 8 > len(raw):
            raise ValueError('Truncated GLB chunk')
        size, kind = struct.unpack_from('<II', raw, offset)
        offset += 8
        if size % 4 or offset + size > len(raw):
            raise ValueError('Invalid GLB chunk length')
        chunks.append((kind, raw[offset:offset + size]))
        offset += size
    if len(chunks) != 2 or [x[0] for x in chunks] != [0x4e4f534a, 0x004e4942]:
        raise ValueError('Scene GLB requires one JSON and one embedded BIN chunk')
    data = json.loads(chunks[0][1].decode('utf-8'))
    if data.get('asset', {}).get('version') != '2.0':
        raise ValueError('Unsupported glTF asset version')
    if any(data.get(k) for k in ('animations', 'skins', 'cameras', 'images', 'textures', 'extensionsRequired')):
        raise ValueError('Static scene GLB excludes animation, rigs, cameras, textures and required extensions')
    if data.get('extensions', {}).get('KHR_lights_punctual'):
        raise ValueError('Scene asset must not import lights')
    buffers = data.get('buffers', [])
    if len(buffers) != 1 or 'uri' in buffers[0] or not 0 < buffers[0].get('byteLength', 0) <= len(chunks[1][1]):
        raise ValueError('Scene GLB must use one local embedded buffer')
    if not data.get('meshes') or not data.get('nodes'):
        raise ValueError('Scene asset requires static mesh nodes')
    for node in data['nodes']:
        if any(k in node for k in ('skin', 'camera', 'weights')) or node.get('extensions'):
            raise ValueError('Unsupported scene node rig/camera/extension')
    material_names = [m.get('name') for m in data.get('materials', [])]
    if not material_names or any(not isinstance(n, str) or not n for n in material_names) or len(set(material_names)) != len(material_names):
        raise ValueError('Scene GLB materials require distinct nonempty names')
    for mesh in data['meshes']:
        if mesh.get('weights'):
            raise ValueError('Scene asset morph animation is unsupported')
        for primitive in mesh.get('primitives', []):
            if primitive.get('targets') or primitive.get('extensions') or primitive.get('mode', 4) != 4:
                raise ValueError('Scene asset supports static triangle meshes only')
            if 'material' not in primitive or not 0 <= primitive['material'] < len(material_names):
                raise ValueError('Every scene primitive needs a named palette material')
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'materials': material_names}


def collect_scene_asset_inputs(story_path):
    story_path = Path(story_path).resolve(strict=True)
    story = json.loads(story_path.read_text('utf-8'))
    entries = story.get('set', {}).get('imports', [])
    if not isinstance(entries, list):
        raise ValueError('set.imports must be a list')
    palette = story.get('set', {}).get('materials', {})
    result = []
    names = set()
    for entry in entries:
        required = {'name', 'file', 'sha256', 'height', 'position', 'materials', 'purpose', 'source', 'license'}
        if not isinstance(entry, dict) or not required <= set(entry) or set(entry) - required - {'rotation'}:
            raise ValueError('Scene import fields are incomplete or unsupported')
        for key in ('name', 'file', 'purpose', 'source', 'license'):
            if not isinstance(entry[key], str) or not entry[key].strip():
                raise ValueError('Scene import requires nonempty ' + key)
        if entry['name'] in names:
            raise ValueError('Duplicate scene import name')
        if len(entry['name'].encode('utf-8')) > 32:
            raise ValueError('Scene asset name must fit 32 UTF-8 bytes for its Blender namespace')
        names.add(entry['name'])
        height = entry['height']
        if isinstance(height, bool) or not isinstance(height, (int, float)) or not math.isfinite(height) or height <= 0:
            raise ValueError('Scene import height must be finite and positive')
        position = _vector(entry['position'], 'Scene position')
        rotation = _vector(entry.get('rotation', [0, 0, 0]), 'Scene rotation')
        path = (story_path.parent / entry['file']).resolve(strict=True)
        if path.suffix.lower() != '.glb':
            raise ValueError('Only self-contained GLB scene files are supported')
        inspected = inspect_static_glb(path)
        if entry['sha256'] != inspected['sha256']:
            raise ValueError('Scene asset hash differs from reviewed story input')
        mapping = entry['materials']
        if not isinstance(mapping, dict) or set(mapping) != set(inspected['materials']) or any(
            not isinstance(v, str) or v not in palette for v in mapping.values()
        ):
            raise ValueError('Map every imported material to an existing story palette key')
        result.append({**entry, 'rotation': rotation, 'position': position, 'path': str(path),
                       'bytes': inspected['bytes']})
    return result
