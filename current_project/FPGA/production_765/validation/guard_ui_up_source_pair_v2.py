"""Approve only the actual source-named private two-FF release crossing.

Emits data for the native attribute hook, never changes a netlist or property.
No transient packed-cell suffix is assumed. A missing/changed graph fails.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import re
from pathlib import Path

def ref(p):return dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--netlist',required=True,type=Path);ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--parser',type=Path,default=Path(__file__).with_name('review_combined_structure.py'));args=ap.parse_args()
    assert not args.out.exists()
    spec=importlib.util.spec_from_file_location('_source_pair_physical_parser',args.parser);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    cells=m.parse_cells(args.netlist.read_text(encoding='utf8'));names={c['name'] for c in cells};assert len(names)==len(cells)
    base='\\u_twin_pcie_ui/u_ingress/'
    pair=m.check_pair(cells,names,base+'ui_up_w[0]',base+'ui_up_w[1]')
    first=next(c for c in cells if c['name']==pair['first_cell'])
    assert first['ports'].get(pair['first_D'])==base+'r_up[2]','Unexpected source of first metastability stage'
    # Ensure the graph validator rejects an added consumer of stage one.
    bad=copy.deepcopy(cells);bad[0]['ports']['illegal_user']=pair['first']
    try:m.check_pair(bad,names,pair['first'],pair['second'])
    except AssertionError:pass
    else:raise AssertionError('Private-Q counterexample accepted')
    pair['both_physical_ASYNC_REG']=None
    pair['ASYNC_REG_scope']='Not checked by this graph-only guard'
    target=sorted({pair['first_cell'],pair['second_cell']})
    assert all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_/\[\]$.-]*',s) for s in target),'Unsafe native object identifier'
    # All names above were used only to validate graph/control; no existing
    # ASYNC_REG inventory was inspected and no ASYNC_REG pass is claimed.
    args.out.mkdir(parents=True)
    (args.out/'approved_cells.tcl').write_text('set candidate_source_pair_cells [list '+' '.join('{'+s+'}' for s in target)+']\n',encoding='utf8')
    v=dict(status='APPROVED_EXACT_SOURCE_UI_UP_PRIVATE_FF_GRAPH_ONLY',actual_cells=target,pair=pair,
           first_input_is_source_r_up2=True,private_Q_counterexample_rejected=True,ASYNC_REG_checked=False,properties_changed=False,
           references=[ref(p) for p in (Path(__file__),args.parser,args.netlist)])
    (args.out/'result.json').write_text(json.dumps(v,indent=2)+'\n',encoding='utf8');print(v['status'],flush=True)

if __name__=='__main__':main()
