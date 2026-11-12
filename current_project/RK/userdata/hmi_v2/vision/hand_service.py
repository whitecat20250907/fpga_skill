import time
from core.config import load,ROOT
from core.hmibus import Publisher,Subscriber
from core.frame_ring import FrameRing
from core.service import Service
from core.clock import fresh
from .bootstrap import activate
from .hand_visibility import usable_palm

def main():
    c=load();v=activate()
    from hand_runtime import SampleClock
    from vision_pipeline import HandRecognizer
    from .gesture_flow import GestureTrajectory
    from classifier import Classifier
    svc=Service('hand',c);run=c['paths']['run'];sub=Subscriber(['hmi.state'],run=run)
    hands_pub=Publisher('vision.hands',run=run);stroke_pub=Publisher('vision.stroke',run=run)
    ring=FrameRing(run+'/frames.memfd')
    if c['npu'].get('fused_gesture',False):
        from .fused_hand import FusedHandRecognizer
        recognizer=FusedHandRecognizer(num_hands=4,core=c['npu']['hand_detector_core'],roi_cores=c['npu']['hand_roi_cores'])
    else:recognizer=HandRecognizer(num_hands=4,core=c['npu']['hand_detector_core'])
    classifier=Classifier(v/'gesture8')
    recorder=GestureTrajectory(c['gestures']);clock=SampleClock(30);serial=0;raw_items=[]
    original=recognizer.pipeline.process
    def process(*args,**kwargs):
        result=original(*args,**kwargs);raw_items[:]=result;return result
    recognizer.pipeline.process=process
    try:
        while svc.running:
            ring.check_owner()
            recorder.tick(time.monotonic())
            sub.poll();state=sub.latest('hmi.state') or {}
            if not fresh(state.get('src_ns'),350,time.monotonic_ns()):state={'state':'DEGRADED','budget':{'hand_hz':0}}
            hz=state.get('budget',{}).get('hand_hz',30)
            if hz<=0:svc.heartbeat(ring.epoch);time.sleep(.02);continue
            clock.period=0 if state.get('budget',{}).get('hand_unlimited') else 1/hz
            delay=clock.delay(time.monotonic())
            if delay>0:time.sleep(min(.01,delay));continue
            frame=ring.latest(serial)
            if not frame:clock.busy(time.monotonic());continue
            serial=frame.serial;meta=frame.meta;stamp=meta['timestamp_ns'];now=time.monotonic_ns()
            if not 0<=now-stamp<=350_000_000:continue
            result=recognizer.recognize_for_video(frame.rgb,stamp/1e6)
            ended=time.monotonic_ns();svc.measurements.observe(ended,hand_total=(ended-now)/1e6,source_age=(ended-stamp)/1e6)
            base=dict(src_ns=stamp,seq=meta['sequence'],epoch=meta['fpga_epoch'])
            hands=[]
            for i,key in enumerate(result.track_ids):
                points=[[float(p.x),float(p.y),float(p.z)] for p in result.hand_landmarks[i]]
                hands.append(dict(track_id=int(key),side=result.handedness[i][0].category_name,side_score=float(result.handedness[i][0].score),
                    image21=points,world21=[[float(p.x),float(p.y),float(p.z)] for p in result.hand_world_landmarks[i]],
                    gesture=result.gestures[i][0].category_name,score=float(result.gestures[i][0].score),
                    probabilities=list(map(float,raw_items[i].get('probabilities',[]))),fingertip=points[8],
                    in_bounds=usable_palm(points)))
            snapshots={}
            finished=recorder.update(result,meta['sequence'],stamp/1e9,ended/1e9,640,360,state)
            for key,image in finished:
                prediction=classifier.predict(image)
                prediction=dict(prediction,accepted=prediction['confidence']>=c['gestures'].get('stroke_confidence',.5))
                ending=next((h for h in hands if h['track_id']==key),{})
                stroke_pub.publish(dict(**base,track_id=int(key),source_side=ending.get('side'),ending_gesture=ending.get('gesture'),gesture_generation=state.get('gesture_generation',0),class_index=classifier.classes.index(prediction['label']),**prediction))
            for key,r in recorder.recorders.items():
                points=list(getattr(r,'points',[]));count=min(48,len(points))
                shown=[points[round(i*(len(points)-1)/max(1,count-1))] for i in range(count)]
                snapshots[str(key)]={'state':str(getattr(r,'state','')),'points':shown,'reason':getattr(r,'reason',''),'remaining_s':max(0.,getattr(r,'countdown_s',.3)-(time.monotonic()-getattr(r,'since',0))) if r.state=='COUNTDOWN' else 0.}
            hands_pub.publish(dict(**base,hands=hands,recorder=snapshots,gesture_generation=state.get('gesture_generation',0)));clock.accepted(time.monotonic());svc.heartbeat(meta['fpga_epoch'])
    finally:
        recognizer.close();classifier.close();ring.close();sub.close();hands_pub.close();stroke_pub.close();svc.close()

if __name__=='__main__':main()
