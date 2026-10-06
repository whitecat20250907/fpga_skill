
/*******************************MILIANKE*******************************
*Company : MiLianKe Electronic Technology Co., Ltd.
*WebSite:https://www.milianke.com
*TechWeb:https://www.uisrc.com
*tmall-shop:https://milianke.tmall.com
*jd-shop:https://milianke.jd.com
*taobao-shop1: https://milianke.taobao.com
*Create Date: 2019/12/17
*Module Name:
*File Name:
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
*3) IO_ input output
*4) S_ system internal signal
*5) _n activ low
*6) _dg debug signal 
*7) _r delay or register
*8) _s state mechine
*********************************************************************/

/*******************************UART单发送控制*********************
--以下是米联客设计的UART发送控制器
--1.代码简洁，占用极少逻辑资源，代码结构清晰，逻辑设计严谨
--2.当I_uart_tx_buf_en，有效，发送I_uart_tx_buf中的数据
--3.uart_wbusy_o,表示当前UART发送总线整忙，这个时候用户程序需要等待非忙的时候，请求发送数据。
*********************************************************************/

`timescale 1ns / 1ns //仿真时间刻度/精度


module ui_uart_tx_block#
(
parameter TX_BYTES = 9,//设置需要发送的字节数
parameter BAUD_DIV = (100_000_000/115200 -1) //设置串口波特率
)
(
input  I_sysclk,//系统时钟输入
output O_uart_tx,//UART 总线发送
input [TX_BYTES*8-1:0] I_uart_tx_buf,//需要发送的数据
input  I_uart_tx_buf_en//发送使能
);


wire     uart_rstn;//系统复位，该复位，通过内部模块计数器实现
wire     uart_wbusy;//uart 发送忙
reg[1:0] S_UART_TX; //UART 发送数据控制器状态机
localparam TX_INDEX_WIDTH = (TX_BYTES <= 1) ? 1 : $clog2(TX_BYTES);
reg[TX_INDEX_WIDTH-1:0] tx_index;   //数据 index,标记正在发送哪一个数据
reg      uart_wreq;  //发送请求信号，高电平请求发送数据   
reg[TX_BYTES*8-1:0] tx_buffer; // Snapshot one complete message at request acceptance.
reg[7:0] uart_wdata; //发送数据寄存器

reg [15:0]rst_cnt = 16'd0;//延迟复位计数器

assign uart_rstn = rst_cnt[15];

//上电延迟复位，用计数器产生一个同步复位
always @(posedge I_sysclk)begin
    rst_cnt <= (rst_cnt[15] == 1'b0) ? (rst_cnt + 1'b1) : rst_cnt ;
end

always @(posedge I_sysclk)begin
    if(uart_rstn==1'b0)begin //复位初始化寄存器和信号
        uart_wdata    <= 8'd0;
        uart_wreq     <= 1'b0;
        S_UART_TX     <= 2'd0;
        tx_index      <= 0;
        tx_buffer    <= 0;
    end
    else begin
        case(S_UART_TX)
        0:if(!uart_wbusy && I_uart_tx_buf_en)begin//当UART 发送总线非忙，并且收到I_uart_tx_buf_en使能信号开始发送
            tx_buffer <= I_uart_tx_buf;
            tx_index <= 0; //重置tx_index=0
            S_UART_TX <= 2'd1;//下一个状态
        end
        1:begin
            if(!uart_wbusy)begin//当总线非忙
                uart_wdata <= tx_buffer[(tx_index*8) +: 8];//把需要发送的数据，保存到寄存器uart_wdata
                uart_wreq <= 1'b1;//请求UART 发送
            end
            else begin//当总线忙,代表已经响应了uart_wreq请求
                uart_wreq <= 1'b0;//重置uart_wreq
                S_UART_TX <= 2'd2;//下一个状态
            end
        end
        2:begin//等待总线空闲，之后返回到状态0
            S_UART_TX <= (uart_wbusy == 1'b0) ? 2'd3: S_UART_TX;
        end 
        3:begin//更新计数器
            if(tx_index < TX_BYTES-1)begin//如果数据没有发送完
                tx_index <= tx_index + 1'b1;//更新需要发送的寄存器
                S_UART_TX  <= 2'd1;//继续回到状态1发送数据
            end
            else begin//没有数据发送，回到状态0
                tx_index   <= 4'd0;
                S_UART_TX  <= 2'd0; 
            end 
        end
        endcase
    end   
end

//例化UART 发送模块
ui_uart_tx#
(
.BAUD_DIV(BAUD_DIV) //设置波特率参数   
)
X_ui_uart_tx 
(
.I_clk(I_sysclk),//系统输入时钟
.I_uart_rstn(uart_rstn),//系统复位
.I_uart_wreq(uart_wreq), //UART发送请求
.I_uart_wdata(uart_wdata),//UART写数据 
.O_uart_wbusy(uart_wbusy),//UART忙标志
.O_uart_tx(O_uart_tx)//UART 发送数据总线
);
    
endmodule

