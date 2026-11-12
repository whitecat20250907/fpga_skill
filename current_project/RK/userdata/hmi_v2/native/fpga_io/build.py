"""Generate a native integration unit; original capture/protocol files stay frozen."""
from pathlib import Path
import subprocess
import platform,ctypes

HERE=Path(__file__).resolve().parent
VENDOR=HERE.parents[1]/'vendor'

def cpu_flags():
    if platform.machine().lower() not in ('aarch64','arm64'):return []
    libc=ctypes.CDLL(None);libc.getauxval.argtypes=[ctypes.c_ulong];libc.getauxval.restype=ctypes.c_ulong
    return ['-march=armv8-a+crc'] if libc.getauxval(16)&(1<<7) else []

def generate():
    source=(VENDOR/'gaze_app/capture_native.c').read_text(encoding='utf-8')
    source=source.replace('int main(int argc,char **argv){','static int capture_main(int argc,char **argv){',1)
    # Both modes publish model tensors from the same C2H1 worker. Allow its
    # existing memfd export alongside C2H0 preview; no CPU area3 processing.
    guard='if(export_fd>=0&&(!model_only||export_fd==model_dma_fd'
    assert source.count(guard)==1
    source=source.replace(guard,'if(export_fd>=0&&(!fpga_model||export_fd==model_dma_fd',1)
    source=source.replace('#include "preview_snapshot.h"','#include "preview_snapshot.h"\n#include "preview_budget.h"',1)
    source=source.replace('struct preview_snapshot preview={.fd=-1};','struct preview_snapshot preview={.fd=-1};\n struct hmi_preview_budget preview_budget={0};',1)
    poll_line='  struct pollfd pollfd={.fd=fd,.events=POLLIN};int r=poll(&pollfd,1,100);'
    assert source.count(poll_line)==1
    source=source.replace(poll_line,'''  if(fpga_model && preview.fd>=0){
   unsigned index;uint64_t now=mono();
   if(hmi_preview_due(&preview_budget,now,&index)){
    struct v4l2_buffer queued;struct v4l2_plane qp[VIDEO_MAX_PLANES];buf(&queued,qp,type,planes,index);
    NEED(call(fd,VIDIOC_QBUF,&queued)==0,"preview_budget_requeue");hmi_preview_requeued(&preview_budget,now);
   }
  }
  struct pollfd pollfd={.fd=fd,.events=POLLIN};int r=poll(&pollfd,1,(fpga_model && preview.fd>=0)?5:100);''',1)
    requeue='  buf(&b,p,type,planes,b.index);NEED(call(fd,VIDIOC_QBUF,&b)==0,"requeue");'
    assert source.count(requeue)==1
    source=source.replace(requeue,'''  if(fpga_model && preview.fd>=0){NEED(hmi_preview_hold(&preview_budget,b.index)==0,"preview_budget_hold");}
  else {buf(&b,p,type,planes,b.index);NEED(call(fd,VIDIOC_QBUF,&b)==0,"requeue");}''',1)
    marker='#include "native_model_export.h"'
    assert source.count(marker)==1
    source=source.replace(marker,marker+'\n#include "owner_hooks.h"\n#define model_export_publish hmi_publish\n')
    source+='\n#undef model_export_publish\n#include "owner_main.h"\n'
    header=(VENDOR/'gaze_app/fpga_model_input.h').read_text(encoding='utf-8')
    assert 'CPU_SET(6,&cpus)' in header and 'SCHED_RR' in header
    header=header.replace('CPU_SET(6,&cpus)','CPU_SET(4,&cpus)').replace('SCHED_RR','SCHED_FIFO').replace('.sched_priority=1}', '.sched_priority=10}')
    header=header.replace('requested_cpu\\\":6','requested_cpu\\\":4').replace('requested_priority\\\":1','requested_priority\\\":10')
    old=''' int err=atomic_load(&m->error);if(!err)err=r;
 if(munmap((void*)m->bar,4096)<0&&!err)err=errno;
 m->bar=NULL;
 if(flock(m->dma,LOCK_UN)<0&&!err)err=errno;
 return err;'''
    new=''' int worker_error=atomic_load(&m->error);
 uint32_t control=m->bar[0x19c/4];
 int unmap_error=munmap((void*)m->bar,4096)<0?errno:0;
 m->bar=NULL;
 int unlock_error=flock(m->dma,LOCK_UN)<0?errno:0;
 return hmi_finish_result(worker_error,r,unmap_error,unlock_error,control);'''
    assert header.count(old)==1, 'Frozen model_finish contract changed'
    header=header.replace(old,new)
    header=header.replace('#include "fpga_model_packet.h"','#include "fpga_model_packet.h"\n#include "finish_diagnostics.h"',1)
    header=header.replace('#include "finish_diagnostics.h"','#include "finish_diagnostics.h"\n#include "receive_diagnostics.h"',1)
    edits={
      ' pthread_setname_np(pthread_self(),"model_dma_rx");':' uint64_t fault_events=0;\n pthread_setname_np(pthread_self(),"model_dma_rx");',
      '  model_write(m,0x1a0,1);m->dma_read_calls++;':'  uint64_t credit_ns=mono();\n  model_write(m,0x1a0,1);m->dma_read_calls++;\n  uint64_t before_read_ns=mono();',
      '  if(s->length<0){q->error=':'  if(s->length<0){hmi_receive_fault(m->bar,++fault_events,s->length,saved?saved:EIO,0,0,credit_ns,before_read_ns,s->received);q->error=',
      '   if(c==1){\n    int r=model_resync_retired_error(m);':'   if(c==1){\n    hmi_receive_fault(m->bar,++fault_events,s->length,0,status,info.frame_id,credit_ns,before_read_ns,s->received);\n    int r=model_resync_retired_error(m);'
    }
    for old,new in edits.items():
        assert header.count(old)==1,'Frozen receiver diagnostic insertion changed'
        header=header.replace(old,new,1)
    (HERE/'fpga_model_input.h').write_text(header,encoding='utf-8')
    out=HERE/'capture_integrated.c';out.write_text(source,encoding='utf-8')
    return out

def main():
    out=generate()
    flags=cpu_flags();print('Native CPU flags:',flags,flush=True)
    common=['gcc',*flags,'-O2','-std=c11','-Wall','-Wextra','-Werror','-pthread','-I'+str(VENDOR/'gaze_app'),'-I'+str(VENDOR/'twb_native'),'-I'+str(HERE)]
    subprocess.run(common+[str(out),str(VENDOR/'gaze_app/async_output.c'),str(HERE/'ui_transaction.c'),str(HERE/'ring.c'),'-o',str(HERE/'fpga_io')],check=True)
    subprocess.run(['gcc',*flags,'-O2','-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC',str(HERE/'ring.c'),'-o',str(HERE/'libring.so')],check=True)
    subprocess.run(['gcc','-O2','-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(VENDOR/'twb_native'),str(HERE/'ui_transaction.c'),'-o',str(HERE/'libui_test.so')],check=True)
    for name in ['panel','device_open','finish_diagnostics','receive_diagnostics','preview_budget']:
        subprocess.run(['gcc','-O2','-std=c11','-Wall','-Wextra','-Werror',str(HERE/('test_'+name+'.c')),'-o',str(HERE/(name+'_test'))],check=True)
    for name,extra in [('crc_fast',flags),('crc_portable',[])]:
        subprocess.run(['gcc',*extra,'-O2','-std=c11','-Wall','-Wextra','-Werror',str(HERE/'test_crc.c'),'-o',str(HERE/(name+'_test'))],check=True)

if __name__=='__main__':main()
