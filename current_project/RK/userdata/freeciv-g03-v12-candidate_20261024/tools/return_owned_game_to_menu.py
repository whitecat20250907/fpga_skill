"""Normal close of the exact native child of an explicitly registered owner."""
import argparse,json,os
from pathlib import Path
from board_demo_session import identity,close_client,wait_state
from run_on_desktop import environment
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--owner',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    need=lambda x: x or (_ for _ in ()).throw(RuntimeError('Owned game identity changed'))
    need(a.owner.resolve().is_relative_to(ROOT/'.maintenance'));reg=json.loads(a.owner.read_text());actual=identity(reg['launcher']['pid'])
    need(actual['birth']==reg['launcher']['birth'] and actual['ppid']==reg['supervisor']['pid'] and actual['cwd']==str(ROOT))
    need(actual['argv']==['python3','-B','launch.py','--build','build-arm64'])
    clients=[]
    for p in Path('/proc').glob('[0-9]*/stat'):
        try:
            row=identity(int(p.parent.name))
            if row['ppid']==actual['pid'] and row['argv'][0]==str(ROOT/'build-arm64/freeciv-gtk3.22'):clients.append(row)
        except (OSError,IndexError):pass
    need(len(clients)==1);env,_=environment(1721);os.environ.update(env)
    close_client(clients[0]['pid'],clients[0]['birth']);s=wait_state(lambda s:s.get('phase')=='menu')
    a.output.write_text(json.dumps(dict(status='EXACT_OWNED_NATIVE_CLIENT_CLOSED_NORMALLY',client=clients[0],launcher=actual,menu=s),indent=2));print('OWNED_GAME_RETURNED_TO_START_PAGE')
if __name__=='__main__':main()
