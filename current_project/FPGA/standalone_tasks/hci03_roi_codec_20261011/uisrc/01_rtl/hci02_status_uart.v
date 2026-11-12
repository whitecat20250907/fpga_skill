`timescale 1ns/1ps
// One actual vendor TX. Periodic five-slot diagnostics: legacy64B DSI6/DSIF,
// HCR2 source/ROI160B, HCE2 left/right144B. Each packet is frozen atomically.
// Eye records are latest measured frames at2Hz, with full publication/skip/
// capacity/deadline counters. This diagnostic stream is not the high-rate ROI
// image transport implemented by HCI03.
module hci02_status_uart #(
 parameter CLOCK_HZ=25000000,VIDEO_CLOCK_HZ=75000000,BAUD=115200,PERIOD_CYCLES=2500000
)(
 input wire I_clk,I_rstn,input wire [31:0] I_flags,I_frames,I_pixels,I_red,I_green,I_blue,
 input wire [31:0] I_raw,I_crc_errors,I_ecc_errors,I_wc_errors,I_overflows,I_timeouts,
 input wire [191:0] I_flow,input wire [31:0] I_flow_status,input wire [127:0] I_extension,
 input wire [2623:0] I_roi_stats,input wire [31:0] I_tag_overflows,I_tag_underflows,I_roi_rejects,
 input wire [31:0] I_eye_fifo_occupancy,I_eye_fifo_high_water,I_eye_fifo_errors,
 output wire O_uart_tx
);
 localparam IDLE=0,CRC=1,SEND=2,WAIT_BUSY=3,WAIT_DONE=4;
 reg [2:0] state=IDLE,phase=0;
 reg [1279:0] packet=0;
 reg [31:0] sequence_number=0,period_count=0,crc=32'hffffffff;
 reg [10:0] crc_index=0;
 reg [7:0] tx_index=0,packet_length=64;
 reg tx_req=0;reg [7:0] tx_data=0;wire tx_busy,tx;
 wire [31:0] crc_step=(crc>>1)^((crc[0]^packet[crc_index])?32'hedb88320:0);
 wire [10:0] crc_last=(packet_length-4)*8-1;
 ui_uart_tx #(.BAUD_DIV(CLOCK_HZ/BAUD-1))u_transport(
  .I_clk(I_clk),.I_uart_rstn(I_rstn),.I_uart_wreq(tx_req),.I_uart_wdata(tx_data),.O_uart_wbusy(tx_busy),.O_uart_tx(tx));
 assign O_uart_tx=(I_rstn&&tx_busy)?tx:1'b1;
 integer j;
 always @(posedge I_clk)begin
  if(!I_rstn)begin
   state<=IDLE;phase<=0;packet<=0;sequence_number<=0;period_count<=0;crc<=32'hffffffff;
   crc_index<=0;tx_index<=0;packet_length<=64;tx_req<=0;tx_data<=0;
  end else begin
   if(period_count<PERIOD_CYCLES)period_count<=period_count+1'b1;
   case(state)
    IDLE:if(period_count>=PERIOD_CYCLES)begin
     packet<=0;packet[95:64]<=sequence_number;
     if(phase<=1)begin
      packet_length<=64;packet[31:0]<=phase==0?32'h36495344:32'h46495344;packet[63:32]<=32'h44530101;
      packet[127:96]<=I_flags;
      if(phase==0)begin
       packet[159:128]<=I_frames;packet[191:160]<=I_pixels;packet[223:192]<=I_red;packet[255:224]<=I_green;packet[287:256]<=I_blue;
       packet[319:288]<=I_raw;packet[351:320]<=I_crc_errors;packet[383:352]<=I_ecc_errors;packet[415:384]<=I_wc_errors;
       packet[447:416]<=I_overflows;packet[479:448]<=I_timeouts;
      end else begin
       for(j=0;j<6;j=j+1)packet[(j+4)*32+:32]<=I_flow[(5-j)*32+:32];
       packet[351:320]<=I_flow_status;packet[479:352]<=I_extension;
      end
     end else if(phase==2)begin
      packet_length<=160;packet[31:0]<=32'h32524348;packet[63:32]<=32'h48430202;packet[127:96]<={I_flags[15:0],16'd160};
      // Input stats58..81: source/invalid/stale/error,3CRCs,3ROIcounts,
      // 3pixelcounts,activeSeq,enable/TTL,6descriptorwords,faceRGBsums.
      for(j=0;j<24;j=j+1)packet[(j+4)*32+:32]<=I_roi_stats[(j+58)*32+:32];
      packet[927:896]<=I_tag_overflows;packet[959:928]<=I_tag_underflows;packet[991:960]<=I_roi_rejects;
      packet[1119:992]<=I_extension;packet[1151:1120]<=CLOCK_HZ;
      packet[1183:1152]<=I_eye_fifo_occupancy;packet[1215:1184]<=I_eye_fifo_high_water;packet[1247:1216]<=I_eye_fifo_errors;
     end else begin
      packet_length<=144;packet[31:0]<=32'h32454348;packet[63:32]<=32'h48430202;
      packet[127:96]<=phase==3?32'd144:32'h00010090;
      for(j=0;j<24;j=j+1)packet[(j+4)*32+:32]<=I_roi_stats[(phase==3?j:j+24)*32+:32];
      for(j=0;j<5;j=j+1)packet[(j+28)*32+:32]<=I_roi_stats[(phase==3?j+48:j+53)*32+:32];
      packet[1087:1056]<=VIDEO_CLOCK_HZ;
     end
     sequence_number<=sequence_number+1'b1;phase<=phase==4?0:phase+1'b1;
     period_count<=0;crc<=32'hffffffff;crc_index<=0;tx_index<=0;state<=CRC;
    end
    CRC:begin
     crc<=crc_step;
     if(crc_index==crc_last)begin packet[(packet_length-4)*8+:32]<=~crc_step;state<=SEND;end
     else crc_index<=crc_index+1'b1;
    end
    SEND:begin tx_data<=packet[tx_index*8+:8];tx_req<=1;state<=WAIT_BUSY;end
    WAIT_BUSY:if(tx_busy)begin tx_req<=0;state<=WAIT_DONE;end
    WAIT_DONE:if(!tx_busy)begin
     if(tx_index==packet_length-1)state<=IDLE;
     else begin tx_index<=tx_index+1'b1;state<=SEND;end
    end
    default:state<=IDLE;
   endcase
  end
 end
endmodule
