<template>
  <div class="sequence-preview">
    <div class="sequence-heading"><strong>{{ title }}</strong><span>{{ sequence.length.toLocaleString('en-US') }} residues</span></div>
    <p>Residue numbers follow the supplied sequence. Colors group residue properties.<template v-if="interactive"> Underlines mark database annotations. Select a residue to locate it in the structure.</template><template v-else> They do not indicate predicted sites.</template></p>
    <div class="sequence-legend"><span v-for="group in groups" :key="group.label"><i :style="{background:group.color}"></i>{{ group.label }}</span></div>
    <div class="sequence-rows" aria-label="Numbered protein sequence">
      <div v-for="row in rows" :key="row.start" class="sequence-row"><small>{{ row.start + 1 }}</small><code><component :is="interactive ? 'button' : 'span'" v-for="(aa, i) in row.text" :key="i" :type="interactive ? 'button' : undefined" :aria-pressed="interactive ? selectedPosition === row.start+i+1 : undefined" :class="{ 'residue-active':selectedPosition === row.start+i+1 }" :style="{background:color(aa), boxShadow:marks.get(row.start+i+1) ? `inset 0 -3px ${marks.get(row.start+i+1)}` : undefined}" :title="`${aa} · residue ${row.start+i+1}`" @click="interactive && emit('select',row.start+i+1)">{{ aa }}</component></code><small>{{ row.start + row.text.length }}</small></div>
    </div>
    <nav v-if="sequence.length > size" aria-label="Sequence pages"><button :disabled="page === 0" @click="page--">← Previous</button><span>{{ page * size + 1 }}–{{ Math.min((page+1)*size,sequence.length) }} of {{ sequence.length }}</span><button :disabled="(page+1)*size >= sequence.length" @click="page++">Next →</button></nav>
  </div>
</template>
<script setup>
import {computed,ref,watch} from 'vue';
const props=defineProps({sequence:{type:String,required:true},title:{type:String,default:'Sequence'},interactive:Boolean,selectedPosition:Number,annotations:{type:Array,default:()=>[]}});
const emit=defineEmits(['select']);
const marks=computed(()=>new Map(props.annotations.filter(s=>s.position).map(s=>[s.position,s.color])));
const page=ref(0),size=300;
watch(()=>props.sequence,()=>{page.value=0;});
watch(()=>props.selectedPosition,position=>{if(position>0 && position<=props.sequence.length)page.value=Math.floor((position-1)/size);});
const groups=[{label:'Nonpolar',letters:'AVILMFWPG',color:'#e4def8'},{label:'Polar',letters:'STCYNQ',color:'#d7eee9'},{label:'Acidic',letters:'DE',color:'#f8dbd9'},{label:'Basic',letters:'KRH',color:'#dbe7fb'},{label:'Other / ambiguous',letters:'',color:'#ececf0'}];
const color=aa=>(groups.find(g=>g.letters.includes(aa))||groups.at(-1)).color;
const rows=computed(()=>Array.from({length:Math.ceil(Math.min(size,props.sequence.length-page.value*size)/30)},(_,i)=>{const start=page.value*size+i*30;return{start,text:props.sequence.slice(start,start+30)};}));
</script>
<style scoped>
.sequence-preview{min-width:0}.sequence-heading,.sequence-preview nav{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;font-size:12px}.sequence-heading span,.sequence-preview p{color:var(--color-text-muted);font-size:11px}.sequence-preview p{margin:8px 0;line-height:1.6}.sequence-legend{display:flex;flex-wrap:wrap;gap:6px 12px;margin:10px 0;font-size:10px}.sequence-legend span{display:flex;align-items:center;gap:4px}.sequence-legend i{width:10px;height:10px;border-radius:2px}.sequence-rows{overflow-x:auto;padding:8px 0}.sequence-row{display:flex;align-items:center;gap:8px;margin:3px 0;min-width:max-content}.sequence-row small{color:var(--color-text-muted);font:10px monospace;min-width:4ch;text-align:right}.sequence-row code{display:flex;color:#27334a;font:12px/22px monospace}.sequence-row code span{width:16px;text-align:center;border-radius:2px;margin-right:1px}.sequence-row code span:nth-child(10n){margin-right:6px}.sequence-preview nav{margin-top:10px;font-size:11px}.sequence-preview button{font:inherit;padding:4px 8px;background:var(--color-surface);border:1px solid var(--color-border);border-radius:5px;color:var(--color-primary);cursor:pointer}.sequence-preview button:disabled{opacity:.4;cursor:default}
</style>
<style scoped>
.sequence-row code button{width:16px;min-width:16px;text-align:center;border:0;border-radius:2px;margin:0 1px 0 0;padding:0;color:#27334a;font:inherit;line-height:22px;cursor:pointer}.sequence-row code button:nth-child(10n){margin-right:6px}.sequence-row code .residue-active{outline:2px solid var(--color-primary);outline-offset:1px;position:relative;z-index:1}.sequence-row code button:hover{filter:brightness(.94)}
</style>
