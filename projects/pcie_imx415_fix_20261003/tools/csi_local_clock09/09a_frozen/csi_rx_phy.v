`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 2025/07/18 16:34:28
// Design Name: 
// Module Name: mipi_csi_rx_phy
// Project Name: 
// Target Devices: 
// Tool Versions: 
// Description: 
// 
// Dependencies: 
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
//////////////////////////////////////////////////////////////////////////////////


module csi_rx_phy#(
    parameter MIPI_LAN  = 4 ,
    parameter DEVICE    = "EG"
)(

input wire I_debug_button,
    // These controls arrive as one coherent, byte-domain mailbox snapshot.
    input wire I_override_enable,
    input wire [5:0] I_override_tap,

    input wire                      I_ref_clock     ,   
    input wire                      I_clk_hs_rx_p   , 
    input wire                      I_reset_n       ,    
    input wire [MIPI_LAN-1:0]       I_hs_data_p     ,
    input wire                      I_enable        ,
    input  wire                     I_wait_for_sync ,
    input  wire                     I_packet_done   ,
    output wire                     O_hs_div_clk    ,
    output wire                     O_reset_out     ,      
    output wire [MIPI_LAN-1:0]      O_rx_byte_data_align_vaild,
    output wire [8*MIPI_LAN-1:0]    O_rx_byte_data_align, 
    output wire                     O_delay_value        ,
    output wire                     O_auto_delay_done,
    output wire [7:0]               O_dbg_delay,
    output wire [5:0]               O_dbg_best_len,
    output wire [8*MIPI_LAN-1:0]    O_dbg_raw_bytes,
    output wire                     O_sampler_reset_n
    );

wire                    w_hs_clk   ;
wire                    w_hs_clk_x2;
wire                    w_pad_clk_x2;
wire                    w_hs_clk_x4;
wire                    w_reset_out  ;
wire                    w_clock_present_n;
localparam DELAY_TAP_COUNT=(DEVICE=="PH1A") ? 32 : 64;
// Reference-domain clock-presence deassertion is synchronized to byte clock.
// Assertion is asynchronous, so clock loss/reset cannot wait for HS edges.
(* async_reg="true" *) reg [1:0] hs_reset_sync;
always @(posedge w_hs_clk or negedge w_clock_present_n)
    if(!w_clock_present_n) hs_reset_sync<=0;
    else hs_reset_sync<={hs_reset_sync[0],1'b1};
assign w_reset_out=hs_reset_sync[1];

// One release chain for every PH1 PAD sampler. Per-lane release chains can
// release on different HS edges and destroy the common deserializer phase.
(* async_reg="true" *) reg [2:0] sampler_reset_sync;
wire w_sampler_reset_n = sampler_reset_sync[2];
always @(posedge w_hs_clk_x4 or negedge w_clock_present_n)
    if(!w_clock_present_n) sampler_reset_sync<=3'b000;
    else sampler_reset_sync<={sampler_reset_sync[1:0],1'b1};
assign O_sampler_reset_n = w_sampler_reset_n;


wire [8*MIPI_LAN-1:0]   w_rx_byte_data;                   //synthesis keep
wire [MIPI_LAN-1:0]     w_rx_byte_data_align_vaild;       //synthesis keep
wire [8*MIPI_LAN-1:0]   w_rx_byte_data_align;             //synthesis keep
wire [5:0]              w_auto_delay_value;
wire 	                w_auto_delay_vaild;
wire                    w_auto_delay_done;
wire [5:0]              w_auto_delay_best_len;
wire [5:0]              w_lane_delay_value;
wire                    w_lane_delay_vaild;
wire 	                w_delay_data_val[MIPI_LAN-1:0];


reg  [1:0] r_debug_button_sync;
reg        r_manual_mode;
reg  [5:0] r_manual_delay;
reg        r_manual_delay_load;
reg        r_override_enable;
reg  [5:0] r_override_tap;
// Unconnected X/Z enable retains legacy automatic operation in simulation.
wire w_override_enable = (I_override_enable === 1'b1);
wire [5:0] w_override_tap = (DEVICE=="PH1A") ? {1'b0,I_override_tap[4:0]} : I_override_tap;
wire w_restore_auto = r_override_enable && !w_override_enable;
wire w_override_load = w_override_enable &&
                       (!r_override_enable || w_override_tap!=r_override_tap);
wire w_effective_manual = w_override_enable || (r_manual_mode && !w_restore_auto);
always @(posedge w_hs_clk or negedge w_reset_out)
    if(!w_reset_out) begin r_override_enable<=0;r_override_tap<=0;end
    else begin r_override_enable<=w_override_enable;r_override_tap<=w_override_tap;end

assign O_dbg_raw_bytes = w_rx_byte_data;
assign O_hs_div_clk                 = w_hs_clk              ;
assign O_reset_out                  = w_reset_out               ;    
assign O_rx_byte_data_align_vaild   = w_rx_byte_data_align_vaild;
assign O_rx_byte_data_align         = w_rx_byte_data_align      ;
assign O_delay_value                = w_lane_delay_value[0]     ;
assign O_auto_delay_done            = w_effective_manual ? 1'b1 : w_auto_delay_done;
assign O_dbg_best_len               = w_auto_delay_best_len;
assign O_dbg_delay                  = {w_lane_delay_vaild, w_effective_manual, w_lane_delay_value};


// debug
// µÍµçÆ½°´ÏÂ¡¢ÊÍ·ÅÑØ(+1 tap)£º
//   1. Î´½øÈëÊÖ¶¯Ä£Ê½Ç°£¬Ê×´ÎÊÍ·ÅÑØËø´æ auto-delay µ±Ç°Öµ
//   2. ½øÈëÊÖ¶¯Ä£Ê½ºó£¬Ã¿´ÎÊÍ·ÅÑØ delay tap + 1
wire w_debug_release = (r_debug_button_sync == 2'b01);

always @(posedge w_hs_clk or negedge w_reset_out) begin
    if (!w_reset_out) begin
        r_debug_button_sync <= 2'b11;
        r_manual_mode       <= 1'b0;
        r_manual_delay      <= 6'd0;
        r_manual_delay_load <= 1'b0;
    end else begin
        r_debug_button_sync <= {r_debug_button_sync[0], I_debug_button};
        r_manual_delay_load <= 1'b0;

        if(w_restore_auto) r_manual_mode<=1'b0;
        else if (w_debug_release && !w_override_enable) begin
            r_manual_mode       <= 1'b1;
            r_manual_delay_load <= 1'b1;

            if (!r_manual_mode)
                r_manual_delay <= w_auto_delay_value;
            else
                r_manual_delay <= (r_manual_delay==DELAY_TAP_COUNT-1)
                    ? 6'd0 : r_manual_delay+1'b1;
        end
    end
end

assign w_lane_delay_value = w_override_enable ? w_override_tap :
                            w_restore_auto ? w_auto_delay_value :
                            r_manual_mode ? r_manual_delay : w_auto_delay_value;
assign w_lane_delay_vaild = w_override_enable ? w_override_load :
                            w_restore_auto ? 1'b1 :
                            r_manual_mode ? r_manual_delay_load : w_auto_delay_vaild;


rx_clk_gen #(
    .DEVICE (DEVICE)
)u_rx_clk_gen(
    .I_mipi_clk_p (I_clk_hs_rx_p ),
    .I_rst        (~I_reset_n    ),
    .O_clk        (w_hs_clk      ),//ï¿½ï¿½ï¿½ï¿½8Î»ï¿½ï¿½ï¿½ï¿½Ê±ï¿½ï¿½
    .O_pad_clk_x2 (w_pad_clk_x2  ),
    .O_clk_x2     (w_hs_clk_x2   ),//ï¿½ï¿½ï¿½ï¿½4Î»ï¿½ï¿½ï¿½ï¿½Ê±ï¿½ï¿½
    .O_clk_x4     (w_hs_clk_x4   ) //4ï¿½ï¿½Ê±ï¿½Ó£ï¿½ï¿½ï¿½ï¿½ï¿½ï¿½ï¿½ï¿½ï¿½Ê±ï¿½ï¿½

);

csi_rx_clock_det u_csi_rx_clock_det(
    .I_ref_clock (I_ref_clock ),
    .I_ext_clock (w_hs_clk),
    .I_enable    (I_enable    ),
    .I_reset_in  (I_reset_n  ),
    .O_reset_out (w_clock_present_n )
);

auto_delay_ctl #(
  .MIPI_LAN(MIPI_LAN),
  .TAP_COUNT(DELAY_TAP_COUNT),
  .LAN_DATA_CUNT(10'h3ff)  
)u_auto_delay_ctl(
    .I_byte_clk        (w_hs_clk),
    .I_reset_n         (w_reset_out),
    .I_byte_align_done (w_rx_byte_data_align_vaild),
        .O_delay_value     (w_auto_delay_value),
        .O_delay_vaild     (w_auto_delay_vaild),
        .O_auto_delay_done (w_auto_delay_done),
        .O_dbg_best_len    (w_auto_delay_best_len)
);

generate 
genvar i;
for (i=0; i<MIPI_LAN; i=i+1) begin : gen_channel_wrapper	
csi_rx_hs_data_phy #(
    .SEPARATE_PAD_PCLK(DEVICE=="PH1A"),
    .DEVICE (DEVICE)
) u_csi_rx_hs_data_phy(
    .I_rxclk        (w_hs_clk      ),
    .I_rxclk_div_x2 (w_hs_clk_x2   ),
    .I_pad_pclk     (w_pad_clk_x2  ),
    .I_rxclk_div_x4 (w_hs_clk_x4   ),
    .I_reset_n      (w_reset_out   ),
    .I_sampler_reset_n(w_sampler_reset_n),
    .I_hs_data_p    (I_hs_data_p[i]),
    .I_delay_value  (w_lane_delay_value),
    .I_delay_vaild  (w_lane_delay_vaild),
    .O_rx_data      (w_rx_byte_data[(8 * i) + 7:8 * i]),
    .O_delay_data_val(w_delay_data_val[i])
);

csi_rx_byte_align u_csi_rx_byte_align(
    .I_clock           (w_hs_clk    ),
    .I_reset_n         (w_reset_out     ),
    .I_enable          (I_enable        ),
    .I_lan_data_in     (w_rx_byte_data[(8 * i) + 7:8 * i]),
    .I_wait_for_sync   (I_wait_for_sync ),
    .I_packet_done     (I_packet_done   ),
    .O_data_out_vaild  (w_rx_byte_data_align_vaild[i]),
    .O_data_out        (w_rx_byte_data_align[(8 * i) + 7:8 * i])
);

end
endgenerate	

//cwc cwc(
//.probe0(I_hs_data_p				),
//.probe1(O_auto_delay_done		),
//.probe2(w_delay_data_val[0]		),
//.probe3(w_delay_data_val[1]		),
//.probe4(w_delay_data_val[2]		),
//.probe5(w_delay_data_val[3]		),
//.probe6(w_rx_byte_data[7:0]		),
//.probe7(w_rx_byte_data[15:8]	),
//.probe8(w_rx_byte_data[23:16]	),
//.probe9(w_rx_byte_data[31:24]	),
//.probe10(r_debug_delay	),
//.clk(w_hs_clk)
//);

endmodule
