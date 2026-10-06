from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RTL = ROOT / 'fpga/uisrc/03_ip/mipi_csi_2'

def install(name, body):
    path = RTL / name
    original = path.read_bytes()
    backup = ROOT / 'tools' / ('csi_before_' + name + '.txt')
    if not backup.exists():
        backup.write_bytes(original)
    prefix = original.split(b'module ', 1)[0]
    path.write_bytes(prefix + body.encode('ascii'))

install('csi_rx_packet_handler.v', r'''module csi_rx_packet_handler #(
    parameter MIPI_LAN = 4,
    parameter VC_ID = 0,
    parameter GAP_TIMEOUT = 64
)(
    input wire I_clock, I_reset_n, I_enable,
    input wire [31:0] I_data,
    input wire I_data_valid,
    output reg O_packet_done,
    output wire O_sync_wait,
    output reg [31:0] O_payload_out,
    output reg O_payload_valid,
    output reg [2:0] O_payload_bytes,
    output reg O_payload_last,
    output reg O_vsync_out,
    output reg O_in_frame,
    output reg O_in_line,
    output reg O_packet_error,
    output reg [31:0] O_raw_packets,
    output reg [31:0] O_crc_errors,
    output reg [31:0] O_ecc_errors,
    output reg [31:0] O_wc_errors,
    output reg [31:0] O_timeout_errors
);
// A 32-bit word contains up to four consecutive CSI bytes, lane 0 first.
// WC describes payload ONLY. CRC occupies the next two bytes, including when
// those bytes share the final payload word. Padding is never a RAW10 byte.
localparam [1:0] WAIT_HDR=0, RX_BODY=1, DRAIN=2;
reg [1:0] state;
reg [15:0] packet_len;
reg [16:0] bytes_read;
reg raw_packet, raw_wc_ok, selected_vc;
reg [15:0] crc_calc, crc_rx;
reg [15:0] gap_count;
reg [2:0] drain_count;
wire [7:0] expected_ecc;
wire [5:0] packet_type = I_data[5:0];
wire [15:0] header_wc = I_data[23:8];
wire header_ecc_ok = I_data[31:24] == expected_ecc;
wire header_vc_ok = I_data[7:6] == VC_ID[1:0];
csi_rx_hdr_ecc ecc_inst(.data(I_data[23:0]), .ecc(expected_ecc));

// Reflected CRC-16 polynomial x^16+x^12+x^5+1, init FFFF, no final xor.
// This equals the local DSI crc16_8b.v equations and CSI transmitted byte order.
function [15:0] crc_byte;
    input [15:0] crc;
    input [7:0] data;
    reg [15:0] v;
    integer n;
    begin
        v=crc;
        for(n=0;n<8;n=n+1)
            if(v[0]^data[n]) v=(v>>1)^16'h8408;
            else v=v>>1;
        crc_byte=v;
    end
endfunction

integer b;
reg [16:0] byte_pos;
reg [15:0] next_crc, next_crc_rx;
reg [2:0] payload_n;
reg [31:0] payload_masked;
always @(*) begin
    next_crc=crc_calc;
    next_crc_rx=crc_rx;
    payload_n=0;
    payload_masked=0;
    byte_pos=0;
    for(b=0;b<4;b=b+1) begin
        byte_pos=bytes_read+b;
        if(byte_pos < {1'b0,packet_len}) begin
            next_crc=crc_byte(next_crc,I_data[b*8+:8]);
            payload_masked[b*8+:8]=I_data[b*8+:8];
            payload_n=payload_n+1'b1;
        end else if(byte_pos == {1'b0,packet_len})
            next_crc_rx[7:0]=I_data[b*8+:8];
        else if(byte_pos == ({1'b0,packet_len}+17'd1))
            next_crc_rx[15:8]=I_data[b*8+:8];
    end
end
assign O_sync_wait = state == WAIT_HDR;

always @(posedge I_clock or negedge I_reset_n) begin
    if(!I_reset_n) begin
        state<=WAIT_HDR; packet_len<=0; bytes_read<=0;
        raw_packet<=0; raw_wc_ok<=0; selected_vc<=0;
        crc_calc<=16'hffff; crc_rx<=0; gap_count<=0; drain_count<=0;
        O_packet_done<=0; O_payload_out<=0; O_payload_valid<=0;
        O_payload_bytes<=0; O_payload_last<=0; O_vsync_out<=0;
        O_in_frame<=0; O_in_line<=0; O_packet_error<=0;
        O_raw_packets<=0; O_crc_errors<=0; O_ecc_errors<=0;
        O_wc_errors<=0; O_timeout_errors<=0;
    end else begin
        O_packet_done<=0; O_payload_valid<=0; O_payload_last<=0;
        O_payload_bytes<=0; O_vsync_out<=0; O_in_line<=0;
        O_packet_error<=0;
        if(!I_enable) begin
            state<=WAIT_HDR; bytes_read<=0; gap_count<=0;
            O_in_frame<=0; raw_packet<=0;
        end else case(state)
            WAIT_HDR: if(I_data_valid) begin
                if(!header_ecc_ok) begin
                    // Release byte/word alignment after an invalid header.
                    O_ecc_errors<=O_ecc_errors+1'b1;
                    O_packet_error<=1; O_packet_done<=1;
                    drain_count<=3; state<=DRAIN;
                end else if(packet_type <= 6'h0f) begin
                    if(header_vc_ok && packet_type==0) begin
                        O_in_frame<=1; O_vsync_out<=1;
                    end
                    if(header_vc_ok && packet_type==1) O_in_frame<=0;
                    O_packet_done<=1; drain_count<=3; state<=DRAIN;
                end else begin
                    packet_len<=header_wc; bytes_read<=0;
                    crc_calc<=16'hffff; crc_rx<=0; gap_count<=0;
                    selected_vc<=header_vc_ok;
                    raw_packet<=header_vc_ok && packet_type==6'h2b;
                    raw_wc_ok<=header_wc!=0 && (header_wc%16'd5)==0;
                    if(header_vc_ok && packet_type==6'h2b) begin
                        if(header_wc==0 || (header_wc%16'd5)!=0) begin
                            O_wc_errors<=O_wc_errors+1'b1;
                            O_packet_error<=1;
                        end else O_in_line<=1;
                    end
                    state<=RX_BODY;
                end
            end
            RX_BODY: begin
                if(I_data_valid) begin
                    gap_count<=0;
                    crc_calc<=next_crc; crc_rx<=next_crc_rx;
                    bytes_read<=bytes_read+17'd4;
                    if(payload_n!=0 && raw_packet && raw_wc_ok && O_in_frame) begin
                        O_payload_out<=payload_masked;
                        O_payload_valid<=1; O_payload_bytes<=payload_n;
                        O_payload_last<=bytes_read+17'd4 >= {1'b0,packet_len};
                    end
                    if(bytes_read+17'd4 >= {1'b0,packet_len}+17'd2) begin
                        if(next_crc!=next_crc_rx && selected_vc) begin
                            O_crc_errors<=O_crc_errors+1'b1;
                            O_packet_error<=1;
                        end else if(raw_packet && raw_wc_ok)
                            O_raw_packets<=O_raw_packets+1'b1;
                        O_packet_done<=1; drain_count<=3; state<=DRAIN;
                    end
                end else if(gap_count==GAP_TIMEOUT-1) begin
                    O_timeout_errors<=O_timeout_errors+1'b1;
                    O_packet_error<=1; O_packet_done<=1;
                    drain_count<=3; state<=DRAIN; gap_count<=0;
                end else gap_count<=gap_count+1'b1;
            end
            DRAIN: begin
                // Allow registered aligner/gearbox data to drain before a new
                // header search. CSI HS bursts require a sync per packet.
                if(drain_count==0) state<=WAIT_HDR;
                else drain_count<=drain_count-1'b1;
            end
            default: state<=WAIT_HDR;
        endcase
    end
end
endmodule
''')

install('csi_rx_10bit_unpack.v', r'''module csi_rx_10bit_unpack (
    input wire I_clock, I_reset_n, I_enable,
    input wire I_line_in,
    input wire [31:0] I_data_in,
    input wire I_din_valid,
    input wire [2:0] I_din_bytes,
    input wire I_din_last,
    output reg [39:0] O_data_out,
    output reg O_dout_valid,
    output reg O_dout_last,
    output reg O_unpack_error
);
// Residual bytes are 0..4, in low byte-first order. Up to four new bytes
// complete at most one RAW10 group. The byte-count, not valid gaps, ends a line.
reg [63:0] byte_buffer;
reg [2:0] byte_count;
reg [63:0] combined;
reg [3:0] total;
integer b;
always @(*) begin
    combined=byte_buffer;
    total={1'b0,byte_count}+{1'b0,I_din_bytes};
    for(b=0;b<4;b=b+1)
        if(b<I_din_bytes) combined[(byte_count+b)*8+:8]=I_data_in[b*8+:8];
end
function [39:0] mipi_unpack;
    input [39:0] p;
    begin
        mipi_unpack[9:0]={p[7:0],p[33:32]};
        mipi_unpack[19:10]={p[15:8],p[35:34]};
        mipi_unpack[29:20]={p[23:16],p[37:36]};
        mipi_unpack[39:30]={p[31:24],p[39:38]};
    end
endfunction
always @(posedge I_clock or negedge I_reset_n) begin
    if(!I_reset_n) begin
        byte_buffer<=0; byte_count<=0;
        O_data_out<=0; O_dout_valid<=0; O_dout_last<=0; O_unpack_error<=0;
    end else begin
        O_dout_valid<=0; O_dout_last<=0; O_unpack_error<=0;
        if(!I_enable || I_line_in) begin
            byte_buffer<=0; byte_count<=0;
        end else if(I_din_valid) begin
            if(I_din_bytes==0 || I_din_bytes>4) begin
                byte_buffer<=0; byte_count<=0; O_unpack_error<=1;
            end else if(total>=5) begin
                O_data_out<=mipi_unpack(combined[39:0]);
                O_dout_valid<=1;
                O_dout_last<=I_din_last && total==5;
                byte_buffer<=combined>>40; byte_count<=total-5;
                if(I_din_last && total!=5) begin
                    O_unpack_error<=1; byte_buffer<=0; byte_count<=0;
                end
            end else begin
                byte_buffer<=combined; byte_count<=total;
                if(I_din_last) begin
                    O_unpack_error<=1; byte_buffer<=0; byte_count<=0;
                end
            end
        end
    end
end
endmodule
''')

install('csi_rx_vid2stream.v', r'''module csi_rx_vid2stream(
    input wire I_data_clk, I_reset_n, I_enable,
    input wire I_packet_done, I_packet_line, I_packet_frame,
    input wire I_frame_start,
    input wire [39:0] I_data_unpack,
    input wire I_dout_unpack_valid, I_dout_unpack_last,
    input wire m_axis_video_aclk, m_axis_video_aresetn,
    input wire m_axis_video_tready,
    output wire m_axis_video_tuser, m_axis_video_tlast, m_axis_video_tvalid,
    output wire [39:0] m_axis_video_tdata,
    output reg [31:0] O_fifo_overflows,
    output reg O_overflow_pulse
);
// Preserve explicit RAW10 end-of-line through the asynchronous pixel FIFO.
// RAW10's natural 4/5 duty cycle must NEVER be interpreted as a line ending.
wire [41:0] rdata;
wire full, empty;
reg frame_start_pending;
reg frame_level_d;
wire frame_start=I_frame_start || (I_packet_frame && !frame_level_d);
wire write_beat=I_enable && I_dout_unpack_valid && !full;
always @(posedge I_data_clk or negedge I_reset_n) begin
    if(!I_reset_n) begin
        frame_start_pending<=0; frame_level_d<=0;
        O_fifo_overflows<=0; O_overflow_pulse<=0;
    end else begin
        frame_level_d<=I_packet_frame;
        O_overflow_pulse<=0;
        if(!I_enable) frame_start_pending<=0;
        else if(frame_start) frame_start_pending<=1;
        else if(write_beat) frame_start_pending<=0;
        if(I_enable && I_dout_unpack_valid && full) begin
            O_fifo_overflows<=O_fifo_overflows+1'b1;
            O_overflow_pulse<=1;
        end
    end
end
assign m_axis_video_tvalid = m_axis_video_aresetn && !empty;
assign m_axis_video_tuser = m_axis_video_tvalid && rdata[0];
assign m_axis_video_tlast = m_axis_video_tvalid && rdata[1];
assign m_axis_video_tdata = rdata[41:2];
mipi_sfifo #(
    .DATA_WIDTH_W(42), .DATA_WIDTH_R(42),
    .ADDR_WIDTH_W(13), .ADDR_WIDTH_R(13),
    .AL_FULL_NUM(4096), .AL_EMPTY_NUM(2),
    .SHOW_AHEAD_EN(1'b1), .OUTREG_EN("NOREG")
) hs_data_fifo (
    .rst(!I_reset_n || !m_axis_video_aresetn),
    .clkw(I_data_clk), .we(write_beat),
    .di({I_data_unpack,I_dout_unpack_last,frame_start_pending || frame_start}),
    .full_flag(full), .afull(), .aempty(), .valid(),
    .clkr(m_axis_video_aclk), .re(m_axis_video_tready && m_axis_video_tvalid),
    .dout(rdata), .empty_flag(empty), .rdusedw(), .wrusedw()
);
endmodule
''')

path=RTL/'mipi_csi_rx.v'
backup=ROOT/'tools/csi_before_mipi_csi_rx.v.txt'
if not backup.exists(): backup.write_bytes(path.read_bytes())
data=backup.read_bytes()
data=data.replace(b'output wire [5:0]         O_dbg_best_len',b'''output wire [5:0]         O_dbg_best_len,
    // Diagnostic counters are in O_hs_div_clk domain: snapshot/handshake at CDC.
    output wire [31:0] O_csi_raw_packets,
    output wire [31:0] O_csi_crc_errors,
    output wire [31:0] O_csi_ecc_errors,
    output wire [31:0] O_csi_wc_errors,
    output wire [31:0] O_csi_timeout_errors,
    output wire [31:0] O_csi_fifo_overflows,
    output wire O_csi_error_pulse''')
needle=b'   assign O_hs_div_clk = w_hs_div_clk;'
data=data.replace(needle,b'''    wire [2:0] w_payload_bytes;
    wire w_payload_last, w_unpack_last, w_packet_error;
    wire w_unpack_error, w_fifo_error;
    reg [1:0] delay_done_sync;
    always @(posedge w_hs_div_clk or negedge w_reset_out)
        if(!w_reset_out) delay_done_sync<=0;
        else delay_done_sync<={delay_done_sync[0],O_auto_delay_done};
    wire parse_enable=I_enable && delay_done_sync[1];
    assign O_csi_error_pulse=w_packet_error || w_unpack_error || w_fifo_error;
'''+needle)
data=data.replace(b'.I_enable        (I_enable               ),',b'.I_enable        (parse_enable           ),')
data=data.replace(b'.O_in_line       (w_in_line              )',b'''.O_in_line       (w_in_line              ),
    .O_payload_bytes (w_payload_bytes),
    .O_payload_last  (w_payload_last),
    .O_packet_error  (w_packet_error),
    .O_raw_packets   (O_csi_raw_packets),
    .O_crc_errors    (O_csi_crc_errors),
    .O_ecc_errors    (O_csi_ecc_errors),
    .O_wc_errors     (O_csi_wc_errors),
    .O_timeout_errors(O_csi_timeout_errors)''')
data=data.replace(b'.I_enable       (I_enable           ),',b'.I_enable       (parse_enable       ),')
data=data.replace(b'.I_din_valid    (w_payload_valid    ),',b'''.I_din_valid    (w_payload_valid    ),
    .I_din_bytes    (w_payload_bytes),
    .I_din_last     (w_payload_last),''')
data=data.replace(b'.O_dout_valid   (w_dout_unpack_valid)',b'''.O_dout_valid   (w_dout_unpack_valid),
    .O_dout_last    (w_unpack_last),
    .O_unpack_error (w_unpack_error)''')
data=data.replace(b'.I_reset_n            (I_reset_n            ),',b'''.I_reset_n            (w_reset_out          ),
    .I_enable             (parse_enable         ),
    .I_frame_start        (w_vsync_out          ),
    .I_dout_unpack_last   (w_unpack_last        ),
    .O_fifo_overflows     (O_csi_fifo_overflows  ),
    .O_overflow_pulse     (w_fifo_error          ),''')
path.write_bytes(data)
print('Installed exact-WC, CRC diagnostics, RAW10 byte-count/end-line and AXI FIFO fixes')
