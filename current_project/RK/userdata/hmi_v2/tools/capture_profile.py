"""Read existing owner telemetry; never open a hardware device or reset counters."""
import argparse,fcntl,json,os,struct,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.config import load
from core.io_service import request


def preview_header(path):
    # Only hold the existing nonblocking record lock for a 64-byte header read.
    # No full image copies and no stale mappings across owner restarts.
    try:
        with open(path,'rb',buffering=0) as f:
            fcntl.lockf(f,fcntl.LOCK_SH|fcntl.LOCK_NB,1,0)
            h=os.pread(f.fileno(),64,0)
            if len(h)!=64 or h[:8]!=b'GZPRV001':return None
            version,width,height,stride,valid,sequence=struct.unpack_from('<6I',h,8)
            if (version,width,height,stride,valid)!=(1,1920,1080,5760,6220800):return None
            stamp,dequeue,serial,published=struct.unpack_from('<4Q',h,32)
            return dict(serial=serial,sequence=sequence,published_ns=published,
                        source_ns=stamp,dequeue_ns=dequeue,inode=os.fstat(f.fileno()).st_ino)
    except (OSError,BlockingIOError):return None


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seconds',type=int,default=60);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if not 5<=a.seconds<=3600:p.error('seconds must be 5..3600')
    run=Path(load()['paths']['run']);rows=[];errors=[];start=time.monotonic()
    while True:
        try:
            s=json.loads(request(run/'fpga_io.sock',b'STAT'))
            if s.get('capture',{}).get('tdm_abi')!=0x314d4454:raise ValueError('Owner capture telemetry/TDM1 unavailable')
            rows.append(dict(monotonic_ns=time.monotonic_ns(),native=s,preview=preview_header(run/'preview.memfd')))
        except (OSError,ValueError) as e:errors.append(dict(seconds=time.monotonic()-start,error=str(e)))
        remaining=a.seconds-(time.monotonic()-start)
        if remaining<=0:break
        time.sleep(min(1,remaining))
    epochs={r['native']['epoch'] for r in rows};summary={}
    if len(rows)>=2 and len(epochs)==1:
        first,last=rows[0],rows[-1];duration=(last['monotonic_ns']-first['monotonic_ns'])/1e9
        a0,b=first['native'],last['native']
        delta=b['serial']-a0['serial']
        if delta<0:errors.append(dict(error='Model serial regressed'))
        summary['model_publish_hz']=delta/duration
        summary['counter_delta_modulo_32bit']={k:(b['capture'][k]-a0['capture'][k])&0xffffffff for k in (
            'preview_blocked_valid_cycles','model_source_frames','model_packet_aborts','model_drops')}
        # Model enable toggles deliberately reset the pixel branch after a
        # sealed error. Its counters can reset WITHOUT changing hardware epoch.
        # Never present their first/last subtraction as a cumulative count.
        summary['model_branch_resettable_counters']={k:dict(first=a0['capture'][k],last=b['capture'][k],
            observed_decreases=sum(y['native']['capture'][k]<x['native']['capture'][k] for x,y in zip(rows,rows[1:])))
            for k in ('model_complete_frames','model_abort_frames','model_overflows')}
        summary['preview_fifo_peak_since_hardware_reset_words']=max(r['native']['capture']['preview_fifo_highwater_words'] for r in rows)
        good=[r for r in rows if r['preview']]
        if len(good)>=2 and len({r['preview']['inode'] for r in good})==1:
            first,last=good[0]['preview'],good[-1]['preview'];dt=(last['published_ns']-first['published_ns'])/1e9
            if dt>0:summary['preview_publish_hz']=(last['serial']-first['serial'])/dt
    else:errors.append(dict(error='Insufficient samples or hardware epoch changed'))
    result=dict(status='PASS_READ_ONLY_MEASUREMENT' if not errors else 'INCOMPLETE',
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),duration_s=time.monotonic()-start,
        summary=summary,errors=errors,samples=rows,
        limits=['Counters are sequential reads, not atomic snapshots.',
                'High-water mark includes the entire hardware epoch, including startup.',
                'blocked_valid_cycles counts valid && !ready cycles; it is not a count of corrupted pixels.',
                '32-bit counters may wrap; deltas assume fewer than 2^32 increments in the interval.',
                'Model branch complete/abort/overflow reset on enable toggles; raw first/last values and observed decreases are not lifetime totals.',
                'Maximum consecutive backpressure is not exposed; these data alone cannot approve a smaller FIFO.',
                'FIFO capacity/word size must be taken from the exact loaded bit source.'])
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='samples'}))
    return bool(errors)


if __name__=='__main__':raise SystemExit(main())
