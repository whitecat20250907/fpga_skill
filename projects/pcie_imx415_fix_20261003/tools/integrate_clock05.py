"""One-time integration into the independent PCIe repair tree, never vendor demos.

Requires the verified build04 source tree. New PLL is a manually instantiated
PH1 candidate, not Wizard output. Acceptance requires fresh STA and board tests.
"""
from pathlib import Path
import hashlib,json,shutil

ROOT=Path(__file__).resolve().parents[1]
FPGA=ROOT/'fpga'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def replace_once(s,old,new):
    assert s.count(old)==1,(old,s.count(old))
    return s.replace(old,new)
top=FPGA/'uisrc/01_rtl/imx415_pcie_top.v'
assert sha(top)=='2000d6555487bba6e34e9fe252dfb901c71c14fc2b13cafcd25f2f91f1c52486'
assert sha(ROOT/'tools/camera_clock_startup.v')=='e3a12c4465c6ea1518e262b7d90e7374572c5612f253ef6c48c77832019a5ace'
s=top.read_bytes().replace(b'\r\n',b'\n').decode('latin1')
assert "cam_pll27 u_cam_pll27" not in s
s=replace_once(s,'// 12MHz to sensor INCK (toggle)','// 27MHz forwarded to sensor INCK')
s=replace_once(s,'// cam_24m   = MCLK source (ODDR) + I2C master clock','// cam_24m   = I2C and startup sequencing; native 27MHz PLL supplies MCLK')
start=s.index('    // IMX415 XCLR: always release from reset')
end=s.index('// ====================================================================\n// SGDMA Subsystem',start)
s=s[:start]+'''    // Sensor register table is the 27 MHz / 891 Mbps profile. The old
    // 24 MHz toggle produced 12 MHz and ~26.67 fps instead of nominal 60.
    // Native PH1 PLL candidate: 25 MHz PFD, 1350 MHz VCO, /50 = 27 MHz.
    // Clock forwarding and I2C release follow the explicit startup sequence.
    wire cam_27m, cam_pll27_lock, cam_clock_cfg_reset_n;
    wire [15:0] cam_clock_startup_status;
    cam_pll27 u_cam_pll27 (.refclk(sys_clk_g),.reset(!int_por_done_r),
        .lock(cam_pll27_lock),.clk25_feedback(),.clk27_out(cam_27m));
    camera_clock_startup u_camera_clock_startup (
        .clock24(cam_24m),.clock27(cam_27m),
        .pll27_lock_raw(cam_pll27_lock),.ui_lock_raw(ui_pll_lock),
        .system_reset_n(user_rst_n),.sensor_xclr(cam_xclr),
        .sensor_mclk(cam_mclk),.config_reset_n(cam_clock_cfg_reset_n),
        .status(cam_clock_startup_status));
    wire [31:0] cam_clock_measured_edges,cam_clock_window_index;
    wire cam_clock_measure_valid,cam_clock_frequency_ok,cam_clock_lock_s;
    (* async_reg="true" *) reg [2:0] cam_monitor_reset27;
    wire cam_monitor_async_reset_n=cam_pll27_lock & user_rst_n;
    always @(posedge cam_27m or negedge cam_monitor_async_reset_n) begin
        if(!cam_monitor_async_reset_n) cam_monitor_reset27<=3'b000;
        else cam_monitor_reset27<={cam_monitor_reset27[1:0],1'b1};
    end
    cam_clock27_monitor #(.REF_HZ(125000000)) u_cam_clock_monitor (
        .clk_ref(user_clk),.ref_reset_n(user_rst_n),.clk_test(cam_27m),
        .test_reset_n(cam_monitor_reset27[2]),.pll_lock(cam_pll27_lock),
        .measured_edges(cam_clock_measured_edges),
        .window_index(cam_clock_window_index),
        .measurement_valid(cam_clock_measure_valid),
        .frequency_ok(cam_clock_frequency_ok),.lock_in_ref(cam_clock_lock_s));
    // Only these individual flags cross domains. No asynchronous binary FSM
    // state is presented as an atomic multibit read to the host.
    (* async_reg="true" *) reg [1:0] cam_xclr_sync,cam_cfg_ready_sync;
    always @(posedge user_clk or negedge user_rst_n) begin
        if(!user_rst_n) begin cam_xclr_sync<=0;cam_cfg_ready_sync<=0;end
        else begin
            cam_xclr_sync<={cam_xclr_sync[0],cam_xclr};
            cam_cfg_ready_sync<={cam_cfg_ready_sync[0],cam_clock_cfg_reset_n};
        end
    end

'''+s[end:]
s=replace_once(s,'''    always @(posedge user_clk) begin
        if (cam_delay_done_s)
            cam_best_len_sync <= cam_dbg_best_len;
    end''','''    always @(posedge user_clk or negedge user_rst_n) begin
        if (!user_rst_n)
            cam_best_len_sync <= 6'd0;
        else if (!cam_delay_done_s)
            cam_best_len_sync <= 6'd0;
        else
            cam_best_len_sync <= cam_dbg_best_len;
    end''')
# Start/lock loss clear the entire 24 MHz configuration state coherently.
assert s.count('posedge cam_24m or negedge ui_pll_lock')==4
assert s.count('if (!ui_pll_lock) begin')==4
s=s.replace('posedge cam_24m or negedge ui_pll_lock','posedge cam_24m or negedge cam_clock_cfg_reset_n')
s=s.replace('if (!ui_pll_lock) begin','if (!cam_clock_cfg_reset_n) begin')
s=replace_once(s,'.I_rst_n        (ui_pll_lock)', '.I_rst_n        (cam_clock_cfg_reset_n)')
s=replace_once(s,"(m_axil_araddr[7:0] <= 8'hC8)","(m_axil_araddr[7:0] <= 8'hD4)")
s=replace_once(s,"            8'hC8:                vid_reg_rdata_d1 <= csi_clock_delta;",'''            8'hC8:                vid_reg_rdata_d1 <= csi_clock_delta;
            8'hCC:                vid_reg_rdata_d1 <= cam_clock_measured_edges;
            8'hD0:                vid_reg_rdata_d1 <= cam_clock_window_index;
            8'hD4:                vid_reg_rdata_d1 <= {27'd0,
                cam_cfg_ready_sync[1],cam_xclr_sync[1],
                (cam_clock_window_index!=0),cam_clock_frequency_ok,
                cam_clock_lock_s};''')
top.write_bytes(s.encode('latin1'))
param=FPGA/'uisrc/01_rtl/param_imx415.v'
param.write_bytes(replace_once(param.read_bytes(),b"32'h5644_0401",b"32'h5644_0501"))
dest=FPGA/'uisrc/03_ip/vid_pipeline'
for name,src in [('cam_pll27.v','cam27_ip_trial/cam_pll27.v'),
                 ('cam_clock27_monitor.v','cam27_ip_trial/cam_clock27_monitor.v'),
                 ('camera_clock_startup.v','camera_clock_startup.v')]:
    shutil.copy2(ROOT/'tools'/src,dest/name)
shutil.copy2(ROOT/'tools/csi_rx_packet_handler_fast.v',
             FPGA/'uisrc/03_ip/mipi_csi_2/csi_rx_packet_handler.v')
al=FPGA/'imx415_pcie_4k.al'
s=al.read_text(encoding='utf-8')
entries=''
for order,name in enumerate(('cam_pll27.v','cam_clock27_monitor.v','camera_clock_startup.v'),139):
    assert name not in s
    entries+=f'''            <File Path="uisrc/03_ip/vid_pipeline/{name}">
                <FileInfo>
                    <Attr Name="UsedInSyn" Val="true"/>
                    <Attr Name="UsedInP&amp;R" Val="true"/>
                    <Attr Name="BelongTo" Val="design_1"/>
                    <Attr Name="CompileOrder" Val="{order}"/>
                </FileInfo>
            </File>
'''
al.write_text(replace_once(s,'        </Verilog>',entries+'        </Verilog>'),encoding='utf-8')
sdc=FPGA/'uisrc/04_pin/imx415_pcie.sdc'
s=sdc.read_text(encoding='utf-8')
s=replace_once(s,'-period 5.0 [get_ports {mipi_clk_hs_rx_p}]',
               '-period 2.244668 [get_ports {mipi_clk_hs_rx_p}]')
s=replace_once(s,'sys_clk u_sgdma_pll/pll_inst.clkc[0] u_sgdma_pll/pll_inst.clkc[1]',
    'sys_clk u_sgdma_pll/pll_inst.clkc[0] u_sgdma_pll/pll_inst.clkc[1] u_cam_pll27/pll_inst.clkc[0] u_cam_pll27/pll_inst.clkc[1]')
sdc.write_text(s,encoding='utf-8')
files=[top,param,al,sdc,*[dest/n for n in ('cam_pll27.v','cam_clock27_monitor.v','camera_clock_startup.v')],
       FPGA/'uisrc/03_ip/mipi_csi_2/csi_rx_packet_handler.v']
(ROOT/'evidence/clock05_integration_manifest.json').write_text(json.dumps(
    {str(p.relative_to(ROOT)):sha(p) for p in files},indent=2)+'\n')
print('Integrated diagnostic version 0x56440501; fresh TD and hardware acceptance remain required.')
