`timescale 1ns/1ps
module tb_csi_calibration;
    reg clk=0, refclk=0;
    always #4.5 clk=~clk;             // ~111 MHz byte clock for control test
    always #3.333 refclk=~refclk;     // ~150 MHz presence reference
    reg rst32=0,rst64=0,phy_rst=0;
    reg [31:0] pass32=0;
    reg [63:0] pass64=0;
    wire [3:0] aligned32=pass32[eye32.scan_tap] ? 4'hf : 0;
    wire [3:0] aligned64=pass64[eye64.scan_tap] ? 4'hf : 0;
    wire [5:0] tap32,tap64,len32,len64;
    wire done32,done64,load32,load64;
    auto_delay_ctl #(.TAP_COUNT(32),.TEST_CYCLES(128),.SETTLE_CYCLES(4),.WAIT_CYCLES(128)) eye32(
        .I_byte_clk(clk),.I_reset_n(rst32),.I_byte_align_done(aligned32),
        .O_delay_value(tap32),.O_delay_vaild(load32),.O_auto_delay_done(done32),.O_dbg_best_len(len32));
    auto_delay_ctl #(.TAP_COUNT(64),.TEST_CYCLES(128),.SETTLE_CYCLES(4),.WAIT_CYCLES(128)) eye64(
        .I_byte_clk(clk),.I_reset_n(rst64),.I_byte_align_done(aligned64),
        .O_delay_value(tap64),.O_delay_vaild(load64),.O_auto_delay_done(done64),.O_dbg_best_len(len64));
    reg button=1;
    wire phy_done,phy_reset;
    wire [7:0] phy_delay;
    wire [5:0] phy_len;
    csi_rx_phy #(.MIPI_LAN(4),.DEVICE("PH1A")) phy(
        .I_debug_button(button),.I_ref_clock(refclk),.I_clk_hs_rx_p(clk),
        .I_reset_n(phy_rst),.I_hs_data_p(4'b0),.I_enable(1'b1),
        .I_wait_for_sync(1'b1),.I_packet_done(1'b0),
        .O_hs_div_clk(),.O_reset_out(phy_reset),.O_rx_byte_data_align_vaild(),
        .O_rx_byte_data_align(),.O_delay_value(),.O_auto_delay_done(phy_done),
        .O_dbg_delay(phy_delay),.O_dbg_best_len(phy_len));
    defparam phy.u_auto_delay_ctl.TEST_CYCLES=128;
    defparam phy.u_auto_delay_ctl.SETTLE_CYCLES=4;
    defparam phy.u_auto_delay_ctl.WAIT_CYCLES=128;
    defparam phy.u_csi_rx_clock_det.LOSS_CYCLES=300;
    task automatic case32(input [31:0] pass,input integer expected_tap,input integer expected_len);
        begin
            @(negedge clk); rst32=0; pass32=pass;
            repeat(3) @(negedge clk); rst32=1;
            wait(done32); @(negedge clk);
            if(tap32!=expected_tap || len32!=expected_len || eye32.best_len!=expected_len)
                $fatal(1,"Eye32 mismatch mask=%h tap=%0d/%0d len=%0d/%0d",pass,tap32,expected_tap,len32,expected_len);
            $display("PASS 32physicaltap mask=%h best_len=%0d selected=%0d",pass,len32,tap32);
        end
    endtask
    task automatic release_button;
        begin
            @(negedge clk); button=0;
            repeat(5) @(negedge clk); button=1;
            repeat(5) @(negedge clk);
        end
    endtask
    integer i,expected_manual;
    initial begin
        case32(32'hffffffff,16,32);
        case32(32'h00ffff00,16,16);
        case32(32'hf000000f,2,4); // two edge windows; equal ties choose first
        case32(32'h80000000,31,1);
        case32(32'h00000001,0,1);
        case32(32'h00000000,16,0); // visible fallback; done is not eye-good
        @(negedge clk); pass64=64'hffffffffffffffff; rst64=1;
        wait(done64); @(negedge clk);
        if(eye64.best_len!=64 || tap64!=32 || len64!=63)
            $fatal(1,"64-tap eye wrapped: best_len=%0d tap=%0d debug=%0d",eye64.best_len,tap64,len64);
        $display("PASS 64tap full eye internally64/debugsaturated63 selected32");
        // The real PHY's controller/reset/manual logic is instantiated. Only
        // electrical clock/IO blocks below are behavioral. This is not an eye
        // quality test and makes no claim about IDDR bit sampling or pad delay.
        force phy.w_rx_byte_data_align_vaild=4'hf;
        @(negedge clk); phy_rst=1;
        wait(phy_done); repeat(3) @(negedge clk);
        if(phy_delay[5:0]!=16 || phy_len!=32 || phy.u_auto_delay_ctl.TAP_COUNT!=32)
            $fatal(1,"PHY did not use 32 physical taps");
        release_button;
        if(!phy_delay[6] || phy_delay[5:0]!=16 || !phy_done)
            $fatal(1,"Manual mode failed to adopt auto-selected tap");
        expected_manual=16;
        for(i=0;i<40;i=i+1) begin
            release_button;
            expected_manual=(expected_manual+1)%32;
            if(phy_delay[5:0]!=expected_manual || phy_delay[5:0]>=32)
                $fatal(1,"Manual delay physical wrap failed got=%0d exp=%0d",phy_delay[5:0],expected_manual);
        end
        $display("PASS real PHY manual controller: copies center16, wraps31to0, 40 physical steps");
        @(negedge clk); phy_rst=0;
        #0.1;
        if(phy_reset || phy_done) $fatal(1,"PHY async reset did not clear done/reset");
        $display("PASS calibration boundaries and manual/reset controller");
        $finish;
    end
    initial begin #2000000; $fatal(1,"Calibration simulation timeout"); end
endmodule

// Behavioral IO shells for CONTROL-LOGIC validation only. PHY bit sampling,
// phase relations and device tap delays require actual library/hardware tests.
module rx_clk_gen #(parameter DEVICE="PH1A")(
    input I_mipi_clk_p,I_rst,output O_clk,O_clk_x2,O_clk_x4);
    assign O_clk=I_mipi_clk_p;
    assign O_clk_x2=I_mipi_clk_p;
    assign O_clk_x4=I_mipi_clk_p;
endmodule
module csi_rx_hs_data_phy #(parameter DEVICE="PH1A")(
    input I_rxclk,I_rxclk_div_x2,I_rxclk_div_x4,I_reset_n,I_hs_data_p,
    input [5:0] I_delay_value,input I_delay_vaild,
    output [7:0] O_rx_data,output O_delay_data_val);
    assign O_rx_data=0;
    assign O_delay_data_val=1;
endmodule
