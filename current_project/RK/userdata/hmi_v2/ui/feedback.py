"""One interaction description shared by HDMI and the browser console."""
GESTURES = {'Pointing_Up': '伸食指', 'Closed_Fist': '握拳', 'Thumb_Down': '拇指向下',
            'Victory': '比 V', 'Thumb_Up': '竖拇指', 'Open_Palm': '张开手掌', 'ILoveYou': '菜单手势'}


def feedback(state):
    phase = state.get('state', 'BOOT')
    actor = state.get('participants', {}).get('active', 1)
    labels = {'BOOT': ('正在连接', '等待摄像头和模型就绪'),
              'STANDBY': ('已暂停' if state.get('estop') else '手势就绪 · 眼控休眠', '短按 MENU 恢复' if state.get('estop') else '握拳准备 · MENU 基础展示'),
              'PRESENT': ('已看到你', '正在检查位置'),
              'ONBOARD': ('手势就绪 · 眼控未标定', '握拳准备 → 伸指画轨迹 / 其它手势'),
              'CALIBRATING': ('请看屏幕上的目标', '张掌保持0.3秒取消'),
              'IDLE': ('手势就绪 · 眼控休眠', '握拳准备 → 伸指画轨迹 / 其它手势'),
              'POINTING': ('目标预览', '握拳确认 · 拇指向下取消'),
              'MENU': ('系统菜单', '比 V 下一项 · 握拳选择 · 拇指向下返回'),
              'WRITING': ('轨迹书写', '握拳 → 伸指 → 倒计时 → 画轨迹 → 握拳结束'),
              'DEGRADED': ('交互暂停', '等待恢复：'+ '、'.join(state.get('health', {}).get('broken', [])))}
    title, hint = labels.get(phase, labels['BOOT'])
    calib=state.get('calib',{})
    if phase=='CALIBRATING' and calib.get('phase')=='VALIDATE':
        title,hint='正在独立评测',f"请看目标 {calib.get('point_i',0)+1}/{calib.get('total',20)} · 张掌保持0.3秒取消"
    elif phase=='CALIBRATING' and state.get('calibrated') and calib.get('phase') in ('READY','RESULT',None):
        title,hint='标定完成','竖拇指或按确认使用 · 比 V 开始评测'
        if calib.get('phase')=='RESULT':title,hint='评测已完成','查看成绩 · 确认使用 · 比 V 再测'
    if state.get('shortcut'):
        title,hint='快捷操作待确认','右手握拳执行 · 拇指向下取消'
    p = state.get('participants', {}).get('registration')
    if p:
        title = f"登记第 {p['slot']} 人"
        hint = '比 V 切换候选 · 握拳确认 · 拇指向下取消' if p['choices'] else '请让待登记的人进入画面，再重新选择登记'
    stroke = state.get('writing', {})
    if phase == 'WRITING':
        s = stroke.get('state', 'IDLE')
        title, hint = {'IDLE': ('先握拳准备', '伸指后保持 0.3 秒开始记录'),
                       'ARMED': ('已就绪，请伸食指', '保持食指，等待倒计时'),
                       'COUNTDOWN': ('即将开始', f"倒计时 {stroke.get('remaining_s', .3):.1f} 秒，请保持伸指"),
                       'REC': ('正在记录轨迹', '右手握拳结束，识别成功直接执行'),
                       'RESULT': ('轨迹已结束', '稍候查看分类结果，松手后可再画')}.get(s, (title, hint))
    gesture = state.get('gesture', {})
    progress = min(1., max(0., gesture.get('progress', 0)))
    if gesture.get('phase')=='ARMED' and phase!='WRITING':
        title,hint='手势识别已开启','伸食指切换轨迹；其它姿势继续手势识别'
    elif gesture.get('phase')=='ARMING' and phase!='WRITING':
        title,hint='握拳准备中','保持片刻，出现已准备后变换手势'
    elif progress > 0 and phase!='WRITING':
        hint = GESTURES.get(gesture.get('name'), '手势')+f'识别中 {round(progress*100)}% · 松开可取消'
    if phase == 'POINTING' and not state.get('cursor', {}).get('valid'):
        hint = '视线暂不可用，已暂停确认'
    pending=state.get('stroke_pending')
    if pending:
        from core.bindings import label
        side='左手' if pending['confirm_side']=='Left' else '右手'
        title='轨迹 '+pending['label']+' → '+label(pending['target'])
        hints={'waiting_hand':'请将'+side+'张掌入镜，然后握拳确认',
               'release_first':side+'先松开，再握拳确认',
               'prepare_palm':side+'张掌已看到，正在准备',
               'make_fist':side+'已就绪，请握拳确认',
               'holding_fist':side+'握拳确认中，请保持',
               'holding_cancel':side+'拇指向下，正在取消',
               'unrecognized':side+'姿势未识别，请正对摄像头握拳'}
        hint=hints.get(pending.get('reason'),side+'松开后握拳确认')+' · 拇指向下取消'
        progress=pending.get('progress',0.)
    intent=state.get('calibration_intent')
    if intent and not state.get('participants',{}).get('registration'):
        title='准备标定第 '+str(intent['slot'])+' 人'
        hint='请居中睁眼，稳定后开始 · 拇指向下取消'
    session=state.get('target_session',{})
    if phase=='POINTING':
        title='眼控接管 · '+session.get('target',{}).get('label','正在选目标')
        hand=session.get('hand_status')
        side={'Left':'左手','Right':'右手'}.get(session.get('hand_side'),'操作手')
        hint=side+'握拳结束眼控 · 不会自动点击'
        if hand=='choose_hand':hint='右手张开后握拳，结束眼控并锁定目标'
        elif hand=='missing':hint='请让'+side+'回到画面，张开后握拳结束眼控'
        elif hand=='release':hint=side+'先松开，再握拳结束眼控'
        elif gesture.get('name')=='Closed_Fist' and progress>0:hint=side+f'锁定中 {round(progress*100)}%'
        if not state.get('cursor',{}).get('valid'):
            vote=session.get('vote',{})
            hint+=('；稳定目标 '+str(min(vote.get('streak',0),vote.get('required_streak',2)))+'/'+str(vote.get('required_streak',2)) if vote.get('samples') else '；等待目标出现，握拳仍可结束')
    elif session.get('phase')=='LOCKED' and phase in ('IDLE','STANDBY','ONBOARD') and not state.get('shortcut') and not gesture:
        title='已锁定 · '+session.get('target',{}).get('label','目标')
        hint='右手张掌→握拳点击；任一手张掌→拇指向下撤回'
        if not session.get('target'):
            title='位置已保持';hint='视图已切换，眼控选择新目标；旋转、缩放可继续'
    previous=state.get('last_action')
    if previous and phase in ('IDLE','STANDBY','ONBOARD') and not state.get('shortcut') and session.get('phase')!='LOCKED':
        title='上次 · '+previous['label']
        hint='任一手：张掌→握拳重复；张掌→拇指向下撤回'
    zoom=state.get('zoom_control',{})
    if zoom.get('active'):
        title,hint='双指缩放',f"{zoom.get('ratio',1.):.2f}× · 放下手指保持"
        progress=1.
    elif zoom.get('preparing'):
        frames=min(3,zoom.get('frames',0))
        title,hint='双指准备',f'{frames}/3'
        progress=frames/3
    context={'DESKTOP':'桌面','GAME':'游戏','DEMO':'医学演示','BASIC':'基础展示'}.get(state.get('context'),'')
    person=f'第 {actor} 人' if state.get('people') == 'dual' else '单人模式'
    return {'title': title, 'hint': hint, 'progress': progress,
            'person': person+(' · '+context if context else ''),
            'toast': state.get('toast', '')}
