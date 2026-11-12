"""Decode an unmodified TrueColor X11 XWD capture for board visual inspection."""
import argparse
from pathlib import Path
import struct


def convert(source, destination):
    from PIL import Image
    data=source.read_bytes()
    if len(data)<100:raise ValueError('Truncated XWD header')
    h=struct.unpack('>25I',data[:100])
    header,version,kind,depth,width,height,offset,order=h[:8]
    bpp,stride,visual,red,green,blue=h[11:17]
    if not (version==7 and kind==2 and depth==24 and offset==0 and visual in (4,5)
            and (red,green,blue)==(0xff0000,0xff00,0xff) and order in (0,1)
            and bpp in (24,32) and 0<width<=16384 and 0<height<=16384):
        raise ValueError('Unsupported factual XWD pixel format')
    start=header+12*h[19]
    if stride<width*(bpp//8) or len(data)!=start+stride*height:raise ValueError('Incomplete XWD pixels')
    rawmode={ (32,0):'BGRX',(32,1):'XRGB',(24,0):'BGR',(24,1):'RGB'}[bpp,order]
    image=Image.frombytes('RGB',(width,height),data[start:],'raw',rawmode,stride,1)
    image.save(destination)
    return width,height


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('destination',type=Path)
    a=p.parse_args();print(convert(a.source,a.destination))
