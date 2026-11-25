<template>
  <article
    class="research-result"
    :class="{ 'failed-result': record.status === 'failed' }"
  >
    <header class="research-result-header">
      <div>
        <span class="eyebrow"
          >{{ evidenceLabel(record) }} <span aria-hidden="true">/</span>
          {{ record.tool }}</span
        >
        <h3>{{ record.title }}</h3>
      </div>
      <span class="result-state">{{
        data.partial ? 'Partial result' : data.source?.stale ? 'Cached result' : resultStatusLabel(record.status)
      }}</span>
    </header>
    <div class="result-meta">
      <span>{{ new Date(record.created * 1000).toLocaleString('en-US') }}</span
      ><span v-if="record.duration">{{ record.duration.toFixed(1) }} s</span
      ><code :title="record.id">{{ record.id.slice(0, 8) }}</code>
    </div>
    <RetentionNotice v-if="!record.local_only" :expires-at="resultExpiry(record)" :notice-key="`retention-result:${record.id}`">
      <button @click="exportResult">Download full result JSON</button>
    </RetentionNotice>
    <section v-if="pending && record.tool === 'structure'" class="blast-pending" role="status">
      <h4>Predicting structure</h4>
      <p>The result updates when coordinates are ready. You can return to this run in Results.</p>
      <p v-if="pollError" class="result-failure">{{ pollError }}</p>
    </section>
    <section v-else-if="pending" class="blast-pending" aria-label="BLAST search status" role="status">
      <h4>{{ record.status === 'submitting' ? 'Submitting your search once' : record.status === 'paused' ? 'Automatic checks paused' : 'Your search is queued at NCBI' }}</h4>
      <p>{{ record.status === 'paused' ? 'Automatic retrieval paused after 24 hours. Check status to resume this same request.' : 'Your search is saved. You can close this page and return to Results; the server will retrieve available alignments automatically.' }}</p>
      <p v-if="data.database !== 'local_uniprot'">NCBI controls queue time. No alignment results are available yet.</p>
      <dl><dt>Database</dt><dd>{{ data.database === 'local_uniprot' ? 'Local UniProt snapshot' : data.database === 'swissprot' ? 'Swiss-Prot · reviewed proteins' : 'nr · broad protein coverage' }}</dd>
        <template v-if="data.request_id"><dt>NCBI request ID</dt><dd><code>{{ data.request_id }}</code></dd></template>
        <template v-if="data.last_checked_at"><dt>Last checked</dt><dd>{{ new Date(data.last_checked_at * 1000).toLocaleString('en-GB') }}</dd></template>
      </dl>
      <p v-if="data.last_poll_error">{{ data.last_poll_error }}</p>
      <div v-if="data.request_id" class="blast-pending-actions"><button v-if="!record.local_only" :disabled="checking" @click="refresh">{{ checking ? 'Checking…' : 'Check status' }}</button><a :href="`https://blast.ncbi.nlm.nih.gov/Blast.cgi?CMD=Get&amp;RID=${encodeURIComponent(data.request_id)}`" target="_blank" rel="noopener noreferrer">Open this request at NCBI ↗</a></div>
      <small v-if="data.database !== 'local_uniprot'">Checks are spaced at least one minute apart. Checking status does not start another search.</small>
      <p v-if="pollError" class="result-failure">{{ pollError }}</p>
    </section>
    <EnzymePairResult v-if="pairs.length" :key="record.id" :pairs="pairs" :tool="record.tool">
      <template v-if="metrics.length && !failure" #default><div class="result-metrics"><div v-for="metric in metrics" :key="metric.label"><span>{{ metric.label }}</span><strong>{{ formatMetric(metric.value) }} <small>{{ metric.unit }}</small></strong></div></div></template>
    </EnzymePairResult>
    <ResultInputs v-if="!blastResult && !pairs.length && !['python', 'enzyme-info', 'mcsa-query'].includes(record.tool)" :record="record" />
    <p v-if="failure" class="result-failure" role="alert">{{ failure }}</p>
    <section v-if="data.partial || data.source?.method === 'uniprot_cache'" class="annotation-notice" :class="{ 'annotation-warning': data.partial || data.source?.stale }" aria-label="Annotation availability" role="status">
      <strong>{{ data.partial ? 'Partial annotations available' : data.source?.stale ? 'Previously retrieved annotations' : 'Saved UniProt annotations' }}</strong>
      <p v-for="(warning, index) in data.warnings?.length ? data.warnings : [data.source?.note]" :key="index">{{ warning }}</p>
      <small v-if="data.source?.retrieved_at">Retrieved from UniProt: {{ new Date(data.source.retrieved_at).toLocaleString('en-GB') }}</small>
      <small v-else-if="data.source?.snapshot_created_at">Local snapshot: {{ new Date(data.source.snapshot_created_at).toLocaleDateString('en-GB') }}</small>
    </section>
    <div v-if="!blastResult && !pairs.length && metrics.length && !['enzyme-info', 'mcsa-query'].includes(record.tool)" class="result-metrics">
      <div v-for="metric in metrics" :key="metric.label">
        <span>{{ metric.label }}</span
        ><strong
          >{{ formatMetric(metric.value) }}
          <small>{{ metric.unit }}</small></strong
        >
      </div>
    </div>
    <p v-if="record.tool === 'parameters' && data.source?.name" class="calculation-source">
      Calculation source: <strong>{{ data.source.name }} {{ data.source.version || '' }}</strong>.
      <span v-if="data.source.method === 'local_fallback'">Local fallback; values may differ slightly from ExPASy.</span>
    </p>
    <McsaResult v-if="record.tool === 'mcsa-query' && !failure" :data="data" />
    <EnzymeInfoResult v-if="record.tool === 'enzyme-info' && !failure" :data="data" />
    <PythonResult v-if="record.tool === 'python'" :record="record" />
    <ResultInsights v-if="!blastResult && !pending && !['python', 'enzyme-info', 'mcsa-query'].includes(record.tool)" :record="record" :show-classification="!pairs.length" />
    <section v-if="sequenceReport" class="sequence-report">
      <h4>Amino acid sequence</h4>
      <p>UniProt sequence · original residue order</p>
      <pre>{{ sequenceReport }}</pre>
    </section>
    <div v-for="(panel, index) in pairs.length ? [] : panels" :key="index">
      <p v-if="panel.record_compatibility?.message" class="compatibility-note">
        {{ panel.record_compatibility.message }}
      </p>
      <ProteinViewer
        :structure="
          panel.structure_data || panel.pdb_content || panel.pdb_text || ''
        "
        :format="panel.structure_format || 'pdb'"
        :sites="siteRows(panel)"
        :sequence="proteinSequence(panel)"
        :title="
          panel.uniprot_id ||
          panel.name ||
          data.uniprot_id ||
          `Protein ${index + 1}`
        "
        :confidence-type="
          record.tool === 'structure' ? 'plddt' : panel.confidence_type || ''
        "
      />
    </div>
    <template v-if="blastResult">
      <BlastResult :key="record.id" :data="data" :inputs="record.inputs" />
      <details class="result-details"><summary>Submitted query and search settings</summary><ResultInputs :record="record" /></details>
    </template>
    <details v-if="markdown && (blastResult || composition.length || pairs.length)" class="result-details">
      <summary>{{ blastResult || pairs.length ? 'Full service report' : 'Full physicochemical report' }}</summary>
      <div
        class="research-markdown"
        v-html="renderMarkdown(markdown, { expandTables: true })"
        @click="followReference"
      ></div>
    </details>
    <div
      v-else-if="markdown"
      class="research-markdown"
      v-html="renderMarkdown(markdown, { expandTables: true })"
      @click="followReference"
    ></div>
    <ResultPreviewDialog v-if="expandedMarkdown" :title="`${record.title} — table`" :return-focus="expandedMarkdown.trigger" @close="expandedMarkdown = null">
      <table>
        <thead><tr><th v-for="(cell, i) in expandedMarkdown.headings" :key="i" scope="col">{{ cell }}</th></tr></thead>
        <tbody><tr v-for="(row, i) in expandedMarkdown.rows" :key="i"><td v-for="(cell, j) in row" :key="j">{{ cell }}</td></tr></tbody>
      </table>
    </ResultPreviewDialog>
    <ScientificData
      v-if="
        !pairs.length && !['python', 'enzyme-info', 'mcsa-query'].includes(record.tool) && !pending && !markdown && !panels.length && !blastResult && !sequenceReport
      "
      :value="detailData"
      :class="{ 'reported-kinetics': record.tool === 'kinetics' }"
      :column-order="record.tool === 'kinetics' ? ['substrate', 'value', 'unit'] : []"
    />
    <details v-if="markdown && data.parameters" class="result-details">
      <summary>Detailed calculated properties</summary>
      <ScientificData :value="data.parameters" />
    </details>
    <details class="result-details">
      <summary>Input &amp; provenance</summary>
      <dl>
        <dt>Evidence</dt>
        <dd>{{ evidenceLabel(record) }}</dd>
        <dt>Source</dt>
        <dd>{{ sourceName }}</dd>
      </dl>
      <pre>{{ JSON.stringify(record.inputs, null, 2) }}</pre>
      <p v-if="record.evidence_type?.includes('Predict')">
        This is a computational prediction. Evaluate it alongside experimental
        evidence.
      </p>
    </details>
    <details class="result-details" data-guide="full-result-data" @toggle="rawOpen = $event.target.open">
      <summary>Complete result data</summary>
      <pre v-if="rawOpen">{{ JSON.stringify(record.payload, null, 2) }}</pre>
    </details>
    <footer class="research-result-actions">
      <button v-if="!record.local_only" class="primary-action" @click="askAgent">
        Discuss with Agent <span>↗</span>
      </button>
      <button
        @click="
          downloadData(
            record,
            `enzymind-${record.tool}-${record.id.slice(0, 8)}.json`,
          )
        "
      >
        Export JSON
      </button>
      <button v-if="toolById[record.tool]" @click="reuseInputs">Reuse inputs</button>
      <button v-if="metrics.length" @click="exportMetrics">Export metrics CSV</button>
      <button v-if="sites.length" @click="exportSites">
        Export residues CSV
      </button>
      <button v-if="!record.local_only" @click="copyLink">
        {{ copied ? "Link copied" : "Copy result link" }}
      </button>
      <router-link v-if="!standalone && !record.local_only" :to="`/results/${record.id}`"
        >Open result →</router-link
      >
    </footer>
    <p v-if="record.local_only" class="compatibility-note">This result is available in this tab. The service did not return a saved result reference; export it before leaving.</p>
    <p v-if="actionError" class="result-failure" role="alert">
      {{ actionError }}
    </p>
  </article>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useLiveBlast } from "@/utils/useLiveBlast";
import { isRunningResult, resultStatusLabel } from "@/utils/blastStatus";
import { useRouter } from "vue-router";
import ResultInputs from "./ResultInputs.vue";
import BlastResult from './BlastResult.vue';
import ResultInsights from "./ResultInsights.vue";
import PythonResult from './PythonResult.vue';
import EnzymeInfoResult from './EnzymeInfoResult.vue';
import McsaResult from './McsaResult.vue';
import EnzymePairResult from './EnzymePairResult.vue';
import {enzymePairs} from '@/utils/enzymePairs';
import ResultPreviewDialog from './ResultPreviewDialog.vue';
import RetentionNotice from './RetentionNotice.vue';
import { resultExpiry } from '@/utils/retention';
import { toolById } from "@/config/tools";
import { toolState } from "@/utils/toolRuns";
import ProteinViewer from "./ProteinViewer.vue";
import ScientificData from "./ScientificData.vue";
import {
  unpackResult,
  proteinPanels,
  siteRows,
  proteinSequence,
  resultMetrics,
  evidenceLabel,
  markdownText,
  resultReference,
  aminoAcidComposition,
} from "@/utils/resultData";
import { renderMarkdown } from "@/utils/markdown";
import { downloadData } from "@/utils/workspace";
import { copyToClipboard } from "@/utils/clipboard";
function exportResult() { downloadData(record.value, `enzymind-${record.value.tool}-${record.value.id.slice(0,8)}.json`); }
const props = defineProps({
  record: { type: Object, required: true },
  standalone: Boolean,
  embedded: Boolean,
});
const emit = defineEmits(["reference", "attach", "updated"]);
const {record, pollError, checking, refresh} = useLiveBlast(() => props.record, value => emit("updated", value));
const pending = computed(() => isRunningResult(record.value));
const router = useRouter(),
  copied = ref(false),
  rawOpen = ref(false),
  actionError = ref("");
const data = computed(() => record.value.tool === 'python' ? record.value.payload : unpackResult(record.value.payload));
const pairs = computed(() => enzymePairs(record.value));
const sequenceReport = computed(() => {
  if (record.value.tool !== "sequence" || typeof data.value.value !== "string")
    return "";
  return (data.value.value.match(/.{1,50}/g) || [])
    .map(
      (row, index) =>
        `${String(index * 50 + 1).padStart(5)}  ${row.match(/.{1,10}/g).join(" ")}`,
    )
    .join("\n");
});
const detailData = computed(() =>
  Object.fromEntries(
    Object.entries(data.value).filter(
      ([key, value]) => {
        if (['partial', 'warnings', 'unavailable_sections'].includes(key)) return false;
        if (key === 'source' && (data.value.partial || data.value.source?.method === 'uniprot_cache')) return false;
        if (data.value.partial && (data.value.unavailable_sections || []).includes(key)) return false;
        if (record.value.tool === 'kinetics') {
          // The accession is already in Submitted inputs; empty service fields
          // remain available in the collapsed complete result data.
          if (key === 'uniprot_id' && value === record.value.inputs?.query) return false;
          if (key !== 'km' && (value == null || value === '' ||
              (Array.isArray(value) && !value.length))) return false;
        }
        return !(
          ["data", "result"].includes(key) &&
          value &&
          typeof value === "object" &&
          !Array.isArray(value)
        );
      },
    ),
  ),
);
const composition = computed(() =>
  record.value.tool === "parameters"
    ? aminoAcidComposition(record.value.payload)
    : [],
);
const panels = computed(() => record.value.tool === 'python' ? [] : proteinPanels(record.value.payload));
const sites = computed(() => panels.value.flatMap(siteRows));
const metrics = computed(() => pending.value || record.value.tool === 'python' ? [] : resultMetrics(record.value));
const markdown = computed(() => record.value.tool === 'python' ? '' : markdownText(record.value.payload));
const failure = computed(
  () =>
    data.value.error ||
    (record.value.status === "failed"
      ? markdown.value || "The analysis did not complete."
      : ""),
);
const blastResult = computed(() => record.value.tool === 'blast' && !pending.value && !failure.value &&
  (Array.isArray(data.value.alignments) || data.value.num_results === 0));
const sourceName = computed(
  () =>
    (typeof data.value.source === "string" ? data.value.source : data.value.source?.name) || (record.value.tool.startsWith("mcsa-")
      ? "Mechanism and Catalytic Site Atlas (M-CSA)"
      : {
          "active-sites": "EasIFA",
          structure: "ESMFold / structure service",
          blast: "NCBI BLAST",
          kcat: "EITLEM",
          km: "EITLEM",
          python: "Python sandbox · code calculation",
        }[record.value.tool]) ||
    (record.value.evidence_type === "Database annotation"
      ? "UniProt / linked database records"
      : "EnzyMind analysis service"),
);
function formatMetric(value) {
  return typeof value === "number"
    ? (value !== 0 && (Math.abs(value) < 0.001 || Math.abs(value) >= 1e7) ? value.toExponential(5) : value.toLocaleString('en-US', { maximumSignificantDigits: 8 }))
    : value;
}
function reuseInputs() {
  const tool=toolById[record.value.tool], state=toolState(tool.id), input=record.value.inputs;
  if(state.running){actionError.value='This tool has a running analysis. Wait before replacing its input.';return;}
  state.protein={text:input.uniprot_id || input.enzyme_query || input.aa_sequence || (tool.protein!==false?input.query:'') || '',method:input.enzyme_input_type || input.input_type || 'auto',selected:'',filename:''};
  state.smiles=input.smiles || input.rxn_smiles || (tool.protein===false?input.query:'') || '';
  state.maxHits=input.max_results || 3;state.database=input.database || 'nr';state.error='';
  router.push(tool.path);
}
function exportMetrics(){const q=v=>`"${String(v??'').replaceAll('"','""')}"`;downloadData([['Metric','Value','Unit'],...metrics.value.map(m=>[m.label,m.value,m.unit])].map(r=>r.map(q).join(',')).join('\n'),'enzymind-metrics.csv','text/csv');}
function askAgent() {
  emit("attach", record.value);
  if (!props.embedded)
    router.push({ path: "/agent", query: { reference: record.value.id } });
}
function followReference(event) {
  const link = event.target.closest("a");
  if (!link && !window.getSelection()?.toString()) {
    const wrapper = event.target.closest('.markdown-table-preview');
    const table = wrapper?.querySelector('table');
    if (table) {
      // Read rendered cell text, never copy tool-provided HTML into the dialog.
      const cells = row => [...row.cells].map(cell => cell.textContent);
      expandedMarkdown.value = { trigger: wrapper.querySelector('button'), headings: [...table.tHead?.rows || []].flatMap(cells), rows: [...table.tBodies].flatMap(body => [...body.rows].map(cells)) };
      return;
    }
  }
  const id = link && resultReference(link.href);
  if (id) {
    event.preventDefault();
    emit("reference", id);
    if (!props.embedded) router.push(`/results/${id}`);
  }
}
const expandedMarkdown = ref(null);
watch(() => [props.record.id, markdown.value], () => { expandedMarkdown.value = null; });
async function copyLink() {
  try {
    if (
      !(await copyToClipboard(
        `${location.origin}/enzymind/results/${record.value.id}`,
      ))
    )
      throw new Error("Copy failed");
    copied.value = true;
    setTimeout(() => (copied.value = false), 2000);
  } catch {
    actionError.value =
      "Could not copy this link. Open the result and copy its address.";
  }
}
function exportSites() {
  const escape = (v) => `"${String(v ?? "").replaceAll('"', '""')}"`;
  const rows = [
    ["position", "residue", "chain", "insertion_code", "site_type", "score"],
    ...sites.value.map((s) => [
      s.position,
      s.residue,
      s.chain,
      s.icode,
      s.type,
      s.confidence,
    ]),
  ];
  downloadData(
    rows.map((r) => r.map(escape).join(",")).join("\n"),
    "enzymind-residues.csv",
    "text/csv",
  );
}
</script>

<style scoped>
.annotation-notice { margin: 18px 0; padding: 16px 18px; border: 1px solid var(--color-border); border-radius: 12px; background: var(--color-primary-light); font-size: 13px; line-height: 1.7; }
.annotation-warning { border-color: #e8ce92; background: #fffaf0; color: #70521d; }
.annotation-notice p { margin: 6px 0; }
.annotation-notice small { display: block; color: var(--color-text-secondary); }
.reported-kinetics { margin: 20px 0; }
.reported-kinetics :deep(details) {
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--color-border);
}
.reported-kinetics :deep(summary) {
  padding: 14px 16px;
  color: var(--color-text);
  text-transform: none;
}
.reported-kinetics :deep(summary span) {
  float: right;
  font-size: 11px;
  color: var(--color-text-secondary);
}
.reported-kinetics :deep(.data-table-scroll) { border-top: 1px solid var(--color-border); }
.reported-kinetics :deep(th), .reported-kinetics :deep(td) { padding: 11px 16px; }
.reported-kinetics :deep(th) {
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-secondary);
  z-index: 1;
}
.reported-kinetics :deep(tbody tr:nth-child(even)) { background: #f8fafc; }
.reported-kinetics :deep(td.numeric-value) {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  color: var(--color-text);
  white-space: nowrap;
}
.calculation-source { font-size: 12px; line-height: 1.6; color: var(--color-text-secondary); margin: 14px 0; }
.blast-pending{padding:20px;margin:18px 0;border:1px solid var(--color-border);border-left:3px solid var(--color-primary);border-radius:var(--radius-md);background:var(--color-primary-light);font-size:13px;line-height:1.7;overflow-wrap:anywhere}.blast-pending p{margin:8px 0}.blast-pending dl{display:grid;grid-template-columns:130px minmax(0,1fr);gap:6px;margin:12px 0}.blast-pending dd{margin:0}.blast-pending small{display:block;margin-top:10px;color:var(--color-text-secondary)}.blast-pending-actions{display:flex;gap:16px;flex-wrap:wrap;align-items:center}.blast-pending button{border:1px solid var(--color-primary);background:white;color:var(--color-primary);padding:8px 12px;border-radius:6px;cursor:pointer}.blast-pending a{color:var(--color-primary)}

.sequence-report {
  margin: 24px 0;
  padding: 18px;
  background: var(--color-primary-light);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}
.sequence-report h4 {
  font-size: 15px;
}
.sequence-report p {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 5px 0 14px;
}
.sequence-report pre {
  font: 12px/2 var(--font-mono);
  overflow-x: auto;
  white-space: pre;
}
.composition-section {
  margin: 22px 0;
}
.composition-section h4 {
  font-size: 14px;
  margin-bottom: 12px;
}
.composition-section p {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-top: 8px;
}
.composition-scroll {
  max-height: 340px;
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}
.composition-table {
  border-collapse: collapse;
  width: 100%;
  font-size: 12px;
}
.composition-table th {
  background: var(--color-background-alt);
  position: sticky;
  top: 0;
  z-index: 1;
  font-weight: 500;
}
.composition-table th,
.composition-table td {
  text-align: left;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-background-alt);
}
.composition-table td:last-child {
  width: 50%;
  position: relative;
}
.composition-table strong {
  display: inline-block;
  min-width: 25px;
  color: var(--color-primary);
}
.composition-value {
  position: relative;
  z-index: 1;
}
.composition-bar {
  position: absolute;
  left: 0;
  top: 5px;
  bottom: 5px;
  background: var(--color-primary-light);
  border-radius: 3px;
}
.compatibility-note {
  background: var(--color-warning-light);
  border: 1px solid var(--color-border);
  color: var(--color-warning);
  border-radius: var(--radius-md);
  padding: 12px;
  font-size: 12px;
  line-height: 1.6;
}

.research-result {
  color: var(--color-text);
  min-width: 0;
}
.research-result-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}
.research-result-header h3 {
  font-size: 21px;
  letter-spacing: -0.025em;
  margin: 5px 0;
}
.eyebrow {
  text-transform: uppercase;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.09em;
  color: var(--color-text-secondary);
}
.eyebrow span {
  margin: 0 7px;
  color: var(--color-text-muted);
}
.result-state {
  background: var(--color-primary-light);
  color: var(--color-success);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 11px;
  padding: 4px 9px;
}
.failed-result .result-state {
  background: var(--color-background-alt);
  color: var(--color-error);
  border-color: var(--color-border);
}
.result-meta {
  display: flex;
  gap: 16px;
  font-size: 11px;
  color: var(--color-text-muted);
  margin: 9px 0 20px;
}
.result-meta code {
  margin-left: auto;
}
.result-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin: 18px 0;
}
.result-metrics > div {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 16px;
  background: var(--color-surface);
}
.result-metrics span {
  display: block;
  color: var(--color-text-muted);
  font-size: 12px;
}
.result-metrics strong {
  display: block;
  font-size: 25px;
  font-weight: 600;
  margin-top: 5px;
  overflow-wrap: anywhere;
}
.result-metrics small {
  font-size: 13px;
  font-weight: 400;
}
.result-failure {
  background: var(--color-error-light);
  color: var(--color-error);
  padding: 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
}
.result-details {
  border-top: 1px solid var(--color-border);
  padding: 12px 0;
  margin-top: 14px;
  font-size: 12px;
}
.result-details summary {
  cursor: pointer;
  color: var(--color-text-secondary);
}
.result-details pre {
  max-height: 340px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--color-background-alt);
  padding: 16px;
  border-radius: var(--radius-md);
  margin: 12px 0;
  font-size: 11px;
}
.result-details dl,
.structured-fields dl {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr);
  gap: 10px;
  padding: 10px 0;
}
.result-details dt,
.structured-fields dt {
  color: var(--color-text-muted);
  text-transform: capitalize;
}
.result-details dd,
.structured-fields dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.research-result-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  border-top: 1px solid var(--color-border);
  padding-top: 17px;
  margin-top: 8px;
  align-items: center;
}
.research-result-actions button,
.research-result-actions a {
  border: 1px solid var(--color-border);
  padding: 9px 12px;
  font-size: 12px;
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  background: white;
  cursor: pointer;
  text-decoration: none;
}
.research-result-actions .primary-action {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
}
.primary-action span {
  margin-left: 8px;
}
.result-details p {
  font-size: 11px;
  color: var(--color-text-muted);
}
.research-markdown {
  font-size: 14px;
  line-height: 1.8;
  overflow-x: auto;
  overflow-wrap: anywhere;
}
.research-markdown :deep(table) {
  border-collapse: collapse;
  width: 100%;
  font-size: 12px;
  margin: 16px 0;
}
.research-markdown :deep(.markdown-table-preview){cursor:zoom-in;}
.research-markdown :deep(.markdown-table-expand){display:block;margin:10px 0 0 auto;padding:6px 10px;border:1px solid #dbe4f2;border-radius:6px;background:#f8fafc;color:#45628c;font:500 11px var(--font-family);cursor:pointer;}
.research-markdown :deep(.markdown-table-expand:focus-visible){outline:2px solid var(--color-primary);outline-offset:2px;}
.research-markdown :deep(th),
.research-markdown :deep(td) {
  text-align: left;
  padding: 9px;
  border-bottom: 1px solid var(--color-border);
}
.research-markdown :deep(th) {
  background: var(--color-background-alt);
}
.research-markdown :deep(a) {
  color: var(--color-primary);
  text-decoration: underline;
}
.research-markdown :deep(p) {
  margin: 10px 0;
}
.research-markdown :deep(ul),
.research-markdown :deep(ol) {
  padding-left: 24px;
}
.muted {
  font-size: 13px;
  color: var(--color-text-muted);
}
button:focus-visible,
a:focus-visible,
summary:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 3px;
}
</style>
