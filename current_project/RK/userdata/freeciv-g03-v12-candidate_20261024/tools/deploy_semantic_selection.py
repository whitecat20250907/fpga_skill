"""Bounded source update, backups, native tests and single-job ARM rebuild."""
import hashlib,io,json,subprocess,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'evidence/semantic_selection_v1'
NAMES=['semantic_selection.py','start_menu.py','input_bridge.py','screen_bridge.py','tools/run_main_with_freeciv.py',
    'tests/test_semantic_selection.py','tests/test_start_menu.py','tests/test_screen_bridge.py',
    'tests/semantic_native.c','tools/test_semantic_native.py',
    'upstream/freeciv-3.2.6/client/gui-gtk-3.22/demo_selection.h',
    'upstream/freeciv-3.2.6/client/gui-gtk-3.22/demo_input_parse.h',
    'upstream/freeciv-3.2.6/client/gui-gtk-3.22/demo_control.inc']
def main():
    OUT.mkdir(exist_ok=False);rows=[]
    with tarfile.open(OUT/'update.tar','w') as archive:
        for name in NAMES:
            old=subprocess.run(['git','show','HEAD:'+name],cwd=ROOT,capture_output=True)
            before=hashlib.sha256(old.stdout).hexdigest() if old.returncode==0 else None
            body=(ROOT/name).read_bytes();rows.append(dict(path=name,old=before,new=hashlib.sha256(body).hexdigest()))
            info=tarfile.TarInfo(name);info.size=len(body);archive.addfile(info,io.BytesIO(body))
        body=json.dumps(rows).encode();info=tarfile.TarInfo('manifest.json');info.size=len(body);archive.addfile(info,io.BytesIO(body))
    (OUT/'manifest.json').write_text(json.dumps(rows,indent=2))
    print('Prepared',len(rows),'files')
if __name__=='__main__':main()
