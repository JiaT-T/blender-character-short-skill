"""Strict external mappings and shortest quaternion distance for existing rigs."""
import math
import re


def validate_plan(plan):
    required = {'schema', 'source_sha256', 'controller_object', 'model_armature',
                'mesh_object', 'existing_controller_bones', 'pairs',
                'maximum_baseline_skin_difference_m'}
    if not isinstance(plan, dict) or set(plan) != required or type(plan['schema']) is not int or plan['schema'] != 1:
        raise ValueError('Require exact existing-controller schema1 fields')
    if not isinstance(plan['source_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', plan['source_sha256']):
        raise ValueError('Reviewed source SHA256 required')
    for field in ('controller_object', 'model_armature', 'mesh_object'):
        if not isinstance(plan[field], str) or not plan[field] or len(plan[field]) > 256:
            raise ValueError('Explicit bounded object names required')
    if plan['controller_object'] == plan['model_armature']:
        raise ValueError('Controller and original model must be distinct')
    count = plan['existing_controller_bones']
    tolerance = plan['maximum_baseline_skin_difference_m']
    if type(count) is not int or not 1 <= count <= 2048:
        raise ValueError('Bounded original controller population required')
    if type(tolerance) not in (int, float) or not math.isfinite(tolerance) or not 0 < tolerance <= 1e-4:
        raise ValueError('Require finite positive baseline tolerance <=0.1mm')
    pairs = plan['pairs']
    if not isinstance(pairs, list) or not 1 <= len(pairs) <= 128:
        raise ValueError('Require1..128 explicit binding pairs')
    for row in pairs:
        if not isinstance(row, dict) or set(row) != {'model_bone', 'controller_bone'}:
            raise ValueError('Exact bone pair fields required')
        if any(not isinstance(v, str) or not v or len(v) > 128 for v in row.values()):
            raise ValueError('Nonempty bounded bone names required')
        if len(('SkillBind-' + row['model_bone']).encode('utf-8')) > 63 or len(row['controller_bone'].encode('utf-8')) > 63:
            raise ValueError('Exact Blender bone/helper names must fit63 UTF8 bytes')
    if len({r['model_bone'] for r in pairs}) != len(pairs) or len({r['controller_bone'] for r in pairs}) != len(pairs):
        raise ValueError('One-to-one missing binding pairs required')
    return plan


def shortest_quaternion_angle_degrees(left, right):
    """q and -q represent the same orientation; refuse invalid measurements."""
    normalized = []
    for q in (left, right):
        if len(q) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in q):
            raise ValueError('Require four finite quaternion components')
        scale = max(abs(v) for v in q)
        if scale == 0:
            raise ValueError('Zero quaternion has no orientation')
        values = [v / scale for v in q]
        norm = math.sqrt(sum(v * v for v in values))
        normalized.append([v / norm for v in values])
    dot = abs(sum(a * b for a, b in zip(*normalized)))
    return math.degrees(2 * math.acos(min(1.0, dot)))
