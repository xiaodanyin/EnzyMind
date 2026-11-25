<template>
  <section class="blast-result alignment-results" aria-label="Sequence alignment hits">
    <header class="heading">
      <div><h4>Alignment hits</h4><p>{{ segments.length }} {{ segments.length === 1 ? 'segment' : 'segments' }}<template v-if="queryLabel"> · Query {{ queryLabel }}</template><template v-if="data.query_length"> · {{ data.query_length.toLocaleString() }} aa</template></p></div>
      <div v-if="databaseLabel" class="database"><strong>{{ databaseLabel }}</strong><span v-if="data.database_size">{{ data.database_size.toLocaleString() }} sequences</span></div>
    </header>
    <p v-if="!segments.length" class="empty">No alignment segments were returned for this search.</p>
    <template v-else>
      <div class="blast-overview" :class="{ scrollable: segments.length > 6 }" role="group" aria-label="Select an alignment segment">
        <div class="comparison-labels comparison-grid" aria-hidden="true"><span>Protein hit</span><span>Query coverage</span><span>Identity</span><span>E-value</span></div>
        <button v-for="(segment, index) in segments" :key="index" type="button" class="hit-row comparison-grid"
          :class="{ selected: index === selection }" :aria-pressed="index === selection" @click="selection = index">
          <span class="protein-cell">
            <span class="rank">{{ index + 1 }}</span>
            <span class="protein-text">
              <span class="protein-name"><strong>{{ segment.name }}</strong><span v-if="segment.fullMatch" class="exact" title="Every position matches across both complete sequences">Full-length exact match</span></span>
              <span class="protein-meta"><span v-if="segment.id" class="accession">{{ segment.id }}</span><em v-if="segment.organism">{{ segment.organism }}</em></span>
            </span>
          </span>
          <span class="metric"><small>Query coverage</small><b>{{ percent(segment.coverage) }}</b>
            <span v-if="segment.coverage !== null" class="track" aria-hidden="true"><i :style="{ left: segment.offset+'%', width: segment.coverage+'%' }"></i></span>
          </span>
          <span class="metric"><small>Identity</small><b>{{ percent(segment.identity) }}</b>
            <span v-if="segment.identity !== null" class="track identity-track" aria-hidden="true"><i :style="{ width: segment.identity+'%' }"></i></span>
          </span>
          <span class="metric e-value"><small>E-value</small><b>{{ evalue(segment.hit.e_value) }}</b></span>
        </button>
      </div>
      <details class="metric-guide"><summary>How to read these scores</summary>
        <dl>
          <dt>Query coverage</dt><dd>Fraction of the full query spanned by this segment. The bar locates that span along the query.</dd>
          <dt>Identity</dt><dd>Identical residue pairs divided by all alignment columns, including gaps.</dd>
          <dt>E-value</dt><dd>Expected number of chance matches scoring at least this well in the searched database. Smaller values indicate stronger evidence of similarity. BLAST reports very small values as zero. Sequence similarity alone cannot confirm identical function.</dd>
        </dl>
      </details>
      <article v-if="active" class="hit-detail">
        <header class="detail-heading">
          <div><p class="segment-label">Segment {{ selection + 1 }} of {{ segments.length }}</p><h5>{{ active.name }}</h5></div>
        </header>
        <p v-if="active.organism || active.id" class="identity-line">
          <a v-if="active.link" :href="active.link" target="_blank" rel="noopener noreferrer">{{ active.id }} ↗</a><span v-else-if="active.id">{{ active.id }}</span>
          <em v-if="active.organism">{{ active.organism }}</em>
        </p>
        <dl v-if="detailMetrics.length" class="detail-metrics">
          <div v-for="metric in detailMetrics" :key="metric.label"><dt>{{ metric.label }}</dt><dd>{{ metric.value }}</dd></div>
        </dl>
        <h6>Residue alignment</h6>
        <AlignmentResidues :key="selection" :hit="active.hit" :preview-title="(active.id || active.name) + ' · residue differences'" />
        <details v-if="active.hit.title || active.hit.annotation" class="annotation" :key="'annotation-'+selection">
          <summary>Database record details</summary>
          <p v-if="active.hit.annotation?.ec"><strong>EC</strong> {{ active.hit.annotation.ec }}</p>
          <p v-if="active.hit.annotation?.function">{{ active.hit.annotation.function }}</p>
          <p v-if="active.hit.annotation?.source"><strong>Annotation source</strong> {{ active.hit.annotation.source }}</p>
          <p v-if="active.hit.title"><strong>Original title</strong> {{ active.hit.title }}</p>
        </details>
      </article>
    </template>
    <p v-if="data.database_release || ['partial','unavailable'].includes(data.annotation_status)" class="source-note">
      <span v-if="data.database_release">Database release · {{ data.database_release }}</span>
      <span v-if="['partial','unavailable'].includes(data.annotation_status)">Some hit annotations are unavailable.</span>
    </p>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue';
import AlignmentResidues from './AlignmentResidues.vue';
import { describeHit } from '@/utils/blastAlignment';
import { accessionId } from '@/utils/enzymeInfo';

const props = defineProps({ data: {type:Object, required:true}, inputs: {type:Object, default:() => ({})} });
const selection = ref(0);
const queryLabel = computed(() => props.data.sequence_source?.requested_accession ||
  accessionId(String(props.inputs.query || '').trim().toUpperCase()));
const databaseLabel = computed(() => ({
  local_uniprot:'Local UniProt', swissprot:'NCBI Swiss-Prot', nr:'NCBI nr',
})[props.data.database || props.inputs.database] || '');
const segments = computed(() => (props.data.alignments || []).filter(Boolean).map(hit => ({
  hit, ...describeHit(hit, props.data.query_length),
})));
const active = computed(() => segments.value[selection.value]);
const percent = value => value === null ? '—' : value.toFixed(1) + '%';
function evalue(value) {
  if (!Number.isFinite(value) || value < 0) return '—';
  return value > 0 && value < .001 ? value.toExponential() : String(value);
}
function range(start, end) {
  return Number.isInteger(start) && start > 0 && Number.isInteger(end) && end > 0 ? start + '–' + end : null;
}
const detailMetrics = computed(() => {
  const s = active.value;
  if (!s) return [];
  const h = s.hit;
  return [
    {label:'Query range', value:range(h.query_start,h.query_end)},
    {label:'Hit range', value:range(h.subject_start,h.subject_end)},
    {label:'Hit length', value:h.length > 0 ? h.length.toLocaleString() + ' aa' : null},
    {label:'Identical columns', value:s.identities !== null ? s.identities + ' / ' + s.length : null},
    {label:'Gaps', value:h.gaps}, {label:'Bit score', value:h.bits},
  ].filter(m => m.value != null);
});
</script>

<style scoped>
.blast-result {
  --ink:#172f42; --secondary:#476071; --accent:#126e64; --rule:var(--color-border);
  min-width:0; container-type:inline-size; margin:24px 0; color:var(--ink);
}
.heading,.detail-heading { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px 18px; }
.heading { margin-bottom:15px; }
.heading h4 { margin:0; font-size:clamp(19px, 2vw, 24px); letter-spacing:-.035em; line-height:1.2; }
.heading p,.detail-heading p,.identity-line,.source-note { color:var(--secondary); font-size:12px; line-height:1.6; }
.heading p { margin:5px 0 0; }
.database { display:flex; flex-wrap:wrap; justify-content:flex-end; align-items:baseline; gap:4px 9px; color:var(--secondary); font-size:12px; }
.database strong { color:var(--ink); }
.blast-overview { border:1px solid var(--rule); border-radius:10px; overflow:auto; }
.blast-overview.scrollable { max-height:28rem; }
.comparison-grid { display:grid; grid-template-columns:minmax(0,1fr) minmax(86px, .31fr) minmax(65px,.23fr) minmax(65px,.24fr); align-items:center; gap:16px; padding:12px 16px; }
.comparison-labels { position:sticky; top:0; z-index:1; background:#f1f5f8; color:var(--secondary); font-size:11px; font-weight:600; }
.hit-row { width:100%; border:0; border-top:1px solid var(--rule); background:var(--color-surface); color:inherit; text-align:left; cursor:pointer; font:inherit; }
.hit-row:hover { background:#f6f9fa; }
.hit-row.selected { box-shadow:inset 3px 0 var(--accent); background:#edf8f5; }
.hit-row:focus-visible { outline:2px solid var(--color-primary); outline-offset:-3px; }
.protein-cell { display:flex; align-items:flex-start; gap:10px; min-width:0; }
.rank { flex:none; min-width:24px; height:24px; padding:0 4px; box-sizing:border-box; display:grid; place-items:center; border:1px solid var(--rule); border-radius:6px; color:var(--secondary); background:var(--color-surface); font:600 11px var(--font-mono); }
.selected .rank { border-color:var(--accent); background:var(--accent); color:white; }
.protein-text { min-width:0; overflow-wrap:anywhere; }
.protein-name { display:flex; gap:3px 8px; align-items:center; flex-wrap:wrap; }
.protein-text strong { font-size:15px; line-height:1.4; }
.protein-meta,.identity-line { display:flex; align-items:baseline; flex-wrap:wrap; gap:3px 9px; }
.protein-meta { margin-top:3px; font-size:11px; line-height:1.5; color:var(--secondary); }
.accession,.metric b { font-family:var(--font-mono); }
.accession { color:#365271; }
.metric { min-width:0; }
.metric b { font-size:13px; font-weight:600; overflow-wrap:anywhere; }
.metric small { position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); }
.track { position:relative; display:block; height:5px; background:#dae4e6; border-radius:5px; margin-top:4px; overflow:hidden; }
.track i { position:absolute; height:100%; background:#6786aa; border-radius:5px; }
.identity-track i { left:0; background:#409282; }
.metric-guide,.annotation { font-size:12px; color:var(--secondary); }
.metric-guide { margin:9px 0 18px; }
summary { cursor:pointer; font-weight:600; width:fit-content; }
.metric-guide dl { display:grid; grid-template-columns:max-content 1fr; gap:5px 14px; margin:10px 0; line-height:1.65; }
.metric-guide dt { font-weight:600; }.metric-guide dd { margin:0; }
.hit-detail { min-width:0; padding:18px; border:1px solid var(--rule); border-top:3px solid var(--accent); border-radius:10px; background:var(--color-surface); }
.detail-heading .segment-label { margin:0 0 3px; color:var(--accent); font-size:11px; font-weight:650; }
.detail-heading h5 { margin:0; font-size:19px; line-height:1.35; overflow-wrap:anywhere; letter-spacing:-.025em; }
.exact { background:#e4f5ec; color:#166042; border:1px solid #b7dcca; border-radius:5px; padding:3px 8px; font-size:11px; font-weight:600; }
.identity-line { margin:5px 0 0; overflow-wrap:anywhere; }
.identity-line a { color:var(--color-primary); font-family:var(--font-mono); }
.detail-metrics { display:flex; gap:12px 24px; flex-wrap:wrap; margin:15px 0; padding:12px 0; border-block:1px solid var(--rule); }
.detail-metrics dt { color:var(--secondary); font-size:11px; }
.detail-metrics dd { margin:3px 0 0; font:600 13px var(--font-mono); }
.hit-detail h6 { margin:14px 0 0; font-size:14px; }
.annotation { margin-top:14px; }.annotation p { margin:6px 0; line-height:1.7; overflow-wrap:anywhere; }
.annotation strong { margin-right:6px; color:var(--ink); }
.source-note { display:flex; gap:2px 12px; flex-wrap:wrap; margin:10px 0 0; }
.empty { padding:18px; border:1px dashed var(--rule); border-radius:8px; color:var(--secondary); font-size:14px; }
@container (max-width:580px) {
  .comparison-labels { display:none; }.hit-row:first-of-type { border-top:0; }
  .hit-row { grid-template-columns:1.15fr 1fr 1fr; gap:8px 14px; padding:12px; }
  .protein-cell { grid-column:1/-1; }.metric small { position:static; display:block; width:auto; height:auto; clip-path:none; color:var(--secondary); font:500 11px var(--font-family); }
  .hit-detail { padding:12px; }.detail-metrics { gap:10px 17px; }
  .database { justify-content:flex-start; }.metric-guide dl { display:block; }.metric-guide dd { margin:0 0 6px; }
}
</style>
