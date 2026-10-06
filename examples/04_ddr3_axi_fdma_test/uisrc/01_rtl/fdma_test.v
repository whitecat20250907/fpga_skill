
/*******************************MILIANKE*******************************
*Company : MiLianKe Electronic Technology Co., Ltd.
*WebSite:https://www.milianke.com
*TechWeb:https://www.uisrc.com
*tmall-shop:https://milianke.tmall.com
*jd-shop:https://milianke.jd.com
*taobao-shop1: https://milianke.taobao.com
*Create Date: 2023/03/23
*Module Name:
*File Name:
*Description: 
*The reference demo provided by Milianke is only used for learning. 
*We cannot ensure that the demo itself is free of bugs, so users 
*should be responsible for the technical problems and consequences
*caused by the use of their own products.
*Copyright: Copyright (c) MiLianKe
*All rights reserved.
*Revision: 4.2
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

module ui_fdma_test#
(
parameter AXI_ADDR_WIDTH  = 32,            //设置AXI总线地址位宽
parameter AXI_DATA_WIDTH  = 256,           //设置AXI4总线数据位宽
parameter TEST_MEM_SIZE   = 32'd409600,    //设置测试内存地址空间大小
parameter FDMA_BURST_LEN  = 16'd1024,      //设置FDMA每次burst长度
parameter ADDR_MEM_OFFSET = 1024*1024*20   //设置测试内存起始地址
)
(
input                              I_clk,  //系统时钟
input                              I_fdma_rstn, //系统复位
output     [AXI_ADDR_WIDTH-1 : 0]  O_fdma_waddr,//fdma写地址
output reg                         O_fdma_wareq,//synthesis keep//fdma写请求
output     [15: 0]                 O_fdma_wsize,//synthesis keep//fdma写数据大小                                     
input                              I_fdma_wbusy,//synthesis keep//fdma写操作忙		
output     [AXI_DATA_WIDTH-1 : 0]  O_fdma_wdata,//synthesis keep//fdma写数据
input                              I_fdma_wvalid,//synthesis keep//fdma写数据有效
output                             O_fdma_wready,//fdma写准备好

output     [AXI_ADDR_WIDTH-1 : 0]  O_fdma_raddr, //fdma读地址
output reg                         O_fdma_rareq, //synthesis keep//fdma读请求
output     [15: 0]                 O_fdma_rsize, //synthesis keep//fdma读大小                                    
input                              I_fdma_rbusy, //synthesis keep//fdma读忙			
input      [AXI_DATA_WIDTH-1 : 0]  I_fdma_rdata, //synthesis keep//fdma读数据
input                              I_fdma_rvalid, //synthesis keep//fdma读数据有效
output                             O_fdma_rready, //fdma读准备好
output                             test_error	  //synthesis keep//数据比对有错误
); 
    
assign O_fdma_rready = 1'b1; //预留信号设置为1
assign O_fdma_wready = 1'b1; //预留信号设置为1   
    
localparam WRITE1 = 0;
localparam WRITE2 = 1;
localparam READ1  = 2;
localparam READ2  = 3;
localparam ADDR_INC = FDMA_BURST_LEN*AXI_DATA_WIDTH/8; //设置每一次FDMA传输结束后，下次一传输的地址增量

localparam TN  = AXI_DATA_WIDTH/16; //该参数用于方便设置写通道测试数据

reg [AXI_ADDR_WIDTH-1: 0] O_fdma_waddr_r;
reg [15 :0] fdma_wdata_r;//synthesis keep
reg [15 :0] fdma_rcnt = 0;//synthesis keep
reg [2  :0] T_S = 0;

assign O_fdma_waddr = O_fdma_waddr_r + ADDR_MEM_OFFSET;//写通道地址
assign O_fdma_raddr = O_fdma_waddr; //读通道地址，每次写完后，启动读操作

assign O_fdma_wdata ={TN{fdma_wdata_r}};//写通道测试数据

assign O_fdma_wsize = FDMA_BURST_LEN; //FDMA burst 写通道长度
assign O_fdma_rsize = FDMA_BURST_LEN; //FDMA burst 读通道长度


reg [10:0] rst_cnt = 0;

//复位模块，异步转同步，延迟复位
always @(posedge I_clk  or  negedge I_fdma_rstn)
    if(I_fdma_rstn == 1'b0)begin
        rst_cnt <=0;
    end 
    else begin
        if(rst_cnt[10] == 1'b0)
            rst_cnt <= rst_cnt + 1'b1;
        else 
            rst_cnt <= rst_cnt;
    end

//读写状态机
always @(posedge I_clk )begin
    if(rst_cnt[10] == 1'b0)begin //初始化信号
        T_S <=0;   
        O_fdma_wareq  <= 1'b0; 
        O_fdma_rareq  <= 1'b0; 
        O_fdma_waddr_r <=0;  
        fdma_wdata_r   <= 0;     
    end 
    else begin
        case(T_S)     
        WRITE1:begin //写状态1
            if(O_fdma_waddr_r==TEST_MEM_SIZE) O_fdma_waddr_r<=0;  //判断测试内存大小是否测完，如果测完则回到相对地址0
                if(!I_fdma_wbusy)begin //FDMA非忙
                    O_fdma_wareq  <= 1'b1; //发送写请求信号
                    fdma_wdata_r    <= 0;  //初始化写数据
                end
                if(O_fdma_wareq&&I_fdma_wbusy)begin//当写请求有效，并且总线变忙，则进入下个状态
                    O_fdma_wareq  <= 1'b0; //清除写请求信号
                    T_S         <= WRITE2; //进入写状态机2
                end
        end
        WRITE2:begin //写状态2
            if(!I_fdma_wbusy) begin //等待fdma_wbusy非忙,代表一次FDMA写传输已经结束
                 T_S <= READ1; //进入读状态1
                 fdma_wdata_r  <= 0;//清除写数据寄存器
            end 
            else if(I_fdma_wvalid) begin //fdma_wvalid有效的每个时钟代表写入有效数据
                 fdma_wdata_r   <= fdma_wdata_r + 1'b1;//以加计数器数据作为测试数据写入
            end
        end
        
        READ1:begin//读状态1
            if(!I_fdma_rbusy)begin //等待fdma控制器非忙
                O_fdma_rareq  <= 1'b1; //发送读请求信号
                fdma_rcnt   <= 0;      //设置fdma_读数据计数器为0，这个计数器用于比对数据是否正确
            end
            if(O_fdma_rareq&&I_fdma_rbusy)begin //当读请求有效，并且总线变忙，则进入下个状态
                 O_fdma_rareq  <= 1'b0; //清除读请求信号
                 T_S         <= READ2;  //进入读状态机2
            end 
        end
        READ2:begin//读状态2
            if(!I_fdma_rbusy) begin //等待fdma_wbusy非忙,代表一次FDMA读传输已经结束
                 T_S <= WRITE1;//进入写状态1
                 O_fdma_waddr_r  <= O_fdma_waddr_r + ADDR_INC;//下一次写地址增加
            end 
            else if(I_fdma_rvalid) begin //fdma_rvalid有效的每个时钟代表读出有效数据
                fdma_rcnt <= fdma_rcnt + 1'b1; //这个计数器用于比对数据是否正确
            end
        end   
        default:
            T_S <= WRITE1;     
        endcase
    end
  end
  
//wire test_error; //synthesis keep
reg [15:0]fdma_rdata_r = 0 ;// synthesis keep
reg [15:0]fdma_rcnt_r =0;// synthesis keep
reg fdma_rvalid_r = 0;// synthesis keep

//对数据打怕同步
always @(posedge I_clk )begin
    fdma_rdata_r  <= I_fdma_rdata;
    fdma_rvalid_r <= I_fdma_rvalid;
    fdma_rcnt_r   <= fdma_rcnt;

end

assign test_error = (fdma_rvalid_r && (fdma_rcnt_r[15:0] != fdma_rdata_r[15:0])); //比对数据是否真确

cwc X_cwc (
	.clk(I_clk), 
	.probe0(fdma_wdata_r),
 	.probe1(O_fdma_wareq),
	.probe2(I_fdma_wvalid),
	.probe3(O_fdma_wready),
	.probe4(I_fdma_wbusy),
	.probe5(fdma_rdata_r),
    .probe6(fdma_rcnt_r),
	.probe7(I_fdma_rvalid),
	.probe8(O_fdma_rready),
	.probe9(O_fdma_rareq),
	.probe10(I_fdma_rbusy),
	.probe11(T_S),
	.probe12(test_error)

);
 
 
endmodule
