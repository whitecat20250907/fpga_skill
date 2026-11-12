from core.snapshot_file import SnapshotReader, SnapshotWriter


def test_observation_rate_keeps_immediate_action_receipt(tmp_path):
    writer=SnapshotWriter(tmp_path/'state.json')
    reader=SnapshotReader(writer.path)
    for t in range(0,100_000_000,1_000_000):
        signature=1 if t>=31_000_000 else 0
        if writer.due(t,signature):writer.publish(t,signature,{'revision':signature,'tick':t})
        data=reader.read()
        assert data['revision']==signature
        assert t-data['tick']<50_000_000
    data['revision']=999
    assert reader.read()['revision']==1


def test_atomic_replace_even_same_size_and_clock_rollback(tmp_path):
    writer=SnapshotWriter(tmp_path/'state.json');reader=SnapshotReader(writer.path)
    writer.publish(20,0,{'x':1});assert reader.read()=={'x':1}
    writer.publish(21,1,{'x':2});assert reader.read()=={'x':2}
    assert writer.due(1,1)
