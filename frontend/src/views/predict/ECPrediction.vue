<template>
  <PageContainer
    title="EC Number Prediction"
    description="Predict the Enzyme Commission (EC) number for a protein sequence to classify its enzymatic function."
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
              <span class="btn-icon">🔬</span> Submit
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
          <div class="btn-group">
            <button class="btn btn-primary" @click="submitSequence" :disabled="loading">
              <span class="btn-icon">🔬</span> Submit
            </button>
            <button class="btn btn-secondary" @click="sequence = ''">Clear</button>
            <button class="btn btn-outline" @click="loadSequenceExample">Load Example</button>
          </div>
        </InputCard>

        <!-- FASTA Input -->
        <InputCard v-if="selectedMethod === 'fasta'" title="FASTA File" hint="Upload a FASTA format file">
          <div class="file-upload-area" :class="{ 'has-file': fastaContent }">
            <input 
              type="file" 
              ref="fastaInput"
              accept=".fasta,.fa"
              @change="handleFileChange"
              class="file-input"
            />
            <div class="file-upload-content">
              <span class="file-icon">📄</span>
              <span class="file-text">{{ fastaContent ? 'File loaded successfully' : 'Click or drag file here' }}</span>
            </div>
          </div>
          <div class="btn-group">
            <button class="btn btn-primary" @click="submitFasta" :disabled="loading || !fastaContent">
              <span class="btn-icon">🔬</span> Submit
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
      <div class="result-main" v-if="ecNumber">
        <div class="ec-result">
          <span class="ec-label">Predicted EC Number:</span>
          <span class="ec-value">{{ ecNumber }}</span>
        </div>
      </div>
      <div class="result-error" v-else-if="error">
        {{ error }}
      </div>
    </ResultBox>

    <LoadingOverlay 
      :show="loading" 
      text="Predicting EC number..."
      hint="This may take a few seconds"
    />
  </PageContainer>
</template>

<script setup>
import { ref, computed } from 'vue'
import PageContainer from '@/components/layout/PageContainer.vue'
import InputCard from '@/components/common/InputCard.vue'
import ResultBox from '@/components/common/ResultBox.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import { enzymeApi } from '@/api'
import { copyToClipboard } from '@/utils/clipboard'

// Input methods configuration
const inputMethods = [
  {
    id: 'uniprot',
    icon: '🔖',
    title: 'UniProt ID',
    description: 'Enter a UniProt accession number for EC number prediction'
  },
  {
    id: 'sequence',
    icon: '🧬',
    title: 'Amino Acid Sequence',
    description: 'Paste a raw protein sequence for analysis'
  },
  {
    id: 'fasta',
    icon: '📁',
    title: 'FASTA File',
    description: 'Upload a FASTA format file for batch processing'
  }
]

const selectedMethod = ref(null)
const uniprotId = ref('')
const sequence = ref('')
const fastaContent = ref('')
const fastaInput = ref(null)

const loading = ref(false)
const showResult = ref(false)
const ecNumber = ref('')
const error = ref('')

const currentMethodInfo = computed(() => {
  return inputMethods.find(m => m.id === selectedMethod.value) || {}
})

const resultStatus = computed(() => {
  if (error.value) return 'error'
  if (ecNumber.value) return 'success'
  return 'info'
})

const resultTitle = computed(() => {
  if (error.value) return 'Error'
  return 'Prediction Result'
})

const selectMethod = (methodId) => {
  selectedMethod.value = methodId
}

const handleFileChange = async (event) => {
  const file = event.target.files[0]
  if (file) {
    fastaContent.value = await file.text()
  }
}

const clearFasta = () => {
  fastaContent.value = ''
  if (fastaInput.value) {
    fastaInput.value.value = ''
  }
}

const submitPrediction = async (inputType, query) => {
  if (!query.trim()) {
    error.value = 'Please provide input data'
    showResult.value = true
    return
  }

  loading.value = true
  showResult.value = false
  ecNumber.value = ''
  error.value = ''

  try {
    const response = await enzymeApi.predictEC({
      input_type: inputType,
      query: query.trim()
    })
    
    if (response.result?.ec_number) {
      ecNumber.value = response.result.ec_number
    } else if (response.error) {
      error.value = response.error
    } else {
      error.value = 'No EC number prediction available'
    }
  } catch (err) {
    error.value = err.message || 'Failed to process request'
  } finally {
    loading.value = false
    showResult.value = true
  }
}

const submitUniprot = () => submitPrediction('uniprot', uniprotId.value)
const submitSequence = () => submitPrediction('sequence', sequence.value)
const submitFasta = () => submitPrediction('fasta', fastaContent.value)

// Load example data
const loadUniprotExample = () => {
  uniprotId.value = 'P00761' // Trypsin - EC 3.4.21.4
}

const loadSequenceExample = () => {
  // Example: Trypsin sequence
  sequence.value = 'IVGGYTCGANTVPYQVSLNSGYHFCGGSLINSQWVVSAAHCYKSGIQVRLGEDNINVVEGNEQFISASKSIVHPSYNSNTLNNDIMLIKLKSAASLNSRVASISLPTSCASAGTQCLISGWGNTKSSGTSYPDVLKCLKAPILSDSSCKSAYPGQITSNMFCAGYLEGGKDSCQGDSGGPVVCSGKLQGIVSWGSGCAQKNKPGVYTKVCNYVSWIKQTIASN'
}

const copyResult = () => {
  const text = ecNumber.value ? `EC Number: ${ecNumber.value}` : error.value
  copyToClipboard(text)
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

// Result styles
.result-main {
  text-align: center;
}

.ec-result {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  
  .ec-label {
    color: var(--color-text-secondary);
    font-weight: 500;
    font-size: 1rem;
  }
  
  .ec-value {
    font-size: 2rem;
    font-weight: 700;
    color: var(--color-success);
  }
}

.ec-hint {
  margin-top: var(--spacing-lg);
  
  a {
    color: var(--color-primary);
    font-weight: 500;
    
    &:hover {
      text-decoration: underline;
    }
  }
}

.result-error {
  color: var(--color-error);
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
