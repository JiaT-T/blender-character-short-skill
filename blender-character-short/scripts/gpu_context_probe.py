"""Initialize/read Blender's real GPU context through documented RenderEngine API.

This engine draws no geometry and makes no OpenGL/driver/security overrides.
The regular device guard still verifies the resulting actual renderer before
any Eevee scene rendering. Do not use synthetic hardware/device substitutions.
"""
def initialize_context():
    import bpy
    import gpu
    observed={}
    class LocalContextProbe(bpy.types.RenderEngine):
        bl_idname='LOCAL_CONTEXT_IDENTITY_PROBE'
        bl_label='Local GPU context identity probe'
        bl_use_gpu_context=True
        def render(self,depsgraph):
            try:
                observed.update(renderer=gpu.platform.renderer_get(),vendor=gpu.platform.vendor_get(),
                                backend=gpu.platform.backend_type_get(),version=gpu.platform.version_get(),
                                device_type=gpu.platform.device_type_get())
            except Exception as error:
                observed['error']=f'{type(error).__name__}: {error}'
            # A blank render result completes the operator; no geometry is drawn.
            result=self.begin_result(0,0,8,8)
            self.end_result(result)
    bpy.utils.register_class(LocalContextProbe)
    scene=bpy.data.scenes.new('Local device context probe')
    camera=bpy.data.objects.new('Local context camera',bpy.data.cameras.new('Local context camera'))
    scene.collection.objects.link(camera);scene.camera=camera
    scene.render.engine=LocalContextProbe.bl_idname
    scene.render.resolution_x=8;scene.render.resolution_y=8;scene.render.resolution_percentage=100
    scene.render.use_compositing=False
    try:
        status=bpy.ops.render.render(scene=scene.name,write_still=False)
        if 'FINISHED' not in status or 'error' in observed or not observed.get('renderer'):
            raise RuntimeError(f'GPU context identity probe failed: {status}, {observed}')
        # Read again outside the callback: identity must persist in this process.
        if gpu.platform.renderer_get()!=observed['renderer']:
            raise RuntimeError('GPU context identity changed after initialization')
        return observed
    finally:
        bpy.data.scenes.remove(scene)
        bpy.data.objects.remove(camera,do_unlink=True)
        bpy.utils.unregister_class(LocalContextProbe)
