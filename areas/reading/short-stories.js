
const STORAGE_KEY = 'reading.shortStoryRatings.v1';
let stories = [];
let ratings = loadRatings();
function loadRatings(){ try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); } catch { return {}; } }
function saveRatings(){ localStorage.setItem(STORAGE_KEY, JSON.stringify(ratings)); render(); }
function storyFeedback(id){ return ratings[id] || {read:false, rating:0, note:''}; }
function esc(s){ return String(s ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function starHtml(story){
  const fb = storyFeedback(story.id);
  let out = '<div class="stars" role="group" aria-label="Star rating">';
  for(let i=1;i<=5;i++){
    out += `<button class="star ${fb.rating>=i?'on':''}" data-id="${esc(story.id)}" data-rating="${i}" title="${i} star${i>1?'s':''}">★</button>`;
  }
  out += `<button class="tiny" data-id="${esc(story.id)}" data-rating="0">clear</button></div>`;
  return out;
}
function matchesFilters(story){
  const fb = storyFeedback(story.id);
  if(document.getElementById('hideRead').checked && fb.read) return false;
  const minStars = Number(document.getElementById('minStars').value || 0);
  if(minStars && (fb.rating || 0) < minStars) return false;
  const q = document.getElementById('searchBox').value.trim().toLowerCase();
  if(q){
    const hay = [story.title, story.author, story.fit, ...(story.tags||[])].join(' ').toLowerCase();
    if(!hay.includes(q)) return false;
  }
  return true;
}
function render(){
  const root = document.getElementById('stories');
  const filtered = stories.filter(matchesFilters);
  root.innerHTML = filtered.map(story => {
    const fb = storyFeedback(story.id);
    const tags = (story.tags||[]).map(t=>`<span class="tag">${esc(t)}</span>`).join(' ');
    return `<article class="card story ${fb.read?'read':''}"><div class="story-head"><div><h2>${esc(story.title)}</h2><p class="muted">${esc(story.author)}${story.year?' · '+esc(story.year):''} · ${esc(story.length||'')}</p></div><label class="read-toggle"><input type="checkbox" data-id="${esc(story.id)}" class="readBox" ${fb.read?'checked':''}> Read</label></div><p>${esc(story.fit)}</p><p>${tags}</p>${starHtml(story)}<p><a href="${esc(story.source_url)}" target="_blank" rel="noopener">${esc(story.source_label || 'Source')}</a></p><textarea class="noteBox" data-id="${esc(story.id)}" placeholder="Optional note for future recommendations">${esc(fb.note || '')}</textarea></article>`;
  }).join('') || '<section class="card"><p>No stories match the current filters.</p></section>';
  const vals = Object.values(ratings);
  const read = vals.filter(v=>v.read).length;
  const rated = vals.filter(v=>Number(v.rating)>0);
  document.getElementById('statRead').textContent = read;
  document.getElementById('statRated').textContent = rated.length;
  document.getElementById('statAverage').textContent = rated.length ? (rated.reduce((a,v)=>a+Number(v.rating||0),0)/rated.length).toFixed(2) : '—';
}
document.addEventListener('click', e => {
  const star = e.target.closest('.star,.tiny');
  if(star){ const id=star.dataset.id; ratings[id] = {...storyFeedback(id), rating:Number(star.dataset.rating)}; saveRatings(); }
});
document.addEventListener('change', e => {
  if(e.target.classList.contains('readBox')){ const id=e.target.dataset.id; ratings[id] = {...storyFeedback(id), read:e.target.checked}; saveRatings(); }
  if(e.target.id==='hideRead' || e.target.id==='minStars') render();
  if(e.target.id==='importRatings'){
    const file=e.target.files[0]; if(!file) return;
    file.text().then(txt=>{ const imported=JSON.parse(txt); ratings = imported.ratings || imported; saveRatings(); });
  }
});
document.addEventListener('input', e => {
  if(e.target.id==='searchBox') render();
  if(e.target.classList.contains('noteBox')){ const id=e.target.dataset.id; ratings[id] = {...storyFeedback(id), note:e.target.value}; localStorage.setItem(STORAGE_KEY, JSON.stringify(ratings)); }
});
document.getElementById('clearFilters').addEventListener('click',()=>{document.getElementById('hideRead').checked=false;document.getElementById('minStars').value='0';document.getElementById('searchBox').value='';render();});
document.getElementById('exportRatings').addEventListener('click',()=>{
  const payload = {schema:'short-story-ratings-v1', exported_at:new Date().toISOString(), ratings, story_count:stories.length};
  const blob = new Blob([JSON.stringify(payload,null,2)], {type:'application/json'});
  const url = URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download='short-story-ratings.json'; a.click(); URL.revokeObjectURL(url);
});
fetch('stories.json').then(r=>r.json()).then(data=>{stories=data.stories||[]; render();});
