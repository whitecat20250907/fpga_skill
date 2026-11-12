//--------------------------------------------------------------------------------------------
// CSI-2 接收包处理器 (完全符合Verilog语法)
// 严格遵守：
//   1. 三段式状态机（状态声明、状态转移、输出逻辑）
//   2. Verilog-2001标准
//   3. 统一的命名规范
//--------------------------------------------------------------------------------------------

module csi_rx_packet_handler #(
    parameter MIPI_LAN = 4,
    parameter VC_ID = 0,
    parameter GAP_TIMEOUT = 64,
    parameter WAIT_VALID_LOW = 0
)(
    input wire I_clock, I_reset_n, I_enable, I_count_enable,
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
// Diagnostic events are qualified at the protocol decision edge. The counter
// bank consumes this captured decision one clock later; live enable changes
// must not cancel a pending event or count it twice.
reg stat_raw_event, stat_crc_event, stat_ecc_event;
reg stat_wc_event, stat_timeout_event;
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
        stat_raw_event<=0; stat_crc_event<=0; stat_ecc_event<=0;
        stat_wc_event<=0; stat_timeout_event<=0;
    end else begin
        O_packet_done<=0; O_payload_valid<=0; O_payload_last<=0;
        O_payload_bytes<=0; O_vsync_out<=0; O_in_line<=0;
        O_packet_error<=0;
        stat_raw_event<=0; stat_crc_event<=0; stat_ecc_event<=0;
        stat_wc_event<=0; stat_timeout_event<=0;
        if(!I_enable) begin
            state<=WAIT_HDR; bytes_read<=0; gap_count<=0;
            O_in_frame<=0; raw_packet<=0;
        end else case(state)
            WAIT_HDR: if(I_data_valid) begin
                if(!header_ecc_ok) begin
                    // Release byte/word alignment after an invalid header.
                    stat_ecc_event<=I_count_enable;
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
                            stat_wc_event<=I_count_enable;
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
                            stat_crc_event<=I_count_enable;
                            O_packet_error<=1;
                        end else if(raw_packet && raw_wc_ok)
                            stat_raw_event<=I_count_enable;
                        O_packet_done<=1; drain_count<=3; state<=DRAIN;
                    end
                end else if(gap_count==GAP_TIMEOUT-1) begin
                    stat_timeout_event<=I_count_enable;
                    O_packet_error<=1; O_packet_done<=1;
                    drain_count<=3; state<=DRAIN; gap_count<=0;
                end else gap_count<=gap_count+1'b1;
            end
            DRAIN: begin
                // Allow registered aligner/gearbox data to drain before a new
                // header search. CSI HS bursts require a sync per packet.
                if (WAIT_VALID_LOW) begin
                    if (!I_data_valid) state<=WAIT_HDR;
                end else if(drain_count==0) state<=WAIT_HDR;
                else drain_count<=drain_count-1'b1;
            end
            default: state<=WAIT_HDR;
        endcase
    end
end

// Only registered one-bit event enables enter the independent counter bank.
// No I_enable/I_count_enable gate here: qualification belongs to the prior
// protocol edge, including an event immediately before capture is disabled.
always @(posedge I_clock or negedge I_reset_n) begin
    if(!I_reset_n) begin
        O_raw_packets<=0; O_crc_errors<=0; O_ecc_errors<=0;
        O_wc_errors<=0; O_timeout_errors<=0;
    end else begin
        if(stat_raw_event) O_raw_packets<=O_raw_packets+1'b1;
        if(stat_crc_event) O_crc_errors<=O_crc_errors+1'b1;
        if(stat_ecc_event) O_ecc_errors<=O_ecc_errors+1'b1;
        if(stat_wc_event) O_wc_errors<=O_wc_errors+1'b1;
        if(stat_timeout_event) O_timeout_errors<=O_timeout_errors+1'b1;
    end
end
endmodule
