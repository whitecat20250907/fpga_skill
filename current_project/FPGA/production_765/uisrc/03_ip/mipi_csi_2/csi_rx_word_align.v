// Lane deskew follows explicit SOT positions. Continuous valid history alone
// cannot distinguish a real SOT from an earlier false lock followed by zeros.
module csi_rx_word_align #(
    parameter MIPI_LAN = 2
)(
    input wire I_word_clock, I_reset_n, I_enable,
    input wire I_packet_done, I_wait_for_sync,
    output wire O_packet_done_out,
    input wire [8*MIPI_LAN-1:0] I_word_in,
    input wire [MIPI_LAN-1:0] I_valid_in, I_sot_in,
    output reg [8*MIPI_LAN-1:0] O_word_out,
    output reg O_valid_out,
    output wire O_sync_locked
);
reg [8*MIPI_LAN-1:0] r_word_dly [0:5];
reg [MIPI_LAN-1:0] r_sot_dly [0:5];
reg [MIPI_LAN-1:0] r_valid_dly_0;
reg [2:0] r_taps [0:MIPI_LAN-1];
reg [2:0] r_next_taps [0:MIPI_LAN-1];
reg [MIPI_LAN-1:0] marker_found;
reg [8*MIPI_LAN-1:0] aligned_word;
reg r_valid;
integer seq_lane,seq_age,comb_lane,comb_age;
assign O_packet_done_out = I_packet_done;
assign O_sync_locked = r_valid;

always @(*) begin
    marker_found = 0;
    aligned_word = 0;
    for (comb_lane=0;comb_lane<MIPI_LAN;comb_lane=comb_lane+1) begin
        r_next_taps[comb_lane] = 0;
        // Lowest history age is the most recent SOT for this lane.
        for (comb_age=0;comb_age<6;comb_age=comb_age+1) begin
            if (!marker_found[comb_lane] && r_sot_dly[comb_age][comb_lane]) begin
                marker_found[comb_lane] = 1;
                r_next_taps[comb_lane] = comb_age;
            end
        end
        case(r_taps[comb_lane])
            3'd5:aligned_word[comb_lane*8+:8]=r_word_dly[5][comb_lane*8+:8];
            3'd4:aligned_word[comb_lane*8+:8]=r_word_dly[4][comb_lane*8+:8];
            3'd3:aligned_word[comb_lane*8+:8]=r_word_dly[3][comb_lane*8+:8];
            3'd2:aligned_word[comb_lane*8+:8]=r_word_dly[2][comb_lane*8+:8];
            3'd1:aligned_word[comb_lane*8+:8]=r_word_dly[1][comb_lane*8+:8];
            default:aligned_word[comb_lane*8+:8]=r_word_dly[0][comb_lane*8+:8];
        endcase
    end
end

always @(posedge I_word_clock) begin
    if (!I_reset_n || !I_enable) begin
        r_valid<=0;O_valid_out<=0;O_word_out<=0;r_valid_dly_0<=0;
        for(seq_age=0;seq_age<6;seq_age=seq_age+1) begin
            r_word_dly[seq_age]<=0;r_sot_dly[seq_age]<=0;
        end
        for(seq_lane=0;seq_lane<MIPI_LAN;seq_lane=seq_lane+1) r_taps[seq_lane]<=0;
    end else begin
        r_word_dly[0]<=I_word_in;
        r_valid_dly_0<=I_valid_in;
        r_sot_dly[0]<=I_sot_in & I_valid_in;
        for(seq_age=1;seq_age<6;seq_age=seq_age+1) begin
            r_word_dly[seq_age]<=r_word_dly[seq_age-1];
            r_sot_dly[seq_age]<=r_sot_dly[seq_age-1];
        end
        O_valid_out<=r_valid;
        O_word_out<=aligned_word;
        if(I_packet_done) begin
            r_valid<=0;O_valid_out<=0;
            for(seq_age=0;seq_age<6;seq_age=seq_age+1) r_sot_dly[seq_age]<=0;
        end else if(!r_valid && I_wait_for_sync && (&marker_found) && (&r_valid_dly_0)) begin
            r_valid<=1;
            for(seq_lane=0;seq_lane<MIPI_LAN;seq_lane=seq_lane+1) r_taps[seq_lane]<=r_next_taps[seq_lane];
        end
    end
end
endmodule
