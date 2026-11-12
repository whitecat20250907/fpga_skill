#!/usr/bin/env python3
"""Strict HCR3-v1 variable GRAY8/RGB24 ROI row decoder; no recovery guessing."""
from __future__ import annotations
import argparse,json,struct,zlib
from pathlib import Path

HEADER=struct.Struct('<4sBBBBIIIQ6H12HII')
assert HEADER.size==72

def decode_lane(src:bytes,mode:int,n:int)->bytes:
    if mode==0:
        if len(src)!=n:raise ValueError('stored lane length')
        delta=src
    else:
        if len(src)>=n:raise ValueError('compressed lane does not save bytes')
        d=bytearray();i=0
        while i<len(src):
            b=src[i];i+=1
            if b!=255:d.append(b)
            else:
                if i==len(src):raise ValueError('truncated escape')
                c=src[i];i+=1
                if c==0:d.append(255)
                elif c>=128 and d:d.extend(bytes([d[-1]])*((c&127)+3))
                else:raise ValueError('illegal LZ token')
            if len(d)>n:raise ValueError('expanded lane overflow')
        if len(d)!=n:raise ValueError('expanded lane length')
        delta=bytes(d)
    v=0;out=bytearray()
    for b in delta:v=(v+b)&255;out.append(v)
    return bytes(out)

def parse_header(data:bytes)->dict:
    if len(data)<72:raise ValueError('truncated header')
    f=HEADER.unpack_from(data)
    magic,version,roi,ch,flags,packet,fid,cfg,stamp,ox,oy,w,h,y,modes,*tail=f
    lens=tail[:12];crc,hcrc=tail[12:]
    if magic!=b'HCR3' or version!=1 or roi>2 or ch!=(3 if roi==2 else 1):raise ValueError('header identity')
    if not flags&8 or flags&~15:raise ValueError('source flags')
    if not 1<=w<=(448 if roi==2 else 256) or not 1<=h<=(448 if roi==2 else 128) or y>=h or ox+w>1920 or oy+h>1080:raise ValueError('ROI geometry')
    if zlib.crc32(data[:68])!=hcrc:raise ValueError('header CRC32')
    nl=4*ch
    if modes>>nl or any(lens[nl:]):raise ValueError('unused lanes or mode bits')
    for i,n in enumerate(lens[:nl]):
        raw=(w+3-i//ch)//4
        if n>raw or ((modes>>i)&1 and (n==0 or n>=raw)) or (not (modes>>i)&1 and n!=raw):raise ValueError('lane bounds/mode')
    body=((max(lens)+1)//2)*2*nl
    return dict(roi=roi,channels=ch,flags=flags,packet_sequence=packet,source_frame_id=fid,config_sequence=cfg,
                source_time_us=stamp,origin_x=ox,origin_y=oy,width=w,height=h,row=y,lane_modes=modes,
                lane_lengths=lens,raw_crc32=crc,encoded_payload_bytes=sum(lens),wire_bytes=72+body,raw_bytes=w*ch)

def decode_packet(packet:bytes)->tuple[bytes,dict]:
    info=parse_header(packet)
    if len(packet)!=info['wire_bytes']:raise ValueError('wire length')
    ch=info['channels'];nl=4*ch;lens=info['lane_lengths'];lanes=[bytearray() for _ in range(nl)];off=72
    for pair in range((max(lens)+1)//2):
        for lane in range(nl):
            for j in range(2):
                b=packet[off];off+=1
                if pair*2+j<lens[lane]:lanes[lane].append(b)
                elif b:raise ValueError('nonzero wire padding')
    raw=bytearray(info['raw_bytes'])
    for lane in range(nl):
        pixel,channel=divmod(lane,ch);n=(info['width']+3-pixel)//4
        q=decode_lane(bytes(lanes[lane]),(info['lane_modes']>>lane)&1,n)
        raw[pixel*ch+channel::4*ch]=q
    if zlib.crc32(raw)!=info['raw_crc32']:raise ValueError('raw CRC32')
    return bytes(raw),info

def decode_stream(data:bytes):
    off=0;previous=None
    while off<len(data):
        info=parse_header(data[off:off+72]);n=info['wire_bytes']
        raw,info=decode_packet(data[off:off+n])
        if previous is not None and info['packet_sequence']!=(previous+1)&0xffffffff:raise ValueError('packet sequence discontinuity')
        previous=info['packet_sequence'];off+=n
        yield raw,info

def main():
    p=argparse.ArgumentParser();p.add_argument('stream',type=Path);p.add_argument('--json',type=Path);a=p.parse_args()
    rows=[i for _,i in decode_stream(a.stream.read_bytes())]
    s=dict(packets=len(rows),raw_bytes=sum(i['raw_bytes'] for i in rows),payload_bytes=sum(i['encoded_payload_bytes'] for i in rows),wire_bytes=sum(i['wire_bytes'] for i in rows),rows=rows)
    out=json.dumps(s,indent=2)+'\n'
    if a.json:a.json.write_text(out,encoding='utf-8')
    else:print(out,end='')
if __name__=='__main__':main()
