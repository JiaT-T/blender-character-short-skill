"""Persistent, local-only job adapter for the reviewed short_project stages.

No arbitrary commands, sockets, process killing, stage retries or installs.
Cancellation is cooperative between stages/render batches. Uncertain jobs retain
project reservations until an operator verifies their descendants and outputs.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import secrets
import threading
import time

SCRIPTS = Path(__file__).resolve().parent
STAGES = frozenset(('doctor', 'baseline', 'look', 'build', 'render', 'encode',
                    'tests', 'check-look', 'diagnostic', 'refine', 'workflow', 'physics'))
TERMINAL = frozenset(('completed', 'failed', 'cancelled'))
KEY = re.compile(r'^[A-Za-z0-9_-]{1,80}$')
# One fsynced metadata temp, at most six replacement attempts, 0.31 s backoff.
METADATA_REPLACE_DELAYS = (.01, .02, .04, .08, .16)


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text('utf-8'))


def write(path, data):
    path = Path(path)
    tmp = path.with_name(path.name + '.tmp-' + secrets.token_hex(8))
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    for attempt in range(len(METADATA_REPLACE_DELAYS) + 1):
        try:
            os.replace(tmp, path)
            return
        except OSError as exc:
            if os.name != 'nt' or getattr(exc, 'winerror', None) not in (5, 32, 33):
                raise
            retry = attempt < len(METADATA_REPLACE_DELAYS)
            delay = METADATA_REPLACE_DELAYS[attempt] if retry else 0
            try:
                sys.stderr.write(json.dumps(dict(event='metadata_replace_retry' if retry else 'metadata_replace_failed',
                                                 path=str(path), attempt=attempt + 1,
                                                 max_attempts=len(METADATA_REPLACE_DELAYS) + 1,
                                                 winerror=exc.winerror, delay_seconds=delay)) + '\n')
                sys.stderr.flush()
            except Exception:
                pass  # Diagnostics cannot replace the original publication error.
            if not retry:
                raise
            time.sleep(delay)


@contextmanager
def mutex(path):
    """Kernel lock: never unlink the lock inode or recover by guessing a PID."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        if path.stat().st_size == 0:
            handle.write(b'0'); handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def under(path, root):
    return path == root or root in path.parents


def producer(scripts):
    return {p.name: sha(p) for p in sorted(scripts.glob('*.py'))}


def input_snapshot(project):
    """Derive plans, lock resource and project hash from the same project bytes."""
    raw = project.read_bytes()
    p = json.loads(raw.decode('utf-8'))
    bound = {str(project): hashlib.sha256(raw).hexdigest()}
    paths = []
    for key in ('baseline_plan', 'refine_plan', 'workflow_brief'):
        if key in p:
            path = (project.parent / p[key]).resolve()
            if not path.is_file():
                raise ValueError('Declared plan is missing: ' + str(path))
            paths.append(path)
    if 'physics' in p:
        paths.append((project.parent / p['physics']['plan']).resolve(strict=True))
    bound.update({str(path): sha(path) for path in paths})
    return p, bound


def inputs(project):
    """Bind the mutable project and canonical external plan files at submission."""
    return input_snapshot(Path(project))[1]


class Jobs:
    def __init__(self, config, scripts=SCRIPTS):
        self.config = Path(config).resolve()
        self.spec = read(self.config)
        if self.spec.get('schema') != 1:
            raise ValueError('Service config schema 1 required')
        self.roots = [Path(p).resolve(strict=True) for p in self.spec['project_roots']]
        if not self.roots or any(not p.is_dir() or p == Path(p.anchor) for p in self.roots):
            raise ValueError('Explicit existing project roots required')
        self.scripts = Path(scripts).resolve()
        self.store = Path(self.spec['state_dir']).resolve()
        if under(self.store, self.scripts.parent):
            raise ValueError('State must be outside the skill')
        self.store.mkdir(parents=True, exist_ok=True)

    def directory(self, job_id):
        if not KEY.fullmatch(job_id):
            raise ValueError('Invalid job id')
        path = self.store / job_id
        if not path.is_dir() or not under(path.resolve(), self.store):
            raise ValueError('Unknown or linked job directory')
        return path

    def submit(self, project, stage, request_id, complete=False, max_batches=100):
        if stage not in STAGES or not KEY.fullmatch(request_id):
            raise ValueError('Use an allowlisted stage and filename-safe request id')
        if type(complete) is not bool or type(max_batches) is not int or not 1 <= max_batches <= 10000:
            raise ValueError('Invalid complete or max_batches')
        if complete and stage != 'render':
            raise ValueError('complete only applies to render')
        path = Path(project).resolve(strict=True)
        if path.suffix.lower() != '.json' or not any(under(path, root) for root in self.roots):
            raise ValueError('Project must be a JSON within configured project roots')
        data, bound_inputs = input_snapshot(path)
        if data.get('schema') != 1:
            raise ValueError('Project schema 1 required')
        resource = (path.parent / data.get('execution_lock', path.name)).resolve()
        request = dict(schema=1, project=str(path), stage=stage,
                       resource=str(resource), request_id=request_id, complete=complete, max_batches=max_batches,
                       inputs=bound_inputs, producer=producer(self.scripts),
                       config_sha256=sha(self.config), scripts=str(self.scripts))
        identity = digest(request)
        job_id = 'job-' + hashlib.sha256(request_id.encode()).hexdigest()[:32]
        folder = self.store / job_id
        guard = resource.with_name(resource.name + '.mcp-owner.json')
        with mutex(self.store / '.submit.lock'):
            if folder.exists():
                try:
                    previous = read(folder / 'request.json')
                    previous_state = read(folder / 'state.json')
                    previous_identity = previous['identity']
                    previous_status = previous_state['status']
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    raise RuntimeError('Incomplete job metadata; inspect original submission; no replay: ' + str(folder)) from exc
                if previous_identity != identity:
                    raise ValueError('Request id already bound to different inputs; no job started')
                # Only this durable pre-launch phase proves that Popen was never
                # reached. Recover to a failed receipt, never launch on retry.
                if (previous_status == 'prepared' or
                        (previous_status == 'failed' and previous_state.get('submission_phase') == 'not_launched')):
                    with mutex(resource.with_name(resource.name + '.mcp.lock')):
                        owner = dict(job_id=job_id, store=str(self.store), identity=identity)
                        if guard.exists() and read(guard) != owner:
                            raise RuntimeError('Reservation differs; inspect original submission; no replay')
                        if previous_state['status'] == 'prepared':
                            previous_state.update(status='failed', heartbeat=time.time(),
                                                  submission_phase='not_launched',
                                                  error='Submission interrupted before worker launch; no stage started')
                            write(folder / 'state.json', previous_state)
                        if guard.exists():
                            guard.unlink()
                return self.status(job_id)
            with mutex(resource.with_name(resource.name + '.mcp.lock')):
                if guard.exists():
                    raise RuntimeError('Project reserved; inspect original job before recovery: ' + str(guard))
                if any(sha(p) != value for p, value in bound_inputs.items()):
                    raise ValueError('Project or plan changed while submitting; no job started')
                # Publish both receipts together. An interrupted metadata write
                # cannot leave the request key bound to a half-written directory.
                pending = self.store / ('.prepare-' + job_id + '-' + secrets.token_hex(8))
                pending.mkdir()
                state = dict(job_id=job_id, status='prepared', submission_phase='prepared', created=time.time(),
                             heartbeat=time.time(), identity=identity)
                try:
                    write(pending / 'request.json', dict(request, identity=identity))
                    write(pending / 'state.json', state)
                    os.replace(pending, folder)
                finally:
                    if pending.exists():
                        for item in pending.iterdir():
                            item.unlink()
                        pending.rmdir()
                write(guard, dict(job_id=job_id, store=str(self.store), identity=identity))
                # A queued receipt means launch may have happened. Never recover
                # it automatically, even if launch.json or the PID is absent.
                state.update(status='queued', submission_phase='launch_possible', heartbeat=time.time())
                write(folder / 'state.json', state)
                flags = (subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS |
                         subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == 'nt' else 0
                try:
                    with (folder / 'worker.log').open('ab') as stream:
                        child = subprocess.Popen([sys.executable, '-B', str(self.scripts / 'mcp_jobs.py'),
                                                  '--config', str(self.config), 'worker', job_id],
                                                 stdin=subprocess.DEVNULL, stdout=stream, stderr=stream,
                                                 creationflags=flags, start_new_session=os.name != 'nt',
                                                 close_fds=True)
                except OSError as exc:
                    state = read(folder / 'state.json')
                    state.update(status='failed', submission_phase='not_launched', error='Worker not launched: ' + str(exc))
                    write(folder / 'state.json', state)
                    guard.unlink()
                    raise
                # From this point the worker may have executed; never release the
                # reservation or call it unlaunched if diagnostic metadata fails.
                threading.Thread(target=child.wait, daemon=True).start()
                try:
                    write(folder / 'launch.json', dict(worker_pid=child.pid, time=time.time()))
                except OSError:
                    pass  # Worker state and project guard remain authoritative.
        return self.status(job_id)

    def status(self, job_id):
        folder = self.directory(job_id)
        try:
            state = read(folder / 'state.json')
            if not isinstance(state, dict) or not isinstance(state.get('status'), str):
                raise ValueError('Invalid state receipt')
        except (OSError, ValueError) as exc:
            return dict(job_id=job_id, status='uncertain',
                        recovery='Job metadata incomplete; inspect original submission; no replay or automatic unlock',
                        cancel_requested=(folder / 'cancel.json').exists(), reservation_inspection_required=True,
                        metadata_read_error=dict(error_type=type(exc).__name__, errno=getattr(exc, 'errno', None),
                            winerror=getattr(exc, 'winerror', None), message=str(exc).replace('\n', ' ')[:240]))
        if state['status'] == 'prepared':
            state['recovery'] = 'Pre-launch receipt: repeat the same request to record failure without launching a stage'
        elif state['status'] not in TERMINAL and time.time() - state.get('heartbeat', 0) > 60:
            state = dict(state, status='uncertain', last_recorded_status=state['status'],
                         recovery='Do not resubmit; inspect original worker, descendants and artifacts')
        state['cancel_requested'] = (folder / 'cancel.json').exists()
        try:
            resource = Path(read(folder / 'request.json')['resource'])
            state['reservation_retained'] = resource.with_name(resource.name + '.mcp-owner.json').exists()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            state['reservation_inspection_required'] = True
            state['reservation_read_error'] = dict(error_type=type(exc).__name__, errno=getattr(exc, 'errno', None),
                winerror=getattr(exc, 'winerror', None), message=str(exc).replace('\n', ' ')[:240])
        return state

    def logs(self, job_id, offset=0, limit=32768):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 65536:
            raise ValueError('Invalid byte offset/limit')
        path = self.directory(job_id) / 'stage.log'
        if not path.exists():
            return dict(text='', next_offset=offset)
        with path.open('rb') as stream:
            stream.seek(offset); data = stream.read(limit)
            return dict(text=data.decode('utf-8', errors='replace'), next_offset=stream.tell())

    def cancel(self, job_id):
        folder = self.directory(job_id)
        status = self.status(job_id)
        if status['status'] not in TERMINAL:
            write(folder / 'cancel.json', dict(requested=time.time()))
        return dict(job_id=job_id, status=status['status'],
                    message='Cooperative request only: active stage/batch finishes; no process is killed')

    def result(self, job_id):
        folder = self.directory(job_id)
        return dict(state=self.status(job_id),
                    result=read(folder / 'result.json') if (folder / 'result.json').exists() else None,
                    log=str(folder / 'stage.log'))

    def worker(self, job_id):
        folder = self.directory(job_id)
        req = read(folder / 'request.json')
        if digest({k: v for k, v in req.items() if k != 'identity'}) != req['identity']:
            raise ValueError('Stored request identity corrupted; reservation retained')
        project = Path(req['project'])
        resource = Path(req['resource'])
        guard = resource.with_name(resource.name + '.mcp-owner.json')
        state = None
        child = None
        known_exit = True
        owns = False
        # Submit briefly holds this same mutex while creating the reservation.
        for attempt in range(100):
            try:
                lock = mutex(resource.with_name(resource.name + '.mcp.lock'))
                lock.__enter__()
                break
            except OSError:
                time.sleep(.05)
        else:
            raise RuntimeError('Could not acquire project lock; reservation retained')
        try:
            state = read(folder / 'state.json')
            if state['status'] != 'queued' or read(guard) != dict(job_id=job_id, store=str(self.store), identity=req['identity']):
                return dict(state, duplicate_worker_refused=True)
            owns = True
            state.update(status='running', worker_pid=os.getpid(), heartbeat=time.time())
            write(folder / 'state.json', state)
            count = 0
            while True:
                if (folder / 'cancel.json').exists():
                    state['status'] = 'cancelled'; break
                if sha(self.config) != req['config_sha256'] or producer(self.scripts) != req['producer']:
                    raise ValueError('Service/producer identity changed; no stage launched')
                if any(sha(p) != value for p, value in req['inputs'].items()):
                    raise ValueError('Project or plan changed; no stage launched')
                command = [sys.executable, '-B', str(self.scripts / 'short_project.py'), req['stage'], '--project', str(project)]
                with (folder / 'stage.log').open('ab') as stream:
                    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream,
                                             stderr=stream, creationflags=flags,
                                             env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1'))
                    known_exit = False
                    state.update(child_pid=child.pid, command=command, batch=count + 1)
                    while child.poll() is None:
                        state['heartbeat'] = time.time(); write(folder / 'state.json', state)
                        time.sleep(.2)
                    code = child.returncode; known_exit = True
                count += 1
                state.update(returncode=code, batches_finished=count, heartbeat=time.time())
                if code != 0:
                    known_exit = False  # A crashed launcher may leave descendants.
                    raise RuntimeError('Canonical stage failed; inspect log, no automatic retry')
                if req['stage'] == 'render':
                    p = read(project)
                    progress = read((project.parent / p['render']['output']).resolve() / 'progress.json')
                    state['render_complete'] = progress['complete']
                    if req['complete'] and not progress['complete']:
                        if (folder / 'cancel.json').exists():
                            state['status'] = 'cancelled'; break
                        if count >= req['max_batches']:
                            raise RuntimeError('Batch budget reached; frames retained; complete render not claimed')
                        continue
                state['status'] = 'completed'; break
            state['heartbeat'] = time.time()
            write(folder / 'result.json', dict(stage=req['stage'], status=state['status'],
                                              identity=req['identity'], returncode=state.get('returncode'),
                                              render_complete=state.get('render_complete'),
                                              canonical_stage_only=True, visual_acceptance=False))
        except BaseException as exc:
            if child is not None and child.poll() is None:
                known_exit = False
            state.update(status='failed' if known_exit else 'uncertain', error=str(exc), heartbeat=time.time())
        finally:
            if owns:
                write(folder / 'state.json', state)
            if owns and known_exit and state['status'] in TERMINAL and guard.exists():
                if read(guard).get('identity') == req['identity']:
                    guard.unlink()
            lock.__exit__(None, None, None)
        return state


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    sub = p.add_subparsers(dest='action', required=True)
    s = sub.add_parser('submit'); s.add_argument('--project', required=True); s.add_argument('--stage', choices=sorted(STAGES), required=True)
    s.add_argument('--wait', action='store_true', help='Keep CLI supervisor alive; required in hosts that clean child trees on command exit'); s.add_argument('--request-id', required=True); s.add_argument('--complete', action='store_true'); s.add_argument('--max-batches', type=int, default=100)
    for name in ('status', 'result', 'cancel', 'worker'):
        sub.add_parser(name).add_argument('job_id')
    l = sub.add_parser('logs'); l.add_argument('job_id'); l.add_argument('--offset', type=int, default=0); l.add_argument('--limit', type=int, default=32768)
    a = p.parse_args(); jobs = Jobs(a.config)
    if a.action == 'submit':
        result = jobs.submit(a.project, a.stage, a.request_id, a.complete, a.max_batches)
        while a.wait and result['status'] not in TERMINAL and result['status'] != 'uncertain':
            time.sleep(.2)
            result = jobs.status(result['job_id'])
    elif a.action == 'logs':
        result = jobs.logs(a.job_id, a.offset, a.limit)
    else:
        result = getattr(jobs, a.action)(a.job_id)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
