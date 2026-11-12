/*****************************************************************
Company : MiLianKe Electronic Technology Co., Ltd.
WebSite:https://www.milianke.com
TechWeb:https://www.uisrc.com
tmall-shop:https://milianke.tmall.com
jd-shop:https://milianke.jd.com
taobao-shop: https://milianke.taobao.com
Description: 
The reference demo provided by Milianke is only used for learning. 
We cannot ensure that the demo itself is free of bugs, so users 
should be responsible for the technical problems and consequences
caused by the use of their own products.
@Author      :   XiaoQingquan 
@Time        :   2024/12 
version:     :   1.0
@Description :   消减图像的�?�余的�???
*****************************************************************/


module image_correction #(parameter DATA_WIDTH=40, TDEST_WIDTH=10)(
    input I_clk, I_rst_n,
    input [14:0] I_v_start, I_v_end, I_h_end,
    input [DATA_WIDTH-1:0] I_raw_tdata,
    input [TDEST_WIDTH-1:0] I_raw_tdest,
    input I_raw_tlast, I_raw_tvalid, I_raw_tuser,
    output I_raw_tready,
    output reg [DATA_WIDTH-1:0] O_raw_tdata,
    output reg O_raw_tlast,
    output reg [TDEST_WIDTH-1:0] O_raw_tdest,
    output reg O_raw_tvalid, O_raw_tuser,
    input O_raw_tready
);
reg [14:0] h_cnt, v_cnt;
wire ce = !O_raw_tvalid || O_raw_tready;
wire [14:0] x = I_raw_tuser ? 15'd0 : h_cnt;
wire [14:0] y = I_raw_tuser ? 15'd0 : v_cnt;
wire selected = (y>I_v_start)&&(y<I_v_end)&&(x>0)&&(x<I_h_end);
assign I_raw_tready=ce;
always @(posedge I_clk or negedge I_rst_n)
    if (!I_rst_n) begin
        h_cnt<=0; v_cnt<=0;
        O_raw_tvalid<=0; O_raw_tlast<=0; O_raw_tuser<=0;
        O_raw_tdata<=0; O_raw_tdest<=0;
    end else if (ce) begin
        O_raw_tvalid<=I_raw_tvalid && selected;
        O_raw_tlast<=I_raw_tvalid && selected && (x==I_h_end-1'b1);
        O_raw_tuser<=I_raw_tvalid && selected && (x==1) && (y==I_v_start+1'b1);
        if (I_raw_tvalid) begin
            O_raw_tdata<=I_raw_tdata; O_raw_tdest<=I_raw_tdest;
            if (I_raw_tlast) begin h_cnt<=0; v_cnt<=y+1'b1; end
            else begin h_cnt<=x+1'b1; v_cnt<=y; end
        end else if (I_raw_tuser) begin
            // CSI frame-start may precede the first RAW payload beat.
            h_cnt<=0; v_cnt<=0;
        end
    end
endmodule
