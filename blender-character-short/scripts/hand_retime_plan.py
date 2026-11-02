"""Validate a bounded, post-contact recovery time map without importing Blender."""


def validate_plan(plan, first, last, contact_end):
    if not isinstance(plan, dict):
        raise ValueError('Hand retime plan must be an object')
    if plan.get('side') not in ('left', 'right'):
        raise ValueError('Choose the configured left or right arm')
    if plan.get('timing') not in ('linear', 'smoothstep'):
        raise ValueError('Timing must be linear or smoothstep')
    intervals = []
    for key in ('source_frames', 'output_frames'):
        pair = plan.get(key)
        if not isinstance(pair, list) or len(pair) != 2 or any(type(v) is not int for v in pair):
            raise ValueError(key + ' requires two integer frames')
        if not first <= pair[0] < pair[1] <= last:
            raise ValueError(key + ' is unordered or outside the saved scene')
        intervals.append(tuple(pair))
    source, output = intervals
    if source[0] != output[0]:
        raise ValueError('Source and output must share the initial recovery frame')
    if min(source[0], output[0]) <= contact_end:
        raise ValueError('Recovery must start after every declared contact transition')
    return source, output


def source_time(frame, source, output, timing):
    if not output[0] <= frame <= output[1]:
        raise ValueError('Frame lies outside the retimed interval')
    u = (frame - output[0]) / (output[1] - output[0])
    if timing == 'smoothstep':
        u = u * u * (3 - 2 * u)
    elif timing != 'linear':
        raise ValueError('Unknown timing')
    return source[0] + u * (source[1] - source[0])
