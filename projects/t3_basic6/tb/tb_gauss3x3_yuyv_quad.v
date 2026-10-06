`timescale 1ns/1ps
module tb_gauss3x3_yuyv_quad;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0, s_valid=0, s_sof=0, s_last=0;
    reg [63:0] s_data=0;
    wire m_valid,m_sof,m_last,input_overlap;
    wire [63:0] m_data;
    reg [7:0] pix [0:23];
    integer y,x,i,j,xx,yy,sum,expected,out_count=0,n,r,c;
    gauss3x3_yuyv_quad #(.WIDTH(8),.HEIGHT(3),.GROUPS(2)) dut (
        .clk(clk),.rst_n(rst_n),.s_valid(s_valid),.s_data(s_data),
        .s_sof(s_sof),.s_last(s_last),.m_valid(m_valid),
        .m_data(m_data),.m_sof(m_sof),.m_last(m_last),
        .input_overlap(input_overlap)
    );
    function [63:0] pack4;
        input [7:0] a,b,c,d;
        begin pack4={8'h80,d,8'h80,c,8'h80,b,8'h80,a}; end
    endfunction
    function integer clamp_x;
        input integer v;
        begin clamp_x=(v<0)?0:((v>7)?7:v); end
    endfunction
    function integer clamp_y;
        input integer v;
        begin clamp_y=(v<0)?0:((v>2)?2:v); end
    endfunction
    task send_group;
        input integer row,col;
        begin
            @(negedge clk);
            s_valid=1; s_sof=(row==0 && col==0); s_last=(col==1);
            s_data=pack4(pix[row*8+col*4],pix[row*8+col*4+1],
                         pix[row*8+col*4+2],pix[row*8+col*4+3]);
            @(posedge clk);
        end
    endtask
    always @(posedge clk) begin
        #1;
        if (m_valid) begin
            y=(out_count/2); x=(out_count%2)*4;
            if (m_sof !== (out_count==0) || m_last !== (out_count%2==1))
                $fatal(1,"sideband mismatch group %0d",out_count);
            for (i=0;i<4;i=i+1) begin
                sum=0;
                for (j=-1;j<=1;j=j+1) begin
                    yy=clamp_y(y+j);
                    xx=clamp_x(x+i-1);
                    sum=sum+pix[yy*8+xx]*((j==0)?2:1);
                    xx=clamp_x(x+i);
                    sum=sum+pix[yy*8+xx]*((j==0)?4:2);
                    xx=clamp_x(x+i+1);
                    sum=sum+pix[yy*8+xx]*((j==0)?2:1);
                end
                expected=(sum+8)>>4;
                if (m_data[i*16+:8] !== expected[7:0] ||
                    m_data[i*16+8+:8] !== 8'h80)
                    $fatal(1,"pixel y=%0d x=%0d got=%0d expected=%0d",
                           y,x+i,m_data[i*16+:8],expected);
            end
            out_count=out_count+1;
        end
    end
    initial begin
        for (n=0;n<24;n=n+1) pix[n]=(n*n*7+n*13+5)&255;
        repeat (3) @(posedge clk);
        @(negedge clk); rst_n=1;
        for (r=0;r<3;r=r+1) begin
            for (c=0;c<2;c=c+1) send_group(r,c);
            @(negedge clk); s_valid=0; s_sof=0; s_last=0;
            repeat (3) @(posedge clk);
        end
        repeat (12) @(posedge clk);
        if (out_count!=6 || input_overlap)
            $fatal(1,"output groups=%0d overlap=%b",out_count,input_overlap);
        $display("PASS gray+gauss: 24 exact pixels, replicated borders");
        $finish;
    end
endmodule
