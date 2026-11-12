"""Short actionable feedback, separate from the camera preview."""
from ui.feedback import feedback


def card(state,receipt=''):
    info=feedback(state);title=info['title'];hint=info['hint']
    if state.get('shortcut'):title='待确认 · '+state['shortcut'].get('label','手势')
    zoom=state.get('zoom_control',{})
    if zoom.get('active'):title='双指缩放 · '+str(round(zoom.get('ratio',1),2))+'×';hint='放下食指保持 · 再次举起继续'
    elif zoom.get('preparing'):title='双指准备 '+str(zoom.get('frames',0))+'/3';hint='两只食指保持举起'
    return dict(title=title,hint=hint,receipt=receipt,progress=info['progress'],person=info['person'])


def placement(width,height,panel_width,panel_height,state):
    x=width-panel_width-24;y=height-panel_height-24
    target=state.get('calib',{}).get('target') if state.get('state')=='CALIBRATING' else None
    if isinstance(target,(list,tuple)) and len(target)>=2:
        tx,ty=target[:2]
        if 0<=tx<=1 and 0<=ty<=1:tx*=width;ty*=height
        if x-48<=tx<=width and y-48<=ty<=height:x=24
    return max(0,x),max(0,y)
