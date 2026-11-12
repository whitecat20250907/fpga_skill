from copy import deepcopy
import errno
import pytest
from adapters.demo import DemoAdapter
from adapters.medical_workflow import stage
from tests.test_medical_workflow_v89 import activate

@pytest.mark.parametrize('page',[0,3])
@pytest.mark.parametrize('case',['case_00000','case_00001','case_00002'])
def test_rotate_opens_selected_volume_and_undo_restores_previous_view(page,case):
    d=DemoAdapter();activate(d,'case:'+case);stage(d,page)
    before=deepcopy(d.state)
    d.on_action({'id':'rotate-maintenance','name':'demo.rotate','args':{'control_hand':{'track_id':1,'side':'Right'}}})
    assert d.state['page']==2 and d.state['case_id']==case and d.state['rotating']
    now=d.rotation_tick+100_000_000
    d.tick(now,{'context':'DEMO','health':{},'src_ns':now,'hand_src_ns':now,'hand_observations':[{'track_id':1,'side':'Right','gesture':'Closed_Fist','score':.9}]})
    assert d.state['orbit'][1]>before['orbit'][1]
    d.on_action({'name':'demo.undo','args':{'undo_id':'rotate-maintenance'}})
    for key,value in before.items():
        if key not in ('revision','rotation_notice'):assert d.state[key]==value,key

def test_rotate_again_stops_without_page_change():
    d=DemoAdapter()
    d.on_action({'name':'demo.rotate','args':{}})
    assert d.state['rotating'] and d.state['page']==2
    d.on_action({'name':'demo.rotate','args':{}})
    assert not d.state['rotating'] and d.state['page']==2

@pytest.mark.parametrize('error,status',[(errno.ENOSPC,507),(errno.EDQUOT,507),(errno.EIO,500)])
def test_console_failed_mapping_write_reports_storage_error_without_queuing(tmp_path,monkeypatch,error,status):
    import ast,io,json,threading
    from pathlib import Path
    from queue import Queue
    import console.server as server
    from core.bindings import defaults
    source=Path(server.__file__).read_text('utf8')
    handler=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.ClassDef) and n.name=='Handler')
    commands=Queue();token='local-unit-test-token'
    env=dict(vars(server),ROOT=tmp_path,token=token,lock=threading.Lock(),commands=commands)
    exec(compile(ast.Module(body=[handler],type_ignores=[]),'actual_console_handler','exec'),env)
    obj=object.__new__(env['Handler']);data=json.dumps(defaults({})).encode()
    obj.path='/api/bindings';obj.headers={'Authorization':'Bearer '+token,'Content-Length':str(len(data))};obj.rfile=io.BytesIO(data)
    replies=[];obj.reply=lambda code,body:replies.append((code,body))
    def fail(*a,**k):raise OSError(error,'simulated filesystem failure')
    monkeypatch.setattr(Path,'write_text',fail)
    obj.do_POST()
    assert replies[0][0]==status and '未保存' in replies[0][1]['error']
    assert commands.empty()
