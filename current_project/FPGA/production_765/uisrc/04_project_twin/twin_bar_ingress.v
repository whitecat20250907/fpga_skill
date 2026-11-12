`timescale 1ns/1ps
`default_nettype none
// BAR0 low20 offsets 0x00c00..0x00c24. Consume only the actual paired AXI
// write-commit observer, never AW/W independently or legacy bank strobes.
// A host must poll credits. A bad/overflow write latches a fault and flushes
// both domains; only an explicit acknowledged FLSH can resume the stream.
module twin_bar_ingress #(parameter integer WORD_ADDR_BITS=9)(
 input wire bar_clk,input wire ui_clk,input wire rst_n,input wire[31:0]ui_now_ms,
 input wire bar_write_valid,input wire[31:0]bar_write_address,bar_write_data,input wire[3:0]bar_write_strobe,
 input wire bar_read_valid,input wire[31:0]bar_read_address,
 output reg bar_read_select,output reg[31:0]bar_read_data,
 output wire byte_valid,output wire[7:0]byte_data,output wire[31:0]byte_ingress_ms,input wire byte_ready,
 output reg stream_reset,
 output wire writer_ready,output wire flushing,output wire fault,
 output reg[31:0]accepted_words,rejected_writes,flush_generation,
 output wire local_bar_reset_n
);
 localparam integer PTR_BITS=WORD_ADDR_BITS+1;
 localparam integer DEPTH=1<<WORD_ADDR_BITS;
 localparam[19:0] CAP=20'h00c00,STATUS=20'h00c04,CREDITS=20'h00c08,ACCEPTED=20'h00c0c,
  DATA=20'h00c10,CONTROL=20'h00c14,REJECTED=20'h00c18,GENERATION=20'h00c1c,USED=20'h00c20,FAULTS=20'h00c24,
  ANCHOR=20'h00c28,NOW=20'h00c2c,ABI=20'h00c38,LIMITS=20'h00c3c;
 (* ram_style="bram(min_area)" *) reg[63:0]memory[0:DEPTH-1];
 (* async_reg="true" *) reg[2:0]w_up=0,r_up=0;
 (* async_reg="true" *) reg[1:0]ui_up_w=0;
 reg[PTR_BITS-1:0]wbin,wgray,rbin,rgray;
 (* async_reg="true" *) reg[PTR_BITS-1:0]rgray_w1=0,rgray_w2=0,wgray_r1=0,wgray_r2=0;
 reg[31:0]time_gray;
 (* async_reg="true" *) reg[31:0]time_w1=0,time_w2=0;
 reg flush_request,flush_ack;
 (* async_reg="true" *) reg[1:0]request_r=0,ack_w=0,busy_r=0;
 reg flush_busy,clear_on_ack;reg[2:0]settle;reg[3:0]fault_flags;
 reg[31:0]anchor_ms;reg anchor_valid;
 reg[63:0]held_word;reg held_valid,r_flushing,r_saw_busy;reg[1:0]byte_index;
 function[PTR_BITS-1:0]ungray;
  input[PTR_BITS-1:0]g;integer k;
  begin ungray[PTR_BITS-1]=g[PTR_BITS-1];for(k=PTR_BITS-2;k>=0;k=k-1)ungray[k]=ungray[k+1]^g[k];end
 endfunction
 function[31:0]ungray_time;
  input[31:0]g;integer k;
  begin ungray_time[31]=g[31];for(k=30;k>=0;k=k-1)ungray_time[k]=ungray_time[k+1]^g[k];end
 endfunction
 wire[PTR_BITS-1:0]used_words=wbin-ungray(rgray_w2);
 wire full=used_words>=DEPTH;
 wire[31:0]free_words=full?32'd0:DEPTH-{{(32-PTR_BITS){1'b0}},used_words};
 wire fifo_empty=rgray==wgray_r2;
 wire[PTR_BITS-1:0]next_wbin=wbin+1'b1,next_rbin=rbin+1'b1;
 wire write_data=bar_write_valid && |bar_write_strobe && bar_write_address[19:0]==DATA;
 wire write_control=bar_write_valid && |bar_write_strobe && bar_write_address[19:0]==CONTROL;
 wire write_anchor=bar_write_valid && |bar_write_strobe && bar_write_address[19:0]==ANCHOR;
 wire flush_command=write_control && bar_write_strobe==4'hf && bar_write_data==32'h48534c46;
 assign flushing=flush_busy;assign fault=|fault_flags;
 wire can_anchor=w_up[2] && ui_up_w[1] && !flush_busy && !fault;
 wire anchor_command=write_anchor && bar_write_strobe==4'hf && bar_write_data==32'h48434e41 && can_anchor;
 assign writer_ready=can_anchor && anchor_valid && !full;
 wire push_word=write_data && bar_write_strobe==4'hf && writer_ready;
 wire bad_data=write_data && !push_word;
 wire bad_control=write_control && (!flush_command || flush_busy);
 wire bad_anchor=write_anchor && !anchor_command;
 wire bad_write=bad_data || bad_control || bad_anchor;
 wire load_word=r_up[2] && !r_flushing && !busy_r[1] && !held_valid && !fifo_empty && request_r[1]==flush_ack;
 assign byte_valid=held_valid && r_up[2] && !r_flushing && !busy_r[1] && request_r[1]==flush_ack;
 assign byte_data=held_word[byte_index*8 +:8];
 assign byte_ingress_ms=held_word[63:32];

 // Every asynchronous first-stage Q feeds only its second stage. Gray time
 // originates in the UI millisecond domain so FIFO residence is charged.
 // Only the local release chains see the asynchronous shared assertion.
 // All other state, including the second CDC stages, releases on its own clock.
 always @(posedge bar_clk or negedge rst_n)
  if(!rst_n)w_up<=0;else w_up<={w_up[1:0],1'b1};
 always @(posedge ui_clk or negedge rst_n)
  if(!rst_n)r_up<=0;else r_up<={r_up[1:0],1'b1};
 wire writer_rst_n=w_up[2],reader_rst_n=r_up[2];
 assign local_bar_reset_n=writer_rst_n;
 always @(posedge bar_clk or negedge writer_rst_n)begin
  if(!writer_rst_n)begin ui_up_w<=0;rgray_w1<=0;rgray_w2<=0;time_w1<=0;time_w2<=0;ack_w<=0;end
  else begin
   ui_up_w<={ui_up_w[0],r_up[2]};
   rgray_w1<=rgray;rgray_w2<=rgray_w1;time_w1<=time_gray;time_w2<=time_w1;ack_w<={ack_w[0],flush_ack};
  end
 end
 always @(posedge ui_clk or negedge reader_rst_n)begin
  if(!reader_rst_n)begin wgray_r1<=0;wgray_r2<=0;request_r<=0;busy_r<=0;time_gray<=0;end
  else begin
   wgray_r1<=wgray;wgray_r2<=wgray_r1;request_r<={request_r[0],flush_request};busy_r<={busy_r[0],flush_busy};
   time_gray<=ui_now_ms^(ui_now_ms>>1);
  end
 end
 // Two independent synchronous memory ports, no resettable RAM data register.
 // ANCH must precede host scene serialization. Retain that earlier time,
 // not first DATA arrival, so host stalls as well as FIFO stalls are charged.
 always @(posedge bar_clk)if(push_word)memory[wbin[WORD_ADDR_BITS-1:0]]<={anchor_ms,bar_write_data};
 always @(posedge ui_clk)if(load_word)held_word<=memory[rbin[WORD_ADDR_BITS-1:0]];
 always @(posedge ui_clk)begin
  if(!r_up[2])begin rbin<=0;rgray<=0;held_valid<=0;byte_index<=0;flush_ack<=0;stream_reset<=1;r_flushing<=0;r_saw_busy<=0;end
  else begin
   stream_reset<=0;
   if(busy_r[1])r_saw_busy<=1;
   if(request_r[1]!=flush_ack)begin
    rbin<=0;rgray<=0;held_valid<=0;byte_index<=0;flush_ack<=request_r[1];stream_reset<=1;r_flushing<=1;
   end else if(busy_r[1] || r_flushing)begin
    // Keep the reader reset until the writer has observed ACK and settled
    // the zero pointers. A toggle ACK alone permits a stale-pointer read.
    rbin<=0;rgray<=0;held_valid<=0;byte_index<=0;stream_reset<=1;r_flushing<=1;
    if(r_flushing && r_saw_busy && !busy_r[1])begin r_flushing<=0;r_saw_busy<=0;end
   end else if(load_word)begin
    held_valid<=1;byte_index<=0;rbin<=next_rbin;rgray<=next_rbin^(next_rbin>>1);
   end else if(byte_valid && byte_ready)begin
    if(byte_index==3)begin held_valid<=0;byte_index<=0;end else byte_index<=byte_index+1'b1;
   end
  end
 end
 always @(posedge bar_clk)begin
  if(!w_up[2])begin
   wbin<=0;wgray<=0;flush_request<=0;flush_busy<=0;clear_on_ack<=0;settle<=0;fault_flags<=0;
   accepted_words<=0;rejected_writes<=0;flush_generation<=0;
   anchor_ms<=0;anchor_valid<=0;
  end else begin
   if(flush_busy)begin
    if(ack_w[1]==flush_request && rgray_w2==0)begin
     if(settle==3)begin flush_busy<=0;settle<=0;if(clear_on_ack)fault_flags<=0;end
     else settle<=settle+1'b1;
    end else settle<=0;
   end
   if(push_word)begin wbin<=next_wbin;wgray<=next_wbin^(next_wbin>>1);accepted_words<=accepted_words+1'b1;end
   if(anchor_command)begin anchor_ms<=ungray_time(time_w2);anchor_valid<=1;end
   if(flush_command && !flush_busy)begin
    flush_request<=~flush_request;flush_busy<=1;clear_on_ack<=1;settle<=0;wbin<=0;wgray<=0;flush_generation<=flush_generation+1'b1;anchor_valid<=0;
   end
   if(bad_write)begin
    rejected_writes<=rejected_writes+1'b1;clear_on_ack<=0;anchor_valid<=0;
    if(bad_data && bar_write_strobe!=4'hf)fault_flags[0]<=1;
    if(bad_data && full)fault_flags[1]<=1;
    if(bad_data && (!ui_up_w[1] || flush_busy || fault || !anchor_valid))fault_flags[2]<=1;
    if(bad_control || bad_anchor)fault_flags[3]<=1;
    if(!flush_busy)begin
     flush_request<=~flush_request;flush_busy<=1;settle<=0;wbin<=0;wgray<=0;flush_generation<=flush_generation+1'b1;
    end
   end
  end
 end
 // Same one-cycle registered read-selection convention as the video CSR mux.
 // Unregistered offsets and low16/low8 aliases never claim a transaction.
 always @(posedge bar_clk)begin
  if(!w_up[2])begin bar_read_select<=0;bar_read_data<=0;end
  else if(bar_read_valid)begin
   bar_read_select<=1;
   case(bar_read_address[19:0])
    CAP:bar_read_data<=32'h32544648;
    STATUS:bar_read_data<={26'd0,anchor_valid,ui_up_w[1],full,fault,flush_busy,writer_ready};
    CREDITS:bar_read_data<=free_words;
    ACCEPTED:bar_read_data<=accepted_words;
    DATA:bar_read_data<=0;
    CONTROL:bar_read_data<=0;
    REJECTED:bar_read_data<=rejected_writes;
    GENERATION:bar_read_data<=flush_generation;
    USED:bar_read_data<={{(32-PTR_BITS){1'b0}},used_words};
    FAULTS:bar_read_data<={28'd0,fault_flags};
    ANCHOR:bar_read_data<=anchor_ms;
    NOW:bar_read_data<=ungray_time(time_w2);
    ABI:bar_read_data<=32'h32425754;
    LIMITS:bar_read_data<=(DEPTH<<16)|32'd1916;
    default:begin bar_read_select<=0;bar_read_data<=0;end
   endcase
  end
 end
endmodule
`default_nettype wire
