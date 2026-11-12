from pathlib import Path
import json,hashlib,shutil
import numpy as np,nibabel as nib,trimesh
from scipy import ndimage
from skimage.measure import marching_cubes
import argparse
parser=argparse.ArgumentParser(description='Build aligned KiTS19 teaching assets from locally downloaded NIfTI sources')
parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();src=args.source;out=args.output;out.mkdir(parents=True,exist_ok=True)
a=nib.as_closest_canonical(nib.load(src/'imaging.nii.gz'));b=nib.as_closest_canonical(nib.load(src/'segmentation.nii.gz'))
assert a.shape==b.shape and np.allclose(a.affine,b.affine)
seg=np.asarray(b.dataobj,dtype=np.uint8);coords=np.argwhere(seg==2);centroid=coords.mean(axis=0);spacing=np.diag(a.affine)[:3];origin=a.affine[:3,3]
labels,n=ndimage.label(seg==1);sizes=np.bincount(labels.ravel());sizes[0]=0;organs=np.argsort(sizes)[-2:]
scene=trimesh.Scene();stats=[]
for name,mask in [('kidney_a',labels==organs[0]),('kidney_b',labels==organs[1]),('tumor',seg==2)]:
 ix=np.argwhere(mask);lo=np.maximum(ix.min(0)-2,0);hi=np.minimum(ix.max(0)+3,seg.shape);roi=mask[tuple(slice(int(x),int(y)) for x,y in zip(lo,hi))]
 verts,faces,_,_=marching_cubes(roi,.5,spacing=spacing,step_size=2 if name!='tumor' else 1)
 ras=verts+lo*spacing+origin;vertices=ras[:,[0,2,1]];vertices[:,2]*=-1
 mesh=trimesh.Trimesh(vertices=vertices,faces=faces,process=False);scene.add_geometry(mesh,geom_name=name,node_name=name);stats.append({'name':name,'vertices':len(verts),'triangles':len(faces),'volume_ml':float(mask.sum()*np.prod(spacing)/1000)})
bounds=scene.bounds;center=bounds.mean(0);scale=2.65/np.max(bounds[1]-bounds[0]);(out/'case_00000.glb').write_bytes(scene.export(file_type='glb'))
# Stored XYZ C-order. Striding preserves a simple, exact voxel-to-RAS transform.
step=3;volume=np.rint(np.asarray(a.dataobj)[::step,::step,::step]).clip(-32768,32767).astype('<i2');mask=seg[::step,::step,::step]
(out/'ct.i16').write_bytes(volume.tobytes());(out/'labels.u8').write_bytes(mask.tobytes())
center_voxel=(centroid/step).tolist();meta={'case':'KiTS19 case_00000','shape':list(volume.shape),'spacing_mm':(spacing*step).tolist(),'origin_ras_mm':origin.tolist(),'axes':'RAS','storage':'XYZ C-order int16 little endian HU; uint8 labels 0 background 1 kidney 2 tumor','source_shape':list(a.shape),'source_spacing_mm':spacing.tolist(),'stride':step,'tumor_voxel':center_voxel,'tumor_ras_mm':(centroid*spacing+origin).tolist(),'mesh_center':center.tolist(),'mesh_scale':float(scale),'segments':stats,'window_presets':[{'name':'软组织','width':400,'level':50},{'name':'窄窗对比','width':200,'level':40},{'name':'骨窗','width':1600,'level':400}],'license':'CC BY-NC-SA 4.0','source':'https://github.com/neheller/kits19','imaging_source':'https://huggingface.co/datasets/neheller/KiTS-Challenge-Imaging','annotation':'Published manual segmentation, not a prediction made by this device.'}
components,count=ndimage.label(mask==1);counts=np.bincount(components.ravel());counts[0]=0
centroids=[np.array(ndimage.center_of_mass(mask==1,components,int(k))) for k in np.argsort(counts)[-2:]]
meta['part_voxels']={'tumor':meta['tumor_voxel']}
for name in ('kidney_a','kidney_b'):
 p=scene.geometry[name].bounds.mean(0);ras=p[[0,2,1]];ras[1]*=-1;voxel=(ras-origin)/(spacing*step)
 meta['part_voxels'][name]=min(centroids,key=lambda c:np.linalg.norm(c-voxel)).tolist()
meta['affected_kidney']=min(('kidney_a','kidney_b'),key=lambda k:np.linalg.norm((np.array(meta['part_voxels'][k])-meta['tumor_voxel'])*meta['spacing_mm']))
(out/'case.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),'utf8');shutil.copy2(src/'DATA_LICENSE.txt',out/'LICENSE.txt');shutil.copy2(src/'SOURCE_MANIFEST.json',out/'SOURCE_MANIFEST.json')
(out/'ATTRIBUTION.md').write_text('''# KiTS19 case_00000

Source: Nicholas Heller et al., The KiTS19 Challenge Data: 300 Kidney Tumor Cases with Clinical Context, CT Semantic Segmentations, and Surgical Outcomes (2019). https://github.com/neheller/kits19 and https://kits19.grand-challenge.org/data/

Data and these derivative CT, masks and meshes: CC BY-NC-SA 4.0. Full license in LICENSE.txt. Original data are anonymized research CT and supervised manual kidney/tumor labels. This viewer is an educational interaction demonstration, not a diagnostic system.

Modifications: reoriented to canonical RAS; CT rounded to int16 HU and subsampled every 3 voxels; labels sampled on exactly the same grid; meshes generated with marching cubes from original labels (kidneys step 2, tumor step 1). Rendering uses R,S,-A coordinates. No predicted or invented lesion is added. Source byte hashes in SOURCE_MANIFEST.json. Original data are retained locally in research/medical_v56; full volumes are not required on the board.
''','utf8')
print(json.dumps(meta,ensure_ascii=False));print('total bytes',sum(p.stat().st_size for p in out.iterdir()))
