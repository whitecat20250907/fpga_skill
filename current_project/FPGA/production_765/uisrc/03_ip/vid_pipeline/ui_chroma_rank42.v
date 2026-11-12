// Candidate46 five-bank collision-independent chroma filter; real camera mode0 by reset. Four RGB pixels per accepted beat, P0 in bits23:0 (R23:16).
// Integer reversible YCoCg; independently rank signed Co/Cg, retain centre Y.
// A reconstruction outside RGB8 returns the entire original centre pixel.
// Every register and line-memory read freezes together under backpressure.
`timescale 1ns/1ps
`default_nettype none
module ui_chroma_rank5_core #(parameter ENABLE=1)(
 input wire clk,rst_n,input wire [479:0] samples,input wire valid,input wire last,user,
 input wire [27:0] geometry,output wire ready,output wire [95:0] data,
 output wire out_valid,out_last,out_user,output wire [27:0] out_geometry,
 output wire [3:0] fallback,input wire out_ready
);
 wire ce=!out_valid || out_ready;
 assign ready=ce;
 // One common-CE register separates window RAM/mux from RGB arithmetic.
 reg [479:0] samples_r;
 reg sample_valid,sample_last,sample_user;
 reg [27:0] sample_geometry;
 always @(posedge clk or negedge rst_n) begin
  if(!rst_n) begin sample_valid<=0;sample_last<=0;sample_user<=0;end
  else if(ce) begin sample_valid<=valid;sample_last<=last;sample_user<=user;end
 end
 always @(posedge clk) if(ce) begin samples_r<=samples;sample_geometry<=geometry;end
 reg [7:0] vp,lp,up;
 reg [27:0] gp[0:7];
 reg [95:0] original[0:6];
 reg [31:0] yy[0:5];
 reg signed [8:0] co[0:5][0:19],cg[0:5][0:19];
 reg signed [9:0] tt[0:3],cco[0:3],ccg[0:3],co_floor_half[0:3],co_ceil_half[0:3];
 reg [95:0] result;
 reg [3:0] bad;
 assign data=result;assign fallback=bad;
 assign out_valid=vp[7];assign out_last=lp[7];assign out_user=up[7];
 assign out_geometry=gp[7];
 function [25:0] forward;
  input [23:0] rgb;
  reg signed [9:0] r,g,b,c,t,d,y;
  begin
   r=$signed({2'b00,rgb[23:16]});g=$signed({2'b00,rgb[15:8]});b=$signed({2'b00,rgb[7:0]});
   c=r-b;t=(r+b)>>>1;d=g-t;y=(g+t)>>>1;
   forward={y[7:0],c[8:0],d[8:0]};
  end
 endfunction
 genvar p,s,k;
 generate for(p=0;p<4;p=p+1) begin:pixel
  for(s=0;s<5;s=s+1) begin:sample
   wire [25:0] f=forward(samples_r[96*s+24*p+:24]);
   always @(posedge clk) if(ce) begin
    co[0][5*p+s]<=f[17:9];cg[0][5*p+s]<=f[8:0];
   end
  end
  wire [25:0] centre=forward(samples_r[192+24*p+:24]);
  always @(posedge clk) if(ce) yy[0][8*p+:8]<=centre[25:18];
  // Five registered odd/even transposition phases sort five values.
  for(s=0;s<5;s=s+1) begin:phase
   for(k=0;k<5;k=k+1) begin:element
    if ((k%2)==(s%2) && k<4) begin:low
     always @(posedge clk) if(ce) begin
      co[s+1][5*p+k]<=($signed(co[s][5*p+k])<$signed(co[s][5*p+k+1]))?co[s][5*p+k]:co[s][5*p+k+1];
      cg[s+1][5*p+k]<=($signed(cg[s][5*p+k])<$signed(cg[s][5*p+k+1]))?cg[s][5*p+k]:cg[s][5*p+k+1];
     end
    end else if (k>0 && ((k-1)%2)==(s%2)) begin:high
     always @(posedge clk) if(ce) begin
      co[s+1][5*p+k]<=($signed(co[s][5*p+k-1])<$signed(co[s][5*p+k]))?co[s][5*p+k]:co[s][5*p+k-1];
      cg[s+1][5*p+k]<=($signed(cg[s][5*p+k-1])<$signed(cg[s][5*p+k]))?cg[s][5*p+k]:cg[s][5*p+k-1];
     end
    end else begin:unchanged
     always @(posedge clk) if(ce) begin co[s+1][5*p+k]<=co[s][5*p+k];cg[s+1][5*p+k]<=cg[s][5*p+k];end
    end
   end
  end
  always @(posedge clk) if(ce) begin
   tt[p]<=$signed({2'b00,yy[5][8*p+:8]})-($signed({cg[5][5*p+2][8],cg[5][5*p+2]})>>>1);
   cco[p]<=$signed({co[5][5*p+2][8],co[5][5*p+2]});
   co_floor_half[p]<=$signed({co[5][5*p+2][8],co[5][5*p+2]})>>>1;
   co_ceil_half[p]<=($signed({co[5][5*p+2][8],co[5][5*p+2]})+10'sd1)>>>1;
   ccg[p]<=$signed({cg[5][5*p+2][8],cg[5][5*p+2]});
  end
  wire signed [9:0] blue=tt[p]-co_floor_half[p];
  wire signed [9:0] red=tt[p]+co_ceil_half[p];
  wire signed [9:0] green=tt[p]+ccg[p];
  wire outside=(red<0 || red>255 || green<0 || green>255 || blue<0 || blue>255);
  always @(posedge clk) if(ce) begin
   result[24*p+:24]<=(ENABLE==0 || outside)?original[6][24*p+:24]:{red[7:0],green[7:0],blue[7:0]};
   bad[p]<=(ENABLE!=0)&&outside;
  end
 end endgenerate
 integer i;
 always @(posedge clk or negedge rst_n) begin
  if(!rst_n) begin vp<=0;lp<=0;up<=0;end
  else if(ce) begin vp<={vp[6:0],sample_valid};lp<={lp[6:0],sample_last};up<={up[6:0],sample_user};end
 end
 always @(posedge clk) if(ce) begin
  gp[0]<=sample_geometry;original[0]<=samples_r[192+:96];
  for(i=1;i<8;i=i+1) gp[i]<=gp[i-1];
  for(i=1;i<7;i=i+1) original[i]<=original[i-1];
  for(i=1;i<6;i=i+1) yy[i]<=yy[i-1];
 end
endmodule

module ui_chroma_rank5_horizontal #(parameter ENABLE=1, parameter LINE_ADDR_WIDTH=11)(
 input wire clk,rst_n,input wire [12:0] width,height,input wire [95:0] data,
 input wire valid,last,user,output wire ready,output wire [95:0] out_data,
 output wire out_valid,out_last,out_user,output wire [27:0] out_geometry,
 output wire [3:0] fallback,output reg [3:0] faults,input wire out_ready,input wire [1:0] pattern_shadow
);
 reg [10:0] x,px;
 reg [12:0] y,py,words,rows,pwords,prows;
 reg pending,flush,started;
 reg [95:0] held;
 reg [47:0] left;
 reg [1:0] frame_mode,p_mode;
 wire geometry_ok=width>=4 && width<=(4<<LINE_ADDR_WIDTH) && width[1:0]==0 && height!=0;
 wire [12:0] iw=user?(geometry_ok?(width>>2):13'd1):words;
 wire [12:0] ih=user?(geometry_ok?height:13'd1):rows;
 wire [10:0] ix=user?11'd0:x;
 wire [12:0] iy=user?13'd0:y;
 wire cr;
 assign ready=cr && !flush;
 wire accept=valid && ready;
 wire emit=pending && (flush || valid);
 wire [1:0] selected_mode=user?pattern_shadow:frame_mode;
 function [23:0] test_pixel;
  input [1:0] mode;input [12:0] xx,yy;
  reg [7:0] r,g,b;
  begin
   r=xx[7:0]^{yy[3:0],yy[7:4]}^8'h35;
   g={xx[3:0],xx[7:4]}^yy[7:0]^8'hA7;
   b=xx[7:0]^yy[7:0]^8'h5B;
   case(mode)
    2'd1: begin
     if(xx[3:0]==0 && yy[3:0]==0) test_pixel=24'h00DC00;
     else test_pixel={r,g,b};
    end
    2'd2: case(xx[9:7])
     0:test_pixel=24'h000000;1:test_pixel=24'hFFFFFF;
     2:test_pixel=24'hFF0000;3:test_pixel=24'h00FF00;
     4:test_pixel=24'h0000FF;5:test_pixel=24'hFFFF00;
     6:test_pixel=24'hFF00FF;7:test_pixel=24'h00FFFF;
     default:test_pixel=24'd0;
    endcase
    2'd3:test_pixel={3{xx[7:0]^yy[7:0]}};
    default:test_pixel=24'd0;
   endcase
  end
 endfunction
 wire [95:0] source_word;
 genvar pattern_pixel;
 generate for(pattern_pixel=0;pattern_pixel<4;pattern_pixel=pattern_pixel+1) begin:pattern_lane
  wire [12:0] pixel_x={ix,2'b00}+pattern_pixel;
  assign source_word[24*pattern_pixel+:24]=(selected_mode==0)?data[24*pattern_pixel+:24]:test_pixel(selected_mode,pixel_x,iy);
 end endgenerate

 wire [47:0] right=flush?{held[24+:24],held[48+:24]}:source_word[47:0];
 wire [191:0] window={right,held,left};
 wire [479:0] samples;
 genvar p,s;
 generate for(s=0;s<5;s=s+1) begin:sm
  for(p=0;p<4;p=p+1) begin:pxl
   assign samples[96*s+24*p+:24]=window[24*(p+s)+:24];
  end
 end endgenerate
 ui_chroma_rank5_core #(.ENABLE(ENABLE)) core(
  .clk(clk),.rst_n(rst_n),.samples(samples),.valid(emit),
  .last(px==pwords-1),.user(px==0 && py==0),.geometry({p_mode,pwords,prows}),.ready(cr),
  .data(out_data),.out_valid(out_valid),.out_last(out_last),.out_user(out_user),
  .out_geometry(out_geometry),.fallback(fallback),.out_ready(out_ready));
 always @(posedge clk or negedge rst_n) begin
  if(!rst_n) begin
   x<=0;y<=0;px<=0;py<=0;words<=1;rows<=1;pwords<=1;prows<=1;
   pending<=0;flush<=0;started<=0;faults<=0;frame_mode<=0;p_mode<=0;
  end else if(cr) begin
   if(flush) begin flush<=0;pending<=0;end
   else if(accept) begin
    if(user && !geometry_ok) faults[0]<=1;
    if(user && (x!=0 || y!=0)) faults[1]<=1;
    if(!user && !started) faults[2]<=1;
    if(last!=(ix==iw-1)) faults[3]<=1;
    if(user) begin words<=iw;rows<=ih;started<=1;frame_mode<=pattern_shadow;end
    held<=source_word;left<=(ix==0)?{source_word[24+:24],source_word[48+:24]}:held[95:48];p_mode<=selected_mode;
    px<=ix;py<=iy;pwords<=iw;prows<=ih;pending<=1;flush<=(ix==iw-1);
    if(ix==iw-1) begin x<=0;y<=(iy==ih-1)?13'd0:iy+1'b1;end
    else begin x<=ix+1'b1;y<=iy;end
   end
  end
 end
endmodule

module ui_chroma_rank5_vertical #(parameter ENABLE=1, parameter LINE_ADDR_WIDTH=11)(
 input wire clk,rst_n,input wire [95:0] data,input wire valid,last,user,
 input wire [27:0] geometry,output wire ready,output wire [95:0] out_data,
 output wire out_valid,out_last,out_user,output wire [3:0] fallback,
 output reg [3:0] faults,input wire out_ready,output wire [1:0] out_mode
);
 localparam FEED=0,DRAIN=1,FINISH=2;
 reg [1:0] state;
 reg [10:0] x,scan_x,qx;
 reg [12:0] y,scan_y,words,rows,qsrc,qcentre,qwords,qrows;
 reg qvalid,qemit,qdrain,started;
 reg [95:0] qinput;
 reg [2:0] write_bank,last_row_bank;
 wire [2:0] current_bank=user?3'd0:write_bank;
 reg [1:0] frame_mode,qmode;
 wire [12:0] iw=user?geometry[25:13]:words;
 wire [12:0] ih=user?geometry[12:0]:rows;
 wire [10:0] ix=user?11'd0:x;
 wire [12:0] iy=user?13'd0:y;
 wire cr;
 assign ready=cr && state==FEED;
 wire accept=valid && ready;
 wire issue=rst_n && cr && (accept || state==DRAIN);
 // On an issued RAM request, accept is true exactly in FEED. Select
 // request geometry from the local registered state; ready/valid still gate
 // issue/CE. This removes upstream ready from the row-index arithmetic.
 wire feed_request=(state==FEED);
 wire [10:0] address=feed_request?ix:scan_x;
 wire [95:0] banks[0:4];
 genvar b;
 generate for(b=0;b<5;b=b+1) begin:bank
  ui_ram_demosaic_eram_infer #(
   .MODE("SDP"),.BYTE_SIZE(1),.INIT_FILE("NONE"),.FILL_REMAIN(0),
   .USE_BYTE_WEA(0),.DATAWIDTH_A(96),.WEA_WIDTH(1),.REGMODE_A("NOREG"),
   .WRITEMODE_A("WRITETHROUGH"),.ADDRWIDTH_A(LINE_ADDR_WIDTH),
   .USE_BYTE_WEB(0),.DATAWIDTH_B(96),.WEB_WIDTH(1),.REGMODE_B("NOREG"),
   .WRITEMODE_B("READBEFOREWRITE"),.ADDRWIDTH_B(LINE_ADDR_WIDTH)
  ) ram(
   .clka(clk),.rsta(1'b0),.cea(rst_n && accept && current_bank==b),.ocea(1'b1),
   .wea(1'b1),.dia(data),.addra(ix[LINE_ADDR_WIDTH-1:0]),.doa(),
   .clkb(clk),.rstb(1'b0),.ceb(issue),.oceb(1'b1),.web(1'b0),.dib(96'd0),
   .addrb(address[LINE_ADDR_WIDTH-1:0]),.dob(banks[b]),.ecc_sbiterrinj(1'b0),.ecc_dbiterrinj(1'b0),
   .ecc_pipece(1'b0),.ecc_sbiterr(),.ecc_dbiterr(),.ecc_erraddr());
 end endgenerate
 function [12:0] reflect;
  input signed [14:0] pos;input [12:0] h;
  reg signed [14:0] hh;
  begin
   hh=$signed({2'b00,h});
   if(h==1) reflect=0;
   else if(h==2) reflect={12'd0,pos[0]};
   else if(pos<0) reflect=-pos;
   else if(pos>=hh) reflect=(hh<<<1)-15'sd2-pos;
   else reflect=pos[12:0];
  end
 endfunction
 // Old rows live in five distinct banks. The current write-bank output is
 // never selected: current-row samples use qinput, older rows use another bank.
 function [2:0] bank_backwards;
  input [2:0] bank,gap;
  begin
   if(gap>4) bank_backwards=0;
   else if(bank>=gap) bank_backwards=bank-gap;
   else bank_backwards={1'b0,bank}+4'd5-{1'b0,gap};
  end
 endfunction
 wire [4:0] invalid_gaps;
 wire [479:0] samples;
 genvar s;
 generate for(s=0;s<5;s=s+1) begin:row
  // Compute row selectors with the synchronous RAM request, not after it.
  wire [12:0] next_centre=feed_request?((iy>=2)?iy-13'd2:13'd0):scan_y;
  wire [12:0] next_rows=feed_request?ih:rows;
  wire [12:0] r=reflect($signed({2'b00,next_centre})+s-2,next_rows);
  wire [12:0] base_row=feed_request?iy:rows-13'd1;
  wire [2:0] base_bank=feed_request?current_bank:last_row_bank;
  // A valid5-row window has source-row minus selected-row in0..4.
  // Low3-bit subtraction is exact on that bounded interval, including row wraps.
  wire [2:0] row_gap=base_row[2:0]-r[2:0];
  assign invalid_gaps[s]=(row_gap>4);
  reg [2:0] bank_index;
  reg use_current;
  always @(posedge clk) if(issue) begin
   bank_index<=bank_backwards(base_bank,row_gap);use_current<=feed_request && r==iy;
  end
  assign samples[96*s+:96]=use_current?qinput:banks[bank_index];
 end endgenerate
 wire [27:0] unused_geometry;
 assign out_mode=unused_geometry[27:26];
 ui_chroma_rank5_core #(.ENABLE(ENABLE)) core(
  .clk(clk),.rst_n(rst_n),.samples(samples),.valid(qvalid && qemit),
  .last(qx==qwords-1),.user(qx==0 && qcentre==0),.geometry({qmode,qwords,qrows}),.ready(cr),
  .data(out_data),.out_valid(out_valid),.out_last(out_last),.out_user(out_user),
  .out_geometry(unused_geometry),.fallback(fallback),.out_ready(out_ready));
 always @(posedge clk or negedge rst_n) begin
  if(!rst_n) begin
   state<=FEED;x<=0;y<=0;scan_x<=0;scan_y<=0;words<=1;rows<=1;
   qvalid<=0;qemit<=0;qdrain<=0;qx<=0;qsrc<=0;qcentre<=0;qwords<=1;qrows<=1;
   started<=0;faults<=0;frame_mode<=0;qmode<=0;write_bank<=0;last_row_bank<=0;
  end else if(cr) begin
   qvalid<=0;
   if(issue && (accept?(iy>=2):1'b1) && |invalid_gaps) faults[3]<=1;
   if(state==FINISH) state<=FEED;
   if(accept) begin
    last_row_bank<=current_bank;
    if(ix==iw-1) begin
     if(iy==ih-1 || current_bank==4) write_bank<=0;
     else write_bank<=current_bank+1'b1;
    end else write_bank<=current_bank;

    if(!user && !started) faults[0]<=1;
    if(user && (x!=0 || y!=0)) faults[1]<=1;
    if(last!=(ix==iw-1)) faults[2]<=1;
    if(user) begin words<=iw;rows<=ih;started<=1;frame_mode<=geometry[27:26];end
    qvalid<=1;qemit<=(iy>=2);qdrain<=0;qmode<=user?geometry[27:26]:frame_mode;qx<=ix;qsrc<=iy;
    qcentre<=(iy>=2)?iy-13'd2:13'd0;qinput<=data;qwords<=iw;qrows<=ih;
    if(ix==iw-1) begin
     x<=0;
     if(iy==ih-1) begin
      y<=0;state<=DRAIN;scan_x<=0;scan_y<=(ih>=3)?ih-13'd2:13'd0;
     end else y<=iy+1'b1;
    end else begin x<=ix+1'b1;y<=iy;end
   end else if(state==DRAIN) begin
    qvalid<=1;qemit<=1;qdrain<=1;qmode<=frame_mode;qx<=scan_x;qcentre<=scan_y;qwords<=words;qrows<=rows;
    if(scan_x==words-1) begin
     scan_x<=0;
     if(scan_y==rows-1) state<=FINISH;else scan_y<=scan_y+1'b1;
    end else scan_x<=scan_x+1'b1;
   end
  end
 end
endmodule

module ui_chroma_rank42 #(parameter ENABLE=1, parameter LINE_ADDR_WIDTH=11)(
 input wire clk,rst_n,input wire [12:0] width,height,input wire [95:0] data,
 input wire valid,last,user,output wire ready,output wire [95:0] out_data,
 output wire out_valid,out_last,out_user,input wire out_ready,
 output wire [31:0] status,output reg [31:0] input_beats,output_beats,input_frames,output_frames,
 output reg [31:0] horizontal_fallback,vertical_fallback,
 input wire [1:0] pattern_shadow,output reg [1:0] active_mode
);
 wire [95:0] hd;wire hv,hl,hu,hr;wire [27:0] hg;wire [3:0] hf,vf,hbad,vbad;wire [1:0] vmode;
 ui_chroma_rank5_horizontal #(.ENABLE(ENABLE),.LINE_ADDR_WIDTH(LINE_ADDR_WIDTH)) horizontal(
  .clk(clk),.rst_n(rst_n),.width(width),.height(height),.data(data),.valid(valid),
  .last(last),.user(user),.ready(ready),.out_data(hd),.out_valid(hv),.out_last(hl),
  .out_user(hu),.out_geometry(hg),.fallback(hf),.faults(hbad),.out_ready(hr),.pattern_shadow(pattern_shadow));
 ui_chroma_rank5_vertical #(.ENABLE(ENABLE),.LINE_ADDR_WIDTH(LINE_ADDR_WIDTH)) vertical(
  .clk(clk),.rst_n(rst_n),.data(hd),.valid(hv),.last(hl),.user(hu),.geometry(hg),
  .ready(hr),.out_data(out_data),.out_valid(out_valid),.out_last(out_last),
  .out_user(out_user),.fallback(vf),.faults(vbad),.out_ready(out_ready),.out_mode(vmode));
 assign status={23'd0,vbad,hbad,(ENABLE!=0)};
 function [2:0] population;
  input [3:0] v;
  begin population={2'd0,v[0]}+{2'd0,v[1]}+{2'd0,v[2]}+{2'd0,v[3]};end
 endfunction
 always @(posedge clk or negedge rst_n) begin
  if(!rst_n) begin input_beats<=0;output_beats<=0;input_frames<=0;output_frames<=0;horizontal_fallback<=0;vertical_fallback<=0;active_mode<=0;end
  else begin
   if(valid && ready) begin input_beats<=input_beats+1'b1;if(user) input_frames<=input_frames+1'b1;end
   if(hv && hr) horizontal_fallback<=horizontal_fallback+population(hf);
   if(out_valid && out_ready) begin
    output_beats<=output_beats+1'b1;vertical_fallback<=vertical_fallback+population(vf);
    if(out_user) begin output_frames<=output_frames+1'b1;active_mode<=vmode;end
   end
  end
 end
endmodule
`default_nettype wire
