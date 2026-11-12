"""Collect bounded owned test artifacts; no environments or credentials."""
import hashlib,json,os,shutil,sys,tarfile,time
from pathlib import Path
ROOT=Path('/userdata/freeciv-rk3576-gaze-demo');BASE=Path('/home/linaro/pcie_fix_20261003')
OUT=BASE/'project_board_20261021_v1'

def main():
    assert not OUT.exists();OUT.mkdir()
    def copy(source,target):
        target=OUT/target;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    for prefix,count in (('campaign_GUI_economy_v',5),('hotseat_actual_v',4)):
        for i in range(1,count+1):
            path=BASE/(prefix+str(i))
            if path.exists():
                for p in path.iterdir():
                    if p.suffix in ('.json','.png'):copy(p,Path('actual_tests')/path.name/p.name)
    for name in ('project_twin_fixtures_v1','project_twin_fixture_render_v1','project_twin_live_v1','project_twin_live_v2'):
        for p in (ROOT/'logs'/name).rglob('*'):
            if p.is_file() and p.suffix in ('.json','.jsonl','.png'):copy(p,Path('features')/name/p.relative_to(ROOT/'logs'/name))
    names=['project_candidate_v1','twin_board_v2']+['campaign_rules_v'+str(i) for i in range(1,4)]+['campaign_client_v'+str(i) for i in range(3,7)]+['campaign_GUI_v'+str(i) for i in range(1,7)]
    for name in names:
        path=ROOT/'.maintenance'/name
        if not path.exists():continue
        for p in path.iterdir():
            if p.is_file() and (p.suffix=='.json' or (p.suffix=='.log' and name!='campaign_GUI_v6')):
                copy(p,Path('maintenance')/name/(p.stem+'.txt' if p.suffix=='.log' else p.name))
    sys.path.insert(0,str(ROOT))
    from project_features import FeatureState
    from project_twin import render
    packet=json.loads((ROOT/'logs/project_twin_fixtures_v1/right_hands.features.json').read_text())
    state=FeatureState();assert packet['fixture'] and state.accept(json.dumps(packet),packet['timestamp_ns']+1)
    render(state,now_ns=packet['timestamp_ns']+1).save(OUT/'corrected_hand_fixture_XYZ.png')
    identities=[]
    for pid in (118016,118079):
        p=Path('/proc')/str(pid);identities.append(dict(pid=pid,cwd=os.readlink(p/'cwd'),birth=(p/'stat').read_text().rsplit(')',1)[1].split()[19]))
    source_names=['launch.py','start_menu.py','project_features.py','project_twin.py','tools/run_project_twin.py','tools/run_mediapipe_gestures.py',
        'scenario/border-keep.sav','scenario/duel-hotseat.sav','upstream/freeciv-3.2.6/client/gui-gtk-3.22/demo_control.inc']
    metadata=dict(observed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        original_main_and_camera=identities,feature_face_wrapper_activated=False,FPGA_screen_accepted=False,
        game_full_battle_new_revision_accepted=False,human_motion_gaze_calibration_accepted=False,
        source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in source_names})
    (OUT/'metadata.json').write_text(json.dumps(metadata,indent=2))
    rows=[dict(path=p.relative_to(OUT).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in OUT.rglob('*') if p.is_file()]
    (OUT/'manifest.json').write_text(json.dumps(rows,indent=2))
    archive=BASE/'project_board_20261021_v1.tar.gz';assert not archive.exists()
    with tarfile.open(archive,'w:gz') as tar:tar.add(OUT,arcname=OUT.name)
    print(json.dumps(dict(archive=str(archive),bytes=archive.stat().st_size,files=len(rows),metadata=metadata)),flush=True)
if __name__=='__main__':main()
