"""Fail-closed render device selection; no preference file changes or CPU retry.

Windows inventory uses DXCore's IsIntegrated, never vendor/name heuristics.
Other platforms currently require an implemented, equally reliable inventory.
"""
import ctypes
import json
import re
import sys
import uuid

VERSION = 'discrete-first-integrated-only-cpu-v1'


class DevicePolicyError(RuntimeError):
    pass


def windows_adapters():
    """Read all DXCore GPU adapters (including software entries, then label them)."""
    if sys.platform != 'win32':
        raise DevicePolicyError('Reliable GPU hardware classification is not implemented on this platform')
    c = ctypes
    guid_type = c.c_ubyte * 16
    guid = lambda value: guid_type.from_buffer_copy(uuid.UUID(value).bytes_le)
    factory_iid = guid('78ee5945-c36e-4b13-a669-005dd11c0f06')
    list_iid = guid('526c7776-40e9-459b-b711-f32ad76dfc28')
    adapter_iid = guid('f0db4c7f-fe5a-42a2-bd62-f2a6cf6fc83e')
    gpu_attribute = guid('b69eb219-3ded-4464-979f-a00bd4687006')

    def method(obj, index, result, *arguments):
        table = c.cast(obj, c.POINTER(c.POINTER(c.c_void_p))).contents
        return c.WINFUNCTYPE(result, c.c_void_p, *arguments)(table[index])

    def check(hr, label):
        if hr < 0:
            raise DevicePolicyError(f'{label}: HRESULT 0x{hr & 0xffffffff:08x}')

    factory = c.c_void_p()
    listing = c.c_void_p()
    try:
        library = c.WinDLL('dxcore.dll')
        create = library.DXCoreCreateAdapterFactory
        create.argtypes = [c.c_void_p, c.POINTER(c.c_void_p)]
        create.restype = c.c_long
        check(create(c.byref(factory_iid), c.byref(factory)), 'DXCoreCreateAdapterFactory')
        check(method(factory, 3, c.c_long, c.c_uint32, c.c_void_p, c.c_void_p, c.POINTER(c.c_void_p))(
            factory, 1, c.byref(gpu_attribute), c.byref(list_iid), c.byref(listing)), 'DXCore GPU inventory')
        count = method(listing, 4, c.c_uint32)(listing)
        if count > 64:
            raise DevicePolicyError('Unexpected GPU inventory size')
        rows = []
        for index in range(count):
            adapter = c.c_void_p()
            try:
                check(method(listing, 3, c.c_long, c.c_uint32, c.c_void_p, c.POINTER(c.c_void_p))(
                    listing, index, c.byref(adapter_iid), c.byref(adapter)), 'GetAdapter')
                if not method(adapter, 3, c.c_bool)(adapter):
                    raise DevicePolicyError('GPU adapter is no longer valid')

                def property_value(prop, kind):
                    if not method(adapter, 5, c.c_bool, c.c_uint32)(adapter, prop):
                        raise DevicePolicyError(f'DXCore property {prop} unsupported; classification is unknown')
                    size = c.c_size_t()
                    check(method(adapter, 7, c.c_long, c.c_uint32, c.POINTER(c.c_size_t))(
                        adapter, prop, c.byref(size)), 'GetPropertySize')
                    if not 0 < size.value <= 65536:
                        raise DevicePolicyError('Invalid DXCore property size')
                    data = c.create_string_buffer(size.value)
                    check(method(adapter, 6, c.c_long, c.c_uint32, c.c_size_t, c.c_void_p)(
                        adapter, prop, size.value, data), 'GetProperty')
                    if kind == 'string':
                        return data.value.decode('utf-8', errors='strict')
                    if kind == 'bool':
                        if size.value != 1 or data.raw[0] not in (0, 1):
                            raise DevicePolicyError('Invalid DXCore Boolean property')
                        return bool(data.raw[0])
                    return int.from_bytes(data.raw, 'little')

                rows.append({'name': property_value(2, 'string'), 'hardware': property_value(11, 'bool'),
                             'integrated': property_value(12, 'bool'), 'luid': property_value(0, 'integer'),
                             'dedicated_bytes': property_value(7, 'integer'), 'provider': 'Windows DXCore IsIntegrated'})
            finally:
                if adapter.value:
                    method(adapter, 2, c.c_ulong)(adapter)
        if method(listing, 5, c.c_bool)(listing):
            raise DevicePolicyError('GPU inventory changed during discovery')
        return rows
    except (OSError, ValueError) as error:
        raise DevicePolicyError(f'GPU inventory unavailable: {error}') from error
    finally:
        if listing.value:
            method(listing, 2, c.c_ulong)(listing)
        if factory.value:
            method(factory, 2, c.c_ulong)(factory)


def hardware_mode(adapters):
    if not isinstance(adapters, list) or not adapters:
        raise DevicePolicyError('No reliable GPU hardware inventory; CPU fallback prohibited')
    for row in adapters:
        if not isinstance(row, dict) or type(row.get('hardware')) is not bool:
            raise DevicePolicyError('Unknown GPU hardware status')
        if row['hardware'] and (type(row.get('integrated')) is not bool or not row.get('name')):
            raise DevicePolicyError('Unknown integrated/discrete classification')
    hardware = [row for row in adapters if row['hardware']]
    if not hardware:
        raise DevicePolicyError('Software adapters alone do not establish integrated-only hardware')
    return 'GPU' if any(not row['integrated'] for row in hardware) else 'CPU'


def normalized_name(name):
    return re.sub(r'[^a-z0-9]', '', name.lower().replace('(tm)', '').replace('(r)', ''))


def matching_discrete(name, adapters):
    matches = [row for row in adapters if row['hardware'] and not row['integrated']
               and normalized_name(row['name']) == normalized_name(name)]
    if len(matches) != 1:
        raise DevicePolicyError(f'Cannot uniquely match active render device to discrete hardware: {name}')
    return matches[0]


def configure_cycles(scene, preferences, adapters):
    """Pure dependency injection supports failure tests; callers supply real Blender RNA."""
    mode = hardware_mode(adapters)
    if mode == 'CPU':
        scene.cycles.device = 'CPU'
        for device in preferences.devices:
            device.use = device.type == 'CPU'
        return {'mode': 'CPU', 'reason': 'All discovered hardware GPUs positively identified as integrated',
                'devices': [], 'backend': 'CPU'}
    failures = []
    # All attempts remain GPU-only. Unsupported enum values / drivers are recorded.
    for backend in ('OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL'):
        try:
            preferences.compute_device_type = backend
            preferences.refresh_devices()
            selected = []
            for device in preferences.devices:
                device.use = False
                if device.type != backend:
                    continue
                try:
                    matching_discrete(device.name, adapters)
                except DevicePolicyError:
                    continue
                selected.append(device)
            if not selected:
                failures.append(f'{backend}: no unambiguously matched discrete Cycles device')
                continue
            # One GPU per render; avoid taking every board on a shared machine.
            selected[0].use = True
            scene.cycles.device = 'GPU'
            if scene.cycles.device != 'GPU' or not selected[0].use or any(
                device.use for device in preferences.devices if device != selected[0]
            ):
                raise DevicePolicyError('Cycles GPU-only settings did not take effect')
            return {'mode': 'GPU', 'backend': backend,
                    'devices': [{'name': selected[0].name, 'id': selected[0].id, 'type': selected[0].type}],
                    'backend_attempts': failures}
        except Exception as error:
            failures.append(f'{backend}: {type(error).__name__}: {error}')
    raise DevicePolicyError('Discrete GPU exists but no compatible Cycles GPU is available; CPU fallback prohibited. '
                            + ' | '.join(failures))


def configure_graphics(engine, renderer, adapters):
    if hardware_mode(adapters) == 'CPU':
        raise DevicePolicyError(f'{engine} has no CPU render mode. Use a reviewed Cycles-compatible project on integrated-only hardware; engine/material conversion is not automatic')
    if not isinstance(renderer, str) or not renderer.strip():
        raise DevicePolicyError('Active graphics renderer cannot be identified')
    # OpenGL adds a /PCIe/SSE2 suffix. Do not use a broad substring match.
    matched = matching_discrete(renderer.split('/', 1)[0].strip(), adapters)
    return {'mode': 'GPU', 'backend': 'graphics context', 'devices': [{'name': matched['name']}],
            'active_graphics_renderer': renderer}


def graphics_identity(bpy_module, gpu_module, adapters, initializer):
    """Handle lazy background initialization without guessing the active GPU.

    Only a known single discrete hardware adapter permits this bounded context
    probe. Always query and match the *real* context again after initialization.
    Multi-GPU and integrated-only systems do not take this recovery route.
    """
    try:
        return gpu_module.platform.renderer_get(), None
    except SystemError as error:
        hardware = [row for row in adapters if row.get('hardware') is True]
        if (not bpy_module.app.background or
            'GPU functions for drawing are not available in background mode' not in str(error) or
            hardware_mode(adapters) != 'GPU' or len(hardware) != 1):
            raise DevicePolicyError(f'Cannot verify actual graphics device: {error}') from error
        try:
            proof = initializer()
            renderer = gpu_module.platform.renderer_get()
            matching_discrete(renderer.split('/', 1)[0].strip(), adapters)
            if proof.get('renderer') != renderer:
                raise DevicePolicyError('GPU identity differs between initialization and guard')
            return renderer, proof
        except Exception as failure:
            raise DevicePolicyError(f'Background GPU context initialization/identity failed: {failure}') from failure
    except Exception as error:
        raise DevicePolicyError(f'Cannot verify actual graphics device: {error}') from error


_CACHE = {}


def prepare_render(scene=None):
    import bpy
    scene = scene or bpy.context.scene
    engine = scene.render.engine
    # Reconfigure after every file load / settings change. Inventory is readonly.
    adapters = windows_adapters()
    if engine == 'CYCLES':
        preferences = bpy.context.preferences.addons['cycles'].preferences
        result = configure_cycles(scene, preferences, adapters)
    elif engine in ('BLENDER_EEVEE_NEXT', 'BLENDER_WORKBENCH'):
        import gpu
        from gpu_context_probe import initialize_context
        renderer, context_proof = graphics_identity(bpy, gpu, adapters, initialize_context)
        result = configure_graphics(engine, renderer, adapters)
        if context_proof is not None:
            result['context_initialization'] = context_proof
    else:
        raise DevicePolicyError(f'Unimplemented renderer device policy: {engine}')
    result.update(policy=VERSION, engine=engine, adapters=adapters, render_completed=False)
    scene['render_device_policy'] = json.dumps(result, ensure_ascii=True, sort_keys=True)
    _CACHE[(scene.as_pointer(), bpy.data.filepath)] = result
    print('RENDER_DEVICE_POLICY', json.dumps(result, ensure_ascii=True, sort_keys=True), flush=True)
    return result


def render_with_policy(**kwargs):
    """Every actual render checks GPU-only settings; exceptions never retry on CPU."""
    import bpy
    scene = bpy.context.scene
    result = _CACHE.get((scene.as_pointer(), bpy.data.filepath))
    if result is None or result['engine'] != scene.render.engine:
        result = prepare_render(scene)
    if scene.render.engine == 'CYCLES':
        preferences = bpy.context.preferences.addons['cycles'].preferences
        selected = [{'name': d.name, 'id': d.id, 'type': d.type} for d in preferences.devices if d.use and d.type != 'CPU']
        if (scene.cycles.device != result['mode'] or
            (result['mode'] == 'GPU' and (preferences.compute_device_type != result['backend'] or
             selected != result['devices'] or any(d.use and d.type == 'CPU' for d in preferences.devices)))):
            raise DevicePolicyError('Render device configuration changed; refusing implicit CPU rendering')
    else:
        import gpu
        if configure_graphics(scene.render.engine, gpu.platform.renderer_get(), result['adapters'])['devices'] != result['devices']:
            raise DevicePolicyError('Graphics render device changed')
    try:
        status = bpy.ops.render.render(**kwargs)
        if 'FINISHED' not in status:
            raise DevicePolicyError(f'Render operator did not finish: {status}')
        return status
    except Exception as error:
        raise DevicePolicyError(f'{result["mode"]} render failed ({result["backend"]}); no CPU retry: {error}') from error


if __name__ == '__main__':
    print(json.dumps({'policy': VERSION, 'adapters': windows_adapters()}, indent=2))
