"""Project-local PMX import for Blender 4.5 + maintained mmd_tools 4.5.14."""
import argparse,json,pathlib,re,sys,zipfile
import bpy
p=argparse.ArgumentParser();p.add_argument('--asset',required=True);p.add_argument('--addon-source',required=True);p.add_argument('--dependency-dir',required=True);p.add_argument('--output',required=True);p.add_argument('--report',required=True);p.add_argument('--scale',type=float,default=.08)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);addon=pathlib.Path(a.addon_source).resolve();dep=pathlib.Path(a.dependency_dir).resolve();asset=pathlib.Path(a.asset).resolve();dest=pathlib.Path(a.output).resolve()
if asset.suffix.lower()!='.pmx' or not asset.is_file():raise FileNotFoundError('PMX asset is missing or has the wrong extension: '+str(asset))
if not (addon/'mmd_tools/__init__.py').is_file():raise FileNotFoundError('mmd_tools source directory is invalid: '+str(addon))
if dest.exists():raise FileExistsError('Imported baseline already exists; choose a new version: '+str(dest))
pathlib.Path(a.report).parent.mkdir(parents=True,exist_ok=True)
dep.mkdir(parents=True,exist_ok=True);dest.parent.mkdir(parents=True,exist_ok=True)
for wheel in (addon/'mmd_tools/wheels').glob('*.whl'):
    with zipfile.ZipFile(wheel) as z:
        for entry in z.infolist():
            target=(dep/entry.filename).resolve()
            if not target.is_relative_to(dep):raise ValueError('Wheel member escapes dependency directory')
        z.extractall(dep)
sys.path[:0]=[str(addon),str(dep)]
import mmd_tools
mmd_tools.register()
for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
bpy.ops.mmd_tools.import_model(filepath=str(asset),scale=a.scale,types={'MESH','ARMATURE','MORPHS','DISPLAY'},clean_model=False,remove_doubles=False,rename_bones=False)
toon=addon/'mmd_tools/externals/MikuMikuDance';repaired=[]
for im in bpy.data.images:
    if im.source=='FILE' and not im.packed_file and not pathlib.Path(bpy.path.abspath(im.filepath)).exists():
        name=pathlib.Path(im.filepath).name
        if re.fullmatch(r'toon\d{2}\.bmp',name,re.I) and (toon/name).is_file():
            im.filepath=str(toon/name);im.reload();repaired.append(name)
images=[{'name':i.name,'path':i.filepath,'loaded':i.size[0]>0,'exists':bool(i.packed_file) or pathlib.Path(bpy.path.abspath(i.filepath)).exists()} for i in bpy.data.images if i.source=='FILE' and i.users]
report={'blender':bpy.app.version_string,'mmd_tools':mmd_tools.MMD_TOOLS_VERSION,'input':str(asset),'output':str(dest),'scale':a.scale,'physics_imported':False,'shared_toons_repaired':repaired,'images':images,'armatures':[{'name':o.name,'bones':len(o.data.bones)} for o in bpy.data.objects if o.type=='ARMATURE'],'meshes':[{'name':o.name,'vertices':len(o.data.vertices),'uv_layers':list(o.data.uv_layers.keys()),'shape_keys':len(o.data.shape_keys.key_blocks) if o.data.shape_keys else 0,'armature_modifiers':sum(m.type=='ARMATURE' for m in o.modifiers)} for o in bpy.data.objects if o.type=='MESH']}
pathlib.Path(a.report).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if any(not i['exists'] or not i['loaded'] for i in images):raise RuntimeError('Missing/unloaded used image; inspect report before material work')
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(dest));print('IMPORTED',dest,report['armatures'],report['meshes'])
