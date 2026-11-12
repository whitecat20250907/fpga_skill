// RGB3 byte-preserving packer; widths must have a row size divisible by 16.
`timescale 1ns/1ps
`default_nettype none
module rgb_row_pack128 #(parameter WIDTH=640)(
 input wire clk,rst_n,input wire s_valid,output wire s_ready,
 input wire [95:0] s_rgb,input wire [2:0] s_count,
 output wire m_valid,input wire m_ready,output wire [127:0] m_data,output wire m_eol
);
 reg [255:0] bytes;reg [4:0] used;reg [7:0] word_x;
 wire send=m_valid&&m_ready,accept=s_valid&&s_ready;
 wire [4:0] base=send?used-5'd16:used;
 wire [255:0] shifted=send?bytes>>128:bytes;
 assign m_valid=used>=16;assign m_data=bytes[127:0];
 assign m_eol=word_x==WIDTH*3/16-1;
 assign s_ready=used<16||m_ready;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin bytes<=0;used<=0;word_x<=0;end
  else begin
   if(send)word_x<=m_eol?0:word_x+1'b1;
   if(accept)begin
    bytes<=shifted|(({160'd0,s_count==1?{72'd0,s_rgb[23:0]}:s_rgb})<<(base*8));
    used<=base+(s_count==1?5'd3:5'd12);
   end else if(send)begin bytes<=shifted;used<=base;end
  end
 end
endmodule
`default_nettype wire
