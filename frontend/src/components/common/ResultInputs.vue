<template>
  <section class="result-inputs" aria-label="Submitted inputs">
    <header><h4>Submitted inputs</h4><span>Saved with this run</span></header>
    <p v-if="!items.length" class="input-note">No input fields were saved with this result.</p>
    <div v-for="item in items" :key="item.key" class="input-field">
      <div class="input-label">{{ item.label }}</div>
      <template v-if="item.kind === 'sequence'"><SequencePreview v-for="(entry,i) in item.records" :key="i" :sequence="entry.sequence" :title="entry.name" /><details><summary>Original sequence input</summary><pre>{{ item.value }}</pre></details></template>
      <template v-else-if="item.kind === 'accession'"><a :href="`https://www.uniprot.org/uniprotkb/${item.accession}/entry`" target="_blank" rel="noopener noreferrer">{{ item.value }} ↗</a><p v-if="!resolvedSequence" class="input-note">Only the accession was saved; this result does not include its sequence.</p></template>
      <template v-else><ChemicalPreview v-if="item.kind === 'chemical'" :smiles="item.value" /><pre>{{ item.value }}</pre></template>
    </div>
    <div v-if="resolvedSequence" class="input-field"><SequencePreview :sequence="resolvedSequence" title="Sequence returned with this result" /></div>
  </section>
</template>
<script setup>
import {computed} from 'vue';
import {resultInputs,returnedSequence} from '@/utils/resultInputs';
import SequencePreview from './SequencePreview.vue';
import ChemicalPreview from './ChemicalPreview.vue';
const props=defineProps({record:{type:Object,required:true}});
const items=computed(()=>resultInputs(props.record)),resolvedSequence=computed(()=>returnedSequence(props.record));
</script>
<style scoped>
.result-inputs{margin:20px 0;padding:18px;border:1px solid var(--color-border);border-radius:10px;background:var(--color-surface);min-width:0}.result-inputs header{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}.result-inputs h4{margin:0;font-size:14px}.result-inputs header span,.input-note{font-size:11px;color:var(--color-text-muted);line-height:1.6}.input-field{margin-top:14px;min-width:0}.input-label{text-transform:capitalize;font-size:11px;font-weight:600;color:var(--color-text-secondary);margin-bottom:6px}.input-field pre{white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;font:12px/1.7 monospace;background:var(--color-bg-secondary);border-radius:5px;padding:8px;max-height:220px;overflow:auto;margin:0}.input-field a{font-size:13px;color:var(--color-primary)}.input-field details{font-size:11px;margin-top:8px}.input-field summary{cursor:pointer;color:var(--color-text-secondary)}
</style>
