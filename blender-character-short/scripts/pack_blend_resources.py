"""Pack reviewed local character dependencies before relocating a blend copy.

Open the input at its real original location. Missing dependencies fail instead
of guessing another directory. Preserve input/asset bytes and save a new file.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,sys
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from body_motion_runtime import character_rig,geometry_identity

def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['blend','output','report']:p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--expected-sha256',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if not bpy.app.background:raise ValueError('Use an isolated background process')
    paths=[v.resolve() for v in [a.blend,a.output,a.report]]
    if len(set(paths))!=3 or a.blend.suffix.lower()!='.blend' or a.output.suffix.lower()!='.blend' or a.report.suffix.lower()!='.json' or a.output.exists() or a.report.exists():raise ValueError('Reviewed original input and distinct new blend/report required')
    if str(paths[0]).startswith(('\\\\','//')) or a.blend.stat().st_size>512*1024*1024:raise ValueError('Bounded local original blend required')
    if len(a.expected_sha256)!=64 or any(c not in '0123456789abcdef' for c in a.expected_sha256) or sha(a.blend)!=a.expected_sha256:raise ValueError('Original input identity mismatch')
    bpy.ops.wm.open_mainfile(filepath=str(paths[0]),load_ui=False,use_scripts=False)
    if bpy.data.libraries:raise ValueError('Linked libraries need a separately reviewed dependency workflow')
    arm,_=character_rig(bpy.context.scene);geometry=geometry_identity(bpy.context.scene,arm);assets=[];total=0
    for image in bpy.data.images:
        if image.source in ['GENERATED','VIEWER']:continue
        if image.source!='FILE':raise ValueError('Only local file or generated images supported: '+image.name)
        row={'image':image.name,'already_packed':bool(image.packed_file)}
        if not image.packed_file:
            raw=bpy.path.abspath(image.filepath)
            if raw.startswith(('\\\\','//')) or '://' in raw:raise ValueError('Network image dependencies are outside this route')
            path=Path(raw).resolve()
            if not path.is_file():raise ValueError('Missing original image dependency; open/pack before relocation: '+str(path))
            size=path.stat().st_size;total+=size
            if size>256*1024*1024 or total>1024*1024*1024:raise ValueError('Image dependency work budget exceeded')
            row.update(original_file=str(path),source_bytes=size,source_sha256=sha(path))
        assets.append(row)
    if 'FINISHED' not in bpy.ops.file.pack_all():raise RuntimeError('Blender dependency packing did not finish')
    if any(i.source=='FILE' and not i.packed_file for i in bpy.data.images):raise ValueError('A file image remains unpacked')
    a.output.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(paths[1]),check_existing=False)
    bpy.ops.wm.open_mainfile(filepath=str(paths[1]),load_ui=False,use_scripts=False);arm,_=character_rig(bpy.context.scene)
    if geometry_identity(bpy.context.scene,arm)!=geometry or any(i.source=='FILE' and not i.packed_file for i in bpy.data.images):raise ValueError('Packed copy did not survive fresh reopen with identical original rest/skin')
    if sha(a.blend)!=a.expected_sha256 or any(sha(row['original_file'])!=row['source_sha256'] for row in assets if 'original_file' in row):raise ValueError('An original blend or image changed')
    result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'local-image-dependencies-packed-copy-reopened','input_sha256':a.expected_sha256,'output':str(paths[1]),'output_sha256':sha(a.output),'writer_sha256':sha(Path(__file__)),'original_geometry_identity':geometry,'file_image_count':len(assets),'all_file_images_packed_after_reopen':True,'input_and_original_image_bytes_unchanged':True,'dependencies':assets,'scope':'One reviewed local character, local image dependencies packed at original source location into a new copy. No automatic missing-path search, linked-library/movie/sequence support, permission change, upload or redistribution rights granted.'}
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='dependencies'},ensure_ascii=True))

if __name__=='__main__':main()
