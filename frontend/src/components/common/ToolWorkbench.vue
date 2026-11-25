<template>
  <PageContainer :title="tool.title" :description="tool.description" allow-overflow>
    <template #overview><ModelWorkflow :tool="tool" :input-type="parsed.type || state.protein.method" @focus-input="focusInput" /></template>
    <RetentionNotice compact />
    <form class="tool-form" @submit.prevent="submit" novalidate>
      <fieldset :disabled="state.running || preparing">
        <ProteinInput v-if="tool.protein !== false" ref="proteinInput" v-model="state.protein" :tool="tool" />
        <section v-if="showChemical" class="chemical-section" aria-labelledby="chemical-heading">
          <div class="field-heading"><div><span class="eyebrow">{{ tool.protein===false?'01':'02' }} / {{ isReaction?'REACTION':'SUBSTRATE' }}</span><h2 id="chemical-heading">{{ isReaction?'Describe the chemical transformation':'Add your substrate molecule' }}</h2></div><span v-if="tool.molecule==='optional-reaction'" class="optional">Optional</span></div>
          <p class="field-hint">{{ isReaction?'Use reactants>>products or draw both sides with a reaction arrow.':'Use a molecular SMILES string or draw a molecule with Ketcher.' }}</p>
          <div class="chemical-tabs" role="group" aria-label="Chemical input method"><button type="button" :aria-pressed="state.chemicalMode==='text'" @click="state.chemicalMode='text'">Paste SMILES</button><button type="button" :aria-pressed="state.chemicalMode==='draw'" @click="state.chemicalMode='draw'">Draw with Ketcher</button><button type="button" @click="loadChemicalExample">Load {{ isReaction?'reaction':'substrate' }} example</button></div>
          <KetcherEditor v-if="state.chemicalMode==='draw'" ref="editor" v-model="state.smiles" :mode="isReaction?'reaction':'molecule'" :disabled="state.running || preparing" />
          <label for="chemical-smiles">{{ isReaction?'Reaction SMILES':'Substrate SMILES' }}<span v-if="tool.molecule!=='optional-reaction'"> · Required</span></label>
          <textarea ref="chemicalInput" id="chemical-smiles" v-model="state.smiles" :placeholder="isReaction?'CC(=O)O.CCO>>CC(=O)OCC.O':'CC(=O)O'" rows="3" spellcheck="false" :aria-invalid="Boolean(chemicalError)" aria-describedby="chemical-error"></textarea>
          <p v-if="chemicalError" id="chemical-error" class="field-error" role="alert">{{ chemicalError }}</p>
          <p v-if="exampleUsed" class="field-hint">This example illustrates the input format; it is not experimental evidence for this enzyme.</p>
        </section>
        <p v-else-if="tool.molecule==='optional-reaction'" class="field-hint reaction-note">UniProt mode follows the database retrieval pathway. Choose sequence / FASTA input to supply your own reaction.</p>
        <details v-if="tool.id==='blast'" class="analysis-options"><summary>Search options</summary><label for="max-hits">Maximum returned alignment segments<select id="max-hits" v-model.number="state.maxHits"><option v-for="n in [3,5,10,25,50]" :key="n" :value="n">{{ n }}</option></select></label><label for="blast-database">Protein database<select id="blast-database" v-model="state.database"><option value="">Service default{{ localBlast ? " · local UniProt" : "" }}</option><option v-if="localBlast" value="local_uniprot">Local UniProt · reviewed snapshot</option><option value="nr">NCBI nr · broad coverage</option><option value="swissprot">Swiss-Prot · reviewed proteins</option></select></label><p class="field-hint">nr searches a broad collection; Swiss-Prot searches a smaller, reviewed collection and may miss unreviewed homologues. Remote searches use the shared NCBI queue. E-value threshold: 0.01.</p></details>
        <div class="submit-row"><button class="btn btn-primary" type="submit">{{ preparing?'Preparing input…':state.running?'Analysis submitted…':tool.action }} <span aria-hidden="true">→</span></button><button class="btn btn-secondary" type="button" @click="clear">Clear inputs</button><span class="output-hint">{{ tool.output }}</span></div>
      </fieldset>
    </form>
    <section v-if="state.running" class="run-status" role="status" aria-live="polite"><span class="run-indicator" aria-hidden="true"></span><div><strong>Analysis submitted · waiting for the service</strong><p>{{ elapsed }} elapsed. {{ tool.id==='structure'?'Model loading and structure prediction may take several minutes.':tool.id==='blast'?'The alignment may take several minutes.':'Your inputs are preserved while the service processes this request.' }}</p><small>You may switch pages in this tab. Refreshing can interrupt this request; completed saved results remain in Results.</small></div></section>
    <div v-if="state.error" class="run-error" role="alert"><strong>{{ state.error }}</strong><p>Review your input above, then submit again when ready. No automatic retry was sent.</p></div>
    <section v-if="state.record" ref="resultSection" class="workbench-result" aria-label="Analysis result" tabindex="-1"><ResearchResult :record="state.record" @updated="state.record = $event" /></section>
    <div v-else-if="!state.running && !state.error" class="result-expectation"><span>WHAT YOU WILL RECEIVE</span><p>{{ tool.output }}. Results include the original input, data source and export options.</p></div>
  </PageContainer>
</template>
<script setup>
import { computed, ref, defineAsyncComponent, onMounted, onBeforeUnmount, watch, nextTick } from 'vue';
import api from '@/api';
import PageContainer from '@/components/layout/PageContainer.vue';
import ModelWorkflow from './ModelWorkflow.vue';
import ProteinInput from './ProteinInput.vue';
import ResearchResult from './ResearchResult.vue';
import RetentionNotice from './RetentionNotice.vue';
import { toolById } from '@/config/tools';
import { parseProtein, validateChemical } from '@/utils/proteinInput';
import { toolState, toolRequest, runTool } from '@/utils/toolRuns';
const KetcherEditor=defineAsyncComponent(()=>import('@/components/KetcherEditor.vue'));
const props=defineProps({toolId:{type:String,required:true}});
const tool=toolById[props.toolId], state=toolState(props.toolId);
const proteinInput=ref(null),chemicalInput=ref(null),editor=ref(null),resultSection=ref(null),chemicalError=ref(''),preparing=ref(false),exampleUsed=ref(false),now=ref(Date.now());let timer;
const localBlast = ref(false);
onMounted(async () => {
  if (tool.id === 'blast') {
    try { localBlast.value = (await api.get('/query/blast/config')).local_available; }
    catch { localBlast.value = false; }
  }
});
const parsed=computed(()=>parseProtein(state.protein.text,tool.protein==='uniprot'?'uniprot':state.protein.method,state.protein.selected));
const isReaction=tool.molecule==='reaction'||tool.molecule==='optional-reaction';
const showChemical=computed(()=>tool.molecule && !(tool.molecule==='optional-reaction' && parsed.value.type==='uniprot'));
const elapsed=computed(()=>{const n=Math.max(0,Math.floor((now.value-state.started)/1000));return `${Math.floor(n/60)}m ${n%60}s`;});
function focusInput(){if(proteinInput.value)proteinInput.value.focus();else chemicalInput.value?.focus();}
function clear(){state.protein={text:'',method:'auto',selected:'',filename:''};state.smiles='';chemicalError.value='';state.error='';exampleUsed.value=false;editor.value?.clear();}
function loadChemicalExample(){state.smiles=isReaction?tool.exampleReaction:tool.exampleSmiles;exampleUsed.value=true;chemicalError.value='';}
async function submit(){
  if(state.running||preparing.value)return;state.error='';chemicalError.value='';preparing.value=true;
  let protein,smiles='';
  try {protein=tool.protein===false?null:proteinInput.value.validate();}
  catch(e){state.error=e.message;preparing.value=false;return;}
  try {if(showChemical.value){smiles=editor.value?await editor.value.getSmilesForSubmission():state.smiles.trim();if(smiles||tool.molecule!=='optional-reaction')smiles=validateChemical(smiles,isReaction?'reaction':'molecule');}}
  catch(e){chemicalError.value=e.message;preparing.value=false;chemicalInput.value?.focus();return;}
  preparing.value=false;
  await runTool(tool,toolRequest(tool,protein,smiles,{maxHits:state.maxHits,database:state.database}));
}
watch(()=>state.record?.id,async(record)=>{if(record){await nextTick();resultSection.value?.focus({preventScroll:true});}});
onMounted(()=>{timer=setInterval(()=>now.value=Date.now(),1000)});onBeforeUnmount(()=>clearInterval(timer));
</script>
<style scoped>
fieldset{border:0;padding:0;min-width:0}fieldset:disabled{opacity:.72}.field-heading{display:flex;justify-content:space-between;align-items:center;gap:14px}.field-heading h2{font-size:1.25rem;margin:5px 0 10px}.eyebrow{font-size:11px;font-weight:700;letter-spacing:.12em;color:var(--color-primary)}.chemical-section{margin-top:28px;padding-top:26px;border-top:1px solid var(--color-border)}.chemical-section:first-child{margin-top:0;padding-top:0;border-top:0}.optional{background:var(--color-primary-light);color:var(--color-primary);border-radius:20px;font-size:12px;padding:4px 10px}.field-hint{font-size:13px;line-height:1.7}.chemical-tabs{display:flex;gap:8px;margin:14px 0;flex-wrap:wrap}.chemical-tabs button{font:inherit;font-size:13px;padding:8px 12px;border:1px solid var(--color-border);border-radius:8px;background:white;cursor:pointer}.chemical-tabs button[aria-pressed=true]{color:var(--color-primary);border-color:var(--color-primary);background:var(--color-primary-light)}label{display:block;font-size:14px;margin:14px 0 7px;font-weight:600}label span{font-size:12px;font-weight:400}textarea{font-family:var(--font-mono);font-size:14px;resize:vertical}.field-error,.run-error{color:var(--color-error)}.field-error{font-size:13px;margin-top:8px}.submit-row{display:flex;gap:12px;align-items:center;margin-top:28px;flex-wrap:wrap}.output-hint{font-size:12px;color:var(--color-text-secondary)}.analysis-options{margin-top:20px;font-size:13px}.analysis-options summary{cursor:pointer}.analysis-options select{max-width:240px;margin:8px 0}.run-status{display:flex;align-items:flex-start;gap:16px;padding:20px;background:var(--color-primary-light);border-radius:12px;margin-top:24px;font-size:14px}.run-status p{margin:6px 0}.run-status small{font-size:12px;color:var(--color-text-secondary)}.run-indicator{width:18px;height:18px;flex-shrink:0;border:2px solid #bfd2f7;border-top-color:var(--color-primary);border-radius:50%;animation:spin 1s linear infinite;margin-top:3px}.run-error{margin-top:22px;padding:18px;border:1px solid #fecaca;background:#fff7f7;border-radius:12px;overflow-wrap:anywhere}.run-error p{font-size:13px;margin:8px 0 0}.workbench-result{margin-top:28px;border-top:1px solid var(--color-border);padding-top:28px;outline:none}.result-expectation{margin-top:28px;border-top:1px solid var(--color-border);padding-top:20px}.result-expectation span{font-size:10px;letter-spacing:.12em;font-weight:700;color:var(--color-text-secondary)}.result-expectation p{font-size:13px;margin:7px 0 0}.reaction-note{padding:12px;background:var(--color-primary-light);border-radius:8px;margin-top:16px}@keyframes spin{to{transform:rotate(360deg)}}@media(prefers-reduced-motion:reduce){.run-indicator{animation:none}}@media(max-width:550px){.submit-row>.btn-primary{width:100%}}
</style>
