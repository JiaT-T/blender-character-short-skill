"""Check native spline metrics against independent integrated cubic length.

Higher calc_length resolution need not be more accurate at float precision.
Require two native resolutions to agree with the separately integrated stored
controls; reject the pose when that independent agreement cannot be established.
"""
import numpy as np
from curve_smoothing import arc_length


def native_length_witness(spline,points,target_length,tolerance):
    for point,co in zip(spline.points,points):point.co=(*co,1.)
    stored=np.array([p.co[:3] for p in spline.points])
    numerical=arc_length(stored,32)
    numerical_delta=abs(numerical-arc_length(stored,24))
    lengths={resolution:float(spline.calc_length(resolution=resolution)) for resolution in (24,28,32,36,40)}
    if not np.isfinite(numerical) or not all(np.isfinite(v) for v in lengths.values()):
        raise ValueError('Non-finite native or integrated curve length')
    qualified=[r for r,length in lengths.items() if abs(length-numerical)<=tolerance*.25]
    if len(qualified)<2 or numerical_delta>tolerance*.125:
        raise ValueError(f'Independent native length agreement failed: integrated={numerical!r}, native={lengths!r}')
    chosen=sorted(qualified,key=lambda r:abs(lengths[r]-numerical))[:2]
    return dict(numerical_length=numerical,numerical_target_error=abs(numerical-target_length),
                quadrature_24_vs_32=numerical_delta,native_lengths=lengths,selected_resolutions=chosen,
                native_target_error=max(abs(lengths[r]-target_length) for r in chosen),
                native_quadrature_error=max(abs(lengths[r]-numerical) for r in chosen),
                native_pair_delta=abs(lengths[chosen[0]]-lengths[chosen[1]]))
