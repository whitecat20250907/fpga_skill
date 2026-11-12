"""Collect explicit owned native-game receipts, not arbitrary board files."""
import hashlib,json,platform,tarfile
from pathlib import Path
ROOT=Path('/userdata/freeciv-rk3576-gaze-demo')
OUT=ROOT/'.maintenance/demo_delivery_20261023_v1'
RUNS=['demo_video_bombard_v1','demo_video_next_unit_v1','demo_video_citydiag_v1','demo_hotseat_battle_v2','demo_video_native_cost_v1','demo_hotseat_native_cost_v1','demo_hotseat_native_settlement_v1','demo_video_intro_balance_v1','demo_hotseat_intro_balance_v1']
def main():
    OUT.mkdir(exist_ok=True)
    files=[]
    for run in RUNS:
        directory=ROOT/'.maintenance'/run
        if directory.is_dir():
            files.extend(p for p in directory.iterdir() if p.suffix in ('.json','.png','.log') and p.is_file())
    for version in range(1,11):
        for name in ('manifest.json','result.json','build.log'):
            path=ROOT/f'.maintenance/demo_video_build_v{version}'/name
            if path.is_file():files.append(path)
    for name in ('owner.json','ready.json'):
        path=ROOT/'.maintenance/demo_video_owner_v2'/name
        if path.is_file():files.append(path)
    inputs=['upstream/freeciv-3.2.6/client/gui-gtk-3.22/demo_control.inc','upstream/freeciv-3.2.6/client/gui-gtk-3.22/demo_control.h',
        'upstream/freeciv-3.2.6/client/gui-gtk-3.22/repodlgs.c','upstream/freeciv-3.2.6/server/srv_main.c',
        'upstream/freeciv-3.2.6/client/gui-gtk-3.22/gui_main.c','upstream/freeciv-3.2.6/client/gui-gtk-3.22/mapctrl.c',
        'upstream/freeciv-3.2.6/client/gui-gtk-3.22/mapview.c','upstream/freeciv-3.2.6/client/gui-gtk-3.22/demo_selection.h',
        'upstream/freeciv-3.2.6/client/gui-gtk-3.22/demo_input_parse.h',
        'scenario/campaign.lua','scenario/border-keep.sav','scenario/duel-hotseat.sav','launch.py','start_menu.py','start-rk3576.sh',
        'tools/play_campaign_v3.py','tools/play_hotseat_battle_v3.py','tools/board_demo_session.py','tools/profile_linux.py','tools/test_live_input.py']
    inputs.extend(str(p.relative_to(ROOT)) for p in (ROOT/'upstream/freeciv-3.2.6/data/gaze_war').iterdir() if p.is_file())
    files.extend(ROOT/name for name in inputs)
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    rows=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(set(files))]
    summary=dict(machine=platform.machine(),kernel=platform.release(),client_sha256=sha(ROOT/'build-arm64/freeciv-gtk3.22'),
        server_sha256=sha(ROOT/'build-arm64/freeciv-server'),inputs={name:sha(ROOT/name) for name in inputs},files=rows)
    (OUT/'inventory.json').write_text(json.dumps(summary,indent=2))
    target=Path('/home/linaro/pcie_fix_20261003/demo_delivery_20261023_v1.tar.gz')
    with tarfile.open(target,'w:gz') as archive:
        for p in sorted(set(files)):archive.add(p,arcname=str(p.relative_to(ROOT)),recursive=False)
        archive.add(OUT/'inventory.json',arcname='inventory.json',recursive=False)
    print(json.dumps(dict(files=len(rows),bytes=target.stat().st_size,sha256=sha(target),client_sha256=summary['client_sha256'])))
if __name__=='__main__':main()
