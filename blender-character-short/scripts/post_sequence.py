"""Composite numbered raw NPZs, optionally preserving source SMAA edge history.

Default image math is unchanged source_post. SMAA is opt-in using paired external
lookup paths. First requested frame has an explicit fresh zero edge target;
subsequent frames use previous edges, including across resume. GPU equivalence
remains pending. One writer per output folder is required.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image
import source_post


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return sha_bytes(Path(path).read_bytes())


def canonical_hash(value):
    return sha_bytes(json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8'))


def atomic_json(path, data):
    temporary = path.with_name(path.name+'.partial')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def valid_png(path, size):
    try:
        with Image.open(path) as image:
            if image.size != size or image.mode != 'RGBA':
                return False
            image.verify()
        with Image.open(path) as image:
            image.load()
        return True
    except Exception:
        return False


def state_hash(edges):
    return sha_bytes(np.ascontiguousarray(edges, dtype='<f4').tobytes())


def load_checkpoint(checkpoint, dest, edge_path, size, raw_sha, job_sha, previous_state_sha, smaa):
    """Only a matching complete PNG + state + predecessor chain may be reused."""
    try:
        record = json.loads(checkpoint.read_text(encoding='utf-8'))
        if record['raw_sha256'] != raw_sha or record['job_sha256'] != job_sha:
            return None, None, 'input-or-job-changed'
        if record['previous_edge_state_sha256'] != previous_state_sha:
            return None, None, 'history-predecessor-changed'
        if not valid_png(dest, size) or record['png_sha256'] != sha(dest):
            return None, None, 'png-missing-corrupt-or-changed'
        edges = None
        if smaa:
            if record['edge_file_sha256'] != sha(edge_path):
                return None, None, 'edge-file-missing-corrupt-or-changed'
            with np.load(edge_path, allow_pickle=False) as data:
                edges = np.asarray(data['edges'], dtype=np.float32)
            if edges.shape != (size[1], size[0], 4) or not np.isfinite(edges).all():
                return None, None, 'edge-shape-or-values-invalid'
            if state_hash(edges) != record['edge_state_sha256']:
                return None, None, 'edge-state-hash-mismatch'
        return record, edges, 'validated-checkpoint'
    except Exception as exc:
        return None, None, 'checkpoint-incomplete:'+type(exc).__name__


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--lut', required=True, type=Path)
    parser.add_argument('--start', type=int, default=1)
    parser.add_argument('--end', type=int, required=True)
    parser.add_argument('--smaa-area', type=Path)
    parser.add_argument('--smaa-search', type=Path)
    args = parser.parse_args()
    if bool(args.smaa_area) != bool(args.smaa_search):
        parser.error('--smaa-area and --smaa-search must be supplied together')
    if args.start < 1 or args.end < args.start:
        parser.error('Require 1 <= start <= end')
    smaa_enabled = args.smaa_area is not None
    smaa = None
    if smaa_enabled:
        import smaa_cpu as smaa
        smaa.load_tables(args.smaa_area, args.smaa_search)  # dimensions/readability before writes
    config = json.loads(args.config.read_text(encoding='utf-8'))
    lut = np.asarray(Image.open(args.lut).convert('RGB'), dtype=np.float32)/255
    signature = {
        'schema': 2,
        'post_config_sha256': sha(args.config), 'lut_sha256': sha(args.lut),
        'raw_job_sha256': sha(args.raw/'render-job.json'),
        'post_sequence_sha256': sha(__file__), 'source_post_sha256': sha(source_post.__file__),
        'frame_range': [args.start, args.end],
        'mode': 'source-smaa-history-v1' if smaa_enabled else 'source-post-no-aa',
        'smaa': None,
    }
    if smaa_enabled:
        signature['smaa'] = {
            'script_sha256': sha(smaa.__file__),
            'area_sha256': sha(args.smaa_area), 'search_sha256': sha(args.smaa_search),
            'initial_edge_state': 'fresh-zero-at-first-requested-frame',
            'initial_frame': args.start, 'continuation': 'previous-frame-edges-no-clear',
            'checkpoint_orientation': 'top-down', 'checkpoint_dtype': 'float16-lossless-for-half-target',
            'gpu_numerical_acceptance': 'pending',
        }
    job_sha = canonical_hash(signature)
    output = args.output
    manifest = output/'post-job.json'
    if manifest.exists():
        if json.loads(manifest.read_text(encoding='utf-8')) != signature:
            raise ValueError('Post output inputs/config/scripts/range/AA mode changed; preserve it and choose a new version')
    elif output.exists() and any(output.iterdir()):
        raise ValueError('Nonempty output has no matching post-job.json; choose a new version')
    # Detect raw holes before changing output. Non-numbered recovery backups are ignored.
    missing = [n for n in range(args.start, args.end+1) if not (args.raw/f'frame_{n:04}.npz').is_file()]
    if missing:
        raise FileNotFoundError(f'Raw sequence has holes: {missing}')
    output.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = output/'checkpoints'; checkpoint_dir.mkdir(exist_ok=True)
    edge_dir = output/'edges'
    if smaa_enabled:
        edge_dir.mkdir(exist_ok=True)
    atomic_json(manifest, signature)
    started = time.monotonic()
    events = []
    previous = None
    previous_state_sha = None
    previous_size = None
    try:
        for frame in range(args.start, args.end+1):
            tick = time.monotonic()
            src = args.raw/f'frame_{frame:04}.npz'
            dest = output/f'frame_{frame:04}.png'
            edge_path = edge_dir/f'frame_{frame:04}.npz'
            checkpoint = checkpoint_dir/f'frame_{frame:04}.json'
            # Hash and decode the same immutable bytes, not separate reads.
            payload = src.read_bytes(); raw_sha = sha_bytes(payload)
            with np.load(io.BytesIO(payload), allow_pickle=False) as data:
                rgba = data['rgba']; weight = data['weight']
            if rgba.ndim != 3 or rgba.shape[-1] != 4:
                raise ValueError('Raw rgba must be HxWx4: '+str(src))
            size = (rgba.shape[1], rgba.shape[0])
            if previous_size is not None and size != previous_size:
                raise ValueError('Sequence dimensions changed; refusing implicit SMAA history reset')
            previous_size = size
            record, resumed_edge, reason = load_checkpoint(
                checkpoint, dest, edge_path, size, raw_sha, job_sha,
                previous_state_sha, smaa_enabled)
            if record is not None:
                if smaa_enabled:
                    previous = resumed_edge
                    previous_state_sha = record['edge_state_sha256']
                event = {'frame': frame, 'status': 'existing-validated', 'seconds': time.monotonic()-tick}
            else:
                stages = source_post.process(rgba, weight, lut, config)
                next_edges = None
                if smaa_enabled:
                    aa = smaa.process(stages['web_premultiplied'][::-1], args.smaa_area, args.smaa_search,
                                      previous_edges=previous)
                    web = aa['output']
                    coverage = web[..., 3:4]
                    rgb = web[..., :3]/np.maximum(coverage, np.float32(1e-4))
                    rgb = np.where(coverage > 0, rgb, 0)
                    display = np.concatenate([np.clip(rgb, 0, 1), coverage], axis=2)
                    next_edges = aa['edges']
                else:
                    display = stages['display_rgba'][::-1]
                temporary = dest.with_name(dest.stem+'.partial.png')
                Image.fromarray(np.uint8(np.rint(display*255)), 'RGBA').save(temporary)
                if not valid_png(temporary, size):
                    raise RuntimeError('Invalid newly composited PNG '+str(temporary))
                temporary.replace(dest)
                record = {
                    'frame': frame, 'raw_sha256': raw_sha, 'job_sha256': job_sha,
                    'size': list(size), 'png_sha256': sha(dest),
                    'previous_edge_state_sha256': previous_state_sha,
                    'edge_file_sha256': None, 'edge_state_sha256': None,
                }
                if smaa_enabled:
                    temporary_edge = edge_path.with_name(edge_path.stem+'.partial.npz')
                    np.savez_compressed(temporary_edge, edges=next_edges.astype(np.float16))
                    # Verify checkpoint content before committing its record.
                    with np.load(temporary_edge, allow_pickle=False) as data:
                        verified = data['edges'].astype(np.float32)
                    if not np.array_equal(verified, next_edges):
                        raise RuntimeError('Edge checkpoint did not round-trip exactly')
                    temporary_edge.replace(edge_path)
                    record['edge_file_sha256'] = sha(edge_path)
                    record['edge_state_sha256'] = state_hash(next_edges)
                    previous = next_edges
                    previous_state_sha = record['edge_state_sha256']
                # Last commit: interruption before this leaves an untrusted frame,
                # which is recomputed rather than trusting PNG or state alone.
                atomic_json(checkpoint, record)
                event = {'frame': frame, 'status': 'composited', 'reason': reason,
                         'seconds': time.monotonic()-tick}
            events.append(event)
            atomic_json(output/'post-progress.json', {
                'status': 'running', 'last_frame': frame, 'range': [args.start, args.end],
                'records': events, 'elapsed': time.monotonic()-started, 'job_sha256': job_sha,
            })
            if frame % 24 == 0:
                print('POST_CHECKPOINT', frame, 'elapsed', round(time.monotonic()-started, 1), flush=True)
        atomic_json(output/'post-progress.json', {
            'status': 'complete', 'range': [args.start, args.end], 'records': events,
            'elapsed': time.monotonic()-started, 'job_sha256': job_sha,
            'smaa_gpu_numerical_acceptance': 'pending' if smaa_enabled else 'not-applicable',
        })
        print('POST_SEQUENCE_DONE', args.end-args.start+1, flush=True)
    except BaseException as exc:
        atomic_json(output/'post-progress.json', {
            'status': 'interrupted' if isinstance(exc, (KeyboardInterrupt, SystemExit)) else 'failed',
            'range': [args.start, args.end], 'records': events, 'elapsed': time.monotonic()-started,
            'error': type(exc).__name__+': '+str(exc), 'job_sha256': job_sha,
            'resume': 'Repeat the exact same command. Every PNG and edge/predecessor checkpoint is validated.',
        })
        raise


if __name__ == '__main__':
    main()
