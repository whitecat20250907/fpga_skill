"""Only spatial actions require a personal gaze calibration."""
INDEPENDENT={'demo.undo','desktop.undo','game.undo','demo.next','demo.cancel','demo.zoom','demo.focus','demo.snap','demo.reset','demo.rotate',
             'desktop.next','desktop.cancel','game.next','game.cancel','game.end'}
DELIBERATE={'Victory','Thumb_Up','Thumb_Down','ILoveYou','Open_Palm','stroke','dual_index'}

def independent_action(name,gesture):
    return name in INDEPENDENT and gesture in DELIBERATE


def locked_action(name):
    return name.endswith(('.click','.confirm')) or name=='demo.focus'
