"""Damage for the unchanged legacy gaze renderer; coordinates are HDMI pixels."""
def regions(phase,size,preview_shape,old_pointer,pointer,font_height):
    w,h=map(int,size)
    if phase in ('CALIBRATE','VALIDATE'):
        return [] # Target/phase changes force a full presentation in the caller.
    out=[(0,70,w,115),(0,225,w,font_height+12)]
    if preview_shape is not None:
        if phase in ('PREVIEW','FAILED'):
            width=min(960,int(w*.62),int(h*.9))
            height=round(width*preview_shape[0]/preview_shape[1])
            out.append(((w-width)//2,(h-height)//2,width,height))
        elif phase=='TRACK':out.append((w-330,10,320,180))
    if phase=='TRACK':
        for point in (old_pointer,pointer):
            if point is not None:
                x,y=map(int,point);out.append((x-24,y-24,49,49))
    return out
