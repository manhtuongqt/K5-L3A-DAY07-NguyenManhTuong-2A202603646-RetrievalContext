"""Run real discovered tests with a UTF-8 log and machine-readable result."""
import io
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.lab_common import ROOT,write_json,now

def main():
    stream=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    path=ROOT/'results/tests.log';path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(stream.getvalue(),encoding='utf-8',newline='\n')
    record={'run_at':now(),'command':'python -X utf8 scripts/run_tests.py',
            'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
            'skipped':len(result.skipped),'passed':result.wasSuccessful(),
            'log':'results/tests.log','scope':'Includes fixture behavioral tests, pinned source/benchmark checks and real local retrieval integration; not semantic model benchmark.'}
    write_json('results/tests.json',record)
    print(record)
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
