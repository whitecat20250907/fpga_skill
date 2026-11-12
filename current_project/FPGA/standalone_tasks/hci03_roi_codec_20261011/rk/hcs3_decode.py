#!/usr/bin/env python3
"""Strict HCS3 carrier chunks and bounded HCR3 packet reconstruction."""
from __future__ import annotations
import struct,zlib
from hcr3_decode import parse_header,decode_packet

HEADER=struct.Struct('<4sBBHIHHIIHHI')
assert HEADER.size==32

def decode_chunk(line:bytes,frame_rows:int=128)->tuple[bytes,dict]:
    if len(line)!=1440:raise ValueError('carrier line length')
    magic,version,flags,size,seq,n,row,frame,crc,first,reserved,hcrc=HEADER.unpack_from(line)
    if magic!=b'HCS3' or version!=1 or flags not in (0,1) or size!=32 or reserved:raise ValueError('carrier header identity')
    if n>1408 or n%4 or row>=frame_rows or flags!=int(n==0):raise ValueError('carrier dimensions/empty flag')
    if zlib.crc32(line[:28])!=hcrc:raise ValueError('carrier header CRC')
    body=line[32:32+n]
    if zlib.crc32(body)!=crc or any(line[32+n:]):raise ValueError('carrier body CRC/padding')
    if first!=65535 and (first>=n or first%4):raise ValueError('first packet offset')
    return body,dict(chunk_sequence=seq,carrier_frame_sequence=frame,carrier_row=row,valid_bytes=n,first_packet_offset=first)

class CarrierDecoder:
    def __init__(self,frame_rows:int=128):
        self.rows=frame_rows;self.previous=None;self.started=False;self.pending=bytearray();self.previous_packet=None
        self.chunks=0;self.empty=0;self.container_bytes=0;self.content_bytes=0;self.acquisition_prefix_bytes=0;self.packets=0
    def feed(self,line:bytes):
        body,info=decode_chunk(line,self.rows)
        if self.previous is not None:
            old=self.previous
            if info['chunk_sequence']!=(old['chunk_sequence']+1)&0xffffffff:raise ValueError('carrier chunk gap')
            row=(old['carrier_row']+1)%self.rows
            frame=(old['carrier_frame_sequence']+int(row==0))&0xffffffff
            if (info['carrier_row'],info['carrier_frame_sequence'])!=(row,frame):raise ValueError('carrier frame/row discontinuity')
        self.previous=info;self.chunks+=1;self.empty+=int(not body);self.container_bytes+=len(line);self.content_bytes+=len(body)
        if not self.started:
            first=info['first_packet_offset']
            if first==65535:self.acquisition_prefix_bytes+=len(body);return []
            self.acquisition_prefix_bytes+=first;body=body[first:];self.started=True
        self.pending.extend(body);out=[]
        # At most the last partial HCR3 packet survives each carrier chunk.
        while len(self.pending)>=72:
            header=parse_header(self.pending[:72]);n=header['wire_bytes']
            if len(self.pending)<n:break
            raw,meta=decode_packet(bytes(self.pending[:n]));del self.pending[:n]
            seq=meta['packet_sequence']
            if self.previous_packet is not None and seq!=(self.previous_packet+1)&0xffffffff:raise ValueError('source packet gap')
            self.previous_packet=seq;self.packets+=1;out.append((raw,meta))
        if len(self.pending)>1416:raise ValueError('source packet buffer limit')
        return out
    def finish(self):
        return dict(chunks=self.chunks,empty_chunks=self.empty,container_bytes=self.container_bytes,content_bytes=self.content_bytes,
                    acquisition_prefix_bytes=self.acquisition_prefix_bytes,complete_packets=self.packets,trailing_partial_packet_bytes=len(self.pending))
