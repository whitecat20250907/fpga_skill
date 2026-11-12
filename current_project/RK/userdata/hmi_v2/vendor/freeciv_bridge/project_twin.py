"""Small CPU renderer of measured 3D hand/face features; no 3D game engine.

The palm surface and finger thickness are visualization geometry. Joint
positions are the model's measured/predicted XYZ, never an idle animation.
"""
import math,time
from functools import lru_cache
from project_features import HAND_EDGES,FACE_OVAL,LEFT_EYE,RIGHT_EYE,face_points_isotropic

def project(points,center,scale,yaw=-.45,pitch=.15):
    cy,sy=math.cos(yaw),math.sin(yaw);cp,sp=math.cos(pitch),math.sin(pitch)
    out=[]
    for x,y,z in points:
        a=cy*x+sy*z;b=-sy*x+cy*z;c=cp*y-sp*b;depth=sp*y+cp*b
        perspective=1/max(.5,1+depth*.7)
        out.append((center[0]+a*scale*perspective,center[1]+c*scale*perspective,depth))
    return out

def fit_projected(points,box,yaw=-.45,pitch=.15):
    """Fit all measured joints inside their panel, without clipping fingers."""
    pts=project(points,(0,0),1,yaw,pitch)
    left,top,right,bottom=box
    lo_x=min(p[0] for p in pts);hi_x=max(p[0] for p in pts)
    lo_y=min(p[1] for p in pts);hi_y=max(p[1] for p in pts)
    scale=min((right-left)/max(hi_x-lo_x,1e-5),(bottom-top)/max(hi_y-lo_y,1e-5))
    cx=(left+right)/2;cy=(top+bottom)/2
    return [(cx+(x-(lo_x+hi_x)/2)*scale,cy+(y-(lo_y+hi_y)/2)*scale,z) for x,y,z in pts]

@lru_cache(maxsize=2)
def _font(size):
    from PIL import ImageFont
    from pathlib import Path
    fonts=[Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')]
    path=next((p for p in fonts if p.is_file()),None)
    return ImageFont.truetype(str(path),size) if path else ImageFont.load_default()

@lru_cache(maxsize=8)
def _background(fixture,left_valid,right_valid):
    from PIL import Image,ImageDraw
    image=Image.new('RGB',(1024,600),'#09111e');d=ImageDraw.Draw(image)
    font=_font(18);small=_font(14)
    def text(x,y,t,color='#dbe8f5',f=font):d.text((x,y),t,font=f,fill=color)
    d.rectangle((0,0,1024,78),fill='#112039');text(24,14,'无接触交互 · 手 / 头 / 双眼数字孪生')
    text(24,46,'原 PCIe 摄像头  ·  复用现有特征  ·  独立质量与时效门控',f=small)
    text(780,22,'离线夹具 / 非实时' if fixture else '实时特征监视','#ffcc80' if fixture else '#41dec0')
    d.rounded_rectangle((20,96,594,438),14,fill='#14243a');d.rounded_rectangle((612,96,1004,438),14,fill='#14243a')
    text(38,108,'手部三维关节 / 掌面');text(632,108,'头部姿态 / 面部特征')
    d.rounded_rectangle((20,456,1004,568),12,fill='#102a32');text(38,469,'双眼 / 注视质量')
    text(38,504,'左眼：'+('原始特征已接收' if left_valid else '未跟踪'),f=small)
    text(268,504,'右眼：'+('原始特征已接收' if right_valid else '未跟踪'),f=small)
    text(500,504,'控制：遵循原标定、眨眼及置信门控',f=small)
    text(38,538,'三维表面为关节驱动的示意几何；不宣称人体测量精度或手眼曝光同步。',f=small)
    text(24,578,'丢跟踪即失效 · 不保持假姿态 · 普通视线不执行游戏操作',f=small)
    return image

def render(state,now_ns=None,fixture=False):
    from PIL import ImageDraw
    now=time.monotonic_ns() if now_ns is None else now_ns
    fixture=fixture or any(p.get('fixture',False) for p in state.samples.values())
    hand=state.fresh('hand',now);face=state.fresh('face',now)
    groups=face.get('groups',{}) if face and face['valid'] else {}
    left_valid=bool(face and face['valid'] and groups.get('left_eye',True))
    right_valid=bool(face and face['valid'] and groups.get('right_eye',True))
    image=_background(fixture,left_valid,right_valid).copy();d=ImageDraw.Draw(image)
    font=_font(18);small=_font(14)
    def text(x,y,t,color='#dbe8f5',f=font):d.text((x,y),t,font=f,fill=color)
    if hand and hand['hands']:
        for index,item in enumerate(hand['hands']):
            if item['confidence']<.6:continue
            world=item['world'];origin=world[0]
            rel=[[p[i]-origin[i] for i in range(3)] for p in world]
            box=(90,180,526,375) if len(hand['hands'])==1 else (55+index*265,180,285+index*265,375)
            pts=fit_projected(rel,box)
            palm=[pts[i][:2] for i in (0,5,9,13,17)];d.polygon(palm,fill='#b88464',outline='#f2bf93')
            for a,b in sorted(HAND_EDGES,key=lambda edge:(pts[edge[0]][2]+pts[edge[1]][2])/2,reverse=True):
                x,y,_=pts[a];xx,yy,_=pts[b]
                d.line((x,y,xx,yy),fill='#ebba92',width=13);d.ellipse((xx-5,yy-5,xx+5,yy+5),fill='#ffe0b6',outline='#40d9c3')
            text(42+index*270,398,f"{item['side']} · {item.get('gesture') or '未分类'}",f=small)
        text(40,140,f"21 点 · 源帧年龄 {(now-hand['timestamp_ns'])/1e6:.0f} ms",'#68dcc8',small)
    else:text(180,254,'手部未跟踪 / 数据过期','#92a7c2')
    if face and face['valid']:
        points=face_points_isotropic(face);nose=points[1];rel=[[p[i]-nose[i] for i in range(3)] for p in points]
        pts=fit_projected(rel,(664,184,962,374),yaw=-.3)
        oval=[pts[i][:2] for i in FACE_OVAL];d.polygon(oval,fill='#3a526c',outline='#7199bb')
        chains=[(1,4,6,168,10),(61,13,291,14,61)]
        if left_valid:chains.append(LEFT_EYE)
        if right_valid:chains.append(RIGHT_EYE)
        for chain in chains:
            d.line([pts[i][:2] for i in chain],fill='#5ee2cd',width=2)
        for iris in (468,473):
            side='left' if iris==468 else 'right'
            if iris<len(pts) and groups.get(side+'_iris',left_valid if side=='left' else right_valid):
                x,y,_=pts[iris];d.ellipse((x-4,y-4,x+4,y+4),fill='#ffd58b')
        text(632,140,f"面部 {len(points)} 点 · {(now-face['timestamp_ns'])/1e6:.0f} ms",'#68dcc8',small)
        text(632,389,f"左眼 {face['eye_left']:.2f}   右眼 {face['eye_right']:.2f}",f=small)
    else:text(668,255,'面部未跟踪 / 数据过期','#92a7c2')
    return image
