// Protocol-qualified calibration. A byte-valid streak can occur while every
// payload CRC is wrong; it is not a passing sampling point.
`timescale 1ns/1ps
module auto_delay_ctl #(
    parameter MIPI_LAN=4, parameter LAN_DATA_CUNT=10'h3ff,
    parameter TAP_COUNT=64,
    parameter TEST_CYCLES=2227500, //20ms at111.375MHz BYTE
    parameter SETTLE_CYCLES=32768, //294us: exceeds even a65535-byte packet
    parameter WAIT_CYCLES=16777216,
    parameter PASS_THRESH=64 //CRC-good RAW packets, not aligned byte cycles
)(
    input wire I_byte_clk,I_reset_n,
    input wire [MIPI_LAN-1:0] I_byte_align_done,
    input wire I_raw_good,I_packet_error,
    output reg [5:0] O_delay_value,
    output reg O_delay_vaild,O_auto_delay_done,
    output wire [5:0] O_dbg_best_len
);
localparam [3:0] ST_WAIT_DATA=0,ST_WAIT_SET=1,ST_SET_TAP=2,ST_SETTLE=3,
    ST_TEST=4,ST_NEXT=5,ST_FIND=6,ST_APPLY=7,ST_DONE=8;
localparam CNT_WIDTH=$clog2(((TEST_CYCLES>SETTLE_CYCLES)?TEST_CYCLES:SETTLE_CYCLES)+1);
localparam GOOD_WIDTH=$clog2(PASS_THRESH+1);
localparam WAIT_WIDTH=(WAIT_CYCLES>1)?$clog2(WAIT_CYCLES):1;
reg [3:0] state;
reg [5:0] scan_tap,cur_start,best_start;
reg [6:0] cur_len,best_len;
reg in_run,pass_flag,bad_seen;
reg [CNT_WIDTH-1:0] cnt;
reg [GOOD_WIDTH-1:0] good_count;
reg [WAIT_WIDTH-1:0] wait_cnt;
assign O_dbg_best_len=best_len[6]?6'd63:best_len[5:0];
always @(posedge I_byte_clk or negedge I_reset_n) begin
    if(!I_reset_n) begin
        state<=ST_WAIT_DATA;scan_tap<=0;cnt<=0;good_count<=0;bad_seen<=0;wait_cnt<=0;
        cur_start<=0;cur_len<=0;best_start<=0;best_len<=0;in_run<=0;pass_flag<=0;
        O_delay_value<=TAP_COUNT/2;O_delay_vaild<=0;O_auto_delay_done<=0;
    end else begin
        O_delay_vaild<=0;
        case(state)
            ST_WAIT_DATA:begin
                O_delay_value<=TAP_COUNT/2;O_delay_vaild<=1;O_auto_delay_done<=0;
                wait_cnt<=0;cnt<=0;cur_start<=0;cur_len<=0;best_start<=0;best_len<=0;
                in_run<=0;pass_flag<=0;state<=ST_WAIT_SET;
            end
            ST_WAIT_SET:begin
                if((|I_byte_align_done) || wait_cnt==WAIT_CYCLES-1) begin scan_tap<=0;state<=ST_SET_TAP;end
                else wait_cnt<=wait_cnt+1'b1;
            end
            ST_SET_TAP:begin
                O_delay_value<=scan_tap;O_delay_vaild<=1;cnt<=0;good_count<=0;bad_seen<=0;state<=ST_SETTLE;
            end
            ST_SETTLE:begin
                if(cnt==SETTLE_CYCLES-1) begin cnt<=0;good_count<=0;bad_seen<=0;pass_flag<=0;state<=ST_TEST;end
                else cnt<=cnt+1'b1;
            end
            ST_TEST:begin
                if(I_raw_good && good_count<PASS_THRESH) good_count<=good_count+1'b1;
                if(I_packet_error) bad_seen<=1;
                if(cnt==TEST_CYCLES-1) begin
                    pass_flag<=(good_count+I_raw_good)>=PASS_THRESH && !(bad_seen||I_packet_error);
                    state<=ST_NEXT;
                end else cnt<=cnt+1'b1;
            end
            ST_NEXT:begin
                if(pass_flag) begin
                    if(!in_run) begin in_run<=1;cur_start<=scan_tap;cur_len<=1;end
                    else cur_len<=cur_len+1'b1;
                end else if(in_run) begin
                    if(cur_len>best_len) begin best_start<=cur_start;best_len<=cur_len;end
                    in_run<=0;cur_len<=0;
                end
                if(scan_tap==TAP_COUNT-1) state<=ST_FIND;
                else begin scan_tap<=scan_tap+1'b1;state<=ST_SET_TAP;end
            end
            ST_FIND:begin
                if(in_run && cur_len>best_len) begin best_start<=cur_start;best_len<=cur_len;end
                state<=ST_APPLY;
            end
            ST_APPLY:begin
                if(best_len!=0) begin
                    O_delay_value<=best_start+best_len[6:1];O_delay_vaild<=1;state<=ST_DONE;
                end else begin
                    // No fabricated calibration-done or unqualified fallback.
                    // Parser feedback remains enabled for a fresh sweep.
                    O_auto_delay_done<=0;state<=ST_WAIT_DATA;
                end
            end
            ST_DONE:O_auto_delay_done<=1;
            default:begin O_auto_delay_done<=0;state<=ST_WAIT_DATA;end
        endcase
    end
end
endmodule
