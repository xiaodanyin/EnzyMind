<template>
  <div ref="shell" class="enzyme-partner">
    <div v-if="protein.name || protein.accession" class="enzyme-identity"><strong v-if="protein.name">{{ protein.name }}</strong><a v-if="protein.accession" :href="`https://www.uniprot.org/uniprotkb/${protein.accession}/entry`" target="_blank" rel="noopener noreferrer">UniProt {{ protein.accession }} ↗</a></div>
    <p v-if="protein.differentProtein" class="pair-note">The returned protein identifier differs from the submitted accession. Showing the returned protein with its own saved data.</p>
    <p v-if="protein.compatibility" class="pair-note">{{ protein.compatibility }}</p>
    <template v-if="protein.structure || protein.sites.length">
      <span class="source-label">Structure / residue annotations saved with this result</span>
      <ProteinViewer :structure="protein.structure" :format="protein.format" :sites="protein.sites" :sequence="savedSequence" :title="protein.accession || protein.name || 'Saved enzyme structure'" :confidence-type="protein.confidenceType" :show-residue-panel="Boolean(protein.sites.length)" />
    </template>
    <details v-if="sequences.length" class="sequence-fold" :open="!protein.structure">
      <summary>{{ protein.sequences.length ? 'Saved enzyme sequence' : 'Reference enzyme sequence' }} <span>{{ sequences.length===1 ? `${sequences[0].sequence.length} residues` : `${sequences.length} separate records` }}</span></summary>
      <p v-if="protein.ambiguousSequences" class="pair-note">Multiple sequences were saved. Their individual pairing with this result was not specified.</p>
      <div v-for="(entry,i) in sequences" :key="i" class="sequence-entry"><span class="source-label">{{ entry.source }}</span><SequencePreview :sequence="entry.sequence" :title="entry.name || `Protein ${i+1}`" /><button class="text-action" @click="exportSequence(entry,i)">Download FASTA</button></div>
    </details>
    <div v-if="protein.accession && !protein.sequences.length" class="reference-status" role="status">
      <p v-if="loading">Loading reference sequence…</p>
      <template v-else-if="reference"><p>Reference sequence retrieved for display. The sequence used by this historical run was not saved.</p><small>{{ reference.source?.name || 'UniProt' }}<template v-if="reference.source?.snapshot_created_at"> · snapshot {{ reference.source.snapshot_created_at }}</template><template v-else-if="reference.source?.retrieved_at"> · retrieved {{ new Date(reference.source.retrieved_at).toLocaleDateString('en-GB') }}</template><template v-if="reference.uniprot_id!==protein.accession"> · resolved accession {{ reference.uniprot_id }}</template></small></template>
      <template v-else><p>{{ error || 'Only the accession was saved. A reference sequence will load when this card is visible.' }}</p><button v-if="error" class="text-action" @click="loadSequence">Retry reference sequence</button></template>
    </div>
    <EcClassification v-if="protein.ecCodes.length" :payload="{ec_numbers:protein.ecCodes}" />
    <p v-if="protein.ecCodes.length && !protein.accession && !sequences.length && !protein.structure" class="pair-note">EC numbers describe enzyme functions. No individual protein sequence or structure was supplied.</p>
    <details v-if="protein.accession && !protein.structure" class="reference-fold" open>
      <summary>Reference 3D structure <span>AlphaFold</span></summary>
      <ReferenceStructure :accession="reference?.uniprot_id || protein.accession" :sequence="sequences.length===1 ? sequences[0].sequence : ''" description="Public AlphaFold reference model for this enzyme. The protein and the paired molecule are displayed as separate structures." />
    </details>
    <p v-if="!protein.accession && !sequences.length && !protein.structure && !protein.ecCodes.length && !protein.sites.length" class="pair-note">No enzyme sequence, structure or EC classification was saved with this result.</p>
  </div>
</template>
<script setup>
import {computed,ref,onMounted,onBeforeUnmount,watch} from 'vue';
import api from '@/api';
import {referenceSequenceFor} from '@/utils/enzymePairs';
import {downloadData} from '@/utils/workspace';
import SequencePreview from './SequencePreview.vue';
import ProteinViewer from './ProteinViewer.vue';
import ReferenceStructure from './ReferenceStructure.vue';
import EcClassification from './EcClassification.vue';
const props=defineProps({protein:{type:Object,required:true}});
const shell=ref(null),reference=ref(null),loading=ref(false),error=ref('');
const savedSequence=computed(()=>props.protein.sequences.length===1 ? props.protein.sequences[0].sequence : '');
const sequences=computed(()=>props.protein.sequences.length ? props.protein.sequences : reference.value ? [{sequence:reference.value.sequence_info.sequence,name:reference.value.uniprot_id,source:'Reference sequence · retrieved for display'}] : []);
let observer,controller,generation=0;
async function loadSequence(){
  const id=props.protein.accession;if(!id || props.protein.sequences.length || loading.value)return;
  const current=++generation;controller?.abort();controller=new AbortController();loading.value=true;error.value='';
  try{const result=await api.get(`/query/enzyme-full-info/${id}/sequence`,{signal:controller.signal,timeout:20000});if(current!==generation)return;const sequence=referenceSequenceFor(result,id);if(!sequence)throw new Error('The returned reference sequence did not match this accession.');reference.value={...result,sequence_info:{...result.sequence_info,sequence}};}
  catch(e){if(current===generation)error.value=e.message || 'Reference sequence unavailable. The saved result remains available.';}
  finally{if(current===generation)loading.value=false;}
}
function observe(){observer?.disconnect();if(!shell.value)return;observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){observer.disconnect();loadSequence();}},{rootMargin:'120px'});observer.observe(shell.value);}
watch(()=>props.protein,()=>{generation++;controller?.abort();reference.value=null;loading.value=false;error.value='';observe();});
onMounted(observe);onBeforeUnmount(()=>{generation++;controller?.abort();observer?.disconnect();});
function exportSequence(entry,index){downloadData(`>${props.protein.accession || `enzyme_${index+1}`} ${entry.source}\n${entry.sequence.match(/.{1,60}/g).join('\n')}\n`,`${props.protein.accession || 'enzyme'}-${index+1}.fasta`,'text/plain');}
</script>
<style scoped>
.enzyme-partner{min-width:0;container-type:inline-size}.enzyme-identity{display:flex;flex-direction:column;gap:6px;margin:0 0 16px}.enzyme-identity strong{font-size:15px;overflow-wrap:anywhere}.enzyme-identity a,.text-action{font-size:11px;color:var(--color-primary)}.enzyme-identity a{text-decoration:none}.source-label{display:block;font-size:10px;color:var(--color-text-muted);margin:10px 0}.sequence-fold,.reference-fold{border:1px solid var(--color-border);border-radius:8px;padding:12px;margin:12px 0}.sequence-fold>summary,.reference-fold>summary{cursor:pointer;font-size:12px;line-height:1.7;font-weight:600}.sequence-fold>summary span,.reference-fold>summary span{font-size:10px;color:var(--color-text-muted);font-weight:400;margin-left:8px}.sequence-entry{margin-top:14px}.pair-note,.reference-status{font-size:12px;line-height:1.75;color:var(--color-text-secondary)}.reference-status p{margin:8px 0}.reference-status small{font-size:10px;overflow-wrap:anywhere}.text-action{background:var(--color-surface);border:1px solid var(--color-border);border-radius:5px;padding:6px 9px;margin-top:10px;cursor:pointer}.reference-fold :deep(.enzyme-section){margin:12px 0 0;padding:0;border:0}.reference-fold :deep(.section-heading){display:none}:deep(.protein-workbench){margin:14px 0}:deep(.sequence-row code span),:deep(.sequence-row code button){width:14px;min-width:14px}:deep(.sequence-rows){max-width:100%}:deep(.ec-classifications h4){font-size:13px}
</style>
