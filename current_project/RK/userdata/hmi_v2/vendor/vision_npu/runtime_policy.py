"""One explicit policy shared by all optional consumers and the main app."""
import json
from pathlib import Path
path=Path(__file__).resolve().parent/'policy.json'
POLICY=json.loads(path.read_text()) if path.exists() else dict(hand_roi_cores=[0,0],face_roi_cores=[],gaze_cores=[],gaze_core=0)
