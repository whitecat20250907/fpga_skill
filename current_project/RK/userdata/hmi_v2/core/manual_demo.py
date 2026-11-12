"""Explicit computer commands may operate the teaching canvas without gaze."""
ACTIONS=frozenset('demo.'+s for s in ('next','cancel','focus','snap','reset','rotate','activate'))
STATES=frozenset(('STANDBY','PRESENT','ONBOARD','IDLE','POINTING'))

def permitted(name,gesture,context,state):
    return gesture=='console' and context=='DEMO' and name in ACTIONS and state in STATES
