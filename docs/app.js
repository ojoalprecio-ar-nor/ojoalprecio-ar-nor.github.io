// Ojo al Precio: lee data.json (lo genera el programa cada 12 h) y arma las tarjetas.
const ICON='<rect x="14" y="16" width="36" height="34" rx="4" fill="none" stroke="currentColor" stroke-width="3"/><path d="M24 16v-4h16v4" fill="none" stroke="currentColor" stroke-width="3"/>';
const fmt=n=>"$ "+Math.round(n).toLocaleString("es-AR");
const chipsEl=document.getElementById("chips"),grid=document.getElementById("grid"),sel=document.getElementById("sort");
let PRODUCTS=[],cats=["Todo"],cat="Todo",sort="rank";
try{const s=JSON.parse(localStorage.getItem("oap")||"{}");if(s.cat)cat=s.cat;if(s.sort)sort=s.sort}catch(e){}
sel.value=sort;
const esc=t=>String(t??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function save(){try{localStorage.setItem("oap",JSON.stringify({cat,sort}))}catch(e){}}
function renderChips(){
  chipsEl.innerHTML="";
  cats.forEach(c=>{const b=document.createElement("button");b.className="chip";b.type="button";
    const n=c==="Todo"?PRODUCTS.length:PRODUCTS.filter(p=>p.cat===c).length;
    b.textContent=c+" · "+n;b.setAttribute("aria-pressed",c===cat);b.onclick=()=>{cat=c;save();renderChips();render()};chipsEl.appendChild(b)});
}
function moveTag(m){
  if(m==="nuevo")return'<span class="move new">Nuevo en el top</span>';
  if(!m)return'<span class="move" style="color:var(--muted)">Sin cambios</span>';
  return m>0?`<span class="move">↑ ${m} puestos</span>`:`<span class="move" style="color:var(--muted)">↓ ${-m} puestos</span>`;
}
function render(){
  let list=PRODUCTS.filter(p=>cat==="Todo"||p.cat===cat);
  if(sort==="off")list=[...list].sort((a,b)=>b.off-a.off);else if(sort==="price")list=[...list].sort((a,b)=>a.price-b.price);else list=[...list].sort((a,b)=>a.rank-b.rank);
  if(!list.length){grid.innerHTML='<p class="empty">No hay ofertas en esta categoría ahora. Volvé en unas horas.</p>';return}
  grid.innerHTML=list.map(p=>{
    const v=p.verdict==="real"?["real","✓ Descuento real"]:p.verdict==="fake"?["fake","⚠ Ojo"]:["real","● En seguimiento"];
    return `<article class="card">
      <div class="card-head"><div class="rank">#${p.rank}<small>en tendencia</small></div>${moveTag(p.move)}</div>
      <div class="thumb">${p.img?`<img src="${esc(p.img)}" alt="" loading="lazy">`:`<svg viewBox="0 0 64 64" aria-hidden="true">${ICON}</svg>`}</div>
      <div><div class="cat">${esc(p.cat)}</div><h3 class="name">${esc(p.name)}</h3></div>
      <div class="prices">
        ${p.was?`<span class="was">${fmt(p.was)}</span>`:""}
        <div class="now"><b>${fmt(p.price)}</b>${p.off?`<span class="off">${p.off}% OFF</span>`:""}</div>
        <div class="verdict ${v[0]}">${v[1]} · ${esc(p.note)}</div>
        <a class="btn go" href="${esc(p.link)}" target="_blank" rel="noopener sponsored" data-umami-event="ir-a-meli">Ver en Mercado Libre</a>
      </div></article>`}).join("");
}
sel.addEventListener("change",()=>{sort=sel.value;save();render()});
document.getElementById("want").addEventListener("click",e=>{e.target.hidden=true;document.getElementById("thanks").hidden=false});
fetch("data.json?v="+Date.now()).then(r=>r.json()).then(d=>{
  PRODUCTS=d.products||[];
  cats=["Todo",...new Set(PRODUCTS.map(p=>p.cat))];if(!cats.includes(cat))cat="Todo";
  const t=new Date(d.updated);
  document.getElementById("upd").textContent="Actualizado el "+t.toLocaleDateString("es-AR",{day:"numeric",month:"long"})+" a las "+t.toLocaleTimeString("es-AR",{hour:"2-digit",minute:"2-digit"});
  renderChips();render();
}).catch(()=>{grid.innerHTML='<p class="empty">No pudimos cargar las ofertas. Probá recargar la página.</p>'});
