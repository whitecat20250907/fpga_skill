
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
/*********ui_zhenghe ******************************
使用BRAM进�?�FIFO整合，并且不影响下一帧的数据传输
--版本�?1.0  
*****************************************************************/


// Preserve valid holes and markers; a clock-span estimate is not a line length.
// The former RAM smoothing stage could replay unwritten addresses when CSI
// cadence changed. The demosaic now counts accepted pixels itself.
module ui_zhenghe #(
    parameter [8:0] DATA_WIDTH=96,
    parameter [8:0] data_complete_delay=50
)(
    input I_clk, I_rst_n,
    input [12:0] I_img_width,
    input I_tlast, I_tuser,
    input [DATA_WIDTH-1:0] I_tdata,
    input I_tvalid,
    output reg O_tlast, O_tuser,
    output reg [DATA_WIDTH-1:0] O_tdata,
    output reg O_tvalid
);
always @(posedge I_clk or negedge I_rst_n)
    if (!I_rst_n) begin
        O_tvalid<=0; O_tlast<=0; O_tuser<=0; O_tdata<=0;
    end else begin
        O_tvalid<=I_tvalid;
        O_tlast<=I_tvalid && I_tlast;
        O_tuser<=I_tvalid && I_tuser;
        if (I_tvalid) O_tdata<=I_tdata;
    end
endmodule
