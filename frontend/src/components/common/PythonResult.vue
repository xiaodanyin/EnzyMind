<template>
  <section class="python-result" aria-label="Python analysis result">
    <div class="execution-bar">
      <span class="execution-status" :class="{ success: payload.execution_status === 'completed', failed: record.status === 'failed' }">
        <span class="status-dot" aria-hidden="true"></span>{{ statusLabel }}
      </span>
      <span class="run-stat">{{ (payload.duration || 0).toFixed(2) }} s</span>
      <span v-if="payload.versions?.python" class="run-stat">Python {{ payload.versions.python.split(' ')[0] }}</span>
      <span v-if="files.length" class="file-count">{{ files.length }} {{ files.length === 1 ? 'file' : 'files' }}</span>
    </div>

    <section v-if="files.length" class="generated-files" aria-label="Generated files">
      <div class="section-heading"><h4>Figures &amp; files</h4><span>Saved with this analysis</span></div>
      <details v-for="file in files" :key="file.id" class="python-file" :open="expanded[file.id]" @toggle="toggleFile(file, $event)">
        <summary class="file-heading">
          <span class="file-type" :class="{ figure: file.mime === 'image/png', table: file.mime === 'text/csv' }">{{ fileType(file) }}</span>
          <span class="file-title"><strong>{{ file.name }}</strong><span>{{ (file.size / 1024).toFixed(1) }} KiB</span></span>
          <button type="button" class="download-button" :disabled="loading[file.id]" :aria-label="'Download ' + file.name" @click.stop.prevent="download(file)">
            <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M10 3v9m-3-3 3 3 3-3M4 13v3h12v-3" /></svg><span>Download</span>
          </button>
          <span class="disclosure-label">{{ expanded[file.id] ? 'Hide' : 'Preview' }}</span><span class="chevron" aria-hidden="true"></span>
        </summary>
        <div class="file-body" :aria-busy="Boolean(loading[file.id])">
          <p v-if="loading[file.id] && !previews[file.id]" class="preview-loading" role="status"><span class="loading-dot" aria-hidden="true"></span>Loading preview…</p>
          <div v-if="errors[file.id]" class="preview-error" role="alert"><p>{{ errors[file.id] }}</p><button type="button" :disabled="loading[file.id]" @click="preview(file)">Retry preview</button></div>
          <ResultPreview v-if="previews[file.id]?.url" :title="file.name" :image-src="previews[file.id].url">
            <figure class="figure-preview"><img :src="previews[file.id].url" :alt="file.name" @error="imageFailed(file)" /></figure>
          </ResultPreview>
          <template v-else-if="previews[file.id]?.rows">
            <ResultPreview v-if="previews[file.id].rows.length" :title="file.name" note="Preview limited to 100 data rows and 30 columns. Download the CSV for complete data.">
            <div class="csv-preview" tabindex="0" :aria-label="'Table preview: ' + file.name">
              <table><thead><tr><th class="row-number" scope="col"><span class="sr-only">Row</span>#</th><th v-for="(cell, j) in previews[file.id].rows[0]" :key="j" scope="col">{{ cell || 'Column ' + (j + 1) }}</th></tr></thead>
                <tbody><tr v-for="(row, i) in previews[file.id].rows.slice(1)" :key="i"><th class="row-number" scope="row">{{ i + 1 }}</th><td v-for="(cell, j) in row" :key="j" :class="{ numeric: isNumeric(cell) }"><span class="cell-value" :title="cell">{{ cell }}</span></td></tr></tbody>
              </table>
            </div>
            </ResultPreview>
            <p v-else class="empty-preview">This table is empty.</p>
            <p class="preview-note">Showing {{ Math.max(0, previews[file.id].rows.length - 1) }} data rows · Preview limited to 100 rows and 30 columns. Download the full table.</p>
          </template>
          <pre v-else-if="previews[file.id]?.text !== undefined" class="text-preview" tabindex="0">{{ previews[file.id].text }}</pre>
        </div>
      </details>
    </section>

    <details v-if="payload.result !== undefined && payload.result !== null" class="result-panel computed-values" open>
      <summary><span>Computed values</span><span class="summary-meta">JSON result</span><span class="chevron" aria-hidden="true"></span></summary>
      <div class="panel-content"><ScientificData :value="jsonPreview(payload.result)" /><p class="preview-note">Preview limited to 100 rows. Export JSON for complete values.</p></div>
    </details>

    <details v-if="record.inputs?.code" class="result-panel code-panel" @toggle="codeOpen = $event.target.open">
      <summary><span>Analysis code</span><span class="summary-meta">Python · {{ codeLineCount }} lines</span><span class="chevron" aria-hidden="true"></span></summary>
      <PythonCode v-if="codeOpen" :code="record.inputs.code" />
    </details>

    <details v-if="payload.stdout || payload.stderr" class="result-panel execution-output" :open="Boolean(payload.stderr)">
      <summary><span>Execution output</span><span class="summary-meta">{{ payload.stderr ? 'Includes stderr' : 'stdout' }}</span><span class="chevron" aria-hidden="true"></span></summary>
      <div class="panel-content output-content">
        <div v-if="payload.stdout"><p class="output-label">Standard output</p><pre tabindex="0">{{ payload.stdout }}</pre></div>
        <div v-if="payload.stderr" class="stderr"><p class="output-label">Standard error</p><pre tabindex="0">{{ payload.stderr }}</pre></div>
      </div>
    </details>

    <details class="result-panel environment-panel">
      <summary><span>Environment</span><span class="summary-meta">Runtime &amp; libraries</span><span class="chevron" aria-hidden="true"></span></summary>
      <div class="panel-content">
        <dl class="library-versions"><div v-for="(version, name) in payload.versions || {}" :key="name"><dt>{{ name }}</dt><dd>{{ version }}</dd></div></dl>
        <p class="image-digest"><span>Image digest</span><code>{{ payload.image_digest || 'Unavailable' }}</code></p>
      </div>
    </details>
  </section>
</template>

<script setup>
import { computed, reactive, ref, onBeforeUnmount, watch } from 'vue';
import ScientificData from './ScientificData.vue';
import PythonCode from './PythonCode.vue';
import ResultPreview from './ResultPreview.vue';
import { workspaceFetch } from '@/utils/workspace';
import { csvPreview, jsonPreview } from '@/utils/pythonFiles';

const props = defineProps({ record: { type: Object, required: true } });
const payload = computed(() => props.record.payload || {});
const priority = file => file.mime === 'image/png' ? 0 : file.mime === 'text/csv' ? 1 : 2;
const files = computed(() => [...(payload.value.files || [])].sort((a, b) => priority(a) - priority(b)));
const statusLabel = computed(() => ({ completed: 'Completed', execution_error: 'Execution failed', timeout: 'Timed out', cancelled: 'Cancelled', running: 'Running' }[payload.value.execution_status] || (payload.value.execution_status || props.record.status || 'Pending').replaceAll('_', ' ')));
const codeLineCount = computed(() => (props.record.inputs?.code || '').split('\n').length);
const codeOpen = ref(false);
const previews = reactive({}), errors = reactive({}), loading = reactive({}), expanded = reactive({});
const blobs = new Map(), controllers = new Map(), urls = new Set();
let generation = 0;
const fileType = file => ({ 'image/png': 'PNG', 'text/csv': 'CSV', 'application/json': 'JSON', 'text/plain': 'TXT' }[file.mime] || 'FILE');
const isNumeric = value => /^[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?$/.test(value.trim());

function discard(id) {
  controllers.get(id)?.abort(); controllers.delete(id); blobs.delete(id);
  if (previews[id]?.url) { URL.revokeObjectURL(previews[id].url); urls.delete(previews[id].url); }
  for (const state of [previews, errors, loading, expanded]) delete state[id];
}
function reset() {
  generation++;
  for (const controller of controllers.values()) controller.abort();
  controllers.clear(); blobs.clear();
  for (const url of urls) URL.revokeObjectURL(url);
  urls.clear();
  for (const state of [previews, errors, loading, expanded]) for (const key of Object.keys(state)) delete state[key];
}
watch(() => [props.record.id, payload.value.files], ([id], previous) => {
  if (!previous || previous[0] !== id) reset();
  const currentIds = new Set(files.value.map(file => file.id));
  for (const key of Object.keys(expanded)) if (!currentIds.has(key)) discard(key);
  for (const file of files.value) {
    if (file.id in expanded) continue;
    expanded[file.id] = ['image/png', 'text/csv'].includes(file.mime);
    if (expanded[file.id]) preview(file);
  }
}, { immediate: true, deep: true });
onBeforeUnmount(reset);

async function load(file, action) {
  if (loading[file.id]) return;
  const current = generation, controller = new AbortController();
  const isCurrent = () => current === generation && files.value.some(item => item.id === file.id);
  loading[file.id] = true; delete errors[file.id]; controllers.set(file.id, controller);
  try {
    let blob = blobs.get(file.id);
    if (!blob) {
      // Use authenticated IDs, never a URL supplied in scientific output.
      const response = await workspaceFetch('/results/' + encodeURIComponent(props.record.id) + '/files/' + encodeURIComponent(file.id), { raw: true, signal: controller.signal });
      blob = await response.blob();
      if (!isCurrent()) return;
      blobs.set(file.id, blob);
    }
    if (isCurrent()) await action(blob, isCurrent);
  } catch (error) {
    if (isCurrent() && error.name !== 'AbortError') { errors[file.id] = error.message; expanded[file.id] = true; }
  } finally {
    if (isCurrent()) { loading[file.id] = false; controllers.delete(file.id); }
  }
}
function toggleFile(file, event) {
  expanded[file.id] = event.target.open;
  if (event.target.open && !errors[file.id]) preview(file);
}
function preview(file) {
  if (previews[file.id]) return;
  return load(file, async (blob, isCurrent) => {
    if (file.mime === 'image/png') {
      if (blob.type !== 'image/png') { blobs.delete(file.id); throw new Error('This file could not be displayed as a PNG image.'); }
      const url = URL.createObjectURL(blob); urls.add(url); previews[file.id] = { url };
    } else {
      let text = await blob.text();
      if (!isCurrent()) return;
      if (file.mime === 'application/json') {
        try { text = JSON.stringify(JSON.parse(text), null, 2); } catch { /* Keep invalid JSON as plain text. */ }
      }
      previews[file.id] = file.mime === 'text/csv' ? { rows: csvPreview(text) } : { text: text.slice(0, 32768) + (text.length > 32768 ? '\n[Preview truncated]' : '') };
    }
  });
}
function imageFailed(file) {
  if (previews[file.id]?.url) { URL.revokeObjectURL(previews[file.id].url); urls.delete(previews[file.id].url); }
  delete previews[file.id]; blobs.delete(file.id);
  errors[file.id] = 'The image could not be displayed. Retry the preview or download the file.';
}
function download(file) {
  return load(file, blob => {
    const url = URL.createObjectURL(blob); urls.add(url);
    const link = document.createElement('a'); link.href = url; link.download = file.name; link.click();
    setTimeout(() => { URL.revokeObjectURL(url); urls.delete(url); }, 1000);
  });
}
</script>

<style scoped>
.python-result{display:grid;gap:16px;margin:22px 0;font-size:13px;min-width:0;--preview-muted:#64748b;}
.execution-bar{display:flex;align-items:center;flex-wrap:wrap;gap:10px 16px;}.execution-status{display:inline-flex;align-items:center;gap:7px;padding:6px 10px;border-radius:6px;background:var(--color-background-alt);font-size:12px;font-weight:600;text-transform:capitalize;}.execution-status.success{background:var(--color-success-light);color:var(--color-success-dark);}.execution-status.failed{background:var(--color-error-light);color:var(--color-error);}.status-dot{width:6px;height:6px;border-radius:50%;background:currentColor;}.run-stat,.file-count{font:11px var(--font-mono);color:var(--preview-muted);}.file-count{margin-left:auto;}
.generated-files{display:grid;gap:14px;min-width:0;}.section-heading{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin:10px 0 0;}.section-heading h4{font-size:15px;letter-spacing:-.2px;margin:0;color:var(--color-text);}.section-heading>span{font-size:11px;color:var(--preview-muted);}
.result-panel,.python-file{border:1px solid var(--color-border);border-radius:12px;background:var(--color-surface);min-width:0;overflow:hidden;}.python-file{box-shadow:0 2px 8px #0f172a04;}
summary{display:flex;align-items:center;gap:12px;padding:15px 18px;cursor:pointer;list-style:none;font-weight:600;color:var(--color-text);}.result-panel>summary{font-size:13px;}summary::-webkit-details-marker{display:none;}summary:hover{background:#f8fafc;}summary:focus-visible,button:focus-visible,.csv-preview:focus-visible,pre:focus-visible{outline:2px solid var(--color-primary);outline-offset:-3px;}.summary-meta{margin-left:auto;font:11px var(--font-mono);color:var(--preview-muted);}.chevron{width:7px;height:7px;flex-shrink:0;border-right:1.5px solid var(--preview-muted);border-bottom:1.5px solid var(--preview-muted);transform:rotate(45deg);margin:0 2px 4px 6px;}details[open]>summary .chevron{transform:rotate(225deg);margin-top:5px;margin-bottom:0;}details[open]>summary{border-bottom:1px solid var(--color-border);}
.file-type{display:grid;place-items:center;width:42px;height:38px;flex-shrink:0;background:var(--color-background-alt);color:var(--color-text-secondary);border:1px solid var(--color-border);border-radius:8px;font:600 10px var(--font-mono);letter-spacing:.5px;}.file-type.figure{color:#1d4ed8;background:#eff6ff;border-color:#dbeafe;}.file-type.table{color:#047857;background:#ecfdf5;border-color:#d1fae5;}.file-title{display:grid;gap:4px;min-width:0;margin-right:auto;}.file-title strong{font-size:12px;font-weight:600;overflow-wrap:anywhere;}.file-title>span{color:var(--preview-muted);font:10px var(--font-mono);}.disclosure-label{font-size:11px;color:var(--preview-muted);font-weight:400;}
button{display:inline-flex;align-items:center;justify-content:center;gap:6px;cursor:pointer;background:var(--color-surface);border:1px solid var(--color-border);padding:7px 10px;border-radius:6px;color:var(--color-text-secondary);font:500 11px var(--font-family);white-space:nowrap;}button:hover{background:var(--color-primary-light);border-color:#bfdbfe;color:var(--color-primary);}button:disabled{opacity:.5;cursor:wait;}button svg{height:16px;width:16px;stroke:currentColor;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round;}
.file-body{min-width:0;}.figure-preview{display:flex;justify-content:center;align-items:center;margin:0;padding:20px;background:#f8fafc;}.figure-preview img{display:block;max-width:100%;max-height:640px;height:auto;object-fit:contain;border-radius:4px;background:white;}.csv-preview{max-height:400px;overflow:auto;}table{border-collapse:separate;border-spacing:0;width:100%;text-align:left;font-size:12px;line-height:1.6;}thead th{position:sticky;top:0;z-index:1;background:#f1f5f9;font-size:11px;font-weight:600;color:#475569;}th,td{border-bottom:1px solid #e8edf3;padding:10px 16px;max-width:320px;min-width:100px;overflow-wrap:anywhere;white-space:pre-wrap;vertical-align:top;}tbody tr:nth-child(even){background:#f8fafc;}tbody tr:hover{background:#eff6ff;}tbody tr:last-child>*{border-bottom:0;}td.numeric{font-family:var(--font-mono);font-variant-numeric:tabular-nums;text-align:right;}.row-number{color:var(--preview-muted);font:10px/1.9 var(--font-mono);text-align:right;min-width:42px;width:42px;padding-right:10px;font-weight:400;}
.preview-note{margin:0;padding:10px 16px;border-top:1px solid var(--color-border);background:#f8fafc;color:var(--preview-muted);font-size:11px;line-height:1.6;}.panel-content{padding:16px 18px;}.panel-content>.preview-note{margin:14px -18px -16px;}.text-preview,pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;max-height:360px;overflow:auto;font:12px/1.8 var(--font-mono);}.text-preview{padding:16px 18px;background:#f8fafc;}.output-content{display:grid;gap:16px;}.output-content pre{padding:12px 14px;background:#f1f5f9;border:1px solid var(--color-border);border-radius:8px;color:#334155;}.output-label{margin:0 0 8px;text-transform:uppercase;letter-spacing:.8px;font-size:10px;font-weight:600;color:var(--preview-muted);}.stderr pre{background:#fff7f7;border-color:#fecaca;color:#b91c1c;}.stderr .output-label{color:#b91c1c;}
.preview-loading,.empty-preview{display:flex;align-items:center;gap:8px;padding:24px 18px;margin:0;color:var(--preview-muted);font-size:12px;}.loading-dot{width:7px;height:7px;background:var(--color-primary);border-radius:50%;}.preview-error{padding:16px 18px;background:#fff7f7;color:#b91c1c;}.preview-error p{margin:0 0 10px;line-height:1.6;}
.library-versions{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin:0;}.library-versions dt{font-size:11px;color:var(--preview-muted);margin-bottom:4px;}.library-versions dd{font:12px/1.6 var(--font-mono);margin:0;overflow-wrap:anywhere;}.image-digest{display:grid;gap:6px;padding-top:14px;margin:18px 0 0;border-top:1px solid var(--color-border);}.image-digest>span{font-size:11px;color:var(--preview-muted);}.image-digest code{font:10px/1.7 var(--font-mono);overflow-wrap:anywhere;}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap;}
.csv-preview table{width:max-content;min-width:100%;}.csv-preview th,.csv-preview td{white-space:pre;overflow-wrap:normal;}.cell-value{display:block;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:pre;}
.computed-values :deep(.scientific-data table){font-variant-numeric:tabular-nums;}.computed-values :deep(.scientific-data table tbody tr:nth-child(even)){background:#f8fafc;}
@media(max-width:600px){.python-result{gap:12px;}.file-heading{gap:9px;padding:12px;}.file-type{width:34px;height:34px;font-size:9px;}.disclosure-label,.download-button>span,.section-heading>span{display:none;}.download-button{padding:7px;}.file-title strong{font-size:11px;}.figure-preview{padding:10px;}summary{padding:13px 12px;gap:8px;}.summary-meta{font-size:10px;}.panel-content{padding:14px 12px;}.panel-content>.preview-note{margin:12px -12px -14px;}th,td{padding:9px 12px;}.code-panel .summary-meta{font-size:9px;}.execution-bar{gap:8px 12px;}}
</style>
