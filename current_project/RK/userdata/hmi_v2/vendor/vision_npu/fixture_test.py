import argparse,json,itertools,time
from pathlib import Path
import cv2,numpy as np
from npu_runtime import ROOT,Model,ReferenceModel
from vision_pipeline import LandmarkPipeline
ASSETS=Path('/userdata/freeciv-rk3576-gaze-demo/.gesture-v1/assets')
def read(p):
    x=cv2.imread(str(p))
    if x is None:raise FileNotFoundError(p)
    return cv2.cvtColor(x,cv2.COLOR_BGR2RGB)
def fixtures():
    face=read('/userdata/model_concurrency_20261021/replay_v1/two_face_composite.jpg')
    pair=read(ASSETS/'right_hands.jpg')
    # Duplicate official static photo to exercise four distinct spatial ROIs.
    # This is a four-hand synthetic composition, not two-person human testing.
    pair=cv2.resize(pair,(640,360));four=np.concatenate([pair,pair],axis=0)
    return [('face_one',np.ascontiguousarray(face[:,:face.shape[1]//2]),False,1),('face_two',face,False,2)]+[(p.stem,read(p),True,None) for p in sorted(ASSETS.glob('*.jpg'))]+[('four_hands',four,True,4)]
def summarize(results):
    return [dict(id=x['id'],presence=x['presence'],gesture=x.get('gesture'),score=x.get('score'),right=x.get('right'),center=np.mean(x['landmarks'][:,:2],axis=0).tolist()) for x in results]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',default='fixture_final');args=parser.parse_args()
    out=ROOT/args.out;out.mkdir(exist_ok=False);rows=[]
    pipelines={}
    try:
        for name,rgb,hand,expected in fixtures():
            if hand not in pipelines:pipelines[hand]=LandmarkPipeline(hand,tracking=False)
            npu=pipelines[hand];npu.reset()
            result=npu.process(rgb,record=True)
            # Repeat with tracking enabled to measure reacquisition/stability.
            npu.tracking=True
            repeated=[len(npu.process(rgb,stamp=100+i*.033)) for i in range(10)]
            npu.tracking=False
            row=dict(name=name,hand=hand,expected_count=expected,npu=summarize(result),repeat_counts=repeated)
            rows.append(row);print(json.dumps(row),flush=True)
            canvas=cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)
            for x in result:
                for p in x['landmarks']:
                    cv2.circle(canvas,(round(float(p[0])*rgb.shape[1]),round(float(p[1])*rgb.shape[0])),1,(0,255,0),-1)
            cv2.imwrite(str(out/(name+'.jpg')),canvas)
        np.savez_compressed(out/'fixtures.npz',**{name:rgb for name,rgb,_,_ in fixtures()})
    finally:
        captured=[r for p in pipelines.values() for r in p.captured]
        for p in pipelines.values():p.close()
    errors=[]
    for name in sorted(set(x['name'] for x in captured)):
        ref=ReferenceModel(name)
        try:
            for row in (r for r in captured if r['name']==name):
                actual=ref(*row['inputs']);outs=[]
                for a,b in zip(actual,row['outputs']):
                    b=b.reshape(a.shape);err=np.abs(a-b);outs.append(dict(max_abs=float(err.max()),rmse=float(np.sqrt(np.mean(err**2))),argmax_equal=bool(np.argmax(a)==np.argmax(b))))
                errors.append(dict(name=name,outputs=outs))
        finally:ref.close()
    # Explicit CPU end-to-end geometry reference, with the same pinned weights.
    for hand in [False,True]:
        p=LandmarkPipeline(hand,backend=ReferenceModel,tracking=False)
        try:
            for row,(name,rgb,is_hand,expected) in zip(rows,fixtures()):
                if is_hand!=hand:continue
                r=p.process(rgb);row['cpu']=summarize(r);row['same_count']=len(r)==len(row['npu'])
                row['same_gesture_multiset']=sorted(x.get('gesture','') for x in r)==sorted(x['gesture'] or '' for x in row['npu']) if hand else None
        finally:p.close()
    report=dict(scope='Official still photos and duplicated composites; no human accuracy or identity acceptance.',fixtures=rows,real_roi_output_errors=errors)
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print('FIXTURE_REPORT_WRITTEN',flush=True)
    assert all(r['same_count'] and r['same_gesture_multiset'] is not False for r in rows)
    assert all(r['expected_count'] is None or (len(r['npu'])==r['expected_count'] and all(n==r['expected_count'] for n in r['repeat_counts'])) for r in rows)
if __name__=='__main__':main()
