const refresh = document.getElementById('model-refresh');
refresh.onclick = async () => {
  const status = document.getElementById('model-status');
  refresh.disabled = true;
  status.textContent = '正在读取开发板的同源模型输入…';
  try {
    const token = document.getElementById('auth').value.trim();
    const response = await fetch('/api/model/frame', {
      headers: {Authorization: 'Bearer ' + token}, signal: AbortSignal.timeout(5000)
    });
    const frame = await response.json();
    if (!response.ok) throw Error(response.status === 403 ? '请先在连接设置中配对控制台' : frame.error);
    const images = document.getElementById('model-planes');
    images.replaceChildren();
    for (const plane of frame.planes) {
      const figure = document.createElement('figure');
      const image = document.createElement('img');
      const caption = document.createElement('figcaption');
      image.src = plane.image; image.alt = plane.label;
      image.width = plane.size * 2; image.height = plane.size * 2;
      caption.textContent = `${plane.label} · ${plane.size} × ${plane.size} · RGB`;
      figure.append(image, caption); images.append(figure);
    }
    status.textContent = `快照帧 ${frame.sequence} · 采样时包龄 ${frame.age_ms.toFixed(1)} ms · 硬件代次 ${frame.epoch}。画面不会自动更新。`;
  } catch (error) { status.textContent = error.message; }
  finally { refresh.disabled = false; }
};
