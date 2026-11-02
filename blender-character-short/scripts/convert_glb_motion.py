"""Convert permitted local GLB2 LINEAR node TRS into external packed-v1 data.

No Blender, network, source mesh/texture export or rig retargeting is performed.
The existing packed decoder remains the consumer and is validated numerically.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

import numpy as np

from source_motion import decode_clip, node_worlds, sample_track

PATHS = {'translation': ('position', 3), 'rotation': ('quaternion', 4), 'scale': ('scale', 3)}
TRS_FIELDS = {'name', 'children', 'translation', 'rotation', 'scale', 'matrix'}
LIMITS = {
    'source_bytes': 64 * 1024 * 1024,
    'json_bytes': 8 * 1024 * 1024,
    'binary_bytes': 56 * 1024 * 1024,
    'provenance_bytes': 256 * 1024,
    'nodes': 2048,
    'hierarchy_depth': 128,
    'channels': 1024,
    'accessor_samples': 100000,
    'decoded_components': 1000000,
    'timeline_samples': 100000,
    'resampled_channel_samples': 250000,
    'resampled_components': 1000000,
    'validation_graph_samples': 250000,
}


def budget(name, value):
    if value > LIMITS[name]:
        raise ValueError(name + ' budget exceeded: ' + str(value) + ' > ' + str(LIMITS[name]))


def read_bounded(path, name):
    path = Path(path)
    budget(name, path.stat().st_size)
    with path.open('rb') as stream:
        raw = stream.read(LIMITS[name] + 1)
    budget(name, len(raw))
    return raw


def finite_worlds(skeleton, tracks=(), time=0):
    try:
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            worlds = node_worlds(skeleton, tracks, time)
    except (FloatingPointError, OverflowError, RecursionError) as exc:
        raise ValueError('World hierarchy evaluation failed its finite/depth bounds at source time ' + str(float(time))) from exc
    if not np.isfinite(worlds).all():
        raise ValueError('Nonfinite world hierarchy matrix at source time ' + str(float(time)))
    return worlds


def read_json(raw, label):
    """Do not silently choose one of contradictory data/rights declarations."""
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(label + ' contains a duplicate JSON key: ' + key)
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError(label + ' contains a non-JSON numeric constant: ' + value)
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except RecursionError as exc:
        raise ValueError(label + ' nesting exceeds the supported parser depth') from exc


def integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(label + ' must be an integer >= ' + str(minimum))
    return value


def item(sequence, index, label):
    integer(index, label)
    if not isinstance(sequence, list) or index >= len(sequence):
        raise ValueError(label + ' is outside its array')
    value = sequence[index]
    if not isinstance(value, dict):
        raise ValueError(label + ' must identify an object')
    return value


def finite_vector(value, count, label):
    if not isinstance(value, list) or len(value) != count or any(
        isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in value
    ):
        raise ValueError(label + ' requires ' + str(count) + ' finite numbers')
    return np.asarray(value, dtype=np.float64)


def unit_quaternions(values, label):
    norms = np.linalg.norm(values.astype(np.float64), axis=-1)
    if not np.isfinite(norms).all() or np.any(np.abs(norms - 1) > 1e-4):
        raise ValueError(label + ' requires unit quaternions')
    return values / norms[..., None]


def read_glb(raw):
    budget('source_bytes', len(raw))
    if len(raw) < 20 or struct.unpack_from('<4sII', raw) != (b'glTF', 2, len(raw)):
        raise ValueError('Expected one complete GLB2 file')
    offset = 12
    chunks = []
    for expected_kind, budget_name in [(0x4e4f534a, 'json_bytes'), (0x004e4942, 'binary_bytes')]:
        if offset + 8 > len(raw):
            raise ValueError('Truncated GLB chunk header')
        size, kind = struct.unpack_from('<II', raw, offset)
        offset += 8
        if size % 4 or offset + size > len(raw):
            raise ValueError('Invalid GLB chunk length/alignment')
        if kind != expected_kind:
            raise ValueError('Expected JSON followed by embedded BIN')
        budget(budget_name, size)
        chunks.append((kind, raw[offset:offset + size]))
        offset += size
    if offset != len(raw):
        raise ValueError('Expected exactly one JSON chunk followed by one embedded BIN chunk')
    document = read_json(chunks[0][1], 'GLB JSON')
    if not isinstance(document, dict) or not isinstance(document.get('asset'), dict) or document['asset'].get('version') != '2.0':
        raise ValueError('Unsupported glTF asset version')
    if document.get('extensionsRequired'):
        raise ValueError('Required glTF extensions are unsupported')
    buffers = document.get('buffers', [])
    if not isinstance(buffers, list) or len(buffers) != 1 or not isinstance(buffers[0], dict) or 'uri' in buffers[0]:
        raise ValueError('Only one embedded buffer is supported; external/data URIs are not read')
    size = integer(buffers[0].get('byteLength'), 'Embedded buffer length', 1)
    if not size <= len(chunks[1][1]) <= size + 3:
        raise ValueError('BIN size differs from declared buffer size/padding')
    return document, chunks[1][1][:size]


def read_accessor(document, binary, index, expected_type):
    accessor = item(document.get('accessors'), index, 'Accessor index')
    if accessor.get('componentType') != 5126 or accessor.get('type') != expected_type:
        raise ValueError('Animation accessor must use float32 ' + expected_type)
    if accessor.get('normalized') or 'sparse' in accessor or accessor.get('extensions'):
        raise ValueError('Normalized, sparse or extended animation accessors are unsupported')
    view = item(document.get('bufferViews'), accessor.get('bufferView'), 'Animation bufferView')
    if view.get('buffer') != 0 or isinstance(view.get('buffer'), bool):
        raise ValueError('Animation accessor must use embedded buffer0')
    if 'byteStride' in view or 'target' in view or view.get('extensions'):
        raise ValueError('Animation bufferView must be tightly packed and have no vertex/index target')
    width = {'SCALAR': 1, 'VEC3': 3, 'VEC4': 4}[expected_type]
    count = integer(accessor.get('count'), 'Accessor count', 1)
    budget('accessor_samples', count)
    view_start = integer(view.get('byteOffset', 0), 'bufferView byteOffset')
    view_size = integer(view.get('byteLength'), 'bufferView byteLength', 1)
    relative = integer(accessor.get('byteOffset', 0), 'Accessor byteOffset')
    start = view_start + relative
    end = start + count * width * 4
    if start % 4 or relative % 4 or end > view_start + view_size or view_start + view_size > len(binary):
        raise ValueError('Animation accessor is misaligned or exceeds its bufferView/BIN')
    values = np.frombuffer(binary, dtype='<f4', count=count * width, offset=start).reshape(count, width).copy()
    if not np.isfinite(values).all():
        raise ValueError('Nonfinite animation accessor values')
    return values


def skeleton_only(document):
    source = document.get('nodes')
    if not isinstance(source, list) or not source:
        raise ValueError('A node hierarchy is required')
    budget('nodes', len(source))
    nodes = []
    parents = {}
    for index, node in enumerate(source):
        if not isinstance(node, dict) or node.get('extensions'):
            raise ValueError('Unsupported node object/extension')
        if 'matrix' in node and any(k in node for k in ('translation', 'rotation', 'scale')):
            raise ValueError('Node cannot combine matrix with TRS')
        for key, count in [('translation', 3), ('rotation', 4), ('scale', 3), ('matrix', 16)]:
            if key in node:
                values = finite_vector(node[key], count, 'Node ' + key)
                if key == 'rotation':
                    unit_quaternions(values, 'Rest rotation')
                if key == 'matrix' and not np.allclose(values.reshape(4, 4).T[3], [0, 0, 0, 1], atol=1e-8):
                    raise ValueError('Node matrix must be affine')
        if 'name' in node and not isinstance(node['name'], str):
            raise ValueError('Node name must be a string')
        children = node.get('children', [])
        if not isinstance(children, list):
            raise ValueError('Node children must be a list')
        for child in children:
            integer(child, 'Child node index')
            if child >= len(source) or child == index or child in parents:
                raise ValueError('Hierarchy contains an invalid/duplicate child')
            parents[child] = index
        nodes.append({key: value for key, value in node.items() if key in TRS_FIELDS})
    skeleton = {'nodes': nodes}
    # Validate depth/cycles iteratively BEFORE the existing recursive evaluator.
    pending = [(index, 1) for index in range(len(nodes)) if index not in parents]
    visited = 0
    while pending:
        index, depth = pending.pop()
        budget('hierarchy_depth', depth)
        visited += 1
        pending.extend((child, depth + 1) for child in nodes[index].get('children', []))
    if visited != len(nodes):
        raise ValueError('Skeleton cycle')
    finite_worlds(skeleton)
    return skeleton


def sample_linear(track, time):
    """Reference interpolation from original keys, independent of packed decoding."""
    times, values = track['times'], track['values']
    if time <= times[0] or len(times) == 1:
        return values[0].astype(np.float64)
    if time >= times[-1]:
        return values[-1].astype(np.float64)
    right = int(np.searchsorted(times, time, side='right'))
    left = right - 1
    weight = float((time - times[left]) / (times[right] - times[left]))
    a, b = values[left].astype(np.float64), values[right].astype(np.float64)
    if track['property'] != 'quaternion':
        return a * (1 - weight) + b * weight
    dot = float(np.dot(a, b))
    if dot < 0:
        b, dot = -b, -dot
    angle = math.acos(max(-1.0, min(1.0, dot)))
    if abs(math.sin(angle)) < 1e-10:
        result = a * (1 - weight) + b * weight
    else:
        result = (math.sin((1 - weight) * angle) * a + math.sin(weight * angle) * b) / math.sin(angle)
    return result / np.linalg.norm(result)


def original_tracks(document, binary, skeleton, animation_index):
    animations = document.get('animations')
    if not isinstance(animations, list) or not animations:
        raise ValueError('No animation is present')
    if animation_index is None:
        if len(animations) != 1:
            raise ValueError('Select --animation explicitly when multiple animations are present')
        animation_index = 0
    animation = item(animations, animation_index, 'Animation index')
    if animation.get('extensions'):
        raise ValueError('Animation extensions are unsupported')
    channels = animation.get('channels')
    if not isinstance(channels, list) or not channels:
        raise ValueError('Selected animation has no channels')
    budget('channels', len(channels))
    if 'name' in animation and not isinstance(animation['name'], str):
        raise ValueError('Animation name must be a string')
    tracks, seen, components = [], set(), 0
    for channel in channels:
        if not isinstance(channel, dict) or channel.get('extensions'):
            raise ValueError('Unsupported animation channel')
        target = channel.get('target')
        if not isinstance(target, dict) or target.get('extensions') or target.get('path') not in PATHS:
            raise ValueError('Only ordinary node translation/rotation/scale targets are supported')
        index = integer(target.get('node'), 'Animation target node')
        if index >= len(skeleton['nodes']) or 'matrix' in skeleton['nodes'][index]:
            raise ValueError('Animated target is missing or uses a static matrix requiring decomposition')
        prop, width = PATHS[target['path']]
        identity = (index, prop)
        if identity in seen:
            raise ValueError('Duplicate animation target channel')
        seen.add(identity)
        sampler = item(animation.get('samplers'), channel.get('sampler'), 'Animation sampler')
        if sampler.get('interpolation', 'LINEAR') != 'LINEAR' or sampler.get('extensions'):
            raise ValueError('Only LINEAR animation is supported; STEP/CUBICSPLINE are not approximated')
        input_count = integer(item(document.get('accessors'), sampler.get('input'), 'Input accessor').get('count'), 'Input samples', 1)
        output_count = integer(item(document.get('accessors'), sampler.get('output'), 'Output accessor').get('count'), 'Output samples', 1)
        budget('accessor_samples', input_count)
        budget('accessor_samples', output_count)
        if input_count != output_count:
            raise ValueError('LINEAR input/output sample counts must match')
        components += input_count + width * output_count
        budget('decoded_components', components)
        times = read_accessor(document, binary, sampler.get('input'), 'SCALAR')[:, 0]
        values = read_accessor(document, binary, sampler.get('output'), 'VEC' + str(width))
        if len(values) != len(times) or times[0] < 0 or np.any(np.diff(times) <= 0):
            raise ValueError('Animation needs equal input/output counts and nonnegative increasing times')
        if prop == 'quaternion':
            values = unit_quaternions(values.astype(np.float64), 'Animation rotation')
        tracks.append({'node': index, 'property': prop, 'times': times, 'values': values})
    return tracks, animation_index, animation.get('name')


def encode_values(values):
    integers = np.rint(values).astype(np.float64)
    if not np.isfinite(integers).all() or np.max(np.abs(integers)) > 2 ** 51:
        raise ValueError('Motion values exceed exact packed-delta integer range')
    integers = integers.astype(np.int64)
    return np.diff(np.vstack([np.zeros((1, integers.shape[1]), np.int64), integers]), axis=0).T.reshape(-1).tolist()


def sampling_plan(tracks, node_count):
    times = np.unique(np.concatenate([t['times'] for t in tracks]))
    budget('timeline_samples', len(times))
    work = {
        'shared_timeline_samples': len(times),
        'resampled_channel_samples': len(tracks) * len(times),
        'resampled_components': sum(4 if t['property'] == 'quaternion' else 3 for t in tracks) * len(times),
    }
    budget('resampled_channel_samples', work['resampled_channel_samples'])
    budget('resampled_components', work['resampled_components'])
    # Every original channel key is mandatory, not an expendable sample. Budget
    # this full coverage before packing; never downsample keys to fit the budget.
    probes = np.unique(np.concatenate([times, np.linspace(0, times[-1], 97)]))
    work['original_world_key_samples'] = len(times)
    work['additional_world_samples'] = len(probes) - len(times)
    work['validation_graph_samples'] = (node_count + len(tracks)) * len(probes)
    budget('validation_graph_samples', work['validation_graph_samples'])
    return times, probes, work


def pack_tracks(tracks, times):
    result = []
    factor = math.sqrt(.5) / (2 ** 23 - 1)
    for source in tracks:
        values = np.asarray([sample_linear(source, float(t)) for t in times])
        track = {'node': source['node'], 'property': source['property']}
        if source['property'] == 'quaternion':
            packed, schedule, previous = [], [], None
            for frame, value in enumerate(values):
                component = int(np.argmax(np.abs(value)))
                value = value * (1 if value[component] >= 0 else -1)
                if component != previous:
                    schedule.append({'at': frame, 'component': component})
                    previous = component
                packed.append(np.delete(value, component) / factor)
            track.update(deltas=encode_values(packed), dropped=schedule)
        else:
            track['deltas'] = encode_values(values * 10 ** 9)
        result.append(track)
    return {'version': 1, 'packing': {'times': times.tolist(), 'valueDigits': 9, 'rotationBits': 24}, 'tracks': result}


def _validate_conversion(skeleton, originals, clip, probes):
    probes = np.asarray(probes, dtype=np.float64)
    if probes.ndim != 1 or not len(probes) or not np.isfinite(probes).all():
        raise ValueError('World validation times must be a finite nonempty vector')
    original_times = np.unique(np.concatenate([track['times'] for track in originals]))
    if not np.isin(original_times, probes).all():
        raise ValueError('World validation plan omits original key times')
    budget('validation_graph_samples', (len(skeleton['nodes']) + len(originals)) * len(probes))
    decoded = decode_clip(clip)
    key_error, rotation_error, world_error, world_scale = 0., 0., 0., 1.
    for original, converted in zip(originals, decoded):
        assert (original['node'], original['property']) == (converted['node'], converted['property'])
        for time, value in zip(original['times'], original['values']):
            reconstructed = sample_track(converted, float(time))
            if not np.isfinite(reconstructed).all() or not np.isfinite(value).all():
                raise ValueError('Nonfinite original/reconstructed key value')
            if original['property'] == 'quaternion':
                dot = np.clip(abs(np.dot(value / np.linalg.norm(value), reconstructed / np.linalg.norm(reconstructed))), 0, 1)
                error = math.degrees(2 * math.acos(dot))
                if not math.isfinite(error):
                    raise ValueError('Nonfinite quaternion key error')
                rotation_error = max(rotation_error, error)
            else:
                error = float(np.max(np.abs(value - reconstructed)))
                if not math.isfinite(error):
                    raise ValueError('Nonfinite vector key error')
                key_error = max(key_error, error)
    for time in probes:
        constants = [{'node': t['node'], 'property': t['property'], 'times': np.array([0.]), 'values': np.asarray([sample_linear(t, float(time))])} for t in originals]
        expected, actual = finite_worlds(skeleton, constants, float(time)), finite_worlds(skeleton, decoded, float(time))
        error = float(np.max(np.abs(expected - actual)))
        scale = float(np.max(np.abs(expected)))
        if not math.isfinite(error) or not math.isfinite(scale):
            raise ValueError('Nonfinite world error/reference scale')
        world_error = max(world_error, error)
        world_scale = max(world_scale, scale)
    if not all(math.isfinite(x) for x in (key_error, rotation_error, world_error, world_scale)):
        raise ValueError('Nonfinite final conversion metric')
    if key_error > 1e-6 or rotation_error > .0001 or world_error > 1e-5 * world_scale:
        raise ValueError('Packed conversion exceeds numerical preservation bounds')
    return {'original_key_max_vector_error': key_error, 'original_key_max_quaternion_degrees': rotation_error, 'world_matrix_max_error': world_error, 'world_matrix_reference_scale': world_scale, 'world_matrix_probe_count': len(probes), 'world_matrix_original_key_count': len(original_times), 'world_matrix_additional_sample_count': len(probes) - len(original_times), 'all_original_key_worlds_checked': True, 'continuous_interval_verified': False, 'scope': 'Every original union key time plus additional discrete samples checked for finite world matrices and numerical agreement. Independent LINEAR/SLERP interpolation uses the existing shared world evaluator; analytic fixtures provide separate narrower world-transform checks. No guarantee for every time inside continuous intervals, Blender/skin/retargeting/contact/naturalness.'}


def validate_conversion(skeleton, originals, clip, probes):
    try:
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            return _validate_conversion(skeleton, originals, clip, probes)
    except (FloatingPointError, OverflowError) as exc:
        raise ValueError('Numerical overflow/invalid operation during conversion validation') from exc


def convert(raw, animation_index=None):
    document, binary = read_glb(raw)
    skeleton = skeleton_only(document)
    tracks, index, name = original_tracks(document, binary, skeleton, animation_index)
    times, probes, work = sampling_plan(tracks, len(skeleton['nodes']))
    clip = pack_tracks(tracks, times)
    verification = validate_conversion(skeleton, tracks, clip, probes)
    return skeleton, clip, {'animation_index': index, 'animation_name': name, 'nodes': len(skeleton['nodes']), 'channels': len(tracks), 'samples': len(times), 'first_time': float(times[0]), 'last_time': float(times[-1]), 'verification': verification, 'resource_usage': work, 'limits': dict(LIMITS)}


def parse_provenance(raw, source_sha):
    budget('provenance_bytes', len(raw))
    value = read_json(raw, 'Provenance')
    required = {'source', 'credit', 'license', 'modifications', 'source_sha256'}
    if not isinstance(value, dict) or not required <= set(value) or any(not isinstance(value[k], str) or not value[k].strip() for k in required):
        raise ValueError('Provenance needs source, credit, license, modifications and reviewed source_sha256 strings')
    if value['source_sha256'] != source_sha:
        raise ValueError('Source bytes differ from reviewed provenance hash')
    allowed = required | {'license_url', 'restrictions'}
    if set(value) - allowed:
        raise ValueError('Unsupported provenance fields: ' + ', '.join(sorted(set(value) - allowed)) + '. Retain item-specific terms in license/restrictions; unknown fields are not discarded.')
    for key in ('license_url', 'restrictions'):
        if key in value and (not isinstance(value[key], str) or not value[key].strip()):
            raise ValueError('Optional ' + key + ' must be a nonempty string')
    return {k: value[k] for k in sorted(allowed) if k in value}


def provenance_record(path, source_sha):
    return parse_provenance(read_bounded(path, 'provenance_bytes'), source_sha)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--provenance', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--animation', type=int)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output must be a new directory; preserve prior conversions')
    raw = read_bounded(args.source, 'source_bytes')
    digest = hashlib.sha256(raw).hexdigest()
    provenance_raw = read_bounded(args.provenance, 'provenance_bytes')
    provenance = parse_provenance(provenance_raw, digest)
    skeleton, clip, report = convert(raw, args.animation)
    report.update(schema=1, status='CPU-conversion-numerically-verified', source_sha256=digest, source_bytes=len(raw), provenance_sha256=hashlib.sha256(provenance_raw).hexdigest(), writer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), decoder_sha256=hashlib.sha256(Path(__file__).with_name('source_motion.py').read_bytes()).hexdigest(), numpy_version=np.__version__, provenance=provenance, rights_scope='All supported source/rights fields retained, unknown fields refused, and input/provenance byte hashes recorded; this tool does not grant or determine legal rights.', modifications='Stripped mesh/skin/material/image/logo references; kept node indices/TRS, unioned LINEAR channel key times, encoded packed-v1 vectors and smallest-three quaternions. No retargeting or appearance export.', output_files=['motion-skeleton.json', 'motion-packed-v1.json', 'conversion-report.json'])
    documents = [(name, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n') for name, value in [('motion-skeleton.json', skeleton), ('motion-packed-v1.json', clip), ('conversion-report.json', report)]]
    args.output.mkdir(parents=True, exist_ok=False)
    for name, text in documents:
        (args.output / name).write_text(text, 'utf-8')
    print(json.dumps({'status': report['status'], 'nodes': report['nodes'], 'channels': report['channels'], 'samples': report['samples'], 'output': str(args.output)}))


if __name__ == '__main__':
    main()
