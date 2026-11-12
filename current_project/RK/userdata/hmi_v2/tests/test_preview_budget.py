from pathlib import Path
import subprocess,sys
import pytest
from core.config import ROOT

def test_preview_budget_native():
    path=ROOT/'native/fpga_io'/('preview_budget_test.exe' if sys.platform=='win32' else 'preview_budget_test')
    if not path.exists():pytest.skip('Build the native preview budget test')
    result=subprocess.run([str(path)],capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'PASS preview budget:' in result.stdout
