"""Report matching Blender/addons without changing preferences or opening UI."""
from pathlib import Path
import argparse,json,sys,importlib,tomllib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from production_contract import write_json,digest,sha
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',required=True);p.add_argument('--report',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);project=json.loads(Path(a.project).read_text('utf-8'));wanted=project['runtime'];addons={}
    if list(bpy.app.version)!=wanted['blender_version']:raise ValueError('Blender version differs from reviewed project')
    for name,version in wanted['addons'].items():
        if name not in bpy.context.preferences.addons:raise ValueError('Required addon is not enabled: '+name)
        module=importlib.import_module(name)
        info=getattr(module,'bl_info',{})
        if not info and name=='MikuMikuRig':info=importlib.import_module('MikuMikuRig.addons.MikuMikuRig').bl_info
        actual=list(info.get('version',()))
        manifest=Path(module.__file__).parent/'blender_manifest.toml'
        if not actual and manifest.is_file():actual=[int(x) for x in tomllib.loads(manifest.read_text('utf-8'))['version'].split('.')]
        if actual!=version:raise ValueError('Addon version differs: '+name+' '+repr(actual))
        addons[name]={'version':actual,'file':str(module.__file__)}
    write_json(a.report,{'accepted':True,'blender':bpy.app.version_string,'blender_python':sys.version,'blender_numpy':np.__version__,'binary':bpy.app.binary_path,'binary_sha256':sha(bpy.app.binary_path),'runtime_spec_sha256':digest(wanted),'background':bpy.app.background,'addons':addons,'ui_used':False,'preferences_saved':False})
if __name__=='__main__':main()
