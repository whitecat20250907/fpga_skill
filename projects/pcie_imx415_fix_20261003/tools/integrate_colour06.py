"""Integrate reviewed candidates into the independent repair tree only."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def once(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b)
top=ROOT/'fpga/uisrc/01_rtl/imx415_pcie_top.v'
assert sha(top)=='bef80e3ba5f108192b00f569005fa09449ec227c537e3c595f67c08261820a75'
manifest=json.loads((ROOT/'tools/bayer_runtime6/manifest.json').read_text())
copies=[
('tools/bayer_runtime6/cam_video_source.v','fpga/uisrc/03_ip/vid_pipeline/cam_video_source.v','b1e2a6c265e54b0feb515654cd3779c6de62312c5672591dbd306f20743e2192'),
('tools/bayer_runtime6/ui_top_demosaic.v','fpga/uisrc/03_ip/ui_isp/ui_top_demosaic.v','9cd6b66cf894553440e17c3235fb107a8d5562f18b0bde29267520f2f1a7a053'),
('tools/bayer_runtime6/ui_bilinear_interpolation.v','fpga/uisrc/03_ip/ui_isp/ui_bilinear_interpolation.v','2cf8f8ebe514478a8f6668ed5efe970a4fac8122f1ba99e5a44eed4e78b0c780'),
('tools/csi_fast6/csi_rx_hs_data_phy.v','fpga/uisrc/03_ip/mipi_csi_2/csi_rx_hs_data_phy.v','9623dbb888879c26043bd8ea4bed8141e25293b661c96e4ee803076b1585b8b2')]
for src,dst,expected in copies:assert sha(ROOT/src)==expected,(src,sha(ROOT/src))
s=top.read_bytes().replace(b'\r\n',b'\n').decode('latin1')
s=once(s,'    reg [1:0]   reg_cam_mode;', '    reg [1:0]   reg_bayer_mode;     // BAR D8 shadow: 0 RGGB, 1 BGGR, 2 GRBG, 3 GBRG\n    wire [1:0]  cam_active_bayer_mode; // BAR DC: accepted cropped-frame mode\n    reg [1:0]   reg_cam_mode;')
s=once(s,'.BAYER_MODE     ("RGGB")','.BAYER_MODE     ("GBRG")')
s=once(s,'        .cfg_img_width      (cam_img_width),','        .cfg_bayer_mode     (reg_bayer_mode),\n        .active_bayer_mode  (cam_active_bayer_mode),\n        .cfg_img_width      (cam_img_width),')
s=once(s,"            reg_cam_mode    <= 2'd0;", "            reg_bayer_mode  <= 2'd3; // Candidate GBRG; must confirm on HDMI chart\n            reg_cam_mode    <= 2'd0;")
s=once(s,"                    8'hA4:           reg_image_loopback <= m_axil_wdata[0];", "                    8'hA4:           reg_image_loopback <= m_axil_wdata[0];\n                    8'hD8:           reg_bayer_mode <= m_axil_wdata[1:0];")
s=once(s,"(m_axil_araddr[7:0] <= 8'hD4)","(m_axil_araddr[7:0] <= 8'hDC)")
s=once(s,"            8'hD4:                vid_reg_rdata_d1 <=", "            8'hD8:                vid_reg_rdata_d1 <= {30'd0,reg_bayer_mode};\n            8'hDC:                vid_reg_rdata_d1 <= {30'd0,cam_active_bayer_mode};\n            8'hD4:                vid_reg_rdata_d1 <=")
for src,dst,expected in copies:shutil.copyfile(ROOT/src,ROOT/dst)
cam=ROOT/copies[0][1]
c=cam.read_bytes().replace(b'\r\n',b'\n').decode('latin1')
c=once(c,'    output wire [31:0]   frame_count_out,','    output wire [31:0]   frame_count_out,\n    output wire [1:0]    active_bayer_mode,')
c=once(c,'    reg [1:0] frame_bayer_mode;','    reg [1:0] frame_bayer_mode;\n    assign active_bayer_mode=frame_bayer_mode;')
cam.write_bytes(c.encode('latin1'));top.write_bytes(s.encode('latin1'))
param=ROOT/'fpga/uisrc/01_rtl/param_imx415.v'
p=param.read_bytes();assert p.count(b'5644_0501')==1
param.write_bytes(p.replace(b'5644_0501',b'5644_0601'))
for fn in ['tools/read_csi_stats.py','tools/hardware_regression.sh']:
    f=ROOT/fn;b=f.read_bytes()
    b=b.replace(b'0x56440401,0x56440501',b'0x56440401,0x56440501,0x56440601')
    b=b.replace(b'version==0x56440501',b'version in (0x56440501,0x56440601)')
    b=b.replace(b'version 04 or 05',b'version 04, 05 or 06')
    f.write_bytes(b)
changes=[dict(source=src,destination=dst,input_sha256=expected,output_sha256=sha(ROOT/dst)) for src,dst,expected in copies]
(ROOT/'evidence/colour06_integration.json').write_text(json.dumps(dict(version='0x56440601',default_bayer='GBRG candidate, hardware unverified',registers={'D8':'shadow','DC':'crop-SOF-locked'},changes=changes,top_sha256=sha(top)),indent=2)+'\n')
print(json.dumps(dict(integrated=True,version='0x56440601',top_sha256=sha(top))))
