#!/usr/bin/env python3
"""Bounded mixed HCR3 ROI/HCE3 feature stream inside strict HCS3 containers."""
from hcs3_decode import decode_chunk
import hcr3_decode,hce3_decode

class MixedCarrierDecoder:
    def __init__(self,frame_rows=128):
        self.rows=frame_rows;self.previous=None;self.started=False;self.pending=bytearray();self.sequence={}
        self.chunks=0;self.empty=0;self.container_bytes=0;self.content_bytes=0;self.acquisition_prefix_bytes=0
        self.roi_packets=0;self.feature_packets=0
    def feed(self,line):
        body,info=decode_chunk(line,self.rows)
        if self.previous is not None:
            old=self.previous;row=(old['carrier_row']+1)%self.rows;frame=(old['carrier_frame_sequence']+int(row==0))&0xffffffff
            if info['chunk_sequence']!=(old['chunk_sequence']+1)&0xffffffff or (info['carrier_row'],info['carrier_frame_sequence'])!=(row,frame):raise ValueError('carrier discontinuity')
        self.previous=info;self.chunks+=1;self.empty+=int(not body);self.container_bytes+=len(line);self.content_bytes+=len(body)
        acquisition=False
        if not self.started:
            first=info['first_packet_offset']
            if first==65535:self.acquisition_prefix_bytes+=len(body);return []
            self.acquisition_prefix_bytes+=first;body=body[first:];self.started=True;acquisition=True
        position=-len(self.pending);expected_first=0 if position==0 and body else None
        self.pending.extend(body);out=[]
        while len(self.pending)>=8:
            magic=self.pending[:4]
            if magic==b'HCR3':
                if len(self.pending)<72:break
                n=hcr3_decode.parse_header(self.pending[:72])['wire_bytes']
                if len(self.pending)<n:break
                payload,meta=hcr3_decode.decode_packet(bytes(self.pending[:n]));meta['kind']='roi';key=('roi',);self.roi_packets+=1
            elif magic==b'HCE3':
                if len(self.pending)<144:break
                n=144;payload=bytes(self.pending[:n]);meta=hce3_decode.decode_packet(payload);key=('feature',meta['eye']);self.feature_packets+=1
            else:raise ValueError('source packet magic')
            seq=meta['packet_sequence']
            if key in self.sequence and seq!=(self.sequence[key]+1)&0xffffffff:raise ValueError('source packet sequence gap')
            self.sequence[key]=seq;out.append((payload,meta));del self.pending[:n];position+=n
            if expected_first is None and 0<=position<len(body):expected_first=position
        if len(self.pending)>1416:raise ValueError('source packet buffer limit')
        # After acquisition, declared first offsets must match parsed boundaries,
        # including a new packet whose header is split into the next chunk.
        if not acquisition and info['first_packet_offset']!=(65535 if expected_first is None else expected_first):raise ValueError('first packet boundary mismatch')
        return out
    def finish(self):
        return dict(chunks=self.chunks,empty_chunks=self.empty,container_bytes=self.container_bytes,content_bytes=self.content_bytes,
                    acquisition_prefix_bytes=self.acquisition_prefix_bytes,roi_packets=self.roi_packets,feature_packets=self.feature_packets,trailing_partial_packet_bytes=len(self.pending))
