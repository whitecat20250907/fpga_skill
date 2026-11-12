// Atomic 64-byte little-endian status packets with a reflected CRC32.
// The transport is the complete, unmodified ui_uart_tx from qualified demo03.
module dsi_status_uart #(
 parameter CLOCK_HZ=25000000,BAUD=115200,PERIOD_CYCLES=2500000,MAGIC=32'h35495344,FLOW_ENABLE=0
)(input I_clk,I_rstn,input [31:0] I_flags,I_frames,I_pixels,I_red,I_green,I_blue,
 input [31:0] I_raw,I_crc_errors,I_ecc_errors,I_wc_errors,I_overflows,I_timeouts,input [191:0] I_flow,input [31:0] I_flow_status,input [127:0] I_extension,output O_uart_tx);
 localparam IDLE=0,CRC=1,SEND=2,WAIT_BUSY=3,WAIT_DONE=4;
 reg [2:0] state=IDLE;
 reg [511:0] packet=0;
 reg [31:0] sequence_number=0,period_count=0,crc=32'hffffffff;
 reg [8:0] crc_index=0;reg [5:0] tx_index=0;
 reg tx_req=0;reg [7:0] tx_data=0;wire tx_busy,tx;
 wire [31:0] crc_step=(crc>>1)^((crc[0]^packet[crc_index])?32'hedb88320:0);
 ui_uart_tx #(.BAUD_DIV(CLOCK_HZ/BAUD-1)) X_transport(
  .I_clk(I_clk),.I_uart_rstn(I_rstn),.I_uart_wreq(tx_req),.I_uart_wdata(tx_data),
  .O_uart_wbusy(tx_busy),.O_uart_tx(tx));
 // The vendor shifter retains its contents on reset. Gate its stale idle
 // value so a reset in the middle of a byte cannot create a false start.
 assign O_uart_tx=(I_rstn&&tx_busy)?tx:1'b1;
 always @(posedge I_clk)begin
  if(!I_rstn)begin
   state<=IDLE;packet<=0;sequence_number<=0;period_count<=0;
   crc<=32'hffffffff;crc_index<=0;tx_index<=0;tx_req<=0;tx_data<=0;
  end else begin
   if(period_count<PERIOD_CYCLES)period_count<=period_count+1'b1;
   case(state)
    IDLE:if(period_count>=PERIOD_CYCLES)begin
     // One clock edge snapshots all fields. The packet is frozen until sent.
     packet[31:0]<=(FLOW_ENABLE&&sequence_number[0])?32'h46495344:MAGIC;packet[63:32]<=32'h44530101;
     packet[95:64]<=sequence_number;packet[127:96]<=I_flags;
     packet[159:128]<=I_frames;packet[191:160]<=I_pixels;
     packet[223:192]<=I_red;packet[255:224]<=I_green;packet[287:256]<=I_blue;
     packet[319:288]<=I_raw;packet[351:320]<=I_crc_errors;packet[383:352]<=I_ecc_errors;
     packet[415:384]<=I_wc_errors;packet[447:416]<=I_overflows;packet[479:448]<=I_timeouts;packet[511:480]<=0;
     if(FLOW_ENABLE&&sequence_number[0])begin
      packet[159:128]<=I_flow[191:160];packet[191:160]<=I_flow[159:128];
      packet[223:192]<=I_flow[127:96];packet[255:224]<=I_flow[95:64];
      packet[287:256]<=I_flow[63:32];packet[319:288]<=I_flow[31:0];
      packet[351:320]<=I_flow_status;packet[383:352]<=I_extension[31:0];packet[415:384]<=I_extension[63:32];packet[447:416]<=I_extension[95:64];packet[479:448]<=I_extension[127:96];
     end
     period_count<=0;crc<=32'hffffffff;crc_index<=0;state<=CRC;
    end
    CRC:begin
     crc<=crc_step;
     if(crc_index==479)begin packet[511:480]<=~crc_step;tx_index<=0;state<=SEND;end
     else crc_index<=crc_index+1'b1;
    end
    SEND:if(!tx_busy)begin tx_data<=packet[tx_index*8+:8];tx_req<=1;state<=WAIT_BUSY;end
    WAIT_BUSY:if(tx_busy)begin tx_req<=0;state<=WAIT_DONE;end
    WAIT_DONE:if(!tx_busy)begin
     if(tx_index==63)begin sequence_number<=sequence_number+1'b1;state<=IDLE;end
     else begin tx_index<=tx_index+1'b1;state<=SEND;end
    end
    default:begin state<=IDLE;tx_req<=0;end
   endcase
  end
 end
endmodule
