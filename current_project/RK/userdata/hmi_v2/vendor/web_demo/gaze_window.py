"""Restore the bound gaze window, including an iconified fullscreen SDL window."""
import subprocess

def restore_gaze_window(pid, env):
    try:
        # --onlyvisible excludes minimized SDL windows; those must be mapped first.
        ids = subprocess.check_output(['xdotool','search','--pid',str(pid)],
                                      env=env,text=True,timeout=2).split()
    except subprocess.CalledProcessError as exc:
        raise RuntimeError('眼动窗口不存在：请检查采集/模型运行状态，重新标定不会重启采集') from exc
    if not ids:
        raise RuntimeError('眼动窗口不存在')
    chosen = None
    for wid in ids:
        title = subprocess.check_output(['xdotool','getwindowname',wid],env=env,text=True,timeout=2)
        if 'MGazeNet' in title:
            chosen = wid
            break
    if chosen is None:
        raise RuntimeError('找不到当前模型进程的 MGazeNet 窗口')
    subprocess.run(['xdotool','windowmap',chosen],env=env,check=True,timeout=2)
    subprocess.run(['xdotool','windowactivate','--sync',chosen],env=env,check=True,timeout=2)
    return chosen
