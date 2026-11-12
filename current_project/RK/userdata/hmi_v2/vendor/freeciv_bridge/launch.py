"""Native start page, single-player campaign and same-board two-player turns."""
from pathlib import Path
import argparse,os,shutil,socket,subprocess,time

ROOT=Path(__file__).resolve().parent

def run_game(build,mode,load_save=None):
    suffix='.exe' if os.name=='nt' else '';env=os.environ.copy();env['FREECIV_DEMO']='1'
    if mode=='hotseat':env['FREECIV_HOTSEAT']='1'
    else:env.pop('FREECIV_HOTSEAT',None)
    env['FREECIV_DATA_PATH']=str(ROOT/'data' if (ROOT/'data').exists() else ROOT/'upstream/freeciv-3.2.6/data')
    env['FREECIV_OPT']=str(ROOT/'profile/client.rc')
    env['PATH']=str(build)+os.pathsep+str(ROOT/'toolchain/msys64/ucrt64/bin')+os.pathsep+env['PATH']
    (ROOT/'profile').mkdir(exist_ok=True);(ROOT/'logs').mkdir(exist_ok=True)
    with socket.socket() as probe:
        try:probe.bind(('127.0.0.1',5557))
        except OSError:raise RuntimeError('已有游戏使用端口 5557，请先退出该实例') from None
    archived=ROOT/'logs'/('before_'+str(time.time_ns()))
    for name in ('server.log','client.log'):
        path=ROOT/'logs'/name
        if path.exists():archived.mkdir(exist_ok=True);shutil.copy2(path,archived/name)
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    with (ROOT/'logs/server.log').open('w',encoding='utf8') as serverlog,(ROOT/'logs/client.log').open('w',encoding='utf8') as clientlog:
        scenario=load_save or ROOT/'scenario'/('duel-hotseat.sav' if mode=='hotseat' else 'border-keep.sav')
        server=subprocess.Popen([str(build/('freeciv-server'+suffix)),'-p','5557','-b','127.0.0.1','-f',str(scenario)],
            cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=serverlog,stderr=subprocess.STDOUT,text=True,creationflags=flags)
        client=None
        try:
            for _ in range(100):
                if server.poll() is not None:raise RuntimeError('Server failed; see logs/server.log')
                try:
                    with socket.create_connection(('127.0.0.1',5557),timeout=.15):break
                except OSError:time.sleep(.1)
            else:raise RuntimeError('Native server startup timed out')
            startup=(ROOT/'logs/server.log').read_text(encoding='utf8',errors='replace')
            if 'Could not load savefile' in startup or 'Error loading savefile' in startup:raise RuntimeError('Scenario load failed')
            client=subprocess.Popen([str(build/('freeciv-gtk3.22'+suffix)),'-a','-s','127.0.0.1','-p','5557','-n','Commander','-t','amplio2'],
                cwd=ROOT,env=env,stdout=clientlog,stderr=subprocess.STDOUT,creationflags=flags)
            for _ in range(100):
                if client.poll() is not None:raise RuntimeError('Client failed; see logs/client.log')
                time.sleep(.15);text=(ROOT/'logs/server.log').read_text(encoding='utf8',errors='replace')
                if 'Commander' in text and ('connected' in text or 'connection' in text):break
            else:raise RuntimeError('Native desktop client did not connect')
            commands=['set autotoggle disabled','set turnblock enabled','aitoggle AI*2','start'] if mode=='hotseat' and load_save is None else ['start']
            # Feed separate console reads; batching lines can leave the native
            # console's buffered input waiting for another pipe readability.
            for command in commands:
                server.stdin.write(command+'\n');server.stdin.flush();time.sleep(.2)
            client.wait()
        finally:
            if client is not None and client.poll() is None:client.terminate();client.wait(timeout=6)
            if server.poll() is None:
                try:server.stdin.write('quit\n');server.stdin.flush();server.wait(timeout=5)
                except (OSError,subprocess.TimeoutExpired):server.terminate();server.wait(timeout=5)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build',default='bin' if (ROOT/'bin').exists() else 'build')
    ap.add_argument('--mode',choices=('campaign','hotseat'),default='campaign')
    ap.add_argument('--direct',action='store_true',help='Explicit maintenance/testing bypass of the start page')
    ap.add_argument('--load-save',type=Path,help='Resume an explicit native save once, then return to the normal start page')
    args=ap.parse_args();mode=args.mode
    resume=args.load_save.resolve() if args.load_save else None
    if resume is not None and not resume.is_file():ap.error('Save file does not exist')
    while True:
        if not args.direct and resume is None:
            from start_menu import show_start_menu
            mode=show_start_menu(mode)
            if mode is None:return
        run_game(ROOT/args.build,mode,resume)
        resume=None
        if args.direct:return

if __name__=='__main__':main()
