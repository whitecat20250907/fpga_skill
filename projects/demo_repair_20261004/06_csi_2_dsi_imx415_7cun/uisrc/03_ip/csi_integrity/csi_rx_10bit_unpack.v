//--------------------------------------------------------------------------------------------
// CSI-2 10位到8位解包模块
// 功能说明：
//   将CSI-2接口的32位输入数据解包为40位输出数据
//   支持连续的10位数据流解包为8位数据
//--------------------------------------------------------------------------------------------

module csi_rx_10bit_unpack (
    input wire I_clock, I_reset_n, I_enable,
    input wire I_line_in,
    input wire [31:0] I_data_in,
    input wire I_din_valid,
    input wire [2:0] I_din_bytes,
    input wire I_din_last,
    output reg [39:0] O_data_out,
    output reg O_dout_valid,
    output reg O_dout_last,
    output reg O_unpack_error
);
// Residual bytes are 0..4, in low byte-first order. Up to four new bytes
// complete at most one RAW10 group. The byte-count, not valid gaps, ends a line.
reg [63:0] byte_buffer;
reg [2:0] byte_count;
reg [63:0] combined;
reg [3:0] total;
integer b;
always @(*) begin
    combined=byte_buffer;
    total={1'b0,byte_count}+{1'b0,I_din_bytes};
    for(b=0;b<4;b=b+1)
        if(b<I_din_bytes) combined[(byte_count+b)*8+:8]=I_data_in[b*8+:8];
end
function [39:0] mipi_unpack;
    input [39:0] p;
    begin
        mipi_unpack[9:0]={p[7:0],p[33:32]};
        mipi_unpack[19:10]={p[15:8],p[35:34]};
        mipi_unpack[29:20]={p[23:16],p[37:36]};
        mipi_unpack[39:30]={p[31:24],p[39:38]};
    end
endfunction
always @(posedge I_clock or negedge I_reset_n) begin
    if(!I_reset_n) begin
        byte_buffer<=0; byte_count<=0;
        O_data_out<=0; O_dout_valid<=0; O_dout_last<=0; O_unpack_error<=0;
    end else begin
        O_dout_valid<=0; O_dout_last<=0; O_unpack_error<=0;
        if(!I_enable || I_line_in) begin
            byte_buffer<=0; byte_count<=0;
        end else if(I_din_valid) begin
            if(I_din_bytes==0 || I_din_bytes>4) begin
                byte_buffer<=0; byte_count<=0; O_unpack_error<=1;
            end else if(total>=5) begin
                O_data_out<=mipi_unpack(combined[39:0]);
                O_dout_valid<=1;
                O_dout_last<=I_din_last && total==5;
                byte_buffer<=combined>>40; byte_count<=total-5;
                if(I_din_last && total!=5) begin
                    O_unpack_error<=1; byte_buffer<=0; byte_count<=0;
                end
            end else begin
                byte_buffer<=combined; byte_count<=total;
                if(I_din_last) begin
                    O_unpack_error<=1; byte_buffer<=0; byte_count<=0;
                end
            end
        end
    end
end
endmodule
