import subprocess,sys
import pytest
from core.config import ROOT
def test_panel_register_model():
    binary=ROOT/'native/fpga_io'/('panel_test.exe' if sys.platform=='win32' else 'panel_test')
    r=subprocess.run([str(binary)],capture_output=True,text=True,timeout=5)
    assert r.returncode==0 and 'PASS panel sequence' in r.stdout,r.stdout+r.stderr

@pytest.mark.skipif(sys.platform!='linux',reason='Linux device flag ABI; execute on target ARM64')
def test_dma_open_selects_packet_completion():
    r=subprocess.run([str(ROOT/'native/fpga_io/device_open_test')],capture_output=True,text=True,timeout=5)
    assert r.returncode==0 and 'atomic EOP-mode open' in r.stdout,r.stdout+r.stderr
