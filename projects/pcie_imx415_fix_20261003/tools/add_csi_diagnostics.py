from pathlib import Path
import shutil
p=Path(__file__).resolve().parents[1]
cam=p/'fpga/uisrc/03_ip/vid_pipeline/cam_video_source.v'
top=p/'fpga/uisrc/01_rtl/imx415_pcie_top.v'
def replace_once(data,old,new):
    old=old.encode();new=new.encode()
    assert data.count(old)==1,old
    return data.replace(old,new)
data=cam.read_bytes().replace(b'\r\n',b'\n')
data=replace_once(data,'output wire [5:0]    dbg_best_len','output wire [223:0] csi_snapshot,\n    output wire [31:0] csi_snapshot_status,\n    output wire [31:0] csi_clock_delta,\n    output wire [5:0]    dbg_best_len')
data=replace_once(data,'    mipi_csi_rx #( ','    mipi_csi_rx #( ') if False else data
data=replace_once(data,'    mipi_csi_rx #(\n','    wire [191:0] csi_stats;\n    csi_stats_snapshot u_csi_snapshot (.src_clk(mipi_div_clk_out),\n        .dst_clk(user_clk),.rst_n(user_rst_n),.src_stats(csi_stats),\n        .snapshot(csi_snapshot),.status(csi_snapshot_status),\n        .clock_delta(csi_clock_delta));\n    mipi_csi_rx #(\n')
data=replace_once(data,'        .O_dbg_best_len         (dbg_best_len)','        .O_csi_raw_packets      (csi_stats[31:0]),\n        .O_csi_crc_errors       (csi_stats[63:32]),\n        .O_csi_ecc_errors       (csi_stats[95:64]),\n        .O_csi_wc_errors        (csi_stats[127:96]),\n        .O_csi_timeout_errors   (csi_stats[159:128]),\n        .O_csi_fifo_overflows   (csi_stats[191:160]),\n        .O_csi_error_pulse      (),\n        .O_dbg_best_len         (dbg_best_len)')
cam.write_bytes(data)
data=top.read_bytes().replace(b'\r\n',b'\n')
data=replace_once(data,'    wire [31:0] cam_frame_count;','    wire [223:0] csi_snapshot;\n    wire [31:0] csi_snapshot_status,csi_clock_delta;\n    wire [31:0] cam_frame_count;')
data=replace_once(data,'        .dbg_best_len       (cam_dbg_best_len)','        .csi_snapshot       (csi_snapshot),\n        .csi_snapshot_status(csi_snapshot_status),\n        .csi_clock_delta    (csi_clock_delta),\n        .dbg_best_len       (cam_dbg_best_len)')
data=replace_once(data,"(m_axil_araddr[7:0] <= 8'hA4)","(m_axil_araddr[7:0] <= 8'hC8)")
data=replace_once(data,"            8'hA4:                vid_reg_rdata_d1 <= {31'd0, reg_image_loopback};", "            8'hA4:                vid_reg_rdata_d1 <= {31'd0, reg_image_loopback};\n            8'hA8:                vid_reg_rdata_d1 <= csi_snapshot_status;\n            8'hAC:                vid_reg_rdata_d1 <= csi_snapshot[223:192];\n            8'hB0:                vid_reg_rdata_d1 <= csi_snapshot[31:0];\n            8'hB4:                vid_reg_rdata_d1 <= csi_snapshot[63:32];\n            8'hB8:                vid_reg_rdata_d1 <= csi_snapshot[95:64];\n            8'hBC:                vid_reg_rdata_d1 <= csi_snapshot[127:96];\n            8'hC0:                vid_reg_rdata_d1 <= csi_snapshot[159:128];\n            8'hC4:                vid_reg_rdata_d1 <= csi_snapshot[191:160];\n            8'hC8:                vid_reg_rdata_d1 <= csi_clock_delta;")
data=data.replace(b'// Default: 4K@30fps',b'// Default: 1080p binning')
top.write_bytes(data)
shutil.copy2(p/'tools/csi_stats_snapshot.v',p/'fpga/uisrc/03_ip/vid_pipeline/csi_stats_snapshot.v')
al=p/'fpga/imx415_pcie_4k.al'
s=al.read_text(encoding='utf-8')
entry='''            <File Path="uisrc/03_ip/vid_pipeline/csi_stats_snapshot.v">
                <FileInfo>
                    <Attr Name="UsedInSyn" Val="true"/>
                    <Attr Name="UsedInP&amp;R" Val="true"/>
                    <Attr Name="BelongTo" Val="design_1"/>
                    <Attr Name="CompileOrder" Val="138"/>
                </FileInfo>
            </File>
'''
# TD writes raw P&R in attribute values, XML-safe representation is equivalent.
assert 'csi_stats_snapshot.v' not in s
s=s.replace('        </Verilog>',entry+'        </Verilog>',1)
al.write_text(s,encoding='utf-8')
print('Connected coherent CSI counters and HS divided clock sampling at BAR A8-C8')
