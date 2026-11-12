"""Check actual PH1 clock forwarding and raw-trace mapping before placement.

PH1_PHY_PAD has a four-bit doq port even with ODDRMODE=OFF. Its ordinary
unregistered output uses doq[0]; a fictitious scalar 'do' port is not required.
The shipped PH1 simulation model is the primary source for this interface.
"""
import argparse
import collections
import hashlib
import json
import re
from pathlib import Path


def ref(p):
    return dict(path=str(p.resolve()), sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def inspect(text):
    cells=[]
    for m in re.finditer(r'^\s*(PH1_PHY_\w+)\s*(?:#\((.*?)\)\s*)?(\\\S+|\w+)\s*\((.*?)\);',text,re.S|re.M):
        params=dict(re.findall(r'\.(\w+)\(([^()]*)\)',m[2] or ''))
        ports={k:''.join(v.split()) for k,v in re.findall(r'\.(\w+)\(([^()]*)\)',m[4])}
        cells.append(dict(kind=m[1],name=m[3].lstrip('\\'),parameters=params,ports=ports))
    trace=[c for c in cells if c['name'].startswith('u_raw_trace/')]
    erams=[c for c in trace if c['kind']=='PH1_PHY_ERAM']
    forbidden=[c for c in trace if 'RAM' in c['kind'] and c['kind']!='PH1_PHY_ERAM']
    pads=[c for c in cells if c['kind']=='PH1_PHY_PAD']
    camera=[c for c in pads if c['name'].startswith(('mipi_clk_hs_rx_p_','mipi_data_hs_p['))]
    clock=[c for c in pads if c['parameters'].get('LOCATION','').strip('"')=='E16']
    plls=[c for c in cells if c['kind']=='PH1_PHY_PLL' and c['name'].startswith('u_twin_dsi/u_pll/')]
    normal=False;direct=False;source=None
    if len(clock)==len(plls)==1:
        p=clock[0]['parameters'];ports=clock[0]['ports'];v=ports.get('doq','')
        bits=v[1:-1].split(',') if v.startswith('{') and v.endswith('}') else []
        normal=(p.get('ODDRMODE','"OFF"')=='"OFF"' and p.get('DO_DFFMODE','"NONE"')=='"NONE"'
                and p.get('OUTDELMUX','"NODEL"')=='"NODEL"' and len(bits)==4
                and all(re.fullmatch(r'open_n\d+',s) for s in bits[:-1])
                and not any(k in ports for k in ('opclk','osclk','do')))
        root=plls[0]['ports'].get('clkc','')
        outputs=root[1:-1].split(',') if root.startswith('{') and root.endswith('}') else []
        if len(outputs)==8 and len(bits)==4:
            source=bits[-1]
            direct=source==outputs[-4] and source not in ("1'b0","1'b1")
    forwarded=normal and direct and len(pads)==40 and len(camera)==10 and any(c['parameters'].get('LOCATION','').strip('"')=='F16' for c in pads)
    passed=len(erams)==4 and not forbidden and forwarded
    return dict(status='PASS_ACTUAL_GATE_RAW_TRACE_FOUR_ERAM_NO_DISTRIBUTED_MEMORY' if passed else 'REJECT_TRACE_OR_FORWARDED_CLOCK_PAD_MAPPING',
        actual_cell_counts=dict(collections.Counter(c['kind'] for c in trace)),ERAM_cells=erams,forbidden_memory_cells=forbidden,
        forwarded_clock_PAD_no_DDR=forwarded,normal_output_uses_doq_bit0=normal,clock_PAD_directly_same_DSI_PLL_clkc3=direct,
        clock_PAD_source=source,actual_PAD_count=len(pads),camera_PAD_count=len(camera),actual_clock_PAD=clock,DSI_PLL=plls,
        mapping_only=True,primitive_port_or_CDC_or_final_timing_or_board_accepted=False)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--netlist',required=True,type=Path);ap.add_argument('--out',required=True,type=Path);a=ap.parse_args()
    assert not a.out.exists();v=inspect(a.netlist.read_text(encoding='utf8'))
    v.update(source=ref(a.netlist),reviewer=ref(Path(__file__)))
    a.out.mkdir(parents=True);(a.out/'result.json').write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
    print(v['status'],flush=True)
    if not v['forwarded_clock_PAD_no_DDR'] or len(v['ERAM_cells'])!=4 or v['forbidden_memory_cells']:raise SystemExit(2)


if __name__=='__main__':main()
