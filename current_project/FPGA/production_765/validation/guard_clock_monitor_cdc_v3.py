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
 targets=[];all_second_D={(p['second_cell'],p['second_D']) for p in pairs.values()}
 for name,p in pairs.items():
  if name.endswith('_release'):
   # Both synchronizer FFs use raw asynchronous assertion; their Q0->D1
   # path remains timed. A packed pair may share one physical ASR pin.
   for key in ('first_cell','second_cell'):
    c=byname[p[key]];assert c['params']['ASRMUX']=='INV' and c['ports'].get('asr')
    targets.append((c['name'],'asr','raw_reset_assertion_into_two_stage_local_release'))
  else:
   c=byname[p['first_cell']];pin=p['first_D'];assert pin in c['ports'] and pin not in ('asr','clk')
   assert (c['name'],pin) not in all_second_D,'Cannot cut second stage data'
   if name in ('ui_sample','hs_sample'):
    assert c['ports'][pin]=='\\u_dsi_clock_control/'+name[:2]+'_div[7]'
   targets.append((c['name'],pin,'single_bit_async_source_into_private_first_D'))
 targets=sorted(set(targets))
 assert 6<=len(targets)<=8 and all(row[0].startswith('u_dsi_clock_control/') for row in targets)
 # Raw reset at either release stage must be the same selected user reset.
 raw_resets={byname[pairs[d+'_release'][k]]['ports']['asr'] for d in ('ui','hs') for k in ('first_cell','second_cell')}
 bar_resets={byname[pairs[n]['first_cell']]['ports']['asr'] for n in ('ui_sample','hs_sample','lock_sample','reset_sample')}
 assert len(raw_resets)==1 and raw_resets==bar_resets
 return dict(pairs=pairs,counters=counters,targets=targets,raw_reset_net=next(iter(raw_resets)))
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
             camera_or_existing_UI_exceptions_changed=False,second_stage_data_or_counter_reset_cut=False,
             references=[ref(p) for p in (Path(__file__),a.parser,a.netlist,a.async_inventory)])
 (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(result['status'],len(v['targets']),flush=True)
if __name__=='__main__':main()
