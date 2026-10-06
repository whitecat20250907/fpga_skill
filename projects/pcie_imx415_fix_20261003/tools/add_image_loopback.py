"""Add a stopped-camera image roundtrip mode to this isolated clone only."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'fpga/uisrc/01_rtl/imx415_pcie_top.v'
b=p.read_bytes()
def replace(old,new):
    global b
    old=old.encode();new=new.encode()
    assert b.count(old)==1, old
    b=b.replace(old,new)
replace('    reg         reg_enable;', '    reg         reg_enable;\n    reg         reg_image_loopback; // BAR 0xA4 bit0: H2C FIFO -> C2H, camera stopped')
replace('wire        cam_enable = reg_enable & user_link_up;', 'wire        cam_enable = reg_enable & user_link_up & !reg_image_loopback;')
replace('.m_tready            (s0_axis_c2h_tready)', '.m_tready            (s0_axis_c2h_tready & !reg_image_loopback)')
replace('assign s0_axis_c2h_tdata  = fc_out_tdata;', 'assign s0_axis_c2h_tdata  = reg_image_loopback ? app_c2h_tdata : fc_out_tdata;')
replace('assign s0_axis_c2h_tkeep  = {KEEP_WIDTH{1\'b1}};', 'assign s0_axis_c2h_tkeep  = reg_image_loopback ? app_c2h_tkeep : {KEEP_WIDTH{1\'b1}};')
replace('assign s0_axis_c2h_tuser  = {KEEP_WIDTH{1\'b1}};', 'assign s0_axis_c2h_tuser  = reg_image_loopback ? app_c2h_tuser : {KEEP_WIDTH{1\'b1}};')
replace('assign s0_axis_c2h_tlast  = fc_out_tlast;', 'assign s0_axis_c2h_tlast  = reg_image_loopback ? app_c2h_tlast : fc_out_tlast;')
replace('assign s0_axis_c2h_tvalid = fc_out_tvalid;', 'assign s0_axis_c2h_tvalid = reg_image_loopback ? app_c2h_tvalid : fc_out_tvalid;')
replace("assign app_c2h_tready = 1'b0;", 'assign app_c2h_tready = reg_image_loopback & s0_axis_c2h_tready;')
replace("reg_cam_mode    <= 2'd1;", "reg_cam_mode    <= 2'd0;")
replace("reg_enable      <= 1'b0;", "reg_enable      <= 1'b0;\n            reg_image_loopback <= 1'b0;")
replace('`REG_CAM_MODE:    reg_cam_mode', "8'hA4:           reg_image_loopback <= m_axil_wdata[0];\n                    `REG_CAM_MODE:    reg_cam_mode")
replace("(m_axil_araddr[7:0] <= 8'hA0);", "(m_axil_araddr[7:0] <= 8'hA4);")
replace('default:              vid_reg_rdata_d1 <= 32\'d0;', "8'hA4:                vid_reg_rdata_d1 <= {31'd0, reg_image_loopback};\n            default:              vid_reg_rdata_d1 <= 32'd0;")
p.write_bytes(b)
# Keep the vendor attribution block in the replacement AWB.
vendor=(root/'evidence/ui_awb_vendor.v').read_bytes()
header=vendor[:vendor.index(b'*/')+2]+b'\n'
awb=root/'fpga/uisrc/03_ip/ui_isp/ui_awb/ui_awb.v'
awb.write_bytes(header+(root/'tools/ui_awb_frame_safe.v').read_bytes())
print('Patched isolated top; preserved AWB vendor attribution.')
