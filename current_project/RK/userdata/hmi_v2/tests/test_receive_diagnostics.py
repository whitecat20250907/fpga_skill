import json,subprocess,sys
from core.config import ROOT

def test_fault_counters_are_read_only_bounded_and_distinguish_timeout():
    exe=ROOT/'native/fpga_io'/('receive_diagnostics_test.exe' if sys.platform=='win32' else 'receive_diagnostics_test')
    result=subprocess.run([str(exe)],capture_output=True,text=True,check=True)
    rows=[json.loads(line) for line in result.stderr.splitlines()]
    assert len(rows)==16
    assert [r['event'] for r in rows[:-1]]==list(range(1,9))+[16,32,64,128,256,512,1024]
    assert rows[0]['overflows']==3 and rows[0]['abort_frames']==2
    assert rows[0]['sealed_status']==8 and rows[0]['read_bytes']==176
    assert rows[-1]['read_errno']==110 and rows[-1]['read_bytes']==-1
    assert all(not r['atomic_hardware_snapshot'] and not r['dma_engine_quiescence_verified'] for r in rows)
