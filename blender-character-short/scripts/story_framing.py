"""Actual deformed story-feature bounds in the configured orthographic camera."""
import bpy,numpy as np

def select_features(scene,arm,character,plan,features):
    selections={};roles={'head':character['bones']['head'],'left_hand':character['bones']['left_wrist'],'right_hand':character['bones']['right_wrist'],'left_foot':plan['feet']['left']['deform_root'],'right_foot':plan['feet']['right']['deform_root']}
    for feature in sorted(features):
        if feature=='prop':
            if scene.objects.get('Story prop') is None:raise ValueError('Actual Story prop missing for framing')
            selections[feature]={'Story prop':None};continue
        bone=arm.pose.bones[roles[feature]];names={bone.name,*[b.name for b in bone.children_recursive]};entries={}
        for obj in scene.objects:
            if obj.type!='MESH' or obj.hide_render or not any(m.type=='ARMATURE' and m.object==arm for m in obj.modifiers):continue
            groups={g.index for g in obj.vertex_groups if g.name in names};indices=[v.index for v in obj.data.vertices if sum(g.weight for g in v.groups if g.group in groups)>=plan['weight_threshold']]
            if indices:entries[obj.name]=indices
        if not entries:raise ValueError('No weighted visible geometry for framing feature '+feature)
        selections[feature]=entries
    return selections

def projected_feature_bounds(scene,selections,world_points):
    camera=scene.camera
    if camera is None or camera.data.type!='ORTHO':raise ValueError('Framing check supports the actual orthographic pipeline camera only')
    inverse=np.asarray(camera.matrix_world.normalized().inverted());corners=camera.data.view_frame(scene=scene);xmin=min(p.x for p in corners);xmax=max(p.x for p in corners);ymin=min(p.y for p in corners);ymax=max(p.y for p in corners)
    if min(xmax-xmin,ymax-ymin)<=1e-8:raise ValueError('Degenerate camera view frame')
    result={}
    for feature,entries in selections.items():
        points=[]
        for name,indices in entries.items():
            if name not in world_points:raise ValueError('Required framing mesh missing from evaluated geometry')
            values=world_points[name]
            if indices is not None and len(values)!=len(scene.objects[name].data.vertices):raise ValueError('Weighted framing requires unchanged character vertex topology')
            points.extend(values if indices is None else (values[index] for index in indices))
        xyz=np.asarray(points,dtype=np.float64)
        if xyz.size==0 or not np.isfinite(xyz).all():raise ValueError('Invalid framing feature vertices')
        local=np.column_stack((xyz,np.ones(len(xyz))))@inverse.T;u=(local[:,0]-xmin)/(xmax-xmin);v=(local[:,1]-ymin)/(ymax-ymin)
        result[feature]={'minimum_u':float(np.min(u)),'maximum_u':float(np.max(u)),'minimum_v':float(np.min(v)),'maximum_v':float(np.max(v)),'minimum_camera_depth':float(np.min(-local[:,2])),'vertices':len(points)}
    return result

def bounds_inside(bounds,margin):return all(row['minimum_camera_depth']>0 and row['minimum_u']>=margin and row['maximum_u']<=1-margin and row['minimum_v']>=margin and row['maximum_v']<=1-margin for row in bounds.values())
