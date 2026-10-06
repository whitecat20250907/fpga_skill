`timescale 1ns/1ps
module tb_yuyv_quad_async_bridge_full;
    reg src_clk=0, dst_clk=0, rst_n=0;
    always #3 src_clk=~src_clk;
    always #4 dst_clk=~dst_clk;
    reg s_valid=0, s_sof=0, s_last=0;
    reg [63:0] s_data=0;
    wire overflow, m_valid, m_sof, m_last;
    wire [31:0] overflow_count;
    wire [31:0] m_data;
    integer i, n=0;
    reg in_line=0;
    yuyv_quad_async_bridge #(.ADDR_BITS(10)) dut (
        .src_clk(src_clk), .dst_clk(dst_clk), .rst_n(rst_n),
        .s_valid(s_valid), .s_data(s_data), .s_sof(s_sof),
        .s_last(s_last), .overflow(overflow),
        .overflow_count(overflow_count),
        .m_valid(m_valid), .m_ready(1'b1), .m_data(m_data),
        .m_sof(m_sof), .m_last(m_last)
    );
    initial begin
        #30 rst_n=1;
        for (i=0; i<960; i=i+1) begin
            @(negedge src_clk);
            s_valid=1;
            s_data[31:0]=2*i;
            s_data[63:32]=2*i+1;
            s_sof=(i==0);
            s_last=(i==479 || i==959);
        end
        @(negedge src_clk);
        s_valid=0; s_last=0; s_sof=0;
    end
    always @(posedge dst_clk) if (rst_n) begin
        if (in_line && !m_valid)
            $fatal(1,"FAIL bubble in line at output %0d",n);
        if (m_valid) begin
            if (n>=1920 || m_data!==n || m_sof!==(n==0) ||
                m_last!==(n==959 || n==1919))
                $fatal(1,"FAIL output %0d data %h SOF %b EOL %b",
                       n,m_data,m_sof,m_last);
            in_line=!m_last;
            n=n+1;
        end
    end
    initial begin
        #30000;
        if (n!=1920 || overflow || overflow_count!=0)
            $fatal(1,"FAIL count %0d overflow %b dropped %0d",
                   n,overflow,overflow_count);
        $display("PASS 2x1920-pixel lines, continuous payload, no overflow");
        $finish;
    end
endmodule
