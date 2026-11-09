"""Run native unit tests separately from role/movie visual acceptance."""
from pathlib import Path
import sys,argparse,unittest,json,datetime,os
sys.path.insert(0,str(Path(__file__).resolve().parent))
from production_contract import write_json,producer_identity
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);report=Path(a.report).resolve();os.environ['BLENDER_TEST_OUTPUT']=str(report.parent/'native-test-fixtures')
    suite=unittest.defaultTestLoader.discover(str(Path(__file__).parent),pattern='test_*.py');result=unittest.TextTestRunner(verbosity=1).run(suite)
    data={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tests':result.testsRun,'errors':len(result.errors),'failures':len(result.failures),'skipped':len(result.skipped),'passed':result.wasSuccessful(),'scope':'Native unit tests only; not a complete role/story or visual acceptance','producers':producer_identity(Path(__file__).parent)};write_json(report,data);print(json.dumps({k:v for k,v in data.items() if k!='producers'}))
    if not result.wasSuccessful():raise RuntimeError('Native regression suite failed')
if __name__=='__main__':main()
