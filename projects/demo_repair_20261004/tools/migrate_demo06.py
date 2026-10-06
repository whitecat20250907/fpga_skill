from pathlib import Path
import hashlib, json, re, shutil, xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'06_csi_2_dsi_imx415_7cun'
SRC=Path('E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003/fpga/uisrc/03_ip')
if (DEST/'migration_applied.json').exists(): raise RuntimeError('Migration already applied; do not overwrite follow-up fixes')
def edit(rel, transform):
 p=DEST/rel
 text=p.read_bytes().decode('latin1').replace('\r\n','\n')
 p.write_bytes(transform(text).encode('latin1'))
def once(text, old, new):
 if text.count(old)!=1: raise RuntimeError('Not unique: '+repr(old))
 return text.replace(old,new,1)

project=ET.ElementTree(ET.fromstring((DEST/'fpga_prj.al').read_text(encoding='utf-8').replace('UsedInP&R','UsedInP&amp;R').replace('BitgenProperty::GeneralOption','BitgenProperty__GeneralOption')))
vfiles=project.getroot().find('Source_Files/Verilog')
provenance={}
for elem in list(vfiles):
 rel=elem.attrib['Path'].replace('\\','/')
 if '/ui_isp/' in rel:
  candidates=list((SRC/'ui_isp').rglob(Path(rel).name))
  if len(candidates)==1:
   shutil.copy2(candidates[0],DEST/rel)
   provenance[rel]=str(candidates[0])
# Helper is in generated vendor RAM source: keep complete helper + vendor wrapper.
ramrel='uisrc/03_ip/ui_isp/ui_demosaic/ui_ram_demosaic/ui_ram_demosaic.v'
shutil.copy2(SRC/'ui_isp/ui_ram_demosaic/ui_ram_demosaic.v',DEST/ramrel)
provenance[ramrel]=str(SRC/'ui_isp/ui_ram_demosaic/ui_ram_demosaic.v')
newdir=DEST/'uisrc/03_ip/csi_integrity'
newdir.mkdir(exist_ok=True)
corefiles=['csi_rx_hdr_ecc.v','csi_rx_packet_handler.v','csi_rx_10bit_unpack.v','csi_rx_vid2stream.v','sfifo.v']
for name in corefiles:
 shutil.copy2(SRC/'mipi_csi_2'/name,newdir/name)
 provenance['uisrc/03_ip/csi_integrity/'+name]=str(SRC/'mipi_csi_2'/name)
shutil.copy2(SRC/'ui_isp/image_correction.v',newdir/'image_correction.v')
provenance['uisrc/03_ip/csi_integrity/image_correction.v']=str(SRC/'ui_isp/image_correction.v')
# The preserved encrypted PHY has no packet_done feedback. It delineates each
# HS burst with valid low; wait for that boundary instead of the newer PHY's
# fixed pipeline drain. Payload valid holes remain legal while RX_BODY.
edit('uisrc/03_ip/csi_integrity/csi_rx_packet_handler.v',lambda t:
 once(once(t,'parameter GAP_TIMEOUT = 64','parameter GAP_TIMEOUT = 64,\n    parameter WAIT_VALID_LOW = 0'),
 'if(drain_count==0) state<=WAIT_HDR;',
 'if (WAIT_VALID_LOW) begin\n                    if (!I_data_valid) state<=WAIT_HDR;\n                end else if(drain_count==0) state<=WAIT_HDR;'))

def isp(t):
 t=once(t,'module ui_isp_top (','module ui_isp_top #(parameter IMG_WIDTH=1920, IMG_HEIGHT=1080, parameter BAYER_MODE="RGGB") (')
 t=once(t,'input \t\t\tI_tvalid\t\t,','input \t\t\tI_tvalid\t\t,') if False else t
 # Keep legacy externally visible port names: O_tready is downstream input,
 # I_tready is upstream output. Only the top's old connections were wrong.
 t=once(t,'.I_tready\t\t(\t\t\t\t\t),','.I_tready\t\t(I_tready\t\t\t),')
 t=re.sub(r'\s*\.IMG_HEIGHT\s*\(1080\s*\),[^\n]*\n\s*\.IMG_WIDTH\s*\(1920\s*\),[^\n]*\n', '\n',t,count=1)
 t=re.sub(r'\.BAYER_MODE\s*\("RGGB"\s*\)', '.BAYER_MODE(BAYER_MODE)',t,count=1)
 t=once(t,'X_ui_top_demosaic\n(','X_ui_top_demosaic\n(\n    .I_img_width(IMG_WIDTH), .I_img_height(IMG_HEIGHT),')
 t=once(t,') X_ui_awb (',') X_ui_awb (\n    .I_img_width(IMG_WIDTH), .I_img_height(IMG_HEIGHT),')
 t=once(t,') X_ui_image_cut \t',') X_ui_image_cut \t') if False else t
 t=re.sub(r'(?<=\.SKIP_COLS_left)\s*\(1\s*\)', '(0)',t,count=1)
 t=once(t,'X_ui_image_cut \t\n(', 'X_ui_image_cut \t\n(\n    .I_img_width(IMG_WIDTH), .I_img_height(IMG_HEIGHT),')
 return t
edit('uisrc/03_ip/ui_isp/ui_isp_top.v',isp)

def top(t):
 t=once(t,'parameter AXI_ADDR_WIDTH  = APP_ADDR_WIDTH+3,','parameter AXI_ADDR_WIDTH  = APP_ADDR_WIDTH+$clog2(`DRAM_BYTE_NUM),')
 t=once(t,'//wire   \t\t\t\t\t\t\tS_clk_25m\t\t;','wire S_clk_25m;\nwire [3:0] S_lane_error;')
 t=once(t,'assign S_ud_wclk \t\t\t\t= S_hs_rx_clk\t;', 'assign S_ud_wclk = S_clk_70m;')
 start=t.index('//csi', t.index('X_mipi_dphy_rx_over_lvds_wrapper('))
 end=t.index('//',t.index('//',t.index('X_ui_isp_top',start))+2) if False else t.index('//',t.index('//',start)+2) if False else t.index('//',start)
 # Replace CSI/unpack/crop as one unit, retaining original encrypted PHY.
 end=t.index('ui_isp_top X_ui_isp_top',start)
 t=t[:start]+'''// Protocol first byte is high byte in the preserved 06 PHY wrapper.
// The frontend adapts bytes, verifies exact WC/CRC/ECC and carries explicit
// line-end through a real Gray CDC FIFO to the stable ISP clock domain.
wire S_axis_tready;
wire [31:0] S_csi_raw_packets, S_csi_crc_errors, S_csi_ecc_errors;
wire [31:0] S_csi_wc_errors, S_csi_timeout_errors, S_csi_fifo_overflows;
wire S_csi_error_pulse;
ui06_csi_frontend X_ui06_csi_frontend (
 .I_hs_clk(S_hs_rx_clk), .I_reset_n(S_pll_lock),
 .I_hs_valid(S_hs_rx_valid), .I_hs_data(S_hs_rx_data),
 .I_video_clk(S_clk_70m), .I_video_reset_n(S_pll_lock),
 .O_tdata(S_axis_tdata), .O_tvalid(S_axis_tvalid),
 .O_tuser(S_axis_tuser), .O_tlast(S_axis_tlast), .I_tready(S_axis_tready),
 .O_raw_packets(S_csi_raw_packets), .O_crc_errors(S_csi_crc_errors),
 .O_ecc_errors(S_csi_ecc_errors), .O_wc_errors(S_csi_wc_errors),
 .O_timeout_errors(S_csi_timeout_errors), .O_fifo_overflows(S_csi_fifo_overflows),
 .O_error_pulse(S_csi_error_pulse)
);

// ISP ports retain legacy names: O_tready=input, I_tready=output.
''' + t[end:]
 # Scope replacement to ISP block, not the camera/PHY.
 begin=t.index('ui_isp_top X_ui_isp_top')
 end=t.index(');',begin)+2
 block=t[begin:end]
 block=block.replace('(S_hs_rx_clk\t\t)','(S_clk_70m\t\t)')
 block=re.sub(r'\.I_tdest\s*\([^)]*\)', ".I_tdest(10'd0)",block)
 block=re.sub(r'\.O_tready\s*\([^)]*\)', '.O_tready(S_ud_wtready)',block)
 block=re.sub(r'\.I_tready\s*\([^)]*\)', '.I_tready(S_axis_tready)',block)
 t=t[:begin]+block+t[end:]
 t=once(t,'.O_W_tready  \t(\t\t\t\t\t),','.O_W_tready  \t(S_ud_wtready\t\t),')
 return t
edit('uisrc/01_rtl/system_top.v',top)

def dbuf(t):
 # One-beat input register plus almost-full threshold leaves two FIFO slots.
 t=once(t,'W_tuser_r1        <= I_W_tuser;', 'W_tuser_r1 <= I_W_tuser && I_W_tvalid && O_W_tready;')
 t=once(t,'W_tlast_r1        <= I_W_tlast;', 'W_tlast_r1 <= I_W_tlast && I_W_tvalid && O_W_tready;')
 t=once(t,'W_tvalid_r1       <= I_W_tvalid;', 'W_tvalid_r1 <= I_W_tvalid && O_W_tready;')
 t=once(t,'W_tuser_r3        <= W_tuser_r2|W_tuser_r1|I_W_tuser;', 'W_tuser_r3 <= W_tuser_r2|W_tuser_r1|(I_W_tuser && I_W_tvalid && O_W_tready);')
 t=once(t,"assign        O_W_tready = 1'b1;", 'assign O_W_tready = I_ui_rstn && wfifo_rst_done && !wfifo_rst && !W_full_pro;')
 # Synchronize level facts used by write-domain reset/startup decisions.
 t=once(t,'//FIFO ?'+chr(0x4e) if False else 'always @(posedge I_W_wclk or negedge I_ui_rstn) begin',
 '''(* async_reg="true" *) reg w_idle_s1=1'b1,w_idle_s2=1'b1;
(* async_reg="true" *) reg w_empty_s1=1'b1,w_empty_s2=1'b1;
always @(posedge I_W_wclk or negedge I_ui_rstn) begin
 if(!I_ui_rstn) begin w_idle_s1<=1;w_idle_s2<=1;w_empty_s1<=1;w_empty_s2<=1;end
 else begin w_idle_s1<=(W_MS==S_IDLE);w_idle_s2<=w_idle_s1;w_empty_s1<=W_empty;w_empty_s2<=w_empty_s1;end
end
always @(posedge I_W_wclk or negedge I_ui_rstn) begin''')
 t=once(t,"I_W_tuser & (W_empty == 1'b0)", "I_W_tuser & (w_empty_s2 == 1'b0)")
 t=once(t,'W_MS == S_IDLE & I_W_tuser', 'w_idle_s2 & I_W_tuser')
 return t
edit('uisrc/03_ip/ui_dbuf/uidbuf.v',dbuf)

# Unregister old inaccurate parser/unpack/crop; leave originals in clone as
# historical source. The old PHY/IP registrations and ADC are untouched.
retired={'uisrc/03_ip/ui_csi_raw/ui_csi_unpacket_4lane.v','uisrc/03_ip/ui_csi_raw/ui_raw10_unpacket_4lane.v','uisrc/03_ip/ui_csi_raw/ui_image_correction.v'}
for elem in list(vfiles):
 if elem.attrib['Path'].replace('\\','/') in retired: vfiles.remove(elem)
for i,name in enumerate(corefiles+['image_correction.v','ui06_csi_frontend.v']):
 elem=ET.SubElement(vfiles,'File',Path='uisrc/03_ip/csi_integrity/'+name)
 info=ET.SubElement(elem,'FileInfo')
 for key,value in [('UsedInSyn','true'),('UsedInP&R','true'),('BelongTo','design_1'),('CompileOrder',str(100+i))]:
  ET.SubElement(info,'Attr',Name=key,Val=value)
ET.indent(project,space='    ')
project.write(DEST/'fpga_prj.al',encoding='utf-8',xml_declaration=True)
# TD's .al writer uses this literal legacy attribute spelling.
alpath=DEST/'fpga_prj.al'
alpath.write_text(alpath.read_text(encoding='utf-8').replace('UsedInP&amp;R','UsedInP&R').replace('BitgenProperty__GeneralOption','BitgenProperty::GeneralOption'),encoding='utf-8')
(DEST/'migration_applied.json').write_text(json.dumps({'source':str(SRC),'copied':provenance,'retired_active_sources':sorted(retired),'status':'Migrated source; simulations, TD and board verification pending'},indent=2),encoding='utf-8')
print('Migrated demo06; preserved encrypted PHY, PLL/DDR/DSI IP and original ADC.')
