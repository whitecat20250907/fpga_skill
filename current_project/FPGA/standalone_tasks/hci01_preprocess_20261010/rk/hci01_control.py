"""HCIC volatile mode control; actual FPGA acceptance is required, not an echo."""
import argparse,hashlib,json,struct,sys,time,zlib
from pathlib import Path
local=Path('C:/qianrushifpga/.local_tools/python-packages')
if local.is_dir():sys.path.insert(0,str(local))
import serial
from serial.tools import list_ports
MODES={'all_three':0,'rgb':1,'luma':6,'sobel':8,'mask':16,'erode':24,'dilate':32}
def command(mode,threshold,sequence):
 assert mode in MODES.values() and 0<=threshold<=255 and 1<=sequence<=0xffffffff
 p=struct.pack('<4sBBBBI',b'HCIC',1,mode,threshold,0,sequence)
 return p+struct.pack('<I',zlib.crc32(p))
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--port',required=True);ap.add_argument('--mode',choices=MODES,required=True)
 ap.add_argument('--threshold',type=int,default=128);ap.add_argument('--sequence',type=int,required=True)
 ap.add_argument('--timeout',type=float,default=8);ap.add_argument('--out',type=Path,required=True)
 a=ap.parse_args();assert not a.out.exists() and 2<=a.timeout<=30
 ports=[p for p in list_ports.comports() if p.device==a.port]
 assert len(ports)==1 and ports[0].vid==0x0403 and ports[0].pid==0x6042 and ports[0].serial_number=='AL7A9AF422B','Target must be the known FPGA U42 UART; do not choose RK debug UART.'
 b=command(MODES[a.mode],a.threshold,a.sequence);raw=bytearray();at=0;values=[];last_sequence=None;found=None
 p=serial.Serial(port=None,baudrate=115200,timeout=.05,write_timeout=1)
 p.port=a.port;p.dtr=False;p.rts=False;p.open()
 try:
  assert p.write(b)==16;p.flush();begin=time.monotonic()
  while time.monotonic()-begin<a.timeout:
   raw.extend(p.read(p.in_waiting or 1))
   if not values:
    offsets=[raw.find(m) for m in (b'DSI6',b'DSIF')];offsets=[i for i in offsets if i>=0]
    if not offsets:continue
    at=min(offsets)
   while at+64<=len(raw):
    frame=bytes(raw[at:at+64]);v=struct.unpack('<16I',frame)
    assert frame[:4] in (b'DSI6',b'DSIF') and v[1]==0x44530101 and zlib.crc32(frame[:60])==v[15]
    if last_sequence is not None:assert v[2]==(last_sequence+1)&0xffffffff
    last_sequence=v[2];values.append(v);at+=64
    if frame[:4]==b'DSIF' and v[3]==31 and v[11]==a.sequence and v[12]&0x3fff==(a.threshold<<6)|MODES[a.mode]:
     assert v[13]==0,'Preprocessing sticky error';found=v;break
   if found:break
 finally:p.close()
 a.out.mkdir(parents=True,exist_ok=False);(a.out/'command.bin').write_bytes(b);(a.out/'actual_serial.bin').write_bytes(raw)
 x={'status':'PASS_ACTUAL_HCI01_SOURCE_FRAME_CONFIG_ACK' if found else 'FAIL_NO_MATCHED_HCI01_SOURCE_CONFIG_ACK',
  'mode':a.mode,'threshold':a.threshold,'command_sequence':a.sequence,'command_sha256':hashlib.sha256(b).hexdigest(),
  'raw_sha256':hashlib.sha256(raw).hexdigest(),'packet_count':len(values),'last_flow':found,
  'scope':'Actual command accepted at source frame, as observed by coherent FPGA status. Does not certify optical appearance or identify screen scanout timing. No programming/NVM/Flash/sensor I2C changes.'}
 (a.out/'result.json').write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8');print(json.dumps(x))
 if not found:raise SystemExit(1)
if __name__=='__main__':main()
