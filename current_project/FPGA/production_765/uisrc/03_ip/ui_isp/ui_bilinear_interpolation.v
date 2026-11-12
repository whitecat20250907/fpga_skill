
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
/*********ui_bilinear_interpolation ******************************
由于RGGB和GBRG的Bayer格式中的三元操作符的条件判断分支是颠倒的，
                 导致在需要插值的地方使用了原始值，在有原始值的地方进行了错误的
                 平均，现在重写修改了此处，让其正确的去进行平均。
--版本号1.0  
*****************************************************************/


// Precision51: preserve native samples through CCM/AWB; tone quantizes to RGB8.
// SAMPLE_BITS controls each native RGB channel; no output precision reduction.
// bayer_ypos is the ACTUAL centre row odd/even flag for every Bayer mode.
// P0..P3 occupy increasing packed 3*SAMPLE_BITS words. Five registered
// stages keep channel sums, divisors, pixels and markers aligned under stall.
module ui_bilinear_interpolation #(parameter SAMPLE_BITS=10, parameter BAYER_MODE="BGGR")(
    input I_clk, I_rst_n, I_tlast, I_tuser, I_tvalid,
    output I_tready,
    input [1:0] I_bayer_mode,
    input bayer_ypos,
    input [12*SAMPLE_BITS-1:0] matrix_last_line, matrix_cur_line, matrix_next_line,
    output O_tlast, O_tuser,
    output [12*SAMPLE_BITS-1:0] O_tdata,
    output O_tvalid,
    input O_tready
);
reg [4:0] valid, last, user;
wire ce=!valid[4] || O_tready;
assign I_tready=ce;
assign O_tvalid=valid[4]; assign O_tlast=last[4]; assign O_tuser=user[4];
localparam [1:0] DEFAULT_BAYER = (BAYER_MODE=="RGGB") ? 2'd0 :
    (BAYER_MODE=="BGGR") ? 2'd1 : (BAYER_MODE=="GRBG") ? 2'd2 : 2'd3;
reg [1:0] frame_bayer_mode;
reg [1:0] requested_bayer_mode;
always @* begin
    case(I_bayer_mode)
        2'd0,2'd1,2'd2,2'd3: requested_bayer_mode=I_bayer_mode;
        default: requested_bayer_mode=DEFAULT_BAYER;
    endcase
end
// Use the incoming selection on the first accepted SOF itself, rather than
// the pre-NBA previous-frame register, while all other beats use the lock.
wire [1:0] beat_bayer_mode=(I_tvalid && I_tuser) ? requested_bayer_mode : frame_bayer_mode;
always @(posedge I_clk or negedge I_rst_n)
    if(!I_rst_n) frame_bayer_mode<=DEFAULT_BAYER;
    else if(I_tvalid && I_tready && I_tuser) frame_bayer_mode<=requested_bayer_mode;
function [1:0] site;
    input [1:0] mode;
    input oddrow, oddcol;
    begin
        if (mode==2'd0) site=(!oddrow&&!oddcol)?0:((oddrow&&oddcol)?2:1);
        else if (mode==2'd1) site=(!oddrow&&!oddcol)?2:((oddrow&&oddcol)?0:1);
        else if (mode==2'd2) site=(!oddrow&&oddcol)?0:((oddrow&&!oddcol)?2:1);
        else site=(!oddrow&&oddcol)?2:((oddrow&&!oddcol)?0:1);
    end
endfunction
always @(posedge I_clk or negedge I_rst_n)
    if (!I_rst_n) begin valid<=0; last<=0; user<=0; end
    else if (ce) begin
        valid<={valid[3:0],I_tvalid};
        last<={last[3:0],I_tvalid&&I_tlast};
        user<={user[3:0],I_tvalid&&I_tuser};
    end
genvar p;
generate for(p=0;p<4;p=p+1) begin: pixel
    wire [SAMPLE_BITS-1:0] tl=matrix_last_line[9*SAMPLE_BITS-1-SAMPLE_BITS*p -:SAMPLE_BITS];
    wire [SAMPLE_BITS-1:0] t =matrix_last_line[8*SAMPLE_BITS-1-SAMPLE_BITS*p -:SAMPLE_BITS];
    wire [SAMPLE_BITS-1:0] tr=matrix_last_line[7*SAMPLE_BITS-1-SAMPLE_BITS*p -:SAMPLE_BITS];
    wire [SAMPLE_BITS-1:0] l =matrix_cur_line [9*SAMPLE_BITS-1-SAMPLE_BITS*p -:SAMPLE_BITS];
    wire [SAMPLE_BITS-1:0] c =matrix_cur_line [8*SAMPLE_BITS-1-SAMPLE_BITS*p -:SAMPLE_BITS];
    wire [SAMPLE_BITS-1:0] r =matrix_cur_line [7*SAMPLE_BITS-1-SAMPLE_BITS*p -:SAMPLE_BITS];
    wire [SAMPLE_BITS-1:0] bl=matrix_next_line[9*SAMPLE_BITS-1-SAMPLE_BITS*p -:SAMPLE_BITS];
    wire [SAMPLE_BITS-1:0] b =matrix_next_line[8*SAMPLE_BITS-1-SAMPLE_BITS*p -:SAMPLE_BITS];
    wire [SAMPLE_BITS-1:0] br=matrix_next_line[7*SAMPLE_BITS-1-SAMPLE_BITS*p -:SAMPLE_BITS];
    reg [SAMPLE_BITS:0] ra, rb, ga, gb, ba, bb;
    reg [1:0] rs, gs, bs;
    reg [SAMPLE_BITS:0] ra0,rb0,ga0,gb0,ba0,bb0;
    reg [1:0] rs0,gs0,bs0,rs1,gs1,bs1;
    reg [SAMPLE_BITS+1:0] rv1,gv1,bv1;
    reg [SAMPLE_BITS-1:0] rv2,gv2,bv2;
    reg [3*SAMPLE_BITS-1:0] rgb3;
    reg [3*SAMPLE_BITS-1:0] rgb4;
    always @* begin
        ra=0; rb=0; ga=0; gb=0; ba=0; bb=0;
        rs=0; gs=0; bs=0;
        if (site(beat_bayer_mode,bayer_ypos,p%2)==0) begin
            ra={1'b0,c};
            ga={1'b0,t}+{1'b0,b}; gb={1'b0,l}+{1'b0,r}; gs=2;
            ba={1'b0,tl}+{1'b0,tr}; bb={1'b0,bl}+{1'b0,br}; bs=2;
        end else if (site(beat_bayer_mode,bayer_ypos,p%2)==2) begin
            ba={1'b0,c};
            ga={1'b0,t}+{1'b0,b}; gb={1'b0,l}+{1'b0,r}; gs=2;
            ra={1'b0,tl}+{1'b0,tr}; rb={1'b0,bl}+{1'b0,br}; rs=2;
        end else begin
            ga={1'b0,c}; rs=1; bs=1;
            if (site(beat_bayer_mode,bayer_ypos,(p%2)==0)==0) begin
                ra={1'b0,l}+{1'b0,r}; ba={1'b0,t}+{1'b0,b};
            end else begin
                ra={1'b0,t}+{1'b0,b}; ba={1'b0,l}+{1'b0,r};
            end
        end
    end
    always @(posedge I_clk or negedge I_rst_n)
        if (!I_rst_n) begin
            ra0<=0;rb0<=0;ga0<=0;gb0<=0;ba0<=0;bb0<=0;
            rs0<=0;gs0<=0;bs0<=0;rs1<=0;gs1<=0;bs1<=0;
            rv1<=0;gv1<=0;bv1<=0; rv2<=0;gv2<=0;bv2<=0;
            rgb3<=0;rgb4<=0;
        end else if (ce) begin
            if (I_tvalid) begin
                ra0<=ra;rb0<=rb;ga0<=ga;gb0<=gb;ba0<=ba;bb0<=bb;
                rs0<=rs;gs0<=gs;bs0<=bs;
            end
            if (valid[0]) begin
                rv1<={1'b0,ra0}+{1'b0,rb0};
                gv1<={1'b0,ga0}+{1'b0,gb0};
                bv1<={1'b0,ba0}+{1'b0,bb0};
                rs1<=rs0;gs1<=gs0;bs1<=bs0;
            end
            if (valid[1]) begin rv2<=rv1>>rs1;gv2<=gv1>>gs1;bv2<=bv1>>bs1; end
            if (valid[2]) rgb3<={rv2,gv2,bv2};
            if (valid[3]) rgb4<=rgb3;
        end
    assign O_tdata[3*SAMPLE_BITS*p +:3*SAMPLE_BITS]=rgb4;
end endgenerate
endmodule
