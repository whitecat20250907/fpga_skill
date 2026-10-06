// Inert header-only stubs; NO ISP/data-path functionality is tested.
module image_correction #(parameter DATA_WIDTH=40, TDEST_WIDTH=10)(
    input I_clk, I_rst_n,
    input [14:0] I_v_start, I_v_end, I_h_end,
    input [DATA_WIDTH-1:0] I_raw_tdata,
    input [TDEST_WIDTH-1:0] I_raw_tdest,
    input I_raw_tlast, I_raw_tvalid, I_raw_tuser,
    output I_raw_tready,
    output reg [DATA_WIDTH-1:0] O_raw_tdata,
    output reg O_raw_tlast,
    output reg [TDEST_WIDTH-1:0] O_raw_tdest,
    output reg O_raw_tvalid, O_raw_tuser,
    input O_raw_tready
);
assign I_raw_tready=0;
assign O_raw_tdata=0;
assign O_raw_tlast=0;
assign O_raw_tdest=0;
assign O_raw_tvalid=0;
assign O_raw_tuser=0;
endmodule

module pack4_rgb24_to_128 (
 input wire clk,rst_n,enable,
 input wire [12:0] cfg_img_height,
 input wire [127:0] s_tdata,
 input wire s_tvalid,
 output wire s_tready,
 input wire s_tlast,s_tuser,
 output reg [127:0] m_tdata,
 output reg m_tvalid,
 input wire m_tready,
 output reg m_tlast,m_frame_last,sof,eof,
 output wire [31:0] frame_count_out
);
assign s_tready=0;
assign m_tdata=0;
assign m_tvalid=0;
assign m_tlast=0;
assign m_frame_last=0;
assign sof=0;
assign eof=0;
assign frame_count_out=0;
endmodule

module sync_fifo_130 #(
    parameter ADDR_WIDTH = 9   
)(
    input  wire          clk,
    input  wire          rst_n,

    
    input  wire [129:0]  wr_data,
    input  wire          wr_en,      
    output wire          full,

    
    output wire [129:0]  rd_data,    
    input  wire          rd_en,      
    output wire          empty
);
assign full=0;
assign rd_data=0;
assign empty=0;
endmodule

module ui_BLC #(
    parameter [9:0] Black_level_offset_r0=15,Black_level_offset_r1=15,
    parameter [9:0] Black_level_offset_r2=15,Black_level_offset_r3=15
)(
    input I_clk,I_rst_n,I_tlast,I_tuser,
    input [39:0] I_tdata,input I_tvalid,input [9:0] I_tdest,
    output I_tready,
    output reg O_tlast,O_tuser,output reg [39:0] O_tdata,
    output reg O_tvalid,output reg [9:0] O_tdest,input O_tready
);
assign I_tready=0;
assign O_tlast=0;
assign O_tuser=0;
assign O_tdata=0;
assign O_tvalid=0;
assign O_tdest=0;
endmodule

module ui_Brightness_adj #(
    parameter  BRIGHTNESS_ADD   = 20,
    parameter  BRIGHTNESS_MINUS = 0
)
(
    input                   I_clk    ,
    input                   I_rst_n  ,

    input                   I_tlast  ,
    input                   I_tuser  ,
    input  [95:0]           I_tdata  ,
    input                   I_tvalid , 
    output                  I_tready ,

    output                  O_tlast  ,
    output                  O_tuser  ,
    output [95:0]           O_tdata  ,
    output                  O_tvalid ,
    input                   O_tready
);
assign I_tready=0;
assign O_tlast=0;
assign O_tuser=0;
assign O_tdata=0;
assign O_tvalid=0;
endmodule

module ui_Contrast_adj #(parameter contrast_level=160)(
    input I_clk,I_rst_n,I_tlast,I_tuser,input [95:0] I_tdata,input I_tvalid,
    output I_tready,output O_tlast,O_tuser,output [95:0] O_tdata,
    output O_tvalid,input O_tready
);
assign I_tready=0;
assign O_tlast=0;
assign O_tuser=0;
assign O_tdata=0;
assign O_tvalid=0;
endmodule

module ui_Saturation_adj#(
parameter [8:0]  ADJUST_VAL = 128 
)  
(
    input                   I_clk    ,    
    input                   I_rst_n  ,    

    input                   I_tlast  ,  
    input                   I_tuser  ,  
    input [95:0]            I_tdata  ,  
    input                   I_tvalid ,  
    output                  I_tready ,  

    output                  O_tlast  ,  
    output                  O_tuser  ,  
    output [95:0]           O_tdata  ,  
    output                  O_tvalid ,  
    input                   O_tready    
);
assign I_tready=0;
assign O_tlast=0;
assign O_tuser=0;
assign O_tdata=0;
assign O_tvalid=0;
endmodule

module ui_awb #(
    parameter IMG_HEIGHT=1080, parameter IMG_WIDTH=1920
)(
    input I_clk, input I_rst_n,
    input [12:0] I_img_width, input [12:0] I_img_height,
    input I_tlast, input I_tuser, input [95:0] I_tdata,
    input I_tvalid, output I_tready,
    output O_tlast, output O_tuser, output [95:0] O_tdata,
    output O_tvalid, input O_tready
);
assign I_tready=0;
assign O_tlast=0;
assign O_tuser=0;
assign O_tdata=0;
assign O_tvalid=0;
endmodule

module ui_data128_96 (

    input  wire [127:0] I_tdata,
    output wire [ 95:0] O_tdata
);
assign O_tdata=0;
endmodule

module ui_data96_128 (

    input wire [95:0] I_tdata,

    output wire [127:0] O_tdata

);
assign O_tdata=0;
endmodule

module ui_gamma #(
    parameter [4:0] GAMMA_10x = 22 
)
(
    input                   I_clk  		, 
    input                   I_rst_n		, 

    input                   I_tlast     , 
    input                   I_tuser     , 
    input [95:0]            I_tdata     , 
    input                   I_tvalid    , 
    output                  I_tready    , 

    output                  O_tlast     , 
    output                  O_tuser     , 
    output [95:0]           O_tdata     , 
    output                  O_tvalid    , 
    input                   O_tready      
);
assign I_tready=0;
assign O_tlast=0;
assign O_tuser=0;
assign O_tdata=0;
assign O_tvalid=0;
endmodule

module ui_image_cut #(
    parameter [12:0] IMG_WIDTH=640,IMG_HEIGHT=480,
    parameter DATA_WIDTH=96,
    parameter SKIP_ROWS_top=2,SKIP_ROWS_bottom=2,SKIP_COLS_left=2,SKIP_COLS_right=2
)(
    input I_clk,I_rst_n,input [12:0] I_img_width,I_img_height,
    input I_tlast,I_tuser,input [DATA_WIDTH-1:0] I_tdata,input I_tvalid,
    output I_tready,output reg O_tlast,O_tuser,
    output reg [DATA_WIDTH-1:0] O_tdata,output reg O_tvalid,input O_tready
);
assign I_tready=0;
assign O_tlast=0;
assign O_tuser=0;
assign O_tdata=0;
assign O_tvalid=0;
endmodule

module ui_top_demosaic #(
    parameter data_complete_delay = 50  ,
    parameter BAYER_MODE          = "BGGR"
)
(
    input           I_clk   		,  
    input           I_rst_n 		,  

    input   [1:0]   I_bayer_mode, 
    input   [12:0]  I_img_width  ,  
    input   [12:0]  I_img_height ,  

    input [39:0]    I_axi4s_tdata 	,  
    input [9:0]     I_axi4s_tdest 	,
    input           I_axi4s_tlast 	,  
    input           I_axi4s_tvalid	,  
    input           I_axi4s_tuser 	,  
    output          I_axi4s_tready	,  

    output          O_tlast  		,  
    output          O_tuser  		,  
    output [127:0]  O_tdata  		,  
    output          O_tvalid 		,  
    input           O_tready 		   
);
assign I_axi4s_tready=0;
assign O_tlast=0;
assign O_tuser=0;
assign O_tdata=0;
assign O_tvalid=0;
endmodule
