// User-adjustable desktop panels; notify layout consumers without resizing the canvas container.
import { addStrings, whenReady } from './ui_shared.js';
import { t } from './i18n.js';
addStrings({
  panelResizeLeft:'Resize mission conditions panel',panelResizeRight:'Resize comparison panel',
  panelResizeHelp:'Drag to resize; use arrow keys; Home or double-click resets the width.'
},{
  panelResizeLeft:'미션 조건 패널 너비 조절',panelResizeRight:'후보 비교 패널 너비 조절',
  panelResizeHelp:'드래그하거나 방향키로 너비를 조절하세요. Home 또는 더블클릭으로 초기화합니다.'
});
whenReady(() => {
  const root=document.documentElement,panels={l:document.getElementById('ls-left'),r:document.getElementById('ls-tray')};
  if(!panels.l||!panels.r||panels.l.querySelector('.pn-resize'))return;
  const KEY='ls.panelWidths.v1',MIN={l:280,r:300},MAX=560,MIN_MAP=344;
  let desired={},pending=0,drag=null,offState='';
  try{const saved=JSON.parse(localStorage.getItem(KEY));for(const side of ['l','r'])if(Number.isFinite(saved?.[side]))desired[side]=Math.max(MIN[side],Math.min(MAX,saved[side]));}catch{/* Storage is optional. */}
  const handles={};
  const off=side=>root.classList.contains(side==='l'?'lp-off':'rp-off');
  const width=side=>panels[side].getBoundingClientRect().width;
  const gap=()=>parseFloat(getComputedStyle(root).getPropertyValue('--G'))||20;
  const budget=()=>innerWidth-(off('l')?(off('r')?2*gap()+56:3*gap()+28):(off('r')?3*gap()+28:4*gap()))-MIN_MAP;
  const maximum=side=>Math.max(MIN[side],Math.min(MAX,budget()-(off(side==='l'?'r':'l')?0:width(side==='l'?'r':'l'))));
  const notify=()=>{if(pending)return;pending=requestAnimationFrame(()=>{pending=0;window.dispatchEvent(new Event('llsn:layout'));});};
  const persist=()=>{try{localStorage.setItem(KEY,JSON.stringify(desired));}catch{/* Keep the in-memory preference. */}};
  const labels=()=>{for(const side of ['l','r']){const h=handles[side];h.setAttribute('aria-label',t(side==='l'?'panelResizeLeft':'panelResizeRight'));h.title=t('panelResizeHelp');}};
  const aria=()=>{for(const side of ['l','r']){const h=handles[side];h.setAttribute('aria-valuemin',String(MIN[side]));h.setAttribute('aria-valuemax',String(Math.round(maximum(side))));h.setAttribute('aria-valuenow',String(Math.round(width(side))));}};
  const apply=()=>{
    if(innerWidth<1100){notify();return;}
    const style=getComputedStyle(root),base={l:parseFloat(style.getPropertyValue('--panel-base-left'))||360,r:parseFloat(style.getPropertyValue('--panel-base-right'))||380};
    const actual={l:desired.l??base.l,r:desired.r??base.r};
    const visible=['l','r'].filter(side=>!off(side)),available=budget();
    if(visible.reduce((n,s)=>n+actual[s],0)>available){
      const spare=Math.max(0,available-visible.reduce((n,s)=>n+MIN[s],0)),extra=visible.reduce((n,s)=>n+actual[s]-MIN[s],0);
      for(const side of visible)actual[side]=MIN[side]+(extra?spare*(actual[side]-MIN[side])/extra:0);
    }
    for(const side of ['l','r'])actual[side]=Math.round(actual[side]);
    if(visible.length&&visible.reduce((n,s)=>n+actual[s],0)>available)actual[visible.at(-1)]-=visible.reduce((n,s)=>n+actual[s],0)-Math.floor(available);
    root.style.setProperty('--panel-user-left',Math.round(actual.l)+'px');
    root.style.setProperty('--panel-user-right',Math.round(actual.r)+'px');
    root.classList.toggle('pn-narrow-r',actual.r<320);
    aria();notify();
  };
  const reset=side=>{delete desired[side];apply();persist();};
  for(const side of ['l','r']){
    const handle=document.createElement('div');handle.className='pn-resize '+side;handle.tabIndex=0;
    handle.setAttribute('role','separator');handle.setAttribute('aria-orientation','vertical');panels[side].append(handle);handles[side]=handle;
    handle.addEventListener('pointerdown',e=>{if(e.button!==0||innerWidth<1100)return;e.preventDefault();e.stopPropagation();drag={side,x:e.clientX,width:width(side),pointer:e.pointerId};handle.setPointerCapture(e.pointerId);root.classList.add('pn-resizing');});
    handle.addEventListener('pointermove',e=>{if(!drag||drag.side!==side)return;const next=drag.width+(e.clientX-drag.x)*(side==='l'?1:-1);desired[side]=Math.max(MIN[side],Math.min(maximum(side),next));apply();});
    const end=()=>{if(!drag||drag.side!==side)return;drag=null;root.classList.remove('pn-resizing');persist();aria();notify();};
    handle.addEventListener('pointerup',end);handle.addEventListener('pointercancel',end);handle.addEventListener('lostpointercapture',end);
    handle.addEventListener('dblclick',()=>reset(side));
    handle.addEventListener('keydown',e=>{
      if(e.key==='Home'){e.preventDefault();reset(side);return;}
      if(e.key!=='ArrowLeft'&&e.key!=='ArrowRight')return;e.preventDefault();
      const delta=(e.key==='ArrowRight'?1:-1)*(side==='l'?1:-1)*(e.shiftKey?30:10);
      desired[side]=Math.max(MIN[side],Math.min(maximum(side),width(side)+delta));apply();persist();
    });
    for(const event of ['transitionend','transitioncancel'])panels[side].addEventListener(event,e=>{if(e.target===panels[side]&&e.propertyName==='transform')notify();});
  }
  new MutationObserver(()=>{const next=String(off('l'))+String(off('r'));if(next===offState)return;offState=next;apply();}).observe(root,{attributes:true,attributeFilter:['class']});
  const ro=new ResizeObserver(()=>{aria();notify();});ro.observe(panels.l);ro.observe(panels.r);
  window.addEventListener('resize',apply);window.addEventListener('llsn:lang',labels);window.addEventListener('llsn:globe',notify);
  labels();apply();
});
