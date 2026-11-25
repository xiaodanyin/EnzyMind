<template>
  <section
    ref="wrapper"
    class="protein-workbench"
    aria-label="Interactive protein structure and residues"
  >
    <div class="protein-toolbar">
      <div>
        <span class="eyebrow">STRUCTURE EXPLORER</span>
        <h4>{{ title }}</h4>
      </div>
      <div class="viewer-controls">
        <label
          >Color
          <select v-model="colorMode" aria-label="Color">
            <option value="sites">Functional sites</option>
            <option value="chain">Chain</option>
            <option v-if="confidenceType === 'plddt'" value="confidence">
              pLDDT
            </option>
          </select></label
        >
        <label
          >View
          <select aria-label="View" v-model="style" :disabled="fallback || !ready">
            <option value="cartoon">Cartoon</option>
            <option value="stick">Sticks</option>
            <option value="surface">Surface</option>
          </select></label
        >
        <label v-if="sites.length"><input v-model="showLabels" type="checkbox" /> Site labels</label>
        <button type="button" @click="reset" :disabled="!ready">Reset</button>
        <button type="button" @click="snapshot" :disabled="!ready">
          {{ fallback ? "Save SVG" : "Save PNG" }}
        </button>
        <button type="button" @click="download" :disabled="!structure">
          Download {{ format.toUpperCase() }}
        </button>
        <button
          type="button"
          @click="fullscreen"
          :disabled="!ready"
          :aria-label="expanded ? 'Exit full screen' : 'Expand structure viewer'"
          :aria-pressed="expanded"
        >
          {{ expanded ? 'Exit full screen' : 'Expand' }}
        </button>
      </div>
    </div>
    <div class="protein-body" :class="{ 'no-structure': !structure, 'single-panel': !showResiduePanel }">
      <div class="molecule-area">
        <div
          ref="canvas"
          class="molecule-canvas"
          aria-label="3D protein model; drag to rotate, scroll to zoom"
        ></div>
        <svg v-if="ready && !fallback && showLabels" class="label-overlay" aria-label="Functional site labels">
          <g v-for="label in overlayLabels" :key="label.key" @click="focusAtom(label.atom)">
            <line :x1="label.anchorX" :y1="label.anchorY" :x2="label.x + label.w/2" :y2="label.y + label.h/2" :stroke="label.color" stroke-width="1.2" />
            <circle :cx="label.anchorX" :cy="label.anchorY" r="3" :fill="label.color" />
            <rect :x="label.x" :y="label.y" :width="label.w" :height="label.h" rx="5" fill="white" :stroke="label.color" />
            <text :x="label.x + 8" :y="label.y + 17" fill="#243349" font-size="11">{{ label.text }}</text>
          </g>
        </svg>
        <svg
          v-if="fallback"
          ref="fallbackSvg"
          class="backbone-preview"
          viewBox="0 0 600 400"
          role="img"
          aria-label="Interactive alpha-carbon backbone preview"
        >
          <g v-for="path in backbonePaths" :key="path.chain">
            <path
              :d="path.d"
              fill="none"
              :stroke="path.color"
              stroke-width="3"
              stroke-linecap="round"
            />
          </g>
          <circle
            v-for="point in projectedResidues"
            :key="`${point.atom.chain}:${point.atom.resi}:${point.atom.icode}`"
            :cx="point.x"
            :cy="point.y"
            :r="
              sameSelection(point.atom)
                ? 6
                : 3
            "
            :fill="residueColor(point.atom)"
            @click="focusAtom(point.atom)"
          >
            <title>
              {{ point.atom.resn }} {{ point.atom.resi }} ·
              {{ point.atom.chain }}
            </title>
          </circle>
        </svg>
        <div v-if="fallback" class="fallback-controls">
          <span>Backbone preview · Mol* unavailable</span
          ><label
            >Rotate
            <input v-model.number="rotation" type="range" min="0" max="360"
          /></label>
        </div>
        <div v-if="!ready" class="viewer-placeholder" role="status">
          <strong>{{
            error ||
            (structure
              ? "Preparing protein structure…"
              : "No structure stored for this result")
          }}</strong>
          <span v-if="!structure"
            >You can still explore the residue annotations below.</span
          >
          <button v-if="error && structure" @click="load">Retry viewer</button>
        </div>
        <div v-if="ready && !fallback" class="viewer-caption">
          Drag to rotate · scroll to zoom · click a residue to inspect
        </div>
        <div v-if="selection" class="residue-selection" role="status">
          <strong
            >{{ selection.resn }} {{ selection.resi
            }}{{ selection.icode || "" }} · chain
            {{ selection.chain || "—" }}</strong
          >
          <span
            v-if="confidenceType === 'plddt' && Number.isFinite(selection.b)"
            >pLDDT {{ selection.b.toFixed(1) }}</span
          >
          <button
            @click="
              selection = null;
              paint();
            "
            aria-label="Clear residue selection"
          >
            ×
          </button>
        </div>
      </div>
      <aside v-if="showResiduePanel" class="residue-panel">
        <div class="residue-heading">
          <h4>Residues</h4>
          <span>{{ filteredSites.length }} / {{ sites.length }} sites</span>
        </div>
        <div class="residue-filters">
          <label
            >Chain
            <select v-model="chain" aria-label="Chain">
              <option value="*">All chains</option>
              <option v-for="c in chains" :key="c" :value="c">
                {{ c || "(unnamed)" }}
              </option>
            </select></label
          >
          <label
            >Type
            <select v-model="siteType">
              <option value="*">All sites</option>
              <option v-for="name in Object.keys(palette)" :key="name">
                {{ name }}
              </option>
            </select></label
          >
          <label v-if="hasProbabilities" class="confidence-filter"
            >Minimum site score <output>{{ threshold.toFixed(2) }}</output
            ><input
              v-model.number="threshold"
              type="range"
              min="0"
              max="1"
              step="0.05"
          /></label>
        </div>
        <ResultPreview v-if="sites.length" :title="`${title} — residue sites`" note="Showing sites that match the current chain, type and score filters.">
        <div class="site-table-wrap">
          <table v-if="sites.length" class="site-table">
            <thead>
              <tr>
                <th>Residue</th>
                <th>Site type</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="site in filteredSites"
                :key="site.key"
                :class="{ selected: selection && matchesSite(selection, site) }"
              >
                <td>
                  <button
                    @click="focusSite(site)"
                    :disabled="!visibleResidues.length"
                    :title="`Locate residue ${site.position} in the structure`"
                  >
                    {{ site.residue }} {{ site.position }}{{ site.icode || "" }}<small v-if="site.chain !== null"> · {{ site.chain || "—" }}</small>
                  </button>
                </td>
                <td>
                  <span
                    class="site-dot"
                    :style="{ background: palette[site.type] || '#687b92' }"
                  ></span
                  >{{ site.type }}
                </td>
                <td>
                  {{
                    site.confidence === null ? "—" : site.confidence.toFixed(4)
                  }}
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="!filteredSites.length" class="muted">
            {{
              sites.length
                ? "No sites match these filters."
                : "No functional sites were provided for this structure."
            }}
          </p>
        </div>
        </ResultPreview>
        <p v-else class="muted">No functional sites were provided for this structure.</p>
        <p v-if="mappingMessage" class="mapping-note" role="status">
          {{ mappingMessage }}
        </p>
        <p class="mapping-note">
          Annotations and coordinates retain their source numbering. Mapping
          requires matching residue numbers and identities; missing residues are
          never renumbered. Site scores and structure confidence describe
          different predictions.
        </p>
      </aside>
    </div>
    <p v-if="error && ready" class="mapping-note" role="status">{{ error }} <button @click="load">Retry Mol*</button></p>
    <p v-if="mappedSites.length > 40 && showLabels" class="mapping-note">Showing 40 labels to keep the model readable. Filter by chain, type or score to inspect other sites.</p>
    <div class="protein-legend" v-if="colorMode === 'sites'">
      <span v-for="(color, name) in palette" :key="name"
        ><i :style="{ background: color }"></i>{{ name }}</span
      ><span><i style="background: #91aabd"></i>Other residues</span>
    </div>
    <div class="protein-legend" v-else-if="colorMode === 'confidence'">
      <span
        v-for="[label, color] in [
          ['≥90', '#0053d6'],
          ['70–90', '#65cbf3'],
          ['50–70', '#ffdb13'],
          ['<50', '#ff7d45'],
        ]"
        :key="label"
        ><i :style="{ background: color }"></i>{{ label }}</span
      ><span>pLDDT · structure confidence</span>
    </div>
    <ScientificChart v-if="showConfidencePlot && confidenceType==='plddt' && atoms.some(a=>Number.isFinite(a.b))" title="Local structure confidence" description="pLDDT from the predicted structure (0–100). Select a point to inspect that residue; zoom into long sequences with the slider." type="line" :rows="visibleResidues.map(a=>({label:`${a.chain}:${a.resi}${a.icode}`,value:Number.isFinite(a.b)?a.b:null}))" x-label="Source residue" y-label="pLDDT" :max="100" :threshold="70" @select="i=>focusAtom(visibleResidues[i])" />
    <div v-if="showSequence && visibleResidues.length" class="sequence-section">
      <span class="eyebrow">SEQUENCE ↔ STRUCTURE</span
      ><span class="muted">
        {{
          ready
            ? "Select a residue to focus the model"
            : "Sequence from this result · no structure available"
        }}</span
      >
      <div class="sequence-track">
        <button
          v-for="atom in visibleResidues"
          :key="`${atom.chain}:${atom.resi}:${atom.icode}`"
          @click="focusAtom(atom)"
          :class="{
            selected:
              sameSelection(atom),
          }"
          :style="{ borderBottomColor: siteColor(atom) }"
          :title="`${atom.resn} ${atom.resi}${atom.icode || ''} · chain ${atom.chain || '—'}`"
        >
          <small>{{ atom.resi }}</small
          >{{
            letters[atom.resn] || (atom.resn.length === 1 ? atom.resn : "X")
          }}
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from "vue";
import ScientificChart from "./ScientificChart.vue";
import ResultPreview from './ResultPreview.vue';
import { SITE_COLORS, parsePdbResidues } from "@/utils/resultData";
import { resolveSite, residueKey, placeLabels } from "@/utils/residueMapping";
import { downloadData } from "@/utils/workspace";

const props = defineProps({
  structure: { type: String, default: "" },
  format: { type: String, default: "pdb" },
  sites: { type: Array, default: () => [] },
  title: { type: String, default: "Protein structure" },
  confidenceType: { type: String, default: "" },
  sequence: { type: String, default: "" },
  showSequence: { type: Boolean, default: true },
  showConfidencePlot: { type: Boolean, default: true },
  showResiduePanel: { type: Boolean, default: true },
  sitePalette: { type: Object, default: null },
});
const emit = defineEmits(['select']);
const palette = computed(() => props.sitePalette || SITE_COLORS);
defineExpose({focusSite});
const canvas = ref(null),
  wrapper = ref(null),
  expanded = ref(false),
  ready = ref(false),
  error = ref(""),
  selection = ref(null);
const fallback = ref(false),
  fallbackSvg = ref(null),
  rotation = ref(35);
const style = ref("cartoon"),
  colorMode = ref(
    props.confidenceType === "plddt" && !props.sites.length
      ? "confidence"
      : "sites",
  ),
  chain = ref("*"),
  siteType = ref("*"),
  threshold = ref(0);
const atoms = ref([]),
  mappingMessage = ref("");
let viewer,
  resizeObserver,
  generation = 0,
  labelFrame;
const showLabels = ref(true), overlayLabels = ref([]);
const letters = {
  ALA: "A",
  ARG: "R",
  ASN: "N",
  ASP: "D",
  CYS: "C",
  GLN: "Q",
  GLU: "E",
  GLY: "G",
  HIS: "H",
  ILE: "I",
  LEU: "L",
  LYS: "K",
  MET: "M",
  PHE: "F",
  PRO: "P",
  SER: "S",
  THR: "T",
  TRP: "W",
  TYR: "Y",
  VAL: "V",
};
const chains = computed(() => [
  ...new Set(atoms.value.map((a) => a.chain || "")),
]);
const visibleResidues = computed(() =>
  (atoms.value.length
    ? atoms.value
    : [...props.sequence].map((letter, index) => ({
        resn: letter,
        resi: index + 1,
        chain: "",
        icode: "",
      }))
  ).filter((a) => chain.value === "*" || a.chain === chain.value),
);
const filteredSites = computed(() =>
  props.sites.filter(
    (s) =>
      (siteType.value === "*" || s.type === siteType.value) &&
      (s.confidence === null || s.confidence >= threshold.value) &&
      (chain.value === "*" || s.chain === null || s.chain === chain.value),
  ),
);
const hasProbabilities = computed(
  () =>
    props.sites.some((s) => s.confidence !== null) &&
    props.sites.every(
      (s) => s.confidence === null || (s.confidence >= 0 && s.confidence <= 1),
    ),
);
const matchesSite = (atom, site) => {
  const matched = resolveSite(site, atoms.value.length ? atoms.value : visibleResidues.value, chain.value);
  return matched && residueKey(matched) === residueKey(atom);
};
const mappedSites = computed(() => filteredSites.value.map(site => ({site, atom:resolveSite(site,atoms.value,chain.value)})).filter(x=>x.atom));
const sameSelection = atom => selection.value && residueKey(selection.value) === residueKey(atom);
const siteColors = computed(() => {
  const colors = new Map();
  const source = atoms.value.length ? atoms.value : visibleResidues.value;
  for (const site of filteredSites.value) {
    const atom = resolveSite(site,source,chain.value);
    if (atom && !colors.has(residueKey(atom))) colors.set(residueKey(atom),palette.value[site.type] || '#91aabd');
  }
  return colors;
});
const siteColor = atom => siteColors.value.get(residueKey(atom)) || '#91aabd';
const residueColor = (atom) =>
  colorMode.value === "confidence"
    ? !Number.isFinite(atom.b)
      ? "#91aabd"
      : atom.b >= 90
        ? "#0053d6"
        : atom.b >= 70
          ? "#65cbf3"
          : atom.b >= 50
            ? "#ffdb13"
            : "#ff7d45"
    : colorMode.value === "chain"
      ? ["#4d91a5", "#b69761", "#819d70"][chains.value.indexOf(atom.chain) % 3]
      : siteColor(atom);
const projectedResidues = computed(() => {
  if (!fallback.value || !visibleResidues.value.length) return [];
  const source = visibleResidues.value,
    theta = (rotation.value * Math.PI) / 180;
  const center = ["x", "y", "z"].map(
    (key) => source.reduce((sum, a) => sum + a[key], 0) / source.length,
  );
  const points = source.map((atom) => {
    const x = atom.x - center[0],
      y = atom.y - center[1],
      z = atom.z - center[2];
    return {
      atom,
      x: x * Math.cos(theta) + z * Math.sin(theta),
      y: y * 0.8 - (z * Math.cos(theta) - x * Math.sin(theta)) * 0.4,
    };
  });
  const extent = Math.max(
      ...points.map((p) => Math.max(Math.abs(p.x), Math.abs(p.y))),
      1,
    ),
    scale = 155 / extent;
  return points.map((p) => ({
    ...p,
    x: 300 + p.x * scale,
    y: 195 - p.y * scale,
  }));
});
const backbonePaths = computed(() =>
  chains.value.map((c, index) => {
    const points = projectedResidues.value.filter((p) => p.atom.chain === c);
    return {
      chain: c,
      color: ["#8eaebb", "#bbac90", "#93b4a0"][index % 3],
      d: points
        .map((p, i) => {
          const previous = points[i - 1]?.atom;
          const connected =
            previous &&
            Math.hypot(
              p.atom.x - previous.x,
              p.atom.y - previous.y,
              p.atom.z - previous.z,
            ) < 4.5;
          return `${connected ? "L" : "M"}${p.x},${p.y}`;
        })
        .join(" "),
    };
  }),
);
function updateLabels() {
  cancelAnimationFrame(labelFrame);
  labelFrame = requestAnimationFrame(() => {
    if (!viewer || !showLabels.value || fallback.value) {overlayLabels.value = []; return;}
    const candidates = mappedSites.value.slice(0, 40).map(({site,atom})=>({atom,color:palette.value[site.type] || '#687b92'}));
    if (selection.value && !candidates.some(x=>residueKey(x.atom)===residueKey(selection.value))) candidates.unshift({atom:selection.value,color:'#6241d9'});
    const points = candidates.map(({atom,color})=> {
      const p = viewer.project(atom);
      return p && {...p,atom,color,key:residueKey(atom),text:`${atom.resn} ${atom.resi}${atom.icode || ''} · ${atom.chain || '—'}`};
    }).filter(p => p && p.x>=0 && p.y>=0 && p.x<=canvas.value.clientWidth && p.y<=canvas.value.clientHeight);
    overlayLabels.value = placeLabels(points,canvas.value.clientWidth,canvas.value.clientHeight);
  });
}
function dispose() {
  cancelAnimationFrame(labelFrame);
  viewer?.dispose(); viewer = null;
  overlayLabels.value = [];
  canvas.value?.replaceChildren();
}
async function load() {
  const current = ++generation;
  ready.value = false; error.value = ''; selection.value = null; atoms.value = [];
  mappingMessage.value = ''; fallback.value = false; dispose();
  if (!props.structure) return;
  const parsed = props.format === 'pdb' ? parsePdbResidues(props.structure) : [];
  atoms.value = parsed; chain.value = '*';
  try {
    const {createProteinViewer} = await import('@/utils/molstarViewer');
    if (current !== generation || !canvas.value) return;
    const next = await createProteinViewer(canvas.value,props.structure,props.format,{select:focusAtom,camera:updateLabels});
    if (current !== generation) {next.dispose(); return;}
    viewer = next; atoms.value = next.atoms; ready.value = true;
    await paint(); await viewer.reset(); updateLabels();
    if (mappedSites.value.length < props.sites.length) mappingMessage.value = 'Some annotations cannot be mapped uniquely. Select a chain and verify source numbering; unresolved sites stay in the table.';
  } catch (e) {
    if (current !== generation) return;
    error.value = `Mol* could not display this structure: ${e?.message || String(e)}`;
    dispose();
    if (parsed.length) {atoms.value = parsed; fallback.value = true; ready.value = true;}
  }
}
async function paint() {
  if (!viewer || !ready.value) return;
  try {
    await viewer.paint({style:style.value,chain:chain.value,color:residueColor,sites:mappedSites.value.map(x=>x.atom)});
    if (!selection.value) viewer?.clearSelection();
    updateLabels();
  } catch(e) {error.value = `Could not update the structure: ${e.message}`;}
}
function focusAtom(atom) {
  selection.value = {...atom};
  emit('select', atom);
  viewer?.focus(atom); updateLabels();
}
function focusSite(site) {
  const match = resolveSite(site,atoms.value.length ? atoms.value : visibleResidues.value,chain.value);
  if (!match) {
    mappingMessage.value = 'No unique residue matches this number, identity, chain and insertion code. Select the intended chain or verify source numbering; unresolved residues are not renumbered.';
    return;
  }
  mappingMessage.value = ''; focusAtom(match);
}
function reset() {
  selection.value = null; rotation.value = 35;
  viewer?.clearSelection(); viewer?.reset(); updateLabels();
}
async function snapshot() {
  if (fallback.value) {
    downloadData(new XMLSerializer().serializeToString(fallbackSvg.value),'enzymind-backbone.svg','image/svg+xml'); return;
  }
  try {
    const link = document.createElement('a');
    link.href = await viewer.snapshot(); link.download = 'enzymind-structure.png'; link.click();
  } catch(e) {error.value = `Snapshot failed: ${e.message}`;}
}
function download() {
  downloadData(
    props.structure,
    `enzymind-structure.${props.format}`,
    "text/plain",
  );
}
async function fullscreen() {
  try {
    if (document.fullscreenElement === wrapper.value) await document.exitFullscreen();
    else await wrapper.value.requestFullscreen();
  } catch {
    error.value = "Fullscreen is unavailable in this browser.";
  }
}
function onFullscreenChange() {
  expanded.value = document.fullscreenElement === wrapper.value;
}
watch(
  () => [props.structure, props.format, props.confidenceType],
  () => {
    colorMode.value =
      props.confidenceType === "plddt" && !props.sites.length
        ? "confidence"
        : "sites";
    load();
  },
);
watch(showLabels, updateLabels);
watch(chain, () => {
  selection.value = null;
  paint();
});
watch(
  [style, colorMode, chain, siteType, threshold, () => props.sites],
  paint,
  { deep: true },
);
onMounted(() => {
  document.addEventListener('fullscreenchange', onFullscreenChange);
  onFullscreenChange();
  load();
  resizeObserver = new ResizeObserver(() => {
    viewer?.resize();
    updateLabels();
  });
  resizeObserver.observe(canvas.value);
});
onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange);
  generation++;
  resizeObserver?.disconnect();
  dispose();
});
</script>

<style scoped>
.label-overlay {position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:2;}
.label-overlay g {pointer-events:auto;cursor:pointer;}
.molecule-canvas :deep(canvas) {display:block;width:100%;height:100%;}
.viewer-controls input[type=checkbox] {width:auto;}

.sequence-section > .muted {
  display: block;
  margin-top: 4px;
}
.backbone-preview {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  background: var(--color-background-alt);
}
.backbone-preview circle {
  cursor: pointer;
}
.fallback-controls {
  position: absolute;
  bottom: 12px;
  left: 16px;
  right: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  font-size: 10px;
  color: var(--color-text-secondary);
}
.fallback-controls label {
  display: flex;
  align-items: center;
  gap: 8px;
}
.fallback-controls input {
  width: 100px;
  accent-color: var(--color-primary);
}

.protein-workbench {
  container-type: inline-size;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: white;
  margin: 20px 0;
  color: var(--color-text);
}
.protein-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
  flex-wrap: wrap;
}
.eyebrow {
  font-size: 10px;
  letter-spacing: 0.12em;
  font-weight: 750;
  color: var(--color-text-secondary);
}
h4 {
  margin: 0;
  font-size: 15px;
}
.viewer-controls {
  display: flex;
  gap: 7px;
  align-items: center;
  flex-wrap: wrap;
}
.viewer-controls label,
.residue-filters label {
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}
.protein-workbench button,
.protein-workbench select {
  font: inherit;
  font-size: 12px;
  border: 1px solid var(--color-border);
  border-radius: 5px;
  background: white;
  color: var(--color-text);
  padding: 6px 8px;
  cursor: pointer;
}
.protein-workbench button:disabled {
  opacity: 0.5;
  cursor: default;
}
.protein-workbench button:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
.protein-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 290px;
}
.protein-body.single-panel { grid-template-columns: minmax(0,1fr); }
.protein-body.no-structure {
  grid-template-columns: 1fr;
}
.protein-body.no-structure .molecule-area {
  height: 145px;
}
.protein-body.no-structure .residue-panel {
  border-left: 0;
  border-top: 1px solid var(--color-border);
}
.molecule-area {
  position: relative;
  min-width: 0;
  height: 420px;
  background: var(--color-background-alt);
}
.molecule-canvas {
  position: absolute;
  inset: 0;
}
.viewer-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  padding: 25px;
  gap: 12px;
  text-align: center;
  color: var(--color-text-muted);
  font-size: 13px;
}
.viewer-caption {
  position: absolute;
  bottom: 12px;
  left: 16px;
  font-size: 10px;
  color: var(--color-text-secondary);
  pointer-events: none;
}
.residue-selection {
  position: absolute;
  left: 14px;
  top: 12px;
  display: flex;
  gap: 10px;
  align-items: center;
  background: var(--color-surface);
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 12px;
  max-width: 95%;
}
.residue-panel {
  border-left: 1px solid var(--color-border);
  padding: 14px;
  min-width: 0;
}
.residue-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: var(--color-text-secondary);
}
.residue-filters {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin: 12px 0;
}
.confidence-filter {
  width: 100%;
  flex-wrap: wrap;
}
.confidence-filter input {
  width: 100%;
  accent-color: var(--color-primary);
}
.confidence-filter output {
  margin-left: auto;
}
.site-table-wrap {
  max-height: 205px;
  overflow: auto;
}
.site-table {
  font-size: 10px !important;
  width: 100%;
  border-collapse: collapse;
}
.site-table th {
  text-align: left;
  font-weight: 600;
  background: var(--color-background-alt);
  position: sticky;
  top: 0;
  padding: 6px;
}
.site-table td {
  padding: 6px 3px;
  border-bottom: 1px solid var(--color-background-alt);
}
.site-table td button {
  padding: 3px;
  font-size: 11px;
  border: 0;
  color: var(--color-primary);
}
.site-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 4px;
}
.mapping-note {
  font-size: 10px;
  line-height: 1.5;
  color: var(--color-text-secondary);
  margin-top: 12px;
}
.protein-legend {
  display: flex;
  gap: 15px;
  flex-wrap: wrap;
  padding: 12px 16px;
  font-size: 11px;
  border-top: 1px solid var(--color-background-alt);
}
.protein-legend span {
  display: flex;
  align-items: center;
  gap: 6px;
}
.protein-legend i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.sequence-section {
  padding: 14px 16px;
  border-top: 1px solid var(--color-background-alt);
}
.muted {
  font-size: 11px;
  color: var(--color-text-muted);
}
.sequence-track {
  display: flex;
  overflow: auto;
  padding: 12px 0;
  gap: 2px;
  max-height: 105px;
}
.sequence-track button {
  flex-shrink: 0;
  border: 0;
  border-bottom: 3px solid;
  padding: 3px;
  min-width: 25px;
  font-family: var(--font-mono);
  font-size: 14px;
  border-radius: 2px;
}
.sequence-track small {
  display: block;
  font-size: 8px;
  color: var(--color-text-muted);
}
.selected {
  background: var(--color-primary-light) !important;
}
.protein-workbench:fullscreen {
  overflow: auto;
}
.protein-workbench:fullscreen .molecule-area {
  height: 70vh;
}
@container (max-width: 760px) {
  .protein-body {
    grid-template-columns: 1fr;
  }
  .residue-panel {
    border-left: 0;
    border-top: 1px solid var(--color-border);
  }
  .molecule-area {
    height: 340px;
  }
}
@media (prefers-reduced-motion: reduce) {
  * {
    scroll-behavior: auto;
  }
}
</style>
