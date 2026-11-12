import math

VERSION = 1
TOPICS = frozenset(('app.targets','frame.meta','vision.face','vision.gaze','vision.hands','vision.stroke',
                   'hmi.state','hmi.action','hmi.ack','cmd.gaze','cmd.system','cmd.operator','ui.scene','sys.metrics'))
EVENTS = frozenset(('vision.stroke','hmi.action','hmi.ack','cmd.gaze','cmd.system','cmd.operator'))

def validate(topic, message):
    if topic not in TOPICS or not isinstance(message, dict) or message.get('v') != VERSION:
        raise ValueError('Invalid topic/schema')
    for key in ('src_ns','seq','pub_ns','epoch'):
        if type(message.get(key)) is not int or message[key] < 0:
            raise ValueError('Invalid '+key)
    if not message['epoch'] or not message['src_ns'] or message['pub_ns'] < message['src_ns']:
        raise ValueError('Invalid epoch/time')
    if message['epoch'] >= 2**64:
        raise ValueError('Epoch exceeds uint64')
    return message

def finite_xy(value):
    return isinstance(value,(list,tuple)) and len(value)==2 and all(type(x) in (float,int) and math.isfinite(x) for x in value)
