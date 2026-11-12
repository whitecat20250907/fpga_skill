"""Measured face surface within the deployed HFT2 presentation capacity.

34 surface vertices remain available alongside both hands, 48 trace points
and the eye/screen projection. Additional measured detail uses only spare
capacity. This is a display LOD, not a replacement for the 478-point model.
"""
import math
from ui.face_geometry import relative_pixels
from ui.face_surface_topology import BASE, TRIANGLES

# Anatomical order: iris centres, eyelids, lips, brows, nose, cheeks, outline.
DETAIL = (468,473,160,158,153,144,385,387,373,380,78,308,0,17,
          63,105,66,296,334,293,6,4,2,98,327,50,280,101,330,
          103,54,21,127,93,58,136,150,176,148,377,400,379,365,
          288,323,356,251,284,332,469,470,471,472,474,475,476,477)
BASE_EDGES = (tuple((i,(i+1)%16,1) for i in range(16)) +
              tuple((start+i,start+(i+1)%4,3) for start in (16,20,25) for i in range(4)) +
              ((29,30,2),(31,32,2),(33,24,2),(24,27,1)))
DETAIL_LINES = ((33,160),(160,158),(158,133),(133,153),(153,144),(144,33),
                (362,385),(385,387),(387,263),(263,373),(373,380),(380,362),
                (70,63),(63,105),(105,66),(66,107),
                (336,296),(296,334),(334,293),(293,300),
                (61,78),(78,13),(13,308),(308,291),(61,17),(17,291),
                (168,6),(6,4),(4,1),(1,2),(98,2),(2,327))


def surface(raw, vertex_budget=82, edge_budget=86, triangle_budget=56):
    if len(raw)<468 or vertex_budget<34 or edge_budget<len(BASE_EDGES) or triangle_budget<len(TRIANGLES):
        raise ValueError('face surface capacity/source')
    # Validate all measured source points before selecting the display subset.
    measured=relative_pixels(raw)
    indices=list(BASE)
    indices.extend(i for i in DETAIL if i<len(raw) and i not in BASE)
    indices=indices[:vertex_budget]
    lookup={key:i for i,key in enumerate(indices)}
    points=[measured[i] for i in indices]
    edges=list(BASE_EDGES)
    # Iris-centre marks take precedence over optional fine contour strokes.
    edges.extend((lookup[i],lookup[i],3) for i in (468,473) if i in lookup)
    edges.extend((lookup[a],lookup[b],2) for a,b in DETAIL_LINES if a in lookup and b in lookup)
    edges=edges[:edge_budget]
    faces=[]
    for a,b,c in TRIANGLES:
        p,q,r=points[a],points[b],points[c]
        u=[q[i]-p[i] for i in range(3)];v=[r[i]-p[i] for i in range(3)]
        normal=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
        length=math.sqrt(sum(n*n for n in normal))
        if normal[2]>0:normal=[-n for n in normal]
        light=max(0.,sum(n*l for n,l in zip(normal,(-.4,-.55,-.733)))/max(length,1e-12))
        shade=min(3,max(0,round(3*(.18+.82*light))))
        # Match the raster's oblique camera; render farther patches first.
        depth=sum(.43359375*points[i][0]+.8984375*points[i][2] for i in (a,b,c))/3
        faces.append((depth,(a,b,c,shade)))
    triangles=[row for _,row in sorted(faces,key=lambda item:item[0],reverse=True)]
    return points,edges,triangles
