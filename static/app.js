const form=document.getElementById('form'), statusBox=document.getElementById('status');
let mode='link', currentJob=null;
document.querySelectorAll('.tab').forEach(btn=>btn.addEventListener('click',()=>{
 document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));btn.classList.add('active');
 mode=btn.dataset.tab;document.getElementById('linkBox').hidden=mode!=='link';document.getElementById('uploadBox').hidden=mode!=='upload';
}));
form.addEventListener('submit',async e=>{
 e.preventDefault();const go=document.getElementById('go');go.disabled=true;go.textContent='⏳ Processing video…';
 statusBox.textContent='Preparing video and detecting five high-energy moments. This can take a while.';
 const fd=new FormData();if(mode==='link')fd.append('source',document.getElementById('url').value);else fd.append('video',document.getElementById('video').files[0]);
 try{const r=await fetch('/api/create',{method:'POST',body:fd});const data=await r.json();if(!r.ok)throw new Error(data.error||'Processing failed');currentJob=data.job;render(data);statusBox.textContent=data.note||'Finished.';}
 catch(err){statusBox.textContent='Error: '+err.message;}
 finally{go.disabled=false;go.textContent='✦ Generate 5 gaming clips';}
});
function render(data){
 document.getElementById('results').hidden=false;const root=document.getElementById('clips');root.innerHTML='';
 data.clips.forEach(c=>{
  const card=document.createElement('article');card.className='clip';
  card.innerHTML=`<video controls playsinline preload="metadata" src="${c.file}"></video><h3>Gaming highlight ${c.id}</h3><div class="meta">Start ${c.start}s · ${c.duration}s · ${c.captions?'Captions generated':'No speech captions'}</div><textarea placeholder="Caption editing is available when Whisper captions are generated" ${c.captions?'':'disabled'}></textarea><div class="actions"><a href="${c.file}" download="ClipForge-clip-${c.id}.mp4">Download MP4</a><button type="button" ${c.captions?'':'disabled'}>Save caption</button></div>`;
  const ta=card.querySelector('textarea'), save=card.querySelector('button');
  save.addEventListener('click',async()=>{const res=await fetch('/api/caption',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job:data.job,clip:c.id,text:ta.value})});const out=await res.json();alert(out.message||out.error);});
  if(c.captions){fetch(c.srt).then(x=>x.text()).then(s=>{ta.value=s.split('\n').filter((l,i)=>l.trim()&&!l.includes('-->')&&!/^\d+$/.test(l)).join('\n');});}
  root.appendChild(card);
 });
 document.getElementById('results').scrollIntoView({behavior:'smooth'});
}
