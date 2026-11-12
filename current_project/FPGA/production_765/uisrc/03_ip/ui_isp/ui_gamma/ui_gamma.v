
/*******************************MILIANKE*******************************
*Company : MiLianKe Electronic Technology Co., Ltd.
*WebSite:https://www.milianke.com
*TechWeb:https://www.uisrc.com
*tmall-shop:https://milianke.tmall.com
*jd-shop:https://milianke.jd.com
*taobao-shop1: https://milianke.taobao.com
*Create Date: 2024/10/23
*Module Name:
*File Name:
*Description: 
*The reference demo provided by Milianke is only used for learning. 
*We cannot ensure that the demo itself is free of bugs, so users 
*should be responsible for the technical problems and consequences
*caused by the use of their own products.
*Copyright: Copyright (c) MiLianKe
*All rights reserved.
*Revision: 1.0
*Signal description
*1) I_ input
*2) O_ output
*3) IO_ input output
*4) S_ system internal signal
*5) _n activ low
*6) _dg debug signal 
*7) _r delay or register
*8) _s state mechine
*********************************************************************/
/*********ui_gamma ********************************************
伽马矫正(Gamma)
--版本号1.0
*****************************************************************/
module ui_gamma #(
    parameter [4:0] GAMMA_10x = 22
)(
    input I_clk, input I_rst_n,
    input I_tlast, input I_tuser,
    input [119:0] I_tdata,
    input I_tvalid, output I_tready,
    output O_tlast, output O_tuser,
    output [95:0] O_tdata,
    output O_tvalid, input O_tready
);
    //51: retain RGB10 until the tone output. P0 is bits29:0={R10,G10,B10}.
    // Four enabled cycles, one shared CE: no stage or marker advances on stall.
    wire isp_ce = !O_tvalid || O_tready;
    reg [3:0] valid_pipe, last_pipe, user_pipe;
    assign I_tready = isp_ce;
    assign O_tvalid = valid_pipe[3];
    assign O_tlast = last_pipe[3];
    assign O_tuser = user_pipe[3];

    // All operands are fourteen bits. The exact numerator is at most4*4095,
    // so there is no rounding, signed wrap or lost low bit before subtract32.
    function [13:0] interpolate4;
        input [11:0] lo, hi;
        input [1:0] fraction;
        begin
            case (fraction)
                2'd0: interpolate4 = {lo,2'b00};
                2'd1: interpolate4 = ({2'b0,lo} << 1) + {2'b0,lo} + {2'b0,hi};
                2'd2: interpolate4 = ({2'b0,lo} << 1) + ({2'b0,hi} << 1);
                default: interpolate4 = {2'b0,lo} + ({2'b0,hi} << 1) + {2'b0,hi};
            endcase
        end
    endfunction

    always @(posedge I_clk or negedge I_rst_n) begin
        if (!I_rst_n) begin
            valid_pipe <= 4'b0;
            last_pipe <= 4'b0;
            user_pipe <= 4'b0;
        end else if (isp_ce) begin
            valid_pipe <= {valid_pipe[2:0], I_tvalid};
            last_pipe <= {last_pipe[2:0], I_tvalid && I_tlast};
            user_pipe <= {user_pipe[2:0], I_tvalid && I_tuser};
        end
    end

    genvar pixel, channel;
    generate
        for (pixel=0; pixel<4; pixel=pixel+1) begin : pixels
            for (channel=0; channel<3; channel=channel+1) begin : channels
                wire [9:0] q = I_tdata[pixel*30+(2-channel)*10 +: 10];
                wire [7:0] index0 = q[9:2];
                wire [7:0] index1 = (index0 == 8'd255) ? 8'd255 : index0 + 8'd1;
                wire [11:0] lut0, lut1;
                reg [11:0] lo0, hi0;
                reg [1:0] fraction0;
                reg [13:0] numerator1, nonnegative2;
                reg [7:0] result3;

                ui_gamma51_selected_lut #(.GAMMA_10x(GAMMA_10x)) endpoint0(
                    .I_clk(I_clk), .I_rst_n(I_rst_n), .address(index0), .value(lut0));
                ui_gamma51_selected_lut #(.GAMMA_10x(GAMMA_10x)) endpoint1(
                    .I_clk(I_clk), .I_rst_n(I_rst_n), .address(index1), .value(lut1));

                always @(posedge I_clk or negedge I_rst_n) begin
                    if (!I_rst_n) begin
                        lo0 <= 12'b0; hi0 <= 12'b0; fraction0 <= 2'b0;
                        numerator1 <= 14'b0; nonnegative2 <= 14'b0; result3 <= 8'b0;
                    end else if (isp_ce) begin
                        if (I_tvalid) begin
                            lo0 <= lut0;
                            hi0 <= lut1;
                            fraction0 <= q[1:0];
                        end
                        if (valid_pipe[0])
                            numerator1 <= interpolate4(lo0, hi0, fraction0);
                        if (valid_pipe[1])
                            nonnegative2 <= (numerator1 <= 14'd32) ? 14'd0 : numerator1 - 14'd32;
                        if (valid_pipe[2])
                            result3 <= (nonnegative2 > 14'd16320) ? 8'd255 : nonnegative2[13:6];
                    end
                end
                assign O_tdata[pixel*24+(2-channel)*8 +: 8] = result3;
            end
        end
    endgenerate
endmodule

// Constant generate selection preserves all nine original parameter tables and
// the original unsupported-parameter fallback2.2. LUT files remain unchanged.
// Two endpoint reads per channel may increase ROM/logic cost; native TD timing
// and resource acceptance is separate from the offline arithmetic proof.
module ui_gamma51_selected_lut #(
    parameter [4:0] GAMMA_10x = 22
)(
    input I_clk, input I_rst_n,
    input [7:0] address,
    output [11:0] value
);
    generate
        if (GAMMA_10x == 5'd26) begin : gamma_2_6
            ui_lut_2_6 table_selected(
                .I_clk(I_clk), .I_rst_n(I_rst_n),
                .I_LUT_2_6_data(address), .O_LUT_2_6_data(value));
        end
        else if (GAMMA_10x == 5'd24) begin : gamma_2_4
            ui_lut_2_4 table_selected(
                .I_clk(I_clk), .I_rst_n(I_rst_n),
                .I_LUT_2_4_data(address), .O_LUT_2_4_data(value));
        end
        else if (GAMMA_10x == 5'd22) begin : gamma_2_2
            ui_lut_2_2 table_selected(
                .I_clk(I_clk), .I_rst_n(I_rst_n),
                .I_LUT_2_2_data(address), .O_LUT_2_2_data(value));
        end
        else if (GAMMA_10x == 5'd20) begin : gamma_2_0
            ui_lut_2_0 table_selected(
                .I_clk(I_clk), .I_rst_n(I_rst_n),
                .I_LUT_2_0_data(address), .O_LUT_2_0_data(value));
        end
        else if (GAMMA_10x == 5'd18) begin : gamma_1_8
            ui_lut_1_8 table_selected(
                .I_clk(I_clk), .I_rst_n(I_rst_n),
                .I_LUT_1_8_data(address), .O_LUT_1_8_data(value));
        end
        else if (GAMMA_10x == 5'd16) begin : gamma_1_6
            ui_lut_1_6 table_selected(
                .I_clk(I_clk), .I_rst_n(I_rst_n),
                .I_LUT_1_6_data(address), .O_LUT_1_6_data(value));
        end
        else if (GAMMA_10x == 5'd14) begin : gamma_1_4
            ui_lut_1_4 table_selected(
                .I_clk(I_clk), .I_rst_n(I_rst_n),
                .I_LUT_1_4_data(address), .O_LUT_1_4_data(value));
        end
        else if (GAMMA_10x == 5'd12) begin : gamma_1_2
            ui_lut_1_2 table_selected(
                .I_clk(I_clk), .I_rst_n(I_rst_n),
                .I_LUT_1_2_data(address), .O_LUT_1_2_data(value));
        end
        else if (GAMMA_10x == 5'd8) begin : gamma_0_8
            ui_lut_0_8 table_selected(
                .I_clk(I_clk), .I_rst_n(I_rst_n),
                .I_LUT_0_8_data(address), .O_LUT_0_8_data(value));
        end
        else begin : fallback_2_2
            ui_lut_2_2 table_selected(
                .I_clk(I_clk), .I_rst_n(I_rst_n),
                .I_LUT_2_2_data(address), .O_LUT_2_2_data(value));
        end
    endgenerate
endmodule
