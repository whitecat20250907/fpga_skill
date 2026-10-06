`timescale 1ns/1ps
module tb_bridge_overflow_count;
    reg src_clk=0,dst_clk=0,rst_n=0,s_valid=0;
    reg [63:0] s_data=0;
    wire overflow;
    wire [31:0] overflow_count;
    always #5 src_clk=~src_clk;
    always #7 dst_clk=~dst_clk;
    yuyv_quad_async_bridge #(.ADDR_BITS(3)) dut(
        .src_clk(src_clk),.dst_clk(dst_clk),.rst_n(rst_n),
        .s_valid(s_valid),.s_data(s_data),.s_sof(1'b0),.s_last(1'b0),
        .overflow(overflow),.overflow_count(overflow_count),
        .m_valid(),.m_ready(1'b0),.m_data(),.m_sof(),.m_last()
    );
    integer i;
    initial begin
        repeat(3) @(negedge src_clk);
        rst_n=1;
        for(i=0;i<12;i=i+1) begin
            @(negedge src_clk);s_valid=1;s_data=i;
        end
        @(negedge src_clk);s_valid=0;
        repeat(3) @(negedge src_clk);
        if(!overflow || overflow_count!=4)
            $fatal(1,"expected 4 dropped 64-bit words, got %0d",overflow_count);
        $display("PASS bridge overflow counted 4 dropped words");
        $finish;
    end
endmodule
