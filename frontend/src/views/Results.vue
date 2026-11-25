<template>
  <div class="results-page container">
    <header class="results-page-header">
      <div>
        <span class="eyebrow">ENZYMIND / RESEARCH RECORDS</span>
        <h1>{{ route.params.id ? "Analysis result" : "Your results" }}</h1>
        <p>
          Inspect the evidence, explore a protein, and continue your research.
        </p>
      </div>
      <div class="results-header-actions"><GuideButton /><router-link to="/agent">Open workspace ↗</router-link></div>
    </header>
    <RetentionNotice v-if="!route.params.id" />
    <div v-if="error" class="result-page-error" role="alert">
      {{ error }} <button @click="load">Retry</button>
      <p>
        Private results open with the workspace access key that created them.
        Restore your access file in the workspace if you changed browsers.
      </p>
    </div>
    <p v-if="loading" role="status">Loading saved research…</p>
    <template v-else-if="record"
      ><router-link to="/results" class="back-link">← All results</router-link>
      <div class="result-page-card">
        <ResearchResult :record="record" standalone @updated="record = $event" /></div
    ></template>
    <template v-else-if="!route.params.id">
      <label class="result-search"
        >Search results<input
          v-model="search"
          type="search"
          placeholder="Search by tool, protein, or result ID"
      /></label>
      <div class="result-filters"><label>Tool<select v-model="toolFilter"><option value="">All tools</option><option v-for="tool in availableTools" :key="tool">{{ tool }}</option></select></label><label>Status<select v-model="statusFilter"><option value="">All statuses</option><option value="completed">Completed</option><option value="running">Predicting structure</option><option value="failed">Failed</option><option value="submitting">Submitting</option><option value="queued">Queued at NCBI</option><option value="paused">Checks paused</option></select></label><label>Evidence<select v-model="evidenceFilter"><option value="">All evidence</option><option v-for="kind in evidenceTypes" :key="kind">{{ kind }}</option></select></label><label>Order<select v-model="sortOrder"><option value="newest">Newest first</option><option value="oldest">Oldest first</option></select></label><span role="status">{{ filtered.length }} results</span></div>
      <div v-if="!filtered.length && !error" class="empty-results">
        <h2>
          {{ search ? "No matching results" : "Your research starts here" }}
        </h2>
        <p>
          Analyses from individual tools and Agent conversations appear here
          automatically.
        </p>
        <router-link to="/agent">Start an analysis →</router-link>
      </div>
      <div class="result-library">
        <router-link
          v-for="item in filtered"
          :key="item.id"
          :to="`/results/${item.id}`"
          class="result-library-item"
          ><span class="eyebrow">{{ evidenceLabel(item) }}</span>
          <h2>{{ item.title }}</h2>
          <p>{{ inputLabel(item.inputs) }}</p>
          <ExpiryBadge :expires-at="resultExpiry(item)" />
          <div>
            <span :class="item.status">{{ resultStatusLabel(item.status) }}</span
            ><time>{{
              new Date(item.created * 1000).toLocaleDateString('en-US')
            }}</time
            ><span>↗</span>
          </div></router-link
        >
      </div>
    </template>
  </div>
</template>
<script setup>
import { ref, computed, watch, onBeforeUnmount } from "vue";
import { useRoute } from "vue-router";
import ResearchResult from "@/components/common/ResearchResult.vue";
import RetentionNotice from '@/components/common/RetentionNotice.vue';
import GuideButton from '@/components/common/GuideButton.vue';
import ExpiryBadge from '@/components/common/ExpiryBadge.vue';
import { resultExpiry } from '@/utils/retention';
import { evidenceLabel } from '@/utils/resultData';
import { workspaceFetch } from "@/utils/workspace";
import { isRunningResult, resultStatusLabel } from "@/utils/blastStatus";
const route = useRoute(),
  record = ref(null),
  results = ref([]),
  search = ref(""),
  error = ref(""),
  loading = ref(false);
let version = 0;
const toolFilter=ref(''),statusFilter=ref(''),evidenceFilter=ref(''),sortOrder=ref('newest');
const availableTools=computed(()=>[...new Set(results.value.map(r=>r.tool))].sort());
const evidenceTypes=computed(()=>[...new Set(results.value.map(evidenceLabel))]);
const filtered = computed(()=>results.value.filter(r=>(!toolFilter.value || r.tool===toolFilter.value)&&(!statusFilter.value || r.status===statusFilter.value)&&(!evidenceFilter.value || evidenceLabel(r)===evidenceFilter.value)&&JSON.stringify([r.title,r.inputs,r.id,r.tool]).toLowerCase().includes(search.value.toLowerCase())).sort((a,b)=>sortOrder.value==='newest'?b.created-a.created:a.created-b.created));
const inputLabel = (inputs) =>
  String(
    inputs?.uniprot_id ||
      inputs?.query ||
      inputs?.enzyme_query ||
      inputs?.aa_sequence ||
      "Saved analysis",
  ).slice(0, 90);
async function load() {
  const current = ++version;
  loading.value = true;
  error.value = "";
  record.value = null;
  try {
    const data = await workspaceFetch(
      route.params.id ? `/results/${route.params.id}` : "/results",
    );
    if (current !== version) return;
    if (route.params.id) record.value = data;
    else results.value = data.results;
  } catch (e) {
    if (current === version) error.value = e.message;
  } finally {
    if (current === version) loading.value = false;
  }
}
watch(() => route.params.id, load, { immediate: true });
let polling = false;
const refreshTimer = setInterval(async () => {
  if (polling || route.params.id || !results.value.some(isRunningResult)) return;
  const current = version; polling = true;
  try { const data = await workspaceFetch('/results'); if (current === version) results.value = data.results; }
  catch { /* Keep the last known library while the server reconnects. */ }
  finally { polling = false; }
}, 10000);
onBeforeUnmount(() => { version++; clearInterval(refreshTimer); });
</script>
<style scoped>
.results-header-actions{display:flex;align-items:center;gap:14px;flex-wrap:wrap;flex-shrink:0;}
.result-filters{display:flex;gap:14px;align-items:end;flex-wrap:wrap;margin:18px 0 26px;}.result-filters label{display:grid;gap:6px;font-size:12px;}.result-filters select{border:1px solid var(--color-border);padding:9px;background:white;border-radius:6px;font:inherit;max-width:200px;}.result-filters>span{font-size:12px;color:var(--color-text-muted);margin-left:auto;}

.results-page {
  padding-block: 42px 80px;
  color: var(--color-text);
}
.results-page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 25px;
  margin-bottom: 32px;
}
.eyebrow {
  font-size: 10px;
  letter-spacing: 0.12em;
  color: var(--color-text-secondary);
  font-weight: 700;
  text-transform: uppercase;
}
.results-page h1 {
  font-family: var(--font-family);
  font-size: 38px;
  font-weight: 800;
  margin: 6px 0;
}
.results-page-header p {
  font-size: 14px;
  color: var(--color-text-secondary);
}
.results-page a {
  color: var(--color-primary);
}
.result-page-card {
  padding: 28px;
  border: 1px solid var(--color-border);
  background: white;
  border-radius: var(--radius-md);
  margin-top: 20px;
}
.result-search {
  display: block;
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 22px 0;
}
.result-search input {
  display: block;
  margin-top: 7px;
  padding: 12px 14px;
  width: 100%;
  max-width: 480px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: white;
  font: inherit;
}
.result-library {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
  gap: 16px;
}
.result-library-item {
  padding: 22px;
  border: 1px solid var(--color-border);
  background: white;
  border-radius: var(--radius-md);
  text-decoration: none;
  transition: border-color 0.15s;
}
.result-library-item:hover {
  border-color: var(--color-primary);
}
.result-library-item h2 {
  font-size: 18px;
  margin: 9px 0;
}
.result-library-item p {
  font-size: 12px;
  color: var(--color-text-muted);
  overflow-wrap: anywhere;
  height: 44px;
  overflow: hidden;
}
.result-library-item > div {
  display: flex;
  gap: 15px;
  font-size: 11px;
  margin-top: 18px;
  color: var(--color-text-muted);
}
.result-library-item > div span:last-child {
  margin-left: auto;
}
.completed {
  color: var(--color-success);
}
.failed {
  color: var(--color-error);
}
.empty-results {
  text-align: center;
  padding: 80px 20px;
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}
.empty-results h2 {
  font-family: var(--font-family);
  font-size: 28px;
  font-weight: 400;
}
.empty-results p {
  font-size: 14px;
  color: var(--color-text-muted);
  margin: 15px 0;
}
.result-page-error {
  padding: 20px;
  background: var(--color-background-alt);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 14px;
}
.result-page-error p {
  font-size: 12px;
  margin-top: 12px;
}
@media (max-width: 700px) {
  .results-page {
    padding-block: 24px;
  }
  .results-page-header {
    align-items: flex-start;
    flex-direction: column;
  }
  .result-page-card {
    padding: 16px;
  }
}
</style>
