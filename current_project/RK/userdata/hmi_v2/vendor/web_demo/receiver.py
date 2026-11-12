"""SSH stdio PC input adapter. No listening server, camera or FPGA access."""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import socket
import secrets
import subprocess
import sys
import time

ACTIONS = {'wake', 'confirm', 'cancel', 'next', 'end'}
KEYS = {'Return', 'Escape', 'Tab', 'space', 'Up', 'Down', 'Left', 'Right', 'F1', *map(str, range(10))}
MENU_SOURCE_SHA = 'aa638c44e4357880549e17fb4111e5558b59566d325fc49362ad1307a2fd9262'

class PendingControl(RuntimeError):
    pass

def owner_control(cfg, verb, argument):
    if (verb == 'mode' and argument not in ('visual','trajectory','game')) or (verb in ('page','register','unregister') and argument not in ('1','2')) or verb not in ('mode','page','register','unregister'):
        raise ValueError('Owner control action not allowed')
    source = cfg['application_client_source']
    path = Path(source['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
        raise ValueError('Application client source changed')
    binding = json.loads(Path(cfg['binding']).read_text())
    if binding['application_client_source'] != source:
        raise ValueError('Actual binding application client differs')
    old_path = list(sys.path)
    sys.path.insert(0,str(path.parent))
    try:
        original = load(path, '_pc_original_application_client')
        if verb == 'mode':
            body = dict(action='set_interaction_mode',mode=argument)
        else:
            body = dict(action='application_control',application=dict(command=verb,slot=int(argument)))
        try:
            return original.command(binding,body,timeout=600.)
        except Exception as exc:
            raise PendingControl('Original client did not return a verified response; inspect its request/response before retry: '+str(exc)) from exc
    finally:
        sys.path[:] = old_path

def menu_target(x, y, viewport, desktop):
    ox,oy,w,h = viewport
    px,py = (x*(desktop[0]-1)-ox)/w*1024, (y*(desktop[1]-1)-oy)/h*600
    for i,(bx,by,bw,bh) in enumerate(((56,216,435,150),(533,216,435,150),(280,414,464,64),(844,522,124,40))):
        if bx <= px <= bx+bw and by <= py <= by+bh:
            return i
    return None

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def start_ticks(pid):
    return int(Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19])

def point(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Normalized pointer must be finite and in [0,1]')
    return value

class Receiver:
    def __init__(self, cfg):
        self.cfg = cfg
        self.active = False
        self.verified_clients = set()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(.15)
        desktop = load(Path(cfg['game_root'])/'tools/run_on_desktop.py', '_pc_desktop')
        self.env, self.desktop = desktop.environment(cfg['desktop_pid'])
        self.identity()
        for source in cfg['launcher_sources']:
            if hashlib.sha256(Path(source['path']).read_bytes()).hexdigest() != source['sha256']:
                raise ValueError('Launcher source mismatch')
        args = Path(f"/proc/{cfg['launcher_pid']}/cmdline").read_bytes().split(b'\0')
        launcher_arg = str(Path(cfg['game_root'])/'launch.py').encode() in args or (
            b'launch.py' in args and Path(f"/proc/{cfg['launcher_pid']}/cwd").resolve() == Path(cfg['game_root']))
        if not launcher_arg:
            raise ValueError('Pinned launcher command line differs')
        binding = cfg['game_binding']
        if hashlib.sha256(Path(binding['path']).read_bytes()).hexdigest() != binding['sha256']:
            raise ValueError('Actual game binding changed')
        self.socket_owner()

    def identity(self):
        if start_ticks(self.cfg['launcher_pid']) != self.cfg['launcher_start_ticks']:
            raise ValueError('Launcher changed; reconnect with fresh configuration')

    def state(self):
        self.identity()
        self.socket_owner()
        nonce = secrets.token_hex(16)
        self.sock.sendto(('query '+nonce).encode(), ('127.0.0.1', 29778))
        deadline = time.monotonic()+1
        while time.monotonic() < deadline:
            try:
                raw, addr = self.sock.recvfrom(32768)
                prefix, echo, body = raw.decode().split(' ', 2)
                if addr == ('127.0.0.1', 29778) and prefix == 'state' and echo == nonce:
                    return json.loads(body)
            except socket.timeout:
                pass
        raise TimeoutError('No nonce-matched game state')

    def socket_owner(self):
        # Do not accept a nonce response from an unrelated replacement game.
        inodes = set()
        for row in Path('/proc/net/udp').read_text().splitlines()[1:]:
            fields = row.split()
            if fields[1] == '0100007F:7452':  # 127.0.0.1:29778
                inodes.add(fields[9])
        launcher = self.cfg['launcher_pid']
        children = Path(f'/proc/{launcher}/task/{launcher}/children').read_text().split()
        owners = []
        for pid in [launcher, *map(int, children)]:
            owned = set()
            try:
                for fd in Path(f'/proc/{pid}/fd').iterdir():
                    try:
                        target = os.readlink(fd)
                    except FileNotFoundError:
                        continue
                    if target.startswith('socket:['):
                        owned.add(target[8:-1])
                if len(inodes) == 1 and inodes.issubset(owned):
                    if pid != launcher:
                        exe = Path(f'/proc/{pid}/exe')
                        meta = exe.stat()
                        stamp = (pid, start_ticks(pid), meta.st_dev, meta.st_ino, meta.st_size, meta.st_mtime_ns)
                        if stamp not in self.verified_clients:
                            if hashlib.sha256(exe.read_bytes()).hexdigest() != self.cfg['game_sha256']:
                                raise RuntimeError('Active child client SHA differs')
                            self.verified_clients.add(stamp)
                    owners.append((pid, start_ticks(pid)))
            except FileNotFoundError:
                continue
        if len(owners) != 1:
            raise RuntimeError('UDP endpoint unavailable or not owned by pinned launcher/client')
        self.endpoint = owners[0]

    def event(self, action, expected=None):
        state = self.state()
        endpoint = self.endpoint
        if expected is not None and (endpoint != expected['endpoint'] or
                any(state.get(key) != expected[key] for key in ('phase','map','pick','selection_ready','awake'))):
            raise RuntimeError('Menu target changed before sending confirmation')
        seq = int(state['last_event'])+1
        self.sock.sendto(f'event {seq} {action}'.encode(), ('127.0.0.1', 29778))
        time.sleep(.06)
        try:
            result = self.state()
        except (TimeoutError, RuntimeError):
            if action == 'confirm' and state.get('phase') == 'menu':
                exiting = state.get('pick') == 3
                return {'phase':'exit_sent' if exiting else 'launching', 'command_sent_once':True,
                        'acceptance':'await_closed' if exiting else 'await_actual_client'}
            raise
        if self.endpoint != endpoint:
            return dict(result, endpoint_transition=True, command_sent_once=True)
        if int(result['last_event']) != seq:
            raise RuntimeError('Input was not uniquely acknowledged; do not retry automatically')
        return result

    def control(self, *args):
        source = self.cfg['application_client_source']
        path = Path(source['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
            raise ValueError('Application client source changed')
        argv = [sys.executable, '-u', str(Path(__file__).resolve()), '--config', self.cfg['_config_path'], '--owner-control', *args]
        if self.cfg.get('control_sudo'):
            argv = ['sudo', '-n', *argv]
        try:
            result = subprocess.run(argv,capture_output=True,text=True,timeout=1200)
        except subprocess.TimeoutExpired as exc:
            raise PendingControl('Owner command may still be pending; do not resubmit; inspect original request/response') from exc
        try:
            reply = json.loads(result.stdout)
        except ValueError as exc:
            raise PendingControl('Owner control result unavailable; inspect original request/response before retry') from exc
        if reply.get('pending'):
            raise PendingControl(reply.get('error','Original owner request pending'))
        if result.returncode:
            raise RuntimeError('Owner refused application control: '+result.stdout[-1200:])
        if reply.get('ok') is not True:
            raise RuntimeError('Owner did not acknowledge application control')
        return reply

    def dispatch(self, req):
        action = req.get('action')
        self.identity()
        if action == 'takeover':
            self.active = False
            self.control('mode', 'visual')  # Inference/visualization continue; game bridge stops sending.
            if self.state().get('phase') != 'menu':
                self.event('cancel')
            result = self.event('mouse')
            self.active = True
            return result
        if action == 'release':
            self.active = False
            if self.state().get('phase') != 'menu':
                self.event('cancel')
            return self.control('mode', 'game')
        if action == 'status':
            return self.state()
        if not self.active:
            raise ValueError('Explicit PC takeover required')
        if action in ACTIONS:
            return self.event(action)
        if action in ('key', 'click'):
            state = self.state()
            if action == 'key':
                if req.get('key') not in KEYS:
                    raise ValueError('Key not allowed')
                command = ['xdotool','key','--clearmodifiers',req['key']]
            else:
                if type(req.get('button')) is not int or req['button'] not in (1,3):
                    raise ValueError('Only complete left/right clicks supported')
                command = ['xdotool','click',str(req['button'])]
            windows = subprocess.check_output(['xdotool','search','--onlyvisible','--pid',str(self.endpoint[0])],env=self.env,text=True,timeout=2).split()
            if not windows:
                raise RuntimeError('Actual endpoint window unavailable')
            subprocess.run(['xdotool','windowactivate','--sync',windows[-1]],env=self.env,check=True,timeout=2)
            if action == 'click':
                self.dispatch({'action':'pointer','space':'desktop','x':req['x'],'y':req['y']})
                if state.get('phase') == 'menu':
                    if req['button'] == 3:
                        return self.event('cancel')
                    menu_path = Path(self.cfg['game_root'])/'start_menu.py'
                    if hashlib.sha256(menu_path.read_bytes()).hexdigest() != MENU_SOURCE_SHA:
                        raise ValueError('Menu click geometry source changed')
                    desktop = tuple(map(int,subprocess.check_output(['xdotool','getdisplaygeometry'],env=self.env,text=True,timeout=2).split()))
                    target = menu_target(point(req['x']),point(req['y']),state['map'],desktop)
                    if target is None:
                        return {'phase':'menu','clicked_background':True,'confirmed':False}
                    endpoint = self.endpoint
                    awake = self.event('wake')
                    self.event('mouse')
                    candidates = [t for t in awake.get('targets',[]) if t.get('id') == target and t.get('arg') == target]
                    if len(candidates) != 1:
                        raise RuntimeError('Actual clicked menu target unavailable')
                    candidate = candidates[0]
                    ox,oy,_,_ = state['map']
                    subprocess.run(['xdotool','mousemove','--sync',str(ox+candidate['x']),str(oy+candidate['y'])],env=self.env,check=True,timeout=2)
                    deadline = time.monotonic()+1.
                    while time.monotonic() < deadline:
                        current = self.state()
                        if self.endpoint != endpoint or current.get('phase') != 'menu' or current.get('map') != state['map']:
                            raise RuntimeError('Menu changed before click confirmation; not confirmed')
                        if current.get('awake') is True and current.get('pick') == target and current.get('selection_ready') is True and candidate in current.get('targets',[]):
                            return self.event('confirm',expected=dict(endpoint=endpoint,phase='menu',map=state['map'],pick=target,selection_ready=True,awake=True))
                        time.sleep(.04)
                    raise TimeoutError('Clicked menu target not ready within one second; not confirmed')
            if action == 'key' and req['key'] == 'Return' and state.get('phase') == 'menu':
                return self.event('confirm')
            subprocess.run(command,env=self.env,check=True,timeout=2)
            return {'input':action, 'source':'PC_MANUAL', 'phase':self.state().get('phase')}
        if action == 'pointer':
            x, y = point(req['x']), point(req['y'])
            state = self.state()
            ox, oy, w, h = state['map']
            if req.get('space', 'map') == 'desktop':
                w,h = map(int,subprocess.check_output(['xdotool','getdisplaygeometry'],env=self.env,text=True,timeout=2).split())
                ox,oy = 0,0
            elif req.get('space', 'map') != 'map':
                raise ValueError('Unknown coordinate space')
            if w <= 0 or h <= 0:
                raise ValueError('Map viewport unavailable')
            subprocess.run(['xdotool', 'mousemove', '--sync', str(ox+round(x*(w-1))), str(oy+round(y*(h-1)))],
                           env=self.env, check=True, timeout=2)
            return {'pointer': [x, y], 'map': state['map']}
        if action in ('page1', 'page2'):
            return self.control('page', action[-1])
        if action in ('register1', 'register2'):
            return self.control('register', action[-1])
        if action in ('unregister1', 'unregister2'):
            return self.control('unregister', action[-1])
        if action in ('visual', 'trajectory'):
            return self.control('mode', action)
        raise ValueError('Unsupported action')

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', required=True)
    ap.add_argument('--owner-control',nargs=2,metavar=('ACTION','ARGUMENT'))
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    cfg['_config_path'] = str(Path(args.config).resolve())
    if args.owner_control:
        try:
            result = owner_control(cfg,*args.owner_control)
        except (TimeoutError,PendingControl) as exc:
            result = dict(ok=False,pending=True,error=str(exc))
        except Exception as exc:
            result = dict(ok=False,error=str(exc))
        print(json.dumps(result),flush=True)
        return 0 if result.get('ok') is True else 3
    receiver = Receiver(cfg)
    print(json.dumps({'ready': True, 'source': 'PC_MANUAL', 'active': False}), flush=True)
    try:
        for line in sys.stdin:
            try:
                req = json.loads(line)
                value = receiver.dispatch(req)
                reply = {'ok': True, 'value': value}
            except Exception as exc:
                reply = {'ok': False, 'error': str(exc), 'pending':isinstance(exc,PendingControl)}
            print(json.dumps(dict(reply, source='PC_MANUAL', active=receiver.active)), flush=True)
    finally:
        # No held keys are ever synthesized; disconnect leaves game in visual/manual mode.
        receiver.sock.close()

if __name__ == '__main__':
    raise SystemExit(main())
