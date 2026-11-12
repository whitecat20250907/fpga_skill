`timescale 1ns/1ps
`default_nettype none
module twin_glyph_rom #(parameter FONT_FILE="twin_font.mem")(
 input wire clk,input wire[11:0]address,output wire[15:0]data
);
`ifdef __ICARUS__
 // RTL functional ROM for Icarus only. It is not a physical primitive model
 // or post-route simulation. Actual device INIT is verified independently.
 reg[15:0]memory[0:4095];reg[15:0]value;
 initial $readmemh(FONT_FILE,memory);
 always @(posedge clk)value<=memory[address];
 assign data=value;
`else
 // Same PH1_LOGIC_ERAM interface/clocking as the retained vendor DSI
 // instruction ROM: synchronous memory, no extra output register.
 PH1_LOGIC_ERAM #(.DATA_WIDTH_A(16),.ADDR_WIDTH_A(12),.DATA_DEPTH_A(4096),
  .DATA_WIDTH_B(16),.ADDR_WIDTH_B(12),.DATA_DEPTH_B(4096),.MODE("SP"),
  .REGMODE_A("NOREG"),.IMPLEMENT("20K"),.DEBUGGABLE("NO"),.PACKABLE("NO"),
  .INIT_FILE("twin_glyph_font.mif"),.FILL_ALL("NONE")) u_font(
   .dia(16'd0),.dib(16'd0),.addra(address),.addrb(12'd0),
   .cea(1'b1),.ceb(1'b0),.clka(clk),.clkb(1'b0),.wea(1'b0),.web(1'b0),
   .bea(1'b0),.beb(1'b0),.rsta(1'b0),.rstb(1'b0),.ocea(1'b0),.oceb(1'b0),
   .doa(data),.dob(),.ecc_sbiterr(),.ecc_dbiterr(),.ecc_sbiterrinj(1'b0),.ecc_dbiterrinj(1'b0));
`endif
endmodule
`default_nettype wire
