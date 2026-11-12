// A single 640x360 input fans out to shared RGB, face128 and palm192.
// C2H1 payload is 680 row records: ROW1, kind, row, byte count; then RGB3.
// Row records may interleave. One outer frame ID/tick and CRC covers all planes.
// A bounded FIFO holds shared RGB while the two detector row streams drain.
`timescale 1ns/1ps
`default_nettype none
module rgb_tensor_bundle(
 input wire clk,rst_n,input wire s_valid,output wire s_ready,
 input wire [47:0] s_rgb,input wire [1:0] s_count,input wire s_sof,s_eol,
 input wire [31:0] s_id,input wire [63:0] s_tick,
 output wire m_valid,input wire m_ready,output wire [127:0] m_data,
 output wire m_sof,m_eof,output wire [31:0] m_id,output wire [63:0] m_tick,
 output wire error,
 input wire[1:0]view_select,
 output wire view_fire,view_sof,view_eol,view_eof,
 output wire[95:0]view_rgb,output wire[2:0]view_count,
 output wire[31:0]view_id,output wire[63:0]view_tick
);
 reg held,busy;reg [47:0] pixels;reg [1:0] remain;reg first,last;
 reg [31:0] frame_id;reg [63:0] frame_tick;
 wire r0,r1,r2;wire take=held&&r0&&r1&&r2;
 assign s_ready=(!held||(take&&remain==1))&&(!s_sof||!busy);
 reg malformed;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin held<=0;busy<=0;pixels<=0;remain<=0;first<=0;last<=0;frame_id<=0;frame_tick<=0;malformed<=0;end
  else begin
   if(take)begin pixels<=pixels>>24;remain<=remain-1'b1;first<=0;if(remain==1)held<=0;end
   if(s_valid&&s_ready)begin
    held<=1;pixels<=s_rgb;remain<=s_count;first<=s_sof;last<=s_eol;
    if(s_sof)begin busy<=1;frame_id<=s_id;frame_tick<=s_tick;end
    else if(!busy||s_id!=frame_id||s_tick!=frame_tick)malformed<=1;
    if(s_count!=1&&s_count!=2)malformed<=1;
   end
   if(m_valid&&m_ready&&m_eof)busy<=0;
  end
 end
 wire[2:0] pv,pr,pl;wire[383:0] pd;
 wire rawv,rawr,rawl,shared_valid;
 reg [1:0] state,choice;reg[9:0] rows;reg[8:0] row0,row1,row2;
 wire[127:0] rawd;wire[8:0] fill;
 assign pv[0]=shared_valid&&(fill>=119||(state==2&&choice==0));
 rgb_row_pack128 #(.WIDTH(640)) shared_pack(clk,rst_n,held&&r1&&r2,r0,{72'd0,pixels[23:0]},3'd1,rawv,rawr,rawd,rawl);
 axis_stream_fifo #(.DATA_WIDTH(128),.DEPTH(256),.ADDR_BITS(8)) shared_fifo(
  .clk(clk),.rst_n(rst_n),.s_tdata(rawd),.s_tvalid(rawv),.s_tready(rawr),.s_tlast(rawl),
  .m_tdata(pd[127:0]),.m_tvalid(shared_valid),.m_tready(pr[0]),.m_tlast(pl[0]),.fill_level(fill));
 wire[1:0] dv,dr,de,df,ds,derr;wire[191:0] dp;wire[5:0] dc;
 wire[63:0] did,dcompleted,dframes;wire[127:0] dt;
 detector_letterbox_stream #(.SIZE(128)) face(
  .clk(clk),.rst_n(rst_n),.s_valid(held&&r0&&r2),.s_ready(r1),.s_rgb(pixels[23:0]),.s_sof(first),.s_eol(last&&remain==1),.s_id(frame_id),.s_tick(frame_tick),
  .m_valid(dv[0]),.m_ready(dr[0]),.m_rgb(dp[95:0]),.m_count(dc[2:0]),.m_sof(ds[0]),.m_eol(de[0]),.m_eof(df[0]),.m_id(did[31:0]),.m_tick(dt[63:0]),.completed(dcompleted[31:0]),.input_frames(dframes[31:0]),.framing_error(derr[0]));
 detector_letterbox_stream #(.SIZE(192)) palm(
  .clk(clk),.rst_n(rst_n),.s_valid(held&&r0&&r1),.s_ready(r2),.s_rgb(pixels[23:0]),.s_sof(first),.s_eol(last&&remain==1),.s_id(frame_id),.s_tick(frame_tick),
  .m_valid(dv[1]),.m_ready(dr[1]),.m_rgb(dp[191:96]),.m_count(dc[5:3]),.m_sof(ds[1]),.m_eol(de[1]),.m_eof(df[1]),.m_id(did[63:32]),.m_tick(dt[127:64]),.completed(dcompleted[63:32]),.input_frames(dframes[63:32]),.framing_error(derr[1]));
 rgb_row_pack128 #(.WIDTH(128)) face_pack(clk,rst_n,dv[0],dr[0],dp[95:0],dc[2:0],pv[1],pr[1],pd[255:128],pl[1]);
 rgb_row_pack128 #(.WIDTH(192)) palm_pack(clk,rst_n,dv[1],dr[1],dp[191:96],dc[5:3],pv[2],pr[2],pd[383:256],pl[2]);

 wire[31:0] row_number=choice==0?{23'd0,row0}:(choice==1?{23'd0,row1}:{23'd0,row2});
 wire[31:0] row_bytes=choice==0?32'd1920:(choice==1?32'd384:32'd576);
 assign pr=state==2&&m_ready?(3'b001<<choice):3'b000;
 assign m_valid=state==1||(state==2&&pv[choice]);
 assign m_data=state==1?{row_bytes,row_number,30'd0,choice,32'h31574f52}:pd[choice*128+:128];
 assign m_sof=state==1&&rows==0;
 assign m_eof=state==2&&pl[choice]&&rows==679;
 assign m_id=frame_id;assign m_tick=frame_tick;
 assign error=malformed||(|derr);
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin state<=0;choice<=0;rows<=0;row0<=0;row1<=0;row2<=0;end
  else begin
   if(state==0&&(|pv))begin choice<=pv[0]?0:(pv[1]?1:2);state<=1;end
   if(state==1&&m_ready)state<=2;
   if(state==2&&pv[choice]&&m_ready&&pl[choice])begin
    state<=0;
    if(rows==679)begin rows<=0;row0<=0;row1<=0;row2<=0;end
    else begin
     rows<=rows+1'b1;
     case(choice)0:row0<=row0+1'b1;1:row1<=row1+1'b1;2:row2<=row2+1'b1;default:begin end endcase
    end
   end
  end
 end
// Passive taps are taken at the exact accepted tensor pixels, before byte
 // packing. They never drive any ready, framing or model data signal.
 reg[8:0]view_shared_row;
 wire shared_last=last&&remain==1;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)view_shared_row<=0;
  else if(take)begin
   if(first)view_shared_row<=0;
   else if(shared_last)view_shared_row<=view_shared_row==359?0:view_shared_row+1'b1;
  end
 end
 assign view_fire=view_select==0?take:(view_select==1?(dv[0]&&dr[0]):(view_select==2?(dv[1]&&dr[1]):1'b0));
 assign view_rgb=view_select==0?{72'd0,pixels[23:0]}:(view_select==1?dp[95:0]:dp[191:96]);
 assign view_count=view_select==0?3'd1:(view_select==1?dc[2:0]:dc[5:3]);
 assign view_sof=view_select==0?first:(view_select==1?ds[0]:ds[1]);
 assign view_eol=view_select==0?shared_last:(view_select==1?de[0]:de[1]);
 assign view_eof=view_select==0?(shared_last&&view_shared_row==359):(view_select==1?df[0]:df[1]);
 assign view_id=view_select==0?frame_id:(view_select==1?did[31:0]:did[63:32]);
 assign view_tick=view_select==0?frame_tick:(view_select==1?dt[63:0]:dt[127:64]);
endmodule
`default_nettype wire
