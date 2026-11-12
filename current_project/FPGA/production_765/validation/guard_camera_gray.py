"""Exact physical camera FIFO/presence Gray boundaries; add bounded skew, no cuts."""
from pathlib import Path
import argparse,importlib.util,json,re,hashlib
ap=argparse.ArgumentParser()
for n in ('parser','netlist','inventory','fifo-rtl','detector-rtl','out'):ap.add_argument('--'+n,type=Path,required=True)
a=ap.parse_args();sp=importlib.util.spec_from_file_location('physical',a.parser);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
rtl=m.norm(a.fifo_rtl.read_text());detector=m.norm(a.detector_rtl.read_text())
for fragment in ('bin2gray[(ADDR_WIDTH-1)]=bin[(ADDR_WIDTH-1)];','bin2gray[(j-1)]=(bin[j]^bin[(j-1)]);','assignprimary_addr_gray=bin2gray(primary_addr_i);','primary_addr_gray_reg<=primary_addr_gray;','assignrd_rst=asy_r_rst1;','assignwr_rst=asy_w_rst1;'):
 assert fragment in rtl,('Gray/reset RTL contract changed',fragment)
assert 'source_count<=source_next;source_gray<=(source_next>>1)^source_next;' in detector
nettext=a.netlist.read_text();cs=m.parse_cells(nettext)
# Compare proven clock connectivity through constant-enabled regional buffers.
# The exported netlist and all native pin identities remain unmodified.
clock_parent={}
for hit in re.finditer(r'\bPH1_PHY_SCLK_V2\s*(?:#\((.*?)\)\s*)?(\\\S+|\w+)\s*\((.*?)\);',nettext,re.S):
 ports={k:m.norm(v) for k,v in re.findall(r'\.(\w+)\((.*?)\)',hit[3],re.S)}
 assert set(ports)<={'clkin','clkout','ce'} and {'clkin','clkout'}<=set(ports)
 if 'ce' in ports:assert ports['ce']=="1'b1"
 assert ports['clkout'] not in clock_parent
 clock_parent[ports['clkout']]=ports['clkin']
def clock_root(sig):
 seen=set()
 while sig in clock_parent:
  assert sig not in seen;seen.add(sig);sig=clock_parent[sig]
 return sig
for c in cs:
 if 'clk' in c['ports']:
  c['physical_clock']=c['ports']['clk'];c['ports']['clk']=clock_root(c['ports']['clk'])
by={c['name']:c for c in cs};names=set(re.findall(r'^cell=(.*?) async_reg=(?:1|true)\b',a.inventory.read_text(),re.M))
drivers={}
for c in cs:
 for q in ('oqa','oqb'):
  if q in c['ports'] and c['params'].get('OQ'+q[-1].upper()+'MUX')=='Q'+q[-1].upper():drivers.setdefault(c['ports'][q],[]).append((c,q))
fifo='\\u_cam_video_source/u_mipi_csi_rx/u_csi_rx_vid2stream/hs_data_fifo/'
det='\\u_cam_video_source/u_mipi_csi_rx/u_csi_rx_phy/u_csi_rx_clock_det/'
groups=[('camera_rdgray',fifo+'rd_to_wr_cross_inst/','primary_addr_gray_reg','sync_r1','primary_addr_gray_sync',13),('camera_wrgray',fifo+'wr_to_rd_cross_inst/','primary_addr_gray_reg','sync_r1','primary_addr_gray_sync',13),('camera_presence_gray',det,'source_gray','gray_s1','gray_s2',6)]
paths=[]
for bus,base,source,first,second,count in groups:
 for bit in range(count):
  pair=m.check_pair(cs,names,base+f'{first}[{bit}]',base+f'{second}[{bit}]')
  sink=by[pair['first_cell']];actual=sink['ports'][pair['first_D']];origin=base+f'{source}[{bit}]'
  allowed=[origin]
  if bus=='camera_presence_gray' and bit==5:allowed.append(base+'source_count[5]')
  assert actual in allowed,(bus,bit,'Unexpected Gray source or combinational entry',actual)
  ds=drivers.get(actual,[]);assert len(ds)==1
  src,q=ds[0];lane=q[-1].upper();params=src['params']
  assert params['LATCHMODE']=='DFF' and params['CLKMUX']=='SIG' and params['CE'+lane+'MUX']=='1'
  assert params['REG'+lane+'_REGSET_ASYNC']=='RESET'
  second_cell=by[pair['second_cell']]
  assert sink['ports']['asr']==second_cell['ports']['asr'] and sink['params']['ASRMUX']==second_cell['params']['ASRMUX']
  assert src['ports']['clk']!=pair['clock'],'Expected asynchronous boundary'
  paths.append(dict(bus=bus,bit=bit,source_signal=actual,source_pin=src['name']+'.'+q,source_timing_start=src['name']+'.clk',source_clock_root=src['ports']['clk'],sink_clock_root=pair['clock'],sink_pin=pair['first_cell']+'.'+pair['first_D'],sync_pair=pair))
assert len(paths)==32
clocks={bus:{(p['source_clock_root'],p['sink_clock_root']) for p in paths if p['bus']==bus} for bus,*_ in groups}
assert all(len(c)==1 for c in clocks.values())
assert clocks['camera_rdgray']=={(dst,src) for src,dst in clocks['camera_wrgray']}
# Reset pairs use active-high asynchronous preset, unlike data synchronizers.
resets=[]
for domain in ('w','r'):
 first=fifo+f'asy_{domain}_rst0';second=fifo+f'asy_{domain}_rst1'
 # RTL assigns wr_rst/rd_rst directly to these ERAM reset inputs; TD may
 # retain the downstream wire name on the very same register Q.
 if second not in drivers:second=fifo+'ram_inst/rst'+('a' if domain=='w' else 'b')
 da=drivers.get(first,[]);dz=drivers.get(second,[]);assert len(da)==len(dz)==1
 ca,qa=da[0];cz,qz=dz[0];d=cz['params']['REG'+qz[-1].upper()+'_SD'].lower()
 assert cz['ports'][d]==first
 assert {(c['name'],pin) for c,pin in m.uses(cs,first)}=={(ca['name'],qa),(cz['name'],d)}
 for c,q in (da[0],dz[0]):
  z=q[-1].upper();assert c['name'] in names and c['params']['LATCHMODE']=='DFF'
  assert c['params']['CE'+z+'MUX']=='1' and c['params']['REG'+z+'_REGSET_ASYNC']=='SET'
  assert c['params']['ASRMUX']=='SIG' and c['params']['CLKMUX']=='SIG'
 assert ca['ports'][ca['params']['REG'+qa[-1].upper()+'_SD'].lower()]=="1'b0"
 assert ca['ports']['clk']==cz['ports']['clk'] and ca['ports']['asr']==cz['ports']['asr']
 resets.append(dict(first_cell=ca['name'],second_cell=cz['name'],domain=domain))
commands=[]
for bus,*_ in groups:
 selected=[p for p in paths if p['bus']==bus]
 expression=lambda values:'[get_pins -filter {'+' || '.join('NAME == '+v for v in sorted(set(values)))+'}]'
 commands.append('set_path_skew -from '+expression(p['source_timing_start'] for p in selected)+' -to '+expression(p['sink_pin'] for p in selected)+' 4.000')
a.out.mkdir(exist_ok=False,parents=True)
(a.out/'gray_skew.sdc').write_text('\n'.join(commands)+'\n')
result=dict(status='IDENTIFIED_32_CAMERA_GRAY_ENTRY_PATHS_REQUIRE_ROUTED_SKEW_REPORT',paths=paths,reset_pairs=resets,full_CDC_accepted=False,references=[dict(path=str(f),sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in (Path(__file__),a.netlist,a.inventory,a.fifo_rtl,a.detector_rtl)])
(a.out/'paths.json').write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
