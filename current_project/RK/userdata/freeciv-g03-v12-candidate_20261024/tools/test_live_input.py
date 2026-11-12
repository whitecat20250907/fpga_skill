"""Exercise the actual board game's UDP safeguards on a fresh scenario.

This manual acceptance test moves the initial cavalry one tile. It does not
start a game, camera or model, reset a session, or simulate human inference.
"""
import argparse
import json
from pathlib import Path
import secrets
import socket
import time


class Link:
    def __init__(self):
        self.socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.socket.settimeout(.15)
        self.address=('127.0.0.1',29778)
        self.sequence=0

    def raw(self,text):self.socket.sendto(text.encode('ascii'),self.address)

    def state(self,timeout=1.5):
        limit=time.monotonic()+timeout
        nonce=secrets.token_hex(16);next_send=0.
        while time.monotonic()<limit:
            if time.monotonic()>=next_send:
                self.raw('query '+nonce);next_send=time.monotonic()+.2
            try:
                data,sender=self.socket.recvfrom(32768)
                prefix,echo,body=data.decode('ascii').split(' ',2)
                if sender==self.address and prefix=='state' and echo==nonce:return json.loads(body)
            except socket.timeout:pass
        raise RuntimeError('No actual game geometry/state reply')

    def event(self,name):
        self.sequence+=1;self.raw(f'event {self.sequence} {name}')
        deadline=time.monotonic()+1.5
        while True:
            time.sleep(.05);state=self.state()
            if int(state['last_event'])==self.sequence or time.monotonic()>=deadline:break
        if int(state['last_event'])!=self.sequence:raise RuntimeError('Event not acknowledged')
        return state

    def point(self,target,state,seconds=.28):
        width,height=state['map'][2:]
        stop=time.monotonic()+seconds
        while time.monotonic()<stop:
            self.raw(f"gaze {target['x']/width:.8f} {target['y']/height:.8f}")
            time.sleep(.035)


def need(condition,message):
    if not condition:raise RuntimeError(message)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    if a.output.exists():ap.error('Preserve prior live test evidence')
    link=Link();cases=[];result=dict(test='REAL_GAME_UDP_ACCEPTANCE',human_gaze_test=False,
                                    camera_or_inference_started=False,cases=cases)
    def record(name,**values):
        cases.append(dict(test=name,passed=True,**values))
    try:
        initial=link.state();result['initial']=initial
        need(initial['turn']==1 and initial['moves']==6 and not initial['awake'] and
             int(initial['last_event'])==0,'Fresh untouched initial cavalry scenario required')
        initial_unit=initial['unit']
        for _ in range(5):link.raw('gaze 0.5 0.5');time.sleep(.04)
        asleep=link.event('confirm')
        need(not asleep['awake'] and asleep['unit']==initial_unit and asleep['moves']==6,
             'Ordinary gaze/asleep confirmation unexpectedly changed an order')
        record('ordinary_gaze_and_asleep_confirm_do_not_order')

        awake=link.event('wake')
        need(awake['awake'] and awake['targets'],'Wake did not expose dynamic candidates')
        target=max((t for t in awake['targets'] if t['kind']==0),key=lambda t:t['x'])
        link.point(target,awake);time.sleep(.41)
        stale=link.event('confirm')
        need(stale['awake'] and stale['unit']==initial_unit and stale['moves']==6,
             'Stale coordinate confirmation executed an order')
        record('coordinates_older_than_350ms_rejected')

        link.point(target,awake);link.raw('gaze nan 0.5');time.sleep(.08)
        invalid=link.event('confirm')
        need(invalid['awake'] and invalid['unit']==initial_unit and invalid['moves']==6,
             'Invalid coordinate failed to invalidate prior sample')
        record('nonfinite_gaze_invalidates_previous_sample')

        cancelled=link.event('cancel')
        need(not cancelled['awake'],'Cancel did not sleep')
        next_state=link.event('next');unit=next_state['unit'];seq=link.sequence
        need(unit!=initial_unit,'Next did not change unit')
        link.raw(f'event {seq} next');link.raw(f'event {seq-1} next');time.sleep(.12)
        duplicate=link.state()
        need(duplicate['unit']==unit and int(duplicate['last_event'])==seq,
             'Duplicate or old event advanced unit')
        record('duplicate_and_old_events_rejected',sequence=seq,unit=unit)

        for text in ('event -1 next','event 18446744073709551616 next',
                     'event 18446744073709551615 unknown','event 999999 next trailing'):
            link.raw(text)
        time.sleep(.12);unchanged=link.state()
        need(unchanged['unit']==unit and int(unchanged['last_event'])==seq,
             'Malformed event poisoned the sequence')
        following=link.event('next')
        need(following['unit']!=unit,'Valid event after malformed traffic was blocked')
        record('signed_overflow_unknown_trailing_events_do_not_poison_sequence')

        for _ in range(5):
            state=link.state()
            if state['unit']==initial_unit:break
            link.event('next')
        need(state['unit']==initial_unit,'Could not return to initial cavalry')
        awake=link.event('wake')
        target=max((t for t in awake['targets'] if t['kind']==0),key=lambda t:t['x'])
        link.point(target,awake)
        moved=link.event('confirm')
        need(not moved['awake'] and moved['unit']==initial_unit and moved['moves']==3,
             'Stable confirmation did not move cavalry once and sleep')
        record('stable_confirmation_moves_once_and_sleeps',before_moves=6,after_moves=3)
        link.raw(f'event {link.sequence} confirm');time.sleep(.12)
        after=link.state()
        need(not after['awake'] and after['moves']==3,'Duplicate confirmation changed order')
        link.event('mouse')  # Documented debug handoff back to mouse simulation.
        result.update(passed=True,final=link.state())
    except BaseException as error:
        result.update(passed=False,error=repr(error))
        raise
    finally:
        link.socket.close()
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
