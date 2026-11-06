"""Explicit neutral-foot source references; no inferred contact labels."""
import math
import numpy as np

def digest(value):
    if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise ValueError('Reviewed lowercase source/reference digest required')

def vector(value):
    if not isinstance(value,list) or len(value)!=3 or any(type(x) not in [int,float] or not math.isfinite(x) for x in value):raise ValueError('Finite three-component foot reference required')
    return np.asarray(value,dtype=float)

def rotation(value):
    if not isinstance(value,list) or len(value)!=3:raise ValueError('Foot reference requires3x3 rotation')
    m=np.asarray([vector(row) for row in value])
    if not np.allclose(m@m.T,np.eye(3),atol=1e-6) or abs(np.linalg.det(m)-1)>1e-6:raise ValueError('Proper unit-scale foot-reference rotation required')
    return m

def validate(value,source_glb_sha256,basis):
    if not isinstance(value,dict) or set(value)!={'source_glb_sha256','review_sha256','feet'}:raise ValueError('Explicit reviewed foot-reference contract required')
    digest(value['source_glb_sha256']);digest(value['review_sha256'])
    if value['source_glb_sha256']!=source_glb_sha256:raise ValueError('Foot references belong to another source clip')
    feet=value['feet']
    if not isinstance(feet,dict) or set(feet)!={'left','right'}:raise ValueError('Both original feet need explicit source references')
    for row in feet.values():
        if not isinstance(row,dict) or set(row)!={'source_frame','ankle_rotation','toe_rotation','forward'}:raise ValueError('Explicit foot frame, rotations and recorded marker direction required')
        if type(row['source_frame']) is not int or not 1<=row['source_frame']<=20000:raise ValueError('Bounded original source calibration frame required')
        rotation(row['ankle_rotation']);rotation(row['toe_rotation']);v=vector(row['forward'])
        if abs(np.linalg.norm(v)-1)>1e-6 or np.linalg.norm((np.asarray(basis)@v)[:2])<.3:raise ValueError('Foot calibration needs a unit direction with a usable horizontal component')
    return value

def heading_alignment(source_forward,basis,target_forward):
    source=np.asarray(basis)@np.asarray(source_forward);target=np.asarray(target_forward,dtype=float)
    if not np.isfinite(source).all() or not np.isfinite(target).all() or min(np.linalg.norm(source[:2]),np.linalg.norm(target[:2]))<1e-6:raise ValueError('Usable finite horizontal toe directions required')
    yaw=math.atan2(source[1],source[0])-math.atan2(target[1],target[0]);c,s=math.cos(yaw),math.sin(yaw)
    return np.asarray([[c,-s,0],[s,c,0],[0,0,1]],dtype=float)
