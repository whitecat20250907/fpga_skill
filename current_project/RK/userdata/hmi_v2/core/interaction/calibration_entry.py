"""Shared readiness of the selected real person; never queues calibration."""
from core.clock import fresh


def readiness(face_message, people, now,policy=None):
    policy=policy or {}
    result={'distance':False,'centered':False,'eyes':False}
    if not fresh(face_message.get('src_ns'),350,now):return result,None,'请让完整人脸进入画面'
    faces=[f for f in face_message.get('faces',[]) if f.get('valid')]
    primary=next((f for f in faces if f.get('primary')),None)
    if people.pending:return result,None,'请先确认登记候选人'
    if not faces:return result,None,'请让完整人脸进入画面'
    selected=people.slots[people.active]
    if people.mode=='dual' and selected is None:return result,None,f'请先登记第 {people.active} 人'
    if not primary or primary.get('track_id') is None:return result,None,'请让完整人脸进入画面'
    if people.mode=='dual' and primary['track_id']!=selected:return result,None,'等待已选择的使用者入画'
    box=primary.get('face_rect',[])
    if len(box)!=4:return result,None,'人脸位置暂不可用'
    result.update(distance=policy.get('min_width',.12)<=box[2]/640<=policy.get('max_width',.6),
        centered=abs((box[0]+box[2]/2)/640-.5)<(.4 if people.mode=='dual' else policy.get('center_x',.35)) and abs((box[1]+box[3]/2)/360-.5)<policy.get('center_y',.3),
        eyes=bool(primary.get('can_gaze')))
    key=(people.mode,people.active,primary['track_id'])
    reason='请调整距离' if not result['distance'] else '请将人脸移到提示区域' if not result['centered'] else '请保持双眼清晰可见' if not result['eyes'] else ''
    return result,key,reason
