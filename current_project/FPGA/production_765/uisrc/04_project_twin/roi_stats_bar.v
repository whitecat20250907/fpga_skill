// Same user_clk domain as the accepted RGB10 tap and PCIe BAR command bus.
// Commands shadow until COMMIT; stats are frame-atomic, read seq before/after.
`timescale 1ns/1ps
module roi_stats_bar(
 input wire clk,rst_n,input wire fire,sof,eol,input wire[119:0]rgb,
 input wire[12:0]width,height,
 input wire write_valid,input wire[31:0]write_address,write_data,input wire[3:0]write_strobe,
 input wire read_valid,input wire[31:0]read_address,
 output reg read_select,output reg[31:0]read_data
);
 reg[31:0]shadow_xy0,shadow_xy1,shadow_source;
 reg[12:0]x0,y0,x1,y1;reg enable;reg[31:0]command_id,source_frame;
 wire[31:0]stats_seq,frame_id,command_used,source_used,pixels;
 wire valid;wire[63:0]sum;wire[511:0]histogram;
 roi_luma_stats stats(.clk(clk),.rst_n(rst_n),.fire(fire),.sof(sof),.eol(eol),.rgb(rgb),.width(width),.height(height),
  .enable(enable),.command_id(command_id),.source_frame(source_frame),.x0(x0),.y0(y0),.x1(x1),.y1(y1),
  .stats_seq(stats_seq),.frame_id(frame_id),.command_used(command_used),.source_used(source_used),
  .valid(valid),.pixels(pixels),.sum(sum),.histogram(histogram));
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   shadow_xy0<=0;shadow_xy1<=0;shadow_source<=0;x0<=0;y0<=0;x1<=0;y1<=0;
   enable<=0;command_id<=0;source_frame<=0;read_select<=0;read_data<=0;
  end else begin
   if(write_valid&&write_strobe==4'hf)case(write_address[19:0])
    20'h00e04:shadow_xy0<=write_data;
    20'h00e08:shadow_xy1<=write_data;
    20'h00e0c:shadow_source<=write_data;
    20'h00e10:begin
     x0<=shadow_xy0[12:0];y0<=shadow_xy0[28:16];
     x1<=shadow_xy1[12:0];y1<=shadow_xy1[28:16];
     source_frame<=shadow_source;enable<=write_data[31];command_id<={1'b0,write_data[30:0]};
    end
   endcase
   if(read_valid)begin
    read_select<=read_address[19:8]==12'h00e;
    case(read_address[7:0])
     8'h00:read_data<=32'h53494f52; // ROIS
     8'h04:read_data<=shadow_xy0;
     8'h08:read_data<=shadow_xy1;
     8'h0c:read_data<=shadow_source;
     8'h10:read_data<={enable,command_id[30:0]};
     8'h14:read_data<=stats_seq;
     8'h18:read_data<={31'd0,valid};
     8'h1c:read_data<=frame_id;
     8'h20:read_data<=command_used;
     8'h24:read_data<=source_used;
     8'h28:read_data<=pixels;
     8'h2c:read_data<=sum[31:0];
     8'h30:read_data<=sum[63:32];
     default:begin
      if(read_address[7:0]>=8'h40&&read_address[7:0]<=8'h7c&&read_address[1:0]==0)
       read_data<=histogram[(read_address[7:2]-6'h10)*32+:32];
      else read_data<=0;
     end
    endcase
   end
  end
 end
endmodule
