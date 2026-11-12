// All views use the same RAS grid and the adapter's shared crosshair.
const volumes=new Map();
export function loadCT(meta){
 const base=meta.assets_base||'/assets/medical/kits19/',key=base+':'+meta.shape.join(',');
 if(!volumes.has(key))volumes.set(key,Promise.all(['ct.i16','labels.u8'].map(async name=>{const r=await fetch(base+name);if(!r.ok)throw Error('CT 数据载入失败');return r.arrayBuffer()})).then(([ct,labels])=>{
  const n=meta.shape.reduce((a,b)=>a*b,1);if(ct.byteLength!==n*2||labels.byteLength!==n)throw Error('CT 数据长度不一致');
  return {ct:new Int16Array(ct),labels:new Uint8Array(labels)};
 }).catch(e=>{volumes.delete(key);throw e}));
 return volumes.get(key);
}
export function rasPosition(meta,voxel){return voxel.map((v,i)=>meta.origin_ras_mm[i]+v*meta.spacing_mm[i])}
export function modelPosition(meta,voxel){const r=rasPosition(meta,voxel);return [r[0],r[2],-r[1]].map((v,i)=>(v-meta.mesh_center[i])*meta.mesh_scale)}
export function drawCT(canvas,plane,state,meta,data){
 const [nx,ny,nz]=meta.shape,point=state.crosshair||meta.tumor_voxel.map(Math.round),preset=meta.window_presets[state.window||0];
 const [u,v,fixed]=plane==='axial'?[0,1,2]:plane==='coronal'?[0,2,1]:[1,2,0];
 const w=meta.shape[u],h=meta.shape[v];canvas.width=w;canvas.height=h;
 canvas.style.aspectRatio=(w*meta.spacing_mm[u])/(h*meta.spacing_mm[v]);
 const ctx=canvas.getContext('2d'),image=ctx.createImageData(w,h),p=point.slice();
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  p[u]=w-1-x;p[v]=h-1-y;const index=(p[0]*ny+p[1])*nz+p[2],gray=Math.max(0,Math.min(255,Math.round((data.ct[index]-(preset.level-preset.width/2))*255/preset.width))),o=(y*w+x)*4;
  const label=state.overlay?data.labels[index]:0,color=label===2?[255,117,91]:label===1?[100,199,199]:null;
  for(let c=0;c<3;c++)image.data[o+c]=color?Math.round(gray*.6+color[c]*.4):gray;image.data[o+3]=255;
 }
 ctx.putImageData(image,0,0);ctx.strokeStyle='#8ce6ef';ctx.lineWidth=.65;ctx.setLineDash([3,3]);const x=w-1-point[u]+.5,y=h-1-point[v]+.5;
 ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();
 return {index:point[fixed]+1,total:meta.shape[fixed],window:preset.name,ras:rasPosition(meta,point)};
}
