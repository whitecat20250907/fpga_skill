`timescale 1ns/1ps
`default_nettype none
// 256 glyphs * 16 rows * 32 bits = 131072 bits; at most eight 20K ERAM.
// One synchronous row read. Font alpha is 2 bits/pixel, no RGB frame cache.
module twin_aa_glyph_rom #(parameter FONT_FILE="twin_font.mem")(
 input wire clk,input wire [11:0] address,output wire [31:0] data
);
`ifdef __ICARUS__
 reg [31:0] memory[0:4095];reg [31:0] value;
 initial $readmemh(FONT_FILE,memory);
 always @(posedge clk)value<=memory[address];
 assign data=value;
`else
 PH1_LOGIC_ERAM #(.DATA_WIDTH_A(32),.ADDR_WIDTH_A(12),.DATA_DEPTH_A(4096),
  .DATA_WIDTH_B(32),.ADDR_WIDTH_B(12),.DATA_DEPTH_B(4096),.MODE("SP"),
  .REGMODE_A("NOREG"),.IMPLEMENT("20K"),.DEBUGGABLE("NO"),.PACKABLE("NO"),
  .INIT_FILE("twin_glyph_font_aa.mif"),.FILL_ALL("NONE")) u_font(
   .dia(32'd0),.dib(32'd0),.addra(address),.addrb(12'd0),
   .cea(1'b1),.ceb(1'b0),.clka(clk),.clkb(1'b0),.wea(1'b0),.web(1'b0),
   .bea(1'b0),.beb(1'b0),.rsta(1'b0),.rstb(1'b0),.ocea(1'b0),.oceb(1'b0),
   .doa(data),.dob(),.ecc_sbiterr(),.ecc_dbiterr(),.ecc_sbiterrinj(1'b0),.ecc_dbiterrinj(1'b0));
`endif
endmodule
`default_nettype wire
