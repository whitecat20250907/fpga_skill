// ============================================================================
// auto_delay_ctl — Eye-Scan 版本 v3
//
// 修复 v2 的致命缺陷：MIPI 时钟启动后 camera 需要 50-100ms 才发第一帧，
// 但 eye-scan 只需 ~19ms，导致全部 tap 测试时无数据，best_len=0 → fallback。
//
// 新增 ST_WAIT_DATA 阶段：
//   0. 先设 tap=32，等待任一 lane 出现 byte_align_done（证明有数据）
//      或超时 ~150ms（2^24 cycles @111MHz），兼容无 camera 场景
//   1. 遍历全部 64 个 tap（0 → 63）
//   2. 每个 tap：settle 256 cycles → 测试 TEST_LEN 个 cycle
//   3. 测试期间计数"4-lane 全部 byte_align"的周期数
//      若 align_cnt >= PASS_THRESH → PASS（容忍 MIPI 包间的消隐间隔）
//   4. 找最长连续 PASS 区间（eye），取中点
//   5. 应用中点 tap 并锁定
//
// 端口保持与原版完全兼容，替换后无需改上层连线
// ============================================================================
`timescale 1ns / 1ps

module auto_delay_ctl #(
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
