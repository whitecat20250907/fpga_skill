"""Real RKNN fixtures, old/new geometry equivalence, and resize regression."""
import importlib.util,json,time,itertools
from pathlib import Path
import cv2,numpy as np
from fixture_test import fixtures,summarize
from vision_pipeline import LandmarkPipeline
from gaze_bridge import Geometry
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('old_bridge','/userdata/npu_dualcore_20261022/gaze_bridge.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
def compare(a,b):
    assert vars(a).keys()==vars(b).keys(),(vars(a).keys(),vars(b).keys())
    for k in vars(a):
        x,y=getattr(a,k),getattr(b,k)
        if isinstance(x,(np.ndarray,list,tuple)):np.testing.assert_array_equal(x,y,err_msg=k)
        else:assert x==y,(k,x,y)
def main():
    cv2.setNumThreads(1);cases=fixtures();checks=0;resize=[];durations={};pointsets=[]
    with_pipeline=LandmarkPipeline(False,tracking=False)
    try:
        for name,rgb,hand,_ in cases:
            if hand:continue
            for item in with_pipeline.process(rgb):pointsets.append((rgb,item['landmarks']))
    finally:with_pipeline.close()
    assert len(pointsets)>=3
    g1=old.Geometry();g2=Geometry();stamp=time.monotonic_ns()
    for rgb,p in pointsets:
        q=p.copy();q[0,0]=np.nan
        for a in [p,p[:468],p*.99+.002,p+np.array([-.2,.03,0]),q,np.zeros((478,3),np.float32),None]:
            compare(g1.from_points(a,rgb,stamp,7),g2.from_points(a,rgb,stamp,7));checks+=1
    rgb,p=pointsets[0]
    for name,g in [('before',g1),('after',g2)]:
        samples=[]
        for _ in range(500):
            t=time.perf_counter_ns();g.from_points(p,rgb,stamp,7);samples.append((time.perf_counter_ns()-t)/1e6)
        durations[name]=dict(median_ms=float(np.median(samples)),p95_ms=float(np.percentile(samples,95)))
    # Exactly the native integer area3 rule, fed from the same simulated 1080 RGB.
    pipeline=LandmarkPipeline(True,tracking=False)
    try:
        for name,rgb,hand,expected in cases:
            if not hand:continue
            h,w=rgb.shape[:2];scale=min(1920/w,1080/h);image=np.zeros((1080,1920,3),np.uint8)
            small=cv2.resize(rgb,(round(w*scale),round(h*scale)));hh,ww=small.shape[:2]
            image[(1080-hh)//2:(1080-hh)//2+hh,(1920-ww)//2:(1920-ww)//2+ww]=small
            center=np.ascontiguousarray(image[1::3,1::3]);area=((image.reshape(360,3,640,3,3).sum((1,3),dtype=np.uint16)+4)//9).astype(np.uint8)
            a=pipeline.process(center);pipeline.reset();b=pipeline.process(area);pipeline.reset()
            same=len(a)==len(b) and sorted(x['gesture'] for x in a)==sorted(x['gesture'] for x in b)
            resize.append(dict(name=name,before=summarize(a),after=summarize(b),same_count_and_labels=same))
            # Compare optimized inactive-input path with full recorded reference inputs.
            c=pipeline.process(area,record=True);pipeline.reset()
            assert len(b)==len(c),name
            for x,y in zip(b,c):
                np.testing.assert_array_equal(x['landmarks'],y['landmarks'])
                np.testing.assert_array_equal(x['probabilities'],y['probabilities'])
                np.testing.assert_array_equal(x['world'],y['world'])
    finally:pipeline.close()
    # All possible byte inputs must retain exactly the old float32 normalization.
    x=np.arange(256,dtype=np.uint8);a=x.astype(np.float32)/255;b=x.astype(np.float32);b/=255
    np.testing.assert_array_equal(a,b);a=a*2-1;b*=2;b-=1;np.testing.assert_array_equal(a,b)
    report=dict(geometry_exact_cases=checks,geometry_timing=durations,resize=resize,all_resize_labels_equal=all(r['same_count_and_labels'] for r in resize),normalization_exact=True,inactive_input_output_exact=True,scope='Static photos and synthetic compositions; not human acceptance')
    (ROOT/'numerical.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
    assert report['all_resize_labels_equal'],'Area3 changes fixture labels/count; investigate before promotion'
if __name__=='__main__':main()
