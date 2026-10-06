// Physical route trial only. All seven ports have real board ADC locations.
// This checksum pin is not a UART protocol; NEVER bitgen/download this wrapper.
module td_local09_top(
    input sys_clk,input mipi_clk_hs_rx_p,input [3:0] mipi_data_hs_p,
    output uart_tx);
    reg [5:0] por_count=0;
    always @(posedge sys_clk)if(!(&por_count))por_count<=por_count+1'b1;
    wire reset_n=&por_count;
    wire byte_clk,byte_reset_n,sampler_reset_n,cal_done;
    wire [31:0] raw,aligned;
    wire [3:0] valid;
    wire [7:0] delay_dbg;
    wire [5:0] best_len;
    reg [31:0] checksum=0,raw_checksum=0;
    reg [15:0] accepted=0;
    reg [4:0] packet_byte=0;
    reg wait_sync=1,packet_done=0;
    // Sinks retain every lane of the actual raw/byte-align datapath. The
    // feedback makes these real register paths, not combinational output-only.
    always @(posedge byte_clk or negedge byte_reset_n)
        if(!byte_reset_n)begin checksum<=0;raw_checksum<=0;accepted<=0;packet_byte<=0;wait_sync<=1;packet_done<=0;end
        else begin
            raw_checksum<={raw_checksum[30:0],raw_checksum[31]}^raw;
            packet_done<=0;
            if((&valid) && !packet_done)begin
                checksum<={checksum[28:0],checksum[31:29]}^aligned;accepted<=accepted+1'b1;
                wait_sync<=0;
                if(packet_byte==24)begin packet_byte<=0;packet_done<=1;wait_sync<=1;end
                else packet_byte<=packet_byte+1'b1;
            end
        end
    assign uart_tx=^checksum ^ ^raw_checksum ^ ^accepted ^ cal_done ^
                   ^delay_dbg ^ ^best_len ^ sampler_reset_n;
    csi_rx_phy #(.MIPI_LAN(4),.DEVICE("PH1A")) phy(
        .I_debug_button(1'b1),.I_override_enable(1'b1),.I_override_tap(6'd0),
        .I_ref_clock(sys_clk),.I_clk_hs_rx_p(mipi_clk_hs_rx_p),.I_reset_n(reset_n),
        .I_hs_data_p(mipi_data_hs_p),.I_enable(1'b1),.I_wait_for_sync(wait_sync),.I_packet_done(packet_done),
        .O_hs_div_clk(byte_clk),.O_reset_out(byte_reset_n),.O_rx_byte_data_align_vaild(valid),
        .O_rx_byte_data_align(aligned),.O_delay_value(),.O_auto_delay_done(cal_done),
        .O_dbg_delay(delay_dbg),.O_dbg_best_len(best_len),.O_dbg_raw_bytes(raw),
        .O_sampler_reset_n(sampler_reset_n));
endmodule
