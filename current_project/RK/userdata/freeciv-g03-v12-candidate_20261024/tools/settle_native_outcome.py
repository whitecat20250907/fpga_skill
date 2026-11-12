"""Finish the existing native turn after a real objective; no winner injection."""
import argparse,json,os,time
from pathlib import Path
from test_live_input import Link,need
from run_on_desktop import environment
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(exist_ok=False)
    link=Link();s=link.state();link.sequence=int(s['last_event']);need(s.get('outcome',0)!=0,'Actual objective required')
    result=dict(initial=s,human_input=False,uses_only_five_actions=True)
    try:
        result['after_end']=link.event('end');end=time.monotonic()+20
        while time.monotonic()<end:
            s=link.state()
            if s.get('game_over'):break
            time.sleep(.05)
        log=(ROOT/'logs/server.log').read_text();(a.output/'server.log').write_text(log)
        victory=[line for line in log.splitlines() if 'Scenario victory' in line]
        result.update(final=s,victory_log=victory,passed=bool(s.get('game_over') and victory))
        env,_=environment(1721);os.environ.update(env)
        import gi;gi.require_version('Gdk','3.0');from gi.repository import Gdk
        w=Gdk.get_default_root_window();Gdk.pixbuf_get_from_window(w,0,0,w.get_width(),w.get_height()).savev(str(a.output/'native_final.png'),'png',[],[])
        need(result['passed'],'Native terminal settlement did not complete')
    finally:
        link.socket.close();(a.output/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(passed=result.get('passed'),game_over=s.get('game_over'),outcome=s.get('outcome'),victory=result.get('victory_log'))))
if __name__=='__main__':main()
