// Bind the selected51 pre-pack ISP bus to four low-first RGB3 pixel words.
// This only wires bytes. Valid/ready, frame identity and fanout remain external.
`timescale 1ns/1ps
`default_nettype none
module rgb4_isp_to_rgb3(input wire [95:0] isp_rgb,output wire [95:0] rgb3);
    genvar p;
    generate for(p=0;p<4;p=p+1) begin: pixel
        assign rgb3[p*24+:24]={isp_rgb[p*24+:8],isp_rgb[p*24+8+:8],isp_rgb[p*24+16+:8]};
    end endgenerate
endmodule
`default_nettype wire
