"""Explicit bounded audit windows without changing source motion/bake identity."""
def audit_times(frames,substeps,window=None):
    if not isinstance(frames,list) or len(frames)!=2 or any(type(x) is not int for x in frames) or not 1<=frames[0]<frames[1]<=20000 or frames[1]-frames[0]+1>480:raise ValueError('Bounded original motion interval required')
    if type(substeps) is not int or substeps not in [1,2]:raise ValueError('Explicit integer/half-frame sampling required')
    selected=frames if window is None else window
    if not isinstance(selected,list) or len(selected)!=2 or any(type(x) is not int for x in selected) or not frames[0]<=selected[0]<selected[1]<=frames[1]:raise ValueError('Audit window must be a nonempty integer interval inside the original motion')
    first,last=selected
    return list(selected),[first+i/substeps for i in range((last-first)*substeps+1)]
