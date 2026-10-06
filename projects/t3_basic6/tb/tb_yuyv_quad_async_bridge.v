`timescale 1ns/1ps
module tb_yuyv_quad_async_bridge;
    reg src_clk=0, dst_clk=0, rst_n=0;
    always #3 src_clk=~src_clk;
    always #4 dst_clk=~dst_clk;
    reg s_valid=0, s_sof=0, s_last=0, m_ready=0;
    reg [63:0] s_data=0;
    wire overflow, m_valid, m_sof, m_last;
    wire [31:0] overflow_count;
    wire [31:0] m_data;
    integer i, n=0;
    reg [31:0] expected [0:15];

    yuyv_quad_async_bridge #(.ADDR_BITS(3)) dut (
        .src_clk(src_clk), .dst_clk(dst_clk), .rst_n(rst_n),
        .s_valid(s_valid), .s_data(s_data), .s_sof(s_sof),
        .s_last(s_last), .overflow(overflow),
        .overflow_count(overflow_count),
        .m_valid(m_valid), .m_ready(m_ready), .m_data(m_data),
        .m_sof(m_sof), .m_last(m_last)
    );

    initial begin
        for (i=0; i<16; i=i+1) expected[i]=32'h80008000+i;
        #30 rst_n=1;
        fork
            begin
                for (i=0; i<8; i=i+1) begin
                    @(negedge src_clk);
                    s_valid=1; s_data={expected[2*i+1],expected[2*i]};
                    s_sof=(i==0); s_last=(i==3 || i==7);
                    @(negedge src_clk);
                    s_valid=0; s_sof=0; s_last=0;
                    repeat (3) @(negedge src_clk);
                end
            end
            begin
                repeat (4) @(negedge dst_clk);
                m_ready=1;
            end
        join
    end
    always @(posedge dst_clk) if (rst_n && m_valid && m_ready) begin
        if (n>=16 || m_data!==expected[n] || m_sof!==(n==0) ||
            m_last!==(n==7 || n==15)) begin
            $display("FAIL n=%0d data=%h sof=%b last=%b",n,m_data,m_sof,m_last);
            $fatal;
        end
        n=n+1;
    end
    always @(negedge dst_clk) if (rst_n && m_ready && n>0 && n<16 &&
                                  n!=8 && !m_valid)
        $fatal(1,"FAIL CSI-2 payload bubble after word %0d",n-1);
    initial begin
        #1500;
        if (n!=16 || overflow || overflow_count!=0)
            $fatal(1,"FAIL count=%0d overflow=%b dropped=%0d",n,overflow,overflow_count);
        $display("PASS bridge 16 words, 2 lines, no overflow");
        $finish;
    end
endmodule
