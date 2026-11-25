<template>
    <section ref="structureSection" class="enzyme-section" aria-label="Reference structure">
      <div class="section-heading"><div><span class="eyebrow">STRUCTURE &amp; ANNOTATIONS</span><h4>Explore the protein in 3D</h4></div><span class="section-tag">AlphaFold · predicted model</span></div>
      <p class="section-note">{{ description || `${annotationSource} site annotations are overlaid only where the model matches the saved sequence. A predicted structure is not experimental evidence of catalytic activity.` }}</p>
      <template v-if="model">
        <div class="structure-meta"><span>Model v{{ model.source?.version || '—' }}</span><span v-if="model.source?.sequence_start">Residues {{ model.source.sequence_start }}–{{ model.source.sequence_end }}</span><span v-if="Number.isFinite(model.source?.mean_plddt)">Mean pLDDT {{ model.source.mean_plddt.toFixed(1) }}</span><a :href="`https://alphafold.ebi.ac.uk/entry/${accession}`" target="_blank" rel="noopener noreferrer">AlphaFold DB ↗</a></div>
        <p v-if="model.source?.stale" class="inline-notice">AlphaFold is temporarily unavailable. Showing a previously retrieved reference model.</p>
        <p v-if="sequence && !mapping.valid" class="inline-notice">The reference model does not match the displayed sequence and numbering. Site overlays and sequence linking are disabled; both remain available to inspect separately.</p>
        <ProteinViewer ref="viewer" :structure="model.structure_data" :format="model.structure_format" :title="`${accession} · reference structure`" :sites="mappedSites" :site-palette="sitePalette" :show-sequence="false" :show-residue-panel="false" :show-confidence-plot="false" confidence-type="plddt" @select="selectAtom" />
        <p class="section-note mapping-status"><template v-if="sites.length">{{ mapping.valid ? `${mappedSites.length} of ${sites.length} annotations mapped to matching coordinates.` : 'No validated annotation mapping is available.' }}</template><span v-if="model.source?.retrieved_at"> Reference retrieved {{ new Date(model.source.retrieved_at).toLocaleDateString('en-GB') }}.</span></p>
        <details class="enzyme-details" @toggle="confidenceOpen = $event.target.open"><summary>Structure confidence along the sequence <span>pLDDT</span></summary><ScientificChart v-if="confidenceOpen" title="Local structure confidence" description="AlphaFold pLDDT measures confidence in local structure, not enzyme activity or site annotation confidence." type="line" :rows="confidenceRows" x-label="Model residue" y-label="pLDDT" :max="100" :threshold="70" @select="index => viewer?.focusSite({position:mapping.residues[index].resi, chain:mapping.residues[index].chain})" /></details>
      </template>
      <div v-else class="structure-empty" role="status"><div class="structure-placeholder-mark" aria-hidden="true">{{ loading ? '···' : '3D' }}</div><div><strong>{{ loading ? 'Loading reference structure…' : structureError ? 'Structure unavailable' : 'Reference structure' }}</strong><p>{{ loading ? 'Sequence, reactions and site annotations can be explored below.' : structureError || (accession ? 'Load a public AlphaFold model to explore annotated residues in 3D.' : 'A UniProt accession is needed to retrieve a reference model.') }}</p><button v-if="accession && !loading" @click="loadStructure">{{ structureError ? 'Retry structure' : 'Load structure' }}</button></div></div>
    </section>

</template>
<script setup>
import {computed,ref,watch,onMounted,onBeforeUnmount} from 'vue';
import api from '@/api';
import {accessionId,referenceMapping} from '@/utils/enzymeInfo';
import ProteinViewer from './ProteinViewer.vue';
import ScientificChart from './ScientificChart.vue';
const props=defineProps({accession:String,sequence:{type:String,default:''},sites:{type:Array,default:()=>[]},sitePalette:Object,annotationSource:{type:String,default:'UniProt'},description:String});
const emit=defineEmits(['select']);
const model=ref(null),loading=ref(false),structureError=ref(''),structureSection=ref(null),viewer=ref(null),confidenceOpen=ref(false);
const mapping=computed(()=>referenceMapping(props.sequence,model.value?.structure_data));
const mappedSites=computed(()=>mapping.value.valid ? props.sites.filter(s=>s.position && mapping.value.positions.has(s.position)).map(s=>({...s,chain:mapping.value.chain})) : []);
const confidenceRows=computed(()=>mapping.value.residues.map(a=>({label:String(a.resi),value:Number.isFinite(a.b)?a.b:null})));
let observer,controller,generation=0;
function focusPosition(position) {
  if(!mapping.value.valid || !mapping.value.positions.has(position))return false;
  viewer.value?.focusSite({position,residue:props.sequence[position-1],chain:mapping.value.chain});return true;
}
function selectAtom(atom){if(mapping.value.valid && atom.chain===mapping.value.chain && mapping.value.positions.has(atom.resi))emit('select',atom.resi);}
async function loadStructure(){
  if(!accessionId(props.accession) || loading.value)return;
  const current=++generation;controller?.abort();controller=new AbortController();loading.value=true;structureError.value='';
  try{const result=await api.get(`/query/enzyme-full-info/${props.accession}/structure`,{signal:controller.signal,timeout:30000});if(current===generation){if(!result.success||!result.structure_data)throw new Error('No reference coordinates were returned.');model.value=result;}}
  catch(error){if(current===generation)structureError.value=error.message||'The reference structure could not load.';}
  finally{if(current===generation)loading.value=false;}
}
function observeStructure(){observer?.disconnect();if(!structureSection.value)return;observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){observer.disconnect();loadStructure();}},{rootMargin:'180px'});observer.observe(structureSection.value);}
watch(()=>props.accession,()=>{generation++;controller?.abort();model.value=null;loading.value=false;structureError.value='';observeStructure();});
onMounted(observeStructure);
onBeforeUnmount(()=>{generation++;controller?.abort();observer?.disconnect();});
defineExpose({focusPosition});
</script>
<style scoped>
.enzyme-section{margin:24px 0;padding-top:22px;border-top:1px solid var(--color-border);min-width:0}.section-heading,.structure-meta{display:flex;align-items:center;flex-wrap:wrap;gap:10px}.section-heading{justify-content:space-between;align-items:flex-start;margin-bottom:10px}.eyebrow{font-size:9px;font-weight:600;letter-spacing:1px;color:var(--color-text-muted)}.section-heading h4{font-size:16px;line-height:1.5;margin:4px 0 0;font-weight:600}.section-tag{font-size:10px;font-weight:500;padding:5px 9px;border-radius:5px;background:var(--color-primary-light);color:var(--color-primary)}.section-note{font-size:12px;color:var(--color-text-secondary);line-height:1.75;margin:10px 0}.structure-meta{font-size:11px;color:var(--color-text-muted);gap:8px 16px;margin:14px 0}a{color:var(--color-primary);text-decoration:none}a:hover{text-decoration:underline}button{cursor:pointer;background:var(--color-surface);border:1px solid var(--color-border);border-radius:5px;padding:6px 10px;font:inherit;font-size:11px;color:var(--color-primary)}.structure-empty{display:flex;align-items:center;justify-content:center;gap:18px;padding:32px 20px;background:var(--color-background);border:1px solid var(--color-border);border-radius:12px;min-height:180px}.structure-placeholder-mark{width:56px;height:56px;flex-shrink:0;display:grid;place-items:center;border:1px solid var(--color-border);border-radius:14px;background:var(--color-primary-light);font-size:17px;color:var(--color-primary)}.structure-empty strong{font-size:13px}.structure-empty p{font-size:12px;line-height:1.7;max-width:460px;color:var(--color-text-secondary);margin:8px 0 12px}.inline-notice{font-size:12px;padding:12px 14px;border-left:3px solid #bf942a;background:#fffaf0;line-height:1.7}.enzyme-details{border:1px solid var(--color-border);border-radius:8px;padding:12px 14px;margin:12px 0;min-width:0}.enzyme-details>summary{cursor:pointer;font-size:12px;font-weight:550;line-height:1.6}.enzyme-details>summary span{font-size:10px;font-weight:400;color:var(--color-text-muted);margin-left:8px}.enzyme-details[open]>summary{margin-bottom:16px}.enzyme-details :deep(.scientific-chart){border:0;padding:0;margin:12px 0}.mapping-status{font-size:11px}:deep(.protein-workbench){margin:14px 0}:deep(.protein-toolbar){padding:12px}:deep(.protein-toolbar .eyebrow){display:none}
@container (max-width:500px){.section-heading h4{font-size:15px}.structure-empty{padding:22px 14px;gap:12px}.enzyme-details{padding:12px 10px}:deep(.molecule-area){height:320px}}
</style>
