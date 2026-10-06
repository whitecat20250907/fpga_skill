"""Capture physical HDMI chart with all four runtime Bayer modes on one bit.

No display/software colour correction. Camera applications must be stopped.
Each capture STREAMOFFs/closes before changing a shadow register.
"""
import argparse,hashlib,json,mmap,os,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
p.add_argument('--width',type=int,default=1920);p.add_argument('--height',type=int,default=1080)
p.add_argument('--frames',type=int,default=90)
a=p.parse_args();R=Path(__file__).resolve().parents[1]
a.out.mkdir(parents=True,exist_ok=False)
names=[q.parent.name for q in Path('/sys/class/video4linux').glob('video*/name')
       if q.read_text().strip()=='Milianke PCIe Capture']
if len(names)!=1:raise RuntimeError('Expected one capture node')
fd=os.open('/dev/ANLOGIC-PCI0_user',os.O_RDWR|os.O_SYNC)
result={'status':'UNRESOLVED','captures':[],'scope':'physical camera raw RGB bytes; no colour correctness assumed'}
try:
 with mmap.mmap(fd,4096) as mem:
  def read(off):return int.from_bytes(mem[off:off+4],'little')
  def write(off,v):mem[off:off+4]=v.to_bytes(4,'little');return read(off)
  if read(0x5c)!=0x56440701:raise RuntimeError('Requires source-rebuilt crop/color07 bit')
  if read(0x60)&1 or read(0xa4)&1:raise RuntimeError('Another camera or loopback client is active')
  original=read(0xd8)
  try:
   for mode,name in enumerate(('RGGB','BGGR','GRBG','GBRG')):
    if write(0xd8,mode)!=mode:raise RuntimeError('Bayer shadow write readback failed')
    prefix=a.out/f'{mode}_{name}'
    with prefix.with_suffix('.jsonl').open('w') as out,prefix.with_suffix('.stderr').open('w') as err:
     completed=subprocess.Popen([str(R/'capture_verify'),'/dev/'+names[0],str(a.width),str(a.height),
        str(a.frames),str(prefix),'30'],stdout=out,stderr=err,
        env=dict(os.environ,CAPTURE_SAVE_MODE='bounded'))
     live_modes=[];deadline=time.monotonic()+45
     try:
      while completed.poll() is None:
       # Once a full camera frame has arrived, sample the crop-SOF-locked
       # field while the capture is still running, before STREAMOFF resets it.
       if prefix.with_suffix('.jsonl').stat().st_size and completed.poll() is None and read(0x60)&1:
        active=read(0xdc)
        if read(0x60)&1:live_modes.append(active)
       if time.monotonic()>deadline:raise TimeoutError('Capture deadline')
       time.sleep(.01)
     finally:
      if completed.poll() is None:
       completed.terminate();completed.wait(timeout=10)
    frames=[json.loads(line) for line in prefix.with_suffix('.jsonl').read_text().splitlines() if line.startswith('{')]
    if completed.returncode or len(frames)!=a.frames or any(f['error'] or f['bytesused']!=a.width*a.height*3 for f in frames):
      raise RuntimeError(f'{name}: capture failed or incomplete: rc={completed.returncode} frames={len(frames)}')
    if not live_modes or any(m!=mode for m in live_modes):
      raise RuntimeError(f'{name}: active mode while streaming disagreed: {sorted(set(live_modes))}')
    raw=Path(str(prefix)+'_last.rgb')
    subprocess.run(['python3',str(R/'preview_rgb.py'),str(raw),str(a.width),str(a.height),str(prefix)+'.png'],check=True,timeout=15)
    row={'mode':mode,'name':name,'frames':len(frames),'raw_path':str(raw),
         'last_raw_sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),
         'shadow_after_capture':read(0xd8),'active_after_capture_reset':read(0xdc),
         'live_mode_values':sorted(set(live_modes)),'live_mode_sample_count':len(live_modes),
         'seconds_last_frame':frames[-1]['seconds']}
    result['captures'].append(row);print(json.dumps(row),flush=True)
   result['status']='CAPTURED_FOUR_MODES_COLOUR_UNVERIFIED'
  finally:
   write(0xd8,original)
except Exception as e:
 result.update(status='FAIL',error=str(e))
finally:
 os.close(fd);(a.out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result),flush=True)
raise SystemExit(result['status']=='FAIL')
