`timescale 1ns/1ps
module tb_camera_meta_overlay;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n = 0;
    reg s_valid = 0, s_sof = 0, s_last = 0;
    reg [63:0] s_data = 0;
    reg [3:0] lane_error = 0;
    reg bridge_overflow = 0;
    reg processing_error = 0;
    wire m_valid, m_sof, m_last;
    wire [63:0] m_data;
    reg [63:0] seen [0:7];
    integer f, row, col;
    camera_meta_overlay dut (
        .clk(clk), .rst_n(rst_n), .s_valid(s_valid), .s_data(s_data),
        .s_sof(s_sof), .s_last(s_last),
        .lane_error(lane_error), .bridge_overflow(bridge_overflow),
        .processing_error(processing_error),
        .m_valid(m_valid), .m_data(m_data),
        .m_sof(m_sof), .m_last(m_last)
    );

    task send_word;
        input integer frame_no, y, x;
        begin
            @(negedge clk);
            s_valid = 1;
            s_sof = (y == 0 && x == 0);
            s_last = (x == 9);
            s_data = {32'h55550000 + frame_no, y[15:0], x[15:0]};
            #1;
            if (!m_valid || m_sof !== s_sof || m_last !== s_last)
                $fatal(1, "handshake sideband mismatch");
            if (frame_no == 3 && y == 0 && x < 8)
                seen[x] = m_data;
            if (x == 9 && m_data !== s_data)
                $fatal(1, "payload beyond header was modified");
            @(posedge clk);
        end
    endtask

    initial begin
        repeat (4) @(posedge clk);
        @(negedge clk); rst_n = 1;
        for (f = 1; f <= 3; f = f + 1) begin
            if (f == 3) begin
                lane_error = 4'b0101;
                bridge_overflow = 1;
                processing_error = 1;
            end
            for (row = 0; row < 2; row = row + 1)
                for (col = 0; col < 10; col = col + 1)
                    send_word(f, row, col);
            @(negedge clk); s_valid = 0; s_sof = 0; s_last = 0;
            repeat (3) @(posedge clk);
        end
        if (seen[0] !== {32'd1, 32'h41475046})
            $fatal(1, "magic/version mismatch: %h", seen[0]);
        if (seen[1][31:0] !== 32'd3 || seen[1][35:32] !== 4'b0101 ||
            seen[1][41] !== 1'b1 || seen[1][42] !== 1'b1)
            $fatal(1, "frame id or error flags mismatch: %h", seen[1]);
        if (seen[3] == 0 || seen[4] == 0)
            $fatal(1, "missing FPGA cycle deltas");
        if (seen[5] !== {32'd20, 32'd2})
            $fatal(1, "previous frame geometry mismatch: %h", seen[5]);
        if (seen[6] !== {32'd64, 32'd111375000})
            $fatal(1, "header frequency/size mismatch: %h", seen[6]);
        if (seen[7] !== 64'd0)
            $fatal(1, "reserved mismatch");
        $display("PASS camera_meta_overlay: frame, ticks, rows, words, flags");
        $finish;
    end
endmodule
