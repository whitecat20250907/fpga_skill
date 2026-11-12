`timescale 1ns/1ns
/*******************************MILIANKE*******************************
*Company : MiLianKe Electronic Technology Co., Ltd.
*WebSite:https://www.milianke.com
*TechWeb:https://www.uisrc.com
*tmall-shop:https://milianke.tmall.com
*jd-shop:https://milianke.jd.com
*taobao-shop1: https://milianke.taobao.com
*Create Date: 2025/12/10
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
*4) S_system internal signal
*5) n_ activ low
*6) dg_ debug signal
*7) r_ delay or register
*8) s_ state mechine
*********************************************************************/
/*********system_top***********
--本方案采用IMX415摄像头,将图像数据经米联客ISP图像算法处理后,
缓存至DDR中,最终通过HDMI输出1080P_60HZ的图像
*********************************************************************/

`define DRAM_BYTE_NUM 2   	   // 1 = x8, 2 = x16,4 = x32,8=x64
`define DRAM_SIZE    "2G"     // AP106,AP102=2G ,AP104=4G    1G , 2G , 4G = 256x16bit, 8G    ,ONE DDR particle capacity

//`define XLNX_NATIVE
//`define ALC_NATIVE  
`define MC_AXI  
 
//`define AXI_ATG  
//`define ATG   
//`define DFI
  
module system_top#(
parameter DRAM_TYPE       = "DDR3"  ,            //"DDR4" "DDR3"
parameter ECC             = "OFF",
parameter APP_ADDR_WIDTH  = (`DRAM_SIZE=="1G")?26:(`DRAM_SIZE=="2G")?27:(`DRAM_SIZE == "4G")?28:(`DRAM_SIZE == "8G")?29:28, //512Mx16bit=29 ,256Mx16bit=28 ,128Mx16bit=27,64Mx16bit = 26,
parameter AXI_ID_WIDTH    =  4,                                                                                   
parameter APP_DATA_WIDTH  = (ECC == "ON")? (`DRAM_BYTE_NUM-1)*8*8 : `DRAM_BYTE_NUM*8*8,
parameter APP_MASK_WIDTH  = (ECC == "ON")? (`DRAM_BYTE_NUM-1)*8   : `DRAM_BYTE_NUM*8,
parameter AXI_ADDR_WIDTH  = APP_ADDR_WIDTH+$clog2(`DRAM_BYTE_NUM),
parameter AXI_DATA_WIDTH  = APP_DATA_WIDTH,
parameter DQ_WIDTH        = `DRAM_BYTE_NUM * 8,
parameter DQS_WIDTH       = `DRAM_BYTE_NUM,
parameter DM_WIDTH        = `DRAM_BYTE_NUM,
parameter ADDR_WIDTH      = (DRAM_TYPE=="DDR4")?17:(`DRAM_SIZE=="1G")?13:(`DRAM_SIZE=="2G")?14:(`DRAM_SIZE == "4G")?15:(`DRAM_SIZE == "8G")?16:15, // 512Mx16bit=16 ,256Mx16bit=15,128Mx16bit=14,64Mx16bit=13
parameter ROW_WIDTH       = (`DRAM_SIZE=="1G")?13:(`DRAM_SIZE=="2G")?14:(`DRAM_SIZE == "4G")?15:(`DRAM_SIZE == "8G")?16:15,                        // 512Mx16bit=16 ,256Mx16bit=15,128Mx16bit=14,64Mx16bit=13
parameter COL_WIDTH       = 10,                  
parameter BA_WIDTH        = 3,                   
parameter BG_WIDTH        = 1,                   
parameter ODT_WIDTH       = 1,                   
parameter CKE_WIDTH       = 1,                   
parameter CS_WIDTH        = 1                    
)
(
    input                           I_sysclk_25m,	//系统时钟
    input                           I_ddr_clk   ,	//DDR参考时钟
	
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
    inout     [ DQS_WIDTH-1:0]      ddr_dqs_p   ,

	//摄像头配置信号
	output wire 					S_clk_25m	,	//摄像头工作时钟
	output wire 					O_clk_rst	,	//摄像头复位信号,默认上拉
    output wire 					O_cam_scl	,   //I2C总线，SCL时钟
    inout  wire 					IO_cam_sda	,   //I2C总线，SDA数据
	
	//MIPI_RX
	input  wire		    			I_clk_hs_p  ,	
	input  wire	[3:0]				I_data_hs_p , 
	input  wire	[3:0]				I_data_lp_p ,
	input  wire	[3:0]				I_data_lp_n ,
	
	//MIPI_TX
	output 		 					O_clk_hs_p	,
	output 		 					O_clk_lp_p	,
	output 		 					O_clk_lp_n	,
	output 		 [3:0] 				O_data_hs_p	,
	output 		 [3:0] 				O_data_lp_p	,
	output 		 [3:0] 				O_data_lp_n,
    input wire I_uart_rx,
    output wire O_uart_tx,
    input wire I_rk_tx_en,
    output wire O_rk_hs_clk_p,O_rk_lp_clk_p,O_rk_lp_clk_n,
    output wire [3:0] O_rk_hs_data_p,O_rk_lp_data_p,O_rk_lp_data_n
);                                      

//-------- User Clock --------//
wire                       		S_dfi_clk             ;
wire                       		S_ddr_init_cal_done   ;
// The vendor MCU clock produces calibration-done. Assert the application
// reset immediately, but release only after two actual DFI clock edges.
wire S_ddr_app_async_n = S_pll_lock && S_ddr_init_cal_done;
(* ASYNC_REG = "TRUE" *) reg [1:0] S_ddr_app_rst_sync;
always @(posedge S_dfi_clk or negedge S_ddr_app_async_n) begin
    if (!S_ddr_app_async_n) S_ddr_app_rst_sync <= 2'b00;
    else S_ddr_app_rst_sync <= {S_ddr_app_rst_sync[0], 1'b1};
end
wire S_ddr_app_rstn = S_ddr_app_rst_sync[1];


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

wire S_clk_25m;
wire [3:0] S_lane_error;
wire        					S_clk_70m		;
wire        					S_pll_lock		;

wire [7:0]						S_ae			;
wire 							S_cam_cfg_done	;
wire 							S_ae_cfg_done	;
wire 							S_ae_req		;

wire          					S_hs_rx_clk		;  
wire          					S_hs_rx_valid	;  
wire [31 : 0] 					S_hs_rx_data	; 

wire        					S_csi_frame_start;       
wire        					S_csi_frame_end	;         
wire        					S_csi_valid		;             
wire[31:0]  					S_csi_data		;  
	
wire          					S_raw10_frame_start;
wire          					S_raw10_frame_end;
wire          					S_raw10_valid	;
wire [39 : 0] 					S_raw10_data	;

wire [39:0]						S_axis_tdata	;
wire 							S_axis_tvalid	;
wire 							S_axis_tlast	; 
wire 							S_axis_tuser	; 

wire							S_ISP_O_tready 	;
wire [127:0]					S_ISP_O_tdata  	;
wire 							S_ISP_O_tlast  	;
wire 							S_ISP_O_tuser  	;
wire 							S_ISP_O_tvalid 	;

wire [7:0] 						S_wbuf_sync		;
wire [7:0] 						S_rbuf_sync		;
					
wire 							S_ud_wclk		;
wire 							S_ud_wtuser		; 
wire 							S_ud_wtvalid	; 
wire 							S_ud_wtlast		; 
wire 							S_ud_wtready	;  
wire [127:0] 					S_ud_wtdata		;
wire [2:0] S_dbuf_write_diag;

wire [23:0] 					S_ud_rtdata		;  
					
wire        					S_R_vrst		;
wire [23:0] 					S_video_in_data	; 
					
assign O_clk_rst				= 1'b1;
	
assign S_ud_wclk = S_clk_70m;
assign S_ud_wtuser = S_hci_sof;
assign S_ud_wtvalid = S_hci_valid;
assign S_ud_wtlast = S_hci_last;
assign S_ud_wtdata = S_hci_data;
		
assign S_video_in_data 			= S_ud_rtdata;


wire        	S_clk;
wire        	S_clk_x2;
wire        	S_clk_x4;
wire        	S_clk_x4_90d;
wire        	S_lp_clk;
wire        	S_pll1_lock;

wire        	S_rst;  //synthesis keep
wire        	S_config_start;
wire        	S_config_done;
	
wire        	S_24b_vsync;  //synthesis keep
wire        	S_24b_hsync;  //synthesis keep
wire        	S_24b_de;  //synthesis keep
wire [23:0] 	S_24b_data;  //synthesis keep
	
wire        	S_32b_vsync;  //synthesis keep
wire        	S_32b_hsync;  //synthesis keep
wire        	S_32b_de;  //synthesis keep
wire [31:0] 	S_32b_data;  //synthesis keep
	
wire        	S_hs_en;  //synthesis keep           
wire        	S_hs_last;  //synthesis keep	       
wire [31:0] 	S_hs_data;  //synthesis keep    
	
wire        	S_lp_tx_valid;
wire        	S_lp_tx_last;
wire [ 7:0] 	S_lp_tx_data;
wire        	S_lp_tx_ready;



//PLL时钟管理IP 
ui_pll X_ui_pll (
    .refclk  	(I_sysclk_25m	),
    .reset		(1'b0			),

    .lock		(S_pll_lock		),

    .clk0_out	(S_clk_70m		),
    .clk1_out	(S_clk_25m		),
    .clk2_out	(S_clk			),
    .clk3_out	(S_clk_x2		),
    .clk4_out	(S_clk_x4		),
    .clk5_out	(S_clk_x4_90d	),
    .clk6_out	(S_lp_clk		)
  );

//PH1_LOGIC_ODDR X_cam_clk (
//    .q  		(O_clk_25m	), 
//    .clk		(S_clk_25m	),
//    .d0 		(1'b1		),
//    .d1 		(1'b0		),
//    .rst		(~S_pll_lock)
//  );
  

//手动配置相机AE
ui_ae_set X_ui_ae_set (
	.I_clk			(S_clk_25m		),
	.I_rst			(S_pll_lock		), 
	.I_btn			( 2'b00			),
	.I_cam_cfg_done	(S_cam_cfg_done	),
	.I_ae_cfg_done	(S_ae_cfg_done	),
	.O_ae_req		(S_ae_req		),
	.O_ae			(S_ae			)
  );
  
//IIC协议配置摄像头寄存器
ui_cfg_imx415#(
	.CLK_DIV(25_000_000/100_000-1)
	)
X_ui_cfg_imx415(
	.I_clk			(S_clk_25m		),  
	.I_rst_n		(S_pll_lock		),  
	.I_ae_req		(S_ae_req		),
	.I_ae_data		(S_ae			),
	.O_cam_scl		(O_cam_scl		), 
	.IO_cam_sda		(IO_cam_sda		), 
	.O_cfg_done		(S_cam_cfg_done	),
	.O_ae_cfg_done	(S_ae_cfg_done	)
  );

//mipi_rx
mipi_dphy_rx_over_lvds_wrapper#(
    .DEVICE           ( "PH1"		 ),
    .LANE_NUM         ( 4    		 )
)X_mipi_dphy_rx_over_lvds_wrapper(
    .I_lp_clk         ( S_clk_70m    ),
    .I_rst            ( ~S_pll_lock  ),

    .I_mipi_clk_p     ( I_clk_hs_p   ),
    .I_mipi_data_hs_p ( I_data_hs_p  ),
    .I_mipi_data_lp_p ( I_data_lp_p  ),
    .I_mipi_data_lp_n ( I_data_lp_n  ),

    .I_lane_hs_invert ( 4'b0000      ),
    .I_lane_lp_invert ( 4'b0000      ),

    .O_hs_rx_clk      ( S_hs_rx_clk  ),
    .O_hs_rx_valid    ( S_hs_rx_valid),
    .O_hs_rx_data     ( S_hs_rx_data ),

    .O_lp_rx_lane0_p  (				 ),
    .O_lp_rx_lane0_n  (				 ),

    .O_lane_error     ( S_lane_error )
);

// Protocol first byte is high byte in the preserved 06 PHY wrapper.
// The frontend adapts bytes, verifies exact WC/CRC/ECC and carries explicit
// line-end through a real Gray CDC FIFO to the stable ISP clock domain.
wire S_axis_tready;
wire [31:0] S_csi_raw_packets, S_csi_crc_errors, S_csi_ecc_errors;
wire [31:0] S_csi_wc_errors, S_csi_timeout_errors, S_csi_fifo_overflows;
wire S_csi_error_pulse;
(* async_reg="true" *) reg [1:0] video_reset_sync=0;
wire S_capture_async_n=S_ddr_app_async_n && S_cam_cfg_done;
always @(posedge S_clk_70m or negedge S_capture_async_n)
 if(!S_capture_async_n) video_reset_sync<=0;else video_reset_sync<={video_reset_sync[0],1'b1};
wire S_video_rstn=video_reset_sync[1];
ui06_csi_frontend X_ui06_csi_frontend (
 .I_hs_clk(S_hs_rx_clk), .I_reset_n(S_capture_async_n),
 .I_hs_valid(S_hs_rx_valid), .I_hs_data(S_hs_rx_data),
 .I_video_clk(S_clk_70m), .I_video_reset_n(S_capture_async_n),
 .O_tdata(S_axis_tdata), .O_tvalid(S_axis_tvalid),
 .O_tuser(S_axis_tuser), .O_tlast(S_axis_tlast), .I_tready(S_axis_tready),
 .O_raw_packets(S_csi_raw_packets), .O_crc_errors(S_csi_crc_errors),
 .O_ecc_errors(S_csi_ecc_errors), .O_wc_errors(S_csi_wc_errors),
 .O_timeout_errors(S_csi_timeout_errors), .O_fifo_overflows(S_csi_fifo_overflows),
 .O_error_pulse(S_csi_error_pulse)
);

(* async_reg="true" *) reg [2:0] telemetry_reset=0;
// New production preprocessing, same75MHz AXIS and real downstream ready.
wire S_hci_ready,S_hci_valid,S_hci_sof,S_hci_last,S_hci_eof,S_hci_lut_valid;
wire [127:0] S_hci_data;wire [13:0] S_hci_output_config;
wire [31:0] S_hci_errors,S_hci_frames;
wire [13:0] host_hci_config;wire [31:0] host_hci_sequence,host_hci_rejected,host_hci_packets;
wire host_hci_valid;wire [543:0] hci_config_snapshot;
wire [191:0] host_roi_windows;wire [2:0] host_roi_enable;
wire [31:0] host_roi_sequence,host_roi_rejected,host_roi_packets;
wire [15:0] host_roi_ttl;wire host_roi_valid;
wire [31:0] hci_config_status,hci_config_clock;
hci02_command_rx u_hci_control(.clk(I_sysclk_25m),.rst_n(telemetry_reset[2]),.uart_rx(I_uart_rx),
 .config_value(host_hci_config),.accepted_sequence(host_hci_sequence),.rejected(host_hci_rejected),
 .complete_packets(host_hci_packets),.config_valid(host_hci_valid),
 .roi_windows(host_roi_windows),.roi_enable(host_roi_enable),.roi_sequence(host_roi_sequence),
 .roi_rejected(host_roi_rejected),.roi_packets(host_roi_packets),.roi_ttl(host_roi_ttl),.roi_valid(host_roi_valid));
csi_stats_snapshot #(.PERIOD(7500),.STATS_WIDTH(512)) u_hci_config_snapshot(
 .src_clk(I_sysclk_25m),.dst_clk(S_clk_70m),.rst_n(S_capture_async_n),
 .src_stats({host_roi_packets,host_roi_rejected,12'd0,host_roi_valid,host_roi_enable,host_roi_ttl,
 host_roi_sequence,host_roi_windows,32'd0,31'd0,host_hci_valid,host_hci_packets,host_hci_rejected,host_hci_sequence,18'd0,host_hci_config}),
 .snapshot(hci_config_snapshot),.status(hci_config_status),.clock_delta(hci_config_clock));
wire [13:0] pending_hci_config=hci_config_snapshot[128]?hci_config_snapshot[13:0]:14'd8192;
reg [31:0] hci_applied_sequence=0;reg [13:0] hci_applied_config=14'd8192;
always @(posedge S_clk_70m or negedge S_video_rstn)
 if(!S_video_rstn)begin hci_applied_sequence<=0;hci_applied_config<=14'd8192;end
 else if(S_ISP_O_tvalid&&S_hci_ready&&S_ISP_O_tuser)begin
  hci_applied_sequence<=hci_config_snapshot[63:32];hci_applied_config<=pending_hci_config;
 end
// Common nominal microsecond time. RAW SOF tag survives actual ISP latency.
wire [63:0] hci02_source_time,hci02_video_time,hci02_tag_time;
wire hci02_tag_valid;wire [31:0] hci02_tag_id,hci02_raw_frames,hci02_isp_frames,hci02_tag_overflows,hci02_tag_underflows;
wire [3:0] hci02_tag_queued;wire [2623:0] hci02_roi_stats;
wire [31:0] hci02_eye_fifo_occupancy,hci02_eye_fifo_high_water,hci02_eye_fifo_errors;
hci02_timebase u_hci02_time(.source_clk(I_sysclk_25m),.video_clk(S_clk_70m),.rst_n(S_capture_async_n),
 .source_time_us(hci02_source_time),.video_time_us(hci02_video_time));
hci02_frame_tags u_hci02_tags(.clk(S_clk_70m),.rst_n(S_video_rstn),
 .raw_sof_accepted(S_axis_tvalid&&S_axis_tready&&S_axis_tuser),
 .isp_sof_accepted(S_ISP_O_tvalid&&S_hci_ready&&S_ISP_O_tuser),.time_us(hci02_video_time),
 .tag_valid(hci02_tag_valid),.tag_time_us(hci02_tag_time),.tag_frame_id(hci02_tag_id),
 .raw_frames(hci02_raw_frames),.isp_frames(hci02_isp_frames),.overflow_count(hci02_tag_overflows),.underflow_count(hci02_tag_underflows),.queued(hci02_tag_queued));
wire [127:0] hci02_producer_data;wire hci02_producer_valid,hci02_producer_sof,hci02_producer_last,hci02_producer_eof,hci02_buffer_ready;
wire [13:0] hci02_producer_config;wire [1:0] hci02_video_buffer_occupancy;
hci02_video_readycut u_hci02_video_buffer(.clk(S_clk_70m),.rst_n(S_video_rstn),
 .s_data(hci02_producer_data),.s_valid(hci02_producer_valid),.s_sof(hci02_producer_sof),.s_last(hci02_producer_last),.s_eof(hci02_producer_eof),.s_config(hci02_producer_config),.s_ready(hci02_buffer_ready),
 .m_ready(S_ud_wtready),.m_data(S_hci_data),.m_valid(S_hci_valid),.m_sof(S_hci_sof),.m_last(S_hci_last),.m_eof(S_hci_eof),.m_config(S_hci_output_config),.occupancy(hci02_video_buffer_occupancy));
wire [2:0] crop_valid,crop_sof,crop_last,crop_eof;
wire [383:0] crop_rgb;wire [95:0] crop_gray;wire [8:0] crop_count;
wire [47:0] crop_x,crop_y,crop_origin_x,crop_origin_y,crop_width,crop_height;
wire [31:0] crop_frame_id,crop_sequence;wire [63:0] crop_time_us;wire [7:0] crop_flags;
wire [1:0] feature_valid;wire [1535:0] feature_result;wire [63:0] feature_received,feature_skipped,feature_deadline;
hci02_vision_pipeline #(.WIDTH(1920),.HEIGHT(1080))u_hci_preprocess(
 .clk(S_clk_70m),.rst_n(S_video_rstn),.s_data(S_ISP_O_tdata),.s_valid(S_ISP_O_tvalid),
 .s_sof(S_ISP_O_tuser),.s_last(S_ISP_O_tlast),.hci_config(pending_hci_config),.s_ready(S_hci_ready),
 .roi_windows(hci_config_snapshot[383:192]),.roi_sequence(hci_config_snapshot[415:384]),
 .roi_ttl(hci_config_snapshot[431:416]),.roi_enable(hci_config_snapshot[434:432]),.roi_valid(hci_config_snapshot[435]),
 .frame_tag_valid(hci02_tag_valid),.frame_tag_id(hci02_tag_id),.frame_time_us(hci02_tag_time),
 .m_ready(hci02_buffer_ready),.m_data(hci02_producer_data),.m_valid(hci02_producer_valid),.m_sof(hci02_producer_sof),.m_last(hci02_producer_last),.m_eof(hci02_producer_eof),
 .m_config(hci02_producer_config),.hci_errors(S_hci_errors),.hci_frames(S_hci_frames),.hci_lut_valid(S_hci_lut_valid),.stats(hci02_roi_stats),
 .crop_valid(crop_valid),.crop_sof(crop_sof),.crop_last(crop_last),.crop_eof(crop_eof),
 .crop_rgb(crop_rgb),.crop_gray(crop_gray),.crop_count(crop_count),.crop_x(crop_x),.crop_y(crop_y),
 .crop_origin_x(crop_origin_x),.crop_origin_y(crop_origin_y),.crop_width(crop_width),.crop_height(crop_height),
 .crop_frame_id(crop_frame_id),.crop_sequence(crop_sequence),.crop_time_us(crop_time_us),.crop_flags(crop_flags),
 .feature_valid(feature_valid),.feature_result(feature_result),.feature_received(feature_received),.feature_skipped(feature_skipped),.feature_deadline(feature_deadline),
 .fifo_occupancy(hci02_eye_fifo_occupancy),.fifo_high_water(hci02_eye_fifo_high_water),.roi_buffer_errors(hci02_eye_fifo_errors));


// RK CSI occupies its original, distinct FMC MIPI output pins. The 7-inch
// DSI/DDR display, camera PLL/configuration and complete ISP remain intact.
wire S_rk_lock,S_rk_clk,S_rk_clk_x2,S_rk_clk_x4,S_rk_clk_x4_90d,S_rk_lp_clk;
hci03_rk_pll u_rk_pll(.refclk(I_sysclk_25m),.reset(1'b0),.lock(S_rk_lock),.clk0_out(),
 .clk1_out(S_rk_clk),.clk2_out(S_rk_clk_x2),.clk3_out(S_rk_clk_x4),.clk4_out(S_rk_clk_x4_90d),.clk5_out(S_rk_lp_clk));
wire rk_link_async_n=S_capture_async_n&&S_rk_lock&&I_rk_tx_en;
(* ASYNC_REG="TRUE" *)reg [1:0] rk_phy_reset_sync;
always @(posedge S_rk_clk or negedge rk_link_async_n)
 if(!rk_link_async_n)rk_phy_reset_sync<=0;else rk_phy_reset_sync<={rk_phy_reset_sync[0],1'b1};
wire rk_phy_reset=~rk_phy_reset_sync[1];
wire rk_hs_valid,rk_hs_last,rk_hs_ready;wire [31:0] rk_hs_data;
wire [1663:0] rk_source_stats;wire [511:0] rk_destination_stats;
hci03_link_pipeline u_rk_link(.src_clk(S_clk_70m),.dst_clk(S_rk_clk),.link_async_n(rk_link_async_n),
 .isp_sof_accepted(S_ISP_O_tvalid&&S_hci_ready&&S_ISP_O_tuser&&hci02_tag_valid),.isp_frame_id(hci02_tag_id),
 .crop_valid(crop_valid),.crop_sof(crop_sof),.crop_last(crop_last),.crop_eof(crop_eof),.crop_rgb(crop_rgb),.crop_gray(crop_gray),.crop_count(crop_count),
 .crop_x(crop_x),.crop_y(crop_y),.crop_origin_x(crop_origin_x),.crop_origin_y(crop_origin_y),.crop_width(crop_width),.crop_height(crop_height),
 .crop_frame_id(crop_frame_id),.crop_sequence(crop_sequence),.crop_time_us(crop_time_us),.crop_flags(crop_flags),
 .feature_valid(feature_valid),.feature_result(feature_result),.feature_received(feature_received),.feature_skipped(feature_skipped),.feature_deadline(feature_deadline),
 .hs_ready(rk_hs_ready),.hs_en(rk_hs_valid),.hs_last(rk_hs_last),.hs_data(rk_hs_data),.source_stats(rk_source_stats),.destination_stats(rk_destination_stats));
mipi_dphy_tx_wrapper #(.LANE_NUM(4),.HS_TX_FIFO_TYPE("DRAM"),.LP_TX_FIFO_TYPE("DRAM"),.LP_TX_MAX_DATA_LENGTH(8),
 .CLK_LANE_MODE("INTERRUPT"),.T_DATA_LPX(10),.T_DATA_HS_PREPARE(7),.T_DATA_HS_ZERO(30),.T_DATA_HS_TRAIL(20),
 .T_CLK_LPX(10),.T_CLK_PREPARE(10),.T_CLK_ZERO(10),.T_CLK_PRE(10),.T_CLK_POST(10),.T_CLK_TRAIL(10))u_rk_dphy_tx(
 .I_hs_clk(S_rk_clk),.I_hs_clk_x2(S_rk_clk_x2),.I_hs_clk_x4(S_rk_clk_x4),.I_hs_clk_x4_90d(S_rk_clk_x4_90d),.I_rst(rk_phy_reset),
 .I_hs_tx_valid(rk_hs_valid),.I_hs_tx_data(rk_hs_data),.I_hs_tx_last(rk_hs_last),.O_hs_tx_ready(rk_hs_ready),
 .I_lpdt_clk(S_rk_lp_clk),.I_lp_tx_valid(1'b0),.I_lp_tx_data(8'd0),.I_lp_tx_last(1'b0),.O_lp_tx_ready(),
 .O_clk_hs_p(O_rk_hs_clk_p),.O_data_hs_p(O_rk_hs_data_p),.O_clk_lp_p(O_rk_lp_clk_p),.O_clk_lp_n(O_rk_lp_clk_n),
 .O_data_lp_p(O_rk_lp_data_p),.O_data_lp_n(O_rk_lp_data_n));
wire [1695:0] rk_source_snapshot;wire [543:0] rk_destination_snapshot;
wire [31:0] rk_source_status,rk_source_clock,rk_destination_status,rk_destination_clock;
csi_stats_snapshot #(.PERIOD(1250000),.STATS_WIDTH(1664))u_rk_source_snapshot(
 .src_clk(S_clk_70m),.dst_clk(I_sysclk_25m),.rst_n(S_pll_lock),.src_stats(rk_source_stats),
 .snapshot(rk_source_snapshot),.status(rk_source_status),.clock_delta(rk_source_clock));
csi_stats_snapshot #(.PERIOD(1250000),.STATS_WIDTH(512))u_rk_destination_snapshot(
 .src_clk(S_rk_clk),.dst_clk(I_sysclk_25m),.rst_n(S_pll_lock&&S_rk_lock),.src_stats(rk_destination_stats),
 .snapshot(rk_destination_snapshot),.status(rk_destination_status),.clock_delta(rk_destination_clock));

// ISP ports retain legacy names: O_tready=input, I_tready=output.
ui_isp_top X_ui_isp_top (
	.I_clk		     (S_clk_70m		),
	.I_rst_n         (S_video_rstn		),
	.I_tlast         (S_axis_tlast 		),
	.I_tuser         (S_axis_tuser 		),
	.I_tdata         (S_axis_tdata 		),
	.I_tvalid        (S_axis_tvalid		),
	.I_tdest(10'd0),
	.O_tready(S_hci_ready),
	.O_tdata         (S_ISP_O_tdata 	),
	.O_tlast         (S_ISP_O_tlast 	),
	.O_tuser         (S_ISP_O_tuser 	),
	.O_tvalid        (S_ISP_O_tvalid	),
	.I_tready(S_axis_tready)
  );


//设置3帧缓存，读延迟写1帧
ui_setvbuf#(
	.BUF_DELAY		(1			),
	.BUF_LENTH		(3			)
)
X_ui_setvbuf
(
	.I_bufn			(S_wbuf_sync),
	.O_bufn			(S_rbuf_sync)
);


//例化uidbuf 控制器
ui_dbuf# (  
	.AXI_DATA_WIDTH	(AXI_DATA_WIDTH		),//AXI总线数据位宽
	.AXI_ADDR_WIDTH	(AXI_ADDR_WIDTH		),//AXI总线地址位宽
	.ENABLE_VSYNC	(1					),
	.W_BUFDEPTH		(2048				),//写通道AXI设置FIFO缓存大小
	.W_DATAWIDTH	(128				),//写通道AXI设置数据位宽大小
	.W_BASEADDR		(0					),//写通道设置内存起始地址
	.W_DSIZEBITS	(25					),//写通道设置缓存数据的增量地址大小，用于FDMA DBUF 计算帧缓存起始地址
	.W_XSIZE		(480				),//写通道设置X方向的数据大小，代表了每次FDMA 传输的数据长度
	.W_XSTRIDE		(480				),//写通道设置X方向的Stride值，主要用于图形缓存应用
	.W_YSIZE		(1080				),//写通道设置Y方向值，代表了进行了多少次XSIZE传输
	.W_XDIV			(2					),//写通道对X方向数据拆分为XDIV次传输，减少FIFO的使用
	.W_BUFSIZE		(3					),//写通道设置帧缓存大小，目前最大支持128帧，可以修改参数支持更缓存数
		
	.R_BUFDEPTH		(2048				),//读通道AXI设置FIFO缓存大小
	.R_DATAWIDTH	(32					),//读通道AXI设置数据位宽大小
	.R_BASEADDR		(0					),//读通道设置内存起始地址
	.R_DSIZEBITS	(25					),//读通道设置缓存数据的增量地址大小，用于FDMA DBUF 计算帧缓存起始地址
	.R_XSIZE		(1024				),//读通道设置X方向的数据大小，代表了每次FDMA 传输的数据长度
	.R_XSTRIDE		(1920				),//读通道设置X方向的Stride值，主要用于图形缓存应用
	.R_YSIZE		(600				),//读通道设置Y方向值，代表了进行了多少次XSIZE传输
	.R_XDIV			(2					),//读通道对X方向数据拆分为XDIV次传输，减少FIFO的使用
	.R_BUFSIZE		(3					) //读通道设置帧缓存大小，目前最大支持128帧，可以修改参数支持更缓存数
)
X_ui_dbuf
(
	.I_ui_clk		(S_dfi_clk			),
	.I_ui_rstn		(S_ddr_app_rstn),
		
	.I_W_en      	(1					),
	.I_W_wclk    	(S_ud_wclk			),
	.I_W_tuser   	(S_ud_wtuser		),
	.I_W_tvalid  	(S_ud_wtvalid		),
	.I_W_tdata   	(S_ud_wtdata		),
	.I_W_tlast   	(S_ud_wtlast		),
	.O_W_tready  	(S_ud_wtready		),
	.O_write_diag (S_dbuf_write_diag),
	.O_W_sync_cnt	(S_wbuf_sync		),
	.I_W_buf     	(S_wbuf_sync		),
	
	.I_R_en      	(S_24b_vsync		),
	.I_R_rclk    	(S_clk				),
	.I_R_tready  	(S_24b_de			),
	.O_R_tuser   	(					),
	.O_R_tvalid  	(					),
	.O_R_tdata   	(S_ud_rtdata		),
	.O_R_tlast   	(					),
	.O_R_sync_cnt	(					),
	.I_R_buf     	(S_rbuf_sync		),
	.O_R_vrst    	(S_R_vrst			),
	
	.O_fdma_waddr 	(S_fdma_waddr		),
	.O_fdma_wareq 	(S_fdma_wareq		),
	.O_fdma_wsize 	(S_fdma_wsize		),
	.I_fdma_wbusy 	(S_fdma_wbusy		),
	.O_fdma_wdata 	(S_fdma_wdata		),
	.I_fdma_wvalid	(S_fdma_wvalid		),
	.O_fdma_wready	(S_fdma_wready		),
	.O_fdma_raddr 	(S_fdma_raddr		),
	.O_fdma_rareq 	(S_fdma_rareq		),
	.O_fdma_rsize 	(S_fdma_rsize		),
	.I_fdma_rbusy 	(S_fdma_rbusy		),
	.I_fdma_rdata 	(S_fdma_rdata		),
	.I_fdma_rvalid	(S_fdma_rvalid		),
	.O_fdma_rready	(S_fdma_rready		)
	//.O_fmda_wbuf  	(fdma_wbuf			),	
	//.O_fdma_wirq  	(fdma_wirq			),		
	//.O_fmda_rbuf  	(fdma_rbuf			),	
	//.O_fdma_rirq  	(fdma_rirq			)
);

//例化米联客uiFDMA AXI 控制器 IP
ui_FDMA#
(
	.M_AXI_B2B_SET		(1				),
	.M_AXI_ID_WIDTH		(AXI_ID_WIDTH	),//ID位宽
	.M_AXI_ADDR_WIDTH	(AXI_ADDR_WIDTH	),//内存地址位宽
	.M_AXI_DATA_WIDTH	(AXI_DATA_WIDTH	),//AXI总线的数据位宽
	.M_AXI_MAX_BURST_LEN(16				) //AXI总线的burst 大小，对于AXI4，支持任意长度，对于AXI3以下最大16
)
X_ui_FDMA
(
	.I_fdma_waddr		(S_fdma_waddr	),//FDMA写通道地址
	.I_fdma_wareq		(S_fdma_wareq	),//FDMA写通道请求
	.I_fdma_wsize		(S_fdma_wsize	),//FDMA写通道一次FDMA的传输大小                                            
	.O_fdma_wbusy		(S_fdma_wbusy	),//FDMA处于BUSY状态，AXI总线正在写操作  
					
	.I_fdma_wdata		(S_fdma_wdata	),//FDMA写数据
	.O_fdma_wvalid		(S_fdma_wvalid	),//FDMA 写有效
	.I_fdma_wready		(1'b1			),//FDMA写准备好，用户可以写数据
	
	.I_fdma_raddr		(S_fdma_raddr	),// FDMA读通道地址
	.I_fdma_rareq		(S_fdma_rareq	),// FDMA读通道请求
	.I_fdma_rsize		(S_fdma_rsize	),// FDMA读通道一次FDMA的传输大小                                      
	.O_fdma_rbusy		(S_fdma_rbusy	),// FDMA处于BUSY状态，AXI总线正在读操作 
					
	.O_fdma_rdata		(S_fdma_rdata	),// FDMA读数据
	.O_fdma_rvalid		(S_fdma_rvalid	),// FDMA 读有效
	.I_fdma_rready		(1'b1			),// FDMA读准备好，用户可以读数据

//以下为AXI总线信号		
	.M_AXI_ACLK         (S_dfi_clk		),
	.M_AXI_ARESETN      (S_ddr_app_rstn),
// Master Interface Write Address Ports
	.M_AXI_AWID         (S_axi_awid		),
	.M_AXI_AWADDR       (S_axi_awaddr	),
	.M_AXI_AWLEN        (S_axi_awlen	),
	.M_AXI_AWSIZE       (S_axi_awsize	),
	.M_AXI_AWBURST      (S_axi_awburst	),
	.M_AXI_AWLOCK       (				),
	.M_AXI_AWCACHE      (S_axi_awcache	),
	.M_AXI_AWPROT       (S_axi_awprot	),
	.M_AXI_AWQOS        (				),
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
	.M_AXI_ARLOCK       (				),
	.M_AXI_ARCACHE      (S_axi_arcache	),
	.M_AXI_ARPROT       (				),
	.M_AXI_ARQOS        (				),
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

	.sys_rst_n  		(S_pll_lock		),
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
    .pll_locked        	(				),
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
`else  // PAXI
// Write Address Ports
    .paxi_awaddr       (				), 
    .paxi_awvalid      (				), 
    .paxi_awready      (				), 
// Write Data Ports    				
    .paxi_wdata        (				), 
    .paxi_wstrb        (				), 
    .paxi_wvalid       (				), 
    .paxi_wlast        (				), 
    .paxi_wready       (				), 
// Write Response Port 				
    .paxi_bresp        (				), 
    .paxi_bvalid       (				), 
    .paxi_bready       (				), 
// Read Address Ports  				
    .paxi_araddr       (				), 
    .paxi_arvalid      (				), 
    .paxi_arready      (				), 			 
// Read Data Ports     				
    .paxi_rdata        (				), 
    .paxi_rlast        (				), 
    .paxi_rvalid       (				), 
    .paxi_rready       (				), 
`endif
// PZQ Share
    .pzq_cal_done_i    (				),
    .pzq_cal_done_o    (				),
// DFX				
    .user_clk          (				), 
    .apb_clk           (				), 
    .mcu_busy          (				), 
    .user_update       (				), 
    .user_ram_addr     (				), 
    .user_ram_wr_en    (				), 
    .user_ram_rd_en    (				), 
    .user_ram_wr_data  (				), 
    .user_ram_rd_data  (				), 
				
    .uart_rxd          (				),
    .uart_txd          (				)
);


  reset_gen u_reset_gen (
      .I_clk     (S_clk),
      .I_pll_lock(S_pll_lock),
      .I_rst     (1'b0),

      .O_rst_n       (),
      .O_rst         (S_rst),
      .O_config_start(S_config_start)
  );

  video_source #(
        .HTOTAL ( 1344 ),
        .HSA    ( 24    ),
        .HBP    ( 136   ),
        .HFP    ( 160   ),
 
        .VTOTAL ( 635 ),
        .VSA    ( 2    ),
        .VBP    ( 21   ),
        .VFP    ( 12   )
  ) u_video_source (
      .I_clk(S_clk),
      .I_rst(S_rst),

      .I_config_done(S_config_done),

      .O_rgb24b_vsync(S_24b_vsync),
      .O_rgb24b_hsync(S_24b_hsync),
      .O_rgb24b_de   (S_24b_de),
      .O_rgb24b_data (S_24b_data)
  );


  rgb_24b_to_32b #(
      .H_ACTIVE(1024)
  ) u_rgb_24b_to_32b (
      .I_clk(S_clk),
      .I_rst(S_rst),

      .I_vsync(S_24b_vsync),
      .I_hsync(S_24b_hsync),
      .I_de   (S_24b_de),
      .I_data (S_ud_rtdata),

      .O_vsync(S_32b_vsync),
      .O_hsync(S_32b_hsync),
      .O_de   (S_32b_de),
      .O_data (S_32b_data)
  );


  dsi_video_mode_packet #(
      .H_ACTIVE(1024)
  ) u_dsi_video_mode_packet (
      .I_clk(S_clk),
      .I_rst(S_rst),

      .I_vsync(S_32b_vsync),
      .I_hsync(S_32b_hsync),
      .I_de   (S_32b_de),
      .I_data (S_32b_data),

      .O_hs_en  (S_hs_en),
      .O_hs_data(S_hs_data),
      .O_hs_last(S_hs_last)
  );


  display_config_wrapper u_display_config_wrapper (
      .I_clk(S_lp_clk),
      .I_rst(S_rst),

      .I_config_start(S_config_start),
      .O_config_done (S_config_done),

      .O_lp_tx_valid(S_lp_tx_valid),
      .O_lp_tx_last (S_lp_tx_last),
      .O_lp_tx_data (S_lp_tx_data),
      .I_lp_tx_ready(S_lp_tx_ready)
  );

  mipi_dphy_tx_wrapper #(
      .LANE_NUM(4),

      .HS_TX_FIFO_TYPE      ("DRAM"),  ///"DRAM","BRAM"
      .LP_TX_FIFO_TYPE      ("DRAM"),  ///"DRAM","BRAM"
      .LP_TX_MAX_DATA_LENGTH(8),       ///1-240

      .CLK_LANE_MODE("CONTINUE"),  ///"INTERRUPT","CONTINUE"

      .T_DATA_LPX       (10),
      .T_DATA_HS_PREPARE(10),
      .T_DATA_HS_ZERO   (20),
      .T_DATA_HS_TRAIL  (20),
      .T_CLK_LPX        (10),
      .T_CLK_PREPARE    (10),
      .T_CLK_ZERO       (10),
      .T_CLK_PRE        (10),
      .T_CLK_POST       (10),
      .T_CLK_TRAIL      (10)
  ) u_mipi_dphy_tx_wrapper (
      .I_hs_clk       (S_clk),
      .I_hs_clk_x2    (S_clk_x2),
      .I_hs_clk_x4    (S_clk_x4),
      .I_hs_clk_x4_90d(S_clk_x4_90d),

      .I_rst(S_rst),

      .I_hs_tx_valid(S_hs_en),
      .I_hs_tx_data (S_hs_data),
      .I_hs_tx_last (S_hs_last),
      .O_hs_tx_ready(),

      .I_lpdt_clk   (S_lp_clk),
      .I_lp_tx_valid(S_lp_tx_valid),
      .I_lp_tx_data (S_lp_tx_data),
      .I_lp_tx_last (S_lp_tx_last),
      .O_lp_tx_ready(S_lp_tx_ready),

      .O_clk_hs_p (O_clk_hs_p),
      .O_data_hs_p(O_data_hs_p),
      .O_clk_lp_p (O_clk_lp_p),
      .O_clk_lp_n (O_clk_lp_n),
      .O_data_lp_p(O_data_lp_p),
      .O_data_lp_n(O_data_lp_n)
  );

  assign O_clk_lp_dir  = 1'b1;
  assign O_dsi_pwm     = 1'b1;
  assign O_data_lp_dir = 4'b1111;



// Coherent observability through existing board UART TX U11, 115200 8N1.
// These monitor existing signals; they do not control or replace CSI/DSI.

always @(posedge I_sysclk_25m or negedge S_pll_lock)
 if(!S_pll_lock)telemetry_reset<=0;else telemetry_reset<={telemetry_reset[1:0],1'b1};
(* async_reg="true" *) reg [1:0] telemetry_ddr_done=0;
always @(posedge I_sysclk_25m)telemetry_ddr_done<={telemetry_ddr_done[0],S_ddr_init_cal_done};
wire [191:0] telemetry_video_stats;
wire [223:0] telemetry_video_snapshot,telemetry_csi_snapshot;
wire [31:0] telemetry_video_status,telemetry_csi_status,telemetry_video_clock,telemetry_csi_clock;
dsi_frame_stats u_frame_observe(.clk(S_clk),.rst(S_rst),.vsync(S_24b_vsync),.de(S_24b_de),
 .rgb(S_ud_rtdata),.config_done(S_config_done),.stats(telemetry_video_stats));
csi_stats_snapshot #(.PERIOD(1250000)) u_video_snapshot(
 .src_clk(S_clk),.dst_clk(I_sysclk_25m),.rst_n(S_pll_lock),.src_stats(telemetry_video_stats),
 .snapshot(telemetry_video_snapshot),.status(telemetry_video_status),.clock_delta(telemetry_video_clock));
csi_stats_snapshot #(.PERIOD(1250000)) u_csi_snapshot(
 .src_clk(S_hs_rx_clk),.dst_clk(I_sysclk_25m),.rst_n(S_pll_lock),.src_stats({S_csi_raw_packets,S_csi_crc_errors,S_csi_ecc_errors,S_csi_wc_errors,S_csi_fifo_overflows,S_csi_timeout_errors}),
 .snapshot(telemetry_csi_snapshot),.status(telemetry_csi_status),.clock_delta(telemetry_csi_clock));
wire [31:0] telemetry_flags={27'b0,(telemetry_csi_status[31:1]!=0),(telemetry_video_status[31:1]!=0),
 telemetry_ddr_done[1],telemetry_video_snapshot[160],S_pll_lock};
// Frame/handshake probes in the actual75MHz RAW/ISP write domain.
reg [31:0] flow_in_beats=0,flow_in_frames=0,flow_out_beats=0,flow_out_frames=0,flow_stalls=0;
always @(posedge S_clk_70m or negedge S_video_rstn)begin
 if(!S_video_rstn)begin flow_in_beats<=0;flow_in_frames<=0;flow_out_beats<=0;flow_out_frames<=0;flow_stalls<=0;end
 else begin
  if(S_axis_tvalid&&S_axis_tready)begin flow_in_beats<=flow_in_beats+1'b1;if(S_axis_tuser)flow_in_frames<=flow_in_frames+1'b1;end
  if(S_ud_wtvalid&&S_ud_wtready)begin flow_out_beats<=flow_out_beats+1'b1;if(S_ud_wtuser)flow_out_frames<=flow_out_frames+1'b1;end
  if(S_axis_tvalid&&!S_axis_tready)flow_stalls<=flow_stalls+1'b1;
 end
end
wire [31:0] flow_flags={24'b0,S_video_rstn,S_dbuf_write_diag,
 S_ud_wtready,S_ud_wtvalid,S_axis_tready,S_axis_tvalid};
wire [3167:0] telemetry_flow_snapshot;
wire [31:0] telemetry_flow_status,telemetry_flow_clock;
csi_stats_snapshot #(.PERIOD(1250000),.STATS_WIDTH(3136)) u_flow_snapshot(
 .src_clk(S_clk_70m),.dst_clk(I_sysclk_25m),.rst_n(S_pll_lock),
 .src_stats({hci02_eye_fifo_errors,hci02_eye_fifo_high_water,hci02_eye_fifo_occupancy,hci_config_snapshot[479:448],hci02_tag_underflows,hci02_tag_overflows,hci02_roi_stats,
 hci_config_snapshot[95:64],S_hci_errors,17'd0,S_hci_lut_valid,hci_applied_config,hci_applied_sequence,flow_in_beats,flow_in_frames,flow_out_beats,flow_out_frames,flow_stalls,flow_flags}),
 .snapshot(telemetry_flow_snapshot),.status(telemetry_flow_status),.clock_delta(telemetry_flow_clock));
hci03_status_uart u_uart_observe(.I_clk(I_sysclk_25m),.I_rstn(telemetry_reset[2]),
 .I_flags(telemetry_flags),.I_frames(telemetry_video_snapshot[159:128]),.I_pixels(telemetry_video_snapshot[127:96]),
 .I_red(telemetry_video_snapshot[95:64]),.I_green(telemetry_video_snapshot[63:32]),.I_blue(telemetry_video_snapshot[31:0]),
 .I_raw(telemetry_csi_snapshot[191:160]),.I_crc_errors(telemetry_csi_snapshot[159:128]),
 .I_ecc_errors(telemetry_csi_snapshot[127:96]),.I_wc_errors(telemetry_csi_snapshot[95:64]),
 .I_overflows(telemetry_csi_snapshot[63:32]),.I_timeouts(telemetry_csi_snapshot[31:0]),.I_flow(telemetry_flow_snapshot[191:0]),.I_flow_status(telemetry_flow_status),.I_extension(telemetry_flow_snapshot[319:192]),.I_roi_stats(telemetry_flow_snapshot[2943:320]),
 .I_tag_overflows(telemetry_flow_snapshot[2975:2944]),.I_tag_underflows(telemetry_flow_snapshot[3007:2976]),
 .I_roi_rejects(telemetry_flow_snapshot[3039:3008]),.I_eye_fifo_occupancy(telemetry_flow_snapshot[3071:3040]),
 .I_eye_fifo_high_water(telemetry_flow_snapshot[3103:3072]),.I_eye_fifo_errors(telemetry_flow_snapshot[3135:3104]),
 .I_link_source(rk_source_snapshot[1663:0]),.I_link_source_status(rk_source_status),.I_link_source_clock(rk_source_clock),
 .I_link_destination(rk_destination_snapshot[511:0]),.I_link_destination_status(rk_destination_status),.I_link_destination_clock(rk_destination_clock),.O_uart_tx(O_uart_tx));

endmodule

