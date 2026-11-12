# Third-party reference

Head surface connectivity was derived using the canonical landmark coordinates from Google MediaPipe, commit a908d668c730da128dfa8d9f6bd25d519d006692:
https://github.com/google-ai-edge/mediapipe/blob/a908d668c730da128dfa8d9f6bd25d519d006692/mediapipe/modules/face_geometry/data/canonical_face_model.obj

The upstream Apache-2.0 license is retained in LICENSES/mediapipe-Apache-2.0.txt. The new 29-slot/34-triangle display connectivity is a modification for this project; it is not the original full canonical mesh. The canonical coordinate asset is used only for development/reference tests, not to replace actual detected coordinates at runtime.
