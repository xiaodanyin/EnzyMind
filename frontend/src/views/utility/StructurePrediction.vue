<template>
  <PageContainer
    title="Structure Prediction"
    description="Predict 3D structure models from UniProt ID, raw amino acid sequence, or FASTA file. Powered by ESMFold."
  >
    <transition name="fade" mode="out-in">
      <div v-if="!selectedMethod" class="method-selection">
        <h3 class="method-title">Select Input Method</h3>
        <div class="method-grid">
          <div class="method-card" v-for="method in inputMethods" :key="method.id" @click="selectMethod(method.id)">
            <div class="method-icon">{{ method.icon }}</div>
            <div class="method-info">
              <h4>{{ method.title }}</h4>
            </div>
            <div class="method-arrow">→</div>
            <div class="method-tooltip">{{ method.description }}</div>
          </div>
        </div>
      </div>

      <div v-else class="input-form">
        <div class="form-header">
          <button class="back-btn" @click="goBack">
            <span class="back-icon">←</span>
            <span>Change Input Method</span>
          </button>
          <div class="current-method">
            <span class="method-badge">{{ currentMethodInfo.icon }} {{ currentMethodInfo.title }}</span>
          </div>
        </div>

        <div class="step-section">
          <div class="step-header">
            <span class="step-number">1</span>
            <span class="step-title">Input Protein Sequence</span>
          </div>
          
          <InputCard v-if="selectedMethod === 'uniprot'" title="UniProt ID" hint="Enter UniProt accession to predict structure">
            <input type="text" v-model="uniprotId" placeholder="e.g., P01308" @keyup.enter="runPrediction" />
            <div class="btn-group">
              <button class="btn btn-primary" @click="runPrediction" :disabled="loading">
                <span class="btn-icon">🔮</span> Predict Structure
              </button>
              <button class="btn btn-secondary" @click="clearAll">Clear</button>
              <button class="btn btn-outline" @click="loadUniprotExample">Load Example</button>
            </div>
          </InputCard>

          <InputCard v-if="selectedMethod === 'sequence'" title="Amino Acid Sequence" hint="Enter raw protein sequence for de novo prediction">
            <textarea v-model="sequence" placeholder="Enter amino acid sequence (one-letter code)..." rows="5"></textarea>
            <div class="btn-group">
              <button class="btn btn-primary" @click="runPrediction" :disabled="loading">
                <span class="btn-icon">🔮</span> Predict Structure
              </button>
              <button class="btn btn-secondary" @click="clearAll">Clear</button>
              <button class="btn btn-outline" @click="loadSequenceExample">Load Example</button>
            </div>
          </InputCard>

          <InputCard v-if="selectedMethod === 'fasta'" title="FASTA File" hint="Upload a FASTA file containing protein sequence">
            <div class="file-upload-area" :class="{ 'has-file': fastaContent }">
              <input type="file" ref="fastaFileInput" accept=".fasta,.fa,.faa,.txt" @change="onFileChange" class="file-input" />
              <div class="file-upload-content">
                <span class="file-icon">📄</span>
                <span class="file-text">{{ fastaContent ? 'File loaded successfully' : 'Click or drag file here' }}</span>
              </div>
            </div>
            <div class="btn-group">
              <button class="btn btn-primary" @click="runPrediction" :disabled="loading">
                <span class="btn-icon">🔮</span> Predict Structure
              </button>
              <button class="btn btn-secondary" @click="clearAll">Clear</button>
            </div>
          </InputCard>
        </div>
      </div>
    </transition>

    <!-- Structure Viewer -->
    <div v-if="showViewer" class="viewer-container">
      <div class="viewer-header">
        <h3>🧬 3D Structure Viewer</h3>
        <div class="viewer-controls">
          <button class="btn btn-sm" @click="setViewStyle('cartoon')" :class="{active: currentStyle === 'cartoon'}">🧬 Cartoon</button>
          <button class="btn btn-sm" @click="setViewStyle('surface')" :class="{active: currentStyle === 'surface'}">🧱 Surface</button>
          <button class="btn btn-sm" @click="setViewStyle('line')" :class="{active: currentStyle === 'line'}">🧩 Line</button>
          <button class="btn btn-sm" @click="toggleBackground">🌙 Toggle BG</button>
          <button class="btn btn-sm" @click="resetView">🔄 Reset</button>
          <button class="btn btn-sm" @click="saveImage">📸 Save Image</button>
          <button class="btn btn-sm btn-secondary" @click="downloadPDB">⬇️ Download PDB</button>
        </div>
      </div>
      <div ref="viewerDiv" class="mol-viewer"></div>
      <div class="viewer-info" v-if="pdbFilename">
        <div class="info-item">
          <span class="info-label">✅ Saved PDB:</span>
          <a :href="pdbUrl" :download="pdbFilename" class="info-link">{{ pdbFilename }}</a>
        </div>
        <div class="color-legend">
          <span class="legend-title">pLDDT Score:</span>
          <span class="legend-item legend-green">≥90 (Very High)</span>
          <span class="legend-item legend-blue">70-90 (High)</span>
          <span class="legend-item legend-orange">50-70 (Low)</span>
          <span class="legend-item legend-red">&lt;50 (Very Low)</span>
        </div>
      </div>
    </div>

    <ResultBox :show="showResult && !showViewer" :status="resultStatus" :title="resultTitle" @copy="copyResult">
      <div class="result-error" v-if="error">{{ error }}</div>
    </ResultBox>

    <LoadingOverlay 
      :show="loading" 
      text="Predicting structure..."
      hint="Structure prediction may take 1-5 minutes depending on sequence length"
    />
  </PageContainer>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import PageContainer from '@/components/layout/PageContainer.vue'
import InputCard from '@/components/common/InputCard.vue'
import ResultBox from '@/components/common/ResultBox.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import api from '@/api'
import { copyToClipboard } from '@/utils/clipboard'

const inputMethods = [
  { id: 'uniprot', icon: '🔖', title: 'UniProt ID', description: 'Enter a UniProt accession number to predict its 3D structure' },
  { id: 'sequence', icon: '🧬', title: 'Amino Acid Sequence', description: 'Paste a raw protein sequence for de novo structure prediction' },
  { id: 'fasta', icon: '📁', title: 'FASTA File', description: 'Upload a FASTA format file containing protein sequence' }
]

const selectedMethod = ref(null)
const uniprotId = ref('')
const sequence = ref('')
const fastaFileInput = ref(null)
const fastaContent = ref('')
const loading = ref(false)
const showResult = ref(false)
const showViewer = ref(false)
const error = ref('')
const pdbFilename = ref('')
const pdbUrl = ref('')

const viewerDiv = ref(null)
const currentStyle = ref('cartoon')
const bgColor = ref('white')
let viewer = null

const currentMethodInfo = computed(() => inputMethods.find(m => m.id === selectedMethod.value) || {})
const resultStatus = computed(() => error.value ? 'error' : 'success')
const resultTitle = computed(() => error.value ? 'Error' : 'Result')

const selectMethod = (methodId) => { selectedMethod.value = methodId }

const goBack = () => {
  if (!showViewer.value) {
    selectedMethod.value = null
  } else {
    selectedMethod.value = null
    showViewer.value = false
  }
}

const loadUniprotExample = () => { uniprotId.value = 'P01308' }
const loadSequenceExample = () => { sequence.value = 'FVNQHLCGSHLVEALYLVCGERGFFYTPKA' }

const onFileChange = (event) => {
  const file = event.target.files[0]
  if (file) {
    const reader = new FileReader()
    reader.onload = (e) => { fastaContent.value = e.target.result }
    reader.readAsText(file)
  }
}

const runPrediction = async () => {
  let queryValue = ''
  let inputType = 'auto'
  let outputName = 'query'

  if (selectedMethod.value === 'uniprot') {
    queryValue = uniprotId.value.trim()
    inputType = 'uniprot'
    if (queryValue) outputName = queryValue.replace(/[^a-zA-Z0-9_-]/g, '_')
  } else if (selectedMethod.value === 'sequence') {
    queryValue = sequence.value.trim()
    inputType = 'sequence'
    if (queryValue) {
      const seqPrefix = queryValue.substring(0, 6).replace(/[^A-Z]/g, '')
      outputName = `seq_${seqPrefix}_${Date.now()}`
    }
  } else if (selectedMethod.value === 'fasta') {
    if (!fastaContent.value) {
      error.value = 'Please select a FASTA file.'
      showResult.value = true
      return
    }
    queryValue = fastaContent.value
    inputType = 'fasta'
    outputName = `fasta_${Date.now()}`
  }

  if (!queryValue) {
    error.value = 'Please provide input.'
    showResult.value = true
    return
  }

  loading.value = true
  showResult.value = false
  showViewer.value = false
  error.value = ''
  pdbFilename.value = ''
  pdbUrl.value = ''

  try {
    const requestBody = { query: queryValue, input_type: inputType, output_name: outputName }
    const response = await api.post('/predict/structure', requestBody)

    let filename = null
    if (response.success && response.pdb_path) {
      filename = response.pdb_path.split('/').pop()
    } else if (response.static_path) {
      filename = response.static_path.split('/').pop()
    } else if (response.result && typeof response.result === 'string' && response.result.includes('.pdb')) {
      filename = response.result.split('/').pop()
    }

    if (filename && response.success) {
      pdbFilename.value = filename
      pdbUrl.value = `/enzymind/api/pdb/${filename}`
      await loadPDBViewer()
    } else {
      error.value = response.error || 'Prediction failed or no PDB returned.'
      showResult.value = true
    }
  } catch (err) {
    error.value = err.message || 'Network error occurred'
    showResult.value = true
  } finally {
    loading.value = false
  }
}

const loadPDBViewer = async () => {
  if (!pdbUrl.value) return
  try {
    const pdbResponse = await fetch(pdbUrl.value)
    if (!pdbResponse.ok) throw new Error(`Failed to fetch PDB file: HTTP ${pdbResponse.status}`)
    
    const pdbText = await pdbResponse.text()
    if (!pdbText || pdbText.length < 50) throw new Error('PDB file is empty or too small')

    showViewer.value = true
    await nextTick()
    
    if (!window.$3Dmol) await loadScript('https://cdnjs.cloudflare.com/ajax/libs/3Dmol/2.0.6/3Dmol-min.js')
    createViewer(pdbText)
  } catch (err) {
    error.value = `Failed to load structure: ${err.message}`
    showResult.value = true
    showViewer.value = false
  }
}

const loadScript = (src) => {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = src
    script.onload = resolve
    script.onerror = reject
    document.head.appendChild(script)
  })
}

const createViewer = (pdbText) => {
  if (!viewerDiv.value || !window.$3Dmol) return
  viewerDiv.value.innerHTML = ''
  viewer = window.$3Dmol.createViewer(viewerDiv.value, { backgroundColor: bgColor.value })
  viewer.addModel(pdbText, 'pdb')
  applyCartoonStyle()
  viewer.zoomTo()
  viewer.render()
  setTimeout(() => viewer.zoomTo(), 100)
}

const applyCartoonStyle = () => {
  if (!viewer) return
  viewer.setStyle({}, {
    cartoon: {
      colorfunc: (atom) => {
        const score = atom.b
        if (score >= 90) return 'green'
        else if (score >= 70) return 'blue'
        else if (score >= 50) return 'orange'
        else return 'red'
      },
      opacity: 0.9
    },
    stick: { radius: 0.2, opacity: 0.6 }
  })
  viewer.render()
}

const setViewStyle = (style) => {
  if (!viewer) return
  currentStyle.value = style
  if (style === 'cartoon') applyCartoonStyle()
  else if (style === 'surface') {
    viewer.setStyle({}, { surface: { opacity: 0.85 }, cartoon: {} })
    viewer.render()
  } else if (style === 'line') {
    viewer.setStyle({}, { lines: {}, cartoon: {} })
    viewer.render()
  }
}

const toggleBackground = () => {
  if (!viewer) return
  bgColor.value = bgColor.value === 'white' ? 'black' : 'white'
  viewer.setBackgroundColor(bgColor.value)
  viewer.render()
}

const resetView = () => { if (viewer) { viewer.zoomTo(); viewer.render() } }

const saveImage = () => {
  if (!viewer) return
  const png = viewer.pngURI()
  const a = document.createElement('a')
  a.href = png
  a.download = 'structure_snapshot.png'
  a.click()
}

const downloadPDB = () => {
  if (!pdbUrl.value) return
  const a = document.createElement('a')
  a.href = pdbUrl.value
  a.download = pdbFilename.value || 'structure.pdb'
  a.click()
}

const clearAll = () => {
  uniprotId.value = ''
  sequence.value = ''
  fastaContent.value = ''
  if (fastaFileInput.value) fastaFileInput.value.value = ''
  showViewer.value = false
  showResult.value = false
  error.value = ''
  pdbFilename.value = ''
  pdbUrl.value = ''
}

const copyResult = () => {
  copyToClipboard(error.value)
}
</script>

<style lang="scss" scoped>
.method-selection { animation: fadeIn 0.4s ease-out; }
.method-title {
  text-align: center; font-size: 1.5rem; font-weight: 700; color: var(--color-text); margin-bottom: var(--spacing-xl);
  &::after { content: ''; display: block; width: 60px; height: 3px; background: var(--color-primary-gradient); margin: var(--spacing-md) auto 0; border-radius: 2px; }
}
.method-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: var(--spacing-lg); max-width: 900px; margin: 0 auto; padding-top: var(--spacing-xl); }
.method-card {
  display: flex; align-items: center; gap: var(--spacing-lg); padding: var(--spacing-lg) var(--spacing-xl);
  background: var(--glass-bg); border: 2px solid var(--color-border); border-radius: var(--radius-xl);
  cursor: pointer; transition: all var(--transition-normal); position: relative; overflow: visible;
  &::before { content: ''; position: absolute; inset: 0; background: var(--color-primary-gradient); opacity: 0; transition: opacity var(--transition-normal); border-radius: inherit; }
  &:hover {
    transform: translateY(-4px); border-color: var(--color-primary); box-shadow: var(--shadow-lg), 0 0 30px rgba(37, 99, 235, 0.15);
    &::before { opacity: 0.05; }
    .method-arrow { transform: translateX(4px); opacity: 1; }
    .method-icon { transform: scale(1.1); }
    .method-tooltip { opacity: 1; visibility: visible; transform: translateX(-50%) translateY(0); }
  }
}
.method-icon { font-size: 2.2rem; flex-shrink: 0; transition: transform var(--transition-normal); }
.method-info {
  flex: 1;
  h4 { font-size: 1.1rem; font-weight: 700; color: var(--color-text); margin: 0; }
}
.method-arrow { font-size: 1.3rem; color: var(--color-primary); opacity: 0.5; transition: all var(--transition-fast); }
.method-tooltip {
  position: absolute; bottom: calc(100% + 12px); left: 50%; transform: translateX(-50%) translateY(8px);
  background: var(--color-text); color: white; padding: 10px 16px; border-radius: var(--radius-lg);
  font-size: 0.85rem; line-height: 1.5; max-width: 280px; white-space: normal; text-align: center;
  opacity: 0; visibility: hidden; transition: all var(--transition-fast); z-index: 100;
  box-shadow: var(--shadow-lg); pointer-events: none;
  &::after { content: ''; position: absolute; top: 100%; left: 50%; transform: translateX(-50%); border: 8px solid transparent; border-top-color: var(--color-text); }
}

.input-form { animation: fadeIn 0.4s ease-out; }
.form-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--spacing-xl); padding-bottom: var(--spacing-md); border-bottom: 1px solid var(--color-border); }
.back-btn {
  display: flex; align-items: center; gap: var(--spacing-sm); padding: var(--spacing-sm) var(--spacing-md);
  background: transparent; border: 1px solid var(--color-border); border-radius: var(--radius-md);
  color: var(--color-text-secondary); font-size: 0.9rem; cursor: pointer; transition: all var(--transition-fast);
  &:hover { border-color: var(--color-primary); color: var(--color-primary); background: var(--color-primary-light); .back-icon { transform: translateX(-3px); } }
  .back-icon { transition: transform var(--transition-fast); }
}
.method-badge { display: inline-flex; align-items: center; gap: var(--spacing-xs); padding: var(--spacing-sm) var(--spacing-md); background: var(--color-primary-light); color: var(--color-primary); border-radius: var(--radius-full); font-size: 0.9rem; font-weight: 600; }

.step-section { margin-bottom: var(--spacing-xl); }
.step-header { display: flex; align-items: center; gap: var(--spacing-md); margin-bottom: var(--spacing-lg); }
.step-number { display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; background: var(--color-primary-gradient); color: white; border-radius: 50%; font-weight: 700; font-size: 0.95rem; }
.step-title { font-size: 1.2rem; font-weight: 600; color: var(--color-text); }

.file-upload-area {
  position: relative; border: 2px dashed var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-xl); text-align: center; transition: all var(--transition-fast); cursor: pointer;
  &:hover { border-color: var(--color-primary); background: var(--color-primary-light); }
  &.has-file { border-color: var(--color-success); background: rgba(5, 150, 105, 0.1); }
}
.file-input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.file-upload-content { display: flex; flex-direction: column; align-items: center; gap: var(--spacing-sm); pointer-events: none; .file-icon { font-size: 2.5rem; } .file-text { color: var(--color-text-secondary); font-size: 0.95rem; } }

.btn-group { display: flex; gap: var(--spacing-md); margin-top: var(--spacing-lg); flex-wrap: wrap; }
.btn-icon { margin-right: var(--spacing-xs); }

.viewer-container {
  background: var(--glass-bg); border-radius: var(--radius-xl); box-shadow: var(--shadow-lg); overflow: hidden; margin-top: var(--spacing-xl);
  border: 1px solid var(--color-border);
}
.viewer-header {
  display: flex; justify-content: space-between; align-items: center; padding: var(--spacing-md) var(--spacing-lg);
  background: var(--color-primary-light); border-bottom: 1px solid var(--color-border); flex-wrap: wrap; gap: var(--spacing-md);
  h3 { margin: 0; color: var(--color-primary); font-size: 1.1rem; }
}
.viewer-controls {
  display: flex; gap: var(--spacing-sm); flex-wrap: wrap;
  .btn-sm {
    padding: 6px 12px; font-size: 0.85rem; background: white; border: 1px solid var(--color-border); border-radius: var(--radius-md); cursor: pointer; transition: all var(--transition-fast);
    &:hover { border-color: var(--color-primary); color: var(--color-primary); }
    &.active { background: var(--color-primary); color: white; border-color: var(--color-primary); }
  }
}
.mol-viewer { width: 100%; height: 500px; position: relative; background: white; }
.viewer-info {
  display: flex; flex-direction: column; gap: var(--spacing-md); padding: var(--spacing-md) var(--spacing-lg);
  background: rgba(255,255,255,0.8); border-top: 1px solid var(--color-border);
}
.info-item { display: flex; align-items: center; gap: var(--spacing-sm); }
.info-label { font-weight: 600; color: var(--color-text); }
.info-link { color: var(--color-primary); text-decoration: underline; &:hover { color: var(--color-primary-dark); } }
.color-legend {
  display: flex; align-items: center; gap: var(--spacing-md); flex-wrap: wrap; font-size: 0.85rem;
  .legend-title { font-weight: 600; color: var(--color-text); }
  .legend-item { padding: 2px 8px; border-radius: var(--radius-sm); color: white; font-weight: 500; }
  .legend-green { background: green; }
  .legend-blue { background: blue; }
  .legend-orange { background: orange; color: #333; }
  .legend-red { background: red; }
}

.result-error { color: var(--color-error); }

.fade-enter-active, .fade-leave-active { transition: all 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; transform: translateY(10px); }

@media (max-width: 768px) {
  .method-grid { grid-template-columns: 1fr; }
  .form-header { flex-direction: column; gap: var(--spacing-md); align-items: flex-start; }
  .viewer-header { flex-direction: column; align-items: flex-start; }
  .mol-viewer { height: 350px; }
}
</style>
