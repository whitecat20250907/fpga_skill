"""Review actual packed viewer FF/RAM topology, then generate flight queries.

Runs on a finished physical export, never on AL_MAP gate cells. Does not alter
the database, constraints, source RTL, or installed image.
"""
from pathlib import Path
import argparse, importlib.util, re, json, hashlib, collections

ap=argparse.ArgumentParser()
for key in ('build','netlist','attrs','out'):ap.add_argument('--'+key,type=Path,required=True)
ap.add_argument('--collect-terminal-attributes',action='store_true')
a=ap.parse_args()
spec=importlib.util.spec_from_file_location('physical',a.build/'validation/review_combined_structure.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
text=a.netlist.read_text();cells=m.parse_cells(text)
assert not re.search(r'^\s*AL_MAP_SEQ',text,re.M),'Use final packed physical export'
attrs=set(re.findall(r'^cell=(.*?) async_reg=(?:1|true)\b',a.attrs.read_text(),re.M))
base=r'\u_twin_pcie_ui/u_input_viewer/'
rtl=a.build/'uisrc/01_rtl/hmi_input_viewer.v'
declared=m.norm(rtl.read_text())
assert '(*async_reg="true"*)reg[2:0]src_up=0,ui_up=0;' in declared
assert '(*async_reg="true"*)reg[1:0]ack_sync,request_sync,enabled_sync;' in declared
parents={}
for hit in re.finditer(r'\bPH1_PHY_SCLK_V2\s*(?:#\((.*?)\)\s*)?(\\\S+|\w+)\s*\((.*?)\);',text,re.S):
    raw=m.norm(''.join(line.split('//')[0] for line in (hit[1] or '').splitlines()))
    for allowed in ('.GSR("ENABLE")','.BYPASS("ENABLE")','.DELAY(0)','.DELAY(1)'):raw=raw.replace(allowed,'')
    assert not raw.replace(',',''),('Unsupported clock-buffer parameters',hit[2],raw)
    ports={k:m.norm(v) for k,v in re.findall(r'\.(\w+)\((.*?)\)',hit[3],re.S)}
    assert set(ports)<={'clkin','clkout','ce'} and {'clkin','clkout'}<=set(ports)
    assert ports.get('ce',"1'b1")=="1'b1"
    assert ports['clkout'] not in parents
    parents[ports['clkout']]=ports['clkin']
def root(sig):
    seen=set()
    while sig in parents:
        assert sig not in seen;seen.add(sig);sig=parents[sig]
    return sig

qs={};users=collections.defaultdict(set)
for c in cells:
    for pin in ('clk','clka','clkb'):
        if pin in c['ports']:c['ports'][pin]=root(c['ports'][pin])
    for pin,value in c['ports'].items():
        for signal in re.findall(r'\\[^,{}]+',value):users[signal].add((c['name'],pin))
    for q in ('oqa','oqb'):
        lane=q[-1].upper()
        if c['params'].get('OQ'+lane+'MUX')=='Q'+lane and q in c['ports']:
            signal=c['ports'][q]
            assert signal not in qs,('Multiple registered drivers',signal)
            qs[signal]=(c,q)

def ff(signal,clock=None,reset=None,always=False,protected=False):
    assert signal in qs,('No exact registered output',signal)
    c,q=qs[signal];p=c['params'];lane=q[-1].upper()
    assert p['LATCHMODE']=='DFF' and p['CLKMUX']=='SIG' and p['SSRMUX']=='0'
    assert p['REG'+lane+'_REGSET_ASYNC']=='RESET' and p['ASRMUX']=='INV'
    if clock is not None:assert c['ports']['clk']==clock
    if reset is not None:assert c['ports']['asr']==reset
    if always:assert p['CE'+lane+'MUX']=='1'
    if protected:assert c['name'] in attrs,('Missing physical ASYNC_REG',signal,c['name'])
    dp=p['REG'+lane+'_SD'].lower()
    # A normal data FF may take its packed LUT output internally. Handshake
    # stages below still require an actual external D net/private Q link.
    return c,q,dp,c['ports'].get(dp)

bar=ff(base+'src_up[0]')[0]['ports']['clk']
ui=ff(base+'ui_up[0]')[0]['ports']['clk']
assert bar!=ui
chains=[];declared_cells=set();missing_terminal=[]
for name,count,clock,reset,source in [
    ('src_up',3,bar,None,"1'b1"),('ui_up',3,ui,None,"1'b1"),
    ('ack_sync',2,bar,base+'src_up[2]',base+'ack'),
    ('request_sync',2,ui,base+'ui_up[2]',base+'completed[0]'),
    ('enabled_sync',2,ui,base+'ui_up[2]',None)]:
    seq=[ff(base+name+f'[{i}]',clock,reset,True,not(a.collect_terminal_attributes and name in ('src_up','ui_up') and i==2)) for i in range(count)]
    declared_cells.update(c['name'] for c,q,dp,d in seq)
    missing_terminal.extend(c['name'] for c,q,dp,d in seq if c['name'] not in attrs)
    assert len({c['ports']['asr'] for c,q,dp,d in seq})==1
    if source is not None:assert seq[0][3]==source,(name,seq[0][3],source)
    for i in range(count-1):
        c,q,dp,d=seq[i];n,nq,ndp,nd=seq[i+1];signal=base+name+f'[{i}]'
        assert nd==signal
        assert users[signal]=={(c['name'],q),(n['name'],ndp)},(signal,users[signal])
    chains.append(dict(name=name,stages=count,clock=clock,reset=seq[0][0]['ports']['asr'],first_D=seq[0][0]['name']+'.'+seq[0][2],first_input=seq[0][3],cells=[c['name'] for c,q,dp,d in seq]))

ram=[c for c in cells if c['kind']=='PH1_PHY_ERAM' and '/u_input_viewer/' in c['name']]
assert len(ram)==16
covered=[];ram_clocks=[]
for c in ram:
    p,t=c['params'],c['ports']
    for key,value in dict(MODE='DP20K',DATA_WIDTH_A='2',DATA_WIDTH_B='2',REGMODE_A='NOREG',REGMODE_B='NOREG',CLKAMUX='SIG',CLKBMUX='SIG',RSTAMUX='0',RSTBMUX='0',WEAMUX='1',WEBMUX='0',CSA0='1',CSA1='1',CSA2='SIG',CSB0='1',CSB1='1',CSB2='1').items():assert p[key]==value,(c['name'],key)
    assert t['clka']==bar and t['clkb']==ui
    match=re.search(re.escape(base)+r'lane_pixels\[(\d+):(\d+)\]\}',t['dob']);assert match
    covered.extend(range(int(match[2]),int(match[1])+1))
    ram_clocks.append(dict(cell=c['name'],source_clock=t['clka'],destination_clock=t['clkb']))
assert sorted(covered)==list(range(32))

source=[];sinks=[]
held_nets={base+'write_bank',base+'held_mode[0]',base+'held_mode[1]'}
direct_captures={}
for signal,(c,q) in qs.items():
    if c['ports'].get('clk')==ui and c['ports'].get('asr')==base+'ui_up[2]':
        lane=q[-1].upper();dp=c['params'].get('REG'+lane+'_SD','').lower()
        if c['ports'].get(dp) in held_nets:direct_captures[signal]=c['ports'][dp]
for signal in qs:
    if re.fullmatch(re.escape(base)+r'(write_bank|held_mode\[\d+\])',signal):
        c,q,dp,d=ff(signal,bar,base+'src_up[2]')
        source.append(dict(signal=signal,cell=c['name'],q=q,clock_pin=c['name']+'.clk'))
    if re.fullmatch(re.escape(base)+r'(read_addr\[12\]|front_bank|front_mode\[\d+\]|front_width\[\d+\]|front_height\[\d+\])',signal) or signal in direct_captures:
        c,q,dp,d=ff(signal,ui,base+'ui_up[2]')
        sinks.append(dict(signal=signal,cell=c['name'],q=q,data_select=dp,data_pin=c['name']+'.'+dp if dp in c['ports'] else None,clock_pin=c['name']+'.clk'))
assert {v['signal'] for v in source}=={base+'write_bank',base+'held_mode[0]',base+'held_mode[1]'}
assert set(direct_captures.values())==held_nets
for sink,source_net in direct_captures.items():
    assert ff(sink,ui,base+'ui_up[2]')[3]==source_net,(sink,'actual bank/mode capture')
assert set(direct_captures)<={v['signal'] for v in sinks}
for cell in ram:
    bank=cell['ports']['addrb'].lstrip('{').split(',')[0]
    assert direct_captures.get(bank)==base+'write_bank',('Read bank is not captured from held write bank',cell['name'],bank)

a.out.mkdir(exist_ok=False,parents=True)
starts=sorted({v['clock_pin'] for v in source});dest=sinks[0]['clock_pin']
queries=['set starts [get_pins -filter {'+' || '.join('NAME == '+x for x in starts)+'}]',
    f'set dstpins [get_pins -filter {{NAME == {dest}}}]',
    f'if {{[llength $starts]!={len(starts)} || [llength $dstpins]!=1}} {{error {{Missing viewer held-data physical pins}}}}',
    'set dstclock [get_clocks -of $dstpins]',
    'if {[llength $dstclock]!=1} {error {Ambiguous viewer destination clock}}',
    'report_timing_path -from $starts -to $dstclock -ep_num 4096 -path_num 1 -file ${corner}_viewer_held.rpt']
(a.out/'queries.tcl').write_text('\n'.join(queries)+'\n')
(a.out/'declared_cells.tcl').write_text('set viewer_declared_async_cells [list '+' '.join('{'+name+'}' for name in sorted(declared_cells))+']\n')
result=dict(status='PENDING_DECLARED_TERMINAL_ATTRIBUTES' if missing_terminal else 'PASS_PACKED_VIEWER_STRUCTURE_PENDING_NATIVE_FLIGHT',missing_terminal_attributes=missing_terminal,chains=chains,RAMs=ram_clocks,held_sources=source,held_sinks=sinks,direct_captures=direct_captures,clock_buffer_parents=parents,full_CDC_accepted=False,hardware_changed=False,protocol='held_mode is latched at SOF; request toggles at validated EOF. Bank/metadata stay held until vblank ack crosses back. Use conservative two destination clock periods as flight bound.',references=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (a.netlist,a.attrs,rtl,Path(__file__))])
(a.out/'structure.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],len(chains),'chains;',len(source),'held source bits;',len(sinks),'destination FF lanes')
