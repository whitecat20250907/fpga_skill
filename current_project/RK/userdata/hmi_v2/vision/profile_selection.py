"""Invalidate only the abandoned/selected profile; retain the other user's calibration."""
def select_profile(profiles,previous,calibration,track,invalidate=False):
    # Single-person selection deliberately uses None. Re-selecting that same
    # stream must not drop its already fitted calibration.
    if previous==track and not invalidate and calibration is not None:return calibration
    if previous is not None:
        if invalidate:profiles.pop(previous,None)
        else:profiles[previous]=calibration
    if invalidate:profiles.pop(track,None)
    return profiles.get(track)
