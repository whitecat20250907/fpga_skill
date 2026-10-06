"""Complete build05 diagnostics with held-bundle and sampled single-bit CDC."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
top=ROOT/'fpga/uisrc/01_rtl/imx415_pcie_top.v'
s=top.read_bytes().decode('latin1').replace('\r\n','\n')
assert 'cam_pll27 u_cam_pll27' in s and 'u_cam_ui_snapshot' not in s
def once(old,new):
    global s
    assert s.count(old)==1,(old,s.count(old))
    s=s.replace(old,new)
for decl in ('reg [1:0]   cam_i2c_done_sync;', 'reg [1:0]   cam_delay_done_sync;',
             'reg [1:0] dbg_pll_stable_sync;', 'reg [2:0] dbg_link_up_sync;'):
    once('    '+decl,'    (* async_reg="true" *) '+decl)
start=s.index('    // Toggle a flag in MIPI clock domain')
end=s.index('    // Frame bytes calculation',start)
s=s[:start]+'''    // Coherent snapshot completion and measured HS edges indicate recent
    // activity. A sampled clock toggle was an instantaneous pulse, not a
    // stable "clock present" indication. Expire after 200ms without a new
    // snapshot, including source-clock loss leaving the handshake busy.
    reg [30:0] mipi_snapshot_seen;
    reg [24:0] mipi_snapshot_age;
    wire mipi_clk_present=(csi_snapshot_status[31:1]!=0) &&
        (csi_clock_delta!=0) && (mipi_snapshot_age<25'd25000000);
    always @(posedge user_clk or negedge user_rst_n) begin
        if(!user_rst_n) begin mipi_snapshot_seen<=0;mipi_snapshot_age<=25'd25000000;end
        else if(csi_snapshot_status[31:1]!=mipi_snapshot_seen) begin
            mipi_snapshot_seen<=csi_snapshot_status[31:1];mipi_snapshot_age<=0;
        end else if(mipi_snapshot_age<25'd25000000)
            mipi_snapshot_age<=mipi_snapshot_age+1'b1;
    end
    (* async_reg="true" *) reg [1:0] cam_raw_valid_sync;
    always @(posedge user_clk or negedge user_rst_n) begin
        if(!user_rst_n) cam_raw_valid_sync<=0;
        else cam_raw_valid_sync<={cam_raw_valid_sync[0],cam_mipi_tvalid};
    end

'''+s[end:]
once('    ui_cfg_imx415 #(\n', '''    // UI metadata is one held-bundle snapshot, never asynchronous counter
    // bits. Its 100ms update is diagnostic, not an I2C command acknowledgment.
    wire [223:0] cam_ui_snapshot;
    csi_stats_snapshot #(.PERIOD(12500000)) u_cam_ui_snapshot (
        .src_clk(cam_24m),.dst_clk(user_clk),
        .rst_n(cam_clock_cfg_reset_n & user_rst_n),
        .src_stats({181'd0,ae_write_cnt,ae_trig_pending,ae_cfg_done_w,cam_i2c_bus_error}),
        .snapshot(cam_ui_snapshot),.status(),.clock_delta());

    ui_cfg_imx415 #(
''')
once('vid_reg_rdata_d1 <= {ae_write_cnt,','vid_reg_rdata_d1 <= {cam_ui_snapshot[10:3],')
once('                                                       ae_trig_pending,','                                                       cam_ui_snapshot[2],')
once('                                                       ae_cfg_done_w,','                                                       cam_ui_snapshot[1],')
once('                                                       cam_mipi_tvalid,','                                                       cam_raw_valid_sync[1],')
once('                                                       cam_i2c_bus_error,','                                                       cam_ui_snapshot[0],')
s=s.replace('MIPI raw tvalid (debug, async!)','MIPI raw tvalid (2FF sampled level)')
s=s.replace('I2C bus error (async!)','I2C bus error (UI snapshot)')
once('    // Assemble status word','''    (* async_reg="true" *) reg [1:0] dbg_ui_lock_sync;
    always @(posedge app_auxclk or negedge pll_lock) begin
        if(!pll_lock) dbg_ui_lock_sync<=0;
        else dbg_ui_lock_sync<={dbg_ui_lock_sync[0],ui_pll_lock};
    end

    // Assemble status word''')
once('                                   ui_pll_lock,','                                   dbg_ui_lock_sync[1],')
once('    wire [31:0] dbg_uart_fcount = cam_frame_count;', '''    wire [223:0] dbg_uart_snapshot;
    csi_stats_snapshot #(.PERIOD(2500000)) u_dbg_uart_snapshot (
        .src_clk(user_clk),.dst_clk(app_auxclk),.rst_n(pll_lock & user_rst_n),
        .src_stats({160'd0,cam_frame_count}),.snapshot(dbg_uart_snapshot),
        .status(),.clock_delta());
    wire [31:0] dbg_uart_fcount = dbg_uart_snapshot[31:0];''')
top.write_bytes(s.encode('latin1'))
p=ROOT/'evidence/clock05_integration_manifest.json'
d=json.loads(p.read_text());d[str(top.relative_to(ROOT))]=hashlib.sha256(top.read_bytes()).hexdigest()
p.write_text(json.dumps(d,indent=2)+'\n')
print('Added held-bundle UI/UART metadata CDC; physical validation is pending.')
