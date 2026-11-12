"""Manual, bounded local feature viewer/recorder; no capture or inference."""
import argparse,json,os,resource,socket,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from project_features import FeatureState
from project_twin import render
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seconds',type=float,default=60)
    ap.add_argument('--port',type=int,default=29802)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--show',action='store_true',help='Optional preview window; FPGA transport is separate')
    args=ap.parse_args()
    if not 1<=args.seconds<=300 or args.output.exists():ap.error('1..300 seconds, fresh output directory')
    args.output.mkdir(parents=True);state=FeatureState();received=0;ages=[];render_ms=[];hand_frames=0;face_frames=0
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind(('127.0.0.1',args.port));sock.setblocking(False)
    display=None;pygame=None
    if args.show:
        import pygame
        pygame.init();display=pygame.display.set_mode((1024,600));pygame.display.set_caption('手 / 头 / 双眼 · 实时特征预览')
    deadline=time.monotonic()+args.seconds;last_frame=0.;last_saved=0.;cpu=time.process_time();start=time.monotonic()
    try:
        with (args.output/'features.jsonl').open('w',buffering=1) as log:
            while time.monotonic()<deadline:
                for _ in range(32):
                    try:body,_=sock.recvfrom(32001)
                    except BlockingIOError:break
                    if state.accept(body):
                        log.write(body.decode()+'\n');received+=1
                        ages.append((time.monotonic_ns()-json.loads(body)['timestamp_ns'])/1e6)
                if pygame and any(e.type==pygame.QUIT for e in pygame.event.get()):break
                if time.monotonic()-last_frame>=.1:
                    begin=time.monotonic();image=render(state);last_frame=time.monotonic();render_ms.append(1000*(last_frame-begin))
                    hand=state.fresh('hand');face=state.fresh('face')
                    if hand and hand['hands']:hand_frames+=1
                    if face and face['valid']:face_frames+=1
                    if display:
                        display.blit(pygame.image.fromstring(image.tobytes(),image.size,'RGB'),(0,0));pygame.display.flip()
                    if time.monotonic()-last_saved>=1:
                        image.save(args.output/'latest.png');last_saved=time.monotonic()
                        if hand and hand['hands']:image.save(args.output/'latest_tracked_hand.png')
                time.sleep(.01)
    finally:
        sock.close()
        render(state).save(args.output/'latest.png')
        if pygame:pygame.quit()
        elapsed=time.monotonic()-start
        result=dict(status='COMPLETED_BOUNDED_EXISTING_FEATURE_VIEW',packets=received,rejected=state.rejected,
            seconds=elapsed,cpu_one_core_percent=100*(time.process_time()-cpu)/elapsed,
            capture_started=False,inference_started=False,FPGA_screen_accepted=False,human_motion_accuracy_accepted=False,
            latest_kinds=sorted(state.samples),tracked_hand_render_frames=hand_frames,tracked_face_render_frames=face_frames,
            max_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
            source_age_ms=dict(mean=sum(ages)/len(ages),maximum=max(ages)) if ages else None,
            render_ms=dict(mean=sum(render_ms)/len(render_ms),maximum=max(render_ms)) if render_ms else None)
        (args.output/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':main()
