"""Deterministic RGB files and manifests for physical PCIe roundtrips."""
from pathlib import Path
import hashlib,json
import numpy as np
root=Path(__file__).resolve().parents[1]/'evidence'
entries=[]
for w,h in [(1280,720),(1920,1080)]:
    x=np.arange(w,dtype=np.uint32)[None,:]
    y=np.arange(h,dtype=np.uint32)[:,None]
    # Position-varying channels catch RGB permutations and row/word shifts.
    a=np.empty((h,w,3),dtype=np.uint8)
    a[:,:,0]=(x*13+y*7)%256
    a[:,:,1]=(x*3+y*17)%256
    a[:,:,2]=(x*19+y*5)%256
    p=root/f'pattern_{w}x{h}.rgb';p.write_bytes(a.tobytes())
    entries.append(dict(path=p.name,width=w,height=h,bytes=p.stat().st_size,
                        sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
(root/'rgb_patterns.json').write_text(json.dumps(entries,indent=2)+'\n')
print(json.dumps(entries))
