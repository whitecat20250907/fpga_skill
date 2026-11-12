"""Semantic screen targets. No grid cells and no gaze timestamp substitution."""
import math
from copy import deepcopy

from functools import lru_cache
from pathlib import Path
import json

@lru_cache(maxsize=1)
def medical_spec():
    return json.loads((Path(__file__).resolve().parents[1]/'console/medical_spec.json').read_text('utf-8'))

def medical_case(state):
    spec=medical_spec()
    if spec.get('workflow')!='renal_review':
        return spec['pages'][int(state.get('page',0))%len(spec['pages'])].get('case')
    identity=state.get('case_id',spec['default_case'])
    return next((c for c in spec['cases'] if c['id']==identity),spec['cases'][0])

def medical_rows(state):
    spec=medical_spec();page=spec['pages'][int(state.get('page',0))%len(spec['pages'])]
    inspection=state.get('inspection');rows=[]
    for item in page.get('controls',[])+page['parts']:
        item=deepcopy(item)
        if spec.get('workflow')=='renal_review' and page['key']=='findings' and item.get('key')=='record' and state.get('record'):continue
        if spec.get('workflow')=='renal_review' and page['key']=='ct' and item.get('plane'):
            # Keep the selected plane in the large viewport. The backend and
            # browser consume these same rectangles; no invisible hit areas.
            primary=state.get('plane','axial')
            positions=page['plane_positions']
            if item['plane']==primary:item['rect']=positions['axial']
            elif item['plane']=='axial':item['rect']=positions[primary]
        if inspection and item.get('content'):
            if item['content']==inspection:
                item['rect']=page['inspection_rect'];item['label']+=' · 再次点击返回'
            elif item.get('detail_rect'):
                item['rect']=item['detail_rect']
        rows.append(item)
    return rows

def demo_targets(state,size):
    w,h=size;spec=medical_spec();page=int(state.get('page',0))%len(spec['pages'])
    rows=[]
    for item in medical_rows(state):
        region='match' in item
        scope=(medical_case(state)['id']+':') if spec.get('workflow')=='renal_review' else ''
        rows.append(dict(id=f"demo:roi:{page}:{scope}{item['key']}" if region else f"demo:control:{page}:{scope}{item['key']}",
                         label=('停止旋转' if state.get('rotating') else '开始旋转') if item['key']=='rotate' else item['label'],action='demo.focus' if region else item['action'],
                         rect=[v*d for v,d in zip(item['rect'],[w,h,w,h])],confidence=1.,
                         part=item['key'] if region else None,page=page,
                         **({'case_id':medical_case(state)['id']} if scope else {}),
                         **({'content':item['content']} if 'content' in item else {})))
    return rows

def center(target):
    x,y,w,h=target['rect'];return [x+w/2,y+h/2]

def medical_view(state):
    """Browser layout and eye targets share one normalized geometry source."""
    source=medical_rows(state);targets=demo_targets(state,(1,1))
    return {'page':state.get('page',0),'case_id':state.get('case_id'),
            'rows':[dict(item,**target) for item,target in zip(source,targets)]}


def resolve_medical_click(requested, rows):
    """A direct content click follows its ID across detail-layout transitions.

    Unlike a gaze lock this request is not a frozen screen position. Resolve
    only the same semantic action on the same page; never reuse stale payloads.
    """
    for row in rows:
        if same_medical_target(requested,row):
            return deepcopy(row)
    raise ValueError('医学页面已变化')

def same_medical_target(a,b):
    # Geometry may move during zoom, rotation or CT viewport promotion. Keep
    # the locked content identity within the same case/page.
    return bool(a and b and a.get('id')) and all(a.get(k)==b.get(k)
        for k in ('id','page','case_id','action','content','part'))

def valid_target(row,size):
    try:
        values=row['rect'];x,y,w,h=values
        return bool(isinstance(row['id'],str) and len(row['id'])<=256 and
                    all(type(v) in (int,float) and math.isfinite(v) for v in values) and
                    w>0 and h>0 and 0<=x+w/2<size[0] and 0<=y+h/2<size[1] and
                    0<float(row.get('confidence',1))<=1)
    except (KeyError,TypeError,ValueError):return False

def select_target(xy,rows,size,previous=None):
    """Nearest real control, weighted by provider confidence; small hysteresis."""
    scored=[]
    for row in rows:
        if not valid_target(row,size):continue
        x,y,w,h=row['rect'];cx,cy=center(row)
        edge=math.hypot(max(x-xy[0],0,xy[0]-x-w),max(y-xy[1],0,xy[1]-y-h))
        score=(edge+.15*math.hypot(cx-xy[0],cy-xy[1]))/float(row.get('confidence',1))
        scored.append((score,row))
    if not scored:return None
    score,best=min(scored,key=lambda p:p[0])
    old=next(((s,r) for s,r in scored if r['id']==previous),None)
    if old and old[0]<=score+12:best=old[1]
    return deepcopy(best)

def same_target(a,b):
    if not (a and b and a.get('id')==b.get('id') and a.get('action')==b.get('action')):return False
    try:
        px,py=center(a);x,y,w,h=b['rect']
        return x<=px<=x+w and y<=py<=y+h
    except (KeyError,TypeError,ValueError):return False
