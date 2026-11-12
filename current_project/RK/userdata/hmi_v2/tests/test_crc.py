import subprocess,sys,zlib
from core.config import ROOT

def test_native_and_packet_crc_match_zlib_all_alignments_and_full_payloads():
    data=bytes(((i*37+(i>>7)*19)^0xa5)&255 for i in range(861824+8))
    for name in ('crc_fast','crc_portable'):
        exe=ROOT/'native/fpga_io'/(name+'_test'+('.exe' if sys.platform=='win32' else ''))
        out=subprocess.check_output([str(exe)],text=True)
        rows=[r for r in out.splitlines() if not r.startswith('BENCH')]
        assert len(rows)==128
        for row in rows:
            offset,n,ring,packet=map(int,row.split())
            assert ring==packet==zlib.crc32(data[offset:offset+n])
