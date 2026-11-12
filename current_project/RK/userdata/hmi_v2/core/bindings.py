"""Allowlisted application bindings. Commands never contain shell or key strings."""
from copy import deepcopy

CONTEXTS=('DESKTOP','GAME','DEMO','BASIC')
SHOWCASE={'0':'system.app_demo','L':'system.app_game','L_rev':'system.app_basic','M':'system.single','W':'system.dual'}
STATIC=('Victory','Thumb_Up')
STROKES=('0','L','L_rev','L_up','L_rev_up','M','W','Z')
SYSTEM=('app_basic','menu','app_demo','app_game','app_desktop','mode_next','eye_takeover','calibrate','calibrate_person1','calibrate_person2','validate','single','dual','person1','person2','estop')
APP={'BASIC':(), 'DESKTOP':('next','cancel'), 'GAME':('next','cancel','end'),
     'DEMO':('next','cancel','reset','rotate')}
LABELS={'system.app_basic':'基础功能展示','system.menu':'系统菜单','system.pointer':'眼控接管','system.eye_takeover':'眼控接管','demo.click':'点击目标（结构自动聚焦）','game.click':'点击锁定目标','system.calibrate':'标定当前人','system.validate':'评测当前人',
        'system.app_demo':'启动医学演示','system.app_game':'启动游戏','system.app_desktop':'切换桌面',
        'system.mode_next':'切换下一个应用','system.calibrate_person1':'第一人登记 / 标定','system.calibrate_person2':'第二人登记 / 标定',
        'game.web_click':'游戏鼠标输入','game.web_key':'游戏按键输入',
        'system.single':'切回单人','system.dual':'切换双人','system.person1':'选择第一人',
        'system.person2':'选择第二人','system.estop':'暂停交互','demo.next':'下一页',
        'demo.cancel':'上一页','demo.zoom':'双指缩放','demo.focus':'聚焦',
        'demo.rotate':'旋转三维','demo.activate':'医学目标操作','demo.snap':'眼控接管','demo.reset':'复位视图','game.next':'游戏下一项',
        'game.cancel':'游戏取消','game.end':'结束回合','desktop.next':'桌面下一项',
        'desktop.cancel':'桌面取消','demo.wake':'预览目标','demo.confirm':'确认目标',
        'desktop.wake':'开始眼控','desktop.click':'点击锁定目标','game.wake':'预览游戏目标',
        'game.confirm':'确认游戏目标'}

def label(action):return LABELS.get(action,'操作')

def options(context):
    prefix={'DESKTOP':'desktop','GAME':'game','DEMO':'demo','BASIC':'basic'}[context]
    return ['']+['system.'+v for v in SYSTEM]+[prefix+'.'+v for v in APP[context]]

def defaults(config):
    return {'static':{c:{} for c in CONTEXTS},
            'stroke':{c:{k:ALIASES.get(v,v) for k,v in config.get('write_actions',{}).get(c,SHOWCASE if c=='BASIC' else {}).items()
                         if k in STROKES and ALIASES.get(v,v) in options(c)} for c in CONTEXTS}}

ALIASES={'demo.zoom_in':'','demo.zoom_out':'','demo.focus':'system.eye_takeover','demo.click':'system.eye_takeover','desktop.click':'system.eye_takeover','game.click':'system.eye_takeover','system.pointer':'system.eye_takeover','demo.snap':'system.eye_takeover'}

def validate(value):
    if not isinstance(value,dict) or set(value)!={'static','stroke'}:raise ValueError('bindings structure')
    value=deepcopy(value)
    for kind,keys in [('static',STATIC),('stroke',STROKES)]:
        if not isinstance(value[kind],dict):raise ValueError('contexts')
        if set(value[kind])==set(CONTEXTS)-{'BASIC'}:value[kind]['BASIC']=dict(SHOWCASE) if kind=='stroke' else {}
        if set(value[kind])!=set(CONTEXTS):raise ValueError('contexts')
        for context,rows in value[kind].items():
            if not isinstance(rows,dict) or len(rows)>len(keys):raise ValueError('binding count')
            for key,target in rows.items():
                target=ALIASES.get(target,target);rows[key]=target
                if key not in keys or target not in options(context):raise ValueError('binding target')
    return deepcopy(value)
