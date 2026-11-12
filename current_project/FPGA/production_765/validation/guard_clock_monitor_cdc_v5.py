"""Approve only six new private synchronizers and their precise async entry pins.

Counter ASR must come from the local second release FF. The old real failed
implementation is rejected before any Tcl is emitted. Never cut a clock group,
the second-stage data pin, counter reset, FIFO, held bundle or camera path.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import re
from pathlib import Path

NAMES=('ui_release','hs_release','ui_sample','hs_sample','lock_sample','reset_sample')
def ref(p):return dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def first_entry(name,p,cells,byname):
 c=byname[p['first_cell']];pin=p['first_D']
 if pin in c['ports']:
  assert pin not in ('asr','clk')
  return pin,None
 # TD may absorb ui_reset = ~reset_release[2] into the first sampling FF.
 # PH1 LSLICE LUT5A_SD1 selects E from IE/IMF. Admit only this unary NOT,
 # with no other LUT output or FF lane consuming the waived input.
 assert name=='reset_sample' and pin=='lut5a',(name,'Unsupported internal FF input')
 cp=c['params'];ports=c['ports']
 assert cp.get('LUT5A')=='(~E)' and cp.get('LUT5A_SD1')=='IMF'
 assert cp.get('LUTMODE')=='DLUT5' and cp.get('OFA_SD')=='LUT5A'
 assert set(ports)=={'asr','clk','imf','oqa'} and p['first_Q']=='oqa'
 assert 'LUT5B' not in cp and cp.get('REGA_SD')=='LUT5A'
 assert ports['imf']=='\\u_twin_dsi/reset_release[2]'
 ds=[(x,q) for x in cells for q in ('oqa','oqb') if x['ports'].get(q)==ports['imf']]
 assert len(ds)==1,'Inverted reset source lacks a unique registered driver'
 source,q=ds[0];lane=q[-1].upper();sp=source['params']
 assert sp['LATCHMODE']=='DFF' and sp['CLKMUX']=='SIG' and sp['OQ'+lane+'MUX']=='Q'+lane
 assert sp['CE'+lane+'MUX']=='1' and sp['REG'+lane+'_REGSET_ASYNC']=='RESET'
 assert source['ports']['clk']=='\\u_twin_dsi/u_pack/I_clk'
 assert source['ports'][sp['REG'+lane+'_SD'].lower()]=='\\u_twin_dsi/reset_release[1]'
 return 'imf',dict(cell=c['name'],input_pin='imf',function='NOT E',source=ports['imf'],source_cell=source['name'],source_Q=q,scope='Only the first reset_sample FF; private next stage remains timed')

def reset_driver(cells,net):
 """Accept only direct, ungated, asynchronously reset clones of one DFF.

 GSR=ENABLE and TESTMODE=OFF are verified defaults in TD 6.2.2.200067
 sim_release/ph1/ph1_phy_lslice.v lines 214 and 230. No name-pattern
 equivalence, LUT equivalence or clock/reset exception is inferred here.
 """
 drivers=[(c,q) for c in cells for q in ('oqa','oqb') if c['ports'].get(q)==net]
 assert len(drivers)==1,(net,'reset has no unique direct FF driver')
 c,q=drivers[0];p=c['params'];v=c['ports'];lane=q[-1].upper()
 assert c['kind']=='PH1_PHY_LSLICE' and p.get('LATCHMODE')=='DFF'
 assert p.get('CLKMUX')=='SIG' and p.get('CE'+lane+'MUX')=='1'
 assert p.get('OQ'+lane+'MUX')=='Q'+lane and p.get('REG'+lane+'_SD')=='IM'+lane
 assert p.get('SSRMUX')=='0' and p.get('REG'+lane+'_REGSET_ASYNC')=='RESET'
 assert p.get('ASRMUX') in ('SIG','INV') and p.get('TESTMODE','OFF')=='OFF'
 signature=dict(data=v['im'+lane.lower()],clock=v['clk'],reset=v['asr'],polarity=p['ASRMUX'],
                gsr=p.get('GSR','ENABLE'),reset_value='RESET',clock_polarity='SIG',enable='1',sync_reset='0')
 return dict(net=net,cell=c['name'],lane=lane,signature=signature)

def review(m,cells,async_names):
 byname={c['name']:c for c in cells};pairs={}
 for name in NAMES:
  base='\\u_dsi_clock_control/'+name
  pairs[name]=m.check_pair(cells,async_names,base+'[0]',base+'[1]')
 # Verify reset of all sixteen actual counter FFs, not only the RTL text.
 counters=[]
 for domain in ('ui','hs'):
  release=pairs[domain+'_release']
  for bit in range(8):
   signal=f'\\u_dsi_clock_control/{domain}_div[{bit}]'
   ds=[(c,pin) for c in cells for pin in ('oqa','oqb') if c['ports'].get(pin)==signal]
   assert len(ds)==1,(signal,'No unique counter FF')
   c,pin=ds[0];lane=pin[-1].upper();p=c['params']
   assert p['LATCHMODE']=='DFF' and p['OQ'+lane+'MUX']=='Q'+lane and p['CE'+lane+'MUX']=='1'
   assert p['REG'+lane+'_REGSET_ASYNC']=='RESET' and p['ASRMUX']=='INV'
   assert c['ports']['asr']==release['second'],(signal,'Counter still has raw/global asynchronous reset')
   assert c['ports']['clk']==release['clock'],(signal,'Counter release clock differs')
   counters.append(dict(signal=signal,cell=c['name'],Q=pin,reset=c['ports']['asr'],clock=c['ports']['clk']))
 targets=[];inverters=[];all_second_D={(p['second_cell'],p['second_D']) for p in pairs.values()}
 for name,p in pairs.items():
  if name.endswith('_release'):
   # Both synchronizer FFs use raw asynchronous assertion; their Q0->D1
   # path remains timed. A packed pair may share one physical ASR pin.
   for key in ('first_cell','second_cell'):
    c=byname[p[key]];assert c['params']['ASRMUX']=='INV' and c['ports'].get('asr')
    targets.append((c['name'],'asr','raw_reset_assertion_into_two_stage_local_release'))
  else:
   c=byname[p['first_cell']];pin,inverter=first_entry(name,p,cells,byname)
   if inverter:inverters.append(inverter)
   assert (c['name'],pin) not in all_second_D,'Cannot cut second stage data'
   if name in ('ui_sample','hs_sample'):
    assert c['ports'][pin]=='\\u_dsi_clock_control/'+name[:2]+'_div[7]'
   targets.append((c['name'],pin,'single_bit_async_source_into_private_first_D'))
 targets=sorted(set(targets))
 assert 6<=len(targets)<=8 and all(row[0].startswith('u_dsi_clock_control/') for row in targets)
 # Raw reset at either release stage must be the same selected user reset.
 raw_resets={byname[pairs[d+'_release'][k]]['ports']['asr'] for d in ('ui','hs') for k in ('first_cell','second_cell')}
 bar_resets={byname[pairs[n]['first_cell']]['ports']['asr'] for n in ('ui_sample','hs_sample','lock_sample','reset_sample')}
 assert raw_resets and bar_resets
 reset_equivalence=[]
 if len(raw_resets)!=1 or raw_resets!=bar_resets:
  reset_equivalence=[reset_driver(cells,n) for n in sorted(raw_resets|bar_resets)]
  assert all(r['signature']==reset_equivalence[0]['signature'] for r in reset_equivalence),'Reset driver clones are not structurally equivalent'
 return dict(pairs=pairs,counters=counters,targets=targets,raw_reset_net=sorted(raw_resets)[0],reset_driver_equivalence=reset_equivalence,verified_first_stage_inverters=inverters)
def main():
 ap=argparse.ArgumentParser()
 for name in ('parser','netlist','async-inventory','out'):ap.add_argument('--'+name,required=True,type=Path)
 a=ap.parse_args();assert not a.out.exists();a.out.mkdir()
 sp=importlib.util.spec_from_file_location('physical_parser',a.parser);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
 cells=m.parse_cells(a.netlist.read_text());async_names=set(re.findall(r'^cell=(.*?) async_reg=(?:1|true)\b',a.async_inventory.read_text(),re.M))
 try:v=review(m,cells,async_names)
 except AssertionError as e:
  result=dict(status='REJECT_MONITOR_COUNTER_RESET_OR_PRIVATE_PAIR_STRUCTURE',reason=str(e),constraints_emitted=False,
              references=[ref(p) for p in (Path(__file__),a.parser,a.netlist,a.async_inventory)])
  (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(result['status'],str(e),flush=True);raise SystemExit(2)
 # Same verifier rejects both a raw counter reset and a first-stage user.
 bad=copy.deepcopy(cells);c=next(c for c in bad if c['name']==v['counters'][0]['cell']);c['ports']['asr']=v['raw_reset_net']
 try:review(m,bad,async_names)
 except AssertionError:pass
 else:raise AssertionError('Raw-counter-reset mutation accepted')
 bad=copy.deepcopy(cells);bad[0]['ports']['illegal_monitor_first_user']=v['pairs']['hs_sample']['first']
 try:review(m,bad,async_names)
 except AssertionError:pass
 else:raise AssertionError('First-stage user mutation accepted')
 # Duplicate reset names must never hide altered D, clock, or reset polarity.
 for item in v['reset_driver_equivalence'][1:]:
  for field in ('data','clock','polarity'):
   bad=[dict(c,params=dict(c['params']),ports=dict(c['ports'])) if c['name']==item['cell'] else c for c in cells]
   cell=next(c for c in bad if c['name']==item['cell'])
   if field=='polarity':cell['params']['ASRMUX']='SIG' if cell['params']['ASRMUX']=='INV' else 'INV'
   else:cell['ports']['im'+item['lane'].lower() if field=='data' else 'clk']='MUTATED_RESET_CLONE_INPUT'
   try:review(m,bad,async_names)
   except AssertionError:pass
   else:raise AssertionError('Non-equivalent reset clone accepted: '+field)
 tcl=r'''# Generated only after actual source-role/private-Q/reset verification.
proc clock_monitor_exact_pin {cell_name pin_name} {
 set cs [get_cells -filter [format {NAME == %s} $cell_name] -verbose]
 if {[llength $cs]!=1} {error "Monitor cell disappeared: $cell_name"}
 set wanted "$cell_name.$pin_name";set found {}
 foreach p [get_pins -of $cs] {
  if {[get_property NAME $p] eq $wanted} {lappend found $p}
 }
 if {[llength $found]!=1} {error "Monitor exact pin missing/ambiguous: $wanted"}
 return $found
}
set clock_monitor_target_names {}
'''
 for cell,pin,role in v['targets']:
  tcl+='set clock_monitor_exact [clock_monitor_exact_pin {'+cell+'} {'+pin+'}]\n'
  tcl+='set_false_path -to $clock_monitor_exact\n'
  tcl+='lappend clock_monitor_target_names {'+cell+'.'+pin+'}\n'
 tcl+='set f [open clock_monitor_constraints_applied.txt w];foreach n $clock_monitor_target_names {puts $f $n};close $f\n'
 tcl+='puts "EXACT_NEW_MONITOR_ASYNC_ENTRY_PINS=[llength $clock_monitor_target_names]"\n'
 (a.out/'approved_monitor_constraints.tcl').write_text(tcl,encoding='utf8')
 names=[c+'.'+p for c,p,_ in v['targets']]
 (a.out/'approved_monitor_entry.sdc').write_text(''.join('set_false_path -to [get_pins -filter {NAME == '+n+'}]\n' for n in names),encoding='utf8')
 (a.out/'approved_monitor_pin_names.txt').write_text('\n'.join(names)+'\n',encoding='utf8')
 result=dict(status='PASS_ONLY_NEW_PRIVATE_MONITOR_ASYNC_ENTRY_PINS_APPROVED',**v,
             first_stage_user_and_raw_counter_reset_mutations_rejected=True,clock_groups_changed=False,
             altered_reset_clone_data_clock_polarity_rejected=True,
             camera_or_existing_UI_exceptions_changed=False,second_stage_data_or_counter_reset_cut=False,
             references=[ref(p) for p in (Path(__file__),a.parser,a.netlist,a.async_inventory)])
 (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(result['status'],len(v['targets']),flush=True)
if __name__=='__main__':main()
