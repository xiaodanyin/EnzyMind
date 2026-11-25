<template>
  <figure ref="shell" class="chemical-preview" :aria-busy="busy">
    <ResultPreview v-if="image" :image-src="image" :title="title || (reaction ? 'Reaction structure' : 'Molecular structure')">
      <img :src="image" :alt="title || (reaction ? '2D depiction of the submitted reaction' : '2D depiction of the submitted substrate molecule')" @error="imageError" />
    </ResultPreview>
    <p v-else role="status">{{ failed ? 'The structure could not be drawn. The original SMILES is preserved below.' : 'Preparing chemical structure…' }}</p>
    <figcaption>{{ reaction ? 'Reactants → products' : 'Molecular structure' }} · Ketcher / Indigo · 2D depiction</figcaption>
  </figure>
</template>
<script setup>
import {ref,computed,onMounted,onBeforeUnmount,watch} from 'vue';
import {chemicalDepiction} from '@/utils/chemicalDepiction';
import ResultPreview from './ResultPreview.vue';
const props=defineProps({smiles:{type:String,required:true},title:String});
const shell=ref(null),image=ref(''),busy=ref(true),failed=ref(false),visible=ref(false);
const reaction=computed(()=>props.smiles.includes('>'));
let observer,revision=0;
function clear(){if(image.value)URL.revokeObjectURL(image.value);image.value='';}
function imageError(){clear();failed.value=true;busy.value=false;}
async function render(){
  const current=++revision;clear();failed.value=false;busy.value=true;
  if(!visible.value)return;
  try{const blob=await chemicalDepiction(props.smiles);if(current===revision)image.value=URL.createObjectURL(blob);}
  catch{if(current===revision)failed.value=true;}
  finally{if(current===revision)busy.value=false;}
}
watch(()=>props.smiles,render);
onMounted(()=>{observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){visible.value=true;observer.disconnect();void render();}},{rootMargin:'150px'});observer.observe(shell.value);});
onBeforeUnmount(()=>{revision++;observer?.disconnect();clear();});
</script>
<style scoped>
.chemical-preview>.result-preview{width:100%;}
.chemical-preview :deep(.preview-toolbar){background:transparent;border:0;padding:0 0 8px;}
.chemical-preview{margin:12px 0;background:#fff;border:1px solid var(--color-border);border-radius:8px;min-height:150px;display:flex;align-items:center;justify-content:center;flex-direction:column;padding:14px;gap:10px;overflow:hidden}.chemical-preview img{display:block;max-width:min(100%,900px);width:100%;height:auto;max-height:300px;object-fit:contain;margin-inline:auto}.chemical-preview p{font-size:12px;color:#596579;line-height:1.7}.chemical-preview figcaption{font-size:10px;color:#596579;text-align:center}
</style>
