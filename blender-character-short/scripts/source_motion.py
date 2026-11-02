"""Read externally supplied packed node motion; no network or bundled clips.

The supported v1 contract uses component-major delta streams, decimal vector
quantization and smallest-three quaternion quantization. Events/morph playback
are not retargeted by this module.
"""
import math
import numpy as np

WIDTH={'position':3,'quaternion':4,'scale':3,'weights':1}


def unpack_deltas(track,count,width):
    values=np.asarray(track.get('deltas',[]),dtype=np.float64)
    if values.ndim!=1 or len(values)!=count*width or not np.isfinite(values).all():
        raise ValueError('Invalid motion delta count or values')
    return np.cumsum(values.reshape(width,count),axis=1).T


def decode_track(track,packing):
    prop=track['property']
    if prop not in WIDTH:raise ValueError('Unsupported motion property: '+prop)
    width=WIDTH[prop]
    if 'value' in track:
        values=np.asarray(track['value'],dtype=np.float32)
        if values.shape!=(width,) or not np.isfinite(values).all():
            raise ValueError('Invalid constant track')
        return np.array([0],np.float32),values.reshape(1,width)
    if not packing:raise ValueError('Animated track requires packing')
    times=np.asarray(packing['times'],dtype=np.float32)
    if times.ndim!=1 or not len(times) or not np.isfinite(times).all() or (np.diff(times)<=0).any():
        raise ValueError('Motion times must be finite and strictly increasing')
    count=len(times)
    if prop!='quaternion':
        digits=int(packing['valueDigits'])
        if not 0<=digits<=12:raise ValueError('Unsupported decimal quantization')
        values=(unpack_deltas(track,count,width)/(10**digits)).astype(np.float32)
        return times,values
    bits=int(packing['rotationBits'])
    if not 2<=bits<=24:raise ValueError('Unsupported quaternion quantization')
    dropped=track.get('dropped',[])
    indexes=[int(event['at']) for event in dropped]
    if indexes!=sorted(set(indexes)) or any(i<0 or i>=count for i in indexes):
        raise ValueError('Invalid dropped-component schedule')
    if any(int(event['component']) not in range(4) for event in dropped):
        raise ValueError('Invalid dropped quaternion component')
    packed=unpack_deltas(track,count,3)
    factor=math.sqrt(.5)/(2**(bits-1)-1)
    output=np.empty((count,4),np.float32)
    cursor=0;component=3
    for frame in range(count):
        if cursor<len(dropped) and indexes[cursor]==frame:
            component=int(dropped[cursor]['component']);cursor+=1
        quaternion=np.zeros(4,np.float64);total=0.;source_index=0
        for index in range(4):
            if index==component:continue
            quaternion[index]=packed[frame,source_index]*factor
            source_index+=1;total+=quaternion[index]*quaternion[index]
        quaternion[component]=math.sqrt(max(0.,1-total))
        if frame and float(np.dot(quaternion,output[frame-1]))<0:quaternion=-quaternion
        output[frame]=quaternion
    return times,output


def decode_clip(document):
    if document.get('version')!=1:raise ValueError('Unsupported packed motion version')
    result=[]
    seen=set()
    for track in document['tracks']:
        node=int(track['node'])
        if node<0:raise ValueError('Negative motion node')
        identity=(node,track['property'],track.get('target'))
        if identity in seen:raise ValueError('Duplicate motion channel')
        seen.add(identity)
        times,values=decode_track(track,document.get('packing'))
        result.append({'node':node,'property':track['property'],
                       'target':track.get('target'),'times':times,'values':values})
    return result


def sample_track(track,time):
    times,values=track['times'],track['values']
    if len(times)==1 or time<=times[0]:return values[0].astype(np.float64)
    if time>=times[-1]:return values[-1].astype(np.float64)
    right=int(np.searchsorted(times,time,side='right'));left=right-1
    weight=float((time-times[left])/(times[right]-times[left]))
    a,b=values[left].astype(np.float64),values[right].astype(np.float64)
    if track['property']!='quaternion':return a*(1-weight)+b*weight
    dot=float(np.dot(a,b))
    if dot<0:b=-b;dot=-dot
    if dot>.9995:
        value=a*(1-weight)+b*weight
    else:
        angle=math.acos(max(-1.,min(1.,dot)))
        value=(math.sin((1-weight)*angle)*a+math.sin(weight*angle)*b)/math.sin(angle)
    norm=np.linalg.norm(value)
    if norm<1e-12:raise ValueError('Degenerate quaternion sample')
    return value/norm


def quaternion_matrix(value):
    x,y,z,w=np.asarray(value,dtype=np.float64)
    norm=x*x+y*y+z*z+w*w
    if norm<1e-12:raise ValueError('Degenerate node quaternion')
    scale=2/norm
    return np.array([[1-scale*(y*y+z*z),scale*(x*y-z*w),scale*(x*z+y*w)],
                     [scale*(x*y+z*w),1-scale*(x*x+z*z),scale*(y*z-x*w)],
                     [scale*(x*z-y*w),scale*(y*z+x*w),1-scale*(x*x+y*y)]])


def node_worlds(skeleton,tracks=(),time=0):
    nodes=skeleton['nodes'];overrides={}
    for track in tracks:
        if track['node']>=len(nodes):raise ValueError('Motion node outside skeleton')
        if track['property']=='weights':continue
        overrides.setdefault(track['node'],{})[track['property']]=sample_track(track,time)
    local=[];parent={}
    for index,node in enumerate(nodes):
        values=overrides.get(index,{})
        if 'matrix' in node:
            if values:raise ValueError('Animated matrix nodes require an explicit decomposition')
            matrix=np.asarray(node['matrix'],dtype=float).reshape(4,4).T
        else:
            matrix=np.eye(4)
            matrix[:3,:3]=quaternion_matrix(values.get('quaternion',node.get('rotation',[0,0,0,1])))@np.diag(values.get('scale',node.get('scale',[1,1,1])))
            matrix[:3,3]=values.get('position',node.get('translation',[0,0,0]))
        if not np.isfinite(matrix).all():raise ValueError('Nonfinite skeleton matrix')
        local.append(matrix)
        for child in node.get('children',[]):
            if child in parent or child not in range(len(nodes)):raise ValueError('Invalid skeleton hierarchy')
            parent[child]=index
    worlds={};active=set()
    def visit(index):
        if index in worlds:return worlds[index]
        if index in active:raise ValueError('Skeleton cycle')
        active.add(index)
        matrix=visit(parent[index])@local[index] if index in parent else local[index]
        active.remove(index);worlds[index]=matrix;return matrix
    return np.array([visit(index) for index in range(len(nodes))])
