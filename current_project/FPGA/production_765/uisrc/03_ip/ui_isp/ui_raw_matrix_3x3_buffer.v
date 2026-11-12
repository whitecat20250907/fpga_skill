
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
/*********ui_raw_matrix_3x3_buffer ******************************
该模块主要是用于3x3矩阵的形成，以及对图像边界像素的处理
在原基�?�上优化了时序，把原来的一些未完全对齐的信号进行�?�齐�?
--版本�?1.0  
*****************************************************************/


// Exact-coordinate 4-pixel demosaic window. Input RAW10 has P0 at bits 9:0;
// internal words have P0 at bits 31:24, matching the interpolation window.
// Two 2048x32 line RAMs replace cadence-dependent smoothing. Row y-1 is
// emitted while row y arrives; a final RAM scan emits the last image row.
// Mirror-101 edges preserve Bayer colour parity. Valid holes do not reset
// neighbourhoods. The fixed 96-bit window uses [71:24] for x-1..x+4.
module ui_raw_matrix_3x3_buffer #(parameter SAMPLE_BITS=10, parameter data_complete_delay=50)(
    input I_clk, I_rst_n,
    input [12:0] I_img_width, I_img_height,
    input [39:0] I_axi4s_video_tdata,
    input [9:0] I_axi4s_video_tdest,
    input I_axi4s_video_tlast, I_axi4s_video_tvalid, I_axi4s_video_tuser,
    output I_axi4s_video_tready,
    output reg O_tlast, O_tuser, O_tvalid,
    input O_tready,
    output reg bayer_ypos,
    output reg [12*SAMPLE_BITS-1:0] matrix_last_line, matrix_cur_line, matrix_next_line
);
reg [10:0] x_count, scan_x;
reg [12:0] y_count, width_words, height;
reg [1:0] state;
localparam FEED=0, DRAIN=1, FINISH=2;
reg qvalid, qdrain;
reg [10:0] qx;
reg [12:0] qy;
reg [4*SAMPLE_BITS-1:0] qinput;
reg pending, flush;
reg [10:0] px;
reg [12:0] py;
reg [4*SAMPLE_BITS-1:0] ptop, pcenter, pbottom;
reg [SAMPLE_BITS-1:0] ltop, lcenter, lbottom;
reg malformed_frame;
wire ce=!O_tvalid || O_tready;
wire sof=I_axi4s_video_tuser;
wire [10:0] ix=sof ? 11'd0 : x_count;
wire [12:0] iy=sof ? 13'd0 : y_count;
wire [12:0] words=sof ? (I_img_width>>2) : width_words;
wire [12:0] rows=sof ? I_img_height : height;
wire [4*SAMPLE_BITS-1:0] rawword={I_axi4s_video_tdata[9 -: SAMPLE_BITS],I_axi4s_video_tdata[19 -: SAMPLE_BITS],
                      I_axi4s_video_tdata[29 -: SAMPLE_BITS],I_axi4s_video_tdata[39 -: SAMPLE_BITS]};
wire accept=I_axi4s_video_tvalid && I_axi4s_video_tready;
assign I_axi4s_video_tready=ce && (state==FEED);
// Alternate the write bank by accepted row. Both banks are read synchronously
// before the current row overwrites its older (y-2) bank. Do not infer a second
// asynchronous line1 read merely to copy it into line2: TD maps that topology
// to distributed RAM. Reuse the vendor SDP template with an explicit read CE;
// its read output has no reset, and holds across downstream backpressure.
wire [10:0] ram_read_addr=accept ? ix : scan_x;
wire ram_read_ce=I_rst_n && ce && (accept || state==DRAIN);
wire ram_write_ce=I_rst_n && accept;
wire [4*SAMPLE_BITS-1:0] bank0_data, bank1_data;
ui_ram_demosaic_eram_infer #(
    .MODE("SDP"), .BYTE_SIZE(1), .INIT_FILE("NONE"), .FILL_REMAIN(0),
    .USE_BYTE_WEA(0), .DATAWIDTH_A(4*SAMPLE_BITS), .WEA_WIDTH(1),
    .REGMODE_A("NOREG"), .WRITEMODE_A("WRITETHROUGH"), .ADDRWIDTH_A(11),
    .USE_BYTE_WEB(0), .DATAWIDTH_B(4*SAMPLE_BITS), .WEB_WIDTH(1),
    .REGMODE_B("NOREG"), .WRITEMODE_B("READBEFOREWRITE"), .ADDRWIDTH_B(11)
) line_bank0 (
    .clka(I_clk), .rsta(1'b0), .cea(ram_write_ce && !iy[0]), .ocea(1'b1),
    .wea(1'b1), .dia(rawword), .addra(ix), .doa(),
    .clkb(I_clk), .rstb(1'b0), .ceb(ram_read_ce), .oceb(1'b1),
    .web(1'b0), .dib({4*SAMPLE_BITS{1'b0}}), .addrb(ram_read_addr), .dob(bank0_data),
    .ecc_sbiterrinj(1'b0), .ecc_dbiterrinj(1'b0), .ecc_pipece(1'b0),
    .ecc_sbiterr(), .ecc_dbiterr(), .ecc_erraddr()
);
ui_ram_demosaic_eram_infer #(
    .MODE("SDP"), .BYTE_SIZE(1), .INIT_FILE("NONE"), .FILL_REMAIN(0),
    .USE_BYTE_WEA(0), .DATAWIDTH_A(4*SAMPLE_BITS), .WEA_WIDTH(1),
    .REGMODE_A("NOREG"), .WRITEMODE_A("WRITETHROUGH"), .ADDRWIDTH_A(11),
    .USE_BYTE_WEB(0), .DATAWIDTH_B(4*SAMPLE_BITS), .WEB_WIDTH(1),
    .REGMODE_B("NOREG"), .WRITEMODE_B("READBEFOREWRITE"), .ADDRWIDTH_B(11)
) line_bank1 (
    .clka(I_clk), .rsta(1'b0), .cea(ram_write_ce && iy[0]), .ocea(1'b1),
    .wea(1'b1), .dia(rawword), .addra(ix), .doa(),
    .clkb(I_clk), .rstb(1'b0), .ceb(ram_read_ce), .oceb(1'b1),
    .web(1'b0), .dib({4*SAMPLE_BITS{1'b0}}), .addrb(ram_read_addr), .dob(bank1_data),
    .ecc_sbiterrinj(1'b0), .ecc_dbiterrinj(1'b0), .ecc_pipece(1'b0),
    .ecc_sbiterr(), .ecc_dbiterr(), .ecc_erraddr()
);
wire center_bank0=qdrain ? height[0] : qy[0];
wire [4*SAMPLE_BITS-1:0] qline1=center_bank0 ? bank0_data : bank1_data;
wire [4*SAMPLE_BITS-1:0] qline2=center_bank0 ? bank1_data : bank0_data;
wire row_ok=qvalid && (qdrain || qy!=0);
wire [12:0] center_y=qdrain ? height-1'b1 : qy-1'b1;
wire [4*SAMPLE_BITS-1:0] topword=qdrain ? ((height==1)?qline1:qline2) : ((qy==1)?qinput:qline2);
wire [4*SAMPLE_BITS-1:0] centerword=qline1;
wire [4*SAMPLE_BITS-1:0] bottomword=qdrain ? ((height==1)?qline1:qline2) : qinput;
always @(posedge I_clk or negedge I_rst_n)
    if (!I_rst_n) begin
        x_count<=0; y_count<=0; scan_x<=0; state<=FEED;
        width_words<=0; height<=0;
        qvalid<=0; qdrain<=0; qx<=0; qy<=0;
        qinput<=0;
        pending<=0; flush<=0; px<=0; py<=0;
        ptop<=0; pcenter<=0; pbottom<=0;
        ltop<=0; lcenter<=0; lbottom<=0;
        O_tvalid<=0; O_tlast<=0; O_tuser<=0; bayer_ypos<=0;
        matrix_last_line<=0; matrix_cur_line<=0; matrix_next_line<=0;
        malformed_frame<=0;
    end else if (ce) begin
        O_tvalid<=0; O_tlast<=0; O_tuser<=0;
        qvalid<=0;
        if (flush && pending) begin
            matrix_last_line<={{3*SAMPLE_BITS{1'b0}},ltop,ptop,ptop[2*SAMPLE_BITS-1 -: SAMPLE_BITS],{3*SAMPLE_BITS{1'b0}}};
            matrix_cur_line <={{3*SAMPLE_BITS{1'b0}},lcenter,pcenter,pcenter[2*SAMPLE_BITS-1 -: SAMPLE_BITS],{3*SAMPLE_BITS{1'b0}}};
            matrix_next_line<={{3*SAMPLE_BITS{1'b0}},lbottom,pbottom,pbottom[2*SAMPLE_BITS-1 -: SAMPLE_BITS],{3*SAMPLE_BITS{1'b0}}};
            O_tvalid<=!malformed_frame; O_tlast<=1;
            O_tuser<=(py==0)&&(px==0);
            bayer_ypos<=py[0];
            pending<=0; flush<=0;
            if ((state==FINISH)&&(py==height-1'b1)) state<=FEED;
        end
        if (row_ok) begin
            if (qx!=0 && pending) begin
                matrix_last_line<={{3*SAMPLE_BITS{1'b0}},ltop,ptop,topword[4*SAMPLE_BITS-1 -: SAMPLE_BITS],{3*SAMPLE_BITS{1'b0}}};
                matrix_cur_line <={{3*SAMPLE_BITS{1'b0}},lcenter,pcenter,centerword[4*SAMPLE_BITS-1 -: SAMPLE_BITS],{3*SAMPLE_BITS{1'b0}}};
                matrix_next_line<={{3*SAMPLE_BITS{1'b0}},lbottom,pbottom,bottomword[4*SAMPLE_BITS-1 -: SAMPLE_BITS],{3*SAMPLE_BITS{1'b0}}};
                O_tvalid<=!malformed_frame; O_tlast<=0;
                O_tuser<=(py==0)&&(px==0);
                bayer_ypos<=py[0];
            end
            ltop<=(qx==0)?topword[3*SAMPLE_BITS-1 -: SAMPLE_BITS]:ptop[SAMPLE_BITS-1:0];
            lcenter<=(qx==0)?centerword[3*SAMPLE_BITS-1 -: SAMPLE_BITS]:pcenter[SAMPLE_BITS-1:0];
            lbottom<=(qx==0)?bottomword[3*SAMPLE_BITS-1 -: SAMPLE_BITS]:pbottom[SAMPLE_BITS-1:0];
            ptop<=topword; pcenter<=centerword; pbottom<=bottomword;
            px<=qx; py<=center_y; pending<=1;
            flush<=(qx==width_words-1'b1);
        end
        if (accept) begin
            qvalid<=1; qdrain<=0; qx<=ix; qy<=iy;
            qinput<=rawword;
            if (sof) begin
                width_words<=words; height<=rows; malformed_frame<=0;
            end
            if (I_axi4s_video_tlast != (ix==words-1'b1)) malformed_frame<=1;
            if (I_axi4s_video_tlast) begin
                x_count<=0; y_count<=iy+1'b1;
                if (iy==rows-1'b1) begin state<=DRAIN; scan_x<=0; end
            end else begin x_count<=ix+1'b1; y_count<=iy; end
        end else if (state==DRAIN) begin
            qvalid<=1; qdrain<=1; qx<=scan_x; qy<=height;
            qinput<=0;
            if (scan_x==width_words-1'b1) state<=FINISH;
            else scan_x<=scan_x+1'b1;
        end
    end
endmodule
