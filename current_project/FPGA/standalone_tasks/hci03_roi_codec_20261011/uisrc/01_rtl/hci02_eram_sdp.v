`timescale 1ns/1ps
// Same-clock simple-dual-port logical ERAM. B reads one clock after accepting
// rd_en and holds its value until another read, even if a popped slot is reused.
// No memory/read-data reset; source control reset gates visibility separately.
module hci02_eram_sdp #(parameter DATA_WIDTH=8,DEPTH=32768,ADDR_BITS=$clog2(DEPTH))(
 input wire clk,input wire wr_en,rd_en,input wire [ADDR_BITS-1:0] wr_addr,rd_addr,
 input wire [DATA_WIDTH-1:0] wr_data,output wire [DATA_WIDTH-1:0] rd_data
);
 PH1_LOGIC_ERAM #(.DATA_WIDTH_A(DATA_WIDTH),.DATA_WIDTH_B(DATA_WIDTH),.ADDR_WIDTH_A(ADDR_BITS),.ADDR_WIDTH_B(ADDR_BITS),
  .DATA_DEPTH_A(DEPTH),.DATA_DEPTH_B(DEPTH),.BYTE_ENABLE(0),.MODE("DP"),.REGMODE_A("NOREG"),.REGMODE_B("NOREG"),
  .WRITEMODE_A("NORMAL"),.WRITEMODE_B("NORMAL"),.RESETMODE_A("ASYNC"),.RESETMODE_B("ASYNC"),
  .OREGSET_A("RESET"),.OREGSET_B("RESET"),.CLKMODE("SYNC"),.INIT_FILE("NONE"))u_storage(
   .clka(clk),.cea(wr_en),.ocea(1'b1),.wea(wr_en),.addra(wr_addr),.dia(wr_data),.rsta(1'b0),.bea(1'b1),.doa(),
   .clkb(clk),.ceb(rd_en),.oceb(1'b1),.web(1'b0),.addrb(rd_addr),.dib({DATA_WIDTH{1'b0}}),.rstb(1'b0),.beb(1'b1),.dob(rd_data),
   .ecc_sbiterrinj(1'b0),.ecc_dbiterrinj(1'b0),.ecc_sbiterr(),.ecc_dbiterr());
 // synthesis translate_off
 initial if(DATA_WIDTH<1||DEPTH<2||(DEPTH&(DEPTH-1))!=0)$fatal(1,"Unsupported logical ERAM geometry");
 // synthesis translate_on
endmodule
