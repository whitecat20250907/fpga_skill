`timescale 1ns/1ps
module tb_histeq_64;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0,s_valid=0,s_sof=0,s_last=0;
    reg [63:0] s_data=0;
    wire m_valid,m_sof,m_last,blank_overlap;
    wire [63:0] m_data;
    integer frame_index=0,checks=0,r,c,k,expected;
    histeq_yuyv_quad #(.WIDTH(8),.HEIGHT(2),.HIST_SHIFT(0),
                       .BINS(64)) dut (
        .clk(clk),.rst_n(rst_n),.s_valid(s_valid),.s_data(s_data),
        .s_sof(s_sof),.s_last(s_last),.m_valid(m_valid),
        .m_data(m_data),.m_sof(m_sof),.m_last(m_last),
        .blank_overlap(blank_overlap)
    );
    task send_group;
        input integer row,col;
        begin
            @(negedge clk);
            s_valid=1;s_sof=(row==0 && col==0);s_last=(col==1);
            s_data={8'h80,8'd65,8'h80,8'd64,
                    8'h80,8'd1,8'h80,8'd0};
            #1;
            if (!m_valid || m_sof!==s_sof || m_last!==s_last)
                $fatal(1,"stream sideband mismatch");
            for(k=0;k<4;k=k+1) begin
                if(frame_index==0)
                    case(k)
                        0:expected=0;1:expected=1;
                        2:expected=64;default:expected=65;
                    endcase
                else expected=(k<2)?0:255;
                if(m_data[k*16+:8]!==expected[7:0])
                    $fatal(1,"frame=%0d pixel=%0d got=%0d expected=%0d",
                           frame_index,k,m_data[k*16+:8],expected);
            end
            checks=checks+1;
            @(posedge clk);
        end
    endtask
    initial begin
        repeat(3) @(posedge clk);
        @(negedge clk);rst_n=1;
        repeat(80) @(posedge clk);
        for(frame_index=0;frame_index<2;frame_index=frame_index+1) begin
            for(r=0;r<2;r=r+1) begin
                for(c=0;c<2;c=c+1) send_group(r,c);
                @(negedge clk);s_valid=0;s_sof=0;s_last=0;
                repeat(2) @(posedge clk);
            end
            repeat(500) @(posedge clk);
        end
        if(checks!=8 || blank_overlap)
            $fatal(1,"checks=%0d overlap=%b",checks,blank_overlap);
        $display("PASS 64-bin FPGA histogram equalizer: exact two-frame mapping");
        $finish;
    end
endmodule
