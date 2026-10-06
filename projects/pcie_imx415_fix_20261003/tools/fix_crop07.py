"""Fix overflowing crop windows; build06 evidence remains immutable."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
top=R/'fpga/uisrc/01_rtl/imx415_pcie_top.v'
assert sha(top)=='066f9ab0fd0cb8e530b4ccd94a0dbaec86e691b596966530411fab010c88ea5e'
s=top.read_bytes().replace(b'\r\n',b'\n').decode('latin1')
assert s.count("cam_crop_v_start = 15'd19;")==2
assert s.count("cam_crop_v_end   = 15'd1100;")==2
s=s.replace("cam_crop_v_start = 15'd19;","cam_crop_v_start = 15'd15; // first row 16, even Bayer phase")
s=s.replace("cam_crop_v_end   = 15'd1100;","cam_crop_v_end   = 15'd1096; // rows 16..1095: 1080 inside 1097")
lines=s.splitlines(True)
for i,line in enumerate(lines):
    if "cam_crop_v_start = 15'd35;  // was 36" in line:
        lines[i]="                cam_crop_v_start = 15'd15; // first row 16, even Bayer phase\n"
    if "cam_crop_v_end   = 15'd2196;" in line:
        lines[i]="                cam_crop_v_end   = 15'd2176; // rows 16..2175: 2160 inside 2192\n"
top.write_bytes(''.join(lines).encode('latin1'))
p=R/'fpga/uisrc/01_rtl/param_imx415.v';b=p.read_bytes()
assert b.count(b'5644_0601')==1;p.write_bytes(b.replace(b'5644_0601',b'5644_0701'))
for fn in ['tools/read_csi_stats.py','tools/hardware_regression.sh']:
    p=R/fn;b=p.read_bytes()
    b=b.replace(b'0x56440401,0x56440501,0x56440601',b'0x56440401,0x56440501,0x56440601,0x56440701')
    b=b.replace(b'version in (0x56440501,0x56440601)',b'version in (0x56440501,0x56440601,0x56440701)')
    b=b.replace(b'version 04, 05 or 06',b'version 04 through 07')
    p.write_bytes(b)
record=dict(version='0x56440701',top_sha256=sha(top),
    source06='build06_sources.json; interrupted before STA because crop defect found',
    observed_short_bytes=6197776,expected_bytes=6220800,
    old_crop_selected_rows=1077,old_matrix_emitted_rows=1076,
    profiles={'1080p':dict(raw_height=1097,start=15,end=1096,first=16,last=1095),
              '4K':dict(raw_height=2192,start=15,end=2176,first=16,last=2175),
              '720p':dict(raw_height=1097,start=35,end=756,first=36,last=755)},
    status='Digital crop/physical RAW height/STA/hardware still require verification')
(R/'evidence/crop07_integration.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
