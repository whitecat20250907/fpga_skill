`timescale 1ps/1ps

module sim_tb_top;

localparam DRAM_WIDTH         = 16;
localparam ADDR_WIDTH         = 15;
localparam DQS_WIDTH          = 4 ;
localparam DQ_WIDTH           = DQS_WIDTH * 8;
localparam DM_WIDTH           = DQS_WIDTH    ;

localparam MRS                           = 3'b000;
localparam REF                           = 3'b001;
localparam PRE                           = 3'b010;
localparam ACT                           = 3'b011;
localparam WR                            = 3'b100;
localparam RD                            = 3'b101;
localparam ZQC                           = 3'b110;
localparam NOP                           = 3'b111;


//-------- Ports Definition --------//
reg                     sys_clk_i;
reg                     sys_rst_n;

wire                    c0_sys_clk_p;
wire                    c0_sys_clk_n;

wire    [ADDR_WIDTH-1:0]          ddr_addr   ;
wire    [ 2:0]          ddr_ba     ;
wire    [ 0:0]          ddr_bg     ;
wire    [ 0:0]          ddr_cke    ;
wire    [ 0:0]          ddr_odt    ;
wire    [ 0:0]          ddr_cs_n   ;
wire                    ddr_ras_n  ;
wire                    ddr_cas_n  ;
wire                    ddr_we_n   ;
wire    [ 0:0]          ddr_ck_t   ;
wire    [ 0:0]          ddr_ck_c   ;
wire                    ddr_reset_n;
wire    [DQS_WIDTH     - 1 : 0]    ddr_dm     ;
wire    [DQS_WIDTH * 8 - 1 : 0]    ddr_dq     ;
wire    [DQS_WIDTH     - 1 : 0]    ddr_dqs_n  ;
wire    [DQS_WIDTH     - 1 : 0]    ddr_dqs_p  ; 

wire            c0_init_calib_complete;
wire            c0_data_compare_error;


//**************************************************************************//
// Reset Generation
//**************************************************************************//
initial begin
    sys_rst_n = 1'b0;
    #20000 
    #200;
    sys_rst_n = 1'b1;
    
end
//**************************************************************************//
// Clock Generation
//**************************************************************************//
always begin
    sys_clk_i = 1'b0;
    #(10000/2.0);
    sys_clk_i = 1'b1; 
    #(10000/2.0);
end

assign c0_sys_clk_p =  sys_clk_i;
assign c0_sys_clk_n = ~sys_clk_i;

//===========================================================================
//                         FPGA Memory Controller && PHY instantiation
//===========================================================================
glbl glbl ();
PH1_PHY_GSR PH1_PHY_GSR ();

example_top u_example_top (

    .I_ddr_clk          (c0_sys_clk_p),
    .I_rst_n            (sys_rst_n),
    //.ddr_act_n          (ddr_act_n),
    //.ddr_bg             (ddr_bg),
    .ddr_addr           (ddr_addr),
    .ddr_ba             (ddr_ba),
    .ddr_cke            (ddr_cke),
    .ddr_odt            (ddr_odt),
    .ddr_cs_n           (ddr_cs_n),
    .ddr_ras_n          (ddr_ras_n),
    .ddr_cas_n          (ddr_cas_n),
    .ddr_we_n           (ddr_we_n),
    .ddr_ck_p           (ddr_ck_t),
    .ddr_ck_n           (ddr_ck_c),
    .ddr_reset_n        (ddr_reset_n),
    .ddr_dm             (ddr_dm),
    .ddr_dq             (ddr_dq),
    .ddr_dqs_p          (ddr_dqs_p),
    .ddr_dqs_n          (ddr_dqs_n)
);

//===========================================================================
//                         Separate DDR CMD
//===========================================================================

wire [2:0] cmd_enc={ddr_ras_n,ddr_cas_n,ddr_we_n};

reg [31:0] cmdName;
always @(*) begin
    if (ddr_reset_n == 1'b0)
        cmdName = "DSEL";
    else
        casez (cmd_enc)
            MRS:     cmdName = "MRS";
            REF:     cmdName = "REF";
            PRE:     cmdName = "PRE";
            ACT:     cmdName = "ACT";
            WR:      cmdName = "WR";
            RD:      cmdName = "RD";
            ZQC:     cmdName = "ZQC";
            NOP:     cmdName = "NOP";
            default: cmdName = "***";
        endcase
end


//===========================================================================
//                         Memory Model instantiation
//===========================================================================

genvar i;
generate
    if (DRAM_WIDTH == 8) begin: mem_model_x8
        for (i = 0; i < DQ_WIDTH/DRAM_WIDTH; i=i+1) begin:memModel
          ddr3 ddr3_x8 (
           .rst_n   (ddr_reset_n),
           .ck      (ddr_ck_t), 
           .ck_n    (ddr_ck_c),
           .cke     (ddr_cke), 
           .cs_n    (ddr_cs_n), 
           .ras_n   (ddr_ras_n), 
           .cas_n   (ddr_cas_n), 
           .we_n    (ddr_we_n), 
           .dm_tdqs (ddr_dm[i]), 
           .ba      (ddr_ba), 
           .addr    (ddr_addr),      
           .dq      (ddr_dq[i*8+:8]), 
           .dqs     (ddr_dqs_p[i]),
           .dqs_n   (ddr_dqs_n[i]),
           .tdqs_n  (),
           .odt     (ddr_odt)
          );
         end  
    end else begin: mem_model_x16

        for (i = 0; i < (DQ_WIDTH/DRAM_WIDTH); i=i+1) begin:memModel
            ddr3 u_ddr3_x16 (
                .tdqs_n  (                                ),
                .addr    ( ddr_addr                       ),
                .ba      ( ddr_ba                         ),
                .cke     ( ddr_cke[0]                     ),
                .odt     ( ddr_odt[0]                     ),
                .cs_n    ( ddr_cs_n[0]                    ),
                .ras_n   ( ddr_ras_n                      ),
                .cas_n   ( ddr_cas_n                      ),
                .we_n    ( ddr_we_n                       ),
                .ck      ( ddr_ck_t                       ),
                .ck_n    ( ddr_ck_c                       ),
                .rst_n   ( ddr_reset_n                    ),
                .dm_tdqs ( ddr_dm   [( 2*(i+1)-1):( 2*i)] ),
                .dq      ( ddr_dq   [(16*(i+1)-1):(16*i)] ),
                .dqs     ( ddr_dqs_p[( 2*(i+1)-1):( 2*i)] ),
                .dqs_n   ( ddr_dqs_n[( 2*(i+1)-1):( 2*i)] )
            );
        end

    end
endgenerate




`ifdef FSDB
initial begin
    $fsdbDumpfile("sim_tb_top.fsdb");
 $fsdbDumpvars(0,sim_tb_top,"+all");
end
`endif

`ifdef VPD
initial begin
 $vcdpluson();
end
`endif



endmodule
