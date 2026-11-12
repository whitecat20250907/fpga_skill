from types import SimpleNamespace
from vision.visible_preview import VisiblePreview


def test_hidden_display_reads_nothing_then_resumes_fresh():
    calls=[];visible=[True]
    selector=SimpleNamespace(rgb=object(),metadata={'old':True},next_poll=1000)
    def select(model,capture,stamp):
        calls.append((model,capture,stamp));return model,'current'
    selector.select=select
    wrapped=VisiblePreview(selector,lambda:visible[0])
    assert wrapped.select('model','capture',1)==('model','current')
    visible[0]=False
    for stamp in range(2,602):assert wrapped.select('model','capture',stamp)==(None,'')
    assert len(calls)==1 and selector.rgb is None and selector.metadata is None
    visible[0]=True
    assert wrapped.select('next','capture',602)==('next','current')
    assert selector.next_poll==0 and calls[-1]==('next','capture',602)
