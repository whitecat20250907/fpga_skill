`timescale 1ns/1ps
// Transaction-level I2C model only. Real polling RTL and real UART transmitter.
module ui_i2c #(parameter WMEN_LEN=5,RMEN_LEN=3,CLK_DIV=4)(
 input I_clk,I_rstn,output O_iic_scl,inout IO_iic_sda,
 input [WMEN_LEN*8-1:0] I_wr_data,input [7:0] I_wr_cnt,
 output reg [RMEN_LEN*8-1:0] O_rd_data=0,input [7:0] I_rd_cnt,
 input I_iic_req,I_iic_mode,output reg O_iic_busy=0);
assign O_iic_scl=1;assign IO_iic_sda=1'bz;
integer cycles=0,reads=0,writes=0;
reg pending_read=0;
always @(posedge I_clk) begin
 if(!I_rstn)begin O_iic_busy<=0;cycles<=0;reads<=0;writes<=0;O_rd_data<=0;end
 else if(!O_iic_busy && I_iic_req)begin
  if(I_wr_data[7:0]!==8'hd0)$fatal(1,"RTC device address");
  if(I_wr_data[15:8]!==8'h00)$fatal(1,"RTC register address");
  pending_read<=I_rd_cnt!=0;
  if(I_rd_cnt!=0)begin
   if(I_wr_cnt!=2||I_rd_cnt!=3)$fatal(1,"Random-read byte counts");
  end else begin
   if(I_wr_cnt!=5)$fatal(1,"RTC initialization write count");
   writes<=writes+1;
  end
  cycles<=20000;O_iic_busy<=1;
 end else if(O_iic_busy)begin
  if(cycles==0)begin
   if(pending_read)begin
    O_rd_data<=24'h123456+reads;reads<=reads+1;
   end
   O_iic_busy<=0;
  end else cycles<=cycles-1;
 end
end
endmodule
module tb_rtc_poll;
reg clk=0;always #5 clk=~clk;
wire tx,scl;tri sda;
reg test_done=0;
integer received=0;
localparam BIT_TIME=40;
rtc_clock_ds1337 #(.SYSCLKHZ(460800)) dut(.I_sysclk(clk),.O_iic_scl(scl),.IO_iic_sda(sda),.O_uart_tx(tx));
function [7:0] golden(input integer index);
 case(index%10)
  0:golden="1";1:golden="2";2:golden="-";3:golden="3";4:golden="4";
  5:golden="-";6:golden="5";7:golden=(index<10)?"6":"7";
  8:golden=13;9:golden=10;
 endcase
endfunction
initial begin: rx
 reg [7:0] value;
 integer b;
 forever begin
  @(negedge tx);
  if(dut.X_ui_i2c.reads<1)$fatal(1,"UART sent before first read completed");
  if(received>=20)$fatal(1,"Unexpected UART byte");
  #(BIT_TIME/2);if(tx!==0)$fatal(1,"Start bit");
  for(b=0;b<8;b=b+1)begin #(BIT_TIME);value[b]=tx;end
  #(BIT_TIME);if(tx!==1)$fatal(1,"Stop bit");
  if(value!==golden(received))$fatal(1,"RTC byte %0d got%h expected%h",received,value,golden(received));
  received=received+1;
 end
end
initial begin
 wait(received==20);wait(dut.X_ui_uart_tx_block.S_UART_TX==0);
 repeat(100)@(posedge clk);
 if(dut.X_ui_i2c.writes!=1||dut.X_ui_i2c.reads!=2)$fatal(1,"Unexpected transaction count");
 test_done=1;$display("RTC POLL PASS: two completed reads, 20 exact UART bytes, no stale/extra byte");$stop;
end
initial begin #10000000;$fatal(1,"RTC timeout");end
endmodule
