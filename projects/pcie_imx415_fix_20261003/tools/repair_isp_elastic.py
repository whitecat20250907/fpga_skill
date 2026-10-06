from pathlib import Path
import shutil,re
ROOT=Path('E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003')
ISP=ROOT/'fpga/uisrc/03_ip/ui_isp'
BACKUP=ROOT/'evidence/isp_before'
def source(name):
    p=ISP/name;b=BACKUP/name
    if not b.exists(): b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,b)
    return b.read_bytes()
def replace(name,body):
    original=source(name);header=original[:original.index(b'module ')]
    (ISP/name).write_bytes(header+body.encode('ascii'))

replace('ui_BLC.v',r'''
module ui_BLC #(
    parameter [9:0] Black_level_offset_r0=15,Black_level_offset_r1=15,
    parameter [9:0] Black_level_offset_r2=15,Black_level_offset_r3=15
)(
    input I_clk,I_rst_n,I_tlast,I_tuser,
    input [39:0] I_tdata,input I_tvalid,input [9:0] I_tdest,
    output I_tready,
    output reg O_tlast,O_tuser,output reg [39:0] O_tdata,
    output reg O_tvalid,output reg [9:0] O_tdest,input O_tready
);
wire ce=!O_tvalid||O_tready;
assign I_tready=ce;
wire [39:0] offsets={Black_level_offset_r3,Black_level_offset_r2,
                     Black_level_offset_r1,Black_level_offset_r0};
integer p;
always @(posedge I_clk or negedge I_rst_n)
    if(!I_rst_n) begin O_tlast<=0;O_tuser<=0;O_tvalid<=0;O_tdest<=0;O_tdata<=0;end
    else if(ce) begin
        O_tvalid<=I_tvalid;O_tlast<=I_tvalid&&I_tlast;O_tuser<=I_tvalid&&I_tuser;
        if(I_tvalid) begin
            O_tdest<=I_tdest;
            for(p=0;p<4;p=p+1)
                O_tdata[10*p+:10]<=(I_tdata[10*p+:10]>offsets[10*p+:10])?
                    I_tdata[10*p+:10]-offsets[10*p+:10]:10'd0;
        end
    end
endmodule
''')

replace('ui_image_cut/ui_image_cut.v',r'''
module ui_image_cut #(
    parameter [12:0] IMG_WIDTH=640,IMG_HEIGHT=480,
    parameter DATA_WIDTH=96,
    parameter SKIP_ROWS_top=2,SKIP_ROWS_bottom=2,SKIP_COLS_left=2,SKIP_COLS_right=2
)(
    input I_clk,I_rst_n,input [12:0] I_img_width,I_img_height,
    input I_tlast,I_tuser,input [DATA_WIDTH-1:0] I_tdata,input I_tvalid,
    output I_tready,output reg O_tlast,O_tuser,
    output reg [DATA_WIDTH-1:0] O_tdata,output reg O_tvalid,input O_tready
);
reg [12:0] h_cnt,v_cnt;
wire ce=!O_tvalid||O_tready;
assign I_tready=ce;
wire [12:0] x=I_tuser?13'd0:h_cnt;
wire [12:0] y=I_tuser?13'd0:v_cnt;
wire [12:0] words=I_img_width>>2;
wire skip=(y<SKIP_ROWS_top)||(y+SKIP_ROWS_bottom>=I_img_height)||
          (x<SKIP_COLS_left)||(x+SKIP_COLS_right>=words);
always @(posedge I_clk or negedge I_rst_n)
    if(!I_rst_n) begin h_cnt<=0;v_cnt<=0;O_tlast<=0;O_tuser<=0;O_tvalid<=0;O_tdata<=0;end
    else if(ce) begin
        O_tvalid<=I_tvalid;O_tlast<=I_tvalid&&I_tlast;O_tuser<=I_tvalid&&I_tuser;
        if(I_tvalid) begin
            O_tdata<=skip?{DATA_WIDTH{1'b0}}:I_tdata;
            if(I_tlast) begin h_cnt<=0;v_cnt<=y+1'b1;end
            else begin h_cnt<=x+1'b1;v_cnt<=y;end
        end
    end
endmodule
''')

# These LUTs are combinational. Freezing the registered gamma stages is safe;
# no clock gating and no generated ROM/IP configuration changes are necessary.
for name in ['ui_gamma/ui_gamma.v','ui_contrast_adj/ui_contrast_adj.v',
             'ui_brightness_adj/ui_Brightness_adj.v','ui_saturation_adj/ui_Saturation_adj.v']:
    data=source(name)
    s=data.decode('latin1')
    offset=s.index(');',s.index('module '))+2
    s=s[:offset]+'\n    wire isp_ce = !O_tvalid || O_tready;\n'+s[offset:]
    s=re.sub(r'else\s+if\s*\((I_tvalid(?:_r\[\d\])?)\)',r'else if(isp_ce && \1)',s)
    # First unconditional post-reset branch in gamma is its LUT register.
    # The remaining unconditional post-reset branches are marker registers.
    s=re.sub(r'(if\s*\(!I_rst_n\)\s*begin[\s\S]*?end)\s*else\s+begin',
             r'\1\n                else if(isp_ce) begin',s)
    s=re.sub(r'(if\s*\(!I_rst_n\)\s*\{I_tlast_r,I_tuser_r,I_tvalid_r\}\s*<=\s*0;)\s*else\s+begin',
             r'\1\n        else if(isp_ce) begin',s)
    s=re.sub(r'assign\s+I_tready\s*=\s*O_tready\s*;',r'assign I_tready = isp_ce;',s)
    # Ignore invalid sidebands; state advances only on accepted valid beats.
    s=s.replace(',I_tlast};',',I_tvalid && I_tlast};')
    s=s.replace(',I_tuser};',',I_tvalid && I_tuser};')
    (ISP/name).write_bytes(s.encode('latin1'))

# Literal LUT values for the self-check are extracted from vendor source, not
# recomputed from a guessed gamma formula. All 256 input values are checked.
lut=(ISP/'ui_gamma/ui_lut_2_2.v').read_text(encoding='latin1')
vals={int(a):int(b) for a,b in re.findall(r'(\d+)\s*:\s*O_LUT_2_2_data\s*=\s*12\x27d(\d+)',lut)}
assert len(vals)==256
(ROOT/'tb/gamma22.hex').write_text('\n'.join(f'{vals[i]:03x}' for i in range(256))+'\n')
