"""Analytical ankle relocation with captured knee-plane parallel transport."""
import math,numpy as np

def vec(v):
    a=np.asarray(v,dtype=np.float64)
    if a.shape!=(3,) or not np.isfinite(a).all():raise ValueError('Finite 3D stance vector required')
    return a

def matched_knee(hip,knee,ankle,target):
    h,k,a,t=map(vec,[hip,knee,ankle,target]);lu=float(np.linalg.norm(k-h));ll=float(np.linalg.norm(a-k));old=a-h;new=t-h;od=float(np.linalg.norm(old));distance=float(np.linalg.norm(new))
    if min(lu,ll,od,distance)<1e-7 or not abs(lu-ll)+1e-7<distance<lu+ll-1e-7:raise ValueError('Degenerate or unreachable ankle relocation')
    old/=od;direction=new/distance;cross=np.cross(old,direction);cosine=float(np.clip(np.dot(old,direction),-1,1))
    if cosine<-.999999:raise ValueError('Antiparallel relocation has no unique captured-plane transport')
    K=np.asarray([[0,-cross[2],cross[1]],[cross[2],0,-cross[0]],[-cross[1],cross[0],0]])
    rotation=np.eye(3)+K+K@K/(1+cosine)
    # Transport the old bend-plane offset as a direction, rather than pinning
    # the old knee point. Pinning that point can add large thigh roll when a
    # nearly straight leg's ankle moves sideways by only a few centimetres.
    pole=rotation@(k-h);pole-=direction*np.dot(pole,direction);length=float(np.linalg.norm(pole))
    if length<1e-7:raise ValueError('Straight captured knee has no reviewed bend plane')
    along=(lu*lu-ll*ll+distance*distance)/(2*distance);rise=math.sqrt(max(0.,lu*lu-along*along));result=h+direction*along+pole/length*rise
    if not np.isfinite(result).all():raise ValueError('Nonfinite relocated knee')
    return result
