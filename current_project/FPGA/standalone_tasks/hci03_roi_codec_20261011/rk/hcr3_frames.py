#!/usr/bin/env python3
"""Assemble only complete, coherent source ROIs for RK model inputs."""
from __future__ import annotations
import argparse,hashlib,json
from collections import OrderedDict
from pathlib import Path
from hcr3_decode import decode_stream

class ROIFrames:
    def __init__(self,max_inflight_per_roi:int=2):
        if not 1<=max_inflight_per_roi<=8:raise ValueError('inflight limit')
        self.limit=max_inflight_per_roi
        self.pending=[OrderedDict() for _ in range(3)]
        self.completed=[0]*3;self.incomplete=[0]*3;self.last_dropped=[None]*3;self.last_complete=[None]*3

    def _discard(self,roi:int,fid:int):
        self.pending[roi].pop(fid)
        self.incomplete[roi]+=1;self.last_dropped[roi]=fid

    def feed(self,raw:bytes,meta:dict):
        rid=meta['roi'];fid=meta['source_frame_id'];w=meta['width'];h=meta['height'];ch=meta['channels'];row=meta['row']
        if not meta['flags']&(1<<rid):raise ValueError('ROI not enabled in source frame')
        if len(raw)!=w*ch or row>=h:raise ValueError('ROI row shape')
        previous=self.last_complete[rid]
        if previous is not None and not 0<((fid-previous)&0xffffffff)<0x80000000:raise ValueError('duplicate or late completed source ROI')
        identity=tuple(meta[k] for k in ['config_sequence','source_time_us','origin_x','origin_y','width','height','channels','flags'])
        queue=self.pending[rid]
        if fid not in queue:
            if len(queue)>=self.limit:self._discard(rid,next(iter(queue)))
            queue[fid]=dict(identity=identity,seen=bytearray(h),rows=0,image=bytearray(w*h*ch),metadata=dict(meta))
        q=queue[fid]
        if q['identity']!=identity:raise ValueError('mixed source config/time/geometry')
        if q['seen'][row]:raise ValueError('duplicate source row')
        q['image'][row*w*ch:(row+1)*w*ch]=raw;q['seen'][row]=1;q['rows']+=1
        if q['rows']!=h:return None
        image=bytes(q['image']);out=dict(q['metadata']);out.pop('row');out['image_bytes']=len(image)
        out['image_sha256']=hashlib.sha256(image).hexdigest();out['pixel_format']='RGB24' if ch==3 else 'GRAY8'
        # These are row-specific fields; a completed image must not retain them
        # as though they described all rows or a model's normalized tensor.
        for key in ['packet_sequence','lane_modes','lane_lengths','raw_crc32','encoded_payload_bytes','wire_bytes','raw_bytes']:out.pop(key,None)
        queue.pop(fid);self.completed[rid]+=1;self.last_complete[rid]=fid
        return image,out

    def finish(self):
        for rid in range(3):
            for fid in list(self.pending[rid]):self._discard(rid,fid)
        return dict(completed=self.completed,incomplete=self.incomplete,last_dropped_source_fid=self.last_dropped)

def main():
    p=argparse.ArgumentParser();p.add_argument('stream',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);frames=ROIFrames();index=[]
    for raw,meta in decode_stream(a.stream.read_bytes()):
        result=frames.feed(raw,meta)
        if result:
            image,info=result;name=f"roi{info['roi']}_fid{info['source_frame_id']:08x}_cfg{info['config_sequence']:08x}.{info['pixel_format'].lower()}"
            (a.output/name).write_bytes(image);info['file']=name;index.append(info)
    report=dict(status='COMPLETE_SOURCE_ROI_BYTES_ONLY_NO_MODEL_INFERENCE_CLAIM',images=index,assembly=frames.finish(),
                scope='Exact source ROI image bytes/identity/sha only. Model preprocessing, normalized tensor hash, actual model SHA/runtime and detections must be bound separately.')
    (a.output/'index.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report['assembly']))
if __name__=='__main__':main()
