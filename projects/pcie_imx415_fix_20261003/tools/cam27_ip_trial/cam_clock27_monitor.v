// Optional diagnostic candidate; not integrated in the frozen design.
// Counts internal clk_test edges against clk_ref. This cannot prove the
// MCLK pin, daughter-card routing, or the clock actually reaching the sensor.
// Assert resets asynchronously; deassert each reset in its own clock domain.
module cam_clock27_monitor #(
    parameter integer REF_HZ = 25000000,
    parameter integer EXPECTED_HZ = 27000000,
    parameter integer WINDOW_US = 10000,
    parameter integer TOLERANCE_PPM = 2000
) (
    input  wire clk_ref,
    input  wire ref_reset_n,
    input  wire clk_test,
    input  wire test_reset_n,
    input  wire pll_lock,
    output reg  [31:0] measured_edges,
    output reg  [31:0] window_index,
    output reg  measurement_valid,
    output reg  frequency_ok,
    output wire lock_in_ref
);
    localparam [63:0] WINDOW_CYCLES64 = 64'd1 * REF_HZ * WINDOW_US / 1000000;
    localparam [31:0] WINDOW_CYCLES = WINDOW_CYCLES64[31:0];
    localparam [63:0] EXPECTED_EDGES64 = 64'd1 * EXPECTED_HZ * WINDOW_CYCLES / REF_HZ;
    localparam [31:0] EXPECTED_EDGES = EXPECTED_EDGES64[31:0];
    localparam [63:0] TOLERANCE64 = EXPECTED_EDGES64 * TOLERANCE_PPM / 1000000 + 4;
    localparam [31:0] LOW_EDGES = EXPECTED_EDGES - TOLERANCE64[31:0];
    localparam [31:0] HIGH_EDGES = EXPECTED_EDGES + TOLERANCE64[31:0];

    reg [31:0] test_binary;
    reg [31:0] test_gray;
    wire [31:0] test_binary_next = test_binary + 32'd1;
    always @(posedge clk_test or negedge test_reset_n) begin
        if (!test_reset_n) begin
            test_binary <= 32'b0;
            test_gray <= 32'b0;
        end else begin
            test_binary <= test_binary_next;
            test_gray <= test_binary_next ^ (test_binary_next >> 1);
        end
    end

    (* async_reg = "true" *) reg [31:0] gray_ref1, gray_ref2, gray_ref3;
    (* async_reg = "true" *) reg lock_ref1, lock_ref2;
    assign lock_in_ref = lock_ref2;
    always @(posedge clk_ref or negedge ref_reset_n) begin
        if (!ref_reset_n) begin
            gray_ref1 <= 32'b0; gray_ref2 <= 32'b0; gray_ref3 <= 32'b0;
            lock_ref1 <= 1'b0; lock_ref2 <= 1'b0;
        end else begin
            gray_ref1 <= test_gray; gray_ref2 <= gray_ref1; gray_ref3 <= gray_ref2;
            lock_ref1 <= pll_lock; lock_ref2 <= lock_ref1;
        end
    end

    function [31:0] gray_to_binary;
        input [31:0] gray;
        integer k;
        begin
            gray_to_binary[31] = gray[31];
            for (k=30; k>=0; k=k-1)
                gray_to_binary[k] = gray_to_binary[k+1] ^ gray[k];
        end
    endfunction
    wire [31:0] sampled_binary = gray_to_binary(gray_ref3);
    reg [31:0] previous_binary;
    reg [31:0] reference_count;
    reg [2:0] warmup;
    wire [31:0] edge_delta = sampled_binary - previous_binary;
    always @(posedge clk_ref or negedge ref_reset_n) begin
        if (!ref_reset_n) begin
            previous_binary <= 32'b0;
            reference_count <= 32'b0;
            warmup <= 3'd0;
            measured_edges <= 32'b0;
            window_index <= 32'b0;
            measurement_valid <= 1'b0;
            frequency_ok <= 1'b0;
        end else begin
            measurement_valid <= 1'b0;
            if (warmup != 3'd4) begin
                warmup <= warmup + 1'b1;
                previous_binary <= sampled_binary;
                reference_count <= 32'b0;
            end else if (reference_count == WINDOW_CYCLES - 1) begin
                reference_count <= 32'b0;
                previous_binary <= sampled_binary;
                measured_edges <= edge_delta;
                window_index <= window_index + 1'b1;
                measurement_valid <= 1'b1;
                frequency_ok <= lock_ref2 && edge_delta >= LOW_EDGES && edge_delta <= HIGH_EDGES;
            end else begin
                reference_count <= reference_count + 1'b1;
            end
        end
    end
endmodule
