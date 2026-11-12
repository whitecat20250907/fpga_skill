"""Msgpack sidecar for the single C hardware owner; never opens device nodes."""
import json,os,socket,struct,subprocess,time
from pathlib import Path
from core.config import ROOT,load
from core.hmibus import Publisher,Subscriber
from core.service import Service
from core.display_contract import csr_mode as display_csr_mode

def request(path,payload):
    with socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET) as s:
        s.settimeout(.3);s.connect(str(path));s.sendall(payload);return s.recv(4096)

def submit_scene(path,payload,transport=request):
    """A refused/late display update must never stop the capture owner.

    No replay: the next current scene supersedes this one. Negative replies
    include the native epoch/age checks; retain them in observed diagnostics.
    """
    try:
        reply=transport(path,payload)
        return struct.unpack('<i',reply)[0] if len(reply)==4 else -1001
    except (OSError,TimeoutError):
        return -1002

def main():
    c=load();run=Path(c['paths']['run']);run.mkdir(parents=True,exist_ok=True)
    profile=c['mipi'].get('profile','legacy')
    if profile not in ('legacy','theater'):raise ValueError('Unknown MIPI layout')
    if profile=='theater' and not c['mipi']['csr_enabled']:raise ValueError('Theater requires UI11 CSR')
    csr_mode=display_csr_mode(c['mipi'])
    roi_enabled=c['hardware'].get('roi_stats',False)
    gain_enabled=c['hardware'].get('auto_exposure',False)
    if gain_enabled and (not roi_enabled or c['hardware'].get('auto_exposure_backend') not in ('example_gain','example_exposure')):raise ValueError('Select the matching ROI-driven sensor backend')
    svc=Service('fpga-io',c);pub=Publisher('frame.meta',run=run);sub=Subscriber(['ui.scene']+(['vision.face'] if roi_enabled else []),run=run)
    command=[str(ROOT/'native/fpga_io/fpga_io'),str(run),c['hardware']['dma'],c['hardware']['bar']]
    if c['hardware']['panel_start']:command.append('--start-panel')
    if c['hardware'].get('preview',False):command.append('--preview')
    # Frozen capture emits binary MCF1 frames on stdout even with memfd export.
    # Discard this legacy stream: persisting it would fill tmpfs at ~50 MB/s.
    # Diagnostics remain on stderr/journal; consumers use the validated ring.
    proc=subprocess.Popen(command,stdout=subprocess.DEVNULL,env=dict(os.environ,HMI_UI_MODE=str(csr_mode),HMI_AE_BACKEND=c['hardware'].get('auto_exposure_backend','example_gain'),HMI_EXAMPLE_GAIN_ENABLED='1' if gain_enabled else '0'))
    serial=0;last_stat=0;epoch=0;started=time.monotonic();mapped=None;last_frame=time.monotonic_ns()
    ui_rejected=0;ui_last_error=0;ui_log_ns=0
    roi_key=None;roi_status={'available':False,'reason':'disabled'}
    try:
        while svc.running:
            if proc.poll() is not None:raise RuntimeError('Native owner exited: '+str(proc.returncode))
            sub.poll(5);scene=sub.latest('ui.scene');now=time.monotonic_ns()
            if not (run/'fpga_io.sock').exists():
                if time.monotonic()-started>30:raise TimeoutError('Native owner startup')
                continue
            if now-last_stat>=500_000_000:
                last_stat=now
                try:
                    status=json.loads(request(run/'fpga_io.sock',b'STAT'));epoch=status['epoch']
                except (OSError,TimeoutError,ValueError,KeyError):
                    status={'ok':False,'detail':'Native status reply unavailable; capture health follows ring advancement'}
                if roi_enabled:
                    from core.roi_stats import decode
                    try:roi_status=decode(request(run/'fpga_io.sock',b'ROIS'))
                    except (OSError,TimeoutError):roi_status={'available':False,'reason':'reply_timeout'}
                svc.heartbeat(epoch,ok=now-last_frame<2_000_000_000,native=status,ui_rejected=ui_rejected,ui_last_error=ui_last_error,roi_stats=roi_status)
            if roi_enabled and epoch:
                from core.roi_stats import command as roi_command
                payload=roi_command(sub.latest('vision.face'),epoch,now)
                # Never renew a lease using a repeated source observation.
                # The disabled command is sent once; the FPGA also expires it.
                enabled=struct.unpack_from('<I',payload,24)[0]
                key=(epoch,payload if enabled else b'disabled')
                if key!=roi_key:
                    roi_result=submit_scene(run/'fpga_io.sock',payload)
                    roi_key=key
                    if roi_result:roi_status={'available':False,'error':roi_result}
            # The header is advisory only; vision readers perform native acquire
            # fences, seqlock recheck and CRC validation on the full payload.
            if mapped is None and (run/'frames.memfd').exists():
                import mmap
                f=open(run/'frames.memfd','rb');mapped=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ);f.close()
            if mapped:
                write_seq=struct.unpack_from('<Q',mapped,32)[0]
                if write_seq>serial:
                    last_frame=now
                    offset=64+((write_seq-1)%3)*(64+850944);seq=struct.unpack_from('<I',mapped,offset+16)[0];stamp=struct.unpack_from('<Q',mapped,offset+24)[0]
                    if epoch and 0<stamp<=now:
                        pub.publish(dict(src_ns=stamp,seq=seq,epoch=epoch,slot=(write_seq-1)%3,serial=write_seq))
                        svc.measurements.observe(now,source_age=(now-stamp)/1e6)
                    serial=write_seq
            if scene and scene is not getattr(main,'last_scene',None):
                main.last_scene=scene
                if scene['epoch']==epoch and 0<=now-scene['src_ns']<=150_000_000:
                    packet=scene['hft2'];values=[int(scene.get('csr',{}).get(str(0xc80+4*i),0)) for i in range(31)]
                    payload=b'UI01'+struct.pack('<QQII31I',epoch,scene['src_ns'],csr_mode,len(packet),*values)+packet
                    result=submit_scene(run/'fpga_io.sock',payload)
                    if result<0:
                        ui_rejected+=1;ui_last_error=result
                        if now-ui_log_ns>=1_000_000_000:
                            svc.log('ui_scene_discarded',result=result,total=ui_rejected,detail='Capture continues; latest scene will replace this update')
                            ui_log_ns=now
    finally:
        proc.terminate()
        try:proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            svc.log('native_stop_timeout',detail='Owner retained for diagnosis; no forced device cleanup')
            raise
        if mapped:mapped.close()
        sub.close();pub.close();svc.close()

if __name__=='__main__':main()
