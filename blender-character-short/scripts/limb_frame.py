"""Proper limb-plane alignment for explicitly calibrated single-axis joints."""
import numpy as np
import math

def unit(value,label):
    v=np.asarray(value,dtype=float)
    if v.shape!=(3,) or not np.isfinite(v).all() or np.linalg.norm(v)<1e-8:raise ValueError('Finite nonzero '+label+' vector required')
    return v/np.linalg.norm(v)

def hinge_alignment(rest_upper,rest_axis,upper,lower,bend_sign,previous_axis=None):
    if type(bend_sign) is not int or bend_sign not in [-1,1]:raise ValueError('Explicit bend sign -1 or1 required')
    ru=unit(rest_upper,'rest upper');rh=unit(rest_axis,'rest hinge');rh=unit(rh-ru*np.dot(rh,ru),'orthogonal rest hinge');u=unit(upper,'upper');l=unit(lower,'lower');axis=np.cross(u,l)
    if np.linalg.norm(axis)<1e-6:
        candidate=unit(previous_axis,'previous hinge') if previous_axis is not None else rh;axis=candidate-u*np.dot(candidate,u)
        if np.linalg.norm(axis)<1e-6:axis=rh-u*np.dot(rh,u)
    else:axis*=bend_sign
    axis=unit(axis,'desired hinge');source=np.column_stack([rh,ru,np.cross(rh,ru)]);dest=np.column_stack([axis,u,np.cross(axis,u)]);rotation=dest@source.T
    if not np.allclose(rotation@rotation.T,np.eye(3),atol=1e-6) or abs(np.linalg.det(rotation)-1)>1e-6:raise ValueError('Proper hinge-frame rotation required')
    return rotation,axis

def bend_floor(upper,lower,minimum_degrees,axis_hint=None):
    if type(minimum_degrees) not in (int,float) or not math.isfinite(minimum_degrees) or not 0<=minimum_degrees<=30:raise ValueError('Explicit minimum bend must be in0..30degrees')
    u=unit(upper,'upper');l=unit(lower,'lower');angle=math.acos(float(np.clip(np.dot(u,l),-1,1)));minimum=math.radians(minimum_degrees)
    if angle>=minimum-1e-9:return l,0.
    axis=np.cross(u,l)
    if np.linalg.norm(axis)<1e-6:
        if axis_hint is None:raise ValueError('Straight source needs a calibrated bend-plane hint')
        axis=unit(axis_hint,'bend hint');axis-=u*np.dot(u,axis)
    elif axis_hint is not None:
        # Below the explicitly configured floor, tiny capture noise can reverse
        # a near-straight normal and roll the target thigh by180degrees. Keep
        # the observed plane, choosing its temporally consistent hemisphere.
        hint=unit(axis_hint,'bend hint');hint-=u*np.dot(hint,u);hint=unit(hint,'orthogonal bend hint')
        if np.dot(axis,hint)<0:axis=-axis
    axis=unit(axis,'bend axis');adapted=u*math.cos(minimum)+np.cross(axis,u)*math.sin(minimum)+axis*np.dot(axis,u)*(1-math.cos(minimum))
    return unit(adapted,'adapted lower'),math.degrees(minimum-angle)
