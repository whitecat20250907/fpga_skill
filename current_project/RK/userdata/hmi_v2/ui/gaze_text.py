"""Keep the original renderer while replacing obsolete private-app controls."""
import re


def interaction_text(text,state):
    phase=state.get('state','BOOT')
    if '处理 ' in text and 'FPS' in text and '停留点击' in text:
        timing=re.search(r'处理\s+([0-9.]+)\s+FPS',text)
        mode={'POINTING':'眼控已唤醒','WRITING':'记录手势轨迹','CALIBRATING':'标定 / 评测中',
              'MENU':'选择菜单','DEGRADED':'服务异常，动作已暂停'}.get(phase,'等待操作')
        return f"眼脸处理 {timing[1] if timing else '—'} FPS · {mode} · 执行结果见右下角"
    if text.startswith('输出：'):
        app={'DESKTOP':'桌面','GAME':'游戏','DEMO':'医学演示','BASIC':'基础展示'}.get(state.get('context'),'等待连接')
        person=f"第 {state.get('participants',{}).get('active',1)} 人" if state.get('people')=='dual' else '单人'
        return f"{app} · {person} · "+('已完成个人标定' if state.get('calibrated') else '尚未完成个人标定')
    if text.startswith('保持头部稳定、眼睛睁开'):
        if phase=='BOOT':return '正在连接交互引擎，动作暂不可用；请等待右下角状态更新。'
        if phase=='STANDBY':return '请让完整人脸进入画面；检测稳定后按右下角提示操作。'
        if phase=='MENU':return '比 V 切换选项，握拳确认；实体键用于应用和人数模式切换。'
        return '居中睁眼，等待距离检查通过；竖拇指或按确认开始标定。'
    return text
