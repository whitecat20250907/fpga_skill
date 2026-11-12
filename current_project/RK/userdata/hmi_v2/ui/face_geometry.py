"""Convert FaceInfo pixel XYZ to relative display XYZ without new inference."""
import math


def relative_pixels(points):
    # geometry_array scales x/z by image width and y by image height already.
    # All three axes therefore have pixel units: use ONE common scale so face
    # proportions and depth survive, then let the viewport perform its fit.
    if not points or any(len(p) != 3 or any(
            type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 32768
            for v in p) for p in points):
        raise ValueError('finite pixel XYZ')
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    span = max(high[i] - low[i] for i in range(3))
    if span <= 1e-8:
        raise ValueError('degenerate pixel XYZ')
    center = [(low[i] + high[i]) / 2 for i in range(3)]
    return [[(p[i] - center[i]) / span for i in range(3)] for p in points]
