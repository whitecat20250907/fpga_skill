from pathlib import Path
import shutil

ROOT = Path('E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003')
ISP = ROOT/'fpga/uisrc/03_ip/ui_isp'
BACKUP = ROOT/'evidence/isp_before'
BACKUP.mkdir(exist_ok=True)

def replace(name, body):
    p = ISP/name
    if not (BACKUP/name).exists():
        (BACKUP/name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, BACKUP/name)
    original = (BACKUP/name).read_bytes()
    header = original[:original.index(b'module ')]
    p.write_bytes(header + body.encode('ascii'))

replace('ui_zhenghe.v', r'''
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
''')

replace('image_correction.v', r'''
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
''')

replace('ui_line_buffer_demosaic.v', r'''
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
''')

replace('ui_raw_matrix_3x3_buffer.v', r'''
// Exact-coordinate 4-pixel demosaic window. Input RAW10 has P0 at bits 9:0;
// internal words have P0 at bits 31:24, matching the interpolation window.
// Two 2048x32 line RAMs replace cadence-dependent smoothing. Row y-1 is
// emitted while row y arrives; a final RAM scan emits the last image row.
// Mirror-101 edges preserve Bayer colour parity. Valid holes do not reset
// neighbourhoods. The fixed 96-bit window uses [71:24] for x-1..x+4.
module ui_raw_matrix_3x3_buffer #(parameter data_complete_delay=50)(
    input I_clk, I_rst_n,
    input [12:0] I_img_width, I_img_height,
    input [39:0] I_axi4s_video_tdata,
    input [9:0] I_axi4s_video_tdest,
    input I_axi4s_video_tlast, I_axi4s_video_tvalid, I_axi4s_video_tuser,
    output I_axi4s_video_tready,
    output reg O_tlast, O_tuser, O_tvalid,
    input O_tready,
    output reg bayer_ypos,
    output reg [95:0] matrix_last_line, matrix_cur_line, matrix_next_line
);
(* ram_style="bram" *) reg [31:0] line1[0:2047];
(* ram_style="bram" *) reg [31:0] line2[0:2047];
reg [10:0] x_count, scan_x;
reg [12:0] y_count, width_words, height;
reg [1:0] state;
localparam FEED=0, DRAIN=1, FINISH=2;
reg qvalid, qdrain;
reg [10:0] qx;
reg [12:0] qy;
reg [31:0] qinput, qline1, qline2;
reg pending, flush;
reg [10:0] px;
reg [12:0] py;
reg [31:0] ptop, pcenter, pbottom;
reg [7:0] ltop, lcenter, lbottom;
reg malformed_frame;
wire ce=!O_tvalid || O_tready;
wire sof=I_axi4s_video_tuser;
wire [10:0] ix=sof ? 11'd0 : x_count;
wire [12:0] iy=sof ? 13'd0 : y_count;
wire [12:0] words=sof ? (I_img_width>>2) : width_words;
wire [12:0] rows=sof ? I_img_height : height;
wire [31:0] rawword={I_axi4s_video_tdata[9:2],I_axi4s_video_tdata[19:12],
                      I_axi4s_video_tdata[29:22],I_axi4s_video_tdata[39:32]};
wire accept=I_axi4s_video_tvalid && I_axi4s_video_tready;
assign I_axi4s_video_tready=ce && (state==FEED);
wire row_ok=qvalid && (qdrain || qy!=0);
wire [12:0] center_y=qdrain ? height-1'b1 : qy-1'b1;
wire [31:0] topword=qdrain ? ((height==1)?qline1:qline2) : ((qy==1)?qinput:qline2);
wire [31:0] centerword=qline1;
wire [31:0] bottomword=qdrain ? ((height==1)?qline1:qline2) : qinput;
always @(posedge I_clk or negedge I_rst_n)
    if (!I_rst_n) begin
        x_count<=0; y_count<=0; scan_x<=0; state<=FEED;
        width_words<=I_img_width>>2; height<=I_img_height;
        qvalid<=0; qdrain<=0; qx<=0; qy<=0;
        qinput<=0; qline1<=0; qline2<=0;
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
            matrix_last_line<={24'd0,ltop,ptop,ptop[15:8],24'd0};
            matrix_cur_line <={24'd0,lcenter,pcenter,pcenter[15:8],24'd0};
            matrix_next_line<={24'd0,lbottom,pbottom,pbottom[15:8],24'd0};
            O_tvalid<=!malformed_frame; O_tlast<=1;
            O_tuser<=(py==0)&&(px==0);
            bayer_ypos<=py[0];
            pending<=0; flush<=0;
            if ((state==FINISH)&&(py==height-1'b1)) state<=FEED;
        end
        if (row_ok) begin
            if (qx!=0 && pending) begin
                matrix_last_line<={24'd0,ltop,ptop,topword[31:24],24'd0};
                matrix_cur_line <={24'd0,lcenter,pcenter,centerword[31:24],24'd0};
                matrix_next_line<={24'd0,lbottom,pbottom,bottomword[31:24],24'd0};
                O_tvalid<=!malformed_frame; O_tlast<=0;
                O_tuser<=(py==0)&&(px==0);
                bayer_ypos<=py[0];
            end
            ltop<=(qx==0)?topword[23:16]:ptop[7:0];
            lcenter<=(qx==0)?centerword[23:16]:pcenter[7:0];
            lbottom<=(qx==0)?bottomword[23:16]:pbottom[7:0];
            ptop<=topword; pcenter<=centerword; pbottom<=bottomword;
            px<=qx; py<=center_y; pending<=1;
            flush<=(qx==width_words-1'b1);
        end
        if (accept) begin
            qvalid<=1; qdrain<=0; qx<=ix; qy<=iy;
            qinput<=rawword; qline1<=line1[ix]; qline2<=line2[ix];
            line1[ix]<=rawword; line2[ix]<=line1[ix];
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
            qinput<=0; qline1<=line1[scan_x]; qline2<=line2[scan_x];
            if (scan_x==width_words-1'b1) state<=FINISH;
            else scan_x<=scan_x+1'b1;
        end
    end
endmodule
''')

replace('ui_bilinear_interpolation.v', r'''
// bayer_ypos is the ACTUAL centre row odd/even flag for every Bayer mode.
// P0..P3 occupy increasing 32-bit words in the RGB output. Five registered
// stages keep channel sums, divisors, pixels and markers aligned under stall.
module ui_bilinear_interpolation #(parameter BAYER_MODE="BGGR")(
    input I_clk, I_rst_n, I_tlast, I_tuser, I_tvalid,
    output I_tready,
    input bayer_ypos,
    input [95:0] matrix_last_line, matrix_cur_line, matrix_next_line,
    output O_tlast, O_tuser,
    output [127:0] O_tdata,
    output O_tvalid,
    input O_tready
);
reg [4:0] valid, last, user;
wire ce=!valid[4] || O_tready;
assign I_tready=ce;
assign O_tvalid=valid[4]; assign O_tlast=last[4]; assign O_tuser=user[4];
function [1:0] site;
    input oddrow, oddcol;
    begin
        if (BAYER_MODE=="RGGB") site=(!oddrow&&!oddcol)?0:((oddrow&&oddcol)?2:1);
        else if (BAYER_MODE=="BGGR") site=(!oddrow&&!oddcol)?2:((oddrow&&oddcol)?0:1);
        else if (BAYER_MODE=="GRBG") site=(!oddrow&&oddcol)?0:((oddrow&&!oddcol)?2:1);
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
    wire [7:0] tl=matrix_last_line[71-8*p -:8];
    wire [7:0] t =matrix_last_line[63-8*p -:8];
    wire [7:0] tr=matrix_last_line[55-8*p -:8];
    wire [7:0] l =matrix_cur_line [71-8*p -:8];
    wire [7:0] c =matrix_cur_line [63-8*p -:8];
    wire [7:0] r =matrix_cur_line [55-8*p -:8];
    wire [7:0] bl=matrix_next_line[71-8*p -:8];
    wire [7:0] b =matrix_next_line[63-8*p -:8];
    wire [7:0] br=matrix_next_line[55-8*p -:8];
    reg [8:0] ra, rb, ga, gb, ba, bb;
    reg [1:0] rs, gs, bs;
    reg [8:0] ra0,rb0,ga0,gb0,ba0,bb0;
    reg [1:0] rs0,gs0,bs0,rs1,gs1,bs1;
    reg [9:0] rv1,gv1,bv1;
    reg [7:0] rv2,gv2,bv2;
    reg [23:0] rgb3;
    reg [31:0] rgb4;
    always @* begin
        ra=0; rb=0; ga=0; gb=0; ba=0; bb=0;
        rs=0; gs=0; bs=0;
        if (site(bayer_ypos,p%2)==0) begin
            ra={1'b0,c};
            ga={1'b0,t}+{1'b0,b}; gb={1'b0,l}+{1'b0,r}; gs=2;
            ba={1'b0,tl}+{1'b0,tr}; bb={1'b0,bl}+{1'b0,br}; bs=2;
        end else if (site(bayer_ypos,p%2)==2) begin
            ba={1'b0,c};
            ga={1'b0,t}+{1'b0,b}; gb={1'b0,l}+{1'b0,r}; gs=2;
            ra={1'b0,tl}+{1'b0,tr}; rb={1'b0,bl}+{1'b0,br}; rs=2;
        end else begin
            ga={1'b0,c}; rs=1; bs=1;
            if (site(bayer_ypos,(p%2)==0)==0) begin
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
            if (valid[3]) rgb4<={8'd0,rgb3};
        end
    assign O_tdata[32*p +:32]=rgb4;
end endgenerate
endmodule
''')
