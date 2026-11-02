"""Read-only identity for the external blueprint files the builder actually opens."""
import hashlib
import json
from pathlib import Path


def collect_blueprint_inputs(character_path):
    character = json.loads(Path(character_path).read_text(encoding='utf-8'))
    settings = character.get('materials', {})
    if not isinstance(settings, dict):
        raise ValueError('Character materials must be an object')
    source = settings.get('dorm_blueprint')
    if not source:
        return None
    if not isinstance(source, str):
        raise ValueError('dorm_blueprint must name a local file')
    # Match build_shader_blueprint: the blueprint path is relative to cwd,
    # and each declared image is relative to the blueprint's parent directory.
    path = Path(source).resolve(strict=True)
    raw = path.read_bytes()
    spec = json.loads(raw.decode('utf-8'))
    images = spec.get('images')
    if not isinstance(images, dict):
        raise ValueError('Blueprint images must be an object')
    result = {'blueprint': {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}, 'images': {}}
    for name, record in sorted(images.items()):
        if not isinstance(record, dict) or not isinstance(record.get('file'), str) or not record['file']:
            raise ValueError('Blueprint image requires a local file: '+str(name))
        image = (path.parent / record['file']).resolve(strict=True)
        result['images'][name] = {'path': str(image), 'sha256': hashlib.sha256(image.read_bytes()).hexdigest()}
    return result
