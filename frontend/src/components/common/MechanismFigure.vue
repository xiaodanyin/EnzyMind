<template>
  <figure ref="shell" class="mechanism-figure">
    <template v-if="url">
      <ResultPreview v-if="visible && !failed" :image-src="url" :title="title" :disabled="!loaded">
        <img :key="attempt" :src="url" :alt="title" referrerpolicy="no-referrer" @load="ready" @error="unavailable" />
      </ResultPreview>
      <p v-if="!loaded" role="status">{{ failed ? 'The source diagram could not load. The step description remains available.' : 'Loading the M-CSA source diagram…' }}</p>
      <button v-if="failed" @click="retry">Retry diagram</button>
      <figcaption>M-CSA source diagram · <a :href="url" target="_blank" rel="noopener noreferrer">Open original image ↗</a></figcaption>
    </template>
    <p v-else class="diagram-empty">No source diagram was included for this step.</p>
  </figure>
</template>
<script setup>
import {ref,watch,onMounted,onBeforeUnmount} from 'vue';
import ResultPreview from './ResultPreview.vue';
const props=defineProps({url:String,title:String});
const shell=ref(null),visible=ref(false),loaded=ref(false),failed=ref(false),attempt=ref(0);
let observer,timer;
function unavailable(){clearTimeout(timer);failed.value=true;loaded.value=false;}
function ready(){clearTimeout(timer);loaded.value=true;failed.value=false;}
function retry(){clearTimeout(timer);failed.value=false;loaded.value=false;visible.value=true;attempt.value++;timer=setTimeout(unavailable,20000);}
watch(()=>props.url,()=>{clearTimeout(timer);loaded.value=false;failed.value=false;if(visible.value && props.url)retry();});
onMounted(()=>{observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){observer.disconnect();retry();}},{rootMargin:'150px'});observer.observe(shell.value);});
onBeforeUnmount(()=>{observer?.disconnect();clearTimeout(timer);});
</script>
<style scoped>
.mechanism-figure{margin:16px 0 0;background:white;border:1px solid var(--color-border);border-radius:8px;overflow:hidden}.mechanism-figure img{display:block;width:100%;height:340px;object-fit:contain;padding:12px;box-sizing:border-box}.mechanism-figure p{font-size:12px;line-height:1.7;color:var(--color-text-secondary);padding:20px;margin:0}.mechanism-figure figcaption{font-size:10px;color:var(--color-text-muted);padding:10px 14px;border-top:1px solid var(--color-border)}a{color:var(--color-primary)}button{margin:0 20px 16px;padding:6px 10px;background:white;color:var(--color-primary);border:1px solid var(--color-border);border-radius:5px;cursor:pointer}
@container (max-width:500px){.mechanism-figure img{height:260px}}
</style>
