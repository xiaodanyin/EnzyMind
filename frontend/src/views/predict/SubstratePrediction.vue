<template>
  <PageContainer
    title="Substrate Prediction"
    description="Predict whether a given molecule can act as a substrate for a specific enzyme."
  >
    <transition name="fade" mode="out-in">
      <div v-if="!selectedMethod" class="method-selection">
        <h3 class="method-title">Select Enzyme Input Method</h3>
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
          <button class="back-btn" @click="selectedMethod = null">
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
            <span class="step-title">Input Enzyme</span>
          </div>
          
          <InputCard v-if="selectedMethod === 'uniprot'" title="UniProt ID" hint="Enter enzyme UniProt ID">
            <input type="text" v-model="enzymeUniprot" placeholder="e.g., P12345" />
            <div class="btn-group-sm">
              <button class="btn btn-outline btn-sm" @click="loadEnzymeExample">Load Example</button>
            </div>
          </InputCard>

          <InputCard v-if="selectedMethod === 'sequence'" title="Amino Acid Sequence" hint="Paste enzyme sequence">
            <textarea v-model="enzymeSequence" placeholder="MKFLILLFNILCLFPVLAADNHGVGPQGAS..." rows="4"></textarea>
            <div class="btn-group-sm">
              <button class="btn btn-outline btn-sm" @click="loadSequenceExample">Load Example</button>
            </div>
          </InputCard>

          <InputCard v-if="selectedMethod === 'fasta'" title="FASTA File" hint="Upload enzyme FASTA file">
            <div class="file-upload-area" :class="{ 'has-file': fastaContent }">
              <input type="file" ref="fastaInput" accept=".fasta,.fa" @change="handleFileChange" class="file-input" />
              <div class="file-upload-content">
                <span class="file-icon">📄</span>
                <span class="file-text">{{ fastaContent ? 'File loaded successfully' : 'Click or drag file here' }}</span>
              </div>
            </div>
          </InputCard>
        </div>

        <div class="step-section">
          <div class="step-header">
            <span class="step-number">2</span>
            <span class="step-title">Input Molecule (Substrate)</span>
          </div>
          
          <InputCard title="Molecule Input" hint="Draw the molecule or enter SMILES directly">
            <!-- JSME Molecule Editor -->
            <div class="jsme-wrapper-small">
              <JSMEEditor
                v-model="smiles"
                container-id="jsme_substrate_editor"
                height="300px"
                width="100%"
                options="oldlook,star,nocanonize"
                @jsme-ready="onJSMEReady"
                @structure-change="onStructureChange"
                ref="jsmeEditor"
              />
            </div>
            
            <!-- SMILES Input -->
            <div class="smiles-input-section">
              <label class="input-label">SMILES</label>
              <textarea v-model="smiles" placeholder="e.g., CC(=O)O (acetic acid)" rows="2"></textarea>
            </div>
            
            <div class="btn-group">
              <button class="btn btn-primary" @click="submit" :disabled="loading">
                <span class="btn-icon">🔬</span> Predict
              </button>
              <button class="btn btn-secondary" @click="clearAll">Clear All</button>
              <button class="btn btn-outline" @click="loadFullExample">Load Full Example</button>
            </div>
          </InputCard>
        </div>
      </div>
    </transition>

    <ResultBox :show="showResult" :status="resultStatus" :title="resultTitle" @copy="copyResult">
      <div class="result-main" v-if="result">
        <div class="prediction-class" :class="result.is_substrate ? 'is-substrate' : 'not-substrate'">
          <span class="label">Prediction:</span>
          <span class="value">{{ result.is_substrate ? 'Is a Substrate' : 'Not a Substrate' }}</span>
        </div>
        <div class="confidence" v-if="result.confidence">
          <span class="label">Confidence:</span>
          <span class="value">{{ (result.confidence * 100).toFixed(2) }}%</span>
        </div>
      </div>
      <div class="result-error" v-else-if="error">{{ error }}</div>
    </ResultBox>

    <LoadingOverlay :show="loading" text="Predicting substrate relationship..." />
  </PageContainer>
</template>

<script setup>
import { ref, computed } from 'vue'
import PageContainer from '@/components/layout/PageContainer.vue'
import InputCard from '@/components/common/InputCard.vue'
import ResultBox from '@/components/common/ResultBox.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import JSMEEditor from '@/components/JSMEEditor.vue'
import { enzymeApi } from '@/api'
import { copyToClipboard } from '@/utils/clipboard'

// JSME editor refs
const jsmeEditor = ref(null)
const jsmeReady = ref(false)

// JSME event handlers
const onJSMEReady = (event) => {
  jsmeReady.value = event.success
  if (!event.success) {
    console.error('JSME failed to initialize:', event.error)
  }
}

const onStructureChange = (event) => {
  console.log('Molecule SMILES updated:', event.smiles)
}

const inputMethods = [
  { id: 'uniprot', icon: '🔖', title: 'UniProt ID', description: 'Enter a UniProt accession number for the enzyme' },
  { id: 'sequence', icon: '🧬', title: 'Amino Acid Sequence', description: 'Paste a raw enzyme protein sequence' },
  { id: 'fasta', icon: '📁', title: 'FASTA File', description: 'Upload a FASTA format file containing enzyme sequence' }
]

const selectedMethod = ref(null)
const enzymeUniprot = ref('')
const enzymeSequence = ref('')
const fastaContent = ref('')
const fastaInput = ref(null)
const smiles = ref('')

const loading = ref(false)
const showResult = ref(false)
const result = ref(null)
const error = ref('')

const currentMethodInfo = computed(() => inputMethods.find(m => m.id === selectedMethod.value) || {})
const resultStatus = computed(() => {
  if (error.value) return 'error'
  if (result.value?.is_substrate) return 'success'
  if (result.value?.is_substrate === false) return 'warning'
  return 'info'
})
const resultTitle = computed(() => error.value ? 'Error' : 'Prediction Result')

const selectMethod = (methodId) => { selectedMethod.value = methodId }

const handleFileChange = async (e) => {
  const file = e.target.files[0]
  if (file) fastaContent.value = await file.text()
}

const clearAll = () => {
  enzymeUniprot.value = ''
  enzymeSequence.value = ''
  fastaContent.value = ''
  smiles.value = ''
  if (fastaInput.value) fastaInput.value.value = ''
  showResult.value = false
  // Clear JSME editor
  if (jsmeEditor.value && jsmeReady.value) {
    jsmeEditor.value.clear()
  }
}

const loadEnzymeExample = () => { enzymeUniprot.value = 'P00761' }
const loadSequenceExample = () => {
  enzymeSequence.value = 'IVGGYTCGANTVPYQVSLNSGYHFCGGSLINSQWVVSAAHCYKSGIQVRLGEDNINVVEGNEQFISASKSIVHPSYNSNTLNNDIMLIKLKSAASLNSRVASISLPTSCASAGTQCLISGWGNTKSSGTSYPDVLKCLKAPILSDSSCKSAYPGQITSNMFCAGYLEGGKDSCQGDSGGPVVCSGKLQGIVSWGSGCAQKNKPGVYTKVCNYVSWIKQTIASN'
}

const loadFullExample = () => {
  if (selectedMethod.value === 'uniprot') enzymeUniprot.value = 'P00761'
  else if (selectedMethod.value === 'sequence') loadSequenceExample()
  smiles.value = 'CC(=O)NC(Cc1ccc(O)cc1)C(=O)O'
}

const submit = async () => {
  if (!smiles.value.trim()) {
    error.value = 'Please enter a SMILES string'
    showResult.value = true
    return
  }

  let enzymeInputType = '', enzymeQuery = ''
  if (selectedMethod.value === 'uniprot' && enzymeUniprot.value.trim()) {
    enzymeInputType = 'uniprot'
    enzymeQuery = enzymeUniprot.value.trim()
  } else if (selectedMethod.value === 'sequence' && enzymeSequence.value.trim()) {
    enzymeInputType = 'sequence'
    enzymeQuery = enzymeSequence.value.trim()
  } else if (selectedMethod.value === 'fasta' && fastaContent.value.trim()) {
    enzymeInputType = 'fasta'
    enzymeQuery = fastaContent.value.trim()
  } else {
    error.value = 'Please provide enzyme input'
    showResult.value = true
    return
  }

  loading.value = true
  showResult.value = false
  result.value = null
  error.value = ''

  try {
    const response = await enzymeApi.predictSubstrate({
      smiles: smiles.value.trim(),
      enzyme_input_type: enzymeInputType,
      enzyme_query: enzymeQuery
    })
    if (response.result) result.value = response.result
    else if (response.error) error.value = response.error
    else error.value = 'Unexpected response'
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
    showResult.value = true
  }
}

const copyResult = () => {
  const text = result.value
    ? `Prediction: ${result.value.is_substrate ? 'Is a Substrate' : 'Not a Substrate'}\nConfidence: ${(result.value.confidence * 100).toFixed(2)}%`
    : error.value
  copyToClipboard(text)
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

.btn-group { display: flex; gap: var(--spacing-md); margin-top: var(--spacing-lg); }
.btn-group-sm { display: flex; gap: var(--spacing-sm); margin-top: var(--spacing-md); }
.btn-sm { padding: 6px 12px; font-size: 0.85rem; }
.btn-icon { margin-right: var(--spacing-xs); }

.result-main { display: flex; flex-direction: column; gap: var(--spacing-md); }
.prediction-class {
  font-size: 1.2rem;
  .label { color: var(--color-text-secondary); margin-right: 8px; }
  .value { font-weight: 700; }
  &.is-substrate .value { color: var(--color-success); }
  &.not-substrate .value { color: var(--color-error); }
}
.confidence {
  .label { color: var(--color-text-secondary); margin-right: 8px; }
  .value { background: var(--color-primary-light); color: var(--color-primary); padding: 2px 10px; border-radius: 4px; font-weight: 600; }
}
.result-error { color: var(--color-error); }

.jsme-wrapper-small {
  width: 100%;
  min-height: 320px;
  margin-bottom: var(--spacing-md);
}

.smiles-input-section {
  margin-bottom: var(--spacing-md);
  
  .input-label {
    display: block;
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--color-text-secondary);
    margin-bottom: var(--spacing-xs);
  }
  
  textarea {
    width: 100%;
  }
}

.fade-enter-active, .fade-leave-active { transition: all 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; transform: translateY(10px); }

@media (max-width: 768px) {
  .method-grid { grid-template-columns: 1fr; }
  .form-header { flex-direction: column; gap: var(--spacing-md); align-items: flex-start; }
  .btn-group { flex-wrap: wrap; }
}
</style>
