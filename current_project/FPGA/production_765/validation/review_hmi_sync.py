"""Audit HMI and ingress local release, including every Gray receiver reset."""
import argparse,copy,hashlib,importlib.util,json,re
from pathlib import Path
from review_dsi_release import review as review_dsi_release

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('netlist','async-inventory','out'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--identify',action='store_true',help='Graph-only identification; never an ASYNC acceptance')
    a=p.parse_args();source=Path(__file__).with_name('review_combined_structure.py')
    spec=importlib.util.spec_from_file_location('physical_parser',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    cells=m.parse_cells(a.netlist.read_text());names=set(re.findall(r'^cell=(.*?) async_reg=(?:1|true)\b',a.async_inventory.read_text(),re.M))
    pairs=[];physical_names={c['name'] for c in cells};release={};inputs={}
    csr='\\u_twin_pcie_ui/u_hmi_csr/';ingress='\\u_twin_pcie_ui/u_ingress/'
    chains=[(csr,c) for c in ('req_sync','ack_sync','bar_up','ui_up')]+[(ingress,c) for c in ('w_up','r_up')]
    for prefix,chain in chains:
        base=prefix+chain
        for stage in (0,1):
            first=f'{base}[{stage}]';second=f'{base}[{stage+1}]'
            if prefix==ingress and stage==1:
                # An exported reset port may become the canonical Q net.
                # Derive its FF lane from the private stage-one D connection.
                users=[(c,p) for c,p in m.uses(cells,first) if p not in ('oqa','oqb')]
                assert len(users)==1,(chain,'Non-private release chain')
                c,dp=users[0]
                qs=[q for q in ('oqa','oqb') if c['params'].get('REG'+q[-1].upper()+'_SD','').lower()==dp and q in c['ports']]
                assert len(qs)==1,(chain,'Ambiguous final reset FF lane')
                actual=c['ports'][qs[0]]
                aliases={second,ingress+'writer_rst_n',ingress+'reader_rst_n',ingress+'local_bar_reset_n','\\u_twin_pcie_ui/ingress_bar_rst_n','\\u_twin_pcie_ui/snapshot_rst_n'}
                assert actual in aliases,(chain,'Unexpected reset output identity',actual)
                second=actual;release[chain]=second
            pairs.append(m.check_pair(cells,physical_names if a.identify else names,first,second))
        inputs[base+'[0]']=csr+{'req_sync':'request_toggle','ack_sync':'ack_toggle'}[chain] if chain in ('req_sync','ack_sync') else "1'b1"
    # TD can pack a CSR reset FF into the other lane of an ingress-named
    # physical slice. Instance naming is not ownership. check_pair above
    # proves the exact Q->D nets, DFF lane, enable, reset and same clock.
    by_name={c['name']:c for c in cells}
    for pair in pairs[::2]:
        cell=by_name[pair['first_cell']]
        assert cell['ports'].get(pair['first_D'])==inputs[pair['first']], (pair['first'],'Wrong stage-zero input')
    receiver_pairs=[]
    for first,second,count,domain in (('rgray_w1','rgray_w2',10,'w_up'),('time_w1','time_w2',32,'w_up'),('wgray_r1','wgray_r2',10,'r_up')):
        for bit in range(count):
            receiver_pairs.append((m.check_pair(cells,physical_names if a.identify else names,f'{ingress}{first}[{bit}]',f'{ingress}{second}[{bit}]'),domain))
    for chain,domain in (('ui_up_w','w_up'),('ack_w','w_up'),('request_r','r_up'),('busy_r','r_up')):
        receiver_pairs.append((m.check_pair(cells,physical_names if a.identify else names,f'{ingress}{chain}[0]',f'{ingress}{chain}[1]'),domain))
    for pair,domain in receiver_pairs:
        local_clock=next(p['clock'] for p in pairs if p['first']==ingress+domain+'[1]')
        for key in ('first_cell','second_cell'):
            cell=by_name[pair[key]]
            assert cell['params']['ASRMUX']=='INV' and cell['ports'].get('asr')==release[domain], (pair['first'],'CDC receiver still uses raw/wrong-domain reset')
            assert cell['ports']['clk']==local_clock,(pair['first'],'Wrong receiver reset clock')
    snapshot_lanes=[]
    for signal in ['\\u_twin_pcie_ui/snapshot_select']+[f'\\u_twin_pcie_ui/snapshot_data[{bit}]' for bit in range(32)]:
        drivers=[(c,q) for c in cells for q in ('oqa','oqb') if c['ports'].get(q)==signal]
        assert len(drivers)==1,(signal,'Missing unique snapshot readback FF')
        cell,q=drivers[0]
        assert cell['params']['LATCHMODE']=='DFF' and cell['params']['ASRMUX']=='INV'
        assert cell['ports'].get('asr')==release['w_up'],(signal,'Snapshot still uses raw reset')
        assert cell['ports']['clk']==next(p['clock'] for p in pairs if p['first']==ingress+'w_up[1]')
        snapshot_lanes.append({'signal':signal,'cell':cell['name'],'Q':q})
    dsi_release=review_dsi_release(cells,physical_names if a.identify else names,m)
    pairs.extend(dsi_release['pairs'])
    approved=sorted({p[k] for p in pairs for k in ('first_cell','second_cell')})
    bad=list(cells);bad[0]=copy.deepcopy(bad[0]);bad[0]['ports']['illegal_first_user']=pairs[0]['first']
    try:m.check_pair(bad,physical_names if a.identify else names,pairs[0]['first'],pairs[0]['second'])
    except AssertionError:pass
    else:raise AssertionError('Accepted first-stage fanout counterexample')
    if a.identify:
        a.out.with_suffix('.tcl').write_text('set hmi_declared_async_cells [list '+''.join('{'+n+'} ' for n in approved)+']\n')
        for pair in pairs:pair['both_physical_ASYNC_REG']=None
    result={'status':'IDENTIFIED_GRAPH_ONLY_NOT_ASYNC_ACCEPTANCE' if a.identify else 'PASS','scope':'Actual placed-netlist structure only; excludes full CDC, Gray skew, MTBF and board acceptance',
            'approved_exact_cells':approved,'ownership':'Exact source Q nets and FF lanes, independent of packed slice naming',
            'three_stage_chains':7,'private_edges':14,'pairs':pairs,'receiver_pairs_checked':len(receiver_pairs),'snapshot_lanes':snapshot_lanes,'local_release_nets':release,'dsi_release':dsi_release,'first_stage_fanout_mutation_rejected':True,
            'references':[{'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in (Path(__file__),Path(__file__).with_name('review_dsi_release.py'),source,a.netlist,a.async_inventory)]}
    a.out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(result['status']+': seven three-stage chains, fourteen private edges, 56 locally reset receiver pairs')
if __name__=='__main__':main()
