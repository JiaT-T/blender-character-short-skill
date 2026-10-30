"""Bake a prop contact point onto a configured moving anatomical anchor.

Character mappings own bone names and palm calibration. Story owns contact
intervals and the prop-local contact point. No physics or collision claim.
"""
from mathutils import Vector
import bpy

def anchor_world(arm,anchor,height):
    start=arm.pose.bones.get(anchor['start_bone']);end=arm.pose.bones.get(anchor['end_bone'])
    if start is None or end is None:raise ValueError('Contact anchor references a missing bone')
    fraction=float(anchor.get('fraction',.5))
    if not 0<=fraction<=1:raise ValueError('Anchor fraction must be in [0,1]')
    point=start.head.lerp(end.head,fraction);normal=start.matrix.to_3x3()@Vector(anchor['normal_local'])
    if normal.length<1e-8:raise ValueError('Contact anchor normal is zero')
    point+=normal.normalized()*height*float(anchor.get('normal_offset',0))
    return arm.matrix_world@point

def bake_contacts(scene,arm,prop,anchors,contacts,height,fps,time_scale,end_frame):
    if not contacts:return {'contacts':[],'frames':[],'scope':'No contact requested'}
    if prop.parent is not None:raise ValueError('Contact bake requires an unparented world-space story prop')
    intervals=[]
    for contact in contacts:
        if contact['anchor'] not in anchors:raise ValueError('Unmapped contact anchor: '+contact['anchor'])
        start=float(contact['start'])*time_scale;end=float(contact['end'])*time_scale;entry=float(contact.get('blend_in',0))*time_scale;exit=float(contact.get('blend_out',0))*time_scale
        if not 0<=start<end or min(entry,exit)<0 or start-entry<0 or end+exit>(end_frame/fps)+1e-7:raise ValueError('Contact timing must fit the shot duration, with nonnegative transition lengths')
        intervals.append((start-entry,end+exit,start,end,entry,exit,contact))
    for a,b in zip(sorted(intervals,key=lambda x:x[0]),sorted(intervals,key=lambda x:x[0])[1:]):
        if a[1]>b[0]:raise ValueError('Overlapping contact transitions need an explicit handoff; unsupported')
    # Capture the entire free trajectory before adding dense keys. Otherwise
    # earlier insertions change later Bezier evaluations during the bake.
    free={}
    for frame in range(1,end_frame+1):
        scene.frame_set(frame);bpy.context.view_layer.update();free[frame]=(prop.location.copy(),prop.matrix_world.to_3x3().copy())
    report=[]
    smooth=lambda x:x*x*(3-2*x)
    for frame in range(1,end_frame+1):
        scene.frame_set(frame);bpy.context.view_layer.update();t=(frame-1)/fps;position,rotation=free[frame];value=position.copy()
        for begin,finish,start,end,entry,exit,c in intervals:
            if not begin<=t<=finish:continue
            weight=1.0
            if t<start:weight=smooth((t-begin)/entry) if entry else 1
            elif t>end:weight=1-smooth((t-end)/exit) if exit else 1
            anchor=anchor_world(arm,anchors[c['anchor']],height);local=Vector(c['prop_point'])*height;offset=rotation@local;target=anchor-offset;value=position.lerp(target,weight);gap=(value+offset-anchor).length
            report.append({'frame':frame,'anchor':c['anchor'],'weight':weight,'anchor_world':list(anchor),'contact_world':list(value+offset),'gap':gap,'full_contact':weight>=1-1e-8})
            if weight>=1-1e-8 and gap>height*1e-6:raise ValueError('Baked full contact exceeds tolerance')
        prop.location=value;prop.keyframe_insert('location',frame=frame)
    for fc in prop.animation_data.action.fcurves:
        if fc.data_path=='location':
            for key in fc.keyframe_points:key.interpolation='LINEAR'
    scene.frame_set(1);bpy.context.view_layer.update()
    return {'contacts':contacts,'frames':report,'scope':'Integer-frame contact-point alignment; calibrated anchor/visible clearance still require rendered checks; no collision/physics/subframe guarantee'}
