"""Palm visibility for static gestures; fingertips may cross the image edge."""
import math


def usable_palm(points):
    if len(points)!=21 or any(len(p)<2 or not all(math.isfinite(v) for v in p[:2]) for p in points):
        return False
    palm=[points[i] for i in (0,5,9,13,17)]
    return (all(-.05<=p[0]<=1.05 and -.05<=p[1]<=1.05 for p in palm)
            and sum(-.08<=p[0]<=1.08 and -.08<=p[1]<=1.08 for p in points)>=16)
