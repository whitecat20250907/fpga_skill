#!/usr/bin/env python3
"""Strict per-measurement feature packet; quality flags remain authoritative."""
import struct,zlib

SIZE=144
def decode_packet(packet:bytes):
    if len(packet)!=SIZE:raise ValueError('eye packet length')
    magic,version,eye,n=struct.unpack_from('<4sBBH',packet)
    if (magic,version,n)!=(b'HCE3',1,SIZE) or eye not in (0,1):raise ValueError('eye packet identity')
    w=struct.unpack_from('<34I',packet,8)
    if w[3]!=0 or zlib.crc32(packet[:140])!=w[33]:raise ValueError('eye packet reserved/CRC')
    r=list(w[6:30]);quality,fid,cfg,tlo,thi,origin,dimensions,threshold,area=r[:9]
    x,y=origin&65535,origin>>16;width,height=dimensions&65535,dimensions>>16
    if not (1<=width<=256 and 1<=height<=128 and x+width<=1920 and y+height<=1080):raise ValueError('eye geometry')
    if quality>>11 or threshold>256 or area>width*height:raise ValueError('eye quality/threshold/area')
    if quality&1 and quality&~257:raise ValueError('valid flag conflicts with rejection')
    if quality&(64|128|1024) and any(r[8:16]):raise ValueError('rejected moments not zero')
    if area:
        lo,hi=r[14:16];xmin,ymin=lo&65535,lo>>16;xmax,ymax=hi&65535,hi>>16
        if not(0<=xmin<=xmax<width and 0<=ymin<=ymax<height):raise ValueError('eye bbox')
        sx,sy,sxx,sxy,syy=r[9:14]
        if not(area*xmin<=sx<=area*xmax and area*ymin<=sy<=area*ymax):raise ValueError('eye first moments')
        if not(area*xmin*xmin<=sxx<=area*xmax*xmax and area*ymin*ymin<=syy<=area*ymax*ymax and area*xmin*ymin<=sxy<=area*xmax*ymax):raise ValueError('eye second moments')
    elif any(r[9:16]):raise ValueError('empty moments not zero')
    if max(r[17],r[18],r[21])>width*height or r[19]>width*height*255 or r[20]>width*height*65025:raise ValueError('eye pixel totals')
    return dict(kind='feature',eye=eye,packet_sequence=w[0],publication_drops=w[1],last_dropped_frame_id=w[2],
                reports_received=w[4],reports_sent_before_capture=w[5],quality_flags=quality,
                source_frame_id=fid,config_sequence=cfg,source_time_us=tlo|(thi<<32),origin_x=x,origin_y=y,width=width,height=height,
                words=r,engine_received=w[30],engine_skipped=w[31],engine_deadline=w[32])
