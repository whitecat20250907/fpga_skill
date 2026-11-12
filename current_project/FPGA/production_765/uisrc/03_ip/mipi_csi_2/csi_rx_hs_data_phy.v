`timescale 1 ps / 1 ps

///  DEVICE: "EF2","EF3","SF1","EG","PH1","PH1A","PH2"
module csi_rx_hs_data_phy #(
    parameter DEVICE = "PH2",
    parameter SEPARATE_PAD_PCLK = 0
)(
    input  wire               I_rxclk,
    input  wire               I_rxclk_div_x2,
    input  wire               I_pad_pclk,
    input  wire               I_rxclk_div_x4,
    input  wire               I_reset_n,
    input  wire               I_sampler_reset_n,
    input  wire               I_hs_data_p,
    input  wire [5:0]         I_delay_value,
    input  wire 	          I_delay_vaild,
    output wire [3:0]         O_rx_nibble, // registered PCLK n0, diagnostic only
    output wire [7:0]         O_rx_data,   
    output wire 		      O_delay_data_val 
	);

    wire        w_hs_data_dalay;
    wire        w_delay_data_val;

   assign     O_delay_data_val = w_delay_data_val;

// ==========================================================
// PH1A (HR bank): PH1_LOGIC_DYNAMIC_IDELAY + PH1_LOGIC_IDDRx2
// HR bank does not support HP_ISERDES or HP_IDELAY
// ==========================================================
generate if (DEVICE == "PH1A") begin : gen_ph1a

    // Diagnostic19: UG910 sec36 uses a persistent active-high enable.
    // Delay-code update pulse is not the primitive enable.
    // Default preserves old instances whose new I_pad_pclk is unconnected.
    // This is a constant elaboration choice, never a run-time clock mux.
    wire w_sampler_pclk = SEPARATE_PAD_PCLK ? I_pad_pclk : I_rxclk_div_x2;
    wire [3:0] w_rx_data_iddr;
    reg  [3:0] r_rx_data_iddr;
    reg  [3:0] r_rx_data_iddr_d1;
    reg  [7:0] r_rx_data_byte;

    PH1_LOGIC_DYNAMIC_IDELAY #(
      .WIDTH ( 5 )
    ) u_idelay (
      .i        ( I_hs_data_p           ),
      .indly_en ( 1'b1 ),
      .in_dly   ( I_delay_value[4:0]    ),
      .o        ( w_hs_data_dalay       )
    );

    PH1_LOGIC_IDDRx2 #(
      .ASYNCRST ( "ENABLE" )
    ) u_iddrx2 (
      .q3   ( w_rx_data_iddr[3] ),
      .q2   ( w_rx_data_iddr[2] ),
      .q1   ( w_rx_data_iddr[1] ),
      .q0   ( w_rx_data_iddr[0] ),
      .pclk ( w_sampler_pclk  ), // documented local LCLK /2 PAD clock
      .sclk ( I_rxclk_div_x4   ),
      .d    ( w_hs_data_dalay   ),
      .rst  ( ~I_sampler_reset_n )   // Shared SCLK reset; explicit PAD PCLK.
    );

    // Diagnostic12 uses UG910 sec.7 IDDRx2l: internal SCLK/2 PCLK.
    // Q is one SCLK cycle later; the real trace must establish byte phase.
    // Combine two 4-bit nibbles into 8-bit byte at byte clock
    // Both adjacent nibbles originate in the same fabric PCLK domain.
    // The raw local-PAD Q is captured only by n0, never by the byte register.
    always @(negedge I_rxclk_div_x2) begin
        r_rx_data_iddr <= w_rx_data_iddr;
        r_rx_data_iddr_d1 <= r_rx_data_iddr;
    end

    always @(posedge I_rxclk)
        r_rx_data_byte <= {r_rx_data_iddr, r_rx_data_iddr_d1};

    assign O_rx_nibble     = r_rx_data_iddr;
    assign O_rx_data       = r_rx_data_byte;
    assign w_delay_data_val = 1'b1;

end
// ==========================================================
// PH2 (default): PH2_LOGIC_HP_ISERDES with built-in delay
// ==========================================================
else begin : gen_ph2
    assign O_rx_nibble=4'b0; // New probe is only valid for PH1A.

    PH2_LOGIC_HP_ISERDES #(
      .MODE         ( "DDR18"    ),
      .DLY_MODE     ( "ENABLE"  )
    ) u_PH2_LOGIC_HP_ISERDES (
      .pclk         ( I_rxclk           ),
      .sclk         ( I_rxclk_div_x4    ),
      .rst_n        ( I_reset_n         ),
      .idata        ( I_hs_data_p       ),
      .odata_vld    ( w_delay_data_val  ),
      .odata        ( O_rx_data         ),
      .dl_en_n      ( ~I_delay_vaild    ),
      .dl_type      ( 2'b10             ),
      .dl_code      ( I_delay_value     )
    );

end endgenerate

endmodule
