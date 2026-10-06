`timescale 1ns/1ps
module tb_f2_meta_chain;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0,s_valid=0,s_sof=0,s_last=0;
    reg [63:0] s_data=0;
    reg [7:0] p0,p1,p2,p3;
    wire gv,gs,gl,go,hv,hs,hl,ho,mv,ms,ml;
    wire [63:0] gd,hd,md;
    integer frame,row,col,seen=0,sofs=0,ends=0;
    gauss3x3_yuyv_quad #(.WIDTH(32),.HEIGHT(4),.GROUPS(8)) g (
        .clk(clk),.rst_n(rst_n),.s_valid(s_valid),.s_data(s_data),
        .s_sof(s_sof),.s_last(s_last),.m_valid(gv),.m_data(gd),
        .m_sof(gs),.m_last(gl),.input_overlap(go));
    histeq_yuyv_quad #(.WIDTH(32),.HEIGHT(4),.HIST_SHIFT(0)) h (
        .clk(clk),.rst_n(rst_n),.s_valid(gv),.s_data(gd),
        .s_sof(gs),.s_last(gl),.m_valid(hv),.m_data(hd),
        .m_sof(hs),.m_last(hl),.blank_overlap(ho));
    camera_meta_overlay m (
        .clk(clk),.rst_n(rst_n),.s_valid(hv),.s_data(hd),
        .s_sof(hs),.s_last(hl),.lane_error(4'd0),
        .bridge_overflow(1'b0),.processing_error(go|ho),
        .m_valid(mv),.m_data(md),.m_sof(ms),.m_last(ml));
    always @(posedge clk) begin
        #1;
        if (mv) begin
            if (ms) begin
                sofs=sofs+1;
                if (md!=={32'd1,32'h41475046})
                    $fatal(1,"missing metadata magic");
            end
            if (ml) ends=ends+1;
            seen=seen+1;
        end
    end
    initial begin
        repeat (4) @(posedge clk);
        @(negedge clk); rst_n=1;
        repeat (270) @(posedge clk);
        for (frame=0;frame<2;frame=frame+1) begin
            for (row=0;row<4;row=row+1) begin
                for (col=0;col<8;col=col+1) begin
                    @(negedge clk);
                    s_valid=1;s_sof=(row==0 && col==0);s_last=(col==7);
                    p0=row*13+col*4;p1=p0+1;p2=p0+2;p3=p0+3;
                    s_data={8'h80,p3,8'h80,p2,8'h80,p1,8'h80,p0};
                    @(posedge clk);
                end
                @(negedge clk);s_valid=0;s_sof=0;s_last=0;
                repeat (3) @(posedge clk);
            end
            repeat (1500) @(posedge clk);
        end
        if (seen!=64 || sofs!=2 || ends!=8 || go || ho)
            $fatal(1,"seen=%0d sofs=%0d ends=%0d g=%b h=%b",
                   seen,sofs,ends,go,ho);
        $display("PASS F2+F5 chain: 2 frames, 64 groups, exact geometry");
        $finish;
    end
endmodule
