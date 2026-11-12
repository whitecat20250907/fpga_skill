"""Wrap the original App, Pipeline, calibration and filtering without editing them."""
import time
import copy
import io
from collections import OrderedDict,deque
from pathlib import Path
from core.config import load,ROOT
from core.hmibus import Publisher,Subscriber
from core.service import Service
from .bootstrap import activate
from .ring_capture import RingCapture
from .inference_demand import InferenceDemand
from .resume_tracking import resume_spatial_track
from .selection_sync import release_unselected,FACE_DETECTION_THRESHOLD

def main():
    c=load();activate()
    import pygame
    import gaze_runtime,run_gaze
    from ui.calibration_feedback import summary
    from ui.render_budget import RenderBudget
    from ui.presentation_regions import regions
    from ui.gaze_text import interaction_text
    evaluation={}
    original_metrics=run_gaze.validation_metrics
    def capture_metrics(*args,**kwargs):
        report=original_metrics(*args,**kwargs)
        evaluation.clear();evaluation.update(summary(report))
        return report
    run_gaze.validation_metrics=capture_metrics
    # Replace only the old file-export boundary. HMI publishes observations on
    # its bus; no obsolete /dev/shm/gaze_npu_people_PID.json producer remains.
    gaze_runtime._publish_people=lambda *_args,**_kwargs:None
    gaze_runtime.open_camera=lambda settings:RingCapture(dict(settings,hmi_admission=admission))
    run_gaze.open_camera=gaze_runtime.open_camera
    service=Service('gaze',c);run=c['paths']['run'];epoch=[0];operator_seq=[0]
    operator=Publisher('cmd.operator',run=run)
    def command(name):
        if epoch[0]:
            operator_seq[0]+=1;operator.publish(dict(command=name,src_ns=time.monotonic_ns(),seq=operator_seq[0],epoch=epoch[0]))
    sub=Subscriber(['cmd.gaze','hmi.state','frame.meta'],run=run)
    gaze_pub=Publisher('vision.gaze',run=run);face_pub=Publisher('vision.face',run=run)
    # Capture actual geometry at the existing detector boundary. No extra inference.
    faces={};admission=InferenceDemand();selection={'track':None,'mode':'single'}
    estimate=gaze_runtime.estimate_with_eye_gate
    def scheduled_estimate(estimator,rgb,face,settings):
        # Positive-rate admission happens in RingCapture. Never inject an
        # invalid sample between accepted frames: that resets the old filter.
        if not admission.accepts(getattr(face,'timestamp',None),'gaze'):
            return gaze_runtime._reject_source(estimator,face)
        admission.gaze_calls+=1
        result=estimate(estimator,rgb,face,settings)
        admission.gaze_npu_calls+=int(bool(estimator.last_timings.get('npu_called')))
        return result
    gaze_runtime.estimate_with_eye_gate=scheduled_estimate
    original=gaze_runtime.MediaPipeFaceAlignment.detect
    def detect(obj,stamp,image,**kwargs):
        if not admission.accepts(stamp):
            return gaze_runtime._empty_source_face(stamp,image,kwargs.get('capture_sequence'))
        resume_spatial_track(obj,admission.since_ns,stamp)
        admission.face_calls+=1
        obj.pipeline.detector.threshold=FACE_DETECTION_THRESHOLD
        result=original(obj,stamp,image,**kwargs)
        people=[result]+list(getattr(result,'additional_faces',[]))
        chosen=next((f for f in people if getattr(f,'track_id',None)==selection['track']),None) if selection['track'] is not None else result
        rows=[]
        for f in people:
            rect=getattr(f,'face_rect',None)
            rows.append(dict(track_id=int(getattr(f,'track_id',0) or 0),primary=f is chosen,
                source_size=[int(image.shape[1]),int(image.shape[0])],
                valid=bool(f.status),face_rect=rect.tolist() if hasattr(rect,'tolist') else list(rect) if rect is not None else [0,0,0,0],
                can_gaze=bool(gaze_runtime.eyes_ready(f,settings)),
                landmarks=getattr(f,'face_landmarks',[]).tolist() if hasattr(getattr(f,'face_landmarks',None),'tolist') else []))
        faces[stamp]=rows
        if chosen is not None:
            result=copy.copy(chosen)
            result.additional_faces=[f for f in people if f is not chosen]
        elif selection['track'] is not None:
            result=copy.copy(result);result.status=False;result.track_id=selection['track'];result.additional_faces=[]
        while len(faces)>16:faces.pop(next(iter(faces)))
        return result
    gaze_runtime.MediaPipeFaceAlignment.detect=detect
    class Wrapped(run_gaze.App):
        def __init__(self,settings):
            from .calibration_transaction import CalibrationTransaction
            self.calibration_transaction=CalibrationTransaction()
            self.profiles={};self.selected_track=None;self.switch_ns=0;self.calibration_request=0
            self.render_budget=RenderBudget();self.render_visible=True
            self.text_cache=OrderedDict();self.draw_samples=deque(maxlen=256)
            self.present_key=None;self.previous_pointer=None
            self.inference_activation=0;self.last_selection_command_ns=0
            super().__init__(settings)
            from .visible_preview import VisiblePreview
            self.preview_selector=VisiblePreview(self.preview_selector,lambda:self.render_visible)
            # Keep calibration/validation records, but never grow an unlimited
            # continuous full-rate gaze.csv during an unattended exhibition.
            self.full_writer=self.writer
            app=self
            class SessionWriter:
                def writerow(self,row):
                    if app.phase in ('CALIBRATE','VALIDATE') and app.csv_stream.tell()<16*1024*1024:
                        app.full_writer.writerow(row)
            self.writer=SessionWriter()
        def select_track(self,track,invalidate=False):
            from .profile_selection import select_profile
            if invalidate or track!=self.selected_track:self.calibration_transaction.clear()
            self.calibration=select_profile(self.profiles,self.selected_track,self.calibration,track,invalidate)
            self.selected_track=track;selection['track']=track;self.switch_ns=time.monotonic_ns()
            self.gaze_filter=gaze_runtime.make_filter(self.settings);self.region.reset();self.region_cell=None
            self.last_gaze=None;self.latest_sample=None;self.phase='PREVIEW'
            self.point_samples=[];self.features=[];self.labels=[];self.point_ids=[]
            self.report_message='';self.report_coverage='';evaluation.clear()
        def begin(self,phase):
            if phase=='CALIBRATE':self.calibration_transaction.begin(self.calibration)
            evaluation.clear();self.report_message='';self.report_coverage=''
            return super().begin(phase)
        def cancel_calibration(self):
            self.calibration=self.calibration_transaction.finish(self.calibration)
            self.phase='PREVIEW'
        def text(self,text,y,color=(220,230,240)):
            state=sub.latest('hmi.state') or {}
            if state.get('epoch')!=epoch[0] or not 0<=time.monotonic_ns()-state.get('src_ns',0)<=150_000_000:state={}
            text=interaction_text(text,state)
            if 'ESC/F10 退出  F6' in text:text='握拳准备手势 · 伸指画轨迹 · F10 紧急待机 · R 标定 · V 评测'
            elif '按 F8 直接开启眼控' in text:text='标定完成：👍 使用结果 / ✌ 独立评测；空格使用，V 评测。'
            elif '按 V 测试，确认效果后按 F8' in text:text='眼控仅在选目标时启用；使用配置的眼控手势开始，F10 紧急待机。'
            elif '报告已保存到 data' in text:text='报告已保存到 data；👍 或空格使用结果，R 重新标定，V 再测。'
            text=text.replace('ESC / F10 退出','ESC / F10 紧急待机').replace('ESC 退出','ESC 紧急待机')
            key=(text,color)
            image=self.text_cache.get(key)
            if image is None:
                image=self.font.render(text,True,color);self.text_cache[key]=image
                if len(self.text_cache)>64:self.text_cache.popitem(last=False)
            else:self.text_cache.move_to_end(key)
            return self.window.blit(image,(28,y))
        def draw(self):
            # The original renderer's legacy status path belongs to the old
            # application. HMI state is published on the bus instead.
            self.last_status_write=time.monotonic()
            now=time.monotonic()
            key=(self.phase,self.point_index,self.report_message,self.report_coverage)
            if not self.render_budget.due(now,key,self.render_visible):return
            pointer=tuple(max(0,min(int(v),int(self.size[i])-1)) for i,v in enumerate(self.last_gaze)) if self.phase=='TRACK' and self.last_gaze is not None and time.perf_counter()-self.last_valid_at<.5 else None
            present_key=(key,tuple(self.size),self.preview is not None)
            damage=None if self.present_key!=present_key else regions(self.phase,self.size,self.preview.shape if self.preview is not None else None,self.previous_pointer,pointer,self.font.get_height())
            original_flip=pygame.display.flip
            # Keep drawing/geometry identical. Only the SDL presentation boundary
            # changes: old/new cursor damage, preview and changing status lines.
            # This process has a single display thread; restore even on failure.
            def present():
                if self.window.get_flags() & pygame.OPENGL:return original_flip()
                if damage is None:return pygame.display.update()
                if damage:return pygame.display.update(damage)
            pygame.display.flip=present
            try:result=super().draw()
            finally:pygame.display.flip=original_flip
            self.present_key=present_key;self.previous_pointer=pointer
            self.draw_samples.append((now,(time.monotonic()-now)*1000))
            return result
        def apply_pointer(self,point,*_):self.hmi_pointer=point
        def controls(self):
            sub.poll()
            frame=sub.latest('frame.meta')
            if frame:
                if epoch[0] and frame['epoch']!=epoch[0]:raise RuntimeError('Hardware owner restarted; reopen gaze reader')
                epoch[0]=frame['epoch']
            for msg in sub.events('cmd.gaze'):
                if msg['epoch']!=epoch[0] or not 0<=time.monotonic_ns()-msg['src_ns']<=1_000_000_000:continue
                name=msg.get('command')
                if name in ('select_track','invalidate_calibration','calibrate','validate'):self.last_selection_command_ns=msg['src_ns']
                if name=='select_track':self.select_track(msg.get('track_id'))
                elif name=='invalidate_calibration':self.select_track(msg.get('track_id'),invalidate=True)
                elif name in ('calibrate','validate'):
                    if name=='calibrate':self.calibration_request=msg['seq']
                    self.render_visible=True;self.present_key=None
                    pygame.display.set_mode(tuple(self.size),pygame.FULLSCREEN)
                    self.begin(name.upper())
                elif name=='track' and self.calibration and self.calibration.has_calibrated:self.phase='TRACK'
                elif name=='preview':self.cancel_calibration()
                elif name=='hide_window':self.render_visible=False;pygame.display.iconify()
                elif name=='show_window':self.render_visible=True;self.present_key=None;pygame.display.set_mode(tuple(self.size),pygame.FULLSCREEN)
                elif name=='stop':self.running=False
            for event in pygame.event.get():
                if event.type in (pygame.VIDEOEXPOSE,getattr(pygame,'WINDOWEXPOSED',-1),getattr(pygame,'WINDOWRESTORED',-1)):self.present_key=None
                if event.type==pygame.QUIT:self.running=False
                if event.type==pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE,pygame.K_F10):command('estop')
                    elif event.key==pygame.K_r:command('calibrate')
                    elif event.key==pygame.K_v:command('validate')
                    elif event.key==pygame.K_SPACE:command('use_calibration' if self.calibration and self.calibration.has_calibrated else 'calibrate')
            self.mouse_enabled=self.click_enabled=False
            if not service.running:self.running=False
            state=sub.latest('hmi.state') or {};admission.update(state,epoch[0])
            if state.get('epoch')==epoch[0] and 0<=time.monotonic_ns()-state.get('src_ns',0)<=350_000_000:
                selection['mode']=state.get('people','single')
            if release_unselected(state,self.selected_track,epoch[0],time.monotonic_ns(),self.last_selection_command_ns):
                service.log('selection_reconciled',old_track=self.selected_track,reason='engine_has_no_selected_person')
                self.select_track(None,invalidate=True)
            if admission.rate('gaze') and self.inference_activation!=admission.since_ns:
                self.inference_activation=admission.since_ns
                self.gaze_filter=gaze_runtime.make_filter(self.settings);self.region.reset();self.region_cell=None
                self.last_gaze=None;self.latest_sample=None
            if (state.get('epoch')==epoch[0] and
                    0<=time.monotonic_ns()-state.get('src_ns',0)<=350_000_000 and
                    state.get('src_ns',0)>self.last_selection_command_ns and
                    state.get('state')!='CALIBRATING' and self.phase in ('CALIBRATE','VALIDATE','FAILED')):
                self.cancel_calibration()
            if state.get('state') not in ('CALIBRATING',) and self.render_visible:
                self.render_visible=False;pygame.display.iconify()
            draws=[r for r in self.draw_samples if 0<=time.monotonic()-r[0]<=5]
            service.heartbeat(epoch[0],phase=self.phase,inference=admission.snapshot(),render={'visible':self.render_visible,'samples':len(draws),'mean_ms':sum(r[1] for r in draws)/len(draws) if draws else 0.,'scope':'presentation only; not inference fps'})
        def process(self,samples):
            self.hmi_pointer=None
            samples=[s for s in samples if admission.accepts(s.get('timestamp_ns')) and s.get('timestamp_ns',0)>self.switch_ns and (self.selected_track is None or s.get('track_id')==self.selected_track)]
            super().process(samples)
            if self.phase in ('READY','RESULT') and self.calibration and self.calibration.has_calibrated:
                self.calibration_transaction.clear()
            if not samples or not epoch[0]:return
            s=self.latest_sample;stamp=s['timestamp_ns'];seq=int(s['capture_sequence'])
            service.measurements.observe(time.monotonic_ns(),source_age=(time.monotonic_ns()-stamp)/1e6,**{k:v for k,v in s['timings'].items() if k.endswith('_ms')})
            base=dict(src_ns=stamp,seq=seq,epoch=epoch[0])
            calibrated=bool(self.calibration and self.calibration.has_calibrated)
            if calibrated and self.selected_track is None and selection['mode']=='dual':
                self.selected_track=s.get('track_id');selection['track']=self.selected_track
            xy=self.last_gaze.tolist() if self.last_gaze is not None else None
            targets=run_gaze.validation_points() if self.phase in ('VALIDATE','RESULT') else run_gaze.calibration_points()
            target=list(targets[self.point_index]) if self.phase in ('CALIBRATE','VALIDATE') and self.point_index<len(targets) else None
            gaze_pub.publish(dict(**base,source_instance=s.get('source_instance'),track_id=s.get('track_id'),valid=bool(s['valid'] and calibrated and xy is not None),reason=s['reason'],
                raw=s['raw'].tolist() if s.get('raw') is not None else None,filtered_xy=xy,
                pointer_xy=[float(v) for v in self.hmi_pointer] if self.hmi_pointer is not None else None,region_enabled=self.region_mode,
                region_cell=list(self.region_cell) if self.region_cell is not None else None,region_conf=float(getattr(self.region,'confidence',0)),
                phase=self.phase,calibration_request=self.calibration_request,screen_size=self.size.tolist(),screen_origin=[self.geometry['x'],self.geometry['y']],
                calib={'done':calibrated,'phase':self.phase,'target':target,'point_i':self.point_index,'total':len(targets),'samples':len(self.point_samples),'report':self.report_message,'coverage':self.report_coverage,'evaluation':copy.deepcopy(evaluation)},timings=s['timings']))
            rows=faces.get(stamp,[])
            face_pub.publish(dict(**base,faces=rows))
    settings=gaze_runtime.load_settings({'output_root':c['paths'].get('data',str(ROOT/'data')),'ring_path':str(Path(run)/'frames.memfd'),'capture_hz':60,'monitor':c['display']['hdmi'],'region_mode':False})
    try:Wrapped(settings).run()
    finally:sub.close();gaze_pub.close();face_pub.close();operator.close();service.close()

if __name__=='__main__':main()
