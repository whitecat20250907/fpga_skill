"""Identify the 52 actual HFT ingress Gray entry paths; no timing waivers."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,re
ap=argparse.ArgumentParser()
for name in ('parser','netlist','inventory','ingress-rtl','out'):ap.add_argument('--'+name,type=Path,required=True)
a=ap.parse_args();spec=importlib.util.spec_from_file_location('physical107',a.parser);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
cells=m.parse_cells(a.netlist.read_text());names=set(re.findall(r'^cell=(.*?) async_reg=(?:1|true)\b',a.inventory.read_text(),re.M));byname={c['name']:c for c in cells}
base='\\u_twin_pcie_ui/u_ingress/';paths=[]
rtl=''.join(a.ingress_rtl.read_text().split())
for pointer in ('r','w'):
 assert f'{pointer}bin<=next_{pointer}bin;{pointer}gray<=next_{pointer}bin^(next_{pointer}bin>>1);' in rtl
drivers={}
for c in cells:
 for q in ('oqa','oqb'):
  if q in c['ports']:drivers.setdefault(c['ports'][q],[]).append((c,q))
for source,first,second,count in (('rgray','rgray_w1','rgray_w2',10),('wgray','wgray_r1','wgray_r2',10),('time_gray','time_w1','time_w2',32)):
 for bit in range(count):
  origin=f'{base}{source}[{bit}]';p=m.check_pair(cells,names,f'{base}{first}[{bit}]',f'{base}{second}[{bit}]')
  sink=byname[p['first_cell']];actual=sink['ports'][p['first_D']]
  # The MSB of b^(b>>1) is exactly b[MSB]. TD legally merges these
  # same-clock, identically updated source FFs; lower bits cannot alias.
  alias=f'{base}{source[0]}bin[{bit}]' if source in ('rgray','wgray') and bit==count-1 else origin
  assert actual in (origin,alias),(origin,'CDC entry contains logic or wrong source')
  alias_basis='Gray MSB equals binary MSB; identical RTL update expression verified' if actual!=origin else None
  origin=actual
  ds=drivers.get(origin,[]);assert len(ds)==1,(origin,'No unique registered Gray source')
  c,q=ds[0];lane=q[-1].upper();assert c['params']['LATCHMODE']=='DFF' and c['params']['OQ'+lane+'MUX']=='Q'+lane
  expected_src='\\u_twin_pcie_ui/bar_clk' if source=='wgray' else '\\u_twin_dsi/u_pack/I_clk'
  expected_dst='\\u_twin_dsi/u_pack/I_clk' if source=='wgray' else '\\u_twin_pcie_ui/bar_clk'
  assert c['ports']['clk']==expected_src and p['clock']==expected_dst,(origin,'Changed Gray clock contract')
  paths.append(dict(bus=source,bit=bit,source_signal=origin,source_alias_basis=alias_basis,source_pin=c['name']+'.'+q,source_timing_start=c['name']+'.clk',source_clock=c['ports']['clk'],sink_pin=p['first_cell']+'.'+p['first_D'],sink_clock=p['clock'],sync_pair=p))
assert len(paths)==52
a.out.mkdir(parents=True,exist_ok=True)
tcl='# No constraints or database modifications. Exact physical pin reports only.\n'
for p in paths:
 name=f"{p['bus']}_{p['bit']:02d}.timing"
 # TD sequential timing starts at the source clock pin, not its output Q.
 for label,pin in (('from',p['source_timing_start']),('to',p['sink_pin'])):
  tcl+='set gray107_'+label+' [get_pins -filter {NAME == '+pin+'}]\n'
  tcl+='if {[llength $gray107_'+label+']!=1} {error {Missing exact Gray '+label+' pin}}\n'
  tcl+='puts "GRAY107_'+label.upper()+'=[get_property NAME $gray107_'+label+']"\n'
 tcl+='report_timing_path -from [get_pins -filter {NAME == '+p['source_timing_start']+'}] -to [get_pins -filter {NAME == '+p['sink_pin']+'}] -ep_num 1 -path_num 1 -file {'+(a.out/name).as_posix()+'}\n'
 tcl+='if {![file isfile {'+(a.out/name).as_posix()+'}] || [file size {'+(a.out/name).as_posix()+'}]==0} {error {Missing native timing report '+name+'}}\n'
 tcl+='puts {GRAY107_REPORTED_'+p['bus']+'_'+str(p['bit'])+'}\n'
(a.out/'report_paths.tcl').write_text(tcl,'utf-8')
report=dict(status='IDENTIFIED_52_ENTRY_PATHS_NOT_FLIGHT_OR_SKEW_ACCEPTANCE',paths=paths,
            references=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (Path(__file__),a.parser,a.netlist,a.inventory,a.ingress_rtl)])
(a.out/'paths.json').write_text(json.dumps(report,indent=2),'utf-8')
print('Identified 52 registered Gray source-to-first-stage paths with private second stages')

# Four ns is the fixed contract for these 125 MHz / 50 MHz domains.
# Preserve all original constraints; add only a skew bound on these paths.
commands=[]
for bus in ('rgray','wgray','time_gray'):
 selected=[p for p in paths if p['bus']==bus]
 starts=sorted({p['source_timing_start'] for p in selected});ends=sorted({p['sink_pin'] for p in selected})
 expression=lambda values:'[get_pins -filter {'+' || '.join('NAME == '+v for v in values)+'}]'
 commands.append('set_path_skew -from '+expression(starts)+' -to '+expression(ends)+' 4.000')
(a.out/'gray_skew.sdc').write_text('\n'.join(commands)+'\n','utf-8')
