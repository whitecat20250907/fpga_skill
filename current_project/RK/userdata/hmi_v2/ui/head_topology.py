"""Fixed surface connectivity; all runtime XYZ comes from detected landmarks.

Topology derived against Google MediaPipe canonical coordinates (Apache-2.0).
See ../THIRD_PARTY_NOTICES.md. No canonical coordinates are used at runtime.
"""
LANDMARK_INDICES = (10, 109, 67, 162, 234, 132, 172, 149, 152, 378, 397, 361, 454, 389, 297, 338, 33, 159, 133, 145, 362, 386, 263, 374, 1, 61, 13, 291, 14)
SURFACE_TRIANGLES = ((0, 15, 20), (1, 0, 18), (2, 1, 17), (3, 2, 16), (4, 3, 16), (4, 16, 19), (5, 4, 19), (5, 19, 25), (6, 5, 25), (7, 6, 25), (7, 25, 28), (8, 7, 28), (9, 8, 28), (10, 9, 27), (11, 10, 27), (12, 11, 23), (13, 12, 22), (14, 13, 22), (15, 14, 21), (16, 2, 17), (17, 1, 18), (18, 0, 20), (18, 20, 24), (19, 18, 24), (19, 24, 25), (20, 15, 21), (20, 23, 24), (21, 14, 22), (22, 12, 23), (23, 11, 27), (24, 23, 27), (25, 24, 26), (26, 24, 27), (27, 9, 28))
OUTLINE_EDGES = tuple((i,(i+1)%16,2) for i in range(16))
FEATURE_EDGES = tuple((start+i,start+(i+1)%4,3 if start<24 else 2)
                      for start in (16,20,25) for i in range(4))

def face_surface(landmarks):
    if len(landmarks)<468:
        raise ValueError("dense face landmarks required")
    return ([landmarks[i] for i in LANDMARK_INDICES],
            list(OUTLINE_EDGES+FEATURE_EDGES),
            [(a,b,c,1) for a,b,c in SURFACE_TRIANGLES])
