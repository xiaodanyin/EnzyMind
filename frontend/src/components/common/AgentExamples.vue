<template>
  <section class="agent-examples" aria-label="Research examples">
    <div class="examples-heading"><h3>Explore a research example</h3><p>{{ AGENT_EXAMPLES.length }} starting points, from annotation to experimental decisions. Choose a question, then review it before sending.</p></div>
    <div class="example-grid">
      <button v-for="(item,i) in AGENT_EXAMPLES" :key="item.id" type="button" :aria-pressed="selectedId === item.id" :aria-controls="detailId" @click="selectExample(item.id)">
        <span class="example-category">0{{ i+1 }} / {{ item.category }}</span><strong>{{ item.title }}</strong><span class="example-description">{{ item.description }}</span>
      </button>
    </div>
    <article v-if="selected" ref="detail" :id="detailId" class="example-detail" aria-label="Selected research example">
      <div class="example-title"><h4>{{ selected.title }}</h4><button type="button" @click="selectedId=''" aria-label="Close example details">×</button></div>
      <p class="example-input">{{ selected.input }}</p>
      <div class="example-coverage"><span v-for="label in selected.coverage" :key="label">{{ label }}</span></div>
      <ul><li v-for="expectation in selected.expected" :key="expectation">{{ expectation }}</li></ul>
      <p v-if="selected.note" class="example-note">{{ selected.note }}</p>
      <p v-if="selected.requiresResult" class="example-note">{{ hasAttachments ? 'A saved result is attached. You can load this question.' : 'Attach a result from your workspace before using this example.' }}</p>
      <details><summary>Read the starting question</summary><p class="example-prompt">{{ selected.prompt }}</p></details>
      <details><summary>Try a follow-up after the first answer</summary><p class="example-prompt">{{ selected.followUp }}</p><button type="button" class="example-secondary" @click="$emit('use',selected.followUp)">Load follow-up</button></details>
      <div class="example-footer"><div class="example-actions"><button type="button" class="example-primary" :disabled="selected.requiresResult && !hasAttachments" @click="$emit('use',selected.prompt)">Load starting question</button><button v-if="selected.requiresResult" type="button" class="example-secondary" @click="$emit('library')">Choose a saved result</button></div><span class="example-sources"><a v-for="source in selected.sources" :key="source.url" :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.label }} ↗</a></span></div>
    </article>
  </section>
</template>
<script setup>
import {computed,ref,getCurrentInstance,nextTick} from 'vue';
import {AGENT_EXAMPLES} from '@/config/agentExamples';
defineProps({hasAttachments:{type:Boolean,default:false}});
defineEmits(['use','library']);
const selectedId=ref('');
const detail=ref(null);
const selected=computed(()=>AGENT_EXAMPLES.find(item=>item.id===selectedId.value));
const detailId=`research-example-${getCurrentInstance().uid}`;
async function selectExample(id) {
  selectedId.value=id;
  await nextTick();
  detail.value?.scrollIntoView({block:'start'});
}
</script>
<style scoped>
.agent-examples{margin:26px 0;min-width:0}.examples-heading h3{font-size:15px;font-weight:650;margin:0}.examples-heading p{font-size:12px;line-height:1.7;color:var(--color-text-secondary);margin:7px 0 14px}.example-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.example-grid>button{display:flex;flex-direction:column;gap:7px;text-align:left;padding:16px 18px;min-width:0;border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-surface);font:inherit;cursor:pointer}.example-grid>button:last-child:nth-child(odd){grid-column:1/-1}.example-grid>button:hover,.example-grid>button[aria-pressed=true]{border-color:var(--color-primary);background:var(--color-primary-light)}.example-category{font:10px var(--font-mono);color:var(--color-primary);letter-spacing:.04em}.example-grid strong{font-size:14px;color:var(--color-text);font-weight:600}.example-description{font-size:12px;line-height:1.55;color:var(--color-text-secondary)}.example-detail{margin-top:14px;padding:20px;border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-surface)}.example-title{display:flex;align-items:start;justify-content:space-between;gap:12px}.example-title h4{font-size:16px;margin:0}.example-title>button{border:0;background:none;color:var(--color-text-secondary);font-size:20px;cursor:pointer}.example-input{font-size:12px;overflow-wrap:anywhere;color:var(--color-text-secondary);margin:8px 0 12px}.example-coverage{display:flex;flex-wrap:wrap;gap:6px}.example-coverage span{font-size:10px;padding:4px 7px;border-radius:4px;background:var(--color-primary-light);color:var(--color-primary)}ul{padding-left:18px;font-size:12px;line-height:1.7;color:var(--color-text-secondary);margin:14px 0}.example-note{font-size:12px;line-height:1.7;border-left:2px solid var(--color-primary);padding-left:10px;margin:12px 0}details{font-size:12px;margin-top:12px}summary{cursor:pointer;color:var(--color-primary);line-height:1.6}.example-prompt{line-height:1.8;white-space:pre-wrap;overflow-wrap:anywhere;margin:10px 0;color:var(--color-text-secondary)}.example-footer{display:flex;flex-wrap:wrap;align-items:center;gap:12px;justify-content:space-between;margin-top:18px}.example-actions{display:flex;flex-wrap:wrap;gap:8px}.example-primary,.example-secondary{font:inherit;font-size:12px;padding:8px 12px;border-radius:6px;cursor:pointer}.example-primary{background:var(--color-primary);border:1px solid var(--color-primary);color:white}.example-primary:disabled{opacity:.5;cursor:not-allowed}.example-secondary{background:transparent;border:1px solid var(--color-border);color:var(--color-primary)}.example-sources{display:flex;gap:10px;flex-wrap:wrap;font-size:11px}.example-sources a{color:var(--color-text-secondary)}@media(max-width:600px){.example-grid{grid-template-columns:1fr}.example-grid>button{padding:14px}.example-detail{padding:16px}}
</style>
