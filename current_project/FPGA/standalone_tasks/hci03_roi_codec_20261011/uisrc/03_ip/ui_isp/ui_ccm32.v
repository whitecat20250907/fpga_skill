// Exact production37 CCM module; copied as a separate registered source.
// Physical37 coefficients are a candidate for06; its own DSI/sensor validation remains required.
module ui_ccm32 (
    input I_clk, I_rst_n, I_tlast, I_tuser, I_tvalid,
    input [95:0] I_tdata,
    output I_tready,
    output reg O_tlast, O_tuser, O_tvalid,
    output reg [95:0] O_tdata,
    input O_tready
);
    localparam signed [15:0] C00 =  16'sd5117;
    localparam signed [15:0] C01 = - 16'sd824;
    localparam signed [15:0] C02 =  16'sd71;
    localparam signed [15:0] C10 = - 16'sd1555;
    localparam signed [15:0] C11 =  16'sd2747;
    localparam signed [15:0] C12 = - 16'sd957;
    localparam signed [15:0] C20 =  16'sd205;
    localparam signed [15:0] C21 = - 16'sd816;
    localparam signed [15:0] C22 =  16'sd4305;
    wire ce = !O_tvalid || O_tready;
    assign I_tready = ce;
    reg [2:0] vp, up, lp;
    reg signed [24:0] product [0:35];
    reg signed [25:0] pair_sum [0:11];
    reg signed [24:0] third_product [0:11];
    reg signed [26:0] total [0:11];
    function [7:0] clamp;
        input signed [26:0] q;
        reg signed [27:0] rounded;
        begin
            rounded = {q[26],q} + 28'sd512;
            if (rounded < 0) clamp = 0;
            else if (rounded >= 28'sd261120) clamp = 255;
            else clamp = rounded[17:10];
        end
    endfunction
    integer p, k;
    always @(posedge I_clk or negedge I_rst_n) begin
        if (!I_rst_n) begin
            vp<=0; up<=0; lp<=0; O_tvalid<=0; O_tuser<=0; O_tlast<=0; O_tdata<=0;
            for(k=0;k<36;k=k+1) product[k]<=0;
            for(k=0;k<12;k=k+1) begin pair_sum[k]<=0;third_product[k]<=0;total[k]<=0;end
        end else if (ce) begin
            vp<={vp[1:0],I_tvalid}; up<={up[1:0],I_tvalid&&I_tuser}; lp<={lp[1:0],I_tvalid&&I_tlast};
            O_tvalid<=vp[2]; O_tuser<=up[2]; O_tlast<=lp[2];
            for(p=0;p<4;p=p+1) begin
                product[9*p+0] <= $signed({1'b0,I_tdata[24*p+16+:8]}) * C00;
                product[9*p+1] <= $signed({1'b0,I_tdata[24*p+ 8+:8]}) * C01;
                product[9*p+2] <= $signed({1'b0,I_tdata[24*p+ 0+:8]}) * C02;
                product[9*p+3] <= $signed({1'b0,I_tdata[24*p+16+:8]}) * C10;
                product[9*p+4] <= $signed({1'b0,I_tdata[24*p+ 8+:8]}) * C11;
                product[9*p+5] <= $signed({1'b0,I_tdata[24*p+ 0+:8]}) * C12;
                product[9*p+6] <= $signed({1'b0,I_tdata[24*p+16+:8]}) * C20;
                product[9*p+7] <= $signed({1'b0,I_tdata[24*p+ 8+:8]}) * C21;
                product[9*p+8] <= $signed({1'b0,I_tdata[24*p+ 0+:8]}) * C22;
                O_tdata[24*p+16+:8]<=clamp(total[3*p+0]);
                O_tdata[24*p+ 8+:8]<=clamp(total[3*p+1]);
                O_tdata[24*p+ 0+:8]<=clamp(total[3*p+2]);
            end
            for(k=0;k<12;k=k+1) begin
                pair_sum[k] <= {product[3*k][24],product[3*k]} + {product[3*k+1][24],product[3*k+1]};
                third_product[k] <= product[3*k+2];
                total[k] <= {pair_sum[k][25],pair_sum[k]} + {{2{third_product[k][24]}},third_product[k]};
            end
        end
    end
endmodule
