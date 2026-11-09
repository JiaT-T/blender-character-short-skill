"""Defaults for newly authored videos; never retime an existing saved scene."""
DEFAULT_WIDTH=1280
DEFAULT_HEIGHT=720
DEFAULT_FPS=24

def new_video_settings(overrides=None):
    result={'width':DEFAULT_WIDTH,'height':DEFAULT_HEIGHT,'fps':DEFAULT_FPS}
    result.update(overrides or {})
    if any(type(result[k]) is not int or result[k]<=0 for k in ['width','height','fps']):
        raise ValueError('New-video dimensions and fps must be positive integers')
    return result

def saved_render_dimensions(job):
    # fps is deliberately absent: the actual saved fps/fps_base remains authoritative.
    return job.get('width',DEFAULT_WIDTH),job.get('height',DEFAULT_HEIGHT)
