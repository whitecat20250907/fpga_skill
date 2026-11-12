"""Verify actual gate-mapped trace RAM data is driven by the 16 new FFs.

This does not certify their half-cycle STA. It prevents a synthesis/mapping
change from silently restoring the old raw-input-to-ERAM path.
"""
import argparse,hashlib,importlib.util,json,re
from pathlib import Path

def mapped_registers(text):
    cells=[]
    for match in re.finditer(r'^\s*(AL_MAP_SEQ_GSR)\s*#\((.*?)\)\s*(\\\S+|\w+)\s*\((.*?)\);',text,re.S|re.M):
        params=dict(re.findall(r'\.([A-Za-z0-9_]+)\("([^"\n]*)"\)',match[2]))
        ports={k:''.join(v.split()) for k,v in re.findall(r'\.([A-Za-z0-9_]+)\((.*?)\)',match[4],re.S)}
        cells.append(dict(kind=match[1],name=match[3].lstrip('\\'),params=params,ports=ports))
    return cells

def expand(expr,widths):
    if not expr:return []
    if expr.startswith('{') and expr.endswith('}'):
        return [b for part in expr[1:-1].split(',') for b in expand(part,widths)]
    if re.fullmatch(r"\d+'[bhd][0-9a-fxz]+",expr,re.I) or re.fullmatch(r'open_n\d+',expr):return []
    match=re.fullmatch(r'(.*)\[(\d+):(\d+)\]',expr)
    if match:
        hi,lo=int(match[2]),int(match[3]);step=1 if lo>hi else -1
        return [f'{match[1]}[{b}]' for b in range(hi,lo+step,step)]
    if expr in widths:
        hi,lo=widths[expr];step=1 if lo>hi else -1
        return [f'{expr}[{b}]' for b in range(hi,lo+step,step)]
    return [expr]

def inspect(cells,widths):
    memories=[c for c in cells if c['kind']=='PH1_PHY_ERAM' and c['name'].startswith('u_raw_trace/')]
    assert len(memories)==4,'Trace must retain exactly four ERAMs'
    sinks=[]
    for cell in memories:
        for pin in ('dia','dia_extra'):
            for net in expand(cell['ports'].get(pin,''),widths):sinks.append((cell,pin,net))
    expected={f'\\u_raw_trace/trace_data_q[{b}]' for b in range(16)}
    assert len(sinks)==16 and {x[2] for x in sinks}==expected,'RAW_TRACE_PIPELINE_NOT_PRESENT_AT_RAM'
    drivers={}
    for cell in cells:
        for q in ('oqa','oqb','q'):
            net=cell['ports'].get(q)
            if net in expected:drivers.setdefault(net,[]).append((cell,q))
    rows=[]
    for ram,pin,net in sinks:
        assert len(drivers.get(net,[]))==1,(net,'Pipeline data must have one registered driver')
        cell,q=drivers[net][0];lane=q[-1].upper();p=cell['params'];ports=cell['ports']
        if cell['kind']=='AL_MAP_SEQ_GSR':
            assert q=='q' and p['DFFMODE']=='FF' and p['CLKMUX']=='SIG'
            assert p['CEMUX']=='1','Unexpected trace input clock enable'
            d='d'
        else:
            assert cell['kind'] in ('PH1_PHY_LSLICE','PH1_PHY_MSLICE')
            assert p['LATCHMODE']=='DFF' and p['CLKMUX']=='SIG' and p['OQ'+lane+'MUX']=='Q'+lane
            assert p['CE'+lane+'MUX']=='1','Unexpected trace input clock enable'
            d=p['REG'+lane+'_SD'].lower()
        assert ports['clk']==ram['ports']['clka'],'Trace pipeline/RAM clock mismatch'
        assert d in ports,'Missing actual FF data input'
        rows.append(dict(signal=net,driver=cell['name'],Q=q,D=d,input=ports[d],clock=ports['clk'],ram=ram['name'],ram_pin=pin))
    return rows

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--netlist',required=True,type=Path);ap.add_argument('--out',required=True,type=Path);a=ap.parse_args()
    parser=Path(__file__).with_name('review_combined_structure.py')
    spec=importlib.util.spec_from_file_location('physical',parser);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    text=a.netlist.read_text();cells=m.parse_cells(text)+mapped_registers(text)
    widths={name:(int(hi),int(lo)) for hi,lo,name in re.findall(r'\bwire\s+\[(\d+):(\d+)\]\s+(\\\S+|\w+)\s*;',text)}
    rows=inspect(cells,widths)
    result=dict(status='PASS_ACTUAL_16_FF_TRACE_DATA_PIPELINE',rows=rows,full_STA_or_CDC_or_board_accepted=False,references=[dict(path=str(f),sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in (Path(__file__),parser,a.netlist)])
    a.out.write_text(json.dumps(result,indent=2));print(result['status'])
if __name__=='__main__':main()
