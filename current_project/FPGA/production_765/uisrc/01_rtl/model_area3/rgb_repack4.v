// Area3's 1/2-pixel stream -> four RGB3 pixels, preserving frame identity.
// Supported rows have a multiple of four pixels. No source clock conversion.
`timescale 1ns/1ps
`default_nettype none
module rgb_repack4(
 input wire clk,rst_n,input wire s_valid,output wire s_ready,
 input wire [47:0] s_rgb,input wire [1:0] s_count,
 input wire s_sof,s_eol,input wire [31:0] s_id,input wire [63:0] s_tag,
 output reg m_valid,input wire m_ready,output reg [95:0] m_rgb,
 output reg m_sof,m_eol,output reg [31:0] m_id,output reg [63:0] m_tag,
 output reg error
);
 reg [95:0] partial;reg [2:0] count;reg pending_sof,active;
 reg [31:0] id;reg [63:0] tag;
 wire advance=!m_valid||m_ready;
 assign s_ready=advance;
 wire [2:0] old_count=s_sof?3'd0:count;
 wire [3:0] total={1'b0,old_count}+{2'b0,s_count};
 wire [47:0] pixels=s_count==1?{24'd0,s_rgb[23:0]}:s_rgb;
 wire [143:0] joined={48'd0,(s_sof?96'd0:partial)}|({96'd0,pixels}<<(old_count*24));
 wire legal=(s_count==1||s_count==2)&&(active||s_sof)&&(!s_eol||total==4)&&
            (s_sof||(s_id==id&&s_tag==tag));
 always @(posedge clk or negedge rst_n) begin
  if(!rst_n) begin partial<=0;count<=0;pending_sof<=0;active<=0;id<=0;tag<=0;m_valid<=0;m_rgb<=0;m_sof<=0;m_eol<=0;m_id<=0;m_tag<=0;error<=0;end
  else if(advance) begin
   m_valid<=0;
   if(s_valid) begin
    if(!legal) begin error<=1;active<=0;count<=0;pending_sof<=0;end
    else begin
     if(s_sof) begin active<=1;id<=s_id;tag<=s_tag;pending_sof<=1;if(count!=0)error<=1;end
     if(total>=4) begin
      m_valid<=1;m_rgb<=joined[95:0];m_sof<=pending_sof||s_sof;m_eol<=s_eol;
      m_id<=s_sof?s_id:id;m_tag<=s_sof?s_tag:tag;
      partial<=joined[143:96];count<=total-4;pending_sof<=0;
     end else begin partial<=joined[95:0];count<=total[2:0];end
    end
   end
  end
 end
endmodule
`default_nettype wire
