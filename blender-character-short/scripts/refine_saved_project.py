"""Hash-bound static refinement of a reviewed saved Eevee project into a new copy."""
from pathlib import Path
import argparse, json, math, shutil, sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.dont_write_bytecode=True
from production_contract import declared_file, sha, digest, write_json, producer_identity

def validate_plan(plan, base):
    if plan.get("schema") != 1:
        raise ValueError("Refinement schema 1 required")
    if set(plan)-{"schema","source","output","backup","report","compositor","scene","samples"}:
        raise ValueError("Unknown refinement plan fields")
    source = declared_file(plan["source"], base)
    paths = {k: (Path(base)/plan[k]).resolve() for k in ("output","backup","report")}
    if len(set(paths.values())|{Path(source["path"])}) != 4:
        raise ValueError("Source, backup, output and report must be distinct")
    if paths["output"].suffix != ".blend" or paths["backup"].suffix != ".blend":
        raise ValueError("Output and backup must be Blender files")
    if any(p.exists() for p in paths.values()):
        raise FileExistsError("Use a new refinement version; no overwrite or silent resume")
    if "compositor" not in plan and "scene" not in plan:
        raise ValueError("At least one explicit refinement operation required")
    if "samples" in plan and (type(plan["samples"]) is not int or not 1 <= plan["samples"] <= 4096):
        raise ValueError("Samples must be an integer from 1 to 4096")
    return source, paths

def protected(scene, mutable_materials=(), mutable_lights=(), allow_compositor=False, original_objects=None):
    import bpy
    import scene_integrity as pi
    from saved_look import node_properties, socket_value
    trees = {}
    def graph(t, key=None):
        if t is None: return None
        key = key or ("group:"+t.name)
        if key in trees: return key
        trees[key] = None
        nodes = {}
        for n in t.nodes:
            row = {"type":n.bl_idname,"mute":n.mute,"properties":node_properties(n),
                   "inputs":[socket_value(s) for s in n.inputs],"outputs":[socket_value(s) for s in n.outputs]}
            for attr in ("image","object"):
                obj = getattr(n,attr,None)
                if obj: row[attr] = obj.name
            if getattr(n,"node_tree",None): row["group"] = graph(n.node_tree)
            if getattr(n,"scene",None): row["scene"] = n.scene.name
            nodes[n.name] = row
        trees[key] = digest({"nodes":nodes,"links":sorted([l.from_node.name,list(l.from_node.outputs).index(l.from_socket),l.to_node.name,list(l.to_node.inputs).index(l.to_socket)] for l in t.links)})
        return key
    objects = [o for o in scene.objects if original_objects is None or o.name in original_objects]
    result = {"objects":{o.name:digest(pi._object(o)) for o in objects},
        "meshes":{o.data.name:digest(pi._mesh(o.data)) for o in objects if o.type=="MESH"},
        "rigs":{o.data.name:digest(pi._armature(o.data)) for o in objects if o.type=="ARMATURE"},
        "actions":{a.name:digest(pi._action(a)) for a in bpy.data.actions},
        "lights":{o.name:digest(pi._rna(o.data,skip={"node_tree","animation_data","override_library","asset_data","library"})) for o in objects if o.type=="LIGHT" and o.name not in mutable_lights},
        "cameras":{o.name:digest(pi._rna(o.data,skip={"animation_data","override_library","asset_data","library"})) for o in objects if o.type=="CAMERA"},
        "view":{k:getattr(scene.view_settings,k) for k in ("view_transform","look","exposure","gamma","use_curve_mapping")},
        "render":{k:getattr(scene.render,k) for k in ("engine","resolution_x","resolution_y","resolution_percentage","film_transparent","use_compositing")},
        "timing":[scene.frame_start,scene.frame_end,scene.frame_current,scene.frame_subframe,scene.render.fps,scene.render.fps_base],
        "camera":scene.camera.name if scene.camera else None,
        "images":{i.name:{"source":i.source,"colorspace":i.colorspace_settings.name,"packed_sha256":__import__("hashlib").sha256(i.packed_file.data).hexdigest() if i.packed_file else None,"path":i.filepath} for i in bpy.data.images if i.source!="VIEWER" and (i.users>0 or i.use_fake_user)},
        "material_graphs":{m.name:graph(m.node_tree,"material:"+m.name) for m in bpy.data.materials if m.name not in mutable_materials},
        "world":graph(scene.world.node_tree,"world:"+scene.world.name) if scene.world else None}
    if not allow_compositor: result["compositor"] = graph(scene.node_tree,"compositor:"+scene.name)
    result["material_settings"] = {m.name:{k:getattr(m,k) for k in ("surface_render_method","use_transparency_overlap","use_backface_culling","use_screen_refraction","pass_index") if hasattr(m,k)} for m in bpy.data.materials if m.name not in mutable_materials}
    result["graphs"] = trees
    return result

def execute(plan_path):
    import bpy
    plan_path=Path(plan_path).resolve(); plan=json.loads(plan_path.read_text("utf-8"));base=plan_path.parent
    source,paths=validate_plan(plan,base)
    bpy.ops.wm.open_mainfile(filepath=source["path"],load_ui=False,use_scripts=False)
    scene=bpy.context.scene
    if scene.render.engine!="BLENDER_EEVEE_NEXT": raise ValueError("Eevee saved source required; no engine conversion")
    cfg=plan.get("scene")
    mutable_materials=[]; mutable_lights=[]
    if "scene" in plan:
        from refine_scene import validate
        scope=validate(scene,cfg)
        mutable_materials=scope["materials"];mutable_lights=scope["lights"]
    names=set(o.name for o in scene.objects)
    guard=lambda:protected(bpy.context.scene,mutable_materials,mutable_lights,"compositor" in plan,names)
    before=guard()
    for p in paths.values(): p.parent.mkdir(parents=True,exist_ok=True)
    with Path(source["path"]).open("rb") as src, paths["backup"].open("xb") as dst: shutil.copyfileobj(src,dst)
    if sha(paths["backup"])!=source["sha256"]: raise ValueError("Backup hash differs")
    record={"schema":1,"accepted":False,"source":source,"backup":str(paths["backup"]),"backup_sha256":sha(paths["backup"]),"plan_sha256":sha(plan_path),"producer":producer_identity(Path(__file__).parent),"changes":{},"dynamic_validation":False}
    write_json(paths["report"],record)
    try:
        if "compositor" in plan:
            from refine_compositor import apply
            record["changes"]["compositor"]=apply(scene,plan["compositor"])
        if "scene" in plan:
            from refine_scene import apply
            record["changes"]["scene"]=apply(scene,cfg)
        if "samples" in plan: scene.eevee.taa_render_samples=plan["samples"]
        bpy.context.view_layer.update()
        if guard()!=before: raise ValueError("Protected source content changed before save")
        expected=protected(scene)
        bpy.ops.wm.save_as_mainfile(filepath=str(paths["output"]),check_existing=False,relative_remap=False)
        output_hash=sha(paths["output"])
        bpy.ops.wm.open_mainfile(filepath=str(paths["output"]),load_ui=False,use_scripts=False)
        after=guard()
        if after!=before:
            record["protected_before"]=before;record["protected_after"]=after
            raise ValueError("Protected source content differs after reopen: "+str([k for k in before if before[k]!=after.get(k)]))
        if protected(bpy.context.scene)!=expected: raise ValueError("Saved refinement data differs after reopen")
        if sha(source["path"])!=source["sha256"]: raise ValueError("Source changed")
        record.update(accepted=True,output=str(paths["output"]),output_sha256=output_hash,source_unchanged=True,reopened=True,protected_sha256=digest(before),protected_equal=True,saved_refinement_equal=True)
        write_json(paths["report"],record)
    except Exception as exc:
        record.update(error=type(exc).__name__+": "+str(exc));write_json(paths["report"],record);raise
    return record

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--plan",required=True)
    args=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else sys.argv[1:]
    a=parser.parse_args(args);print(json.dumps(execute(a.plan),ensure_ascii=False))
if __name__=="__main__": main()
