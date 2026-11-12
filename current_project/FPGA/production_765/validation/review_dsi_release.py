"""Physical DSI reset release chain. Does not certify PHY/LP recovery timing."""

def review(cells, async_names, parser):
    prefix='\\u_twin_dsi/'
    pairs=[]
    for i in (0,1):
        pairs.append(parser.check_pair(cells,async_names,
            f'{prefix}reset_release[{i}]',f'{prefix}reset_release[{i+1}]'))
    by_name={c['name']:c for c in cells}
    clocks=set();resets=set();lanes=[]
    for pair in pairs:
        for ck,qk in (('first_cell','first_Q'),('second_cell','second_Q')):
            cell=by_name[pair[ck]];q=pair[qk]
            assert cell['params']['ASRMUX']=='SIG', 'DSI release must assert asynchronously high'
            clocks.add(cell['ports']['clk']);resets.add(cell['ports']['asr'])
            lanes.append((cell['name'],q))
    assert len(set(lanes))==3,'Expected three separate FF lanes'
    assert len(clocks)==1 and len(resets)==1,'Mixed DSI release clock or reset'
    first=by_name[pairs[0]['first_cell']]
    assert first['ports'].get(pairs[0]['first_D'])=="1'b1",'Release entry must shift constant one'
    # Compare with the actual UI-domain config-done receiver, not a clock name.
    done=[c for c in cells if any(c['ports'].get(q)==prefix+'done_ui[1]' for q in ('oqa','oqb'))]
    assert len(done)==1 and done[0]['ports']['clk'] in clocks,'Release is not in UI clock domain'
    assert all(c['name'] in async_names for c in (by_name[n] for n,q in set(lanes)))
    return dict(pairs=pairs,three_ff_lanes=sorted(set(lanes)),clock=next(iter(clocks)),
                asynchronous_assert_net=next(iter(resets)),
                scope='Three local UI-clock release FFs only; output polarity, full reset fanout and related LP/HS recovery remain separate reviews')
