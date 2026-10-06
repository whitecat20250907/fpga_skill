/*******************************MILIANKE*******************************
*Company : MiLianKe Electronic Technology Co., Ltd.
*WebSite:https://www.milianke.com
*TechWeb:https://www.uisrc.com
*tmall-shop:https://milianke.tmall.com
*jd-shop:https://milianke.jd.com
*taobao-shop1: https://milianke.taobao.com
*Create Date: 2022/12/17
*Module Name:uart_top_tb
*File Name:uart_top_tb.v
*Description: 
*The reference demo provided by Milianke is only used for learning. 
*We cannot ensure that the demo itself is free of bugs, so users 
*should be responsible for the technical problems and consequences
*caused by the use of their own products.
*Copyright: Copyright (c) MiLianKe
*All rights reserved.
*Revision: 1.0
*Signal description
*1) I_ input
*2) O_ output
*3)IO_ input output
*4) S_ state mechine
*5) _n activ low
*6) _dg debug signal 
*7) _r delay or register
*********************************************************************/
`timescale 1ns/1ns	//定义仿真时间刻度/精度


module sim_top_tb();
 
localparam	BPS 	     = 'd115200		;			  //波特率
localparam 	CLK_FRE    = 'd25_000_000	;	            //系统频率
localparam     CLK_TIME   =  'd250_000_000 /CLK_FRE;          //计算系统时钟周期，以ns为单位
localparam	BIT_TIME   = 'd250_000_000  / BPS ;	       //计算出传输每个bit所需要的时间以ns为单位
localparam     NUM_BYTES  = 3;                                //需要发送的BYTES

reg 			  I_sysclk;			                      //系统时钟
reg              bsp_clk ;                                    //波特率时钟
reg 	 		  uart_tx;                                     //uart 数据发送,该信号接入到，FPGA的uart 接收
wire             uart_rx;                                     //uart 数据接收,该信号接入到，FPGA的uart 发送
reg [8*NUM_BYTES-1:0] uart_send_data;                         //需要发送的数据
reg [7:0]		      uart_send_data_r;                        //寄存每次需要发送的BYTE

integer i,j;

//例化顶层模块
uart_top uart_top_inst
(
.I_sysclk(I_sysclk),
.I_uart_rx(uart_tx),
.O_uart_tx(uart_rx)
);

//仿真初始化
initial begin	

//初始化REG寄存器
I_sysclk =0;
bsp_clk  = 0;  
uart_tx  = 1;
i=0;
j=0;

uart_send_data   =0;
uart_send_data_r =0;

#20000;//延迟20000ns,等待uart测试代码中的复位延迟

uart_send_data[(0*8) +: 8] = 8'b1001_0101;//初始化需要发送的第1个BYTE
uart_send_data[(1*8) +: 8] = 8'b0000_0101;//初始化需要发送的第2个BYTE
uart_send_data[(2*8) +: 8] = 8'b1000_0100;//初始化需要发送的第3个BYTE

//uart tx 发送数据
  for(i=0; i<NUM_BYTES;i=i+1)
  begin

      uart_send_data_r = uart_send_data[(i*8) +: 8];//寄存需要发送的数据到寄存器
      $display("uart_send_data : 0x%h",uart_send_data_r);//打印准备发送的数据

      @(posedge bsp_clk);  //发送起始位1bit
      uart_tx = 1'b0;

      for(j=0;j<8;j=j+1)begin//发送数据8bits
      @(posedge bsp_clk);  //发送
      uart_tx = uart_send_data_r[j];
      end

       @(posedge bsp_clk);//发送停止位1bit
       uart_tx = 1'b1;  

  end
       @(posedge bsp_clk); 
       #200 $finish;			
end
 
always #(CLK_TIME/2) I_sysclk = ~I_sysclk;	  //产生主时钟
always #(BIT_TIME/2) bsp_clk  = ~bsp_clk;		//产生波特率时钟
 


endmodule

