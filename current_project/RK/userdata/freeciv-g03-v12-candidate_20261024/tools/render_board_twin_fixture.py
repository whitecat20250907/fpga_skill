"""Render actual retained RK hand-inference XYZ. Explicit offline replay."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from project_features import FeatureState
from project_twin import render

if __name__=='__main__':
    source=ROOT/'logs/project_twin_fixtures_v1/right_hands.features.json'
    packet=json.loads(source.read_text());assert packet['fixture'] is True
    out=ROOT/'logs/project_twin_fixture_render_v1';assert not out.exists();out.mkdir()
    state=FeatureState();assert state.accept(json.dumps(packet),packet['timestamp_ns']+1)
    render(state,now_ns=packet['timestamp_ns']+1).save(out/'actual_fixture_xyz.png')
    result=dict(source=str(source),hands=len(packet['hands']),fixture=True,
        actual_RK_inference_XYZ=True,live_human_accepted=False,FPGA_screen_accepted=False)
    (out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
