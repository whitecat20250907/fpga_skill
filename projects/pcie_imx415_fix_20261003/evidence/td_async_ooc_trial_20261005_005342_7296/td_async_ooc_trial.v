// Independent digital TD attribute/OOC trial, never part of the FPGA project.
module td_async_ooc_trial (
    input wire clk,
    input wire reset_n,
    input wire async_input,
    output wire uart_like_tx
);
    (* async_reg = "true" *) reg [2:0] async_sync;
    (* mark_debug = "true" *) reg [7:0] count;
    always @(posedge clk or negedge reset_n) begin
        if (!reset_n) begin
            async_sync <= 3'b000;
            count <= 8'h00;
        end else begin
            async_sync <= {async_sync[1:0], async_input};
            count <= count + 1'b1;
        end
    end
    assign uart_like_tx = count[7] ^ async_sync[2];
endmodule
