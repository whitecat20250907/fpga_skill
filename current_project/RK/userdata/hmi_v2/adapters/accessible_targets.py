"""Isolated AT-SPI reader. A broken accessibility bus cannot crash adapters."""
import json,sys,time

def main():
    import gi
    gi.require_version('Atspi','2.0')
    from gi.repository import Atspi
    Atspi.set_timeout(150,250)
    pid=int(sys.argv[1]);root=Atspi.get_desktop(0);out=[];deadline=time.monotonic()+1.5
    apps=[root.get_child_at_index(i) for i in range(root.get_child_count())]
    for app in apps:
        if app.get_process_id()!=pid:continue
        queue=[(app,'app')];seen=0
        while queue and seen<1200 and len(out)<200 and time.monotonic()<deadline:
            item,path=queue.pop(0);seen+=1
            try:
                states=item.get_state_set()
                if states.contains(Atspi.StateType.DEFUNCT):continue
                component=item.get_component_iface();action=item.get_action_iface()
                if component and action and action.get_n_actions()>0 and states.contains(Atspi.StateType.SHOWING) and states.contains(Atspi.StateType.SENSITIVE):
                    rect=component.get_extents(Atspi.CoordType.SCREEN)
                    if rect.width>0 and rect.height>0:
                        out.append(dict(id=f'desktop:{pid}:{path}',label=item.get_name() or item.get_role_name(),
                                        rect=[rect.x,rect.y,rect.width,rect.height],confidence=1.,action='desktop.click'))
                for i in range(min(item.get_child_count(),200)):queue.append((item.get_child_at_index(i),path+'.'+str(i)))
            except Exception:continue
    print(json.dumps(out,ensure_ascii=False))

if __name__=='__main__':main()
