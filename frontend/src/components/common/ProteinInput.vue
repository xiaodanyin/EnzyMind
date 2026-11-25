<template>
  <section class="protein-input" aria-labelledby="protein-input-title">
    <div class="field-heading"><div><span class="eyebrow">01 / PROTEIN INPUT</span><h2 id="protein-input-title">Start with your protein</h2></div><button type="button" class="btn btn-outline btn-sm" @click="example">Load protein example</button></div>
    <div class="input-modes" role="group" aria-label="Protein input format"><button v-for="m in methods" :key="m.id" type="button" :aria-pressed="modelValue.method === m.id" @click="update({ method: m.id })">{{ m.label }}</button></div>
    <label for="protein-query">{{ onlyUniprot || modelValue.method === 'uniprot' ? 'UniProt accession' : 'UniProt accession, protein sequence or FASTA' }} <span class="required">Required</span></label>
    <textarea id="protein-query" ref="input" :value="modelValue.text" @input="update({ text: $event.target.value, selected: '', filename: '' })" :rows="onlyUniprot ? 2 : 5" :placeholder="onlyUniprot ? 'P00761' : 'P00761, or paste your amino acid sequence / FASTA here…'" :aria-invalid="Boolean(touched && parsed.error)" aria-describedby="protein-help protein-validation" spellcheck="false" @blur="touched = true"></textarea>
    <div v-if="!onlyUniprot" class="drop-zone" :class="{ dragging }" @dragover.prevent="dragging = true" @dragleave.prevent="dragging = false" @drop.prevent="drop">
      <label for="protein-file">Drop a FASTA file here, or <strong>choose a file</strong><small>{{ modelValue.filename || '.fasta, .fa, .faa, .txt · up to 1 MB' }}</small></label><input id="protein-file" type="file" accept=".fasta,.fa,.faa,.txt" @change="fileChange" />
    </div>
    <label v-if="parsed.records?.length > 1" class="record-select">Select one of {{ parsed.records.length }} FASTA records<select :value="modelValue.selected" @change="update({ selected: $event.target.value })"><option value="" disabled>Choose a protein — no record is selected automatically</option><option v-for="(r, i) in parsed.records" :value="String(i)" :key="i">{{ r.name }} · {{ r.sequence.length }} aa</option></select></label>
    <p id="protein-validation" :class="{ 'field-error': uploadError || (touched && parsed.error), 'input-valid': !parsed.error }" role="status">{{ uploadError || (touched || modelValue.text ? parsed.error : '') || (!parsed.error ? `${parsed.type === 'uniprot' ? 'UniProt accession detected' : `${parsed.length} amino acids · ${parsed.label}`} · ready to submit` : '') }}</p>
    <p id="protein-help" class="field-hint">{{ onlyUniprot ? 'Find the accession on a UniProt protein entry. Names and EC numbers are not accessions.' : 'Whitespace and letter case are normalized. Other characters are preserved for review. One selected protein is submitted per analysis.' }}</p>
  </section>
</template>
<script setup>
import { computed, ref } from 'vue';
import { parseProtein } from '@/utils/proteinInput';
const props = defineProps({ modelValue: { type: Object, required: true }, tool: { type: Object, required: true } });
const emit = defineEmits(['update:modelValue']);
const touched = ref(false), dragging = ref(false), uploadError = ref(''), input = ref(null);
const onlyUniprot = computed(() => props.tool.protein === 'uniprot');
const methods = computed(() => onlyUniprot.value ? [{id:'uniprot',label:'UniProt accession'}] : [{id:'auto',label:'Detect automatically'},{id:'uniprot',label:'UniProt ID'},{id:'sequence',label:'Sequence / FASTA'}]);
const parsed = computed(() => parseProtein(props.modelValue.text, onlyUniprot.value ? 'uniprot' : props.modelValue.method, props.modelValue.selected));
function update(change) { uploadError.value = ''; emit('update:modelValue', { ...props.modelValue, ...change }); }
function example() { const id = onlyUniprot.value || props.modelValue.method !== 'sequence'; update({text: id ? props.tool.exampleId : props.tool.exampleSequence, selected:'',filename:''}); touched.value = true; }
async function readFile(file) { dragging.value = false; if (!file) return; if (file.size > 1048576) { uploadError.value = 'Choose a text FASTA file smaller than 1 MB.'; return; } try { const text = new TextDecoder('utf-8', {fatal:true}).decode(await file.arrayBuffer()); update({text,method:'sequence',selected:'',filename:file.name}); touched.value = true; } catch { uploadError.value = 'Could not read this file. Choose a UTF-8 FASTA text file.'; } }
function drop(e) { readFile(e.dataTransfer.files[0]); }
function fileChange(e) { readFile(e.target.files[0]); e.target.value = ''; }
function validate() { touched.value = true; if (uploadError.value || parsed.value.error) { input.value?.focus(); throw new Error(uploadError.value || parsed.value.error); } return parsed.value; }
defineExpose({validate, focus: () => input.value?.focus()});
</script>
<style scoped>
.field-heading{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:18px}.field-heading h2{font-size:1.25rem;margin:5px 0}.eyebrow{font-size:11px;color:var(--color-primary);letter-spacing:.12em;font-weight:700}.input-modes{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 18px}.input-modes button{font:inherit;font-size:13px;padding:8px 12px;border:1px solid var(--color-border);background:white;border-radius:8px;cursor:pointer}.input-modes button[aria-pressed=true]{background:var(--color-primary-light);border-color:var(--color-primary);color:var(--color-primary)}label{display:block;font-size:14px;font-weight:600;margin-bottom:7px}.required{font-size:11px;font-weight:400;margin-left:6px;color:var(--color-text-secondary)}textarea{font-family:var(--font-mono);resize:vertical;font-size:14px;line-height:1.65}.drop-zone{position:relative;border:1px dashed #a4b8d4;background:#f8faff;border-radius:10px;margin-top:12px;padding:17px}.drop-zone.dragging{background:var(--color-primary-light);border-color:var(--color-primary)}.drop-zone label{cursor:pointer;font-weight:400;margin:0}.drop-zone strong{color:var(--color-primary)}.drop-zone small{display:block;margin-top:4px;color:var(--color-text-secondary)}.drop-zone input{position:absolute;opacity:0;inset:0;width:100%;cursor:pointer}.record-select{margin-top:16px}.record-select select{margin-top:8px;font-size:13px}.field-hint,#protein-validation{font-size:13px;margin:9px 0 0;overflow-wrap:anywhere}.field-error{color:var(--color-error)}.input-valid{color:#047857}@media(max-width:550px){.field-heading{align-items:flex-start}.field-heading .btn{padding:7px 9px;font-size:11px}}
</style>
