// Bundle 13: movable/resizable minimap; independent closed/open dimensions.
import { t } from './i18n.js';
import { addStrings, whenReady } from './ui_shared.js';
addStrings({mmMove:'Move minimap (arrow keys to move, double-click to reset)',mmResize:'Resize minimap'}, {mmMove:'미니맵 옮기기 (방향키로 이동, 더블클릭하면 원래 자리)',mmResize:'미니맵 크기 조절'});
const KEY='ls.minimapPos', SIZE_KEY='ls.minimapSizes.v13';
// below 1200 px the map area is only ~400 px wide: a 222 px box would cover the time read-out, so the default folded box is smaller there
const defaults={closed:window.innerWidth<1200?{w:158,h:164}:{w:222,h:228},open:{w:580,h:358}};
let box, grip, pos={fx:1,fy:0}, sizes=structuredClone(defaults), lastOpen=false, frame=0;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const compact=()=>innerWidth<=899;
const still=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
function load(){try{const p=JSON.parse(localStorage.getItem(KEY));if(p&&Number.isFinite(p.fx)&&Number.isFinite(p.fy))pos={fx:clamp(p.fx,0,1),fy:clamp(p.fy,0,1)};
 const s=JSON.parse(localStorage.getItem(SIZE_KEY));for(const mode of ['closed','open'])if(s?.[mode]&&Number.isFinite(s[mode].w)&&Number.isFinite(s[mode].h))sizes[mode]={w:clamp(s[mode].w,mode==='open'?304:142,2000),h:clamp(s[mode].h,mode==='open'?228:148,1500)};
}catch{/* Storage is optional. */}}
function save(){try{localStorage.setItem(KEY,JSON.stringify(pos));localStorage.setItem(SIZE_KEY,JSON.stringify(sizes));}catch{/* Keep state in memory. */}}
function area(){
 const sc=document.querySelector('.ls-screen').getBoundingClientRect(),R=s=>document.querySelector(s)?.getBoundingClientRect();
 const wide=innerWidth>=1100,L=R('.ls-left'),T=R('.ls-tray'),D=R('.ls-toolbar'),head=R('.ls-head');
 const root=document.documentElement,gap=parseFloat(getComputedStyle(root).getPropertyValue('--G'))||20;
 const leftOff=root.classList.contains('lp-off'),rightOff=root.classList.contains('rp-off');
 return {sc,l:wide&&L?(leftOff?gap+28:L.right-sc.left+gap):12,r:wide&&T?(rightOff?sc.width-gap-28:T.left-sc.left-gap):sc.width-12,
 t:(head?.height||48),b:wide&&D&&D.height?D.top-sc.top-8:Math.min(sc.height,innerHeight)-20};
}
function dimensions(a,mode){const s=sizes[mode];return {w:Math.min(s.w,Math.max(1,a.r-a.l)),h:Math.min(s.h,Math.max(1,a.b-a.t))};}
function followers(bx,by,w,h,a){
 const follow=['#hud-1','#globe-stage .g3-dock','#map-legend'].map(s=>document.querySelector(s)).filter(e=>e&&!e.hidden&&e.offsetParent!==null);
 const total=follow.reduce((n,e)=>n+e.offsetHeight+8,0),right=pos.fx>.5;
 let y=by+h+8+total<=a.b?by+h+8:Math.max(a.t,by-total-8);
 for(const e of follow){Object.assign(e.style,{top:`${Math.round(y)}px`,bottom:'auto',left:right?'auto':`${Math.round(bx)}px`,right:right?`${Math.round(a.sc.width-bx-w)}px`:'auto'});y+=e.offsetHeight+8;}
}
function place(animate=false){
 if(!box)return;
 if(compact()){
  const open=box.classList.contains('open');
  Object.assign(box.style,{left:'',top:'',right:'',bottom:'',width:`${Math.min(open?580:222,innerWidth-32)}px`,height:`${open?358:228}px`});
  for(const selector of ['#hud-1','#globe-stage .g3-dock','#map-legend']){const el=document.querySelector(selector);if(el)for(const key of ['left','top','right','bottom'])el.style[key]='';}
  return;
 }
 const a=area(),d=dimensions(a,box.classList.contains('open')?'open':'closed');
 let x=a.l+pos.fx*Math.max(0,a.r-a.l-d.w),y=a.t+pos.fy*Math.max(0,a.b-a.t-d.h);
 x=clamp(x,a.l,a.r-d.w);y=clamp(y,a.t,a.b-d.h);
 box.classList.toggle('mm-anim',animate&&!still());
 Object.assign(box.style,{left:`${Math.round(x)}px`,top:`${Math.round(y)}px`,right:'auto',bottom:'auto',width:`${Math.round(d.w)}px`,height:`${Math.round(d.h)}px`});
 followers(x,y,d.w,d.h,a);
}
function positionFromRect(x,y,w){const a=area(),d=dimensions(a,box.classList.contains('open')?'open':'closed');pos={fx:clamp((x-a.l)/Math.max(1,a.r-a.l-w),0,1),fy:clamp((y-a.t)/Math.max(1,a.b-a.t-d.h),0,1)};}
function later(){if(!frame)frame=requestAnimationFrame(()=>{frame=0;place();});}
function init(){
 box=document.getElementById('ls-minimap');if(!box?.querySelector('.mm-ball')||box.querySelector('.mm-grip'))return;load();
 grip=document.createElement('div');grip.className='mm-grip';grip.setAttribute('role','button');grip.tabIndex=0;grip.innerHTML='<i></i>';box.prepend(grip);
 const handles=['n','s','e','w','ne','nw','se','sw'].map(edge=>{const h=document.createElement('div');h.className=`mm-resize mm-${edge}`;h.dataset.edge=edge;h.tabIndex=0;h.setAttribute('role','button');box.append(h);return h;});
 const label=()=>{grip.setAttribute('aria-label',t('mmMove'));grip.title=t('mmMove');handles.forEach(h=>h.setAttribute('aria-label',`${t('mmResize')} (${h.dataset.edge})`));};label();window.addEventListener('llsn:lang',label);
 let drag=null;
 box.addEventListener('pointerdown',e=>{
  if(compact())return;
  const handle=e.target.closest('.mm-resize'),moving=e.target.closest('.mm-grip');if((!handle&&!moving)||e.button!==0)return;
  const r=box.getBoundingClientRect(),a=area();drag={edge:handle?.dataset.edge,x:e.clientX,y:e.clientY,l:r.left-a.sc.left,t:r.top-a.sc.top,w:r.width,h:r.height,a};
  (handle||moving).setPointerCapture(e.pointerId);box.classList.add('dragging');e.preventDefault();e.stopPropagation();
 });
 function change(dx,dy){
  const d=drag,a=d.a,mode=box.classList.contains('open')?'open':'closed';let l=d.l,r=d.l+d.w,tp=d.t,b=d.t+d.h;
  if(!d.edge){l=clamp(l+dx,a.l,a.r-d.w);tp=clamp(tp+dy,a.t,a.b-d.h);r=l+d.w;b=tp+d.h;}
  else{const minW=Math.min(mode==='open'?304:142,a.r-a.l),minH=Math.min(mode==='open'?228:148,a.b-a.t);
   if(d.edge.includes('w'))l=clamp(l+dx,a.l,r-minW);if(d.edge.includes('e'))r=clamp(r+dx,l+minW,a.r);
   if(d.edge.includes('n'))tp=clamp(tp+dy,a.t,b-minH);if(d.edge.includes('s'))b=clamp(b+dy,tp+minH,a.b);
   sizes[mode]={w:r-l,h:b-tp};
  }
  positionFromRect(l,tp,r-l);place();
 }
 box.addEventListener('pointermove',e=>{if(drag)change(e.clientX-drag.x,e.clientY-drag.y);});
 const end=()=>{if(!drag)return;const moved=!drag.edge;drag=null;box.classList.remove('dragging');
  if(moved){const a=area(),c=dimensions(a,box.classList.contains('open')?'open':'closed');for(const [key,space]of [['fx',a.r-a.l-c.w],['fy',a.b-a.t-c.h]]){if(pos[key]*space<=12)pos[key]=0;else if((1-pos[key])*space<=12)pos[key]=1;}}
  save();place(true);
 };box.addEventListener('pointerup',end);box.addEventListener('pointercancel',end);
 const reset=()=>{pos={fx:1,fy:0};save();place(true);};grip.addEventListener('dblclick',reset);
 grip.addEventListener('keydown',e=>{
  if(compact())return;
  if(e.key==='Home'){e.preventDefault();reset();return;}const delta={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[e.key];if(!delta)return;
  e.preventDefault();const a=area(),r=box.getBoundingClientRect(),step=e.shiftKey?40:10;positionFromRect(r.left-a.sc.left+delta[0]*step,r.top-a.sc.top+delta[1]*step,r.width);save();place();
 });
 handles.forEach(h=>h.addEventListener('keydown',e=>{const delta={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[e.key];if(!delta)return;e.preventDefault();const a=area(),r=box.getBoundingClientRect();drag={edge:h.dataset.edge,l:r.left-a.sc.left,t:r.top-a.sc.top,w:r.width,h:r.height,a};change(delta[0]*(e.shiftKey?40:10),delta[1]*(e.shiftKey?40:10));end();}));
 new MutationObserver(()=>{const open=box.classList.contains('open');if(open!==lastOpen){
  if(compact()){lastOpen=open;place(true);return;}
  const a=area(),old=dimensions(a,lastOpen?'open':'closed'),next=dimensions(a,open?'open':'closed');
  const x=a.l+pos.fx*Math.max(0,a.r-a.l-old.w)+old.w-next.w,y=a.t+pos.fy*Math.max(0,a.b-a.t-old.h);
  lastOpen=open;positionFromRect(x,y,next.w);place(true);
 }}).observe(box,{attributes:true,attributeFilter:['class']});
 window.addEventListener('resize',later);
 // Transforms do not trigger ResizeObserver; remeasure after the side panel settles.
 for(const selector of ['.ls-left','.ls-tray']){
  const panel=document.querySelector(selector);if(!panel)continue;
  for(const event of ['transitionend','transitioncancel'])panel.addEventListener(event,e=>{
   if(e.target===panel&&e.propertyName==='transform')later();
  });
 }
 ['llsn:ready','llsn:lang','llsn:pins','llsn:globe','llsn:layout'].forEach(ev=>window.addEventListener(ev,later));
 for(const s of ['.ls-toolbar','#map-legend','#hud-1','.ls-left','.ls-tray']){const e=document.querySelector(s);if(e)new ResizeObserver(later).observe(e);}
 const legend=document.getElementById('map-legend');if(legend)new MutationObserver(later).observe(legend,{attributes:true,attributeFilter:['hidden'],childList:true});
 place();
}
window.addEventListener('llsn:minimap-ready',init);
whenReady(init);
