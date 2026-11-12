import * as THREE from 'three';
import {GLTFLoader} from '/assets/three/GLTFLoader.js';
import {loadCT,drawCT,modelPosition} from '/assets/medical/ct.js';
const $=s=>document.querySelector(s),spec=await(await fetch('/api/medical/spec')).json();
let token=decodeURIComponent(location.hash.slice(1));try{token=token||sessionStorage.getItem('hmi.medical.auth')||sessionStorage.getItem('hmi.console.auth')||'';if(token)sessionStorage.setItem('hmi.medical.auth',token)}catch{}history.replaceState(null,'',location.pathname);
let state={page:0,case_id:spec.default_case},rows=[],session={},fresh=false,layoutKey='',ctKey='',visualKey='',loading=false,lastPoll=0,dirty=true,animUntil=0,lastDraw=0,localReceipt='',receiptUntil=0;
let displayZoom=1,calibrating=false;
const assets=new Map(),volumes=new Map(),loader=new GLTFLoader();let renderer=null;
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(34,1,.05,50);camera.position.z=5.4;
scene.add(new THREE.HemisphereLight(0xe7edf0,0x30383d,1.7));
for(const [color,intensity,position] of [[0xffe2d0,2.6,[-3,4,5]],[0xa9d9df,1.8,[4,1,-2]],[0xe9f0f2,.8,[0,-3,3]]]){const light=new THREE.DirectionalLight(color,intensity);light.position.set(...position);scene.add(light)}
try{renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(devicePixelRatio,1));renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.05;renderer.setClearColor(0,0);renderer.autoClear=false;$('#stage').append(renderer.domElement);document.body.dataset.renderer='webgl'}catch(e){notice('三维显示不可用');document.body.dataset.renderer='failed'}
function meta(){return spec.cases.find(c=>c.id===state.case_id)||spec.cases[0]}
function notice(text){localReceipt=text;receiptUntil=performance.now()+5000;$('#receipt').textContent=text}
async function model(c){
 if(assets.has(c.id))return assets.get(c.id);
 const entry={root:null,promise:null,meshes:[],anchors:{},marker:null};assets.set(c.id,entry);
 entry.promise=loader.loadAsync('/assets/medical/'+c.model).then(gltf=>{
  const root=new THREE.Group();gltf.scene.updateMatrixWorld(true);
  gltf.scene.traverse(o=>{if(!o.isMesh)return;const geometry=o.geometry.clone().applyMatrix4(o.matrixWorld);geometry.translate(...c.mesh_center.map(v=>-v));geometry.scale(c.mesh_scale,c.mesh_scale,c.mesh_scale);if(!geometry.attributes.normal)geometry.computeVertexNormals();geometry.computeBoundingBox();
   const color=o.name==='tumor'?0xca8271:0xc0c7c8,material=new THREE.MeshPhongMaterial({color,shininess:56,specular:0x789497,side:THREE.DoubleSide,transparent:true,opacity:o.name==='tumor'?1:.72});
   const mesh=new THREE.Mesh(geometry,material);mesh.name=o.name;mesh.userData.base=material.color.clone();root.add(mesh);entry.meshes.push(mesh);
   const centre=geometry.boundingBox.getCenter(new THREE.Vector3()),point=new THREE.Vector3();let distance=Infinity;
   for(let i=0;i<geometry.attributes.position.count;i++){point.fromBufferAttribute(geometry.attributes.position,i);const d=point.distanceToSquared(centre);if(d<distance){distance=d;entry.anchors[o.name]={mesh,point:point.clone()}}}
  });
  const marker=new THREE.Mesh(new THREE.SphereGeometry(.022,16,8),new THREE.MeshBasicMaterial({color:0xa4f1d8,depthTest:false}));marker.renderOrder=9;root.add(marker);entry.marker=marker;entry.root=root;scene.add(root);root.visible=false;dirty=true;animUntil=performance.now()+600;return entry;
 }).catch(e=>{assets.delete(c.id);notice('模型载入失败');document.body.dataset.modelError=String(e);throw e});
 return entry;
}
async function ensureModels(){for(const c of state.page===0?spec.cases:[meta()]){const entry=await model(c);entry.promise.catch(()=>{})}}
function setRect(element,r){Object.assign(element.style,{left:r[0]*100+'%',top:r[1]*100+'%',width:r[2]*100+'%',height:r[3]*100+'%'})}
async function activate(id){if(!token){notice('请从控制台打开');return}try{const r=await fetch('/api/medical/target',{method:'POST',signal:AbortSignal.timeout(6000),headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify({target_id:id})});const d=await r.json();if(!r.ok)throw Error(d.error||'未执行');notice('已提交')}catch(e){notice(e.message)}}
function controls(){
 const key=JSON.stringify([state.page,state.case_id,rows.map(r=>[r.id,r.rect])]);
 if(key!==layoutKey){layoutKey=key;ctKey='';$('#controls').replaceChildren();$('#leaders').replaceChildren();
  for(const row of rows){const b=document.createElement('button');b.dataset.id=row.id;b.dataset.key=row.key;b.setAttribute('aria-label',row.label);b.className=row.plane?'ct-panel':row.thumbnail?'case-card':row.model_preview?'model-card':row.part?'region':'content-button';setRect(b,row.rect);
   if(row.thumbnail){const img=document.createElement('img');img.src='/assets/medical/'+row.thumbnail;img.alt=row.label+' CT';b.append(img);const n=document.createElement('span');n.className='case-number';n.textContent=row.label;b.append(n)}
   else if(row.plane){const canvas=document.createElement('canvas');canvas.setAttribute('aria-label',row.label);b.append(canvas);const label=document.createElement('span');label.className='slice-label';label.textContent=row.label;b.append(label);const status=document.createElement('small');b.append(status)}
   else{const label=document.createElement('span');label.textContent=row.label;b.append(label);if(row.part){const small=document.createElement('small');small.textContent=row.caption||'';b.append(small)}}
   b.onclick=()=>activate(row.id);$('#controls').append(b);
   if(row.part||row.content?.startsWith('locate:')){const path=document.createElementNS('http://www.w3.org/2000/svg','path');path.dataset.key=row.key;path.setAttribute('marker-end','url(#arrow)');$('#leaders').append(path)}
  }
  ensureModels();dirty=true;animUntil=performance.now()+600;
 }
 for(const b of $('#controls').children){const row=rows.find(r=>r.id===b.dataset.id);b.classList.toggle('selected',fresh&&session.phase==='SELECTING'&&session.target?.id===b.dataset.id);b.classList.toggle('locked',session.phase==='LOCKED'&&session.target?.id===b.dataset.id);b.classList.toggle('focused',!!(row?.part&&state.focus&&row.part===state.part));}
 document.body.dataset.phase=spec.pages[state.page||0].key;$('#phase').textContent=spec.pages[state.page||0].title;$('#case').textContent=state.page?meta().title:'';for(const [i,step]of [...document.querySelectorAll('#steps span')].entries()){step.classList.toggle('current',i===state.page);step.classList.toggle('complete',i<state.page);}
 $('#record').hidden=state.page!==3;
 if(state.page===3){const r=state.record;$('#record-status').textContent=r?'已记录':'待记录';$('#record-location').textContent=r?'定位  '+r.ras_mm.map(v=>v.toFixed(1)).join(' / ')+' mm':state.suspect_voxel?'已标记观察位置':'尚未标记';$('#record-views').textContent=[state.reviewed?.ct?'CT 已查看':'CT 待查看',state.reviewed?.volume?'三维已查看':'三维待查看'].join(' · ')}
}
async function updateCT(){
 if(!rows.some(r=>r.plane))return;
 const c=meta(),key=JSON.stringify([c.id,state.page,state.plane,state.crosshair,state.overlay,state.zoom,state.focus]);if(key===ctKey)return;
 if(!volumes.has(c.id)){if(loading)return;loading=true;$('#loading').textContent='载入影像';try{volumes.set(c.id,await loadCT(c))}catch(e){notice(e.message)}finally{loading=false;$('#loading').textContent=''}if(c.id!==meta().id)return;}
 const data=volumes.get(c.id);if(!data)return;ctKey=key;
 for(const row of rows.filter(r=>r.plane)){const b=[...$('#controls').children].find(b=>b.dataset.id===row.id);if(!b)continue;
  const info=drawCT(b.querySelector('canvas'),row.plane,state,c,data);b.querySelector('small').textContent=`${info.index} / ${info.total}`;
  const primary=state.page===1&&row.plane===state.plane;const factor=primary?(state.zoom||1)*(state.focus?1.35:1):1;
  const axes=row.plane==='axial'?[0,1]:row.plane==='coronal'?[0,2]:[1,2],point=state.crosshair||c.initial_voxel;
  const canvas=b.querySelector('canvas'),ratio=c.shape[axes[0]]*c.spacing_mm[axes[0]]/(c.shape[axes[1]]*c.spacing_mm[axes[1]]),width=Math.min(b.clientWidth,b.clientHeight*ratio);canvas.style.width=width+'px';canvas.style.height=(width/ratio)+'px';canvas.style.objectFit='fill';canvas.style.transformOrigin=`${(1-point[axes[0]]/(c.shape[axes[0]]-1))*100}% ${(1-point[axes[1]]/(c.shape[axes[1]]-1))*100}%`;canvas.style.transform=`scale(${factor})`;
 }
 dirty=true;
}
function drawLeaders(entry,viewport){
 const point=new THREE.Vector3();entry.root.updateMatrixWorld(true);
 for(const row of rows.filter(r=>r.part)){
  const path=$(`#leaders path[data-key="${row.key}"]`),anchor=entry.anchors[row.part];if(!path||!anchor)continue;
  point.copy(anchor.point).applyMatrix4(anchor.mesh.matrixWorld).project(camera);const visible=point.z>=-1&&point.z<=1&&Math.abs(point.x)<=1&&Math.abs(point.y)<=1;path.style.display=visible?'':'none';if(!visible)continue;
  const x=(viewport[0]+(point.x+1)*viewport[2]/2)*innerWidth,y=(viewport[1]+(1-point.y)*viewport[3]/2)*innerHeight;
  const r=row.rect,left=r[0]+r[2]/2<x/innerWidth,sx=(r[0]+(left?r[2]:0))*innerWidth,sy=(r[1]+r[3]/2)*innerHeight,elbow=sx+(left?16:-16);
  path.setAttribute('d',`M${sx},${sy} L${elbow},${sy} L${x},${y}`);
 }
}
function drawCTLeaders(){
 const row=rows.find(r=>r.plane===state.plane);if(!row)return;const b=[...$('#controls').children].find(b=>b.dataset.id===row.id),canvas=b?.querySelector('canvas');if(!canvas)return;
 const rect=canvas.getBoundingClientRect(),c=meta(),axes=row.plane==='axial'?[0,1]:row.plane==='coronal'?[0,2]:[1,2];
 for(const r of rows.filter(r=>r.content?.startsWith('locate:'))){const point=c.part_voxels[r.key],path=$(`#leaders path[data-key="${r.key}"]`);if(!point||!path)continue;
  const x=rect.x+(1-point[axes[0]]/(c.shape[axes[0]]-1))*rect.width,y=rect.y+(1-point[axes[1]]/(c.shape[axes[1]]-1))*rect.height;
  const bounds=b.getBoundingClientRect();path.style.display=x<bounds.left||x>bounds.right||y<bounds.top||y>bounds.bottom?'none':'';
  path.setAttribute('d',`M${(r.rect[0]+r.rect[2]/2)*innerWidth},${(r.rect[1]+r.rect[3])*innerHeight} L${x},${y}`);
 }
}
function renderModel(entry,viewport,animate){
 if(!entry?.root)return;const root=entry.root;root.visible=true;
 const part=state.focus&&state.part?entry.meshes.find(m=>m.name===state.part):null,box=part?.geometry.boundingBox;
 const center=box?.getCenter(new THREE.Vector3())||new THREE.Vector3(),factor=box?Math.min(4,2.3/Math.max(...box.getSize(new THREE.Vector3()).toArray())):1;
 const orbit=animate?(state.orbit||[0,0,0]):[0,-15,0],zoom=animate?displayZoom:1;
 root.rotation.set(...orbit.map(v=>v*Math.PI/180));root.scale.setScalar(zoom);
 for(const mesh of entry.meshes){mesh.scale.setScalar(animate?factor:1);mesh.position.copy(center).multiplyScalar(animate?-factor:0);mesh.material.opacity=mesh.name==='tumor'?1:animate&&part?(mesh===part?.9:.13):.72;mesh.material.depthWrite=mesh.material.opacity>.99;mesh.material.emissive.set(animate&&part===mesh?0x153434:0)}
 entry.marker.visible=!!(animate&&state.suspect_voxel);if(entry.marker.visible)entry.marker.position.fromArray(modelPosition(meta(),state.crosshair||state.suspect_voxel)).sub(center).multiplyScalar(factor);
 camera.aspect=innerWidth*viewport[2]/(innerHeight*viewport[3]);camera.position.z=5.1*Math.max(1,.7/camera.aspect);camera.updateProjectionMatrix();
 renderer.setViewport(viewport[0]*innerWidth,(1-viewport[1]-viewport[3])*innerHeight,viewport[2]*innerWidth,viewport[3]*innerHeight);renderer.render(scene,camera);
 if(animate&&state.page===2)drawLeaders(entry,viewport);root.visible=false;
}
function draw(now){requestAnimationFrame(draw);if(!renderer||document.hidden||calibrating||now-lastDraw<33||(!dirty&&now>animUntil))return;lastDraw=now;displayZoom+=(Number(state.zoom||1)-displayZoom)*.6;renderer.setViewport(0,0,innerWidth,innerHeight);renderer.clear();for(const e of assets.values())if(e.root)e.root.visible=false;
 if(state.page===0){for(const r of rows.filter(r=>r.thumbnail)){const c=spec.cases.find(c=>c.id===r.key);renderModel(assets.get(c.id),[r.rect[0],r.rect[1]+r.rect[3]*.45,r.rect[2],r.rect[3]*.49],false)}}
 else if(state.page===2)renderModel(assets.get(meta().id),spec.pages[2].model_viewport,true);
 else if(state.page===3){const r=rows.find(r=>r.model_preview);if(r)renderModel(assets.get(meta().id),r.rect,true)}
 else if(state.page===1){const r=rows.find(r=>r.model_preview);if(r)renderModel(assets.get(meta().id),[r.rect[0],r.rect[1],r.rect[2],r.rect[3]*.86],false);drawCTLeaders();}dirty=false;document.body.dataset.caseId=meta().id;document.body.dataset.readyStage=state.page;document.body.dataset.triangles=renderer.info.render.triangles;
}
function resize(){if(renderer)renderer.setSize(innerWidth,innerHeight);$('#annotation').setAttribute('viewBox',`0 0 ${innerWidth} ${innerHeight}`);dirty=true;ctKey='';updateCT();animUntil=performance.now()+200}addEventListener('resize',resize);resize();requestAnimationFrame(draw);
let polling=false;
async function poll(){if(polling||document.hidden)return;polling=true;try{const response=await fetch('/api/state',{signal:AbortSignal.timeout(2000)});const data=await response.json();const paused=data.hmi_fresh&&data.hmi?.state==='CALIBRATING';if(calibrating&&!paused){dirty=true;ctKey='';}calibrating=paused;if(calibrating||!data.demo?.case_id)return;
 const previous=visualKey;if(state.page!==data.demo.page||state.case_id!==data.demo.case_id)displayZoom=data.demo.zoom||1;state=data.demo;rows=data.medical_view?.rows||[];session=data.hmi?.target_session||{};fresh=data.hmi_fresh;
 visualKey=JSON.stringify([state.page,state.case_id,state.zoom,state.focus,state.part,state.orbit,state.suspect_voxel,state.crosshair,state.overlay]);if(previous!==visualKey){dirty=true;animUntil=performance.now()+150}
 controls();updateCT();$('#receipt').textContent=performance.now()<receiptUntil?localReceipt:fresh?(state.rotating?(state.page===1?'阅片中':'旋转中'):(data.display?.receipt||data.display?.status||'就绪')):'连接中断';lastPoll=performance.now();
 }catch(e){if(performance.now()-lastPoll>2000)$('#receipt').textContent='连接中断'}finally{polling=false}}
poll();setInterval(poll,60);
