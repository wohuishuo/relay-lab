(()=>{
  const $=s=>document.querySelector(s);
  try{if(localStorage.getItem('relay-theme'))document.documentElement.dataset.theme=localStorage.getItem('relay-theme')}catch{}
  $('#theme').addEventListener('click',()=>{const next=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=next;try{localStorage.setItem('relay-theme',next)}catch{}});
  $('#menu').addEventListener('click',()=>{const open=document.body.classList.toggle('menu-open');$('#menu').setAttribute('aria-expanded',String(open))});
  const pages=JSON.parse($('#search-data').textContent);
  $('#search').addEventListener('input',event=>{const term=event.target.value.trim().toLowerCase();let count=0;document.querySelectorAll('nav a[data-page]').forEach(a=>{const item=pages[a.dataset.page];const matches=!term||item.toLowerCase().includes(term);a.classList.toggle('hidden',!matches);if(matches)count++});$('#search-status').textContent=term?`找到 ${count} 篇相关内容`:''});
  document.querySelectorAll('article table').forEach(t=>{const wrapper=document.createElement('div');wrapper.className='table-wrap';t.before(wrapper);wrapper.appendChild(t)});
  if($('#bench-data')){
    const data=JSON.parse($('#bench-data').textContent);
    const labels={'reality':'REALITY','hy2':'HY2','tuic':'TUIC','ss':'SS'};
    function draw(scenario){
      const rows=data.filter(r=>r.scenario===scenario), maximum=Math.max(...rows.flatMap(r=>[r.summary.download.median_mbps,r.summary.upload.median_mbps]));
      $('#bars').replaceChildren();
      rows.forEach(r=>{const row=document.createElement('div');row.className='chart-row';const name=document.createElement('span');name.textContent=labels[r.protocol];row.appendChild(name);const bars=document.createElement('div');['download','upload'].forEach(direction=>{const value=r.summary[direction].median_mbps;const bar=document.createElement('div');bar.className='bar '+direction;const fill=document.createElement('i');fill.style.width=(100*value/maximum)+'%';bar.appendChild(fill);const label=document.createElement('em');label.textContent=(direction==='download'?'↓ 下载 ':'↑ 上传 ')+value.toFixed(2)+' Mbps';bar.appendChild(label);bars.appendChild(bar)});row.appendChild(bars);$('#bars').appendChild(row)});
      document.querySelectorAll('[data-scenario]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.scenario===scenario)));
    }
    document.querySelectorAll('[data-scenario]').forEach(button=>button.addEventListener('click',()=>draw(button.dataset.scenario)));
    draw('rtt80');
  }
})();
