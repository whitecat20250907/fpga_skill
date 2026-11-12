"""Display-only fit from vendor app_scene; new disjoint viewport ABI UI11."""
import math
from hft2_wire import project_q4
BOXES=((24, 82, 131, 207), (140, 82, 247, 207), (112, 28, 159, 75), (284, 44, 463, 145), (284, 160, 463, 219))

def _points(rows,count=None):
    if count is not None and len(rows)!=count:raise ValueError('point count')
    if not rows or any(len(p)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>100 for x in p) for p in rows):
        raise ValueError('finite XYZ')
    return rows


def add_xyz(scene,group,points,edges,triangles,source_age):
    """Fit actual relative XYZ to the new panel, preserving hardware projection."""
    _points(points)
    left,top,right,bottom=BOXES[group]
    projected=[(.8984375*x-.43359375*z,.98828125*y-.1484375*(.43359375*x+.8984375*z)) for x,y,z in points]
    dx=max(p[0] for p in projected)-min(p[0] for p in projected)
    dy=max(p[1] for p in projected)-min(p[1] for p in projected)
    if max(dx,dy)<1e-8:raise ValueError('degenerate XYZ')
    # Four logical pixels are reserved for the actual shaded hand capsule.
    pad=6 if group<2 else 3
    scale=min((right-left-2*pad)/max(dx,1e-8),(bottom-top-2*pad)/max(dy,1e-8))
    quantized=[tuple(round(float(v)*scale*16) for v in p) for p in points]
    if any(not -32768<=v<=32767 for p in quantized for v in p):raise ValueError('Q4 overflow')
    qp=[project_q4(p,group) for p in quantized]
    offset=((left+right-min(p[0] for p in qp)-max(p[0] for p in qp))//2,
            (top+bottom-min(p[1] for p in qp)-max(p[1] for p in qp))//2)
    if any(not left+pad-1<=p[0]+offset[0]<=right-pad+1 or not top+pad-1<=p[1]+offset[1]<=bottom-pad+1 for p in qp):
        raise ValueError('projected panel fit')
    start=len(scene.vertices)
    scene.vertices.extend((group,*p) for p in quantized)
    scene.edges.extend((start+a,start+b,shade) for a,b,shade in edges)
    scene.triangles.extend((start+a,start+b,start+c,shade) for a,b,c,shade in triangles)
    scene.valid|=1<<group;scene.ages[group]=source_age;scene.offsets[group]=offset


def add_flat(scene,group,xy,edges,source_age):
    """Absolute logical screen/trace XY: never yaw/pitch or re-fit each frame."""
    left,top,right,bottom=BOXES[group]
    if not xy or any(len(p)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p) or
            not left<=p[0]<=right or not top<=p[1]<=bottom for p in xy):raise ValueError('flat viewport')
    start=len(scene.vertices)
    scene.vertices.extend((group,round(x*16),round(y*16),0) for x,y in xy)
    scene.edges.extend((start+a,start+b,shade) for a,b,shade in edges)
    scene.valid|=1<<group;scene.ages[group]=source_age


