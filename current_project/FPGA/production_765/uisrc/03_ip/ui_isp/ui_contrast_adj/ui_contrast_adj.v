
/*******************************MILIANKE*******************************
*Company : MiLianKe Electronic Technology Co., Ltd.
*WebSite:https://www.milianke.com
*TechWeb:https://www.uisrc.com
*tmall-shop:https://milianke.tmall.com
*jd-shop:https://milianke.jd.com
*taobao-shop1: https://milianke.taobao.com
*Create Date: 2024/10/23
*Module Name:
*File Name:
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
/*********ui_Contrast_adj ********************************************
--对比度调节(Contrast)
--版本号1.0   
*****************************************************************/


// Signed contrast arithmetic. A negative (pixel-128) must not be interpreted
// as an unsigned 16-bit value before multiplication by an odd coefficient.
module ui_Contrast_adj #(parameter contrast_level=160)(
    input I_clk,I_rst_n,I_tlast,I_tuser,input [95:0] I_tdata,input I_tvalid,
    output I_tready,output O_tlast,O_tuser,output [95:0] O_tdata,
    output O_tvalid,input O_tready
);
reg [2:0] valid,last,user;
wire ce=!valid[2]||O_tready;
assign I_tready=ce;
assign O_tvalid=valid[2];assign O_tlast=last[2];assign O_tuser=user[2];
function [7:0] clamp;
    input signed [40:0] value;
    begin clamp=(value<0)?8'd0:((value>255)?8'd255:value[7:0]);end
endfunction
always @(posedge I_clk or negedge I_rst_n)
    if(!I_rst_n) begin valid<=0;last<=0;user<=0;end
    else if(ce) begin
        valid<={valid[1:0],I_tvalid};
        last<={last[1:0],I_tvalid&&I_tlast};
        user<={user[1:0],I_tvalid&&I_tuser};
    end
genvar c;
generate for(c=0;c<12;c=c+1) begin: channel
    reg signed [8:0] delta;
    reg signed [40:0] product;
    reg [7:0] value;
    always @(posedge I_clk or negedge I_rst_n)
        if(!I_rst_n) begin delta<=0;product<=0;value<=0;end
        else if(ce) begin
            if(I_tvalid) delta<=$signed({1'b0,I_tdata[8*c+:8]})-9'sd128;
            if(valid[0]) product<=delta*$signed(contrast_level);
            if(valid[1]) value<=clamp((product>>>7)+41'sd128);
        end
    assign O_tdata[8*c+:8]=value;
end endgenerate
endmodule
