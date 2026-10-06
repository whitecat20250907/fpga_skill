"""Preview captured RGB24 without changing the raw evidence."""
import sys
import cv2
import numpy as np
from pathlib import Path

prefix, width, height = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
sources = [Path(prefix)] if prefix.endswith('.rgb') else [Path(prefix+'_'+kind+'.rgb') for kind in ('first','last')]
for source in sources:
    data = np.fromfile(source, dtype=np.uint8)
    assert len(data)==width*height*3, (source,len(data))
    rgb=data.reshape(height,width,3)
    preview=cv2.resize(rgb, (640, round(height*640/width)), interpolation=cv2.INTER_AREA)
    dest=source.with_suffix('.png')
    assert cv2.imwrite(str(dest), cv2.cvtColor(preview, cv2.COLOR_RGB2BGR))
    print(dest, dest.stat().st_size)
