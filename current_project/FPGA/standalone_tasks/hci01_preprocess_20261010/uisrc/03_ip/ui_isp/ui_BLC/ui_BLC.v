
/*******************************MILIANKE*******************************
*Company : MiLianKe Electronic Technology Co., Ltd.
*WebSite:https://www.milianke.com
*TechWeb:https://www.uisrc.com
*tmall-shop:https://milianke.tmall.com
*jd-shop:https://milianke.jd.com
*taobao-shop1: https://milianke.taobao.com
*Create Date: 2023/03/23
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
/*********ui_BLC 黑电平矫正********************************************
--版本号1.0  
*****************************************************************/
`timescale 1ns / 1ps


module ui_BLC #(
    parameter [9:0] Black_level_offset_r0=15,Black_level_offset_r1=15,
    parameter [9:0] Black_level_offset_r2=15,Black_level_offset_r3=15
)(
    input I_clk,I_rst_n,I_tlast,I_tuser,
    input [39:0] I_tdata,input I_tvalid,input [9:0] I_tdest,
    output I_tready,
    output reg O_tlast,O_tuser,output reg [39:0] O_tdata,
    output reg O_tvalid,output reg [9:0] O_tdest,input O_tready
);
wire ce=!O_tvalid||O_tready;
assign I_tready=ce;
wire [39:0] offsets={Black_level_offset_r3,Black_level_offset_r2,
                     Black_level_offset_r1,Black_level_offset_r0};
integer p;
always @(posedge I_clk or negedge I_rst_n)
    if(!I_rst_n) begin O_tlast<=0;O_tuser<=0;O_tvalid<=0;O_tdest<=0;O_tdata<=0;end
    else if(ce) begin
        O_tvalid<=I_tvalid;O_tlast<=I_tvalid&&I_tlast;O_tuser<=I_tvalid&&I_tuser;
        if(I_tvalid) begin
            O_tdest<=I_tdest;
            for(p=0;p<4;p=p+1)
                O_tdata[10*p+:10]<=(I_tdata[10*p+:10]>offsets[10*p+:10])?
                    I_tdata[10*p+:10]-offsets[10*p+:10]:10'd0;
        end
    end
endmodule
