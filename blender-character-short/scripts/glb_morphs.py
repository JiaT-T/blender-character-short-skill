"""Read named GLB POSITION morph deltas, including sparse zero-base accessors.

Matches the pinned source GLTFLoader.loadAccessor zero/override behavior.
Deliberately restricted to unnormalized FLOAT VEC3 targets in the GLB buffer.
"""
import numpy as np


def read_position_target(doc,binary,index,read_base):
    a=doc['accessors'][index]
    if a['componentType']!=5126 or a['type']!='VEC3' or a.get('normalized',False):
        raise ValueError('Source morph reader supports only unnormalized FLOAT VEC3 POSITION targets')
    count=a['count']
    values=np.array(read_base(index),dtype=np.float64,copy=True) if 'bufferView' in a else np.zeros((count,3),dtype=np.float64)
    if values.shape!=(count,3):raise ValueError('Morph base accessor has inconsistent shape')
    sparse=a.get('sparse')
    if sparse:
        n=sparse['count'];ix=sparse['indices'];val=sparse['values'];types={5121:np.dtype('u1'),5123:np.dtype('<u2'),5125:np.dtype('<u4')}
        if ix['componentType'] not in types:raise ValueError('Morph sparse indices must be unsigned bytes, shorts or ints')
        if n<0 or n>count:raise ValueError('Invalid sparse morph count')
        def read_view(spec,dtype,components):
            view=doc['bufferViews'][spec['bufferView']]
            if view.get('buffer',0)!=0 or view.get('byteStride'):raise ValueError('Sparse morph data must use a contiguous view of the GLB buffer')
            relative=spec.get('byteOffset',0);offset=view.get('byteOffset',0)+relative;length=n*components*dtype.itemsize
            if relative<0 or relative+length>view['byteLength'] or offset+length>len(binary):raise ValueError('Sparse morph buffer range is invalid')
            return np.frombuffer(binary,dtype=dtype,count=n*components,offset=offset).reshape(n,components)
        indices=read_view(ix,types[ix['componentType']],1).ravel().astype(np.int64);patch=read_view(val,np.dtype('<f4'),3)
        if len(indices) and (indices.min()<0 or indices.max()>=count or np.any(np.diff(indices)<=0)):raise ValueError('Sparse morph indices must be increasing, unique and in range')
        values[indices]=patch
    if not np.isfinite(values).all():raise ValueError('Nonfinite source morph POSITION target')
    return values
