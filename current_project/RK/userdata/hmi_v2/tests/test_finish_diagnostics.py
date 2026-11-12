import json, subprocess, sys
from core.config import ROOT


def test_receiver_timeout_does_not_become_a_second_cleanup_timeout():
    exe=ROOT/'native/fpga_io'/('finish_diagnostics_test.exe' if sys.platform=='win32' else 'finish_diagnostics_test')
    result=subprocess.run([str(exe)],capture_output=True,text=True,check=True)
    rows=[json.loads(line) for line in result.stderr.splitlines()]
    assert len(rows)==6
    assert rows[0]['worker_errno'] and rows[0]['local_cleanup_errno']==0
    assert rows[1]['worker_errno']==rows[1]['local_cleanup_errno']==0
    for row in rows[2:5]:
        assert row['worker_errno']==0 and row['local_cleanup_errno']
    assert rows[5]['worker_errno'] and rows[5]['local_cleanup_errno']
    assert rows[5]['model_control_before_unmap']==4
    assert all(row['dma_engine_quiescence_verified'] is False for row in rows)
