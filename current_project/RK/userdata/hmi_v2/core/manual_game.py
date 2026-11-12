"""Bounded browser input to the current native game window."""
import math
from .manual_demo import STATES

KEYS=('F1','space','Return','Tab','Escape')

def permitted(name,gesture,context,state):
    return gesture=='console' and context=='GAME' and name in ('game.web_click','game.web_key') and state in STATES

def validate(args):
    if not isinstance(args,dict):raise ValueError('game input')
    if type(args.get('window')) is not int or not 0<args['window']<2**32:raise ValueError('window')
    rect=args.get('rect')
    if not isinstance(rect,list) or len(rect)!=4 or any(type(n) is not int for n in rect) or not all(0<v<=8192 for v in rect[2:]):raise ValueError('geometry')
    if type(args.get('frame_ns')) is not int or args['frame_ns']<=0:raise ValueError('frame age')
    if args.get('kind')=='click':
        if args.get('button') not in (1,3) or type(args.get('button')) is not int:raise ValueError('button')
        if any(type(args.get(k)) not in (float,int) or not math.isfinite(args[k]) or not 0<=args[k]<=1 for k in ('x','y')):raise ValueError('position')
    elif args.get('kind')!='key' or args.get('key') not in KEYS:raise ValueError('key')
    return args
