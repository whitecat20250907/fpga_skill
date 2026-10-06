// Four padded RGB pixels -> RGB24, 16 bytes per beat.
// TLAST is end of line. EOF accompanies final data, without an extra zero beat.
`timescale 1ns/1ps
module pack4_rgb24_to_128 (
 input wire clk,rst_n,enable,
 input wire [12:0] cfg_img_height,
 input wire [127:0] s_tdata,
 input wire s_tvalid,
 output wire s_tready,
 input wire s_tlast,s_tuser,
 output reg [127:0] m_tdata,
 output reg m_tvalid,
 input wire m_tready,
 output reg m_tlast,m_frame_last,sof,eof,
 output wire [31:0] frame_count_out
);
 wire [23:0] p0={s_tdata[7:0],s_tdata[15:8],s_tdata[23:16]};
 wire [23:0] p1={s_tdata[39:32],s_tdata[47:40],s_tdata[55:48]};
 wire [23:0] p2={s_tdata[71:64],s_tdata[79:72],s_tdata[87:80]};
 wire [23:0] p3={s_tdata[103:96],s_tdata[111:104],s_tdata[119:112]};
 wire [95:0] new_bytes={p3,p2,p1,p0};
 reg [127:0] accum;
 reg [4:0] byte_offset;
 reg [12:0] line_index;
 reg in_frame,sof_pending,flush_pending,flush_final;
 reg [31:0] frame_count;
 wire output_free=!m_tvalid || m_tready;
 wire [4:0] offset_now=s_tuser ? 5'd0 : byte_offset;
 wire final_line=((s_tuser ? 13'd0 : line_index)==cfg_img_height-13'd1);
 assign frame_count_out=frame_count;
 assign s_tready=enable && !flush_pending && ((offset_now!=0)?output_free:1'b1);
 always @(posedge clk or negedge rst_n) begin
  if (!rst_n) begin
   accum<=0; byte_offset<=0; line_index<=0; in_frame<=0;
   sof_pending<=0; flush_pending<=0; flush_final<=0; frame_count<=0;
   m_tdata<=0; m_tvalid<=0; m_tlast<=0; m_frame_last<=0; sof<=0; eof<=0;
  end else begin
   if (m_tvalid && m_tready) begin
    if (m_frame_last) frame_count<=frame_count+1'b1;
    m_tvalid<=0; m_tlast<=0; m_frame_last<=0; sof<=0; eof<=0;
   end
   if (!enable) begin
    accum<=0; byte_offset<=0; line_index<=0; in_frame<=0;
    sof_pending<=0; flush_pending<=0; flush_final<=0;
    m_tvalid<=0; m_tlast<=0; m_frame_last<=0; sof<=0; eof<=0;
   end else if (flush_pending && output_free) begin
    m_tdata<=accum; m_tvalid<=1; m_tlast<=1;
    m_frame_last<=flush_final; eof<=flush_final; sof<=sof_pending;
    accum<=0; byte_offset<=0; sof_pending<=0;
    flush_pending<=0; flush_final<=0;
   end else if (s_tvalid && s_tready && (in_frame || s_tuser)) begin
    if (s_tuser) begin line_index<=0; in_frame<=1; sof_pending<=1; end
    case (offset_now)
     0: begin accum<={32'd0,new_bytes}; byte_offset<=12; end
     12: begin
      m_tdata<={new_bytes[31:0],accum[95:0]}; m_tvalid<=1;
      m_tlast<=0; m_frame_last<=0; eof<=0; sof<=sof_pending; sof_pending<=0;
      accum<={64'd0,new_bytes[95:32]}; byte_offset<=8;
     end
     8: begin
      m_tdata<={new_bytes[63:0],accum[63:0]}; m_tvalid<=1;
      m_tlast<=0; m_frame_last<=0; eof<=0; sof<=sof_pending; sof_pending<=0;
      accum<={96'd0,new_bytes[95:64]}; byte_offset<=4;
     end
     4: begin
      m_tdata<={new_bytes[95:0],accum[31:0]}; m_tvalid<=1; m_tlast<=s_tlast;
      m_frame_last<=s_tlast && final_line; eof<=s_tlast && final_line;
      sof<=sof_pending; sof_pending<=0; accum<=0; byte_offset<=0;
     end
     default: begin accum<=0; byte_offset<=0; end
    endcase
    if (s_tlast) begin
     if (offset_now!=4) begin flush_pending<=1; flush_final<=final_line; end
     if (final_line) begin in_frame<=0; line_index<=0; end
     else line_index<=(s_tuser?13'd0:line_index)+1'b1;
    end
   end
  end
 end
endmodule
