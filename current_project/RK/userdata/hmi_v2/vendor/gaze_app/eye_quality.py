"""Shared eye validity policy. No fabricated EAR threshold or fixed openness."""
import math

def eyes_ready(face, settings):
    threshold=settings.get('eye_ear_threshold')
    if threshold is None:
        threshold=float(settings['eye_openness_threshold'])
        values=(face.left_eye_openness,face.right_eye_openness)
    else:
        threshold=float(threshold)
        if not math.isfinite(threshold) or not 0<=threshold<=1:
            raise ValueError('eye_ear_threshold must be finite in [0,1], or None for legacy area')
        values=(getattr(face,'left_eye_ear',None),getattr(face,'right_eye_ear',None))
    return bool(all(v is not None and math.isfinite(v) and v>threshold for v in values))
