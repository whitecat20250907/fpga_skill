"""Pause does not consume tracker lifetime; resumption still detects real ROIs.

The frozen tracker resets IDs after a 0.5s source gap. For an intentional
suspension only, retain its spatial matching seeds and force a fresh detector
pass. New/ambiguous/moved faces still receive new IDs under the original matcher.
No source timestamps or face observations are rewritten.
"""


def resume_spatial_track(aligner, activation_ns, source_ns):
    pipeline = getattr(aligner, 'pipeline', None)
    last = getattr(pipeline, 'last_stamp', None)
    if last is None or not activation_ns:
        return False
    if last*1e9 < activation_ns <= source_ns and source_ns-last*1e9 > 500_000_000:
        pipeline.last_stamp = None
        pipeline.last_detection = -float('inf')
        return True
    return False
