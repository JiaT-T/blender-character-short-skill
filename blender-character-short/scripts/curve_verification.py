"""Shared pre-write/read-back sampling budget; no Blender or asset dependency."""
import math


def verification_times(original_knots,candidate_knots,required_times,control_count,maximum_points=1000000):
    if type(control_count) is not int or not 4<=control_count<=128:
        raise ValueError('4..128 curve controls required')
    if type(maximum_points) is not int or not 1<=maximum_points<=1000000:
        raise ValueError('Verification point budget must be 1..1000000')
    groups=[list(original_knots),list(candidate_knots),list(required_times)]
    if any(len(group)>16000 for group in groups):raise ValueError('Verification time input budget exceeded')
    merged=sorted({float(t) for group in groups for t in group})
    if len(merged)<2 or not all(map(math.isfinite,merged)):
        raise ValueError('Finite distinct verification times required')
    result=set(merged)
    for left,right in zip(merged[:-1],merged[1:]):
        result.update(left+(right-left)*fraction for fraction in (.25,.5,.75))
    result=sorted(result)
    if len(result)*control_count>maximum_points:
        raise ValueError(f'Verification budget exceeded before mutation: {len(result)} times x {control_count} controls > {maximum_points}')
    return result
