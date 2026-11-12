import argparse,json
from pathlib import Path
import cv2
from benchmark import run_case
ROOT=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',default='bench_v1');p.add_argument('--seconds',type=float,default=12);p.add_argument('--case',default='all');a=p.parse_args()
    cv2.setNumThreads(1);out=ROOT/a.out;out.mkdir(exist_ok=False);rows=[];cases=[]
    for hands in [1,2,4]:
        for policy,cores in [('serial',()),('auto2',(0,0)),('pin2',(1,2))]:
            cases.append(dict(label=f'hand{hands}_{policy}',nfaces=0,nhands=hands,hand_cores=cores,cnn=False))
    for people,hands in [(1,2),(2,4)]:
        for policy,cores,face,detector,gaze in [('serial',(),0,0,0),('auto2',(0,0),0,0,0),('pin2',(1,2),0,0,0),('face_hand_split',(2,2),1,2,1)]:
            cases.append(dict(label=f'mix{people}_{policy}_backpressure',nfaces=people,nhands=hands,hand_cores=cores,core_face=face,core_hand=detector,core_gaze=gaze))
    cases.append(dict(label='mix2_both_roi_pin2_backpressure',nfaces=2,nhands=4,hand_cores=(1,2),face_cores=(1,2)))
    for people in [1,2]:cases.append(dict(label=f'eye{people}_stage_split_backpressure',nfaces=people,nhands=0,core_face=1,core_gaze=2,cnn=False))
    for policy,cores in [('auto2',(0,0)),('pin2',(1,2))]:
        for people,hands in [(1,0),(2,0),(1,2),(2,4)]:
            cases.append(dict(label=f'full{people}_hands{hands}_{policy}_backpressure',nfaces=people,nhands=hands,hand_cores=cores,face_cores=cores,gaze_cores=cores,cnn=bool(hands)))
    for hands in [2,4]:cases.append(dict(label=f'hand{hands}_graph2',nfaces=0,nhands=hands,core_hand=3,cnn=False))
    for people,hands in [(1,2),(2,4)]:
        cases.append(dict(label=f'mix{people}_graph2_backpressure',nfaces=people,nhands=hands,core_hand=3,core_gaze=3))
        cases.append(dict(label=f'mix{people}_gaze_parallel_backpressure',nfaces=people,nhands=hands,hand_cores=(0,0),gaze_cores=(0,0)))
        cases.append(dict(label=f'mix{people}_stage_split_backpressure',nfaces=people,nhands=hands,hand_cores=(0,0),core_face=1,core_gaze=2))
        cases.append(dict(label=f'mix{people}_gaze_graph2_handauto_backpressure',nfaces=people,nhands=hands,hand_cores=(0,0),core_gaze=3))
    for case in cases:
        if a.case!='all' and case['label'] not in a.case.split(','):continue
        result=run_case(seconds=a.seconds,**case)
        (out/(case['label']+'.json')).write_text(json.dumps(result,indent=2)+'\n')
        s=result['summary'];rows.append(s);(out/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
        print(json.dumps({k:s[k] for k in ['label','gaze_batch_hz','hand_batch_hz','all_people_valid_hz','all_hands_valid_hz','age_ms','cpu_one_core_percent','hand_counts']}),flush=True)
if __name__=='__main__':main()
