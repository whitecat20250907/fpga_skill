`timescale 1ns/1ps
// Compact quad ROI input -> scalar eye samples. Four interleaved synchronous
// RAM banks accept up to four adjacent pixels every clock; one held output
// retires each clock. Small per-eye storage absorbs horizontal pixel bursts.
// All source identity/ROI/config/time fields accompany every buffered pixel.
module hci02_eye_pixel_fifo #(parameter DEPTH=1024,PBITS=$clog2(DEPTH))(
 input wire clk,rst_n,input wire s_valid,output wire s_ready,input wire [31:0] s_gray,
 input wire [2:0] s_count,input wire s_sof,s_last,s_eof,
 input wire [15:0] s_x,s_y,s_origin_x,s_origin_y,s_width,s_height,
 input wire [31:0] s_frame_id,s_config_sequence,input wire [63:0] s_time_us,input wire [7:0] s_flags,
 input wire m_ready,output reg m_valid,output wire [242:0] m_pixel,
 output wire [31:0] occupancy,output reg [31:0] high_water,errors
);
 reg [PBITS-1:0] wr,rd;reg [PBITS:0] count;
 wire advance=!m_valid||m_ready;wire pop=count!=0&&advance;
 wire legal=s_count>=1&&s_count<=4;
 assign s_ready=count+s_count<=DEPTH;
 wire push=s_valid&&s_ready&&legal;
 assign occupancy=count+m_valid;
 wire [242:0] words[0:3];wire [PBITS-1:0] addresses[0:3];
 genvar k;generate for(k=0;k<4;k=k+1)begin:pixel
  wire [15:0] local_x=s_x+k;
  assign words[k]={s_flags,s_time_us,s_config_sequence,s_frame_id,s_height,s_width,s_origin_y,s_origin_x,s_y,local_x,
   s_eof&&(k==s_count-1),s_last&&(k==s_count-1),s_sof&&(k==0),s_gray[k*8+:8]};
  assign addresses[k]=wr+k;
 end endgenerate
 reg [3:0] write_enable;reg [242:0] write_data[0:3];reg [PBITS-3:0] write_address[0:3];
 integer b,j;
 always @*begin
  write_enable=0;
  for(b=0;b<4;b=b+1)begin write_data[b]=0;write_address[b]=0;end
  for(j=0;j<4;j=j+1)if(j<s_count)begin
   write_enable[addresses[j][1:0]]=1;
   write_data[addresses[j][1:0]]=words[j];write_address[addresses[j][1:0]]=addresses[j][PBITS-1:2];
  end
 end
 wire [242:0] bank_q0,bank_q1,bank_q2,bank_q3;reg [1:0] output_bank;
 assign m_pixel=output_bank==0?bank_q0:output_bank==1?bank_q1:output_bank==2?bank_q2:bank_q3;
 hci02_eram_sdp #(.DATA_WIDTH(243),.DEPTH(DEPTH/4),.ADDR_BITS(PBITS-2))u_bank0(
  .clk(clk),.wr_en(rst_n&&push&&write_enable[0]),.wr_addr(write_address[0]),.wr_data(write_data[0]),
  .rd_en(rst_n&&pop&&rd[1:0]==2'd0),.rd_addr(rd[PBITS-1:2]),.rd_data(bank_q0));
 hci02_eram_sdp #(.DATA_WIDTH(243),.DEPTH(DEPTH/4),.ADDR_BITS(PBITS-2))u_bank1(
  .clk(clk),.wr_en(rst_n&&push&&write_enable[1]),.wr_addr(write_address[1]),.wr_data(write_data[1]),
  .rd_en(rst_n&&pop&&rd[1:0]==2'd1),.rd_addr(rd[PBITS-1:2]),.rd_data(bank_q1));
 hci02_eram_sdp #(.DATA_WIDTH(243),.DEPTH(DEPTH/4),.ADDR_BITS(PBITS-2))u_bank2(
  .clk(clk),.wr_en(rst_n&&push&&write_enable[2]),.wr_addr(write_address[2]),.wr_data(write_data[2]),
  .rd_en(rst_n&&pop&&rd[1:0]==2'd2),.rd_addr(rd[PBITS-1:2]),.rd_data(bank_q2));
 hci02_eram_sdp #(.DATA_WIDTH(243),.DEPTH(DEPTH/4),.ADDR_BITS(PBITS-2))u_bank3(
  .clk(clk),.wr_en(rst_n&&push&&write_enable[3]),.wr_addr(write_address[3]),.wr_data(write_data[3]),
  .rd_en(rst_n&&pop&&rd[1:0]==2'd3),.rd_addr(rd[PBITS-1:2]),.rd_data(bank_q3));
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin wr<=0;rd<=0;count<=0;m_valid<=0;output_bank<=0;high_water<=0;errors<=0;end
  else begin
   if(s_valid&&!legal)errors[0]<=1;
   if(push)wr<=wr+s_count;
   if(pop)begin rd<=rd+1'b1;output_bank<=rd[1:0];end
   if(advance)m_valid<=pop;
   if(push&&pop)count<=count+s_count-1'b1;
   else if(push)count<=count+s_count;
   else if(pop)count<=count-1'b1;
   if(occupancy>high_water)high_water<=occupancy;
  end
 end
 // synthesis translate_off
 initial if(DEPTH<8||(DEPTH&(DEPTH-1))!=0)$fatal(1,"Eye FIFO depth must be a power of two, at least8");
 // synthesis translate_on
endmodule
