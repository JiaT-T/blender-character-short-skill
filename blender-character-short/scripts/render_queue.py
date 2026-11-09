"""Queue explicit hash-bound saved-native production jobs; preserve saved fps."""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from saved_project_render import render_job
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--jobs',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);path=Path(a.jobs).resolve()
    for job in json.loads(path.read_text('utf-8')):render_job(job,path.parent)
if __name__=='__main__':main()
