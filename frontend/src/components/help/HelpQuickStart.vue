<template>
  <div class="help-quick-start">
    <div class="start-options">
      <article class="start-option workspace-option">
        <span class="option-eyebrow">ASK & EXPLORE</span>
        <h3>Research in Workspace</h3>
        <p>Ask a research question. The Agent automatically selects and runs tools to analyze your inputs and answer with supporting evidence. Review the results and ask a follow-up.</p>
        <button type="button" @click="focusWorkspaceGuide">View Workspace guide <span aria-hidden="true">↓</span></button>
      </article>
      <article class="start-option">
        <span class="option-eyebrow">CHOOSE & RUN</span>
        <h3>Use Individual Tools</h3>
        <p>Use individual tools directly. Enter your inputs, adjust the available parameters and run an analysis. Inspect the results and download the data you need.</p>
        <button type="button" @click="focusToolPicker">Choose a tool <span aria-hidden="true">↓</span></button>
      </article>
    </div>

    <section ref="workspaceGuide" class="tool-guide-browser workspace-guide-browser" aria-labelledby="guide-title-workspace">
      <HelpGuideCard :guide="WORKSPACE_HELP_GUIDE" heading-tag="h3" />
    </section>

    <section ref="toolPicker" class="tool-guide-browser" aria-labelledby="tool-guides-title">
      <header class="guide-browser-heading">
        <div><span class="option-eyebrow">STEP BY STEP</span><h3 id="tool-guides-title">Find your tool guide</h3></div>
        <span class="guide-count">11 tools · one guide at a time</span>
      </header>
      <div class="guide-groups" role="group" aria-label="Tool categories">
        <button v-for="item in HELP_GUIDE_GROUPS" :key="item.id" type="button" :aria-pressed="group === item.id" @click="group = item.id">
          {{ item.label }} <span>{{ item.count }}</span>
        </button>
      </div>
      <div class="guide-tool-picker" role="group" :aria-label="`${group === 'prediction' ? 'Prediction' : 'Utility'} tool guides`">
        <button v-for="tool in tools" :key="tool.id" type="button" :aria-pressed="selected.id === tool.id" aria-controls="selected-tool-guide" @click="selection[group] = tool.id">{{ tool.title }}</button>
      </div>

      <HelpGuideCard id="selected-tool-guide" :guide="selected" />
    </section>

    <div class="help-more" aria-labelledby="help-more-title">
      <h3 id="help-more-title">A little more guidance</h3>
      <details>
        <summary><span><strong>Inputs & molecules</strong><small>Protein formats, FASTA records and Ketcher</small></span><span class="details-chevron" aria-hidden="true">⌄</span></summary>
        <div class="note-body">
          <p>Each model page starts with its input and method workflow. Select “Go to input”, load an example, or paste a UniProt accession, sequence or FASTA. Select one record explicitly when a FASTA file contains several proteins. Invalid amino acids are reported rather than removed.</p>
          <p>Choose “Draw with Ketcher” to edit a molecule or reaction. The drawing and SMILES field stay linked. Substrate tools accept a molecule; reaction tools require <code>reactants&gt;&gt;products</code>. Atom maps, isotopes, charge and stereochemistry are retained. If the editor cannot load, paste SMILES directly.</p>
        </div>
      </details>
      <details>
        <summary><span><strong>Structures & residues</strong><small>Explore Mol*, site annotations and confidence</small></span><span class="details-chevron" aria-hidden="true">⌄</span></summary>
        <div class="note-body">
          <p>Choose cartoon, sticks or surface view in Mol*. Select a chain, filter sites by type or score, and select a residue in the sequence or table to locate it in the model. Site scores and structure pLDDT measure different predictions.</p>
          <p>Source numbering is preserved. Ambiguous or missing mappings remain visible as annotations and are never silently renumbered. Historical results without coordinates still show their available sequence and residue annotations.</p>
          <p>If WebGL is unavailable, PDB structures use an interactive alpha-carbon preview. Download the original coordinates for other molecular viewers.</p>
        </div>
      </details>
      <details>
        <summary><span><strong>Workspace & saved results</strong><small>Examples, conversation memory and evidence reuse</small></span><span class="details-chevron" aria-hidden="true">⌄</span></summary>
        <div class="note-body">
          <p><router-link to="/agent">Open Workspace</router-link> and choose a research starter or write your own question. Open result cards or citations to inspect inputs, sources, values and residues. Use “Add to question” to attach up to four saved records for interpretation without repeating the analysis. Continue a saved conversation from the left menu; open the conversation menu first on mobile.</p>
          <p>The eight Workspace examples cover function annotation, reaction recommendation, kinetics, functional sites and mechanism, sequence and structure profiling, BLAST comparison, saved-result interpretation, and CYP2A6-mediated coumarin hydroxylation. Each includes inputs, expected evidence and a follow-up question. “Load starting question” fills the composer; review and send it when ready. Use “Examples” to return to follow-ups, and attach a saved result before the evidence-reuse example.</p>
          <p>Open “Conversation memory” to inspect the saved summary, covered exchanges and estimated context size. The Agent preserves raw history and result references, summarizes older exchanges when needed, and commits a new summary only with a completed answer. Failed or interrupted turns do not erase earlier memory or automatically repeat predictions.</p>
          <p>Tool analyses appear automatically in <router-link to="/results">Results</router-link>. Use “Discuss with Agent” to bring a result into a conversation. Tool, Workspace and result pages offer a guide on the first visit in this browser. Skip or close it, then select “Guide” to replay it. Animated previews do not change your data; reduced-motion settings are respected. Home and Help have no automatic popup guides.</p>
          <p>Records belong to this browser’s workspace. Under “Workspace access”, export your access file before clearing browser data or changing browsers. Restoring it reopens records that have not expired. Access files and result links do not back up the data or prevent deletion.</p>
        </div>
      </details>
      <details ref="downloadsDetails">
        <summary><span><strong>Downloads & recovery</strong><small>Export your work, retention and interrupted analyses</small></span><span class="details-chevron" aria-hidden="true">⌄</span></summary>
        <div class="note-body">
          <p>Export JSON for the complete result, CSV for predicted residues, and download figures and protein coordinates separately. “Download conversation” saves messages and result references; download each result’s JSON to keep its full scientific data.</p>
          <p>Conversations and results persist after refresh within a 90-day retention period. Each result and each question-and-answer exchange is automatically deleted 90 days after creation. Viewing records or continuing a conversation does not extend that deadline. Cleanup runs hourly and temporarily protects active analyses. Expiry dates appear on results, with a reminder in the final 7 days.</p>
          <p>Close a reminder with × to leave a small retention or expiry-date link that reopens the details. This browser remembers the choice. Hiding a reminder does not change deletion dates; clearing browser storage resets guide and reminder preferences.</p>
          <p>Refreshing reconnects to a running Workspace analysis. Stop ends Agent orchestration; a submitted computation may still finish. Completed results remain available. After a server interruption, expired execution leases are marked interrupted. Inspect existing results before resubmitting.</p>
        </div>
      </details>
    </div>
    <div class="quick-start-retention"><span aria-hidden="true">90d</span><p>Results and conversations are deleted after 90 days. Download what you need.</p><button type="button" @click="showDownloads">Details</button></div>

  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { HELP_GUIDES, HELP_GUIDE_GROUPS, WORKSPACE_HELP_GUIDE } from '@/config/helpGuides'
import HelpGuideCard from './HelpGuideCard.vue'

const group = ref('prediction')
const selection = reactive({ prediction: 'recognize', utility: 'enzyme-info' })
const tools = computed(() => HELP_GUIDES.filter(guide => guide.group === group.value))
const selected = computed(() => HELP_GUIDES.find(guide => guide.id === selection[group.value]))
const toolPicker = ref(null)
const workspaceGuide = ref(null)
const downloadsDetails = ref(null)
function scrollBehavior() { return window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' }
function focusWorkspaceGuide() {
  workspaceGuide.value.scrollIntoView({ behavior: scrollBehavior(), block: 'start' })
  workspaceGuide.value.querySelector('.open-tool').focus({ preventScroll: true })
}
function focusToolPicker() {
  toolPicker.value.scrollIntoView({ behavior: scrollBehavior(), block: 'start' })
  toolPicker.value.querySelector('.guide-tool-picker button[aria-pressed="true"]').focus({ preventScroll: true })
}
function showDownloads() {
  downloadsDetails.value.open = true
  downloadsDetails.value.querySelector('summary').focus({ preventScroll: true })
  downloadsDetails.value.scrollIntoView({ behavior: scrollBehavior(), block: 'nearest' })
}
</script>

<style scoped>
.help-quick-start { --guide-ink: #233b5a; --guide-muted: #60738d; color: var(--guide-ink); }
.start-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin: 4px 0 30px; }
.start-option { padding: 22px; border: 1px solid #dce5f3; border-radius: 14px; background: #f5f7ff; display: flex; flex-direction: column; align-items: flex-start; }
.workspace-option { background: #f0f8f7; border-color: #d9e9e7; }
.option-eyebrow { font-size: 10px; letter-spacing: .13em; color: #5974a9; font-weight: 700; }
.workspace-option .option-eyebrow { color: #498078; }
.start-option h3 { margin: 8px 0; font-size: 20px; letter-spacing: -.025em; line-height: 1.3; }
.start-option p { color: var(--guide-muted); font-size: 14px; line-height: 1.7; margin: 0 0 18px; }
.start-option a, .start-option button { margin-top: auto; display: inline-flex; align-items: center; gap: 12px; color: #365fba; background: none; border: 0; padding: 0; min-height: 30px; font: 600 13px var(--font-family); text-decoration: none; cursor: pointer; }
.workspace-option a, .workspace-option button { color: #27796d; }
.tool-guide-browser { scroll-margin-top: 110px; border: 1px solid #dce5f3; border-radius: 16px; background: #fff; overflow: hidden; }
.workspace-guide-browser { margin-bottom: 30px; }
.workspace-guide-browser :deep(.selected-tool-guide) { border-top: 0; }
.guide-browser-heading { padding: 24px 24px 18px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.guide-browser-heading h3 { font-size: 22px; letter-spacing: -.025em; margin: 6px 0 0; }
.guide-count { color: #7b8ba3; font-size: 11px; text-align: right; }
.guide-groups { display: flex; gap: 5px; padding: 0 24px 16px; }
.guide-groups button { display: flex; align-items: center; gap: 9px; min-height: 40px; padding: 8px 14px; border: 1px solid transparent; border-radius: 9px; background: #f3f6fb; color: #5c6f8c; font: 600 13px var(--font-family); cursor: pointer; }
.guide-groups button[aria-pressed="true"] { color: #fff; background: #4165cf; border-color: #4165cf; }
.guide-groups button span { font-size: 10px; min-width: 19px; padding: 2px 4px; text-align: center; border-radius: 4px; background: #8196c01c; }
.guide-groups button[aria-pressed="true"] span { background: #ffffff2b; }
.guide-tool-picker { display: flex; gap: 8px; flex-wrap: wrap; padding: 0 24px 22px; }
.guide-tool-picker button { min-height: 38px; padding: 8px 11px; font: 12px var(--font-family); color: #5a6d87; background: white; border: 1px solid #dce4f0; border-radius: 7px; cursor: pointer; text-align: left; }
.guide-tool-picker button[aria-pressed="true"] { color: #315dbf; border-color: #8ca9ea; background: #eef4ff; box-shadow: inset 0 0 0 1px #8ca9ea; }
.help-more { margin-top: 30px; }
.help-more > h3 { font-size: 18px; margin: 0 0 14px; }
.help-more details { border: 1px solid #dfe7f2; border-radius: 10px; margin-top: 9px; background: white; overflow: hidden; }
.help-more summary { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 15px 18px; cursor: pointer; list-style: none; }
.help-more summary::-webkit-details-marker { display: none; }
.help-more summary strong { font-size: 14px; font-weight: 600; display: block; }
.help-more summary small { display: block; font-size: 12px; color: #74859d; margin-top: 4px; line-height: 1.5; }
.details-chevron { color: #7b8ba6; font-size: 19px; }
.help-more details[open] .details-chevron { transform: rotate(180deg); }
.help-more details[open] summary { background: #f7f9fd; border-bottom: 1px solid #e5ebf4; }
.note-body { padding: 2px 18px 6px; }
.note-body p { font-size: 13px; line-height: 1.85; color: #5b6f88; margin: 14px 0; }
.note-body a { color: #3862bf; text-underline-offset: 3px; }
.note-body code { font-size: 12px; overflow-wrap: anywhere; }
.quick-start-retention { display: flex; align-items: center; gap: 10px; margin-top: 18px; padding: 12px 14px; border-radius: 9px; background: #f0f5ff; color: #5d7293; }
.quick-start-retention > span { font: 600 11px var(--font-mono); color: #4264b7; background: #e0eaff; padding: 5px; border-radius: 5px; }
.quick-start-retention p { font-size: 12px; margin: 0; flex: 1; line-height: 1.65; }
.quick-start-retention button { background: none; border: 0; padding: 6px 0 6px 6px; color: #3f63b6; font: 12px var(--font-family); cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
button:focus-visible, a:focus-visible, summary:focus-visible { outline: 3px solid #7b9fe8; outline-offset: 3px; }
@media (hover: hover) { .guide-tool-picker button:hover { border-color: #9bb4e4; background: #f5f8ff; } .help-more summary:hover { background: #f7f9fd; } }
@media (max-width: 700px) { .start-options { gap: 12px; } .start-option { padding: 18px; } .start-option h3 { font-size: 18px; } .guide-browser-heading { padding: 20px; } .guide-groups { padding-right: 20px; padding-left: 20px; } .guide-tool-picker { padding-right: 20px; padding-left: 20px; } }
@media (max-width: 500px) { .start-options { grid-template-columns: 1fr; } .start-option p { margin-bottom: 12px; } .guide-browser-heading { align-items: flex-start; } .guide-browser-heading h3 { font-size: 20px; } .guide-count { max-width: 80px; line-height: 1.6; } .guide-tool-picker { gap: 7px; } .guide-tool-picker button { font-size: 11px; } .help-more summary { padding: 14px; } }
@media (prefers-reduced-motion: no-preference) { .guide-tool-picker button, .guide-groups button { transition: background-color .18s, border-color .18s, color .18s; } .help-more details[open] .note-body { animation: notes-in .18s ease-out; } @keyframes notes-in { from { opacity: 0; transform: translateY(-3px); } to { opacity: 1; transform: translateY(0); } } }
</style>
