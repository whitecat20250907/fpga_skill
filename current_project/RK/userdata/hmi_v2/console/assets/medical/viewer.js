import * as THREE from 'three';
import {loadCT,drawCT,modelPosition} from '/assets/medical/ct.js';
import {GLTFLoader} from '/assets/three/GLTFLoader.js';
const $=s=>document.querySelector(s);let token=decodeURIComponent(location.hash.slice(1));try{token=token||sessionStorage.getItem('hmi.medical.auth')||sessionStorage.getItem('hmi.console.auth')||'';if(token)sessionStorage.setItem('hmi.medical.auth',token)}catch(e){}history.replaceState(null,'',location.pathname);
const spec=await(await fetch('/api/medical/spec')).json();let state={page:0,zoom:1,rotation:0,focus:false},session={},fresh=false,current=-1,busy=false,last=0,signature='',loadGeneration=0,dirty=true,animateUntil=0;
let localReceipt="",receiptUntil=0;function showError(text){localReceipt=text;receiptUntil=performance.now()+8000;$("#receipt").textContent=text}let renderedAt=0;let renderer,scene,camera,root,meshes=[],partSets={},partAnchors={},cache=new Map(),desired={scale:1,rotation:0,part:null,focus:false};let ctData=null,ctSignature='',ctLoading=false,marker=null;const selectedColor=new THREE.Color('#9ddbd8');
try{renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(devicePixelRatio,1));renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.08;renderer.setClearColor(0x000000,0);$('#stage').append(renderer.domElement);scene=new THREE.Scene();camera=new THREE.PerspectiveCamera(34,1,.05,60);camera.position.set(0,0,5.6);scene.add(new THREE.HemisphereLight(0xe6edf2,0x30303a,1.6));for(const [color,intensity,position] of [[0xffe0c9,2.8,[-3,4,5]],[0x92c9df,2.1,[4,1,-2]],[0xe7efff,1.0,[0,-3,3]]]){const l=new THREE.DirectionalLight(color,intensity);l.position.set(...position);scene.add(l)}document.body.dataset.renderer='webgl';}catch(e){$('#loading').textContent='当前浏览器未能启用三维显示';$('#loading').className='error';document.body.dataset.renderer='failed';}
const loader=new GLTFLoader();
function match(name,pattern){const n=name.toLowerCase();if(pattern==='__left__')return n.endsWith('_l');if(pattern==='__right__')return n.endsWith('_r');if(pattern==='__stem__')return /pons|medulla|midbrain/.test(n);return n.includes(pattern)}
function baseColor(name,page){const n=name.toLowerCase();if(spec.pages[page].case)return n==='tumor'?'#e28a73':'#b0c3ca';if(page===0)return n.includes('valve')?'#f1d2a0':n.includes('papillary')?'#ca8b6e':n.includes('septum')?'#bc766f':n.includes('right_')?'#699eaa':'#c48078';if(page===1)return /cerebell|pons|medulla/.test(n)?'#9aa8b1':n.endsWith('_r')?'#b49b94':'#d0b6aa';return /papilla|pyramid/.test(n)?'#d5a389':n.includes('hilum')?'#81adb5':'#b7807a'}
async function loadPage(page){const generation=++loadGeneration;current=page;signature='';if(root)root.visible=false;$('#loading').style.display='block';$('#loading').textContent='正在载入三维参考模型…';const p=spec.pages[page];document.body.classList.toggle('case-view',!!p.case);resize();$('#model-status').textContent=p.case?'CT + SEGMENTATION / KiTS19':'真实三维网格 / HRA';$('#attribution').innerHTML=p.case?'KiTS19 · Heller et al. · CC BY-NC-SA 4.0<br>公开病例人工标注 · 降采样教学演示':'HRA · Browne & Schlehlein · CC BY 4.0<br>解剖参考模型 · 教学交互演示';$('#title').replaceChildren(document.createTextNode(p.title));const sub=document.createElement('span');sub.textContent=p.subtitle;$('#title').append(sub);$('.chapter').textContent=(p.case?'CASE REVIEW / ':'ANATOMY / ')+String(page+1).padStart(2,'0');$('#description').textContent=p.description;$('#target-count').textContent=(p.parts.length+(p.controls||[]).length)+' 个可选目标';$('#page').textContent=String(page+1).padStart(2,'0')+' / '+String(spec.pages.length).padStart(2,'0');if(!renderer)return;
 try{let group=cache.get(page);if(!group){const gltf=await loader.loadAsync('/assets/medical/'+p.model);gltf.scene.updateMatrixWorld(true);group=new THREE.Group();gltf.scene.traverse(o=>{if(!o.isMesh)return;const geo=o.geometry.clone().applyMatrix4(o.matrixWorld);if(!geo.attributes.normal)geo.computeVertexNormals();geo.computeBoundingBox();const color=baseColor(o.name,page);const mat=new THREE.MeshPhongMaterial({color,shininess:48,specular:0x7d8995,side:THREE.DoubleSide});const m=new THREE.Mesh(geo,mat);m.name=o.name;m.userData.base=new THREE.Color(color);m.userData.home=new THREE.Vector3();group.add(m)});const box=new THREE.Box3().setFromObject(group),center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3()),factor=2.65/Math.max(size.x,size.y,size.z);for(const m of group.children){m.geometry.translate(-center.x,-center.y,-center.z);m.geometry.scale(factor,factor,factor);m.geometry.computeBoundingBox()}cache.set(page,group)}if(generation!==loadGeneration)return;if(root)scene.remove(root);root=group;root.visible=true;scene.add(root);meshes=root.children.filter(m=>m.isMesh&&!m.userData.crosshair);marker=root.children.find(m=>m.userData.crosshair)||null;if(p.case&&!marker){marker=new THREE.Mesh(new THREE.SphereGeometry(.018,12,8),new THREE.MeshBasicMaterial({color:0x8ce6ef,depthTest:false}));marker.userData.crosshair=true;marker.renderOrder=10;root.add(marker)}partSets={};for(const part of p.parts)partSets[part.key]=meshes.filter(m=>match(m.name,part.match));buildPartAnchors();root.rotation.set(0,p.yaw,0);root.scale.setScalar(state.zoom||1);for(const m of meshes){m.position.set(0,0,0);m.scale.setScalar(1)}$('#loading').style.display='none';document.body.dataset.meshes=meshes.length;document.body.dataset.readyPage=page;dirty=true;updateDesired();}catch(e){$('#loading').textContent='模型载入失败，请返回控制台重试';$('#loading').className='error';document.body.dataset.modelError=String(e)}}
function updateDesired(){desired={scale:state.zoom||1,rotation:(state.orbit||[0,(state.rotation||0)*45,0]).map((v,i)=>v*Math.PI/180+(i===1?(spec.pages[current]?.yaw||0):0)),part:state.part,focus:!!state.focus};document.body.classList.toggle('focus',desired.focus);$('#focus-label').textContent=spec.pages[current]?.parts.find(p=>p.key===state.part)?.label||'整体聚焦';dirty=true;animateUntil=performance.now()+900;}
function regionBounds(part){const box=new THREE.Box3();for(const m of partSets[part]||[])box.union(m.geometry.boundingBox);return box.isEmpty()?null:box;}
// Anchors are source-mesh vertices, selected once per page load. Project the
// same vertex through the mesh world matrix every draw (including focus/zoom).
function buildPartAnchors(){
 partAnchors={};const box=new THREE.Box3(),center=new THREE.Vector3(),candidate=new THREE.Vector3();
 for(const p of spec.pages[current].parts){
  const members=partSets[p.key]||[];box.makeEmpty();for(const m of members)box.union(m.geometry.boundingBox);
  if(box.isEmpty())continue;box.getCenter(center);let best=Infinity,anchor=null;
  for(const mesh of members){const positions=mesh.geometry.attributes.position;
   for(let i=0;i<positions.count;i++){candidate.fromBufferAttribute(positions,i);const distance=candidate.distanceToSquared(center);
    if(distance<best){best=distance;anchor={mesh,point:candidate.clone()};}
   }
  }
  if(anchor)partAnchors[p.key]=anchor;
 }
}
// Four segments per annotation: short label elbow, leader, two arrow wings.
// The overlay shares the WebGL canvas; it creates no additional click targets.
const leaderOverlay=new THREE.Scene(),leaderCamera=new THREE.OrthographicCamera(-1,1,1,-1,0,2);
leaderCamera.position.z=1;
const leaderLines=new Float32Array(64*4*6),leaderColors=new Float32Array(64*4*6);
const lineGeometry=new THREE.BufferGeometry();
lineGeometry.setAttribute('position',new THREE.BufferAttribute(leaderLines,3).setUsage(THREE.DynamicDrawUsage));
lineGeometry.setAttribute('color',new THREE.BufferAttribute(leaderColors,3).setUsage(THREE.DynamicDrawUsage));
lineGeometry.setDrawRange(0,0);
const lineLayer=new THREE.LineSegments(lineGeometry,new THREE.LineBasicMaterial({vertexColors:true,transparent:true,opacity:.7,depthTest:false,depthWrite:false}));
lineLayer.frustumCulled=false;leaderOverlay.add(lineLayer);
const leaderPoint=new THREE.Vector3(),leaderViewport=new THREE.Vector4();
const normalLeader=new THREE.Color('#69838d'),activeLeader=new THREE.Color('#b8efdf');
$('#leaders').style.display='none';
function leaders(){
 if(!root||state.inspection){document.body.dataset.annotationCount=0;return 0;}
 root.updateMatrixWorld(true);renderer.getViewport(leaderViewport);
 let count=0,offset=0;
 function segment(x1,y1,x2,y2,color){
  for(const [x,y] of [[x1,y1],[x2,y2]]){
   leaderLines[offset]=2*x/innerWidth-1;leaderLines[offset+1]=1-2*y/innerHeight;leaderLines[offset+2]=0;
   leaderColors[offset]=color.r;leaderColors[offset+1]=color.g;leaderColors[offset+2]=color.b;offset+=3;
  }
 }
 for(const p of spec.pages[current].parts){
  const anchor=partAnchors[p.key];if(!anchor||count>=64)continue;
  leaderPoint.copy(anchor.point).applyMatrix4(anchor.mesh.matrixWorld).project(camera);
  if(!Number.isFinite(leaderPoint.x)||leaderPoint.z < -1||leaderPoint.z > 1||Math.abs(leaderPoint.x)>1||Math.abs(leaderPoint.y)>1)continue;
  const x=leaderViewport.x+(leaderPoint.x+1)*.5*leaderViewport.z;
  const y=innerHeight-(leaderViewport.y+(leaderPoint.y+1)*.5*leaderViewport.w);
  const r=p.rect,left=r[0]+r[2]/2<.5;
  const sx=(r[0]+(left?r[2]:0))*innerWidth,sy=(r[1]+r[3]/2)*innerHeight;
  const elbow=sx+(left?1:-1)*Math.min(26,innerWidth*.018);
  const dx=x-elbow,dy=y-sy,length=Math.hypot(dx,dy);if(length<12)continue;
  const ux=dx/length,uy=dy/length,wing=4,back=9;
  const color=(desired.focus&&desired.part===p.key||session.target?.part===p.key)?activeLeader:normalLeader;
  segment(sx,sy,elbow,sy,color);segment(elbow,sy,x,y,color);
  segment(x,y,x-back*ux+wing*uy,y-back*uy-wing*ux,color);
  segment(x,y,x-back*ux-wing*uy,y-back*uy+wing*ux,color);count++;
 }
 lineGeometry.setDrawRange(0,offset/3);lineGeometry.attributes.position.needsUpdate=true;lineGeometry.attributes.color.needsUpdate=true;
 const autoClear=renderer.autoClear;renderer.autoClear=false;renderer.setViewport(0,0,innerWidth,innerHeight);
 renderer.render(leaderOverlay,leaderCamera);renderer.setViewport(leaderViewport);renderer.autoClear=autoClear;
 document.body.dataset.annotationCount=count;
 return renderer.info.render.calls;
}

function render(now){requestAnimationFrame(render);if(now-renderedAt<33)return;renderedAt=now;if(!renderer||!root||!root.visible||document.hidden||(!dirty&&now>animateUntil))return;const focusMembers=desired.part?(partSets[desired.part]||[]):meshes;const bounds=desired.focus&&desired.part?regionBounds(desired.part):null;const center=bounds?.getCenter(new THREE.Vector3())||new THREE.Vector3();const scale=bounds?Math.min(4.5,2.3/Math.max(...bounds.getSize(new THREE.Vector3()).toArray())):1;['x','y','z'].forEach((axis,i)=>root.rotation[axis]+=(desired.rotation[i]-root.rotation[axis])*.16);root.scale.lerp(new THREE.Vector3().setScalar(desired.scale),.16);
 for(const m of meshes){const selected=desired.focus&&focusMembers.includes(m),ghost=desired.focus&&!selected;const paired=!!spec.pages[current]?.case;const f=paired&&desired.focus?scale:selected?scale:1;const dest=(selected||paired&&desired.focus)?center.clone().multiplyScalar(-f):new THREE.Vector3();m.scale.lerp(new THREE.Vector3().setScalar(f),.16);m.position.lerp(dest,.16);const opacity=paired?(m.name==='tumor'?1:desired.focus?.13:.48):ghost?.07:current===2&&!desired.focus&&/capsule|outer_cortex/.test(m.name)?.22:1;m.material.opacity+=(opacity-m.material.opacity)*.2;m.material.transparent=m.material.opacity<.995;m.material.depthWrite=!m.material.transparent;m.material.color.lerp(selected&&!paired?selectedColor:m.userData.base,.16);m.material.emissive.set(selected?0x0d3039:0);}
 if(marker){const meta=spec.pages[current].case,point=new THREE.Vector3(...modelPosition(meta,state.crosshair||meta.tumor_voxel)),f=desired.focus?scale:1;marker.position.copy(point.sub(desired.focus?center:new THREE.Vector3()).multiplyScalar(f));marker.visible=!!state.overlay;}renderer.render(scene,camera);const anatomyCalls=renderer.info.render.calls,triangles=renderer.info.render.triangles;const annotationCalls=leaders();dirty=false;document.body.dataset.drawCalls=anatomyCalls+annotationCalls;document.body.dataset.triangles=triangles;document.body.dataset.annotationRenderer='webgl';}
function resize(){if(!renderer)return;renderer.setSize(innerWidth,innerHeight);const paired=!!spec.pages[current]?.case;if(paired){renderer.setViewport(innerWidth*.19,innerHeight*.14,innerWidth*.54,innerHeight*.68);camera.aspect=innerWidth*.54/(innerHeight*.68)}else{renderer.setViewport(0,0,innerWidth,innerHeight);camera.aspect=innerWidth/innerHeight;}camera.position.z=paired?5.15*Math.max(1,.92/camera.aspect):5.8;camera.updateProjectionMatrix();dirty=true;animateUntil=performance.now()+100}addEventListener('resize',resize);resize();requestAnimationFrame(render);
async function activate(id){if(!token){showError('请用手势确认；电脑点击请从控制台打开演示');return}try{const r=await fetch('/api/medical/target',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify({target_id:id})});const d=await r.json();if(!r.ok)throw Error(d.error||'操作未执行');$('#receipt').textContent='已提交，等待执行回执'}catch(e){showError(e.message)}}
function medicalRows(){
 const page=spec.pages[state.page||0];return [...(page.controls||[]),...page.parts].map(t=>({...t,rect:state.inspection&&t.content===state.inspection?page.inspection_rect:state.inspection&&t.detail_rect?t.detail_rect:t.rect,label:t.label+(state.inspection&&t.content===state.inspection?' · 再次点击返回':'')}));
}
function controls(){
 const page=state.page||0,rows=medicalRows(),sig=page+':'+(state.inspection||'');document.body.classList.toggle('inspect-view',!!state.inspection);updateInspector();
 if(signature!==sig){signature=sig;ctSignature='';$('#controls').replaceChildren();$('#ct-panes').replaceChildren();
  for(const t of rows){const b=document.createElement('button');b.dataset.id=`demo:${t.match?'roi':'control'}:${page}:${t.key}`;b.className=t.match?'region':'control';b.dataset.side=t.rect[0]<.5?'left':'right';b.setAttribute('aria-label',t.label);
   const expanded=t.content&&t.content===state.inspection;
   if(t.plane&&(expanded||t.preview!==false)){b.className='ct-panel';b.dataset.plane=t.plane;b.innerHTML='<strong></strong><canvas></canvas><span class="orientation"></span><small></small>';b.querySelector('strong').textContent=t.label.replace(' · 再次点击返回','');b.querySelector('canvas').setAttribute('aria-label',t.label+'切片');b.querySelector('.orientation').textContent=t.plane==='sagittal'?'A · 前　　P · 后':'R · 右　　L · 左';}
   else if(t.paragraphs&&expanded){b.className='case-report';const eyebrow=document.createElement('small');eyebrow.textContent='KiTS19 / CASE 00000';b.append(eyebrow);const title=document.createElement('h2');title.textContent=t.label.replace(' · 再次点击返回','');b.append(title);for(const text of t.paragraphs){const para=document.createElement('p');para.textContent=text;b.append(para)}const hint=document.createElement('small');hint.textContent='病例资料';b.append(hint);}
   else{const index=document.createElement('span');index.className='target-code';index.textContent=t.code||'';b.append(index);const label=document.createElement('span');label.className='part-name';label.textContent=t.label;b.append(label);if(t.caption){const caption=document.createElement('small');caption.className='target-caption';caption.textContent=t.caption;b.append(caption)}}
   Object.assign(b.style,{left:t.rect[0]*100+'%',top:t.rect[1]*100+'%',width:t.rect[2]*100+'%',height:t.rect[3]*100+'%'});b.onclick=()=>activate(b.dataset.id);$('#controls').append(b);
  }
 }
 for(const b of $('#controls').children){b.setAttribute('aria-pressed',String(!!(state.focus&&b.dataset.id.endsWith(':'+state.part)||state.inspection&&b.dataset.id.endsWith(':'+rows.find(t=>t.content===state.inspection)?.key))));b.classList.toggle('selected',fresh&&session.phase==='SELECTING'&&session.target?.id===b.dataset.id);b.classList.toggle('locked',session.phase==='LOCKED'&&session.target?.id===b.dataset.id);b.classList.toggle('focused',state.focus&&b.dataset.id.endsWith(':'+state.part))}
}

function updateInspector(){
 const p=spec.pages[state.page||0],part=p.parts.find(t=>t.key===state.part),selected=state.focus&&part;
 $('#selection-name').textContent=selected?part.label:p.case?'同病例 CT / 三维对应':'整体结构';
 const count=selected?(partSets[part.key]||[]).length:meshes.length;
 $('#selection-info').textContent=selected?`${part.caption} · ${count} 个源网格 · 再次确认恢复整体`:p.case?'人工标注与影像使用同一坐标系':'选择任一结构 · 局部聚焦 / 邻近结构半透明';
}
async function poll(){if(busy||document.hidden)return;busy=true;try{const r=await fetch('/api/state',{signal:AbortSignal.timeout(2000)});const s=await r.json(),d=s.demo||{};fresh=s.hmi_fresh;const previousTarget=session.target?.id;session=s.hmi?.target_session||{};if(previousTarget!==session.target?.id)dirty=true;const changed=JSON.stringify([state.page,state.zoom,state.orbit,state.focus,state.part,state.crosshair,state.overlay,state.inspection])!==JSON.stringify([d.page,d.zoom,d.orbit,d.focus,d.part,d.crosshair,d.overlay,d.inspection]);state=d;if((d.page||0)!==current)loadPage(d.page||0);else if(changed)updateDesired();controls();updateCT();$('#receipt').textContent=performance.now()<receiptUntil?localReceipt:fresh?(state.rotating?'旋转中':(s.display?.receipt||s.display?.status||'就绪')):'连接中断';last=performance.now();}catch(e){if(performance.now()-last>2000)$('#receipt').textContent='等待控制服务连接'}finally{busy=false}}poll();setInterval(poll,250);

async function updateCT(){
 const meta=spec.pages[state.page||0]?.case;if(!meta)return;
 const sig=JSON.stringify([state.page,state.crosshair,state.window,state.overlay,state.plane]);if(sig===ctSignature)return;
 if(!ctData){if(ctLoading)return;ctLoading=true;try{ctData=await loadCT(meta)}catch(e){$('#receipt').textContent=e.message}finally{ctLoading=false}if(!ctData)return;return updateCT()}
 ctSignature=sig;
 for(const b of document.querySelectorAll('.ct-panel')){const control=spec.pages[state.page||0].controls.find(t=>'demo:control:'+state.page+':'+t.key===b.dataset.id);const displayState=control?.overlay_override===undefined?state:{...state,overlay:control.overlay_override};const info=drawCT(b.querySelector('canvas'),b.dataset.plane,displayState,meta,ctData);b.querySelector('small').textContent=`${b.dataset.plane==='axial'?'横断面':b.dataset.plane==='coronal'?'正面切面':'侧面切面'} · ${info.index} / ${info.total} 层 · ${state.inspection===control?.content?'查看中':'CT'}`;}
 $('#model-status').textContent='CT + 3D · 同病例对应 · 珊瑚色为公开病灶标注';
}

