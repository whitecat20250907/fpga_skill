from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
RTL=ROOT/'fpga/uisrc/03_ip/mipi_csi_2'
def backup(name):
    path=RTL/name
    out=ROOT/'tools'/('csi_before_'+name+'.txt')
    if not out.exists(): out.write_bytes(path.read_bytes())
    return path.read_bytes()

old=backup('auto_delay_ctl.v')
prefix=old.split(b'module ',1)[0]
body=r'''module auto_delay_ctl #(
    parameter MIPI_LAN=4,
    parameter LAN_DATA_CUNT=10'h3ff,
    parameter TAP_COUNT=64,
    parameter TEST_CYCLES=32768,
    parameter SETTLE_CYCLES=256,
    parameter WAIT_CYCLES=16777216,
    parameter PASS_THRESH=64
)(
    input wire I_byte_clk, I_reset_n,
    input wire [MIPI_LAN-1:0] I_byte_align_done,
    output reg [5:0] O_delay_value,
    output reg O_delay_vaild, O_auto_delay_done,
    output wire [5:0] O_dbg_best_len
);
// TAP_COUNT is a physical device capability: PH1A HR IDELAY has 5 bits, so
// there are 32 distinct taps. A 64-tap scanner must not visit each tap twice.
// Seven-bit run lengths represent a full 64-tap eye without wrap to zero.
localparam [3:0] ST_WAIT_DATA=0, ST_WAIT_SET=1, ST_SET_TAP=2,
    ST_SETTLE=3, ST_TEST=4, ST_NEXT=5, ST_FIND=6, ST_APPLY=7, ST_DONE=8;
reg [3:0] state;
reg [5:0] scan_tap,cur_start,best_start;
reg [6:0] cur_len,best_len;
reg in_run,pass_flag;
localparam CNT_WIDTH=$clog2(((TEST_CYCLES>SETTLE_CYCLES) ? TEST_CYCLES : SETTLE_CYCLES)+1);
localparam ALIGN_WIDTH=$clog2(TEST_CYCLES+1);
localparam WAIT_WIDTH=(WAIT_CYCLES>1) ? $clog2(WAIT_CYCLES) : 1;
reg [CNT_WIDTH-1:0] cnt;
reg [ALIGN_WIDTH-1:0] align_cnt;
reg [WAIT_WIDTH-1:0] wait_cnt;
wire all_aligned=&I_byte_align_done;
wire any_aligned=|I_byte_align_done;
// Retain the existing six-bit debug ABI; 64 is saturated to 63, not wrapped.
// PH1A's actual maximum 32 is represented exactly.
assign O_dbg_best_len=best_len[6] ? 6'd63 : best_len[5:0];
always @(posedge I_byte_clk or negedge I_reset_n) begin
    if(!I_reset_n) begin
        state<=ST_WAIT_DATA;scan_tap<=0;cnt<=0;align_cnt<=0;wait_cnt<=0;
        cur_start<=0;cur_len<=0;best_start<=0;best_len<=0;
        in_run<=0;pass_flag<=0;O_delay_value<=TAP_COUNT/2;
        O_delay_vaild<=0;O_auto_delay_done<=0;
    end else begin
        O_delay_vaild<=0;
        case(state)
            ST_WAIT_DATA: begin
                O_delay_value<=TAP_COUNT/2;O_delay_vaild<=1;
                wait_cnt<=0;cnt<=0;state<=ST_WAIT_SET;
            end
            ST_WAIT_SET: begin
                if(any_aligned || wait_cnt==WAIT_CYCLES-1) begin
                    scan_tap<=0;state<=ST_SET_TAP;
                end else wait_cnt<=wait_cnt+1'b1;
            end
            ST_SET_TAP: begin
                O_delay_value<=scan_tap;O_delay_vaild<=1;
                cnt<=0;align_cnt<=0;state<=ST_SETTLE;
            end
            ST_SETTLE: begin
                if(cnt==SETTLE_CYCLES-1) begin
                    cnt<=0;pass_flag<=0;state<=ST_TEST;
                end else cnt<=cnt+1'b1;
            end
            ST_TEST: begin
                if(all_aligned) align_cnt<=align_cnt+1'b1;
                if(cnt==TEST_CYCLES-1) begin
                    // Include the final tested sample in the decision.
                    pass_flag<=(align_cnt+all_aligned)>=PASS_THRESH;
                    state<=ST_NEXT;
                end else cnt<=cnt+1'b1;
            end
            ST_NEXT: begin
                if(pass_flag) begin
                    if(!in_run) begin
                        in_run<=1;cur_start<=scan_tap;cur_len<=1;
                    end else cur_len<=cur_len+1'b1;
                end else if(in_run) begin
                    if(cur_len>best_len) begin best_start<=cur_start;best_len<=cur_len;end
                    in_run<=0;cur_len<=0;
                end
                if(scan_tap==TAP_COUNT-1) state<=ST_FIND;
                else begin scan_tap<=scan_tap+1'b1;state<=ST_SET_TAP;end
            end
            ST_FIND: begin
                if(in_run && cur_len>best_len) begin best_start<=cur_start;best_len<=cur_len;end
                state<=ST_APPLY;
            end
            ST_APPLY: begin
                if(best_len!=0) O_delay_value<=best_start+best_len[6:1];
                else O_delay_value<=TAP_COUNT/2;
                O_delay_vaild<=1;state<=ST_DONE;
            end
            ST_DONE: O_auto_delay_done<=1;
            default: state<=ST_WAIT_DATA;
        endcase
    end
end
endmodule
'''
(RTL/'auto_delay_ctl.v').write_bytes(prefix+body.encode('ascii'))

path=RTL/'csi_rx_phy.v'
backup('csi_rx_phy.v')
data=(ROOT/'tools/csi_before_csi_rx_phy.v.txt').read_bytes()
data=data.replace(b'wire                    w_reset_out  ;',b'''wire                    w_reset_out  ;
wire                    w_clock_present_n;
localparam DELAY_TAP_COUNT=(DEVICE=="PH1A") ? 32 : 64;
// Reference-domain clock-presence deassertion is synchronized to byte clock.
// Assertion is asynchronous, so clock loss/reset cannot wait for HS edges.
(* async_reg="true" *) reg [1:0] hs_reset_sync;
always @(posedge w_hs_clk or negedge w_clock_present_n)
    if(!w_clock_present_n) hs_reset_sync<=0;
    else hs_reset_sync<={hs_reset_sync[0],1'b1};
assign w_reset_out=hs_reset_sync[1];''')
data=data.replace(b'r_manual_delay <= r_manual_delay + 1\'b1;',b'''r_manual_delay <= (r_manual_delay==DELAY_TAP_COUNT-1)
                    ? 6'd0 : r_manual_delay+1'b1;''')
data=data.replace(b'.O_reset_out (w_reset_out )',b'.O_reset_out (w_clock_present_n )')
data=data.replace(b'.LAN_DATA_CUNT(10\'h3ff)',b'.TAP_COUNT(DELAY_TAP_COUNT),\n  .LAN_DATA_CUNT(10\'h3ff)')
start=data.index(b'reg  [1:0] r_debug_button_sync;')
end=data.index(b'wire w_debug_release',start)
manual_declarations=data[start:end]
data=data[:start]+data[end:]
start=data.index(b'assign O_hs_div_clk')
data=data[:start]+manual_declarations+data[start:]
path.write_bytes(data)

path=RTL/'csi_rx_packet_handler.v'
data=path.read_bytes()
while b'I_count_enable, I_count_enable,' in data:
    data=data.replace(b'I_count_enable, I_count_enable,',b'I_count_enable,')
while b'if(I_count_enable) if(I_count_enable)' in data:
    data=data.replace(b'if(I_count_enable) if(I_count_enable)',b'if(I_count_enable)')
if b'I_enable, I_count_enable,' not in data:
    data=data.replace(b'input wire I_clock, I_reset_n, I_enable,',b'input wire I_clock, I_reset_n, I_enable, I_count_enable,')
for field in ['O_ecc_errors','O_wc_errors','O_crc_errors','O_raw_packets','O_timeout_errors']:
    old=(field+'<='+field+"+1'b1;").encode()
    new=('if(I_count_enable) '+field+'<='+field+"+1'b1;").encode()
    if new not in data: data=data.replace(old,new)
path.write_bytes(data)

path=RTL/'mipi_csi_rx.v'
data=path.read_bytes()
data=data.replace(b'wire parse_enable=I_enable && delay_done_sync[1];',b'''wire parse_ready=I_enable && delay_done_sync[1];
    reg capture_armed, pixel_frame_start;
    // Calibration must not disable parser feedback used by PHY byte alignment.
    // Only image output is gated; after calibration wait for a NEW complete FS.
    always @(posedge w_hs_div_clk or negedge w_reset_out)
        if(!w_reset_out) begin capture_armed<=0; pixel_frame_start<=0; end
        else begin
            pixel_frame_start<=0;
            if(!parse_ready) capture_armed<=0;
            else if(w_vsync_out) begin capture_armed<=1; pixel_frame_start<=1; end
        end
    wire pixel_enable=parse_ready && capture_armed;''')
data=data.replace(b'assign O_csi_error_pulse=w_packet_error || w_unpack_error || w_fifo_error;',b'assign O_csi_error_pulse=pixel_enable && (w_packet_error || w_unpack_error || w_fifo_error);')
data=data.replace(b'.I_enable        (parse_enable           ),',b'''.I_enable        (I_enable               ),
    .I_count_enable  (pixel_enable),''')
data=data.replace(b'.I_enable       (parse_enable       ),',b'.I_enable       (pixel_enable       ),')
data=data.replace(b'.I_enable             (parse_enable         ),',b'.I_enable             (pixel_enable         ),')
data=data.replace(b'.I_frame_start        (w_vsync_out          ),',b'.I_frame_start        (pixel_frame_start    ),')
path.write_bytes(data)
print('Installed device-accurate eye scan, byte-domain reset release and non-circular calibration/image gate')
