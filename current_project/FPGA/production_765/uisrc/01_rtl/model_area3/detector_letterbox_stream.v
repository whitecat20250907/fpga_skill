// Fixed detector input contract from the deployed 640x360 RGB3 frame.
// Matches OpenCV warpPerspective INTER_LINEAR, zero border, square 640 ROI.
// SIZE=128: sample at (5*x,5*y-140); SIZE=192: (10*x/3,10*y/3-140).
// Fractional coordinates use OpenCV's 1/32 interpolation table (0,11,21).
// No full-frame image store. Top interpolation row + two output-row banks.
// In a passive camera branch, honor s_ready through an upstream drop FIFO.
`timescale 1ns/1ps
`default_nettype none
module detector_letterbox_stream #(parameter SIZE=128)(
 input wire clk,rst_n,
 input wire s_valid,output wire s_ready,input wire [23:0] s_rgb,
 input wire s_sof,s_eol,input wire [31:0] s_id,input wire [63:0] s_tick,
 output wire m_valid,input wire m_ready,output wire [95:0] m_rgb,
 output wire [2:0] m_count,output wire m_sof,m_eol,m_eof,
 output wire [31:0] m_id,output wire [63:0] m_tick,
 output reg [31:0] completed,input_frames,output reg framing_error
);
 localparam TOP=SIZE==128?28:42;
 localparam ACTIVE=SIZE==128?72:108;
 localparam [8:0] LAST=SIZE-1;
 reg active,input_done;
 reg [9:0] ix,iy,sx,sy;
 reg [8:0] ox,oy;
 reg [1:0] xphase,yphase;
 wire [5:0] fx=SIZE==128?6'd0:(xphase==0?6'd0:(xphase==1?6'd11:6'd21));
 wire [5:0] fy=SIZE==128?6'd0:(yphase==0?6'd0:(yphase==1?6'd11:6'd21));
 reg [23:0] left_pixel;
 reg [38:0] top_read;
 (* ram_style="bram" *) reg [38:0] top_line[0:SIZE-1];
 (* ram_style="bram" *) reg [23:0] row_pixels[0:2*SIZE-1];
 reg [1:0] row_ready;
 reg write_bank;
 reg [31:0] frame_id;reg [63:0] frame_tick;
 reg [8:0] out_x,out_y;
 reg read_bank,read_pending,pixel_valid;
 reg [23:0] read_pixel;
 wire padding=(out_y<TOP || out_y>=TOP+ACTIVE);
 wire selected=(iy==sy || (fy!=0 && iy==sy+1'b1));
 wire capture_pair=active&&!input_done&&s_valid&&s_ready&&selected&&ix==sx+1'b1;
 // Two row banks allow output and input to overlap; never overwrite live rows.
 assign s_ready=!input_done&&(!active||!(selected&&row_ready[write_bank]));
 wire fire=s_valid&&s_ready;
 reg hvalid,hlast,hbottom;reg [8:0] hx;reg [5:0] hyfrac;
 reg [38:0] hvalue,hprevious;
 reg vvalid,vlast;reg [8:0] vx;reg [23:0] vvalue;
 wire [8:0] write_addr=write_bank?SIZE+vx:vx;
 integer c;
 reg [12:0] hcalc[0:2];
 reg [19:0] vcalc[0:2];
 always @*begin
  for(c=0;c<3;c=c+1)begin
   hcalc[c]=left_pixel[c*8+:8]*(6'd32-fx)+s_rgb[c*8+:8]*fx;
   vcalc[c]=hyfrac==0?({7'd0,hvalue[c*13+:13]}<<5)+20'd512:
     hprevious[c*13+:13]*(6'd32-hyfrac)+hvalue[c*13+:13]*hyfrac+20'd512;
  end
 end
 assign m_valid=active&&out_y<SIZE&&(padding||pixel_valid);
 assign m_rgb=padding?96'd0:{72'd0,read_pixel};
 assign m_count=padding?3'd4:3'd1;
 assign m_sof=out_x==0&&out_y==0;
 assign m_eol=padding?out_x==SIZE-4:out_x==LAST;
 assign m_eof=m_eol&&out_y==LAST;
 assign m_id=frame_id;assign m_tick=frame_tick;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   active<=0;input_done<=0;ix<=0;iy<=0;sx<=0;sy<=0;ox<=0;oy<=0;xphase<=0;yphase<=0;
   left_pixel<=0;top_read<=0;row_ready<=0;write_bank<=0;frame_id<=0;frame_tick<=0;
   out_x<=0;out_y<=0;read_bank<=0;read_pending<=0;pixel_valid<=0;read_pixel<=0;
   hvalid<=0;hlast<=0;hbottom<=0;hx<=0;hyfrac<=0;hvalue<=0;hprevious<=0;
   vvalid<=0;vlast<=0;vx<=0;vvalue<=0;completed<=0;input_frames<=0;framing_error<=0;
  end else begin
   hvalid<=capture_pair;vvalid<=0;
   if(fire)begin
    if(!active)begin
     if(s_sof&&!s_eol)begin
      active<=1;ix<=1;iy<=0;sx<=0;sy<=0;ox<=0;oy<=0;xphase<=0;yphase<=0;
      frame_id<=s_id;frame_tick<=s_tick;left_pixel<=s_rgb;input_frames<=input_frames+1'b1;
      input_done<=0;row_ready<=0;write_bank<=0;out_x<=0;out_y<=0;read_bank<=0;
      read_pending<=0;pixel_valid<=0;hvalid<=0;vvalid<=0;
     end else framing_error<=1;
    end else begin
     if(s_sof||s_eol!=(ix==639)||s_id!=frame_id||s_tick!=frame_tick)framing_error<=1;
     if(selected&&ix==sx)begin left_pixel<=s_rgb;top_read<=top_line[ox];end
     if(capture_pair)begin
      hvalue<={hcalc[2],hcalc[1],hcalc[0]};hprevious<=top_read;
      hx<=ox;hlast<=ox==LAST;hyfrac<=fy;hbottom<=iy!=sy;
      if(ox==LAST)begin
       ox<=0;sx<=0;xphase<=0;
       if(fy==0||iy!=sy)begin
        oy<=oy+1'b1;
        if(SIZE==128)sy<=sy+10'd5;
        else begin sy<=sy+(yphase==2?10'd4:10'd3);yphase<=yphase==2?0:yphase+1'b1;end
       end
      end else begin
       ox<=ox+1'b1;
       if(SIZE==128)sx<=sx+10'd5;
       else begin sx<=sx+(xphase==2?10'd4:10'd3);xphase<=xphase==2?0:xphase+1'b1;end
      end
     end
     if(ix==639)begin ix<=0;if(iy==359)input_done<=1;else iy<=iy+1'b1;end
     else ix<=ix+1'b1;
    end
   end
   if(hvalid)begin
    if(hyfrac!=0&&!hbottom)top_line[hx]<=hvalue;
    else begin
     vvalid<=1;vx<=hx;vlast<=hlast;
     for(c=0;c<3;c=c+1)begin
      vvalue[c*8+:8]<=vcalc[c][17:10];
     end
    end
   end
   if(vvalid)begin
    row_pixels[write_addr]<=vvalue;
    if(vlast)begin row_ready[write_bank]<=1;write_bank<=!write_bank;end
   end
   if(active&&!padding&&!pixel_valid&&!read_pending&&row_ready[read_bank])begin
    read_pixel<=row_pixels[(read_bank?SIZE:0)+out_x];read_pending<=1;
   end
   if(read_pending)begin read_pending<=0;pixel_valid<=1;end
   if(m_valid&&m_ready)begin
    pixel_valid<=0;
    if(m_eol)begin
     out_x<=0;out_y<=out_y+1'b1;
     if(!padding)begin row_ready[read_bank]<=0;read_bank<=!read_bank;end
    end else out_x<=out_x+(padding?9'd4:9'd1);
    if(m_eof)begin
     // Input may still have unused bottom rows. Completion requires both tails.
     out_y<=SIZE;
    end
   end
   if(active&&out_y==SIZE&&input_done)begin active<=0;input_done<=0;completed<=completed+1'b1;end
  end
 end
endmodule
`default_nettype wire
