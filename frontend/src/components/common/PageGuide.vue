<template>
  <Teleport to="body">
    <div v-if="active && current" class="page-guide-layer" @keydown="onKeydown">
      <svg class="guide-shade" aria-hidden="true" width="100%" height="100%">
        <defs><mask id="enzymind-guide-mask"><rect width="100%" height="100%" fill="white"/><rect v-if="spotlight" v-bind="spotlight" rx="10" fill="black"/></mask></defs>
        <rect width="100%" height="100%" fill="rgba(10, 22, 46, .60)" mask="url(#enzymind-guide-mask)"/>
      </svg>
      <div v-if="spotlight" class="guide-spotlight" :style="{left:`${spotlight.x}px`,top:`${spotlight.y}px`,width:`${spotlight.width}px`,height:`${spotlight.height}px`}" aria-hidden="true"></div>
      <section ref="card" class="page-guide-dialog" :style="position" role="dialog" aria-modal="true" aria-labelledby="page-guide-title" aria-describedby="page-guide-description" tabindex="-1" :data-guide-key="guide.key">
        <header class="guide-heading"><span>PAGE GUIDE <b>·</b> {{ guide.title }}</span><button type="button" class="guide-close" aria-label="Close page guide" @click="close()">×</button></header>
        <div class="guide-body" :key="`${guide.key}-${index}`">
          <p class="guide-step-count" aria-live="polite">STEP {{ String(index+1).padStart(2,'0') }} / {{ String(guide.steps.length).padStart(2,'0') }}</p>
          <h2 id="page-guide-title">{{ current.title }}</h2>
          <p id="page-guide-description">{{ current.text }}</p>
          <GuidePreview :kind="current.preview" :tool="guide.tool" />
        </div>
        <footer class="guide-footer">
          <div class="guide-progress" aria-label="Guide steps"><button v-for="(item,i) in guide.steps" :key="item.title" type="button" :class="{current:index===i,done:index>i}" :aria-current="index===i?'step':undefined" :aria-label="`Go to step ${i+1}: ${item.title}`" @click="go(i)"></button></div>
          <div class="guide-controls"><button type="button" class="guide-skip" @click="close()">Skip guide</button><div><button type="button" class="guide-back" :disabled="index===0" @click="go(index-1)">Back</button><button type="button" class="guide-next" @click="index===guide.steps.length-1?close():go(index+1)">{{ index===guide.steps.length-1?'Finish guide':'Next' }} <span aria-hidden="true">→</span></button></div></div>
          <p class="guide-return">Replay anytime with the <b>? Guide</b> button.</p>
        </footer>
      </section>
    </div>
  </Teleport>
</template>
<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { pageGuide } from '@/config/pageGuides';
import { GUIDE_EVENT, hasSeenTour, markTourSeen } from '@/utils/uiPreferences';
import GuidePreview from './GuidePreview.vue';

const route=useRoute(), guide=computed(()=>pageGuide(route));
const active=ref(false), index=ref(0), card=ref(null), spotlight=ref(null), position=ref({});
const current=computed(()=>guide.value?.steps[index.value]);
let autoTimer, readyObserver, resizeObserver, frame, generation=0, anchor, priorFocus, appRoot, priorInert, priorOverflow, scrollState;
function cancelAutomatic() { clearTimeout(autoTimer); readyObserver?.disconnect(); readyObserver=null; }
function findTarget(selector) {
  if(!selector)return null;
  return [...document.querySelectorAll(selector)].find(el=>{
    const box=el.getBoundingClientRect(), style=getComputedStyle(el);
    return box.width>0 && box.height>0 && box.left<innerWidth && box.right>0 && style.visibility!=='hidden' && style.display!=='none';
  });
}
function measure() {
  if(!active.value || !card.value)return;
  const w=innerWidth,h=innerHeight,box=anchor?.isConnected?anchor.getBoundingClientRect():null;
  if(box && box.bottom>0 && box.top<h) {
    const x=Math.max(6,box.left-6),y=Math.max(6,box.top-6);
    spotlight.value={x,y,width:Math.max(0,Math.min(w-6,box.right+6)-x),height:Math.max(0,Math.min(h-6,box.bottom+6)-y)};
  } else spotlight.value=null;
  const width=Math.min(390,w-24),height=card.value.offsetHeight;
  let left=(w-width)/2,top=(h-height)/2;
  if(w<=640){left=12;top=box && box.top>h*.62 ? 12 : h-height-12;}
  else if(box){
    if(w-box.right>width+28){left=box.right+18;top=box.top;}
    else if(box.left>width+28){left=box.left-width-18;top=box.top;}
    else{left=Math.min(w-width-20,Math.max(20,box.left));top=box.bottom+18;
      if(top+height>h-20)top=box.top-height-18;
      if(top<20){left=w-width-20;top=h-height-20;}
    }
  }
  position.value={width:`${width}px`,left:`${Math.max(12,left)}px`,top:`${Math.max(12,Math.min(h-height-12,top))}px`};
}
function trackMotion() {
  cancelAnimationFrame(frame);
  const until=performance.now()+900;
  const tick=()=>{measure();if(active.value && performance.now()<until)frame=requestAnimationFrame(tick);};
  frame=requestAnimationFrame(tick);
}
async function go(next) {
  if(!active.value || next<0 || next>=guide.value.steps.length)return;
  index.value=next;
  await nextTick();
  if(!active.value)return;
  anchor=findTarget(current.value.target)||findTarget(current.value.fallback)||findTarget(guide.value.ready);
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(anchor && innerWidth<=640 && !anchor.closest('.agent-workspace')){
    // Keep the highlighted control above the mobile sheet, below the fixed nav.
    anchor.scrollIntoView({block:'start',inline:'nearest',behavior:'instant'});
    const navHeight=document.querySelector('.app-header')?.getBoundingClientRect().height || 60;
    window.scrollBy({top:anchor.getBoundingClientRect().top-navHeight-24,behavior:reduced?'instant':'smooth'});
  }else anchor?.scrollIntoView({block:'center',inline:'nearest',behavior:reduced?'instant':'smooth'});
  card.value?.querySelector('.guide-next')?.focus({preventScroll:true});
  measure();trackMotion();
}
async function start() {
  cancelAutomatic();
  if(!guide.value || active.value)return;
  const ticket=++generation;
  priorFocus=document.activeElement;
  scrollState={x:scrollX,y:scrollY,panels:[...document.querySelectorAll('.conversation-scroll,.result-inspector,.memory-panel')].map(el=>({el,top:el.scrollTop,left:el.scrollLeft}))};
  appRoot=document.getElementById('app-container');priorInert=appRoot?.inert;priorOverflow=document.body.style.overflow;
  if(appRoot)appRoot.inert=true;
  document.body.style.overflow='hidden';
  index.value=0;active.value=true;markTourSeen(guide.value.key);
  await nextTick();
  if(ticket!==generation || !active.value)return;
  resizeObserver=new ResizeObserver(measure);resizeObserver.observe(card.value);
  await go(0);
}
function close(restore=true) {
  ++generation;
  cancelAutomatic();cancelAnimationFrame(frame);resizeObserver?.disconnect();resizeObserver=null;
  if(!active.value)return;
  active.value=false;spotlight.value=null;
  if(appRoot)appRoot.inert=priorInert;
  document.body.style.overflow=priorOverflow;
  if(restore){
    scrollState?.panels.forEach(({el,top,left})=>{if(el.isConnected)el.scrollTo({top,left,behavior:'instant'});});
    if(scrollState)window.scrollTo({top:scrollState.y,left:scrollState.x,behavior:'instant'});
    const focus=priorFocus?.isConnected && priorFocus!==document.body?priorFocus:document.querySelector('.page-guide-trigger');
    focus?.focus({preventScroll:true});
  }
}
function schedule() {
  close(false);cancelAutomatic();
  if(!guide.value || hasSeenTour(guide.value.key))return;
  const key=guide.value.key;
  const ready=()=>{
    if(guide.value?.key!==key || !findTarget(guide.value.ready))return;
    readyObserver?.disconnect();readyObserver=null;
    autoTimer=setTimeout(()=>{
      const editing=document.activeElement?.matches('input,textarea,[contenteditable="true"]');
      if(guide.value?.key===key && !hasSeenTour(key) && !editing)start();
    },700);
  };
  readyObserver=new MutationObserver(ready);readyObserver.observe(document.body,{childList:true,subtree:true});ready();
}
function onKeydown(event) {
  if(event.key==='Escape'){event.preventDefault();event.stopPropagation();close();return;}
  if(event.key==='Tab'){
    const elements=[...card.value.querySelectorAll('button:not([disabled]),a[href],[tabindex="0"]')].filter(el=>el.getClientRects().length);
    const first=elements[0],last=elements.at(-1);
    if(event.shiftKey && (document.activeElement===first || document.activeElement===card.value)){event.preventDefault();last?.focus();}
    else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first?.focus();}
  }
  if(event.key==='ArrowRight' && index.value<guide.value.steps.length-1){event.preventDefault();go(index.value+1);}
  if(event.key==='ArrowLeft' && index.value>0){event.preventDefault();go(index.value-1);}
}
function onInput(){if(!active.value)cancelAutomatic();}
watch(()=>route.fullPath,schedule,{flush:'post'});
onMounted(()=>{window.addEventListener(GUIDE_EVENT,start);window.addEventListener('resize',measure);window.addEventListener('scroll',measure,true);window.addEventListener('input',onInput,true);schedule();});
onBeforeUnmount(()=>{close(false);window.removeEventListener(GUIDE_EVENT,start);window.removeEventListener('resize',measure);window.removeEventListener('scroll',measure,true);window.removeEventListener('input',onInput,true);});
</script>
<style scoped>
.page-guide-layer{position:fixed;inset:0;z-index:10000;font-family:var(--font-family);color:var(--color-text);isolation:isolate;}.guide-shade{position:absolute;inset:0;}.guide-spotlight{position:fixed;border:2px solid #a5c4ff;border-radius:10px;box-shadow:0 0 0 4px #c2d6ff33,0 0 28px #548dff44;pointer-events:none;}.page-guide-dialog{position:fixed;background:var(--color-surface);border:1px solid #d8e3f7;border-radius:16px;box-shadow:0 20px 70px #07193255;max-height:calc(100dvh - 24px);overflow:auto;overscroll-behavior:contain;scrollbar-width:thin;animation:guide-dialog-in .25s ease-out;}.guide-heading{display:flex;align-items:center;justify-content:space-between;padding:11px 13px 9px 21px;border-bottom:1px solid #e9eef7;gap:10px;}.guide-heading>span{font:10px var(--font-mono);line-height:1.6;color:#637c9d;}.guide-heading b{padding:0 5px;color:#9dafcb;}.guide-close{flex-shrink:0;border:0;background:transparent;color:#72819a;font:24px var(--font-family);width:32px;height:32px;cursor:pointer;border-radius:6px;}.guide-close:hover{background:#eef4ff;}.guide-body{padding:17px 21px 0;animation:guide-dialog-in .2s ease-out;}.guide-step-count{font:10px var(--font-mono);color:var(--color-primary);letter-spacing:.1em;margin:0 0 7px;}.guide-body h2{font-size:21px;font-weight:650;line-height:1.3;letter-spacing:-.025em;margin:0 0 10px;}.guide-body>p:last-of-type{font-size:13px;line-height:1.75;color:var(--color-text-secondary);margin:0;}.guide-footer{padding:16px 21px 12px;background:white;position:sticky;bottom:0;}.guide-progress{display:flex;gap:5px;margin-bottom:14px;}.guide-progress button{flex:1;height:4px;border:0;border-radius:2px;background:#e3eaf5;cursor:pointer;padding:0;position:relative;}.guide-progress button:before{content:'';position:absolute;inset:-5px 0;}.guide-progress .done{background:#a8c1f4;}.guide-progress .current{background:var(--color-primary);}.guide-controls{display:flex;align-items:center;justify-content:space-between;gap:12px;}.guide-controls>div{display:flex;gap:7px;}.guide-controls button{font:600 12px var(--font-family);border-radius:7px;cursor:pointer;padding:9px 12px;min-height:36px;}.guide-skip{border:0;background:none;color:#718099;padding-left:0!important;}.guide-back{border:1px solid #dce5f4;background:white;color:#52647e;}.guide-back:disabled{opacity:.35;cursor:default;}.guide-next{background:var(--color-primary);color:white;border:1px solid var(--color-primary);}.guide-next span{padding-left:7px;}.guide-return{margin:11px 0 0;font-size:10px;color:#8290a5;text-align:center;}.guide-return b{font-weight:500;}.page-guide-dialog button:focus-visible{outline:2px solid var(--color-primary);outline-offset:3px;}@keyframes guide-dialog-in{from{opacity:0;transform:translateY(7px)}to{opacity:1;transform:translateY(0)}}
@media(max-width:640px){.page-guide-dialog{max-height:65dvh;border-radius:14px;}.guide-body{padding:14px 17px 0;}.guide-body h2{font-size:19px;}.guide-body>p:last-of-type{font-size:12px;line-height:1.65;}.guide-footer{padding:12px 17px 10px;}.guide-heading{padding-left:17px;}}
@media(prefers-reduced-motion:reduce){.page-guide-layer *{animation:none!important;transition:none!important;}}
</style>
