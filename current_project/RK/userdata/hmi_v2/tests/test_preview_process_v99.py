from types import SimpleNamespace
import pytest
from console.process_preview import ProcessPreview,capture,start_worker


def test_worker_is_spawned_once_and_pending_calls_are_coalesced(monkeypatch,tmp_path):
    submitted=[];options={};stopped=[]
    future=SimpleNamespace(done=lambda:False,result=lambda timeout:{'model_image':b'jpeg','planes':[]})
    def pool(**kw):
        options.update(kw)
        return SimpleNamespace(submit=lambda *args:submitted.append(args) or future,shutdown=lambda **args:stopped.append(args))
    monkeypatch.setattr('console.process_preview.ProcessPoolExecutor',pool)
    p=ProcessPreview(tmp_path,[7])
    try:
        assert p.capture_packet({'frame':1},{})[:4]==b'HBP1'
        assert p.capture_packet({'frame':2},{})[:4]==b'HBP1'
        assert len(submitted)==1 and submitted[0]==(capture,{'frame':1},{})
        assert options['max_workers']==1 and options['mp_context'].get_start_method()=='spawn'
        assert options['initializer'] is start_worker and options['initargs']==(str(tmp_path),[7])
    finally:p.close()
    assert stopped==[{'wait':True,'cancel_futures':True}]


def test_failed_capture_is_reported_and_following_request_can_run(monkeypatch,tmp_path):
    count=[0]
    def result(timeout):
        count[0]+=1
        if count[0]==1:raise ValueError('等待新的 FPGA 模型图像')
        return {'ok':True}
    future=SimpleNamespace(done=lambda:True,result=result)
    monkeypatch.setattr('console.process_preview.ProcessPoolExecutor',lambda **kw:SimpleNamespace(submit=lambda *a:future,shutdown=lambda **kw:None))
    p=ProcessPreview(tmp_path)
    try:
        with pytest.raises(ValueError):p._dispatch({},{})
        assert p._dispatch({},{})=={'ok':True}
    finally:p.close()


@pytest.mark.parametrize('cpus',[[],[8],[-1],[True],[7,7],'7'])
def test_invalid_configuration_cannot_spawn(tmp_path,cpus):
    with pytest.raises(ValueError,match='affinity'):ProcessPreview(tmp_path,cpus)
