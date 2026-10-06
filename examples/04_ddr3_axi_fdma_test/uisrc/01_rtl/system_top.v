`timescale 1ns/1ns
/*******************************MILIANKE*******************************
*Company : MiLianKe Electronic Technology Co., Ltd.
*WebSite:https://www.milianke.com
*TechWeb:https://www.uisrc.com
*tmall-shop:https://milianke.tmall.com
*jd-shop:https://milianke.jd.com
*taobao-shop1: https://milianke.taobao.com
*Create Date: 2019/12/17
*Module Name:run_led
*File Name:run_led.v
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
*3) _n activ low
*4) _dg debug signal 
*5) _r delay or register
*6) S_ state mechine
*********************************************************************/
`timescale 1ps/1ps

`define DRAM_BYTE_NUM 2   // 1 = x8, 2 = x16,4 = x32,8=x64
`define DRAM_SIZE    "2G"     // AP106,AP102=2G ,AP104=4G    1G , 2G , 4G = 256x16bit, 8G    ,ONE DDR particle capacity

//`define XLNX_NATIVE
//`define ALC_NATIVE  
`define MC_AXI  
 
//`define AXI_ATG  
//`define ATG   
//`define DFI
  
module example_top#(
parameter DRAM_TYPE       = "DDR3"  ,            //"DDR4" "DDR3"
parameter ECC             = "OFF",
parameter APP_ADDR_WIDTH  = (`DRAM_SIZE=="1G")?26:(`DRAM_SIZE=="2G")?27:(`DRAM_SIZE == "4G")?28:(`DRAM_SIZE == "8G")?29:28, //512Mx16bit=29 ,256Mx16bit=28 ,128Mx16bit=27,64Mx16bit = 26,
parameter AXI_ID_WIDTH    =  4,                                                                                   
parameter APP_DATA_WIDTH  = (ECC == "ON")? (`DRAM_BYTE_NUM-1)*8*8 : `DRAM_BYTE_NUM*8*8,
parameter APP_MASK_WIDTH  = (ECC == "ON")? (`DRAM_BYTE_NUM-1)*8   : `DRAM_BYTE_NUM*8,
parameter AXI_ADDR_WIDTH  = APP_ADDR_WIDTH+3,
parameter AXI_DATA_WIDTH  = APP_DATA_WIDTH,
parameter DQ_WIDTH        = `DRAM_BYTE_NUM * 8,
parameter DQS_WIDTH       = `DRAM_BYTE_NUM,
parameter DM_WIDTH        = `DRAM_BYTE_NUM,
parameter ADDR_WIDTH      = (DRAM_TYPE=="DDR4")?17:(`DRAM_SIZE=="1G")?13:(`DRAM_SIZE=="2G")?14:(`DRAM_SIZE == "4G")?15:(`DRAM_SIZE == "8G")?16:15, // 512Mx16bit=16 ,256Mx16bit=15,128Mx16bit=14,64Mx16bit=13
parameter ROW_WIDTH       = (`DRAM_SIZE=="1G")?13:(`DRAM_SIZE=="2G")?14:(`DRAM_SIZE == "4G")?15:(`DRAM_SIZE == "8G")?16:15,                        // 512Mx16bit=16 ,256Mx16bit=15,128Mx16bit=14,64Mx16bit=13
parameter COL_WIDTH       = 10,                  //
parameter BA_WIDTH        = 3,                   //
parameter BG_WIDTH        = 1,                   //
parameter ODT_WIDTH       = 1,                   // PP phy 2, single phy 1
parameter CKE_WIDTH       = 1,                   // PP phy 2, single phy 1
parameter CS_WIDTH        = 1                    // PP phy 2, single phy 1

)(
    input                           I_ddr_clk	,
    //input                           I_rst_n   	,
	
	//DDR 
    output    [ADDR_WIDTH-1:0]      ddr_addr    , 
    output    [  BA_WIDTH-1:0]      ddr_ba      ,
    output    [ CKE_WIDTH-1:0]      ddr_cke     ,
    output    [ ODT_WIDTH-1:0]      ddr_odt     ,
    output    [  CS_WIDTH-1:0]      ddr_cs_n    ,
    output                          ddr_ras_n   ,
    output                          ddr_cas_n   ,
    output                          ddr_we_n    ,
    output                          ddr_ck_p    ,
    output                          ddr_ck_n    ,
    output                          ddr_reset_n ,
    inout     [  DM_WIDTH-1:0]      ddr_dm  	,
    inout     [  DQ_WIDTH-1:0]      ddr_dq      ,
    inout     [ DQS_WIDTH-1:0]      ddr_dqs_n   ,
    inout     [ DQS_WIDTH-1:0]      ddr_dqs_p   
    //output                          O_uart_txd	,	
    //input                           I_uart_rxd	
	
    //output    [ 3:0]                led   

);                                      

//-------- User Clock --------//
wire                       		S_dfi_clk             ;
wire                       		S_pll_locked          ;
wire                       		S_ddr_init_cal_done   ;

// AXI Write Addr
wire [AXI_ADDR_WIDTH-1:0]      	S_axi_awaddr  	;
wire                           	S_axi_awvalid 	;
wire                           	S_axi_awready 	;
wire   [AXI_ID_WIDTH-1:0]      	S_axi_awid    	;
wire                [7:0]      	S_axi_awlen   	; 
wire                [2:0]      	S_axi_awsize  	; 
wire                [1:0]      	S_axi_awburst 	; 
wire                [0:0]      	S_axi_awlock  	; 
wire                [3:0]      	S_axi_awcache 	; 
wire                [2:0]      	S_axi_awprot  	; 
wire                [3:0]      	S_axi_awqos   	;
// AXI Write Data              		
wire [APP_DATA_WIDTH-1:0]      	S_axi_wdata   	;
wire [APP_MASK_WIDTH-1:0]      	S_axi_wstrb   	;
wire                           	S_axi_wvalid  	;
wire                           	S_axi_wlast   	;
wire                           	S_axi_wready  	;
// Write Response Port         		
wire   [AXI_ID_WIDTH-1:0]      	S_axi_bid     	;    
wire                [1:0]      	S_axi_bresp   	;    
wire                           	S_axi_bvalid  	;    
wire                           	S_axi_bready  	;    
								
// AXI Read Addr               	
wire [AXI_ADDR_WIDTH-1:0]      	S_axi_araddr  	;
wire                           	S_axi_arvalid 	;
wire                           	S_axi_arready 	;
wire [  AXI_ID_WIDTH-1:0]      	S_axi_arid    	;
wire                [7:0]      	S_axi_arlen   	;
wire                [2:0]      	S_axi_arsize  	;
wire                [1:0]      	S_axi_arburst 	;
wire                [0:0]      	S_axi_arlock  	;
wire                [3:0]      	S_axi_arcache 	;
wire                [2:0]      	S_axi_arprot  	;
wire                [3:0]      	S_axi_arqos   	;
// AXI Read Data               		
wire [APP_DATA_WIDTH-1:0]      	S_axi_rdata   	;
wire                           	S_axi_rlast   	;
wire                           	S_axi_rvalid  	;
wire                           	S_axi_rready  	;
wire   [AXI_ID_WIDTH-1:0]      	S_axi_rid     	;
wire                [1:0]      	S_axi_rresp   	;

//MLK_FDMA
wire [AXI_ADDR_WIDTH-1:  0]    	S_fdma_waddr	;   //FDMA写通道地址
wire                           	S_fdma_wareq	;   //FDMA写通道请求
wire [15: 0]                   	S_fdma_wsize	;   //FDMA写通道一次FDMA的传输大小                
wire                           	S_fdma_wbusy	;   //FDMA处于BUSY状态，AXI总线正在写操作
wire [AXI_DATA_WIDTH-1 : 0]    	S_fdma_wdata	;   //FDMA写数据
wire                           	S_fdma_wvalid	;   //FDMA 写有效
wire                           	S_fdma_wready	;   //FDMA写准备好，用户可以写数据
								                    
wire [AXI_ADDR_WIDTH-1:  0]    	S_fdma_raddr	;   //FDMA读通道地址
wire                           	S_fdma_rareq	;   //FDMA读通道请求
wire [15: 0]                   	S_fdma_rsize	;   //FDMA读通道一次FDMA的传输大小                    
wire                           	S_fdma_rbusy	;   //FDMA处于BUSY状态，AXI总线正在读操作	
wire [AXI_DATA_WIDTH-1 : 0]    	S_fdma_rdata	;   //FDMA读数据
wire                           	S_fdma_rvalid	;   //FDMA 读有效
wire                           	S_fdma_rready	;   //FDMA读准备好，用户可以读数据	
wire                           	S_test_error	;   //测试是否有错误，1有错误，0没错误


reg [31:0] dbg_clk_cnt = 32'h0;
always @ ( posedge S_dfi_clk or negedge S_pll_locked )
begin
    if (S_pll_locked == 1'b0)
        dbg_clk_cnt <= 32'h0 ;
    else
        dbg_clk_cnt <= dbg_clk_cnt + 1'b1 ;
end

//assign led[0] = S_pll_locked  & S_ddr_init_cal_done & dbg_clk_cnt[26]   ;
//assign led[1] = !S_axi_rvalid;
//assign led[2] = !S_test_error;   
//assign led[3] = !S_ddr_init_cal_done;


//例化fdma_test模块，对DDR测试
ui_fdma_test#
(
	.AXI_ADDR_WIDTH	(AXI_ADDR_WIDTH		),
	.AXI_DATA_WIDTH	(AXI_DATA_WIDTH		),
	.TEST_MEM_SIZE	(2*1024*1024*1024	),
	.FDMA_BURST_LEN	(16'd1024			),
	.ADDR_MEM_OFFSET(0					)
)
X_ui_fdma_test
(
	.I_clk			(S_dfi_clk			),
	.I_fdma_rstn	(S_ddr_init_cal_done), 
	.O_fdma_waddr	(S_fdma_waddr		),
	.O_fdma_wareq	(S_fdma_wareq		),
	.O_fdma_wsize	(S_fdma_wsize		),                                     
	.I_fdma_wbusy	(S_fdma_wbusy		),		
	.O_fdma_wdata	(S_fdma_wdata		),
	.I_fdma_wvalid	(S_fdma_wvalid		),
	.O_fdma_wready	(S_fdma_wready		),
	
	.O_fdma_raddr	(S_fdma_raddr		),
	.O_fdma_rareq	(S_fdma_rareq		),
	.O_fdma_rsize	(S_fdma_rsize		),                                     
	.I_fdma_rbusy	(S_fdma_rbusy		),			
	.I_fdma_rdata	(S_fdma_rdata		),
	.I_fdma_rvalid	(S_fdma_rvalid		),
	.O_fdma_rready	(S_fdma_rready		),
	.test_error		(S_test_error		)	
); 

//例化米联客uiFDMA AXI 控制器 IP
ui_FDMA#
(
	.M_AXI_B2B_SET		(1				),
	.M_AXI_ID_WIDTH		(AXI_ID_WIDTH	),
	.M_AXI_ADDR_WIDTH	(AXI_ADDR_WIDTH	),//ID位宽
	.M_AXI_DATA_WIDTH	(AXI_DATA_WIDTH	),//内存地址位宽
	.M_AXI_MAX_BURST_LEN(16				) //AXI总线的数据位宽
)                                         //AXI总线的burst 大小，对于AXI4，支持任意长度，对于AXI3以下最大16
X_ui_FDMA                                 
(                                         
	.I_fdma_waddr		(S_fdma_waddr	),
	.I_fdma_wareq		(S_fdma_wareq	),//FDMA写通道地址
	.I_fdma_wsize		(S_fdma_wsize	),//FDMA写通道请求
	.O_fdma_wbusy		(S_fdma_wbusy	),//FDMA写通道一次FDMA的传输大小                                            
					                      //FDMA处于BUSY状态，AXI总线正在写操作  
	.I_fdma_wdata		(S_fdma_wdata	),
	.O_fdma_wvalid		(S_fdma_wvalid	),//FDMA写数据
	.I_fdma_wready		(1'b1			),//FDMA 写有效
	                                      //FDMA写准备好，用户可以写数据
	.I_fdma_raddr		(S_fdma_raddr	),
	.I_fdma_rareq		(S_fdma_rareq	),// FDMA读通道地址
	.I_fdma_rsize		(S_fdma_rsize	),// FDMA读通道请求
	.O_fdma_rbusy		(S_fdma_rbusy	),// FDMA读通道一次FDMA的传输大小                                      
					                      // FDMA处于BUSY状态，AXI总线正在读操作 
	.O_fdma_rdata		(S_fdma_rdata	),
	.O_fdma_rvalid		(S_fdma_rvalid	),// FDMA读数据
	.I_fdma_rready		(1'b1			),// FDMA 读有效
                                          // FDMA读准备好，用户可以读数据
//以下为AXI总线信号		
	.M_AXI_ACLK         (S_dfi_clk		),
	.M_AXI_ARESETN      (S_ddr_init_cal_done),
// Master Interface Write Address Ports
	.M_AXI_AWID         (S_axi_awid		),
	.M_AXI_AWADDR       (S_axi_awaddr	),
	.M_AXI_AWLEN        (S_axi_awlen	),
	.M_AXI_AWSIZE       (S_axi_awsize	),
	.M_AXI_AWBURST      (S_axi_awburst	),
	.M_AXI_AWLOCK       (S_axi_awlock	),
	.M_AXI_AWCACHE      (S_axi_awcache	),
	.M_AXI_AWPROT       (S_axi_awprot	),
	.M_AXI_AWQOS        (S_axi_awqos	),
	.M_AXI_AWVALID      (S_axi_awvalid	),
	.M_AXI_AWREADY      (S_axi_awready	),
// Master Interface Write Data Ports
	.M_AXI_WDATA        (S_axi_wdata	),
	.M_AXI_WSTRB        (S_axi_wstrb	),
	.M_AXI_WLAST        (S_axi_wlast	),
	.M_AXI_WVALID       (S_axi_wvalid	),
	.M_AXI_WREADY       (S_axi_wready	),
// Master Interface Write Response Ports
	.M_AXI_BID          (S_axi_bid		),
	.M_AXI_BRESP        (S_axi_bresp	),
	.M_AXI_BVALID       (S_axi_bvalid	),
	.M_AXI_BREADY       (S_axi_bready	),
// Master Interface Read Address Ports
	.M_AXI_ARID         (S_axi_arid		),
	.M_AXI_ARADDR       (S_axi_araddr	),
	.M_AXI_ARLEN        (S_axi_arlen	),
	.M_AXI_ARSIZE       (S_axi_arsize	),
	.M_AXI_ARBURST      (S_axi_arburst	),
	.M_AXI_ARLOCK       (S_axi_arlock	),
	.M_AXI_ARCACHE      (S_axi_arcache	),
	.M_AXI_ARPROT       (S_axi_arprot	),
	.M_AXI_ARQOS        (S_axi_arqos	),
	.M_AXI_ARVALID      (S_axi_arvalid	),
	.M_AXI_ARREADY      (S_axi_arready	),
// Master Interface Read Data Ports
	.M_AXI_RID          (S_axi_rid		),
	.M_AXI_RDATA        (S_axi_rdata	),
	.M_AXI_RRESP        (S_axi_rresp	),
	.M_AXI_RLAST        (S_axi_rlast	),
	.M_AXI_RVALID       (S_axi_rvalid	),
	.M_AXI_RREADY       (S_axi_rready	)		
);


//例化DDR IP
//===== DDR3 PHY INS =====//
ui_ddr X_ui_ddr (

	.sys_rst_n  		(1'b1			),
    .sys_clk    		(I_ddr_clk		),

// DDRIO
`ifdef MC0_DRAM_DDR4
    .ddr_ck_t       	(				),
    .ddr_ck_c       	(				),
    .ddr_reset_n    	(				),
    .ddr_cke        	(				),
    .ddr_odt        	(				),
    .ddr_cs_n       	(				),
    .ddr_act_n      	(				),
    .ddr_bg         	(				),
    .ddr_ba         	(				),
    .ddr_addr       	(				),
    .ddr_dqs_t      	(				),
    .ddr_dqs_c      	(				),
    .ddr_dq         	(				),
    .ddr_dm_dbi     	(				),
`else
    .ddr_ck_p       	(ddr_ck_p		),    
    .ddr_ck_n       	(ddr_ck_n		),    
    .ddr_reset_n    	(ddr_reset_n	),    
    .ddr_cke        	(ddr_cke		),    
    .ddr_odt        	(ddr_odt		),    
    .ddr_cs_n       	(ddr_cs_n		),    
    .ddr_ras_n      	(ddr_ras_n		),    
    .ddr_cas_n      	(ddr_cas_n		), 		
    .ddr_we_n       	(ddr_we_n		),    
    .ddr_ba         	(ddr_ba			),    
    .ddr_addr       	(ddr_addr		),      
    .ddr_dqs_p      	(ddr_dqs_p		),    
    .ddr_dqs_n      	(ddr_dqs_n		),    
    .ddr_dq         	(ddr_dq			),    
    .ddr_dm            	(ddr_dm			),    
`endif

    .ctl_ram_rst_n     	(				),
    .ctl_ram_cke       	(				),

// user interface ports
    .dfi_clk           	(S_dfi_clk		),
    .pll_locked        	(S_pll_locked	),
    .ddrphy_rst_n      	(				),
    .ddr_init_cal_done 	(S_ddr_init_cal_done),
    .ddr_init_cal_err  	(				),
    .ddr_init_cal_step 	(				),

// mc user interface
`ifdef MC0_MIS_AXI
// AXI Interface
    .axi_aclk          	(				),
    .axi_aresetn       	(				),
// AXI Write Address Channel
    .axi_awid          (S_axi_awid   	),
    .axi_awaddr        (S_axi_awaddr 	),
    .axi_awlen         (S_axi_awlen  	),
    .axi_awsize        (S_axi_awsize 	),
    .axi_awburst       (S_axi_awburst	),
    .axi_awlock        (S_axi_awlock 	),
    .axi_awcache       (S_axi_awcache	),
    .axi_awprot        (S_axi_awprot 	),
    .axi_awqos         (S_axi_awqos  	),
    .axi_awvalid       (S_axi_awvalid	),
    .axi_awready       (S_axi_awready	),
// AXI Write Data Channel                 
    .axi_wdata         (S_axi_wdata 	),
    .axi_wstrb         (S_axi_wstrb 	),
    .axi_wlast         (S_axi_wlast 	),
    .axi_wvalid        (S_axi_wvalid	),
    .axi_wready        (S_axi_wready	),
// AXI Write Response Channel             
    .axi_bid           (S_axi_bid   	),
    .axi_bresp         (S_axi_bresp 	),
    .axi_bvalid        (S_axi_bvalid	),
    .axi_bready        (S_axi_bready	),
// AXI Read Address Channel               
    .axi_arid          (S_axi_arid   	),
    .axi_araddr        (S_axi_araddr 	),
    .axi_arlen         (S_axi_arlen  	),
    .axi_arsize        (S_axi_arsize 	),
    .axi_arburst       (S_axi_arburst	),
    .axi_arlock        (S_axi_arlock 	),
    .axi_arcache       (S_axi_arcache	),
    .axi_arprot        (S_axi_arprot 	),
    .axi_arqos         (S_axi_arqos  	),
    .axi_arvalid       (S_axi_arvalid	),
    .axi_arready       (S_axi_arready	),
// AXI Read Data Channel                  
    .axi_rid           (S_axi_rid   	),
    .axi_rdata         (S_axi_rdata 	),
    .axi_rresp         (S_axi_rresp 	),
    .axi_rlast         (S_axi_rlast 	),
    .axi_rvalid        (S_axi_rvalid	),
    .axi_rready        (S_axi_rready	),
`else
`endif
    .uart_rxd          (I_uart_rxd		),
    .uart_txd		   (O_uart_txd		)
);

 
endmodule

