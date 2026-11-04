"""Opt-in start stance and bounded acceleration into an actual source-first pose."""
import math
import bpy
from mathutils import Vector
from body_approach_pose import smooth,blend_basis,mesh_point,solve_ankle
from body_motion_runtime import orient_world,foot_points
from build_performance import two_bone

def prepare_launch(character,plan,gait,base,first_root,pivot,source_anchor):
    if plan['schema']!=2:return None
    settings=plan['launch'];h=character['height'];fps=plan['fps'];duration=(settings['ramp_frames']+1)/fps;direction=Vector(plan['travel']['direction']);speed=(gait[1]['root']-gait[0]['root']).dot(direction)*fps
    if not math.isfinite(speed) or speed<=0:raise ValueError('Launch needs positive measured source-first travel velocity')
    distance=.5*speed*duration
    if distance>.25*h:raise ValueError('Launch acceleration distance exceeds.25character heights')
    shift=first_root-gait[0]['root'];initial_root=first_root-direction*distance;initial_root.z-=settings['crouch_H']*h;horizontal=initial_root-base[0]['root'];horizontal.z=0
    side=settings['reference_side'];other='left' if side=='right' else 'right'
    return {'settings':settings,'height':h,'ground':character['ground'],'duration':duration,'speed':speed,'distance':distance,'direction':direction,'first_root':first_root,'initial_root':initial_root,'initial_basis':base[0]['basis'],'first_basis':gait[0]['basis'],'first_feet':gait[0]['feet'],'source_offset':shift,'reference_pivot':pivot,'reference_anchor':source_anchor+shift,'reference_side':side,'free_side':other,'free_initial_ankle':base[0]['feet'][other]['ankle']+horizontal,'free_initial_rotation':base[0]['feet'][other]['rotation'],'free_end_ankle':gait[0]['feet'][other]['ankle']+shift,'free_end_velocity':(gait[1]['feet'][other]['ankle']-gait[0]['feet'][other]['ankle'])*fps,'maximum_reference_error_H':0.,'maximum_free_clearance_lift_H':0.,'minimum_sole_H':1e9,'rows':[]}

def apply_launch(scene,arm,actor,controls,legs,character,plan,selection,context,frame):
    s=context['settings'];h=context['height'];u=max(0.,min(1.,(frame-s['hold_frames'])/(s['ramp_frames']+1)));weight=smooth(u);side=context['reference_side'];other=context['free_side'];floor=character['ground']+plan['travel']['sole_height']*h
    for name in controls:arm.pose.bones[name].matrix_basis=blend_basis(context['initial_basis'][name],context['first_basis'][name],weight)
    # A constant source-first shoe orientation avoids rolling the ready foot
    # through the ground while the neutral torso rises into the first stride.
    toe=legs[side]['bones'][3];arm.pose.bones[toe].matrix_basis=context['first_basis'][toe]
    actor.location=context['first_root']-context['direction']*context['distance']*(1-u*u);actor.location.z-=s['crouch_H']*h*(1-weight);bpy.context.view_layer.update()
    def pole(names,label):
        a,b,c=[arm.pose.bones[n] for n in names];axis=c.head-a.head;offset=b.head-a.head
        if axis.length>1e-8:
            offset-=axis.normalized()*offset.dot(axis.normalized())
            if offset.length>.00001*h:return arm.matrix_world@b.head
        raw=character.get('stationary_support',{}).get(label,{}).get('pole')
        if raw is None:raise ValueError('Launch straight leg requires an explicit actor-relative knee pole')
        return Vector((raw[0]*h,raw[1]*h,character['ground']+raw[2]*h))+actor.location
    names=legs[side]['bones'][:3];q=context['first_feet'][side]['rotation'];target=context['first_feet'][side]['ankle']+context['source_offset'];ref_pole=pole(names,side);solve_ankle(arm,names,target,q,two_bone,h,ref_pole)
    for iteration in range(12):
        error=context['reference_anchor']-mesh_point(scene,context['reference_pivot'])
        if error.length<.00003*h:break
        target+=error;solve_ankle(arm,names,target,q,two_bone,h,ref_pole)
    reference_error=(mesh_point(scene,context['reference_pivot'])-context['reference_anchor']).length/h
    if reference_error>.0001:raise ValueError('Launch material reference failed at frame'+str(frame)+' errorH'+str(reference_error))
    p0=context['free_initial_ankle'];p1=context['free_end_ankle'];tangent=context['free_end_velocity']*context['duration'];target=p0*(2*u**3-3*u*u+1)+p1*(-2*u**3+3*u*u)+tangent*(u**3-u*u);target.z+=s['free_lift_H']*h*math.sin(math.pi*u)**2
    names=legs[other]['bones'][:3];q=context['free_initial_rotation'].slerp(context['first_feet'][other]['rotation'],weight);free_pole=pole(names,other);solve_ankle(arm,names,target,q,two_bone,h,free_pole);added=0.
    for iteration in range(4):
        low=min(p.z for _,_,p in foot_points(selection,other))
        if low>=floor-.00003*h:break
        delta=floor-low;added+=delta/h
        if added>.03:raise ValueError('Launch free-foot floor correction exceeds.03H')
        target.z+=delta;solve_ankle(arm,names,target,q,two_bone,h,free_pole)
    minimum=min(p.z for label in (side,other) for _,_,p in foot_points(selection,label))/h
    if minimum<floor/h-.00003:raise ValueError('Launch actual sole below floor at frame'+str(frame))
    context['maximum_reference_error_H']=max(context['maximum_reference_error_H'],reference_error);context['maximum_free_clearance_lift_H']=max(context['maximum_free_clearance_lift_H'],added);context['minimum_sole_H']=min(context['minimum_sole_H'],minimum)
    row={'frame':frame,'phase':'hold' if frame<=s['hold_frames'] else 'accelerating-launch','u':u,'root':list(actor.location),'reference_pivot':context['reference_pivot'],'reference_anchor_world':list(context['reference_anchor']),'reference_contact_phase':'launch','reference_pivot_error_H':reference_error,'minimum_sole_z_H':minimum,'free_clearance_lift_H':added}
    context['rows'].append(row);return row

def launch_report(context):
    if context is None:return None
    return {'settings':context['settings'],'ramp_duration_seconds':context['duration'],'measured_source_initial_speed_world':context['speed'],'acceleration_distance_H':context['distance']/context['height'],'maximum_reference_pivot_error_H':context['maximum_reference_error_H'],'maximum_free_clearance_lift_H':context['maximum_free_clearance_lift_H'],'minimum_selected_sole_z_H':context['minimum_sole_H'],'rows':context['rows'],'scope':'Original-rig ready stance and bounded quadratic root acceleration into the actual source-first pose. Reference shoe orientation/material anchor retained; free ankle Hermite endpoint velocity and sin-squared lift. No full-body rotational C1, physics, mass balance, collision, subframe or naturalness acceptance.'}
