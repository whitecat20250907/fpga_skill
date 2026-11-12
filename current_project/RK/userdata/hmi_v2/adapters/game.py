"""Order the final fresh gaze before a one-shot game confirmation."""
def submit(game, action, send):
    name = action['name'].split('.')[-1]
    if name == 'sleep':
        return game.invalidate_gaze()
    if name == 'confirm':
        cursor = action['args']['cursor']
        stamp = cursor['src_ns']/1e9
        if stamp > game.last_source:
            origin = cursor.get('screen_origin', [0, 0])
            if not game.gaze_screen(cursor['xy'][0]+origin[0], cursor['xy'][1]+origin[1], stamp):
                return False
        elif stamp != game.last_source or not game.gaze_active:
            return False
    return bool(send(game, name))


def submit_locked(game,lock):
    """Use the native mouse-selection path at the frozen point, never fake gaze age."""
    native=lock.get('target',{}).get('native');view=game.update()
    if not native or not view or not view.get('selection_ready'):
        return False,'游戏目标尚未就绪，请稍后再次点击'
    rows=view.get('targets',[]);pick=view.get('pick',-1)
    chosen=next((t for t in rows if t['id']==pick),None) if view.get('phase')=='menu' else (rows[pick] if 0<=pick<len(rows) else None)
    if not chosen or any(chosen.get(k)!=v for k,v in native.items()):
        return False,'游戏目标与锁定点不一致，请重新眼控接管'
    return bool(game.action('confirm')),'游戏确认已发送'
