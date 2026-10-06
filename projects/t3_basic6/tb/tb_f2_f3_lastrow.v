`timescale 1ns/1ps
module tb_f2_f3_lastrow;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0,s_valid=0,s_sof=0,s_last=0;
    reg [63:0] s_data=0;
    wire g_valid,g_sof,g_last,g_overlap;
    wire [63:0] g_data;
    wire m_valid,m_sof,m_last,line_overlap;
    wire [63:0] m_data;
    reg [7:0] input_gray[0:3839],expected[0:5119];
    integer row,col,b,byte_count=0,sof_count=0,last_count=0;
    gauss3x3_yuyv_quad #(.WIDTH(1920),.HEIGHT(2),
                          .BOTTOM_WAIT(1024)) u_gauss(
        .clk(clk),.rst_n(rst_n),.s_valid(s_valid),.s_data(s_data),
        .s_sof(s_sof),.s_last(s_last),.m_valid(g_valid),
        .m_data(g_data),.m_sof(g_sof),.m_last(g_last),
        .input_overlap(g_overlap)
    );
    lz4_line_packetizer #(.WIDTH(1920),.HEIGHT(2),
                           .QUANT_BITS(4)) u_codec(
        .clk(clk),.rst_n(rst_n),.s_valid(g_valid),.s_data(g_data),
        .s_sof(g_sof),.s_last(g_last),.sensor_sof(s_sof),
        .link_error(7'd0),.bridge_overflow_count(32'd0),
        .m_valid(m_valid),.m_data(m_data),
        .m_sof(m_sof),.m_last(m_last),.line_overlap(line_overlap)
    );
    always @(negedge clk) begin
        if(rst_n && m_valid) begin
            if(m_sof) sof_count=sof_count+1;
            if(m_last) last_count=last_count+1;
            for(b=0;b<8;b=b+1) begin
                if(byte_count>=5120) $fatal(1,"extra container bytes");
                if(!(byte_count>=1952 && byte_count<2008) &&
                   m_data[b*8+:8]!==expected[byte_count])
                    $fatal(1,"byte %0d got %h expected %h",
                           byte_count,m_data[b*8+:8],expected[byte_count]);
                byte_count=byte_count+1;
            end
        end
    end
    initial begin
        $readmemh("tb/generated/f2_f3_input.hex",input_gray);
        $readmemh("tb/generated/f2_f3_expected.hex",expected);
        repeat(4) @(posedge clk);
        @(negedge clk);rst_n=1;
        for(row=0;row<2;row=row+1) begin
            for(col=0;col<480;col=col+1) begin
                @(negedge clk);
                s_valid=1;s_sof=(row==0 && col==0);s_last=(col==479);
                s_data={8'h80,input_gray[row*1920+col*4+3],
                        8'h80,input_gray[row*1920+col*4+2],
                        8'h80,input_gray[row*1920+col*4+1],
                        8'h80,input_gray[row*1920+col*4]};
            end
            @(negedge clk);s_valid=0;s_sof=0;s_last=0;
            if(row==0) repeat(1145) @(posedge clk);
        end
        repeat(4000) @(posedge clk);
        if(byte_count!=5120 || sof_count!=1 || last_count!=2 ||
           g_overlap || line_overlap)
            $fatal(1,"bytes=%0d sof=%0d last=%0d gerr=%b lerr=%b",
                   byte_count,sof_count,last_count,g_overlap,line_overlap);
        $display("PASS F2 Gaussian -> F3: last row delayed, two exact CRC containers");
        $finish;
    end
endmodule
