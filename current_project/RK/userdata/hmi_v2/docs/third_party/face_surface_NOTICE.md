The reduced face-display topology and canonical offline fixture are derived
from Google MediaPipe's canonical_face_model.obj (Apache License 2.0):
https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/modules/face_geometry/data/canonical_face_model.obj

Copyright 2019 The MediaPipe Authors. All Rights Reserved.
License text: mediapipe_APACHE_LICENSE.txt in this directory.

Modifications: selected 34 landmark indices, generated reduced Delaunay
surface connectivity with open eye/mouth apertures; canonical coordinates
converted to pixel-like units for offline tests only. Runtime geometry uses
the existing model's measured landmarks, with optional additional detail.
Source SHA and generation record are kept in face88/topology_source.json
in the workstation evidence bundle.
