# KiTS19 case_00001

Source: Nicholas Heller et al., The KiTS19 Challenge Data: 300 Kidney Tumor Cases with Clinical Context, CT Semantic Segmentations, and Surgical Outcomes (2019). https://github.com/neheller/kits19 and https://kits19.grand-challenge.org/data/

Data and these derivative CT, masks and meshes: CC BY-NC-SA 4.0. Full license in LICENSE.txt. Original data are anonymized research CT and supervised manual kidney/tumor labels. This viewer is an educational interaction demonstration, not a diagnostic system.

Modifications: reoriented to canonical RAS; CT rounded to int16 HU and subsampled every 3 voxels; labels sampled on exactly the same grid; meshes generated with marching cubes from original labels (kidneys step 2, tumor step 1). Rendering uses R,S,-A coordinates. No predicted or invented lesion is added. Source byte hashes in SOURCE_MANIFEST.json. Original data are retained locally in research/medical_v56; full volumes are not required on the board.
