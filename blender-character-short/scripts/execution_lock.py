"""Hold a cooperative Windows file lock while one local command runs.

All cooperating render entrypoints must use the same lock path. This does not
discover existing unwrapped Blender processes, and a forcibly killed wrapper
cannot prove its descendants exited. Inspect the actual host before recovery.
"""
import argparse,json,os,subprocess,sys,time
from pathlib import Path

def wait_for_child(child):
    while True:
        try:return child.wait()
        except (KeyboardInterrupt,SystemExit):
            print('Wrapper interrupted; retaining lock until child exits. Verify/stop the owned child on its actual host if cancellation is required.',file=sys.stderr)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lock',required=True,type=Path)
    p.add_argument('command',nargs=argparse.REMAINDER)
    a=p.parse_args();command=a.command
    if command and command[0]=='--':command=command[1:]
    if not command:p.error('A command after -- is required')
    if os.name!='nt':p.error('This lock implementation has only been validated on Windows')
    import msvcrt
    lock=a.lock.resolve();lock.parent.mkdir(parents=True,exist_ok=True)
    owner=lock.with_name(lock.name+'.owner.json')
    with lock.open('a+b') as handle:
        handle.seek(0,os.SEEK_END)
        if not handle.tell():handle.write(b'0');handle.flush()
        handle.seek(0)
        try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            print('EXECUTION_BUSY: shared lock is held; no command started: '+str(lock),file=sys.stderr)
            return 75
        child=None
        try:
            state={'schema':1,'wrapper_pid':os.getpid(),'started_unix':time.time(),'status':'starting','command':command}
            def save():
                tmp=owner.with_name(owner.name+'.partial');tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2),'utf-8');tmp.replace(owner)
            save()
            try:
                child=subprocess.Popen(command)
            except OSError as exc:
                state.update(status='launch-failed',error=str(exc))
                try:save()
                except OSError as meta_exc:print('Launch failed; owner metadata also failed: '+str(meta_exc),file=sys.stderr)
                return 127
            state.update(status='running',child_pid=child.pid)
            try:save()
            except OSError as exc:print('Owner metadata update failed; child is running and lock remains held: '+str(exc),file=sys.stderr)
            code=wait_for_child(child)
            state.update(status='finished',returncode=code,finished_unix=time.time())
            try:save()
            except OSError as exc:print('Final owner metadata update failed after child exit: '+str(exc),file=sys.stderr)
            return code
        finally:
            if child is not None and child.poll() is None:wait_for_child(child)
            handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)

if __name__=='__main__':raise SystemExit(main())
