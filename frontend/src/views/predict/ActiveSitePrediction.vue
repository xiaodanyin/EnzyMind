<template>
  <PageContainer
    title="Active Site Prediction"
    description="Predict active site residues using EasIFA. Identifies catalytic residues, binding sites, and their positions in the enzyme."
  >
    <!-- Input Method Selection -->
    <transition name="fade" mode="out-in">
      <div v-if="!selectedMethod" class="method-selection">
        <h3 class="method-title">Select Input Method</h3>
        <div class="method-grid">
          <div 
            class="method-card"
            v-for="method in inputMethods"
            :key="method.id"
            @click="selectMethod(method.id)"
          >
            <div class="method-icon">{{ method.icon }}</div>
            <div class="method-info">
              <h4>{{ method.title }}</h4>
            </div>
            <div class="method-arrow">→</div>
            <div class="method-tooltip">{{ method.description }}</div>
          </div>
        </div>
      </div>

      <!-- Input Form -->
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

        <!-- UniProt Input -->
        <InputCard v-if="selectedMethod === 'uniprot'" title="UniProt ID" hint="Enter a UniProt accession number">
          <input 
            type="text" 
            v-model="uniprotId" 
            placeholder="e.g., P12345"
            @keyup.enter="submitUniprot"
          />
          <div class="btn-group">
            <button class="btn btn-primary" @click="submitUniprot" :disabled="loading">
              <span class="btn-icon">🎯</span> Predict
            </button>
            <button class="btn btn-secondary" @click="uniprotId = ''">Clear</button>
            <button class="btn btn-outline" @click="loadUniprotExample">Load Example</button>
          </div>
        </InputCard>

        <!-- Sequence Input -->
        <InputCard v-if="selectedMethod === 'sequence'" title="Amino Acid Sequence" hint="Paste a raw protein sequence">
          <textarea 
            v-model="sequence" 
            placeholder="MKFLILLFNILCLFPVLAADNHGVGPQGAS..."
            rows="6"
          ></textarea>
          
          <!-- Collapsible Reaction SMILES Section -->
          <div class="optional-field">
            <button class="toggle-btn" @click="showJsmeSequence = !showJsmeSequence">
              <span class="toggle-icon">{{ showJsmeSequence ? '▼' : '▶' }}</span>
              <span class="label-icon">⚗️</span>
              Reaction SMILES (Optional)
              <span class="toggle-hint">- Click to {{ showJsmeSequence ? 'hide' : 'show' }} reaction editor</span>
            </button>
            
            <transition name="slide">
              <div v-show="showJsmeSequence" class="jsme-section">
                <!-- JSME Editor -->
                <div class="jsme-wrapper">
                  <JSMEEditor
                    v-model="rxnSmiles"
                    container-id="jsme_sequence_editor"
                    height="350px"
                    width="100%"
                    options="oldlook,star,nocanonize,reaction"
                    @jsme-ready="onJSMEReady"
                    ref="jsmeEditorSequence"
                  />
                </div>
                
                <!-- SMILES Text Input -->
                <div class="smiles-text-input">
                  <label class="input-label">Or enter SMILES directly:</label>
                  <input 
                    type="text" 
                    v-model="rxnSmiles" 
                    placeholder="e.g., CC(=O)O.CCO>>CC(=O)OCC.O"
                    class="smiles-input"
                  />
                </div>
                <div class="input-help">
                  <span class="help-icon">💡</span>
                  <span>Providing reaction SMILES can improve prediction accuracy. Use '>>' to separate substrates from products.</span>
                </div>
              </div>
            </transition>
          </div>
          
          <div class="btn-group">
            <button class="btn btn-primary" @click="submitSequence" :disabled="loading">
              <span class="btn-icon">🎯</span> Predict
            </button>
            <button class="btn btn-secondary" @click="clearSequence">Clear</button>
            <button class="btn btn-outline" @click="loadSequenceExample">Load Example</button>
          </div>
        </InputCard>

        <!-- FASTA File Input -->
        <InputCard v-if="selectedMethod === 'fasta'" title="FASTA File" hint="Upload a FASTA format file (.fasta or .fa)">
          <div class="file-upload-area" :class="{ 'has-file': fastaContent }">
            <input 
              type="file" 
              ref="fastaInput"
              accept=".fasta,.fa"
              @change="handleFastaChange"
              class="file-input"
            />
            <div class="file-upload-content">
              <span class="file-icon">📄</span>
              <span class="file-text">{{ fastaContent ? 'File loaded successfully' : 'Click or drag FASTA file here' }}</span>
            </div>
          </div>
          
          <!-- Collapsible Reaction SMILES Section -->
          <div class="optional-field">
            <button class="toggle-btn" @click="showJsmeFasta = !showJsmeFasta">
              <span class="toggle-icon">{{ showJsmeFasta ? '▼' : '▶' }}</span>
              <span class="label-icon">⚗️</span>
              Reaction SMILES (Optional)
              <span class="toggle-hint">- Click to {{ showJsmeFasta ? 'hide' : 'show' }} reaction editor</span>
            </button>
            
            <transition name="slide">
              <div v-show="showJsmeFasta" class="jsme-section">
                <!-- JSME Editor -->
                <div class="jsme-wrapper">
                  <JSMEEditor
                    v-model="rxnSmiles"
                    container-id="jsme_fasta_editor"
                    height="350px"
                    width="100%"
                    options="oldlook,star,nocanonize,reaction"
                    @jsme-ready="onJSMEReady"
                    ref="jsmeEditorFasta"
                  />
                </div>
                
                <!-- SMILES Text Input -->
                <div class="smiles-text-input">
                  <label class="input-label">Or enter SMILES directly:</label>
                  <input 
                    type="text" 
                    v-model="rxnSmiles" 
                    placeholder="e.g., CC(=O)O.CCO>>CC(=O)OCC.O"
                    class="smiles-input"
                  />
                </div>
                <div class="input-help">
                  <span class="help-icon">💡</span>
                  <span>Providing reaction SMILES can improve prediction accuracy. Use '>>' to separate substrates from products.</span>
                </div>
              </div>
            </transition>
          </div>
          
          <div class="btn-group">
            <button class="btn btn-primary" @click="submitFasta" :disabled="loading || !fastaContent">
              <span class="btn-icon">🎯</span> Predict
            </button>
            <button class="btn btn-secondary" @click="clearFasta">Clear</button>
          </div>
        </InputCard>
      </div>
    </transition>

    <ResultBox 
      :show="showResult" 
      :status="resultStatus"
      :title="resultTitle"
      @copy="copyResult"
    >
      <div class="result-main" v-if="result">
        <div class="markdown-content" v-html="renderedMarkdown"></div>
      </div>
      <div class="result-error" v-else-if="error">
        {{ error }}
      </div>
    </ResultBox>

    <LoadingOverlay 
      :show="loading" 
      text="Predicting active sites..."
      hint="This may take several minutes for new predictions"
    />
  </PageContainer>
</template>

<script setup>
import { ref, computed } from 'vue'
import { marked } from 'marked'
import PageContainer from '@/components/layout/PageContainer.vue'
import InputCard from '@/components/common/InputCard.vue'
import ResultBox from '@/components/common/ResultBox.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import JSMEEditor from '@/components/JSMEEditor.vue'
import { enzymeApi } from '@/api'
import { copyToClipboard } from '@/utils/clipboard'

// Input methods configuration
const inputMethods = [
  {
    id: 'uniprot',
    icon: '🔖',
    title: 'UniProt ID',
    description: 'Enter a UniProt accession number for active site prediction'
  },
  {
    id: 'sequence',
    icon: '🧬',
    title: 'Amino Acid Sequence',
    description: 'Paste a raw protein sequence, optionally with reaction SMILES'
  },
  {
    id: 'fasta',
    icon: '📁',
    title: 'FASTA File',
    description: 'Upload a FASTA format file for active site prediction'
  }
]

const selectedMethod = ref(null)
const uniprotId = ref('')
const sequence = ref('')
const rxnSmiles = ref('')
const fastaContent = ref('')
const fastaInput = ref(null)

// JSME editor state
const showJsmeSequence = ref(false)
const showJsmeFasta = ref(false)
const jsmeEditorSequence = ref(null)
const jsmeEditorFasta = ref(null)
const jsmeReady = ref(false)

const loading = ref(false)
const showResult = ref(false)
const result = ref('')
const error = ref('')

const currentMethodInfo = computed(() => {
  return inputMethods.find(m => m.id === selectedMethod.value) || {}
})

const resultStatus = computed(() => {
  if (error.value) return 'error'
  if (result.value) return 'success'
  return 'info'
})

const resultTitle = computed(() => {
  if (error.value) return 'Error'
  return 'Active Sites Prediction Result'
})

const renderedMarkdown = computed(() => {
  if (!result.value) return ''
  return marked(result.value)
})

const selectMethod = (methodId) => {
  selectedMethod.value = methodId
}

// JSME event handler
const onJSMEReady = (event) => {
  jsmeReady.value = event.success
  if (!event.success) {
    console.error('JSME failed to initialize:', event.error)
  }
}

const handleFastaChange = async (event) => {
  const file = event.target.files[0]
  if (file) {
    fastaContent.value = await file.text()
  }
}

const clearSequence = () => {
  sequence.value = ''
  rxnSmiles.value = ''
  // Clear JSME editor if ready
  if (jsmeEditorSequence.value && jsmeReady.value) {
    jsmeEditorSequence.value.clear()
  }
}

const clearFasta = () => {
  fastaContent.value = ''
  rxnSmiles.value = ''
  if (fastaInput.value) {
    fastaInput.value.value = ''
  }
  // Clear JSME editor if ready
  if (jsmeEditorFasta.value && jsmeReady.value) {
    jsmeEditorFasta.value.clear()
  }
}

// Submit functions
const submitUniprot = async () => {
  if (!uniprotId.value.trim()) {
    error.value = 'Please enter a UniProt ID'
    showResult.value = true
    return
  }

  await submitPrediction({ uniprot_id: uniprotId.value.trim() })
}

const submitSequence = async () => {
  if (!sequence.value.trim()) {
    error.value = 'Please enter an amino acid sequence'
    showResult.value = true
    return
  }

  const requestData = { aa_sequence: sequence.value.trim() }
  if (rxnSmiles.value.trim()) {
    requestData.rxn_smiles = rxnSmiles.value.trim()
  }

  await submitPrediction(requestData)
}

const submitFasta = async () => {
  if (!fastaContent.value.trim()) {
    error.value = 'Please upload a FASTA file'
    showResult.value = true
    return
  }

  // Parse FASTA to extract sequence
  const lines = fastaContent.value.trim().split('\n')
  const sequenceLines = lines.filter(line => !line.startsWith('>'))
  const extractedSequence = sequenceLines.join('').replace(/\s/g, '')

  if (!extractedSequence) {
    error.value = 'Could not extract sequence from FASTA file'
    showResult.value = true
    return
  }

  const requestData = { aa_sequence: extractedSequence }
  if (rxnSmiles.value.trim()) {
    requestData.rxn_smiles = rxnSmiles.value.trim()
  }

  await submitPrediction(requestData)
}

const submitPrediction = async (requestData) => {
  loading.value = true
  showResult.value = false
  result.value = ''
  error.value = ''

  try {
    const response = await enzymeApi.predictActiveSites(requestData)

    if (response.result) {
      result.value = response.result
    } else if (response.markdown) {
      result.value = response.markdown
    } else if (response.error) {
      error.value = response.error
    } else {
      error.value = 'No active site data returned'
    }
  } catch (err) {
    error.value = err.message || 'Failed to process request'
  } finally {
    loading.value = false
    showResult.value = true
  }
}

// Load example data
const loadUniprotExample = () => {
  uniprotId.value = 'P00761' // Trypsin - has well-characterized active site residues (His57, Asp102, Ser195)
}

const loadSequenceExample = () => {
  // Example: Adenylate Kinase sequence
  sequence.value = 'MASKLLRAVILGPPGSGKGTVCQRIAQNFGLQHLSSGHFLRENIKASTEVGEVAKQYIEKSLLVPDHVITRLMMSELENRRGQHWLLDGFPRTLGQAEALDKICEVDLVISLNIPFETLKDRLSRRWIHPPSGRVYNLDFNPPHVHGIDDVTGEPLVQQEDDKPEAVAARLRQYKDAAKPVIELYKSRGVLHQFSGTETNKIWPYVYTLFSNKITPIQSKEAY'
  rxnSmiles.value = ''
}

const copyResult = () => {
  copyToClipboard(result.value || error.value)
}
</script>

<style lang="scss" scoped>
// Method Selection Styles
.method-selection {
  animation: fadeIn 0.4s ease-out;
}

.method-title {
  text-align: center;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: var(--spacing-xl);
  
  &::after {
    content: '';
    display: block;
    width: 60px;
    height: 3px;
    background: var(--color-primary-gradient);
    margin: var(--spacing-md) auto 0;
    border-radius: 2px;
  }
}

.method-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--spacing-lg);
  max-width: 900px;
  margin: 0 auto;
}

.method-card {
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
  padding: var(--spacing-lg) var(--spacing-xl);
  background: var(--glass-bg);
  border: 2px solid var(--color-border);
  border-radius: var(--radius-xl);
  cursor: pointer;
  transition: all var(--transition-normal);
  position: relative;
  overflow: visible;
  
  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background: var(--color-primary-gradient);
    opacity: 0;
    transition: opacity var(--transition-normal);
    border-radius: inherit;
  }
  
  &:hover {
    transform: translateY(-4px);
    border-color: var(--color-primary);
    box-shadow: var(--shadow-lg), 0 0 30px rgba(37, 99, 235, 0.15);
    
    &::before {
      opacity: 0.05;
    }
    
    .method-arrow {
      transform: translateX(4px);
      opacity: 1;
    }
    
    .method-icon {
      transform: scale(1.1);
    }
    
    .method-tooltip {
      opacity: 1;
      visibility: visible;
      transform: translateX(-50%) translateY(0);
    }
  }
}

.method-icon {
  font-size: 2.2rem;
  flex-shrink: 0;
  transition: transform var(--transition-normal);
}

.method-info {
  flex: 1;
  
  h4 {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--color-text);
    margin: 0;
  }
}

.method-arrow {
  font-size: 1.3rem;
  color: var(--color-primary);
  opacity: 0.5;
  transition: all var(--transition-fast);
}

.method-tooltip {
  position: absolute;
  bottom: calc(100% + 12px);
  left: 50%;
  transform: translateX(-50%) translateY(8px);
  background: var(--color-text);
  color: white;
  padding: 10px 16px;
  border-radius: var(--radius-lg);
  font-size: 0.85rem;
  line-height: 1.5;
  white-space: nowrap;
  max-width: 280px;
  white-space: normal;
  text-align: center;
  opacity: 0;
  visibility: hidden;
  transition: all var(--transition-fast);
  z-index: 100;
  box-shadow: var(--shadow-lg);
  pointer-events: none;
  
  &::after {
    content: '';
    position: absolute;
    top: 100%;
    left: 50%;
    transform: translateX(-50%);
    border: 8px solid transparent;
    border-top-color: var(--color-text);
  }
}

// Form Header
.input-form {
  animation: fadeIn 0.4s ease-out;
}

.form-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-xl);
  padding-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--color-border);
}

.back-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  font-size: 0.9rem;
  cursor: pointer;
  transition: all var(--transition-fast);
  
  &:hover {
    border-color: var(--color-primary);
    color: var(--color-primary);
    background: var(--color-primary-light);
    
    .back-icon {
      transform: translateX(-3px);
    }
  }
  
  .back-icon {
    transition: transform var(--transition-fast);
  }
}

.method-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-primary-light);
  color: var(--color-primary);
  border-radius: var(--radius-full);
  font-size: 0.9rem;
  font-weight: 600;
}

// Optional Field Styles
.optional-field {
  margin-top: var(--spacing-lg);
  padding-top: var(--spacing-lg);
  border-top: 1px dashed var(--color-border);
}

.field-label {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: var(--spacing-sm);
  
  .label-icon {
    font-size: 1rem;
  }
}

.smiles-input {
  width: 100%;
  padding: var(--spacing-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-family: monospace;
  font-size: 0.9rem;
  transition: all var(--transition-fast);
  
  &:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px var(--color-primary-light);
  }
}

.field-hint {
  display: block;
  margin-top: var(--spacing-xs);
  font-size: 0.8rem;
  color: var(--color-text-secondary);
}

// File Upload
.file-upload-area {
  position: relative;
  border: 2px dashed var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--spacing-xl);
  text-align: center;
  transition: all var(--transition-fast);
  cursor: pointer;
  
  &:hover {
    border-color: var(--color-primary);
    background: var(--color-primary-light);
  }
  
  &.has-file {
    border-color: var(--color-success);
    background: rgba(5, 150, 105, 0.1);
    
    .file-icon {
      color: var(--color-success);
    }
  }
}

.file-input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.file-upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-sm);
  pointer-events: none;
  
  .file-icon {
    font-size: 2.5rem;
  }
  
  .file-text {
    color: var(--color-text-secondary);
    font-size: 0.95rem;
  }
}

// Button group
.btn-group {
  display: flex;
  gap: var(--spacing-md);
  margin-top: var(--spacing-lg);
}

.btn-icon {
  margin-right: var(--spacing-xs);
}

// Result Markdown Styles
.result-main {
  text-align: left;
}

.markdown-content {
  :deep(table) {
    width: 100%;
    border-collapse: collapse;
    margin: var(--spacing-md) 0;
    font-size: 0.9rem;
    
    th, td {
      padding: 12px 16px;
      border: 1px solid var(--color-border);
      text-align: left;
    }
    
    th {
      background: var(--color-primary-light);
      font-weight: 600;
      color: var(--color-primary);
    }
    
    tr:nth-child(even) {
      background: var(--color-bg-secondary);
    }
    
    tr:hover {
      background: var(--color-primary-light);
    }
  }
  
  :deep(h3) {
    color: var(--color-success);
    margin-top: var(--spacing-lg);
    font-size: 1.1rem;
  }
  
  :deep(p) {
    color: var(--color-text-secondary);
    line-height: 1.6;
  }
}

.result-error {
  color: var(--color-error);
  text-align: center;
  padding: var(--spacing-lg);
}

// JSME Toggle Button and Section
.toggle-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  width: 100%;
  padding: var(--spacing-md);
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-text);
  text-align: left;
  transition: all var(--transition-fast);
  border-radius: var(--radius-md);
  
  &:hover {
    background: var(--color-bg-secondary);
  }
  
  .toggle-icon {
    font-size: 0.8rem;
    color: var(--color-primary);
    transition: transform var(--transition-fast);
  }
  
  .label-icon {
    font-size: 1rem;
  }
  
  .toggle-hint {
    font-weight: 400;
    font-size: 0.85rem;
    color: var(--color-text-secondary);
    margin-left: auto;
  }
}

.jsme-section {
  margin-top: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--color-bg-secondary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
}

.jsme-wrapper {
  width: 100%;
  min-height: 370px;
  margin-bottom: var(--spacing-md);
  background: white;
  border-radius: var(--radius-md);
  overflow: hidden;
}

.smiles-text-input {
  margin-bottom: var(--spacing-sm);
  
  .input-label {
    display: block;
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--color-text-secondary);
    margin-bottom: var(--spacing-xs);
  }
}

.input-help {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-primary-light);
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  color: var(--color-text-secondary);
  
  .help-icon {
    flex-shrink: 0;
  }
}

// Slide transition for collapsible sections
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
  margin-top: 0;
  padding: 0;
}

.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 600px;
}

// Transitions
.fade-enter-active,
.fade-leave-active {
  transition: all 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 768px) {
  .method-grid {
    grid-template-columns: 1fr;
  }
  
  .form-header {
    flex-direction: column;
    gap: var(--spacing-md);
    align-items: flex-start;
  }
  
  .btn-group {
    flex-wrap: wrap;
  }
}
</style>
