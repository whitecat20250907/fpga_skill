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
/*********ui_line_buffer_demosaic ******************************
--版本�?1.0  
*****************************************************************/


// One line in accepted beats. Synchronous RAM read-before-write, same address.
// SOF selects address zero for the CURRENT transfer, not a later transfer.
module ui_line_buffer_demosaic(
    input I_clk, I_rst_n,
    input [12:0] I_img_width,
    input I_tuser, I_valid,
    input [32:0] I_data,
    output reg O_valid,
    output [32:0] O_data
);
reg [10:0] address;
reg primed;
wire [10:0] addr=I_tuser ? 11'd0 : address;
wire [12:0] words=I_img_width>>2;
ui_ram_demosaic ram(
    .clka(I_clk), .wea(I_valid), .dia(I_data), .addra(addr), .doa(),
    .clkb(I_clk), .web(1'b0), .dib(33'd0), .addrb(addr), .dob(O_data)
);
always @(posedge I_clk or negedge I_rst_n)
    if (!I_rst_n) begin address<=0; primed<=0; O_valid<=0; end
    else begin
        O_valid<=I_valid && primed && !I_tuser;
        if (I_valid) begin
            address <= (addr==words-1'b1) ? 11'd0 : addr+1'b1;
            if (I_tuser) primed<=(words==1);
            else if (addr==words-1'b1) primed<=1;
        end
    end
endmodule
