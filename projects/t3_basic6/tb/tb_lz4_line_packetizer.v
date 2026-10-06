`timescale 1ns/1ps
module tb_lz4_line_packetizer;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0,s_valid=0,s_sof=0,s_last=0;
    reg [63:0] s_data=0;
    wire m_valid,m_sof,m_last,line_overlap;
    wire [63:0] m_data;
    reg [7:0] gray[0:5759],expected[0:7679];
    integer i,b,c,cycles,worst_cycles,byte_count,sof_count,last_count,fd;
    lz4_line_packetizer dut(
        .clk(clk),.rst_n(rst_n),.s_valid(s_valid),.s_data(s_data),
        .s_sof(s_sof),.s_last(s_last),.sensor_sof(s_sof),
        .link_error(7'd0),.bridge_overflow_count(32'd0),.m_valid(m_valid),
        .m_data(m_data),.m_sof(m_sof),.m_last(m_last),
        .line_overlap(line_overlap)
    );
    initial begin
        $readmemh("tb/generated/lz4_gray_row.hex",gray);
        $readmemh("tb/generated/lz4_expected_row.hex",expected);
        fd=$fopen("log/lz4_hdl_3rows.hex","w");
        if(!fd) $fatal(1,"cannot open HDL output file");
        repeat(4) @(posedge clk);
        @(negedge clk);rst_n=1;
        byte_count=0;sof_count=0;last_count=0;worst_cycles=0;
        for(c=0;c<3;c=c+1) begin
            for(i=0;i<480;i=i+1) begin
                @(negedge clk);
                s_valid=1;s_sof=(c==0 && i==0);s_last=(i==479);
                s_data={8'h80,gray[c*1920+i*4+3],
                        8'h80,gray[c*1920+i*4+2],
                        8'h80,gray[c*1920+i*4+1],
                        8'h80,gray[c*1920+i*4]};
            end
            @(negedge clk);s_valid=0;s_sof=0;s_last=0;
            cycles=0;
            while(byte_count<(c+1)*2560 && cycles<1800) begin
                @(negedge clk);cycles=cycles+1;
                if(m_valid) begin
                    if(m_sof) sof_count=sof_count+1;
                    if(m_last) last_count=last_count+1;
                    for(b=0;b<8;b=b+1) begin
                        if(c==0 && byte_count>=1952 && byte_count<2008) begin
                            if(byte_count==1952 && m_data[b*8+:8]!==8'h54)
                                $fatal(1,"missing TICK telemetry");
                            if(byte_count==1992 && m_data[b*8+:8]!==8'h4F)
                                $fatal(1,"missing OVFL telemetry");
                        end else if(m_data[b*8+:8]!==expected[byte_count])
                            $fatal(1,"byte %0d got %h expected %h",
                                   byte_count,m_data[b*8+:8],expected[byte_count]);
                        $fdisplay(fd,"%02h",m_data[b*8+:8]);
                        byte_count=byte_count+1;
                    end
                end
            end
            if(cycles>worst_cycles) worst_cycles=cycles;
            if(cycles>=1100)
                $fatal(1,"line packet exceeded measured camera blank budget");
        end
        if(byte_count!=7680 || sof_count!=1 || last_count!=3 || line_overlap)
            $fatal(1,"incomplete packet bytes=%0d sof=%0d last=%0d overlap=%b",
                   byte_count,sof_count,last_count,line_overlap);
        $fclose(fd);
        $display("PASS LZ4: three complete rows, Python golden exact; worst post-line %0d clocks",
                 worst_cycles);
        $finish;
    end
endmodule
