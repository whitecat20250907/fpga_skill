`timescale 1ns/1ps
// Complete packet CDC: data uses ordinary per-word Gray retirement; a separate
// per-packet Gray descriptor FIFO publishes the complete length. A commit
// pointer that jumps by the packet length is NOT a safe Gray crossing.
// Backpressure preserves every accepted word. Source row drops remain in the
// upstream bounded codec counters, rather than becoming silent word holes.
module hci03_packet_async_bridge #(
 parameter ADDR_BITS=10,DESC_BITS=4,MAX_PACKET_WORDS=177
)(
 input wire src_clk,dst_clk,rst_n,input wire [63:0] s_data,
 input wire s_valid,s_first,s_last,output wire s_ready,
 output wire [31:0] m_data,output wire m_valid,m_first,m_last,input wire m_ready,
 output wire [15:0] m_packet_bytes,
 output reg [31:0] accepted_words,committed_packets,source_wait_clocks,source_errors,
 output reg [31:0] delivered_packets,destination_errors,output reg [ADDR_BITS:0] high_water
);
 localparam DEPTH=1<<ADDR_BITS,DD=1<<DESC_BITS;
 (* async_reg="true" *)reg [1:0] src_reset_sync,dst_reset_sync;
 always @(posedge src_clk or negedge rst_n)
  if(!rst_n)src_reset_sync<=0;else src_reset_sync<={src_reset_sync[0],1'b1};
 always @(posedge dst_clk or negedge rst_n)
  if(!rst_n)dst_reset_sync<=0;else dst_reset_sync<={dst_reset_sync[0],1'b1};
 wire src_rst_n=src_reset_sync[1],dst_rst_n=dst_reset_sync[1];
 reg [ADDR_BITS:0] wbin,wgray,rbin,rgray;
 reg [DESC_BITS:0] dwbin,dwgray,drbin,drgray;
 (* async_reg="true" *)reg [ADDR_BITS:0] rgray_s1,rgray_s2;
 (* async_reg="true" *)reg [DESC_BITS:0] drgray_s1,drgray_s2,dwgray_d1,dwgray_d2;
 reg [15:0] descriptors[0:DD-1];reg [15:0] input_words;
 wire word_full=wgray=={~rgray_s2[ADDR_BITS:ADDR_BITS-1],rgray_s2[ADDR_BITS-2:0]};
 wire desc_full=dwgray=={~drgray_s2[DESC_BITS:DESC_BITS-1],drgray_s2[DESC_BITS-2:0]};
 wire desc_empty=drgray==dwgray_d2;
 assign s_ready=src_rst_n&&!word_full&&(!s_last||!desc_full);
 wire write_word=s_valid&&s_ready;
 wire [ADDR_BITS:0] next_wbin=wbin+1'b1;
 wire [DESC_BITS:0] next_dwbin=dwbin+1'b1,next_drbin=drbin+1'b1;
 function [ADDR_BITS:0] gray_to_binary;
  input [ADDR_BITS:0] g;integer n;
  begin gray_to_binary[ADDR_BITS]=g[ADDR_BITS];for(n=ADDR_BITS-1;n>=0;n=n-1)gray_to_binary[n]=gray_to_binary[n+1]^g[n];end
 endfunction
 wire [ADDR_BITS:0] used=wbin-gray_to_binary(rgray_s2);
 reg active,upper,qwrite,qread,rd_pending;reg [1:0] qcount;
 reg [63:0] queue[0:1];reg [15:0] total_words,unissued,word_index;
 wire rd_en=active&&unissued!=0&&({1'b0,qcount}+rd_pending)<3'd2;
 wire [63:0] ram_data;
 // Two genuinely independent clocks, no RAM/output-data reset.
 PH1_LOGIC_ERAM #(.DATA_WIDTH_A(64),.DATA_WIDTH_B(64),.ADDR_WIDTH_A(ADDR_BITS),.ADDR_WIDTH_B(ADDR_BITS),
  .DATA_DEPTH_A(DEPTH),.DATA_DEPTH_B(DEPTH),.BYTE_ENABLE(0),.MODE("DP"),.REGMODE_A("NOREG"),.REGMODE_B("NOREG"),
  .WRITEMODE_A("NORMAL"),.WRITEMODE_B("NORMAL"),.RESETMODE_A("ASYNC"),.RESETMODE_B("ASYNC"),
  .OREGSET_A("RESET"),.OREGSET_B("RESET"),.CLKMODE("ASYNC"),.INIT_FILE("NONE"))u_words(
   .clka(src_clk),.cea(write_word),.ocea(1'b1),.wea(write_word),.addra(wbin[ADDR_BITS-1:0]),.dia(s_data),.rsta(1'b0),.bea(1'b1),.doa(),
   .clkb(dst_clk),.ceb(rd_en),.oceb(1'b1),.web(1'b0),.addrb(rbin[ADDR_BITS-1:0]),.dib(64'd0),.rstb(1'b0),.beb(1'b1),.dob(ram_data),
   .ecc_sbiterrinj(1'b0),.ecc_dbiterrinj(1'b0),.ecc_sbiterr(),.ecc_dbiterr());
 assign m_valid=dst_rst_n&&active&&qcount!=0;
 assign m_data=upper?queue[qread][63:32]:queue[qread][31:0];
 assign m_first=m_valid&&!upper&&word_index==0;
 assign m_last=m_valid&&upper&&word_index==total_words-1'b1;
 assign m_packet_bytes=total_words<<3;
 wire pop=m_valid&&m_ready&&upper;
 always @(posedge src_clk or negedge src_rst_n)begin
  if(!src_rst_n)begin
   wbin<=0;wgray<=0;dwbin<=0;dwgray<=0;rgray_s1<=0;rgray_s2<=0;drgray_s1<=0;drgray_s2<=0;input_words<=0;
   accepted_words<=0;committed_packets<=0;source_wait_clocks<=0;source_errors<=0;high_water<=0;
  end else begin
   rgray_s1<=rgray;rgray_s2<=rgray_s1;drgray_s1<=drgray;drgray_s2<=drgray_s1;
   if(used>high_water)high_water<=used;
   if(s_valid&&!s_ready)source_wait_clocks<=source_wait_clocks+1'b1;
   if(write_word)begin
    wbin<=next_wbin;wgray<=(next_wbin>>1)^next_wbin;accepted_words<=accepted_words+1'b1;
    if(s_first!=(input_words==0))source_errors[0]<=1;
    if(input_words>=MAX_PACKET_WORDS)source_errors[1]<=1;
    input_words<=s_last?16'd0:input_words+1'b1;
    if(s_last)begin
     descriptors[dwbin[DESC_BITS-1:0]]<=input_words+1'b1;
     dwbin<=next_dwbin;dwgray<=(next_dwbin>>1)^next_dwbin;committed_packets<=committed_packets+1'b1;
    end
   end
  end
 end
 always @(posedge dst_clk or negedge dst_rst_n)begin
  if(!dst_rst_n)begin
   rbin<=0;rgray<=0;drbin<=0;drgray<=0;dwgray_d1<=0;dwgray_d2<=0;
   active<=0;upper<=0;qwrite<=0;qread<=0;qcount<=0;rd_pending<=0;queue[0]<=0;queue[1]<=0;
   total_words<=0;unissued<=0;word_index<=0;delivered_packets<=0;destination_errors<=0;
  end else begin
   dwgray_d1<=dwgray;dwgray_d2<=dwgray_d1;rd_pending<=rd_en;
   if(!active&&!desc_empty)begin
    total_words<=descriptors[drbin[DESC_BITS-1:0]];unissued<=descriptors[drbin[DESC_BITS-1:0]];
    word_index<=0;active<=1;upper<=0;
    if(descriptors[drbin[DESC_BITS-1:0]]==0||descriptors[drbin[DESC_BITS-1:0]]>MAX_PACKET_WORDS)destination_errors[0]<=1;
   end
   if(rd_en)begin rbin<=rbin+1'b1;rgray<=((rbin+1'b1)>>1)^(rbin+1'b1);unissued<=unissued-1'b1;end
   if(rd_pending)begin queue[qwrite]<=ram_data;qwrite<=~qwrite;end
   case({rd_pending,pop})2'b10:qcount<=qcount+1'b1;2'b01:qcount<=qcount-1'b1;default:;endcase
   if(m_valid&&m_ready)begin
    upper<=~upper;
    if(upper)begin
     qread<=~qread;word_index<=word_index+1'b1;
     if(m_last)begin
      active<=0;delivered_packets<=delivered_packets+1'b1;drbin<=next_drbin;drgray<=(next_drbin>>1)^next_drbin;
      if(qcount!=1||rd_pending||unissued!=0)destination_errors[1]<=1;
     end
    end
   end
  end
 end
 // synthesis translate_off
 initial if(ADDR_BITS<2||DESC_BITS<2||MAX_PACKET_WORDS<1||MAX_PACKET_WORDS>DEPTH)$fatal(1,"packet bridge capacity");
 // synthesis translate_on
endmodule
