from pathlib import Path
import re
ROOT=Path('E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003')
ISP=ROOT/'fpga/uisrc/03_ip/ui_isp'
# Run after repair_isp_elastic.py. Keep the literal LUTs and selected gamma.
p=ISP/'ui_gamma/ui_gamma.v'
s=p.read_bytes().decode('latin1')
assert s.count('[20]) ? 8\x27d255')==3
s=s.replace('[20]) ? 8\x27d255','[20]) ? 8\x27d0')
p.write_bytes(s.encode('latin1'))

p=ISP/'ui_contrast_adj/ui_contrast_adj.v'
old=(ROOT/'evidence/isp_before/ui_contrast_adj/ui_contrast_adj.v').read_bytes()
header=old[:old.index(b'module ')]
body=r'''
// Signed contrast arithmetic. A negative (pixel-128) must not be interpreted
// as an unsigned 16-bit value before multiplication by an odd coefficient.
module ui_Contrast_adj #(parameter contrast_level=160)(
    input I_clk,I_rst_n,I_tlast,I_tuser,input [95:0] I_tdata,input I_tvalid,
    output I_tready,output O_tlast,O_tuser,output [95:0] O_tdata,
    output O_tvalid,input O_tready
);
reg [2:0] valid,last,user;
wire ce=!valid[2]||O_tready;
assign I_tready=ce;
assign O_tvalid=valid[2];assign O_tlast=last[2];assign O_tuser=user[2];
function [7:0] clamp;
    input signed [40:0] value;
    begin clamp=(value<0)?8'd0:((value>255)?8'd255:value[7:0]);end
endfunction
always @(posedge I_clk or negedge I_rst_n)
    if(!I_rst_n) begin valid<=0;last<=0;user<=0;end
    else if(ce) begin
        valid<={valid[1:0],I_tvalid};
        last<={last[1:0],I_tvalid&&I_tlast};
        user<={user[1:0],I_tvalid&&I_tuser};
    end
genvar c;
generate for(c=0;c<12;c=c+1) begin: channel
    reg signed [8:0] delta;
    reg signed [40:0] product;
    reg [7:0] value;
    always @(posedge I_clk or negedge I_rst_n)
        if(!I_rst_n) begin delta<=0;product<=0;value<=0;end
        else if(ce) begin
            if(I_tvalid) delta<=$signed({1'b0,I_tdata[8*c+:8]})-9'sd128;
            if(valid[0]) product<=delta*$signed(contrast_level);
            if(valid[1]) value<=clamp((product>>>7)+41'sd128);
        end
    assign O_tdata[8*c+:8]=value;
end endgenerate
endmodule
'''
p.write_bytes(header+body.encode('ascii'))

lut=(ISP/'ui_gamma/ui_lut_0_8.v').read_bytes().decode('latin1')
vals={int(a):int(b) for a,b in re.findall(r'(\d+)\s*:\s*O_LUT_0_8_data\s*=\s*12\x27d(\d+)',lut)}
assert len(vals)==256
(ROOT/'tb/gamma08.hex').write_text('\n'.join(f'{vals[i]:03x}' for i in range(256))+'\n')
