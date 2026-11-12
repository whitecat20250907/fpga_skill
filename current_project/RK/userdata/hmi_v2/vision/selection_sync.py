"""Reconcile a surviving gaze worker with the current engine selection."""
from core.clock import fresh

FACE_DETECTION_THRESHOLD=.35

def release_unselected(state,selected,epoch,now,last_command_ns=0):
    if selected is None or state.get('epoch')!=epoch or not fresh(state.get('src_ns'),350,now):return False
    if state.get('src_ns',0)<last_command_ns or state.get('state')=='CALIBRATING' or state.get('calibrated'):return False
    people=state.get('participants',{});slots=people.get('slots',{})
    active=people.get('active')
    if active is None or str(active) not in slots:return False
    return slots[str(active)].get('track_id') is None
