
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
/*********ui_image_cut ********************************************
--版本�?1.0  
*****************************************************************/


module ui_image_cut #(
    parameter [12:0] IMG_WIDTH=640,IMG_HEIGHT=480,
    parameter DATA_WIDTH=96,
    parameter SKIP_ROWS_top=2,SKIP_ROWS_bottom=2,SKIP_COLS_left=2,SKIP_COLS_right=2
)(
    input I_clk,I_rst_n,input [12:0] I_img_width,I_img_height,
    input I_tlast,I_tuser,input [DATA_WIDTH-1:0] I_tdata,input I_tvalid,
    output I_tready,output reg O_tlast,O_tuser,
    output reg [DATA_WIDTH-1:0] O_tdata,output reg O_tvalid,input O_tready
);
reg [12:0] h_cnt,v_cnt;
wire ce=!O_tvalid||O_tready;
assign I_tready=ce;
wire [12:0] x=I_tuser?13'd0:h_cnt;
wire [12:0] y=I_tuser?13'd0:v_cnt;
wire [12:0] words=I_img_width>>2;
wire skip=(y<SKIP_ROWS_top)||(y+SKIP_ROWS_bottom>=I_img_height)||
          (x<SKIP_COLS_left)||(x+SKIP_COLS_right>=words);
always @(posedge I_clk or negedge I_rst_n)
    if(!I_rst_n) begin h_cnt<=0;v_cnt<=0;O_tlast<=0;O_tuser<=0;O_tvalid<=0;O_tdata<=0;end
    else if(ce) begin
        O_tvalid<=I_tvalid;O_tlast<=I_tvalid&&I_tlast;O_tuser<=I_tvalid&&I_tuser;
        if(I_tvalid) begin
            O_tdata<=skip?{DATA_WIDTH{1'b0}}:I_tdata;
            if(I_tlast) begin h_cnt<=0;v_cnt<=y+1'b1;end
            else begin h_cnt<=x+1'b1;v_cnt<=y;end
        end
    end
endmodule
