<template>
  <figure ref="shell" class="model-workflow">
    <div class="workflow-heading"><div><span class="eyebrow">{{ tool.analysis ? 'ANALYSIS WORKFLOW' : 'FROM INPUT TO PREDICTION' }}</span><p>A clear view of the method behind your result.</p></div></div>
    <svg :viewBox="compact ? '0 0 360 432' : '0 0 1140 220'" role="group" :aria-labelledby="`${uid}-title ${uid}-description`" xmlns="http://www.w3.org/2000/svg" font-family="'Segoe UI', sans-serif">
      <title :id="`${uid}-title`">{{ tool.title }} — {{ tool.analysis ? 'analysis workflow' : 'prediction principle' }}</title><desc :id="`${uid}-description`">{{ tool.steps.map(s => s.title + ': ' + s.detail).join('. ') }}. Illustrative method diagram, not a prediction result.</desc>
      <defs>
        <linearGradient :id="`${uid}-panel`" x2="1" y2="1"><stop stop-color="#f8fbff"/><stop offset="1" stop-color="#f0edff"/></linearGradient>
        <marker :id="`${uid}-arrow`" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0 7 3.5 0 7Z" fill="#899cc2"/></marker>
        <symbol :id="`${uid}-sequence`" viewBox="0 0 110 70"><path d="M8 48C27-10 48 91 67 24S95 54 103 17" fill="none" stroke="#8b5cf6" stroke-width="6" opacity=".25"/><g v-for="(letter,i) in 'MKTAYI'" :key="letter+i"><rect :x="i*17+4" y="24" width="15" height="23" rx="4" :fill="i%2 ? '#e5dbff' : '#dceafe'"/><text :x="i*17+11.5" y="40" font-family="monospace" font-size="12" text-anchor="middle" fill="#334887">{{ letter }}</text></g></symbol>
        <symbol :id="`${uid}-molecule`" viewBox="0 0 110 70"><g stroke="#596ec2" stroke-width="2.4" fill="none" stroke-linejoin="round"><path d="M29 20 49 9 69 20 69 43 49 55 29 43Z M34 23 49 15 M63 23V40 M34 40 49 49 M69 20 89 9 M29 43 12 53"/></g><text x="88" y="12" fill="#b75472" font-size="13">OH</text><text x="1" y="65" fill="#4063be" font-size="13">N</text></symbol>
        <symbol :id="`${uid}-reaction`" viewBox="0 0 110 70"><path d="M9 43 22 34 35 43 M22 34V18 M27 33V18 M76 43 89 34 102 43 M89 34V18" fill="none" stroke="#596ec2" stroke-width="2"/><text x="18" y="16" fill="#b75472" font-size="12">O</text><text x="84" y="16" fill="#b75472" font-size="12">OH</text><path d="M43 34H67M61 29 67 34 61 39" fill="none" stroke="#8b5cf6" stroke-width="2"/></symbol>
        <symbol :id="`${uid}-pair`" viewBox="0 0 110 70"><use :href="`#${uid}-sequence`" x="0" y="0" width="57" height="65"/><use :href="`#${uid}-molecule`" x="54" y="0" width="57" height="65"/><text x="51" y="41" font-size="12" fill="#8b5cf6">+</text></symbol>
        <symbol :id="`${uid}-embedding`" viewBox="0 0 110 70"><g v-for="row in 4" :key="row"><rect v-for="col in 8" :key="col" :x="col*11+2" :y="row*12-1" width="8" height="9" rx="2" :fill="['#b2c8fa','#8d9fe9','#ccbbf4','#537bd0'][(col*3+row)%4]" :opacity=".55+(col+row)%3*.2"/></g><path d="M13 60H96" stroke="#b8c8e5"/></symbol>
        <symbol :id="`${uid}-network`" viewBox="0 0 110 70"><g stroke="#b9c3ed" stroke-width="1" fill="none"><template v-for="a in 3" :key="a"><path v-for="b in 4" :key="b" :d="`M16 ${a*18-4} L55 ${b*14-1} L96 ${a*18-4}`"/></template></g><circle v-for="i in 3" :key="`l${i}`" cx="16" :cy="i*18-4" r="5" fill="#5a84d5"/><circle v-for="i in 4" :key="`m${i}`" cx="55" :cy="i*14-1" r="6" fill="#9a7bd9"/><circle v-for="i in 3" :key="`r${i}`" cx="96" :cy="i*18-4" r="5" fill="#5a84d5"/></symbol>
        <symbol :id="`${uid}-classification`" viewBox="0 0 110 70"><rect x="9" y="8" width="92" height="54" rx="8" fill="#fff" stroke="#cdd8ed"/><g v-for="i in 3" :key="i"><circle cx="22" :cy="i*14+6" r="3" :fill="i===1?'#4b83ce':'#a8b6ce'"/><path :d="`M32 ${i*14+6} H${93-i*9}`" :stroke="i===1?'#8c6ad1':'#c6d4ed'" stroke-width="6" stroke-linecap="round"/></g></symbol>
        <symbol :id="`${uid}-metric`" viewBox="0 0 110 70"><path d="M15 8V58H101" fill="none" stroke="#c1cce2" stroke-width="1.5"/><path d="M22 49Q36 25 50 24T93 14" fill="none" stroke="#8b5cf6" stroke-width="3"/><circle cx="50" cy="24" r="5" fill="#4c7fd6"/><path d="M50 31V56" stroke="#a9b9da" stroke-dasharray="3 3"/><text x="65" y="49" fill="#63769b" font-size="10">value · unit</text></symbol>
        <symbol :id="`${uid}-protein`" viewBox="0 0 110 70"><path d="M16 41C-3 7 51 7 42 31S74 63 87 37 55 4 51 22 101 61 67 62 10 63 22 37 69 2 91 12" stroke="#b7a0e5" stroke-width="8" fill="none" stroke-linecap="round"/><path d="M16 41C-3 7 51 7 42 31S74 63 87 37 55 4 51 22 101 61 67 62 10 63 22 37 69 2 91 12" stroke="#5c8bd5" stroke-width="3" fill="none"/><circle cx="42" cy="31" r="5" fill="#14946f"/><circle cx="87" cy="37" r="5" fill="#d85367"/></symbol>
      </defs>
      <g v-for="(stage,i) in stages" :key="i" :transform="compact ? `translate(10 ${i*108+4})` : `translate(${i*290+2} 5)`">
        <rect :width="compact?340:266" :height="compact?92:200" rx="14" :fill="`url(#${uid}-panel)`" stroke="#dce3f1"/>
        <text :x="compact?16:16" :y="compact?18:22" fill="#7787a4" font-size="10" letter-spacing="1.2">0{{ i+1 }}</text>
        <use :href="`#${uid}-${stage.icon}`" :x="compact?8:78" :y="compact?20:35" :width="compact?72:110" :height="compact?62:70"/>
        <text :x="compact?94:133" :y="compact?34:132" :text-anchor="compact?'start':'middle'" fill="#233c66" :font-size="compact?14:16" font-weight="650">{{ stage.title }}</text>
        <text v-for="(line,j) in wrap(stage.detail,compact?30:34)" :key="j" :x="compact?94:133" :y="(compact?55:155)+j*17" :text-anchor="compact?'start':'middle'" fill="#586c8b" font-size="12">{{ line }}</text>
        <path v-if="i<3" :d="compact?'M170 94V105':'M269 103H285'" stroke="#899cc2" stroke-width="1.5" fill="none" :marker-end="`url(#${uid}-arrow)`"/>
        <rect v-if="i===0" :width="compact?340:266" :height="compact?92:200" rx="14" fill="transparent" class="input-link" role="button" tabindex="0" aria-label="Go to protein or molecule input" @click="$emit('focus-input')" @keydown.enter="$emit('focus-input')" @keydown.space.prevent="$emit('focus-input')"/>
      </g>
    </svg>
    <figcaption><span>Illustrative method · not a prediction result</span><button type="button" @click="$emit('focus-input')">Go to input ↓</button></figcaption>
    <details class="method-details"><summary>Method details &amp; interpretation</summary><p>{{ tool.method }}</p></details>
  </figure>
</template>
<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue';
const props = defineProps({ tool: { type: Object, required: true }, inputType: { type:String, default:'auto' } });
defineEmits(['focus-input']);
const shell=ref(null),compact=ref(false);let observer;
const uid=`method-${props.tool.id}`;
const stages=computed(()=>props.tool.steps.map((s,i)=>i===0 && props.tool.protein!==false && props.inputType==='uniprot' ? {...s,detail: props.tool.molecule==='molecule'?'Accession → sequence + substrate':'UniProt accession → retrieve sequence'} : s));
function wrap(value,max){const lines=[''];for(const word of value.split(' ')){if((lines.at(-1)+' '+word).trim().length>max)lines.push(word);else lines[lines.length-1]=(lines.at(-1)+' '+word).trim();}return lines;}
onMounted(()=>{observer=new ResizeObserver(([e])=>{compact.value=e.contentRect.width<700});observer.observe(shell.value)});
onBeforeUnmount(()=>observer?.disconnect());
</script>
<style scoped>
.model-workflow{margin:0 0 28px;padding:20px 22px 12px;border:1px solid #dae2f1;border-radius:18px;background:linear-gradient(135deg,#ffffffeb,#f7f8ff);box-shadow:0 6px 24px #182b5b05}.workflow-heading{display:flex;justify-content:space-between;gap:16px;align-items:center}.eyebrow{font-size:11px;font-weight:700;letter-spacing:.12em;color:var(--color-primary)}.workflow-heading p{font-size:13px;margin:4px 0 12px}.model-workflow svg{display:block;width:100%;height:auto}.model-workflow button{border:0;background:none;color:var(--color-primary);font:inherit;font-size:12px;cursor:pointer;padding:5px}.input-link{cursor:pointer}.input-link:focus{outline:none;stroke:#2563eb;stroke-width:2}figcaption{display:flex;justify-content:space-between;align-items:center;font-size:11px;color:var(--color-text-secondary);padding:6px 0}.method-details{border-top:1px solid #e0e6f1;padding:10px 0 0;font-size:13px}.method-details summary{cursor:pointer;color:#455b7e}.method-details p{margin:10px 0;line-height:1.75}@media(max-width:550px){.model-workflow{padding:16px 10px}.workflow-heading{align-items:flex-start}figcaption{gap:8px;font-size:10px}}
</style>
