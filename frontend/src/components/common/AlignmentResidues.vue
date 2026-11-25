<template>
  <div ref="container" class="residue-view">
    <p v-if="!blocks.length" class="note">Aligned residue strings are unavailable for this segment.</p>
    <template v-else>
      <div class="controls">
        <div class="view-options" role="group" aria-label="Residue view">
          <button type="button" :aria-pressed="!differencesOnly" @click="differencesOnly = false">Alignment</button>
          <button type="button" :aria-pressed="differencesOnly" :disabled="!changes.length" @click="differencesOnly = true">Differences ({{ changes.length }})</button>
        </div>
        <div v-if="!differencesOnly" class="legend" aria-label="Alignment symbols">
          <span v-for="item in legend" :key="item.kind"><b :class="item.kind">{{ item.symbol }}</b>{{ item.label }}</span>
        </div>
      </div>
      <p v-if="hit.alignment_length > hit.query.length" class="note">Showing {{ hit.query.length }} saved columns of {{ hit.alignment_length }} aligned.</p>
      <component :is="differencesOnly ? ResultPreview : 'div'" :class="{ 'change-preview': differencesOnly }"
        v-bind="differencesOnly ? { title:previewTitle, note:'Positions use each protein’s residue numbering. A dash marks a gap or an unavailable coordinate.' } : {}">
        <div v-if="!differencesOnly" class="sequence-window" :style="{ '--coord-width': coordinateWidth + 'ch' }" role="group" aria-label="Aligned query and hit residues">
          <div v-for="block in visibleBlocks" :key="block.offset" class="sequence-block">
            <div v-for="row in rows" :key="row.key" class="sequence-line" :class="{ symbols: row.key === 'marks' }" :aria-hidden="row.key === 'marks' || undefined">
              <span class="row-label">{{ row.label }}</span>
              <span class="coordinate">{{ row.label ? block[row.key+'Start'] ?? '—' : '' }}</span>
              <code><span v-for="(run, i) in block.runs" :key="i" :class="[run.kind, { spaced: run.groupStart }]">{{ run[row.key] }}</span></code>
              <span class="coordinate end">{{ row.label ? block[row.key+'End'] ?? '—' : '' }}</span>
            </div>
          </div>
        </div>
        <table v-else class="change-table">
            <thead><tr><th>Column</th><th>Query</th><th>Hit</th><th>Difference</th></tr></thead>
            <tbody><tr v-for="change in visibleChanges" :key="change.column">
              <td>{{ change.column }}</td>
              <td><b>{{ change.query }}</b> {{ change.queryPosition ?? '—' }}</td>
              <td><b :class="change.kind">{{ change.subject }}</b> {{ change.subjectPosition ?? '—' }}</td>
              <td>{{ change.kind === 'gap' ? (change.query === '-' ? 'Gap in query' : 'Gap in hit') : change.kind === 'positive' ? 'Positive substitution' : 'Substitution' }}</td>
            </tr></tbody>
        </table>
        <div v-if="pages > 1" class="pages">
          <span aria-live="polite">{{ differencesOnly ? 'Differences' : 'Blocks' }} {{ first + 1 }}–{{ Math.min(first + pageSize, total) }} of {{ total }}</span>
          <button type="button" :disabled="pageIndex === 0" :aria-label="'Previous '+pageLabel" @click="pageIndex--">← Previous</button>
          <button type="button" :disabled="pageIndex + 1 >= pages" :aria-label="'Next '+pageLabel" @click="pageIndex++">Next →</button>
        </div>
      </component>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import ResultPreview from './ResultPreview.vue';
import { alignmentBlocks } from '@/utils/blastAlignment';

const props = defineProps({ hit: { type:Object, required:true }, previewTitle: { type:String, required:true } });
const container = ref(null), columns = ref(30), differencesOnly = ref(false), pageIndex = ref(0);
const rows = [{key:'query',label:'Query'}, {key:'marks',label:''}, {key:'subject',label:'Hit'}];
const legend = [
  {kind:'identical',symbol:'|',label:'Identical'}, {kind:'positive',symbol:'+',label:'Positive substitution'},
  {kind:'substitution',symbol:'·',label:'Other substitution'}, {kind:'gap',symbol:'–',label:'Gap'},
];
const coordinateWidth = computed(() => Math.max(2, ...[
  props.hit.query_start, props.hit.query_end, props.hit.subject_start, props.hit.subject_end,
].filter(Number.isInteger).map(n => String(n).length)));
const pageSize = computed(() => differencesOnly.value ? 8 : 3);
const blocks = computed(() => alignmentBlocks(props.hit, columns.value));
const changes = computed(() => blocks.value.flatMap(block => block.differences));
const total = computed(() => differencesOnly.value ? changes.value.length : blocks.value.length);
const pages = computed(() => Math.ceil(total.value / pageSize.value));
const first = computed(() => pageIndex.value * pageSize.value);
const visibleBlocks = computed(() => blocks.value.slice(first.value, first.value + pageSize.value));
const visibleChanges = computed(() => changes.value.slice(first.value, first.value + pageSize.value));
const pageLabel = computed(() => differencesOnly.value ? 'residue differences' : 'alignment blocks');
watch(differencesOnly, () => { pageIndex.value = 0; });
watch(columns, () => { if (!differencesOnly.value) pageIndex.value = 0; });
let observer;
onMounted(() => {
  function fit(width) {
    // Reserve the two coordinates, row label, gaps and padding before wrapping residues.
    const space = width - 95 - 18 * coordinateWidth.value;
    columns.value = Math.min(100, Math.max(5, Math.floor(space / 48) * 5));
  }
  fit(container.value.clientWidth);
  observer = new ResizeObserver(([entry]) => fit(entry.contentRect.width));
  observer.observe(container.value);
});
onBeforeUnmount(() => observer?.disconnect());
</script>

<style scoped>
.residue-view { min-width: 0; }
.controls,.legend,.legend span,.pages { display:flex; align-items:center; flex-wrap:wrap; }
.controls { justify-content:space-between; gap:10px; margin:15px 0 10px; }
.legend { gap:5px 12px; }
.legend span,.note,.pages { font-size:12px; color:var(--color-text-secondary); }
.legend span { gap:4px; }
.legend b { display:grid; place-items:center; width:17px; height:17px; border-radius:4px; font:700 13px var(--font-mono); }
.view-options { display:inline-flex; padding:2px; gap:2px; border:1px solid var(--color-border); border-radius:6px; background:#f2f6f7; }
.view-options button { padding:5px 8px; border:1px solid transparent; border-radius:4px; background:transparent; color:var(--color-text-secondary); font:600 12px var(--font-family); cursor:pointer; }
.view-options button[aria-pressed="true"] { background:white; color:#165e53; border-color:#c7dcd6; }
.view-options button:disabled { opacity:.6; cursor:default; }
.change-preview { border:1px solid var(--color-border); border-radius:8px; overflow:hidden; }
.change-table { width:100%; border-collapse:collapse; font-size:12px; }
.change-table th,.change-table td { text-align:left; padding:7px clamp(3px,1.3vw,14px); border-bottom:1px solid var(--color-border); }
.change-table th { color:var(--color-text-secondary); font-size:11px; font-weight:600; }
.change-table td:not(:last-child) { font-family:var(--font-mono); white-space:nowrap; }
.change-table tr:last-child td { border-bottom:0; }
.change-table td b { padding:1px 3px; border-radius:3px; }
.sequence-window { border:1px solid var(--color-border); border-radius:8px; overflow-x:auto; background:var(--color-surface); }
.sequence-block { padding:12px 10px; min-width:max-content; }
.sequence-block + .sequence-block { border-top:1px solid var(--color-border); }
.sequence-line { display:grid; grid-template-columns:4.5ch var(--coord-width) max-content var(--coord-width); justify-content:start; gap:.6ch; align-items:baseline; font:14px/1.6 var(--font-mono); }
.sequence-line code { font:inherit; white-space:pre; letter-spacing:0; font-variant-ligatures:none; }
.sequence-line .row-label { font:600 11px var(--font-family); color:var(--color-text-secondary); }
.coordinate { text-align:right; color:var(--color-text-secondary); font-size:11px; }
.coordinate.end { text-align:left; }
.spaced { margin-left:.55ch; }
.identical { color:#175d53; background:#e7f4ef; }
.positive { color:#244b85; background:#deebfe; }
.substitution { color:#87430c; background:#ffebc5; }
.gap { color:#753958; background:#f7e3ee; }
.symbols { line-height:1; }
.symbols code span { background:none; }
.pages { gap:6px; margin-top:10px; }
.change-preview .pages { padding:0 8px 8px; }
.pages span { margin-right:auto; }
.pages button { padding:5px 9px; background:var(--color-surface); border:1px solid var(--color-border); border-radius:5px; color:var(--color-text); font:inherit; cursor:pointer; }
.pages button:disabled { opacity:.45; cursor:default; }
.note { margin:8px 0; }
</style>
