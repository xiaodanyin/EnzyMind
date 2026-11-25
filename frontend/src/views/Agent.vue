<template>
  <div ref="workspaceElement" class="agent-workspace" :class="{ 'inspector-open': inspectorOpen, 'is-resizing': dragging }" :style="layoutStyle">
    <button
      v-if="sidebarOpen"
      class="sidebar-backdrop"
      aria-label="Close conversation menu"
      @click="sidebarOpen = false"
    ></button>
    <aside
      id="agent-conversations"
      class="workspace-sidebar"
      :class="{ 'mobile-open': sidebarOpen }"
      aria-label="Research conversations"
    >
      <div class="workspace-brand">
        <span class="workspace-mark">E·</span>
        <div><strong>Research workspace</strong><span>ENZYMIND</span></div>
      </div>
      <button
        class="sidebar-close"
        @click="sidebarOpen = false"
        aria-label="Close conversation menu"
      >
        ×
      </button>
      <button class="new-conversation" @click="newConversation">
        ＋ New conversation
      </button>
      <div class="sidebar-label">
        CONVERSATIONS
        <button @click="loadSessions" aria-label="Refresh conversations">
          ↻
        </button>
      </div>
      <div class="conversation-list">
        <button
          v-for="session in sessions"
          :key="session.id"
          class="conversation-item"
          :class="{ active: session.id === sessionId }"
          @click="selectSession(session.id)"
        >
          <span>{{ session.title }}</span
          ><small>{{ formatDate(session.updated) }}</small>
        </button>
        <p v-if="!sessions.length" class="sidebar-empty">
          Your conversations will be saved here.
        </p>
      </div>
      <div class="sidebar-bottom">
        <button @click="showLibrary">
          ▤ Saved results <span>{{ library.length || "" }}</span></button
        ><router-link to="/help">Getting started ↗</router-link>
        <details>
          <summary>Workspace access</summary>
          <p>
            Results are private to this browser's workspace. Save your access
            file to restore them on another browser. Keep it private.
          </p>
          <button @click="exportAccess">Export access file</button
          ><button @click="accessInput.click()">Restore access file</button
          ><input
            ref="accessInput"
            type="file"
            accept=".json"
            hidden
            @change="importAccess"
          />
        </details>
      </div>
    </aside>
    <div class="column-resizer sidebar-resizer" role="separator" tabindex="0" aria-orientation="vertical"
      aria-label="Resize conversations panel" aria-controls="agent-conversations" :aria-valuenow="Math.round(columns.left)"
      :aria-valuemin="190" :aria-valuemax="Math.round(columns.leftMax)" :aria-valuetext="`${Math.round(columns.left)} pixels`"
      title="Drag to resize · Arrow keys to adjust · Double-click to reset"
      @pointerdown="startResize('left', $event)" @keydown="resizeKey('left', $event)" @dblclick="resetWidth('left')"><i></i></div>
    <section class="conversation-pane" aria-label="Agent conversation">
      <header class="workspace-topbar">
        <div>
          <span class="eyebrow"
            >RESEARCH /
            {{ sessionId ? sessionId.slice(0, 8) : "NEW CONVERSATION" }}</span
          >
          <h1>{{ currentTitle }}</h1>
        </div>
        <div class="topbar-actions">
          <GuideButton />
          <button v-if="turns.length" @click="toggleExamples" :aria-expanded="examplesOpen">Examples</button>
          <button
            class="mobile-new"
            @click="sidebarOpen = !sidebarOpen"
            :aria-expanded="sidebarOpen"
            aria-label="Open conversations"
          >
            ☰</button
          ><button v-if="sessionId" data-guide="agent-memory" class="memory-indicator" aria-label="Conversation memory" @click="memoryOpen = !memoryOpen" :aria-expanded="memoryOpen"
            ><i></i><span class="memory-label-full">Conversation memory</span><span class="memory-label-short">Memory</span></button
          ><button data-guide="agent-results" @click="showLibrary" :aria-expanded="inspectorOpen">
            Results <span>{{ currentResults.length }}</span></button
          ><button v-if="turns.length" @click="exportConversation">
            Export
          </button>
        </div>
      </header>
      <RetentionNotice compact class="workspace-retention">
        <button v-if="turns.length" @click="exportConversation">Download conversation</button>
        <router-link to="/results">Download saved results ↗</router-link>
      </RetentionNotice>
      <section v-if="memoryOpen && sessionId" class="memory-panel" aria-label="Conversation memory">
        <div class="memory-panel-heading"><strong>Research context</strong><span>{{ memoryStatus }}</span><button type="button" class="memory-close" aria-label="Close conversation memory" @click="memoryOpen=false">×</button></div>
        <dl><div><dt>Original exchanges</dt><dd>{{ turns.filter(t=>t.status === 'completed').length }}</dd></div><div><dt>Summarized exchanges</dt><dd>{{ (memory.summarized_count || 0) / 2 }}</dd></div><div><dt>Saved results</dt><dd>{{ currentResults.length }}</dd></div><div><dt>Last context estimate</dt><dd>{{ memory.context_tokens ? memory.context_tokens.toLocaleString('en-US') + ' tokens' : 'Not yet measured' }}</dd></div></dl>
        <p>Conversation messages remain saved for 90 days from creation. Older exchanges are summarized when needed within that period. Exact scientific values remain in linked results until their own expiry dates.</p>
        <p v-if="memory.retention_reset_at">Expired messages were removed on {{ formatDate(memory.retention_reset_at) }}. Conversation memory is rebuilt from the remaining messages.</p>
        <details v-if="memory.summary"><summary>Read saved summary · revision {{ memory.memory_revision }} · {{ memory.compression_count || 0 }} compression passes</summary><p class="memory-summary">{{ memory.summary }}</p></details>
        <p v-else>No summary is needed yet.</p>
      </section>
      <div v-if="workspaceNotice.message" class="workspace-notice" role="alert">
        {{ workspaceNotice.message }}
      </div>
      <div v-if="legacyHistory" class="workspace-notice">
        An earlier chat is stored on this browser.
        <button
          @click="downloadData(legacyHistory, 'enzymind-previous-chat.json')"
        >
          Export previous chat</button
        ><button
          @click="legacyHistory = null"
          aria-label="Dismiss previous chat notice"
        >
          ×
        </button>
      </div>
      <div ref="messageList" class="conversation-scroll" @scroll="onScroll">
        <div v-if="booting" class="loading-state" role="status">
          Opening your workspace…
        </div>
        <div v-else-if="!turns.length" class="workspace-welcome">
          <div class="welcome-kicker">
            <span aria-hidden="true">✳</span> FROM QUESTION TO EVIDENCE
          </div>
          <h2>What would you like<br />to discover?</h2>
          <p>
            Start with a protein, a reaction, or a research question.<br />EnzyMind
            connects the analysis, the evidence, and your next step.
          </p>
          <AgentExamples :has-attachments="attachments.length > 0" @use="usePrompt" @library="showLibrary" />
          <div class="workspace-how">
            <span><b>1</b> Ask a question</span><i>→</i
            ><span><b>2</b> Inspect the evidence</span><i>→</i
            ><span><b>3</b> Refine your analysis</span>
          </div>
        </div>
        <div v-else class="turn-list">
          <AgentExamples v-if="examplesOpen" :has-attachments="attachments.length > 0" @use="usePrompt" @library="showLibrary" />
          <article v-for="turn in turns" :key="turn.id" class="research-turn">
            <div class="user-turn">
              <div class="message-byline">
                YOU <time>{{ formatTime(turn.created) }}</time>
                <ExpiryBadge :expires-at="resultExpiry(turn)" />
              </div>
              <p v-if="turn.message.length < 1400">{{ turn.message }}</p>
              <details v-else>
                <summary>{{ turn.message.slice(0, 160) }}…</summary>
                <pre>{{ turn.message }}</pre>
              </details>
              <div v-if="turn.references.length" class="inline-references">
                <button
                  v-for="id in turn.references"
                  :key="id"
                  @click="inspectResult(id)"
                >
                  ▤ {{ resultTitle(id) }} ↗
                </button>
              </div>
            </div>
            <div class="assistant-turn">
              <div class="message-byline">
                <span class="assistant-mark">E·</span> ENZYMIND
                <span
                  v-if="['running', 'queued'].includes(turn.status)"
                  class="live-label"
                  >{{ turn.partial_output ? 'Streaming' : 'Working' }}</span
                >
              </div>
              <details
                v-if="toolEvents(turn).length"
                class="tool-timeline"
                :open="['running', 'queued'].includes(turn.status)"
              >
                <summary>
                  Analysis steps <span>{{ toolEvents(turn).length }}</span>
                </summary>
                <button
                  v-for="(step, i) in toolEvents(turn)"
                  :key="i"
                  :disabled="!step.result_id"
                  @click="inspectResult(step.result_id)"
                >
                  <span :class="['step-status', step.status]">{{
                    step.status === "completed"
                      ? "✓"
                      : step.status === "failed"
                        ? "!"
                        : step.status === "running"
                          ? "◌"
                          : "—"
                  }}</span
                  ><span>{{ step.label }}</span
                  ><small>{{
                    step.status === "completed"
                      ? `${step.duration.toFixed(1)} s`
                      : step.status
                  }}</small
                  ><span v-if="step.result_id">↗</span>
                </button>
              </details>
              <div
                v-if="turn.output || turn.partial_output"
                class="agent-markdown"
                :aria-busy="['queued', 'running'].includes(turn.status)"
                v-html="renderMarkdown(turn.output || turn.partial_output)"
                @click="handleCitation"
              ></div>
              <div
                v-else-if="['queued', 'running'].includes(turn.status)"
                class="working-status"
                role="status"
              >
                <span class="working-dot"></span>{{ latestStatus(turn) }}
              </div>
              <p v-if="turn.partial_output && !['queued', 'running', 'completed'].includes(turn.status)" class="partial-notice">Partial response · generation did not finish. This text was not added to conversation memory.</p>
              <p v-if="contextWarning(turn)" class="context-notice" role="status">{{ contextWarning(turn) }}</p>
              <div v-if="turn.error" class="turn-error" role="alert">
                <strong>{{
                  turn.status === "cancelled"
                    ? "Analysis stopped"
                    : "Analysis needs attention"
                }}</strong>
                <p>{{ turn.error }}</p>
                <button v-if="!running" @click="reuseTurn(turn)">
                  Use this question again
                </button>
              </div>
              <div v-if="turnResultIds(turn).length" class="answer-results">
                <span class="eyebrow">RESULTS &amp; EVIDENCE</span
                ><button
                  v-for="id in turnResultIds(turn)"
                  :key="id"
                  @click="inspectResult(id)"
                >
                  <span>▤</span><span>{{ resultTitle(id) }}</span
                  ><span>Inspect ↗</span>
                </button>
              </div>
            </div>
          </article>
        </div>
      </div>
      <div class="composer-area">
        <div v-if="error" class="composer-error" role="alert">
          {{ error }}
          <button @click="error = ''" aria-label="Dismiss error">×</button>
        </div>
        <div v-if="attachments.length || file" class="composer-attachments">
          <button
            v-for="item in attachments"
            :key="item.id"
            @click="removeAttachment(item.id)"
            :title="`Remove ${item.title}`"
          >
            ▤ {{ item.title }} <span>×</span></button
          ><button v-if="file" @click="file = null">
            FASTA · {{ file.name }} <span>×</span>
          </button>
        </div>
        <div class="agent-billing" aria-label="Daily Agent allowance">
          <span v-if="deepseekKey" class="billing-personal">Using your DeepSeek key</span>
          <span v-else-if="quota" :title="`Resets at ${quota.resets_at} (${quota.timezone}). New conversations share this allowance.`"><strong>{{ quota.remaining }} / {{ quota.limit }}</strong> free turns left today <small>· resets at midnight, {{ quota.timezone }}</small></span>
          <span v-else>{{ quotaError || 'Checking daily allowance…' }}</span>
          <button v-if="deepseekKey" type="button" @click="forgetKey">Forget key</button>
          <button v-else type="button" @click="keyDialogOpen=true">Use my DeepSeek key</button>
        </div>
        <form class="message-composer" @submit.prevent="send">
          <label class="sr-only" for="research-message">Research question</label
          ><textarea
            id="research-message"
            ref="composer"
            v-model="draft"
            rows="3"
            maxlength="24000"
            :placeholder="
              attachments.length
                ? 'Ask about the attached results…'
                : 'Ask about an enzyme, paste a UniProt ID, or describe your research goal…'
            "
            @keydown="onKeydown"
          ></textarea>
          <div class="composer-toolbar">
            <div>
              <button
                type="button"
                @click="fileInput.click()"
                :disabled="running"
              >
                ＋ Protein file</button
              ><button type="button" @click="showLibrary">
                ▤ Reference a result</button
              ><input
                ref="fileInput"
                type="file"
                accept=".fasta,.fa,.faa,.txt"
                hidden
                @change="attachFile"
              />
            </div>
            <button
              v-if="running"
              type="button"
              class="stop-button"
              @click="stop"
              :disabled="stopping"
            >
              ■ {{ stopping ? "Stopping…" : "Stop analysis" }}</button
            ><button
              v-else
              class="send-button"
              type="submit"
              :disabled="sending || !draft.trim()"
            >
              {{ sending ? "Starting…" : limitReached && !deepseekKey ? "Add DeepSeek key" : "Send question" }} <span>↑</span>
            </button>
          </div>
        </form>
        <div class="composer-footnote">
          <span>Enter to send · Shift + Enter for a new line</span
          ><span>Predictions require scientific interpretation.</span>
        </div>
      </div>
    </section>
    <DeepSeekKeyDialog v-if="keyDialogOpen" :limit="quota?.limit || 10" @close="keyDialogOpen=false" @use-key="useKey" />
    <div v-if="inspectorOpen" class="column-resizer inspector-resizer" role="separator" tabindex="0" aria-orientation="vertical"
      aria-label="Resize results panel" aria-controls="agent-results-panel" :aria-valuenow="Math.round(columns.right)"
      :aria-valuemin="320" :aria-valuemax="Math.round(columns.rightMax)" :aria-valuetext="`${Math.round(columns.right)} pixels`"
      title="Drag to resize · Arrow keys to adjust · Double-click to reset"
      @pointerdown="startResize('right', $event)" @keydown="resizeKey('right', $event)" @dblclick="resetWidth('right')"><i></i></div>
    <aside
      id="agent-results-panel"
      v-if="inspectorOpen"
      class="result-inspector"
      aria-label="Results inspector"
    >
      <header>
        <div>
          <span class="eyebrow">EVIDENCE PANEL</span>
          <h2>{{ inspected ? "Result details" : "Saved results" }}</h2>
        </div>
        <button
          @click="inspectorOpen = false"
          aria-label="Close result inspector"
        >
          ×
        </button>
      </header>
      <div class="inspector-scroll">
        <p v-if="inspecting" role="status">Loading result…</p>
        <p v-if="inspectorError" class="composer-error" role="alert">
          {{ inspectorError }}
        </p>
        <template v-if="inspected"
          ><div class="inspector-navigation">
            <button @click="inspected = null">← Result library</button
            ><button @click="attachResult(inspected)">
              ＋ Add to question
            </button>
          </div>
          <ResearchResult
            :record="inspected"
            @updated="updateInspectedResult"
            embedded
            @reference="inspectResult"
            @attach="attachResult"
        /></template>
        <template v-else
          ><label class="library-search"
            >Find a saved analysis<input
              v-model="resultSearch"
              type="search"
              placeholder="Protein, task, or result ID"
          /></label>
          <p class="library-help">
            Open a result to inspect it, or attach it to your next question.
            Results from individual tools appear here too.
          </p>
          <div class="library-tabs">
            <button
              :class="{ active: libraryScope === 'all' }"
              @click="libraryScope = 'all'"
            >
              All results</button
            ><button
              :class="{ active: libraryScope === 'conversation' }"
              @click="libraryScope = 'conversation'"
            >
              This conversation
            </button>
          </div>
          <div v-if="!filteredLibrary.length" class="inspector-empty">
            <span>▤</span><strong>No results yet</strong>
            <p>
              {{
                resultSearch
                  ? "Try a different search."
                  : "Run an analysis to build your evidence collection."
              }}
            </p>
            <router-link to="/predict/enzyme"
              >Explore analysis tools →</router-link
            >
          </div>
          <article
            v-for="item in filteredLibrary"
            :key="item.id"
            class="library-card"
          >
            <span class="eyebrow">{{ evidenceLabel(item) }}</span
            ><button class="library-card-title" @click="inspectResult(item.id)">
              {{ item.title }} ↗
            </button>
            <p>{{ inputLabel(item.inputs) }}</p>
            <ExpiryBadge :expires-at="resultExpiry(item)" />
            <footer>
              <span :class="item.status"
                >{{ item.status }} · {{ formatDate(item.created) }}</span
              ><button
                @click="attachResult(item)"
                :disabled="attachments.some((a) => a.id === item.id)"
              >
                {{
                  attachments.some((a) => a.id === item.id)
                    ? "Attached"
                    : "＋ Attach"
                }}
              </button>
            </footer>
          </article></template
        >
      </div>
    </aside>
  </div>
</template>
<script setup>
import {
  ref,
  computed,
  watch,
  nextTick,
  onMounted,
  onBeforeUnmount,
} from "vue";
import { useRoute, useRouter } from "vue-router";
import ResearchResult from "@/components/common/ResearchResult.vue";
import AgentExamples from "@/components/common/AgentExamples.vue";
import RetentionNotice from '@/components/common/RetentionNotice.vue';
import GuideButton from '@/components/common/GuideButton.vue';
import ExpiryBadge from '@/components/common/ExpiryBadge.vue';
import DeepSeekKeyDialog from '@/components/common/DeepSeekKeyDialog.vue';
import { useAgentLayout } from '@/utils/agentLayout';
import { resultExpiry } from '@/utils/retention';
import {
  workspaceFetch,
  postWorkspace,
  downloadData,
  workspaceNotice,
  exportAccess,
  restoreAccess,
  newRequestId,
  streamWorkspaceTurn,
} from "@/utils/workspace";
import { renderMarkdown } from "@/utils/markdown";
import { resultReference, evidenceLabel } from "@/utils/resultData";
const route = useRoute(),
  router = useRouter();
const sessions = ref([]),
  sessionId = ref(""),
  turns = ref([]),
  currentResults = ref([]),
  library = ref([]);
const memory = ref({}), memoryOpen = ref(false), examplesOpen = ref(false);
const quota=ref(null), quotaError=ref(''), deepseekKey=ref(''), keyDialogOpen=ref(false);
const limitReached=computed(()=>quota.value?.remaining === 0);
async function loadUsage(){
  try{const data=await workspaceFetch('/usage');if(Number.isInteger(data.limit)&&Number.isInteger(data.remaining)){quota.value=data;quotaError.value='';}}
  catch{quotaError.value='Daily allowance unavailable. Retry when sending.';}
}
function useKey(value){deepseekKey.value=value;keyDialogOpen.value=false;error.value='';composer.value?.focus();}
function forgetKey(){deepseekKey.value='';void loadUsage();}
const memoryStatus = computed(() => {
  const last = turns.value.at(-1);
  if (last && ['running','queued'].includes(last.status)) return [...(last.events || [])].reverse().find(e=>e.kind==='memory')?.data.label || 'Preparing context';
  return 'Saved on this workspace';
});
const draft = ref(""),
  attachments = ref([]),
  file = ref(null),
  error = ref(""),
  booting = ref(true),
  sending = ref(false),
  stopping = ref(false);
const composer = ref(null),
  messageList = ref(null),
  fileInput = ref(null),
  accessInput = ref(null),
  legacyHistory = ref(null);
const inspectorOpen = ref(false),
  sidebarOpen = ref(false),
  inspected = ref(null),
  inspecting = ref(false),
  inspectorError = ref(""),
  resultSearch = ref(""),
  libraryScope = ref("all");
const workspaceElement = ref(null);
const { columns, style: layoutStyle, dragging, start: startResize, key: resizeKey, reset: resetWidth } = useAgentLayout(workspaceElement, inspectorOpen);
let pollTimer,
  streamController,
  sessionVersion = 0,
  inspectVersion = 0,
  unmounted = false,
  followBottom = true,
  pendingRequest = null;
const running = computed(() =>
  turns.value.some((t) => ["running", "queued"].includes(t.status)),
);
const currentTitle = computed(
  () =>
    sessions.value.find((s) => s.id === sessionId.value)?.title ||
    "Research with EnzyMind",
);
const filteredLibrary = computed(() =>
  (libraryScope.value === "conversation"
    ? currentResults.value
    : library.value
  ).filter((r) =>
    JSON.stringify([r.title, r.inputs, r.id])
      .toLowerCase()
      .includes(resultSearch.value.toLowerCase()),
  ),
);
const formatDate = (t) =>
  new Date(t * 1000).toLocaleDateString('en-US', {
    month: "short",
    day: "numeric",
  });
const formatTime = (t) =>
  new Date(t * 1000).toLocaleTimeString('en-US', {
    hour: "2-digit",
    minute: "2-digit",
  });
const inputLabel = (input) =>
  String(
    input?.uniprot_id ||
      input?.query ||
      input?.enzyme_query ||
      input?.aa_sequence ||
      "Saved analysis",
  ).slice(0, 75);
const resultTitle = (id) =>
  [...currentResults.value, ...library.value].find((r) => r.id === id)?.title ||
  `Result ${id.slice(0, 8)}`;
function updateInspectedResult(record) {
  inspected.value = record;
  currentResults.value = currentResults.value.map(r => r.id === record.id ? {...r, status:record.status} : r);
  library.value = library.value.map(r => r.id === record.id ? {...r, status:record.status} : r);
}
function toolEvents(turn) {
  const steps = [];
  for (const event of turn.events || []) {
    if (event.kind === "tool_start")
      steps.push({
        ...event.data,
        status: ["running", "queued"].includes(turn.status)
          ? "running"
          : "interrupted",
      });
    if (event.kind === "tool_end") {
      const step = [...steps]
        .reverse()
        .find((s) => s.tool === event.data.tool && !s.result_id);
      if (step) Object.assign(step, event.data);
      else steps.push(event.data);
    }
  }
  return steps.map(step => {
    const saved = [...currentResults.value, ...library.value].find(r => r.id === step.result_id);
    return saved && ['submitting', 'queued', 'paused'].includes(step.status) ? {...step, status:saved.status} : step;
  });
}
function turnResultIds(turn) {
  return [
    ...new Set(
      (turn.events || []).flatMap((e) =>
        e.kind === "tool_end"
          ? e.data.result_id
            ? [e.data.result_id]
            : []
          : e.kind === "references"
            ? e.data.results.map((r) => r.id)
            : [],
      ),
    ),
  ];
}
const latestStatus = (turn) =>
  [...(turn.events || [])].reverse().find((e) => ["status", "memory", "tool_start", "tool_end"].includes(e.kind))?.data
    .label || "Starting analysis…";
const contextWarning = (turn) =>
  [...(turn.events || [])].reverse().find(e => e.kind === "memory" && e.data.warning)?.data.warning || "";
function rememberSession() {
  try {
    localStorage.setItem("enzymind_workspace_session_v2", sessionId.value);
  } catch {}
}
async function loadSessions() {
  try {
    sessions.value = (await workspaceFetch("/sessions")).sessions;
  } catch (e) {
    error.value = e.message;
  }
}
async function loadLibrary() {
  const data = await workspaceFetch("/results");
  library.value = data.results;
}
async function selectSession(id) {
  if (sending.value) return;
  sidebarOpen.value = false;
  const version = ++sessionVersion;
  disconnectStream();
  clearTimeout(pollTimer);
  error.value = "";
  booting.value = true;
  try {
    const data = await workspaceFetch(`/sessions/${id}`);
    if (version !== sessionVersion || unmounted) return;
    sessionId.value = id;
    memory.value = data;
    turns.value = data.turns;
    currentResults.value = data.results;
    rememberSession();
    followBottom = true;
    await scrollBottom();
    schedulePoll();
  } catch (e) {
    if (version === sessionVersion) error.value = e.message;
  } finally {
    if (version === sessionVersion) {
      booting.value = false;
      await scrollBottom();
    }
  }
}
async function newConversation() {
  if (sending.value) return;
  sidebarOpen.value = false;
  sessionVersion++;
  disconnectStream();
  clearTimeout(pollTimer);
  sessionId.value = "";
  memory.value = {};
  examplesOpen.value = false;
  turns.value = [];
  currentResults.value = [];
  attachments.value = [];
  draft.value = "";
  file.value = null;
  pendingRequest = null;
  error.value = "";
  booting.value = false;
  rememberSession();
  await nextTick();
  if (messageList.value) messageList.value.scrollTop = 0;
  composer.value?.focus({ preventScroll: true });
}
function schedulePoll() {
  clearTimeout(pollTimer);
  if (running.value && !unmounted && !streamController) void followTurn();
}
function disconnectStream() {
  streamController?.abort();
  streamController = null;
}
async function followTurn() {
  const turn = turns.value.find(t => ['queued', 'running'].includes(t.status));
  if (!turn || streamController || unmounted) return;
  const controller = new AbortController(), version = sessionVersion;
  streamController = controller;
  let finished = false;
  try {
    await streamWorkspaceTurn(turn.id, controller.signal, async (kind, data) => {
      if (version !== sessionVersion || controller.signal.aborted || unmounted) return;
      const current = turns.value.find(t => t.id === turn.id);
      if (!current) return;
      if (kind === 'snapshot' || kind === 'done') Object.assign(current, data.turn);
      if (kind === 'delta') current.partial_output = (current.partial_output || '') + data.text;
      if (kind === 'progress') Object.assign(current, data);
      if (data.results) currentResults.value = data.results;
      if (error.value.startsWith('Connection interrupted.')) error.value = '';
      if (followBottom) await scrollBottom();
      if (kind === 'done') finished = true;
    });
  } catch (e) {
    if (!controller.signal.aborted && version === sessionVersion && !unmounted)
      error.value = `Connection interrupted. Reconnecting to the saved analysis. ${e.message}`;
  } finally {
    if (streamController === controller) streamController = null;
    if (!controller.signal.aborted && version === sessionVersion && !unmounted) {
      if (finished) {
        await refreshTurn();
        await Promise.all([loadSessions(), loadLibrary(), loadUsage()]).catch(() => {});
      } else {
        // Read-only fallback and reconnect. Never replay the POST that starts work.
        pollTimer = setTimeout(refreshTurn, 1200);
      }
    }
  }
}
async function refreshTurn() {
  const version = sessionVersion,
    id = sessionId.value;
  try {
    const data = await workspaceFetch(`/sessions/${id}`);
    if (version !== sessionVersion || unmounted) return;
    const wasRunning = running.value;
    if (error.value.startsWith("Connection interrupted.")) error.value = "";
    memory.value = data;
    turns.value = data.turns;
    currentResults.value = data.results;
    if (followBottom) await scrollBottom();
    if (wasRunning && !running.value)
      await Promise.all([loadSessions(), loadLibrary(), loadUsage()]);
  } catch (e) {
    if (version === sessionVersion)
      error.value = `Connection interrupted. Reconnecting to the saved analysis. ${e.message}`;
  } finally {
    if (version === sessionVersion) schedulePoll();
  }
}
async function send() {
  if (!draft.value.trim() || sending.value || running.value || booting.value)
    return;
  sending.value = true;
  await loadUsage();
  if(limitReached.value && !deepseekKey.value){keyDialogOpen.value=true;sending.value=false;return;}
  error.value = "";
  const message =
    draft.value.trim() +
    (file.value
      ? `\n\nAttached FASTA file: ${file.value.name}\n\n${file.value.text}`
      : "");
  if (message.length > 300000) {
    error.value =
      "The question and FASTA exceed 300,000 characters. Use fewer records per analysis.";
    sending.value = false;
    return;
  }
  try {
    if (!sessionId.value) {
      const session = await postWorkspace("/sessions");
      sessionId.value = session.id;
      sessions.value.unshift(session);
      rememberSession();
    }
    const body = { message, references: attachments.value.map((r) => r.id) },
      fingerprint = JSON.stringify([sessionId.value, body]);
    if (pendingRequest?.fingerprint !== fingerprint)
      pendingRequest = { fingerprint, id: newRequestId() };
    const turn = await postWorkspace(`/sessions/${sessionId.value}/turns`, {
      ...body,
      request_id: pendingRequest.id,
    }, deepseekKey.value ? {'X-DeepSeek-API-Key': deepseekKey.value} : {});
    if (!turns.value.some((t) => t.id === turn.id)) turns.value.push(turn);
    pendingRequest = null;
    draft.value = "";
    attachments.value = [];
    file.value = null;
    followBottom = true;
    await scrollBottom();
    schedulePoll();
    await Promise.all([loadSessions(),loadUsage()]);
  } catch (e) {
    error.value = e.message;
    if(e.code==='daily_limit'){quota.value=e.quota || quota.value;keyDialogOpen.value=true;await loadUsage();}
  } finally {
    sending.value = false;
  }
}
function onKeydown(event) {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    send();
  }
}
async function stop() {
  const turn = turns.value.find((t) =>
    ["running", "queued"].includes(t.status),
  );
  if (!turn) return;
  stopping.value = true;
  try {
    await postWorkspace(`/turns/${turn.id}/cancel`);
    disconnectStream();
    await refreshTurn();
  } catch (e) {
    error.value = e.message;
  } finally {
    stopping.value = false;
  }
}
function usePrompt(text) {
  draft.value = text;
  composer.value?.focus();
}
async function toggleExamples() {
  examplesOpen.value = !examplesOpen.value;
  if (examplesOpen.value) memoryOpen.value = false;
  await nextTick();
  if (examplesOpen.value && messageList.value) messageList.value.scrollTop = 0;
}
function reuseTurn(turn) {
  draft.value = turn.message;
  // Saved messages already contain any uploaded FASTA text.
  file.value = null;
  pendingRequest = null;
  error.value = "";
  attachments.value = (turn.references || []).map((id) => ({
    id,
    title: resultTitle(id),
  }));
  composer.value?.focus();
}
async function attachFile(event) {
  const chosen = event.target.files[0];
  event.target.value = "";
  if (!chosen) return;
  if (chosen.size > 24000) {
    error.value = "Please use a FASTA file smaller than 24 KB.";
    return;
  }
  try {
    const text = await chosen.text();
    const records = text.trim().split(/^>/m).filter(Boolean);
    if (
      !text.trim().startsWith(">") ||
      records.some(
        (r) =>
          !r.includes("\n") ||
          !/^[ACDEFGHIKLMNPQRSTVWYBXZJUO\s*]+$/i.test(
            r.slice(r.indexOf("\n") + 1),
          ),
      )
    )
      throw new Error(
        "Use a valid FASTA file with a header and amino acid sequence for each protein.",
      );
    file.value = { name: chosen.name, text };
    if (!draft.value)
      draft.value = "Help me analyze the protein records in this FASTA file.";
  } catch (e) {
    error.value = e.message;
  }
}
function attachResult(record) {
  if (attachments.value.some((a) => a.id === record.id)) return;
  if (attachments.value.length >= 4) {
    error.value = "Attach up to four results per question.";
    return;
  }
  attachments.value.push({ id: record.id, title: record.title });
  composer.value?.focus();
}
function removeAttachment(id) {
  attachments.value = attachments.value.filter((r) => r.id !== id);
}
async function showLibrary() {
  sidebarOpen.value = false;
  inspectVersion++;
  inspectorOpen.value = true;
  inspected.value = null;
  inspectorError.value = "";
  try {
    await loadLibrary();
  } catch (e) {
    inspectorError.value = e.message;
  }
}
async function inspectResult(id) {
  const version = ++inspectVersion;
  inspectorOpen.value = true;
  inspecting.value = true;
  inspectorError.value = "";
  inspected.value = null;
  try {
    const record = await workspaceFetch(`/results/${id}`);
    if (version === inspectVersion) inspected.value = record;
  } catch (e) {
    if (version === inspectVersion) inspectorError.value = e.message;
  } finally {
    if (version === inspectVersion) inspecting.value = false;
  }
}
function handleCitation(event) {
  const link = event.target.closest("a");
  const id = link && resultReference(link.href);
  if (id) {
    event.preventDefault();
    inspectResult(id);
  }
}
async function attachFromRoute() {
  const id = route.query.reference;
  if (typeof id !== "string") return;
  try {
    const record = await workspaceFetch(`/results/${id}`);
    attachResult(record);
    inspected.value = record;
    inspectorOpen.value = true;
    if (!draft.value)
      draft.value =
        "Help me interpret this result and identify the next useful analysis.";
    await router.replace({ path: "/agent" });
  } catch (e) {
    error.value = e.message;
  }
}
async function importAccess(event) {
  const chosen = event.target.files[0];
  event.target.value = "";
  if (!chosen) return;
  if (sending.value) {
    error.value =
      "Wait for your current question to be saved before switching workspaces.";
    return;
  }
  try {
    restoreAccess(JSON.parse(await chosen.text()).access_key);
    deepseekKey.value='';
    newConversation();
    inspected.value = null;
    inspectorOpen.value = false;
    await Promise.all([loadSessions(), loadLibrary(), loadUsage()]);
  } catch (e) {
    error.value = e.message;
  }
}
function exportConversation() {
  downloadData(
    {
      title: currentTitle.value,
      turns: turns.value,
      results: currentResults.value,
    },
    `enzymind-conversation-${sessionId.value.slice(0, 8)}.json`,
  );
}
function onScroll() {
  const el = messageList.value;
  followBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
}
async function scrollBottom() {
  await nextTick();
  if (messageList.value)
    messageList.value.scrollTop = messageList.value.scrollHeight;
}
watch(() => route.query.reference, attachFromRoute);
let resultPolling = false;
const resultTimer = setInterval(async () => {
  if (unmounted || resultPolling || ![...library.value, ...currentResults.value].some(r => r.tool === 'blast' && ['submitting','queued'].includes(r.status))) return;
  resultPolling = true;
  try {
    const data = await workspaceFetch('/results');
    if (unmounted) return;
    library.value = data.results;
    currentResults.value = currentResults.value.map(r => data.results.find(next => next.id === r.id) || r);
  } catch { /* Preserve the last known results while reconnecting. */ }
  finally { resultPolling = false; }
}, 10000);
onMounted(async () => {
  try {
    try {
      const old = localStorage.getItem("enzymind_chat_history");
      if (old) legacyHistory.value = JSON.parse(old);
    } catch {}
    await Promise.all([loadSessions(), loadLibrary(), loadUsage()]);
    let saved = "";
    try {
      saved = localStorage.getItem("enzymind_workspace_session_v2") || "";
    } catch {}
    if (sessions.value.some((s) => s.id === saved)) await selectSession(saved);
    await attachFromRoute();
  } catch (e) {
    error.value = e.message;
  } finally {
    booting.value = false;
  }
});
onBeforeUnmount(() => {
  clearInterval(resultTimer);
  deepseekKey.value='';
  unmounted = true;
  sessionVersion++;
  disconnectStream();
  clearTimeout(pollTimer);
});
</script>
<style scoped>
.agent-billing{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 9px;font-size:11px;line-height:1.5;color:var(--color-text-secondary);}.agent-billing strong{color:var(--color-primary);font-variant-numeric:tabular-nums;}.agent-billing small{font-size:10px;color:var(--color-text-muted);}.agent-billing button{font:inherit;background:transparent;border:0;color:var(--color-primary);cursor:pointer;padding:3px 0;}.billing-personal{color:var(--color-primary);font-weight:600;}@media(max-width:600px){.agent-billing small{display:block;}}
.memory-label-short{display:none;}.memory-close{border:0;background:transparent;color:var(--color-text-secondary);font-size:20px;line-height:1;cursor:pointer;padding:0 4px;}
.topbar-actions .page-guide-trigger{padding:7px 9px;}
@media(max-width:600px){.workspace-topbar{flex-wrap:wrap;height:auto!important;gap:8px!important;}.workspace-topbar>div:first-child{flex-basis:100%;}.topbar-actions{width:100%;justify-content:flex-end;gap:6px!important;flex-wrap:wrap;}.topbar-actions .page-guide-trigger :deep(.guide-button-label){display:none;}}
.workspace-retention{margin:10px 28px;}
@media(max-width:600px){.workspace-retention{margin:8px 12px;}}
.partial-notice {font-size:12px;color:var(--color-text-muted);line-height:1.6;margin-top:12px;}
.memory-panel {flex-shrink:0;max-height:300px;overflow:auto;padding:18px 28px;background:var(--color-background-alt);border-bottom:1px solid var(--color-border);font-size:12px;}
.memory-panel-heading {display:flex;gap:16px;justify-content:space-between;flex-wrap:wrap;color:var(--color-primary);}
.memory-panel dl {display:flex;gap:25px;flex-wrap:wrap;margin:12px 0;}
.memory-panel dt {color:var(--color-text-muted);font-size:11px;}
.memory-panel dd {margin:4px 0;font-weight:600;}
.memory-panel p {line-height:1.7;margin:10px 0;}
.memory-summary {white-space:pre-wrap;}
.memory-panel summary {cursor:pointer;}

.agent-workspace {
  --ink: var(--color-text);
  --muted: var(--color-text-muted);
  --line: var(--color-border);
  display: grid;
  grid-template-columns: var(--sidebar-width, 250px) 8px minmax(0, 1fr);
  height: calc(100dvh - var(--navbar-height, 72px) - 48px);
  min-height: 620px;
  max-width: calc(var(--container-max-width) - 2 * var(--page-gutter));
  margin: 24px auto;
  width: calc(100% - 2 * var(--page-gutter));
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  overflow: hidden;
  box-shadow: var(--shadow-xl);
  background: var(--glass-bg);
  color: var(--ink);
  font-family: var(--font-family);
}
.agent-workspace.inspector-open {
  grid-template-columns: var(--sidebar-width, 220px) 8px minmax(360px, 1fr) 8px var(--inspector-width, 42%);
}
.column-resizer { display: flex; align-items: center; justify-content: center; cursor: col-resize; touch-action: none; background: var(--color-surface); z-index: 2; }
.column-resizer i { width: 3px; height: 36px; border-radius: 3px; background: var(--color-border); transition: background .15s, height .15s; pointer-events: none; }
.column-resizer:hover, .column-resizer:focus-visible, .is-resizing .column-resizer { background: var(--color-primary-light); outline: none; }
.column-resizer:hover i, .column-resizer:focus-visible i, .is-resizing .column-resizer i { background: var(--color-primary); height: 56px; }
.column-resizer:focus-visible { box-shadow: inset 0 0 0 2px var(--color-primary); }
button {
  font: inherit;
  cursor: pointer;
}
button:disabled {
  cursor: default;
  opacity: 0.5;
}
button:focus-visible,
a:focus-visible,
summary:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 3px;
}
.sidebar-backdrop,
.sidebar-close {
  display: none;
}
.workspace-sidebar {
  min-width: 0;
  background: linear-gradient(
    160deg,
    var(--color-primary-light),
    var(--color-surface)
  );
  border-right: 1px solid var(--line);
  padding: 24px 16px 16px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.workspace-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 25px 4px;
}
.workspace-mark {
  font-family: var(--font-family);
  font-size: 30px;
  background: var(--color-primary-gradient);
  color: var(--color-surface);
  border-radius: var(--radius-md);
  width: 42px;
  height: 42px;
  text-align: center;
  line-height: 40px;
}
.workspace-brand strong {
  display: block;
  font-size: 14px;
  font-weight: 600;
}
.workspace-brand div > span {
  font-size: 11px;
  letter-spacing: 0.18em;
  color: var(--muted);
}
.new-conversation {
  background: var(--color-primary-gradient);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 11px;
  color: var(--color-text-inverse);
  text-align: left;
  font-size: 13px;
}
.sidebar-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--color-text-muted);
  margin: 25px 8px 10px;
}
.sidebar-label button {
  border: 0;
  background: none;
  color: var(--color-text-secondary);
  font-size: 17px;
}
.conversation-list {
  overflow: auto;
  flex: 1;
  min-height: 0;
}
.conversation-item {
  width: 100%;
  background: none;
  border: 1px solid transparent;
  text-align: left;
  border-radius: var(--radius-md);
  padding: 10px;
  margin: 2px 0;
  color: var(--color-text-secondary);
}
.conversation-item span {
  display: block;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
  font-size: 13px;
}
.conversation-item small {
  font-size: 12px;
  opacity: 0.65;
  display: block;
  margin-top: 4px;
}
.conversation-item.active {
  background: var(--color-primary-light);
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.sidebar-empty {
  font-size: 13px;
  color: var(--color-text-muted);
  padding: 12px 8px;
  line-height: 1.7;
}
.sidebar-bottom {
  border-top: 1px solid var(--color-border);
  padding-top: 14px;
  margin-top: 16px;
  font-size: 13px;
}
.sidebar-bottom > button,
.sidebar-bottom > a {
  display: flex;
  width: 100%;
  padding: 9px 7px;
  color: var(--color-text-secondary);
  border: 0;
  background: none;
  text-align: left;
  text-decoration: none;
  gap: 12px;
}
.sidebar-bottom > button span {
  margin-left: auto;
}
.sidebar-bottom details {
  font-size: 12px;
  margin: 10px 7px;
  color: var(--color-text-muted);
}
.sidebar-bottom summary {
  cursor: pointer;
}
.sidebar-bottom details p {
  margin: 10px 0;
  font-size: 12px;
  line-height: 1.6;
}
.sidebar-bottom details button {
  background: white;
  border: 1px solid var(--color-border);
  padding: 6px;
  border-radius: 4px;
  font-size: 12px;
  margin: 4px 0;
  display: block;
  color: var(--color-text-secondary);
}
.conversation-pane {
  container-type: inline-size;
  container-name: conversation;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  background: var(--color-surface);
}
.workspace-topbar {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--color-background-alt);
  padding: 17px 28px;
  gap: 16px;
  min-height: 81px;
}
.eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.11em;
  color: var(--color-text-muted);
  text-transform: uppercase;
}
.workspace-topbar h1 {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.4;
  margin: 4px 0 0;
  max-width: 440px;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}
.workspace-topbar > div:first-child {
  min-width: 0;
  flex: 1;
}
.topbar-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}
.topbar-actions button {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  font-size: 12px;
  padding: 7px 10px;
  white-space: nowrap;
}
.topbar-actions button span {
  margin-left: 5px;
  color: var(--color-primary);
}
.mobile-new {
  display: none;
}
.memory-indicator {
  font-size: 12px;
  color: var(--color-text-muted);
  display: flex;
  gap: 5px;
  align-items: center;
  margin-right: 9px;
  white-space: nowrap;
}
.memory-indicator i {
  width: 5px;
  height: 5px;
  background: var(--color-success);
  border-radius: 50%;
}
.conversation-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  scrollbar-width: thin;
}
.workspace-welcome {
  max-width: 850px;
  margin: auto;
  padding: 30px 45px 24px;
}
.welcome-kicker {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  color: var(--color-primary);
  display: flex;
  gap: 10px;
  align-items: center;
}
.welcome-kicker > span {
  font-size: 22px;
  color: var(--color-primary);
}
.workspace-welcome h2 {
  font-family: var(--font-family);
  font-weight: 800;
  font-size: clamp(32px, 3vw, 44px);
  line-height: 1.15;
  letter-spacing: -0.035em;
  background: var(--color-primary-gradient);
  background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 18px 0;
}
.workspace-welcome > p {
  font-size: 14px;
  line-height: 1.85;
  color: var(--color-text-secondary);
}
.research-journeys {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 11px;
  margin: 30px 0 23px;
}
.research-journeys button {
  position: relative;
  display: flex;
  flex-direction: column;
  text-align: left;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 18px 20px;
  transition:
    border-color 0.15s,
    background 0.15s;
  min-height: 116px;
}
.research-journeys button:hover {
  border-color: var(--color-primary);
  background: var(--color-surface);
}
.journey-number {
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--color-text-muted);
  margin-bottom: 9px;
}
.research-journeys strong {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}
.research-journeys strong + span {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 5px;
}
.research-journeys b {
  position: absolute;
  right: 17px;
  top: 17px;
  font-size: 14px;
  font-weight: 400;
  color: var(--color-primary);
}
.workspace-how {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--color-text-muted);
  font-size: 11px;
}
.workspace-how span {
  display: flex;
  align-items: center;
  gap: 6px;
}
.workspace-how b {
  border: 1px solid var(--color-border);
  width: 17px;
  height: 17px;
  border-radius: 50%;
  text-align: center;
  line-height: 15px;
  font-size: 11px;
  font-weight: 400;
  color: var(--color-primary);
}
.workspace-how i {
  color: var(--color-border);
  font-style: normal;
}
.composer-area {
  padding: 10px 28px 17px;
  background: var(--color-surface);
}
.message-composer {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: 0 5px 17px rgba(37, 99, 235, 0.04);
  padding: 13px 15px 10px;
  max-width: 900px;
  margin: 0 auto;
}
.message-composer:focus-within {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}
.message-composer textarea {
  width: 100%;
  border: 0;
  outline: 0;
  resize: vertical;
  min-height: 66px;
  max-height: 200px;
  background: none;
  color: var(--color-text);
  font: inherit;
  font-size: 14px;
  line-height: 1.7;
  padding: 2px;
}
.message-composer textarea::placeholder {
  color: var(--color-text-muted);
}
.composer-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}
.composer-toolbar > div {
  display: flex;
  gap: 10px;
}
.composer-toolbar button {
  font-size: 12px;
  color: var(--color-text-muted);
  border: 0;
  background: none;
  padding: 7px 0;
}
.composer-toolbar .send-button {
  background: var(--color-primary-gradient);
  color: var(--color-surface);
  padding: 9px 14px;
  border-radius: var(--radius-md);
  font-size: 12px;
}
.send-button span {
  margin-left: 15px;
}
.composer-toolbar .stop-button {
  color: var(--color-error);
  background: var(--color-error-light);
  padding: 8px 12px;
  border-radius: var(--radius-md);
}
.composer-footnote {
  max-width: 900px;
  margin: 9px auto 0;
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--color-text-muted);
  gap: 10px;
}
.composer-attachments {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  max-width: 900px;
  margin: 0 auto 8px;
}
.composer-attachments button {
  border: 1px solid var(--color-border);
  border-radius: 5px;
  background: var(--color-primary-light);
  padding: 6px 9px;
  font-size: 12px;
  color: var(--color-primary);
}
.composer-attachments span {
  margin-left: 10px;
}
.composer-error,
.workspace-notice {
  padding: 10px 13px;
  background: var(--color-background-alt);
  border: 1px solid var(--color-border);
  color: var(--color-warning);
  border-radius: var(--radius-md);
  font-size: 13px;
  max-width: 900px;
  margin: 0 auto 8px;
  overflow-wrap: anywhere;
}
.workspace-notice {
  margin: 10px 20px 0;
  max-width: none;
  font-size: 12px;
}
.composer-error button,
.workspace-notice button {
  border: 0;
  background: none;
  color: inherit;
  margin-left: 8px;
  text-decoration: underline;
}
.turn-list {
  max-width: 900px;
  margin: 0 auto;
  padding: 30px 32px;
}
.research-turn {
  margin-bottom: 38px;
}
.message-byline {
  display: flex;
  gap: 9px;
  align-items: center;
  font-size: 12px;
  letter-spacing: 0.07em;
  font-weight: 700;
  color: var(--color-text-secondary);
  margin-bottom: 12px;
}
.message-byline time {
  font-weight: 400;
  font-size: 11px;
  letter-spacing: 0;
  color: var(--color-text-muted);
  margin-left: 5px;
}
.user-turn {
  margin: 0 0 25px 32px;
  background: var(--color-background-alt);
  border: 1px solid var(--color-background-alt);
  padding: 16px 20px;
  border-radius: var(--radius-md);
}
.user-turn p {
  font-size: 14px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--color-text);
  line-height: 1.8;
}
.user-turn details {
  font-size: 13px;
}
.user-turn pre {
  max-height: 260px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
}
.assistant-turn {
  font-size: 14px;
  line-height: 1.8;
  min-width: 0;
}
.assistant-mark {
  background: var(--color-primary-gradient);
  color: white;
  width: 24px;
  height: 24px;
  border-radius: 5px;
  text-align: center;
  line-height: 24px;
  font-family: var(--font-family);
  font-size: 16px;
  letter-spacing: 0;
}
.live-label {
  color: var(--color-primary);
  font-size: 11px;
  letter-spacing: 0;
  font-weight: 400;
}
.agent-markdown {
  overflow-wrap: anywhere;
  overflow-x: auto;
  padding-left: 33px;
  color: var(--color-text-secondary);
}
.agent-markdown :deep(p) {
  margin-bottom: 12px;
}
.agent-markdown :deep(h1),
.agent-markdown :deep(h2),
.agent-markdown :deep(h3) {
  font-size: 17px;
  margin: 22px 0 10px;
}
.agent-markdown :deep(a) {
  color: var(--color-primary);
  text-decoration: underline;
  text-decoration-color: var(--color-primary);
  text-underline-offset: 3px;
}
.agent-markdown :deep(ul),
.agent-markdown :deep(ol) {
  padding-left: 22px;
  margin: 10px 0;
}
.agent-markdown :deep(table) {
  border-collapse: collapse;
  font-size: 13px;
  margin: 15px 0;
  width: 100%;
}
.agent-markdown :deep(th),
.agent-markdown :deep(td) {
  padding: 8px;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
}
.agent-markdown :deep(th) {
  background: var(--color-background-alt);
}
.agent-markdown :deep(pre) {
  background: var(--color-background-alt);
  padding: 12px;
  overflow: auto;
  border-radius: var(--radius-md);
  font-size: 13px;
}
.inline-references {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}
.inline-references button {
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  border-radius: 4px;
  color: var(--color-primary);
  font-size: 12px;
  padding: 5px 8px;
}
.tool-timeline {
  margin: 12px 0 17px 33px;
  border: 1px solid var(--color-background-alt);
  border-radius: var(--radius-md);
  font-size: 12px;
  background: var(--color-surface);
}
.tool-timeline summary {
  padding: 9px 12px;
  cursor: pointer;
  color: var(--color-text-secondary);
}
.tool-timeline summary span {
  margin-left: 8px;
  color: var(--color-text-muted);
}
.tool-timeline > button {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 9px;
  border: 0;
  border-top: 1px solid var(--color-background-alt);
  padding: 9px 12px;
  text-align: left;
  font-size: 12px;
  background: var(--color-surface);
  color: var(--color-text-secondary);
}
.tool-timeline > button:disabled {
  opacity: 1;
}
.tool-timeline small {
  margin-left: auto;
  font-size: 12px;
  color: var(--color-text-muted);
}
.step-status {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  text-align: center;
  background: var(--color-background-alt);
  line-height: 16px;
  color: var(--color-text-muted);
}
.step-status.completed {
  background: var(--color-primary-light);
  color: var(--color-success);
}
.step-status.failed {
  background: var(--color-background-alt);
  color: var(--color-error);
}
.step-status.running {
  animation: pulse 1.6s infinite;
  color: var(--color-primary);
}
.working-status {
  font-size: 13px;
  color: var(--color-text-muted);
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 15px 0 15px 33px;
}
.working-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
  animation: pulse 1.6s infinite;
}
.context-notice {
  margin: 14px 0 0;
  padding: 12px 16px;
  border: 1px solid #c8dcf2;
  border-radius: 10px;
  background: #f3f8ff;
  color: #435c79;
  font-size: 13px;
  line-height: 1.6;
  overflow-wrap: anywhere;
}
.turn-error {
  background: var(--color-background-alt);
  border: 1px solid var(--color-border);
  padding: 14px;
  border-radius: var(--radius-md);
  margin-left: 33px;
  font-size: 13px;
  color: var(--color-warning);
}
.turn-error p {
  margin: 6px 0;
}
.turn-error button {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 6px 8px;
  font-size: 12px;
  color: var(--color-warning);
}
.answer-results {
  margin: 20px 0 0 33px;
}
.answer-results > button {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 11px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-primary);
  font-size: 12px;
  margin-top: 7px;
  text-align: left;
}
.answer-results > button span:last-child {
  margin-left: auto;
  color: var(--color-primary);
  font-size: 12px;
}
.result-inspector {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--color-border);
  background: var(--color-surface);
}
.result-inspector > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 19px 22px;
  border-bottom: 1px solid var(--color-border);
  height: 81px;
}
.result-inspector h2 {
  font-size: 15px;
  font-weight: 600;
  margin: 4px 0 0;
}
.result-inspector > header button {
  border: 0;
  background: transparent;
  font-size: 22px;
  color: var(--color-text-muted);
}
.inspector-scroll {
  overflow: auto;
  padding: 20px;
  min-height: 0;
  scrollbar-width: thin;
}
.library-search {
  font-size: 12px;
  color: var(--color-text-muted);
}
.library-search input {
  display: block;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 10px 11px;
  width: 100%;
  font: inherit;
  font-size: 13px;
  margin-top: 6px;
  background: var(--color-surface);
}
.library-help {
  font-size: 12px;
  color: var(--color-text-muted);
  line-height: 1.7;
  margin: 12px 0;
}
.library-tabs {
  display: flex;
  gap: 5px;
  margin: 20px 0;
}
.library-tabs button {
  border: 1px solid transparent;
  background: none;
  font-size: 12px;
  padding: 6px 9px;
  color: var(--color-text-muted);
  border-radius: 5px;
}
.library-tabs button.active {
  background: white;
  border-color: var(--color-border);
  color: var(--color-primary);
}
.library-card {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 17px;
  margin-bottom: 11px;
}
.library-card-title {
  display: block;
  font-size: 14px;
  color: var(--color-text);
  font-weight: 600;
  border: 0;
  background: none;
  margin: 6px 0 9px;
  text-align: left;
}
.library-card p {
  font-size: 12px;
  color: var(--color-text-muted);
  word-break: break-word;
  max-height: 35px;
  overflow: hidden;
}
.library-card footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: var(--color-text-muted);
  margin-top: 14px;
  gap: 10px;
}
.library-card footer button {
  border: 1px solid var(--color-border);
  background: var(--color-primary-light);
  border-radius: 4px;
  padding: 5px 8px;
  color: var(--color-primary);
  font-size: 12px;
}
.completed {
  color: var(--color-success);
}
.failed {
  color: var(--color-error);
}
.inspector-empty {
  text-align: center;
  padding: 50px 15px;
  color: var(--color-text-muted);
}
.inspector-empty > span {
  display: block;
  font-size: 35px;
  color: var(--color-border);
  margin-bottom: 15px;
}
.inspector-empty strong {
  font-size: 14px;
  color: var(--color-text-secondary);
}
.inspector-empty p {
  font-size: 12px;
  margin: 10px 0 22px;
}
.inspector-empty a {
  color: var(--color-primary);
  font-size: 12px;
  text-decoration: none;
}
.inspector-navigation {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin: 0 0 22px;
}
.inspector-navigation button {
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  border-radius: 5px;
  padding: 7px 10px;
  font-size: 12px;
  color: var(--color-primary);
}
.loading-state {
  padding: 50px;
  color: var(--color-text-muted);
  text-align: center;
  font-size: 14px;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
@keyframes pulse {
  50% {
    opacity: 0.35;
  }
}
@media (max-width: 1200px) {
  .inspector-resizer { display: none; }
  .agent-workspace.inspector-open {
    grid-template-columns: var(--sidebar-width, 250px) 8px minmax(0, 1fr);
  }
  .inspector-open .result-inspector {
    position: fixed;
    right: 0;
    top: var(--navbar-height, 72px);
    bottom: 0;
    width: min(720px, 70vw);
    z-index: 100;
    box-shadow: -15px 0 50px rgba(15, 23, 42, 0.12);
  }
  .memory-indicator {
    display: inline-flex;
    margin-right: 0;
  }
  .memory-label-full{display:none;}
  .memory-label-short{display:inline;}
  .workspace-welcome {
    padding: 40px 30px 25px;
  }
}
@media (max-width: 760px) {
  .column-resizer { display: none; }
  .memory-panel{max-height:min(240px,30dvh);}
  .agent-workspace,
  .agent-workspace.inspector-open {
    grid-template-columns: 1fr;
    min-height: 500px;
  }
  .workspace-sidebar {
    display: none;
  }
  .workspace-sidebar.mobile-open {
    display: flex;
    position: fixed;
    top: var(--navbar-height, 72px);
    bottom: 0;
    left: 0;
    width: min(320px, 88vw);
    z-index: 60;
    box-shadow: 10px 0 40px rgba(15, 23, 42, 0.15);
  }
  .sidebar-backdrop {
    display: block;
    position: fixed;
    inset: var(--navbar-height, 72px) 0 0;
    z-index: 59;
    background: rgba(15, 23, 42, 0.3);
    border: 0;
  }
  .mobile-open .sidebar-close {
    display: block;
    position: absolute;
    right: 14px;
    top: 14px;
    border: 0;
    background: transparent;
    font-size: 24px;
    color: var(--color-text-secondary);
  }
  .mobile-new {
    display: block;
  }
  .workspace-topbar {
    padding: 12px 16px;
    height: 70px;
    min-height: 70px;
  }
  .workspace-topbar h1 {
    font-size: 14px;
    max-width: 155px;
  }
  .workspace-topbar .eyebrow {
    font-size: 8px;
  }
  .workspace-welcome {
    padding: 30px 22px 20px;
  }
  .workspace-welcome h2 {
    font-size: 35px;
  }
  .workspace-welcome > p {
    font-size: 13px;
  }
  .research-journeys {
    gap: 8px;
    margin-top: 22px;
  }
  .research-journeys button {
    padding: 14px;
    min-height: 110px;
  }
  .research-journeys strong {
    font-size: 13px;
  }
  .research-journeys strong + span {
    font-size: 12px;
    line-height: 1.5;
  }
  .workspace-how {
    flex-wrap: wrap;
    font-size: 8px;
    gap: 7px;
  }
  .composer-area {
    padding: 9px 14px 13px;
  }
  .composer-footnote {
    font-size: 8px;
  }
  .composer-footnote span:last-child {
    display: none;
  }
  .composer-toolbar > div {
    gap: 8px;
  }
  .composer-toolbar button {
    font-size: 11px;
  }
  .composer-toolbar .send-button {
    padding: 9px;
    font-size: 12px;
  }
  .turn-list {
    padding: 22px 15px;
  }
  .user-turn {
    margin-left: 15px;
    padding: 13px;
  }
  .agent-markdown {
    padding-left: 10px;
  }
  .answer-results,
  .tool-timeline,
  .working-status,
  .turn-error {
    margin-left: 10px;
  }
  .inspector-open .result-inspector {
    width: 100vw;
    top: var(--navbar-height, 72px);
  }
  .inspector-scroll {
    padding: 16px;
  }
  .topbar-actions button {
    font-size: 12px;
    padding: 6px;
  }
}
@container conversation (max-width: 600px) {
  .workspace-topbar { flex-wrap: wrap; height: auto; padding: 12px 16px; gap: 8px; }
  .workspace-topbar > div:first-child { flex-basis: 100%; }
  .topbar-actions { width: 100%; gap: 6px; flex-wrap: wrap; }
  .memory-label-full { display: none; }
  .memory-label-short { display: inline; }
  .workspace-welcome { padding: 30px 22px 20px; }
  .workspace-welcome h2 { font-size: 35px; }
  .composer-area { padding: 9px 14px 13px; }
  .composer-toolbar { flex-wrap: wrap; gap: 8px; }
  .composer-toolbar > div { flex-wrap: wrap; }
  .composer-footnote { flex-wrap: wrap; gap: 5px; }
}
@media (prefers-reduced-motion: reduce) {
  .working-dot,
  .step-status.running {
    animation: none;
  }
}
</style>
