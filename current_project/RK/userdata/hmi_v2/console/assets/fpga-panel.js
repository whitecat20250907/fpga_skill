function fpgaPayload(d){
 const valid=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0;
 // Published image payload only: excludes transport headers, discarded packets and retries.
 if(!d.raw_image||!valid(d.raw_hz)||!valid(d.input_hz)||d.roi_status?.available)return null;
 return (d.raw_hz*1920*1080*3+d.input_hz*(640*360+128*128+192*192)*3)/1e6;
}
function renderFpga(d){
 const t=d.telemetry||{},fmt=(v,n=1)=>typeof v==='number'&&Number.isFinite(v)?v.toFixed(n):'—';
 const meters=(container,rows)=>{
  const root=document.getElementById(container);root.replaceChildren();
  for(const row of rows){const block=document.createElement('div');block.className='resource-row';
   const label=document.createElement('div'),name=document.createElement('span'),value=document.createElement('strong');
   name.textContent=row.name;value.textContent=fmt(row.percent)+'%';label.append(name,value);
   const meter=document.createElement('div'),fill=document.createElement('i');meter.className='meter';fill.style.width=(Number.isFinite(row.percent)?Math.max(0,Math.min(100,row.percent)):0)+'%';meter.append(fill);
   const caption=document.createElement('small');caption.textContent=row.detail||'';block.append(label,meter,caption);root.append(block);
  }
 };
 const profile=t.fpga_static,resources=profile?.resources||{};
 meters('fpga-resources',['LUT6','ERAM','DSP','SLICE'].map(name=>{const row=resources[name];return {name,percent:row&&row.total>0?row.used/row.total*100:null,detail:row?row.used+' / '+row.total:'等待构建记录'};}));
 document.getElementById('resource-version').textContent=profile?(profile.flash_verified?'Flash 固化 · 静态资源':profile.active_verified?'本次下载 · 静态资源':'构建记录 · 未核对当前位流'):'等待位流与报告核对';
 meters('compute-meters',[{name:'CPU',percent:t.cpu_percent},{name:'NPU 0',percent:t.npu_percent?.['0']},{name:'NPU 1',percent:t.npu_percent?.['1']}]);
 const link=t.pcie,mb=fpgaPayload(d),capacity=link?.encoded_capacity_MB_s;
 document.getElementById('pcie-link').textContent=link?link.speed_gt_s+' GT/s ×'+link.lanes:'协商速率待测';
 document.getElementById('pcie-payload').textContent=fmt(mb);
 document.getElementById('pcie-meter').style.width=(mb!==null&&capacity>0?Math.min(100,mb/capacity*100):0)+'%';
 document.getElementById('pcie-util').textContent=mb===null?'等待全部通道载荷计数':'发布量估算 · 非 PCIe 总线忙碌率';
 const counts=t.fpga_counters||{};
 document.getElementById('fifo').textContent='预览 FIFO 高水位 '+fmt(counts.preview_fifo_highwater_words,0)+' words';
 document.getElementById('model-link').textContent=fmt(counts.model_complete_frames_hz)+' / '+fmt(counts.model_drops_hz)+' Hz';
 document.getElementById('capture-error').textContent='中断 '+fmt(counts.model_abort_frames_hz)+' / 溢出 '+fmt(counts.model_overflows_hz)+' Hz';
}
if(typeof module!=='undefined')module.exports={fpgaPayload};
