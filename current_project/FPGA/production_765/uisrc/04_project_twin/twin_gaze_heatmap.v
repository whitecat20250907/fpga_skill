`timescale 1ns/1ps
`default_nettype none
// Display-only occupancy. Port A: serialized read/modify/write. Port B: video.
module twin_gaze_heatmap(
 input wire clk,rst,blank,input wire [31:0] now_ms,
 input wire snapshot_valid,input wire [31:0] context_id,sample_word,
 input wire [9:0] x,y,
 output wire [7:0] level,output wire visible
);
 localparam CLEAR=0,IDLE=1,STAMP_READ=2,STAMP_WRITE=3,DECAY_READ=4,DECAY_WRITE=5;
 reg [2:0] state;reg [7:0] index,peak,decay_peak;
 reg active,have_token,pending;reg [31:0] context_seen,last_decay,last_snapshot;
 reg [15:0] last_token;reg [3:0] sample_x,pending_x,sample_y,pending_y,tap;
 wire eligible=snapshot_valid && sample_word[31];
 wire sample_ok=sample_word[30] && sample_word[13:7]<104;
 wire new_sample=eligible && sample_ok && (!have_token || last_token!=sample_word[29:14]);
 wire invalidate=(snapshot_valid && (!sample_word[31] || !active || context_seen!=context_id)) ||
                 (active && !snapshot_valid && now_ms-last_snapshot>=350);
 wire left_col=tap==0 || tap==3 || tap==6;
 wire right_col=tap==2 || tap==5 || tap==8;
 wire top_row=tap<3,bottom_row=tap>5;
 wire tap_valid=!(left_col && sample_x==0) && !(right_col && sample_x==15) &&
                !(top_row && sample_y==0) && !(bottom_row && sample_y==12);
 wire [3:0] cell_x=left_col?sample_x-1'b1:right_col?sample_x+1'b1:sample_x;
 wire [3:0] cell_y=top_row?sample_y-1'b1:bottom_row?sample_y+1'b1:sample_y;
 wire [2:0] weight=tap==4?3'd4:(tap==1 || tap==3 || tap==5 || tap==7)?3'd2:3'd1;
 wire stamping=state==STAMP_READ || state==STAMP_WRITE;
 wire [7:0] update_address=stamping?{cell_y,cell_x}:index;
 reg [7:0] update_q;
 wire [8:0] sum={1'b0,update_q}+{6'd0,weight};
 wire [7:0] increased=sum[8]?8'hff:sum[7:0];
 wire [7:0] decreased=update_q>8?update_q-8'd8:8'd0;
 wire write_enable=!rst && !invalidate && (state==CLEAR ||
                   (blank && ((state==STAMP_WRITE && tap_valid) || state==DECAY_WRITE)));
 wire [7:0] write_value=state==CLEAR?8'd0:state==STAMP_WRITE?increased:decreased;
 // No reset on the RAM: CLEAR writes all locations before enabling display.
 (* ram_style="bram(min_area)" *) reg [7:0] cells[0:255];
 wire in_inset=x>=840 && x<968 && y>=164 && y<268;
 wire [9:0] local_x=x-840,local_y=y-164;
 wire [7:0] read_address={local_y[6:3],local_x[6:3]};
 reg [7:0] count_d1,count_d2;reg [1:0] visible_pipe;
 always @(posedge clk)begin
  update_q<=cells[update_address];
  if(write_enable)cells[update_address]<=write_value;
  count_d1<=cells[in_inset?read_address:8'd0];
 end
 always @(posedge clk)begin
  if(rst)begin
   state<=CLEAR;index<=0;peak<=0;decay_peak<=0;active<=0;context_seen<=0;
   have_token<=0;pending<=0;last_token<=0;last_decay<=now_ms;last_snapshot<=now_ms;
   sample_x<=0;sample_y<=0;pending_x<=0;pending_y<=0;tap<=0;
   count_d2<=0;visible_pipe<=0;
  end else begin
   count_d2<=count_d1;visible_pipe<={visible_pipe[0],in_inset && active && state!=CLEAR};
   if(snapshot_valid)last_snapshot<=now_ms;
   if(invalidate)begin
    active<=eligible;context_seen<=context_id;state<=CLEAR;index<=0;peak<=0;
    have_token<=eligible && sample_ok;pending<=eligible && sample_ok;last_decay<=now_ms;
    last_token<=sample_word[29:14];pending_x<=sample_word[6:3];pending_y<=sample_word[13:10];
   end else begin
    if(new_sample)begin
     have_token<=1;last_token<=sample_word[29:14];pending<=1;
     pending_x<=sample_word[6:3];pending_y<=sample_word[13:10];
    end
    case(state)
     CLEAR:begin index<=index+1'b1;if(index==255)state<=IDLE;end
     IDLE:if(active && blank)begin
      if(now_ms-last_decay>=1000)begin index<=0;decay_peak<=0;state<=DECAY_READ;last_decay<=now_ms;end
      else if(pending)begin sample_x<=pending_x;sample_y<=pending_y;tap<=0;state<=STAMP_READ;if(!new_sample)pending<=0;end
     end
     STAMP_READ:if(blank)state<=STAMP_WRITE;
     STAMP_WRITE:if(blank)begin
      if(tap_valid && increased>peak)peak<=increased;
      if(tap==8)state<=IDLE;else begin tap<=tap+1'b1;state<=STAMP_READ;end
     end
     DECAY_READ:if(blank)state<=DECAY_WRITE;
     DECAY_WRITE:if(blank)begin
      if(decreased>decay_peak)decay_peak<=decreased;
      if(index==255)begin peak<=decreased>decay_peak?decreased:decay_peak;state<=IDLE;end
      else begin index<=index+1'b1;state<=DECAY_READ;end
     end
     default:begin state<=CLEAR;index<=0;peak<=0;end
    endcase
   end
  end
 end
 wire [10:0] scaled={count_d2,3'b000};
 wire [10:0] p2={2'd0,peak,1'b0},p4={1'd0,peak,2'b00},p8={peak,3'b000};
 reg [7:0] normalized;
 always @*begin
  normalized=0;
  if(peak!=0 && count_d2!=0)begin
   if(scaled>=p8-peak)normalized=7;
   else if(scaled>=p4+p2)normalized=6;
   else if(scaled>=p4+peak)normalized=5;
   else if(scaled>=p4)normalized=4;
   else if(scaled>=p2+peak)normalized=3;
   else if(scaled>=p2)normalized=2;
   else normalized=1;
  end
 end
 assign level=normalized;
 assign visible=visible_pipe[1] && active && state!=CLEAR && normalized!=0;
endmodule
`default_nettype wire
