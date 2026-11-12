"""One case, linked CT/mesh coordinates, explicit observation records."""
import time
from copy import deepcopy
from core.targets import medical_spec,medical_case,medical_rows

def reset(adapter,whole=False):
    s=adapter.state;meta=medical_case(s)
    s.update(zoom=1.,focus=False,part=None,rotation=0,orbit=[0,0,0],axis=1,
             inspection=None,rotating=False,rotation_notice='',window=0,overlay=False)
    if whole or 'crosshair' not in s:
        s.update(crosshair=list(meta['initial_voxel']),plane='axial',suspect_voxel=None,
                 confirmed=False,record=None,reviewed={'ct':False,'volume':False})

def stage(adapter,page):
    s=adapter.state;s['page']=page;s['zoom']=1.;s['focus']=False
    adapter.stop_rotation('');s['inspection']=None
    if page==1:s['reviewed']['ct']=True
    if page==2:s['reviewed']['volume']=True

def apply(adapter,action):
    s=adapter.state;spec=medical_spec();args=action.get('args',{});name=action['name'].split('.')[-1]
    lock=args.get('target_lock') or {};target=lock.get('target') or {}
    if name in ('activate','click','confirm'):
        if name=='activate':target=args.get('medical_target') or {}
        if target.get('page')!=s['page'] or target.get('case_id')!=s['case_id']:
            raise ValueError('病例或视图已切换，请选择当前内容')
        name=target.get('action','').split('.')[-1]
    meta=medical_case(s)
    if name in ('wake','sleep'):s['awake']=name=='wake'
    elif name in ('next','cancel'):
        stage(adapter,(s['page']+(1 if name=='next' else -1))%len(spec['pages']))
    elif name=='reset':reset(adapter)
    elif name=='focus':
        part=target.get('part') or s.get('part')
        if part not in meta['part_voxels']:
            # Focus remains a view operation when no anatomical target exists.
            s['focus']=not s['focus']
        else:
            s['focus']=not s['focus'] if part==s.get('part') else True;s['part']=part
            s['crosshair']=[round(v) for v in meta['part_voxels'][part]]
        s['reviewed']['ct' if s['page']==1 else 'volume']=True
    elif name=='rotate':
        if s['rotating']:adapter.stop_rotation('已停止')
        else:
            # A confirmed rotation is already an explicit navigation intent.
            # Keep the selected case and open its volume from overview/report.
            if s['page']!=2:stage(adapter,2)
            s['rotating']=True;s['rotation']+=1
            adapter.rotation_hand=dict(args['control_hand']) if args.get('control_hand') else None
            adapter.rotation_seen=time.monotonic_ns();adapter.rotation_tick=adapter.rotation_seen
            adapter.palm_since=0;adapter.palm_stamp=adapter.rotation_seen
            s['rotation_notice']='旋转中'
    elif name=='inspect':
        content=target.get('content')
        if content not in {r.get('content') for r in medical_rows(s)}:raise ValueError('当前视图没有该内容')
        if content.startswith('case:'):
            key=content.split(':',1)[1]
            if key not in {c['id'] for c in spec['cases']}:raise ValueError('病例不存在')
            s['case_id']=key;reset(adapter,whole=True);stage(adapter,1)
        elif content.startswith('stage:'):stage(adapter,int(content.split(':')[1]))
        elif content.startswith('review:'):
            s['plane']=content.split(':')[1];stage(adapter,1)
        elif content.startswith('plane:'):
            adapter.stop_rotation('');plane=content.split(':')[1]
            s['zoom']=1.;s['focus']=False;s['plane']=plane;s['reviewed']['ct']=True
        elif content.startswith('locate:'):
            part=content.split(':')[1];s['crosshair']=[round(v) for v in meta['part_voxels'][part]];s['part']=part;s['reviewed']['ct']=True
        elif content=='annotation':s['overlay']=not s['overlay']
        elif content=='mark':
            adapter.stop_rotation('');s['suspect_voxel']=list(s['crosshair']);s['confirmed']=False;s['record']=None
        elif content=='record':
            point=list(s['crosshair']);s['suspect_voxel']=point
            s['confirmed']=True
            s['record']=dict(case_id=s['case_id'],voxel=list(point),
                ras_mm=[meta['origin_ras_mm'][i]+point[i]*meta['spacing_mm'][i] for i in range(3)],
                reviewed=deepcopy(s['reviewed']),part=s.get('part'),source='user_confirmed_location',
                annotation='公开人工分割',saved_ns=time.monotonic_ns())
            stage(adapter,3)
        else:raise ValueError('未知医学内容')
    else:raise ValueError('Unsupported demo action')
    s['revision']+=1
    return {'ok':True,'detail':deepcopy(s)}
