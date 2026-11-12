
/*******************************MILIANKE*******************************
*Company : MiLianKe Electronic Technology Co., Ltd.
*WebSite:https://www.milianke.com
*TechWeb:https://www.uisrc.com
*tmall-shop:https://milianke.tmall.com
*jd-shop:https://milianke.jd.com
*taobao-shop1: https://milianke.taobao.com
*Create Date: 2023/08/07
*Module Name:key
*File Name:key.v
*Description: 
*The reference demo provided by Milianke is only used for learning. 
*We cannot ensure that the demo itself is free of bugs, so users 
*should be responsible for the technical problems and consequences
*caused by the use of their own products.
*Copyright: Copyright (c) MiLianKe
*All rights reserved.
*Revision: 1.0
*Signal description
*1) I_ input
*2) O_ output
*3) IO_ input output
*4) S_ system internal signal
*5) _n activ low
*6) _dg debug signal 
*7) _r delay or register
*8) _s state mechine
*********************************************************************/
/*********ui_cfg_imx415 IIC控制模块 ***********
--版本�?1.0
*********************************************************************/

// Transaction-complete sensor initialization, then one explicit stream start.
// CLK_DIV keeps the vendor I2C core. CLOCK_HZ describes the real control clock.
// IMX415 standby exit to XMSTA uses80ms, consistent with Linux imx415_wakeup.
// Transaction-complete sensor initialization, then one explicit stream start.
// CLK_DIV keeps the vendor I2C core. CLOCK_HZ describes the real control clock.
// IMX415 standby exit to XMSTA uses80ms, consistent with Linux imx415_wakeup.
module ui_cfg_imx415 #(
    parameter CLK_DIV=16'd999,
    parameter ENABLE_EXPOSURE=0,
    parameter integer CLOCK_HZ=24000000,
    parameter integer STANDBY_WAIT_US=80000,
    parameter integer BUS_TIMEOUT_US=4000
)(
    input wire I_clk,I_rst_n,
    input wire [1:0] I_cam_mode,
    input wire I_ae_req,
    input wire [7:0] I_ae_data,
    input wire I_ae_override_valid,
    input wire I_ae_exposure_valid,input wire[19:0]I_ae_shr,
    output reg[19:0]O_applied_shr,
    output wire O_cam_scl,
    inout wire IO_cam_sda,
    output reg O_cfg_done,
    output reg O_ae_cfg_done,
    output reg O_ae_write_success,
    output wire O_bus_error
);
function integer us_cycles;
    input integer us;
    begin us_cycles=(CLOCK_HZ/1000000)*us+
        (((CLOCK_HZ%1000000)*us+999999)/1000000)+1;end
endfunction
localparam integer WAIT_CYCLES=us_cycles(STANDBY_WAIT_US);
localparam integer TIMEOUT_CYCLES=us_cycles(BUS_TIMEOUT_US);
localparam [3:0] BOOT=0,PREP_TABLE=1,TX_START=2,TX_BUSY=3,
    TX_END=4,AFTER_TABLE=5,WAIT_WAKEUP=6,AFTER_WAKEUP=7,
    AFTER_XMSTA=8,RUN=9,AFTER_AE=10,ERROR=11,VERIFY_AE=12;
reg [3:0] state,return_state;
reg [1:0] config_mode;
reg [8:0] index;
wire [31:0] table_data;
wire [7:0] table_size;
reg [31:0] write_data;
reg request,transaction_error,error_latched;
reg [31:0] timer;
reg [7:0] boot_count;
reg ae_request_held;
wire busy,core_error;
reg full_exposure,transaction_read;
reg[2:0]ae_step;reg[19:0]held_shr;reg[7:0]held_gain;
wire[7:0]read_value;
wire[19:0]mode_vmax=config_mode==1 ? 20'd4503 : 20'd2283;
wire exposure_request=ENABLE_EXPOSURE&&(I_ae_exposure_valid===1'b1);
function[31:0]ae_word;
 input[2:0]step;input[19:0]shr;input[7:0]gain;
 begin case(step)
  0:ae_word=32'h01013034; // REGHOLD=1
  1:ae_word={shr[7:0],8'h50,8'h30,8'h34};
  2:ae_word={shr[15:8],8'h51,8'h30,8'h34};
  3:ae_word={4'd0,shr[19:16],8'h52,8'h30,8'h34};
  4:ae_word={gain,8'h90,8'h30,8'h34};
  default:ae_word=32'h00013034; // REGHOLD=0
 endcase end
endfunction
assign O_bus_error=error_latched|core_error;
ui_imx415reg X_ui_imx415reg(.MODE(config_mode),.REG_INDEX(index),
    .REG_DATA(table_data),.REG_SIZE(table_size));
ui_i2c #(.WMEN_LEN(4),.RMEN_LEN(1),.CLK_DIV(CLK_DIV)) X_ui_i2c(
    .I_clk(I_clk),.I_rstn(I_rst_n),.O_iic_scl(O_cam_scl),
    .IO_iic_sda(IO_cam_sda),.I_wr_data(write_data),.I_wr_cnt(transaction_read?8'd3:8'd4),
    .O_rd_data(read_value),.I_rd_cnt(transaction_read?8'd1:8'd0),.I_iic_req(request),.I_iic_mode(transaction_read),
    .O_iic_busy(busy),.O_iic_bus_error(core_error),.O_iic_sda_dg());
// Inputs are already synchronized by the caller. Mode is frozen for each
// entire table, and may restart only after a completed I2C transaction.
always @(posedge I_clk or negedge I_rst_n) begin
    if(!I_rst_n) begin
        state<=BOOT;return_state<=AFTER_TABLE;config_mode<=0;index<=0;
        write_data<=0;request<=0;transaction_error<=0;error_latched<=0;
        timer<=0;boot_count<=0;O_cfg_done<=0;O_ae_cfg_done<=1;O_ae_write_success<=0;
        ae_request_held<=0;full_exposure<=0;transaction_read<=0;ae_step<=0;held_shr<=8;held_gain<=32;O_applied_shr<=8;
    end else begin
        O_ae_write_success<=0;
        if(!I_ae_req) ae_request_held<=0;
        if(core_error && (state==TX_BUSY || state==TX_END)) transaction_error<=1;
        case(state)
            BOOT:begin
                O_cfg_done<=0;request<=0;
                if(boot_count==127) begin
                    config_mode<=I_cam_mode;index<=0;error_latched<=0;
                    state<=PREP_TABLE;
                end else boot_count<=boot_count+1'b1;
            end
            PREP_TABLE:begin
                transaction_read<=0;full_exposure<=0;
                // Explicit manual gain survives a mode-table reload. With
                // no override, preserve each mode's original ROM default.
                write_data<={(I_ae_override_valid && table_data[23:8]==16'h3090)
                    ? I_ae_data : table_data[7:0],table_data[15:8],table_data[23:16],8'h34};
                return_state<=AFTER_TABLE;timer<=0;state<=TX_START;
            end
            TX_START:begin
                if(!busy) begin
                    request<=1;timer<=0;transaction_error<=0;state<=TX_BUSY;
                end else if(timer==TIMEOUT_CYCLES-1) begin
                    request<=0;error_latched<=1;O_cfg_done<=0;state<=ERROR;
                end else timer<=timer+1'b1;
            end
            TX_BUSY:begin
                if(busy) begin request<=0;timer<=0;state<=TX_END;end
                else if(timer==TIMEOUT_CYCLES-1) begin
                    request<=0;error_latched<=1;O_cfg_done<=0;state<=ERROR;
                end else timer<=timer+1'b1;
            end
            TX_END:begin
                if(!busy) begin
                    if(transaction_error || core_error) begin
                        error_latched<=1;O_cfg_done<=0;state<=ERROR;
                    end else if(I_cam_mode!=config_mode&&!full_exposure) begin
                        if(return_state==AFTER_AE) O_ae_write_success<=1;
                        O_cfg_done<=0;config_mode<=I_cam_mode;index<=0;O_ae_cfg_done<=1;ae_request_held<=0;
                        state<=PREP_TABLE;
                    end else state<=return_state;
                end else if(timer==TIMEOUT_CYCLES-1) begin
                    request<=0;error_latched<=1;O_cfg_done<=0;state<=ERROR;
                end else timer<=timer+1'b1;
            end
            AFTER_TABLE:begin
                if(index+1==table_size) begin
                    // Leave STANDBY only once the entire table has completed.
                    write_data<=32'h00003034; // slave34, register3000, value00
                    return_state<=AFTER_WAKEUP;timer<=0;state<=TX_START;
                end else begin index<=index+1'b1;state<=PREP_TABLE;end
            end
            AFTER_WAKEUP:begin timer<=0;state<=WAIT_WAKEUP;end
            WAIT_WAKEUP:begin
                if(I_cam_mode!=config_mode) begin
                    O_cfg_done<=0;config_mode<=I_cam_mode;index<=0;O_ae_cfg_done<=1;ae_request_held<=0;state<=PREP_TABLE;
                end else if(timer==WAIT_CYCLES-1) begin
                    write_data<=32'h00023034; // register3002, value00
                    return_state<=AFTER_XMSTA;timer<=0;state<=TX_START;
                end else timer<=timer+1'b1;
            end
            AFTER_XMSTA:begin O_cfg_done<=1;O_applied_shr<=8;state<=RUN;end
            RUN:begin
                if(I_cam_mode!=config_mode) begin
                    O_cfg_done<=0;config_mode<=I_cam_mode;index<=0;O_ae_cfg_done<=1;ae_request_held<=0;state<=PREP_TABLE;
                end else if(I_ae_req && !ae_request_held) begin
                    ae_request_held<=1;O_ae_cfg_done<=0;transaction_read<=0;
                    full_exposure<=exposure_request;held_shr<=I_ae_shr;held_gain<=I_ae_data;ae_step<=0;
                    write_data<=exposure_request ? ae_word(0,I_ae_shr,I_ae_data) : {I_ae_data,8'h90,8'h30,8'h34};
                    return_state<=AFTER_AE;timer<=0;state<=TX_START;
                    if(exposure_request&&(I_ae_shr<8||I_ae_shr>mode_vmax-4||I_ae_data>240))begin
                     error_latched<=1;O_cfg_done<=0;state<=ERROR;
                    end
                end
            end
            AFTER_AE:begin
                if(full_exposure)begin
                    // Read back each group register through the same master.
                    // The source command stays latched through HOLD release.
                    transaction_read<=1;return_state<=VERIFY_AE;timer<=0;state<=TX_START;
                end else begin O_ae_cfg_done<=1;O_ae_write_success<=1;state<=RUN;end
            end
            VERIFY_AE:begin
                transaction_read<=0;
                if(read_value!=write_data[31:24])begin error_latched<=1;O_cfg_done<=0;state<=ERROR;end
                else if(ae_step==5)begin
                    O_applied_shr<=held_shr;O_ae_cfg_done<=1;O_ae_write_success<=1;full_exposure<=0;state<=RUN;
                end else begin
                    ae_step<=ae_step+1'b1;write_data<=ae_word(ae_step+1'b1,held_shr,held_gain);
                    return_state<=AFTER_AE;timer<=0;state<=TX_START;
                end
            end
            ERROR:begin
                request<=0;O_cfg_done<=0;
                // A new mode or caller reset explicitly retries the table.
                if(!busy && I_cam_mode!=config_mode) begin
                    error_latched<=0;transaction_error<=0;O_ae_cfg_done<=1;ae_request_held<=0;
                    config_mode<=I_cam_mode;index<=0;state<=PREP_TABLE;
                end
            end
            default:begin request<=0;O_cfg_done<=0;error_latched<=1;state<=ERROR;end
        endcase
    end
end
endmodule
