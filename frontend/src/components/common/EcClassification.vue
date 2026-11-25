<template>
  <section v-if="codes.length" class="ec-classifications" aria-label="EC classification names">
    <h4>EC classification</h4>
    <p class="ec-note">Read each number from its broad enzyme class to the accepted enzyme name. These names describe the EC classification, not additional model evidence.</p>
    <p v-if="error" role="status">The EC name reference could not load. Follow an EC link to view its official entry.</p>
    <details v-for="(code,i) in codes" :key="code" :open="i === 0">
      <summary><strong>EC {{ code }}</strong><span>{{ reference?.names[code] || (reference ? 'Classification details' : 'Loading names…') }}</span></summary>
      <ol class="ec-hierarchy" aria-label="EC classification hierarchy">
        <li v-for="level in ecHierarchy(code, reference)" :key="level.label"><small>{{ level.label }}</small><a :href="`https://enzyme.expasy.org/EC/${level.code}`" target="_blank" rel="noopener noreferrer">{{ level.code }} ↗</a><span>{{ reference ? level.name : 'Loading…' }}</span></li>
      </ol>
    </details>
    <p v-if="reference" class="ec-source">Names: <a href="https://enzyme.expasy.org/" target="_blank" rel="noopener noreferrer">SIB ExPASy ENZYME</a> · {{ reference.release }} · <a :href="reference.licenseUrl" target="_blank" rel="noopener noreferrer">{{ reference.license }}</a>. Transferred and deleted entries retain the official notice.</p>
  </section>
</template>
<script setup>
import {computed,shallowRef,ref,watch} from 'vue';
import {ecNumbers,ecHierarchy} from '@/utils/ecHierarchy';
const props=defineProps({payload:{type:Object,required:true}});
const codes=computed(()=>ecNumbers(props.payload)),reference=shallowRef(null),error=ref(false);
watch(()=>codes.value.length,async count=>{if(!count||reference.value)return;try{reference.value=(await import('@/data/ec-reference.json')).default;}catch{error.value=true;}},{immediate:true});
</script>
<style scoped>
.ec-classifications{margin:20px 0;min-width:0}.ec-classifications h4{font-size:14px;margin:0}.ec-note,.ec-source{font-size:11px;line-height:1.7;color:var(--color-text-muted);margin:8px 0}.ec-classifications details{border:1px solid var(--color-border);border-radius:8px;padding:14px;margin:8px 0}.ec-classifications summary{cursor:pointer;font-size:13px;overflow-wrap:anywhere}.ec-classifications summary span{display:block;margin:5px 0 0 16px;color:var(--color-text-secondary);font-size:12px}.ec-hierarchy{list-style:none;padding:0;margin:14px 0 0;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,170px),1fr));gap:8px}.ec-hierarchy li{padding:12px;background:var(--color-primary-light);border-radius:6px;display:flex;flex-direction:column;gap:7px;min-width:0;overflow-wrap:anywhere}.ec-hierarchy small{font-size:10px;color:var(--color-text-muted)}.ec-hierarchy a{font:600 14px monospace}.ec-hierarchy span{font-size:12px;line-height:1.6}.ec-classifications a{color:var(--color-primary)}
</style>
