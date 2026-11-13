"""Verify and enable explicitly declared installed addons in this process only."""
from collections.abc import Mapping
import importlib
import json
import os
from pathlib import Path
import re
import tomllib

ENVIRONMENT_KEY = 'BLENDER_SHORT_RUNTIME_ADDONS'
MMD_MODULE = re.compile(r'(?:mmd_tools|bl_ext\.[A-Za-z_][A-Za-z0-9_]*\.mmd_tools)\Z')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate project/runtime key: ' + key)
        result[key] = value
    return result


def load_project(path):
    """Do not lose duplicate runtime addon declarations before validation."""
    return json.loads(Path(path).read_text('utf-8'), object_pairs_hook=unique_object)


def version_tuple(value, label):
    if (not isinstance(value, (list, tuple)) or len(value) != 3 or
            any(type(part) is not int or not 0 <= part <= 9999 for part in value)):
        raise ValueError('Explicit three-integer version required: ' + label)
    return tuple(value)


def string_version(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', value):
        raise ValueError('Invalid installed version metadata: ' + label)
    return version_tuple(tuple(int(part) for part in value.split('.')), label)


def validate_addons(addons):
    if not isinstance(addons, Mapping):
        raise ValueError('runtime.addons must be a module-to-version mapping')
    result = {}
    mmd_seen = False
    for module, version in addons.items():
        if not isinstance(module, str) or (module != 'MikuMikuRig' and not MMD_MODULE.fullmatch(module)):
            raise ValueError('Unsupported runtime addon module: ' + repr(module))
        is_mmd = module != 'MikuMikuRig'
        if module in result or (is_mmd and mmd_seen):
            raise ValueError('Duplicate runtime addon or MMD Tools aliases')
        result[module] = list(version_tuple(version, module))
        mmd_seen = mmd_seen or is_mmd
    return result


def runtime_spec(runtime):
    if not isinstance(runtime, Mapping) or 'addons' not in runtime or 'blender_version' not in runtime:
        raise ValueError('Declared runtime Blender/addon versions required')
    return {'blender_version': list(version_tuple(runtime['blender_version'], 'Blender')),
            'addons': validate_addons(runtime['addons'])}


def installed_version(module_name, module):
    """Use native imported metadata, never an installer or external code string."""
    versions = []
    info = getattr(module, 'bl_info', None)
    if info:
        if not isinstance(info, Mapping) or 'version' not in info:
            raise ValueError('Invalid installed bl_info: ' + module_name)
        versions.append(version_tuple(info['version'], module_name))
    filename = getattr(module, '__file__', None)
    if not filename or not Path(filename).is_file():
        raise ValueError('Installed addon module file missing: ' + module_name)
    manifest = Path(filename).parent / 'blender_manifest.toml'
    if manifest.is_file():
        metadata = tomllib.loads(manifest.read_text('utf-8'))
        versions.append(string_version(metadata.get('version'), module_name))
    if not versions and module_name == 'MikuMikuRig':
        nested = importlib.import_module('MikuMikuRig.addons.MikuMikuRig')
        info = getattr(nested, 'bl_info', None)
        if not isinstance(info, Mapping) or 'version' not in info:
            raise ValueError('Installed MikuMikuRig version metadata missing')
        versions.append(version_tuple(info['version'], module_name))
    if not versions or any(value != versions[0] for value in versions):
        raise ValueError('Installed addon version metadata missing or inconsistent: ' + module_name)
    legacy = getattr(module, 'MMD_TOOLS_VERSION', None)
    if module_name != 'MikuMikuRig' and legacy is not None and string_version(legacy, module_name) != versions[0]:
        raise ValueError('MMD_TOOLS_VERSION differs from installed addon metadata: ' + module_name)
    return versions[0]


def initialize(runtime, bpy_module=None):
    """Preflight all declarations, then enable only missing allowed addons."""
    spec = runtime_spec(runtime)
    if bpy_module is None:
        import bpy as bpy_module
    if not bpy_module.app.background:
        raise ValueError('Runtime addon initialization requires background Blender')
    if list(bpy_module.app.version) != spec['blender_version']:
        raise ValueError('Blender version differs from reviewed runtime')
    installed = {}
    for name, expected in spec['addons'].items():
        try:
            module = importlib.import_module(name)
        except ImportError as exc:
            raise ValueError('Declared installed addon unavailable: ' + name) from exc
        if list(installed_version(name, module)) != expected:
            raise ValueError('Installed addon version differs from reviewed runtime: ' + name)
        installed[name] = module
    result = {}
    for name, module in installed.items():
        enabled_now = not bool(bpy_module.context.preferences.addons.get(name))
        if enabled_now and bpy_module.ops.preferences.addon_enable(module=name) != {'FINISHED'}:
            raise ValueError('Runtime addon activation did not finish: ' + name)
        if (not bpy_module.context.preferences.addons.get(name) or
                list(installed_version(name, module)) != spec['addons'][name]):
            raise ValueError('Reviewed addon not enabled at declared version: ' + name)
        result[name] = {'version': spec['addons'][name], 'file': str(module.__file__),
                        'enabled_in_this_process': True, 'enabled_now': enabled_now}
    return {'blender_version': spec['blender_version'], 'addons': result,
            'preferences_saved': False, 'process_only': True}


def main():
    payload = os.environ.get(ENVIRONMENT_KEY)
    if payload is None:
        raise ValueError('Declared runtime addon bootstrap payload missing')
    runtime = json.loads(payload, object_pairs_hook=unique_object)
    print('RUNTIME_ADDONS_READY ' + json.dumps(initialize(runtime), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
