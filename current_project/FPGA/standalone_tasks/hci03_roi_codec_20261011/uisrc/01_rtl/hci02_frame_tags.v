`timescale 1ns/1ps
// The common video clock associates the accepted RAW SOF with the later
// accepted ISP SOF. A timestamp is kept until the ISP actually accepts it.
// Missing/overflow tags are visible; an empty simultaneous push/pop is valid.
module hci02_frame_tags #(parameter DEPTH=8,PBITS=$clog2(DEPTH))(
 input wire clk,rst_n,raw_sof_accepted,isp_sof_accepted,input wire [63:0] time_us,
 output wire tag_valid,output wire [63:0] tag_time_us,output wire [31:0] tag_frame_id,
 output reg [31:0] raw_frames,isp_frames,overflow_count,underflow_count,
 output reg [PBITS:0] queued
);
 reg [95:0] tags[0:DEPTH-1];reg [PBITS-1:0] wr,rd;
 assign tag_valid=queued!=0||raw_sof_accepted;
 assign tag_time_us=queued!=0?tags[rd][63:0]:time_us;
 assign tag_frame_id=queued!=0?tags[rd][95:64]:raw_frames+1'b1;
 wire pop=isp_sof_accepted&&tag_valid;
 wire push=raw_sof_accepted&&(queued<DEPTH||pop);
 wire bypass=queued==0&&pop&&push;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin wr<=0;rd<=0;queued<=0;raw_frames<=0;isp_frames<=0;overflow_count<=0;underflow_count<=0;end
  else begin
   if(raw_sof_accepted)begin
    raw_frames<=raw_frames+1'b1;
    if(!push)overflow_count<=overflow_count+1'b1;
   end
   if(isp_sof_accepted)begin
    isp_frames<=isp_frames+1'b1;
    if(!pop)underflow_count<=underflow_count+1'b1;
   end
   if(push&&!bypass)begin tags[wr]<={raw_frames+1'b1,time_us};wr<=wr+1'b1;end
   if(pop&&!bypass)rd<=rd+1'b1;
   case({push,pop})
    2'b10:queued<=queued+1'b1;
    2'b01:queued<=queued-1'b1;
    default:;
   endcase
  end
 end
 // synthesis translate_off
 initial if(DEPTH<2||(DEPTH&(DEPTH-1))!=0)$fatal(1,"Frame tag FIFO depth must be a power of two");
 // synthesis translate_on
endmodule
