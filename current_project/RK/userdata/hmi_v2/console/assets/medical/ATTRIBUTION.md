# Medical presentation assets

Original anatomical GLB files: Human Reference Atlas / HuBMAP, Kristen Browne and Heidi Schlehlein (2024). CC BY 4.0, https://creativecommons.org/licenses/by/4.0/ .

- Heart, Female v1.3: https://doi.org/10.48539/HBM449.SHRV.225
- Brain, Female v1.4: https://doi.org/10.48539/HBM674.NTLM.353
- Kidney, Female, Left v1.3: https://doi.org/10.48539/HBM449.JPXL.964
- Source library: https://humanatlas.io/3d-reference-library
- Repository: https://github.com/hubmapconsortium/hra-kg . Exact per-model creator, reviewers, dataset bibliography and license are retained in *-metadata.yaml.

Model bytes are original. This application changes display colors, normalizes display coordinates, rotates the view and isolates/scales selected mesh groups. It does not infer or annotate patient disease. Brain derives from the Allen reference atlas; heart and kidney derive from the NLM Visible Human Dataset, as described in source metadata.

Three.js r160 and GLTFLoader: https://github.com/mrdoob/three.js/tree/r160 , MIT; license retained at ../three/LICENSE. Loader utility import path adjusted for local serving. No external CDN is used at runtime.

Research / design references (no images or video copied):
- Mayo Clinic, How 3-D imaging helps doctors and patients (2017): https://newsnetwork.mayoclinic.org/discussion/mayo-clinic-minute-how-3-d-imaging-helps-doctors-and-patients/
- Mayo Clinic, 3D printing operations growing (2023): https://newsnetwork.mayoclinic.org/discussion/mayo-clinics-3d-printing-operations-growing-changing-medicine-along-the-way/
- 3D Slicer volume rendering documentation: https://slicer.readthedocs.io/en/5.6/user_guide/modules/volumerendering.html
- The Good Doctor S1E9, Intangibles, referenced for fictional spatial rehearsal composition only: https://the-good-doctor.fandom.com/wiki/Intangibles . No clinical workflow claim is based on television.

The viewer renders anatomical surface meshes, not CT/MRI volume ray casting. Holographic color and enlargement are presentation effects. The native Freeciv game remains GPL-2.0-or-later with its original assets and rules.
