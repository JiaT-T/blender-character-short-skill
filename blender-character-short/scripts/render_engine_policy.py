"""Engine choice is independent of device choice. Existing projects are preserved."""

EEVEE = 'BLENDER_EEVEE_NEXT'
CYCLES = 'CYCLES'


class EnginePolicyError(ValueError):
    pass


def engine_plan(saved_engine=None, requested=None):
    """New scenes prefer Eevee. Existing scenes never undergo implicit conversion.

    A requested engine is an assertion, not a conversion flag. Conversion belongs
    in a separately reviewed copy with user agreement and material validation.
    """
    if saved_engine is None:
        chosen = requested or EEVEE
    else:
        chosen = saved_engine
        if requested is not None and saved_engine != requested:
            raise EnginePolicyError(f'Saved engine {saved_engine} differs from requested {requested}; no automatic engine/material conversion')
    if chosen not in (EEVEE, CYCLES):
        raise EnginePolicyError(f'Unsupported production engine: {chosen}')
    return chosen


def require_engine(scene, requested=None):
    return engine_plan(scene.render.engine, requested)


def apply_sampling(scene, samples, denoise=False):
    """Apply sampling only for the saved engine, never change that engine."""
    engine = require_engine(scene)
    if type(samples) is not int or samples < 1 or type(denoise) is not bool:
        raise EnginePolicyError('Positive integer samples and Boolean denoise required')
    if engine == EEVEE:
        scene.eevee.taa_render_samples = samples
        # Eevee temporal AA is not Cycles' OpenImageDenoise option.
        return {'engine': engine, 'samples': samples, 'denoise': False,
                'cycles_denoise_requested_but_not_applicable': denoise}
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.use_denoising = denoise
    if denoise:
        scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    return {'engine': engine, 'samples': samples, 'denoise': denoise}
