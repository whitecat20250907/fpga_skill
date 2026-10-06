// Synthesis-only PAD/reset mapping trial; never download this wrapper.
module td_reset8_top(
    input sys_clk,reset_n,enable,wait_sync,packet_done,
    input override_enable,input [5:0] override_tap,
    input mipi_clk_hs_rx_p,input [3:0] mipi_data_hs_p,
    output byte_clk,byte_reset_n,sampler_reset_n,cal_done,
    output [31:0] raw,aligned,output [3:0] valid,
    output [7:0] delay_dbg,output [5:0] best_len);
    csi_rx_phy #(.MIPI_LAN(4),.DEVICE("PH1A")) phy(
        .I_debug_button(1'b1),.I_override_enable(override_enable),.I_override_tap(override_tap),
        .I_ref_clock(sys_clk),.I_clk_hs_rx_p(mipi_clk_hs_rx_p),.I_reset_n(reset_n),
        .I_hs_data_p(mipi_data_hs_p),.I_enable(enable),.I_wait_for_sync(wait_sync),.I_packet_done(packet_done),
        .O_hs_div_clk(byte_clk),.O_reset_out(byte_reset_n),.O_rx_byte_data_align_vaild(valid),
        .O_rx_byte_data_align(aligned),.O_delay_value(),.O_auto_delay_done(cal_done),
        .O_dbg_delay(delay_dbg),.O_dbg_best_len(best_len),.O_dbg_raw_bytes(raw),
        .O_sampler_reset_n(sampler_reset_n));
endmodule
